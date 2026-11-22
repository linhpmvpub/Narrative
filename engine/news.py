"""Durable polling worker for a private, unverified market-news inbox."""

import argparse
import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_, select, update

from engine.adapters.news import FetchError, NewsClient, canonical_url
from engine.db import database
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_items as items
from engine.models.schema_v13 import news_revisions as revisions
from engine.models.schema_v13 import news_sources as sources
from engine.settings import Settings

ALIASES = {
    "MU": r"micron",
    "NVDA": r"nvidia",
    "AMD": r"advanced micro devices|\bAMD\b",
    "DELL": r"\bdell\b",
    "SNDK": r"sandisk",
}


def register(engine, configs):
    if len({c["id"] for c in configs}) != len(configs):
        raise ValueError("Duplicate source ID")
    for c in configs:
        if not re.fullmatch(r"[a-z0-9_-]{1,60}", c["id"]) or c["kind"] not in {"rss", "x"}:
            raise ValueError("Invalid source")
        if not 60 <= c["interval_seconds"] <= 86400:
            raise ValueError("Poll interval outside limits")
        if c["kind"] == "rss":
            if not canonical_url(c["url"]).startswith("https://"):
                raise ValueError("RSS transport requires HTTPS")
        elif not re.fullmatch(r"[A-Za-z0-9_]{1,15}", c["handle"]):
            raise ValueError("Invalid X handle")
    with engine.begin() as conn:
        for config in configs:
            old = (
                conn.execute(select(sources).where(sources.c.id == config["id"])).mappings().first()
            )
            if not old:
                conn.execute(
                    sources.insert().values(
                        id=config["id"],
                        config=config,
                        state={},
                        next_poll_at=datetime.now(UTC),
                        failures=0,
                        last_status="NEVER_POLLED" if config["enabled"] else "DISABLED",
                    )
                )
            else:
                # Changing identity under a durable cursor would lose/reassign posts.
                key = "url" if old["config"]["kind"] == "rss" else "handle"
                if old["config"]["kind"] != config["kind"] or old["config"].get(key) != config.get(
                    key
                ):
                    raise ValueError("Source identity changed; use a new source ID")
                conn.execute(
                    update(sources).where(sources.c.id == config["id"]).values(config=config)
                )


def claim(engine, source_id, now):
    lease = str(uuid4())
    with engine.begin() as conn:
        changed = conn.execute(
            update(sources)
            .where(
                sources.c.id == source_id,
                sources.c.next_poll_at <= now,
                or_(sources.c.lease_until.is_(None), sources.c.lease_until <= now),
            )
            .values(lease_id=lease, lease_until=now + timedelta(minutes=5), last_attempt=now)
        )
        if not changed.rowcount:
            return None
        return dict(conn.execute(select(sources).where(sources.c.id == source_id)).mappings().one())


def save_rows(conn, source, rows, capture_hash, now):
    counts = {"created": 0, "updated": 0, "duplicates": 0}
    for row in rows:
        payload = {
            **row,
            "source_name": source["config"]["name"],
            "kind": source["config"]["kind"],
            "category": source["config"]["category"],
            "verification": "UNVERIFIED_NEWS",
            "impact": "UNKNOWN",
            "graph_eligible": False,
        }
        text = row["title"] + " " + row["summary"]
        payload["ticker_mentions"] = [
            ticker
            for ticker, pattern in ALIASES.items()
            if re.search(pattern, text, re.I) or re.search(r"\$" + ticker + r"\b", text)
        ]
        key = digest([source["id"], row["external_id"]])
        content_hash = digest(payload)
        old = conn.execute(select(items).where(items.c.id == key)).mappings().first()
        if old and old["content_sha256"] == content_hash:
            counts["duplicates"] += 1
            continue
        version = old["version"] + 1 if old else 1
        values = {
            "payload": payload,
            "content_sha256": content_hash,
            "version": version,
            "article_key": digest(canonical_url(row["url"])),
        }
        if old:
            conn.execute(update(items).where(items.c.id == key).values(**values))
            counts["updated"] += 1
        else:
            conn.execute(
                items.insert().values(
                    id=key,
                    source_id=source["id"],
                    external_id=row["external_id"],
                    first_seen_at=now,
                    **values,
                )
            )
            counts["created"] += 1
        conn.execute(
            revisions.insert().values(
                id=str(uuid4()),
                item_id=key,
                version=version,
                received_at=now,
                capture_sha256=capture_hash,
                payload=payload,
            )
        )
    return counts


def poll(engine, client, *, now=None):
    Settings.from_env()
    explicit_now = now
    now = now or datetime.now(UTC)
    with engine.connect() as conn:
        configs = conn.execute(select(sources)).mappings().all()
    results = []
    for config in configs:
        now = explicit_now or datetime.now(UTC)
        if not config["config"]["enabled"]:
            continue
        source = claim(engine, config["id"], now)
        if not source:
            continue
        try:
            rows, state, sha, status, rejected = client.fetch(
                source["config"], source["state"], now
            )
            now = explicit_now or datetime.now(UTC)
            counts = {}
            with engine.begin() as conn:
                current = (
                    conn.execute(
                        select(sources).where(sources.c.id == source["id"]).with_for_update()
                    )
                    .mappings()
                    .one()
                )
                if current["lease_id"] != source["lease_id"]:
                    continue  # A newer worker owns this source; never overwrite its checkpoint.
                counts = save_rows(conn, source, rows, sha, now)
                conn.execute(
                    update(sources)
                    .where(sources.c.id == source["id"])
                    .values(
                        state=state,
                        failures=0,
                        last_status=status,
                        last_success=now,
                        next_poll_at=now + timedelta(seconds=source["config"]["interval_seconds"]),
                        lease_id=None,
                        lease_until=None,
                    )
                )
            results.append(
                {"source_id": source["id"], "status": status, "rejected": rejected, **counts}
            )
        except (FetchError, ValueError, KeyError, TypeError) as exc:
            status = exc.status if isinstance(exc, FetchError) else "INVALID_SOURCE_RESPONSE"
            failures = source["failures"] + 1
            retry = max(
                source["config"]["interval_seconds"],
                min(3600, 60 * 2 ** min(failures, 6)),
                exc.retry if isinstance(exc, FetchError) else 0,
            )
            with engine.begin() as conn:
                conn.execute(
                    update(sources)
                    .where(sources.c.id == source["id"], sources.c.lease_id == source["lease_id"])
                    .values(
                        failures=failures,
                        last_status=status,
                        next_poll_at=now + timedelta(seconds=retry),
                        lease_id=None,
                        lease_until=None,
                    )
                )
            results.append({"source_id": source["id"], "status": status})
    return results


def status(engine):
    now = datetime.now(UTC)
    with engine.connect() as conn:
        rows = conn.execute(select(sources)).mappings().all()
    return [
        {
            "id": r["id"],
            "name": r["config"]["name"],
            "kind": r["config"]["kind"],
            "enabled": r["config"]["enabled"],
            "category": r["config"]["category"],
            "interval_seconds": r["config"]["interval_seconds"],
            "status": r["last_status"] if r["config"]["enabled"] else "DISABLED",
            "last_success": utc(r["last_success"]) if r["last_success"] else None,
            "last_attempt": utc(r["last_attempt"]) if r["last_attempt"] else None,
            "next_poll_at": utc(r["next_poll_at"]),
            "stale": r["last_success"] is None
            or (now - utc(r["last_success"])).total_seconds()
            > max(600, r["config"]["interval_seconds"] * 3),
        }
        for r in rows
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/news-sources.json"))
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=Path(os.getenv("NEWS_CAPTURE_DIR", "source-cache/rss-captures")),
    )
    args = parser.parse_args()
    Settings.from_env()
    engine = database()
    configs = json.loads(args.config.read_text(encoding="utf-8"))
    if os.getenv("NEWS_ENABLE_X", "false") != "true":
        configs = [{**c, "enabled": False} if c["kind"] == "x" else c for c in configs]
    register(engine, configs)
    token = os.getenv("X_BEARER_TOKEN") if os.getenv("NEWS_ENABLE_X") == "true" else None
    client = NewsClient(token=token, capture_dir=args.capture_dir)
    try:
        while True:
            result = poll(engine, client)
            if result:
                print(
                    json.dumps(
                        {
                            "polled_at": datetime.now(UTC).isoformat(),
                            "results": result,
                            "delivery": "disabled",
                        }
                    ),
                    flush=True,
                )
            if args.once:
                break
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()
        engine.dispose()


if __name__ == "__main__":
    main()
