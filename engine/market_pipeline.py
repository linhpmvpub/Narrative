"""Local bounded market collection, profile coverage, and pinned extraction queue."""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

from engine.company_profiles import available_bundles
from engine.db import database
from engine.ingestion.contracts import digest
from engine.local_worker_lock import worker_lock
from engine.market_discovery import coverage, prioritize, profile_plan
from engine.market_sources import MarketClient
from engine.models.schema_v13 import news_items, news_revisions, news_sources
from engine.news import poll, register, status
from engine.news_articles import HOSTS, capture, read_packet
from engine.settings import Settings


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def collect_due(engine, factory, *, workers=4, budget=40, delay=0.5):
    if not 1 <= workers <= 4 or not 1 <= budget <= 100 or delay < 0.5:
        raise ValueError("Bounded workers, source budget and host delay required")
    now = datetime.now(UTC)
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(news_sources)
                .where(news_sources.c.next_poll_at <= now)
                .order_by(news_sources.c.next_poll_at, news_sources.c.id)
            )
            .mappings()
            .all()
        )
    groups: dict[str, list[str]] = {}
    for row in [r for r in rows if r["config"]["enabled"]][:budget]:
        host = urlsplit(row["config"].get("url", "https://api.x.com")).hostname
        groups.setdefault(host or "unknown", []).append(row["id"])

    def run(ids):
        client = factory()
        try:
            results = []
            for index, source_id in enumerate(ids):
                if index:
                    time.sleep(delay)
                results.extend(poll(engine, client, source_ids=[source_id], max_sources=1))
            return results
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return [r for result in pool.map(run, groups.values()) for r in result]


def inbox_rows(engine, *, limit=10000, days=30):
    if not 1 <= limit <= 10000 or not 1 <= days <= 90:
        raise ValueError("Bounded inbox window required")
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(
                    news_items.c.id.label("item_id"),
                    news_items.c.version,
                    news_items.c.article_key,
                    news_items.c.source_id,
                    news_items.c.payload,
                    news_revisions.c.id.label("revision_id"),
                    news_revisions.c.capture_sha256,
                    news_revisions.c.received_at,
                )
                .join(
                    news_revisions,
                    (news_revisions.c.item_id == news_items.c.id)
                    & (news_revisions.c.version == news_items.c.version),
                )
                .where(news_revisions.c.received_at >= datetime.now(UTC) - timedelta(days=days))
                .order_by(news_revisions.c.received_at.desc(), news_items.c.id)
                .limit(limit + 1)
            )
            .mappings()
            .all()
        )
    return rows[:limit], len(rows) > limit


def extract_queue(engine, queue, root, factory, budget):
    if not 0 <= budget <= 20:
        raise ValueError("Article budget must be 0..20")
    counts = {
        "captured": 0,
        "already_captured": 0,
        "failed": 0,
        "host_held": 0,
        "retry_held": 0,
        "superseded": 0,
    }
    attempts = 0
    client = factory()
    try:
        for item in queue:
            key = digest([item["revision_id"], item["payload_sha256"]])
            path = root / "queue-state" / (key + ".json")
            state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            with engine.connect() as conn:
                revision = (
                    conn.execute(
                        select(news_revisions)
                        .join(
                            news_items,
                            (news_revisions.c.item_id == news_items.c.id)
                            & (news_revisions.c.version == news_items.c.version),
                        )
                        .where(news_revisions.c.id == item["revision_id"])
                    )
                    .mappings()
                    .first()
                )
            if not revision or digest(revision["payload"]) != item["payload_sha256"]:
                counts["superseded"] += 1
                continue
            if state.get("packet_sha256"):
                try:
                    read_packet(revision, state["packet_sha256"])
                    counts["already_captured"] += 1
                    continue
                except (OSError, ValueError, KeyError, TypeError):
                    counts["failed"] += 1
                    continue  # preserve corruption; do not repair evidence silently
            if state.get("retry_at") and datetime.fromisoformat(state["retry_at"]) > datetime.now(
                UTC
            ):
                counts["retry_held"] += 1
                continue
            if urlsplit(item["url"]).hostname not in HOSTS:
                counts["host_held"] += 1
                continue
            if attempts >= budget:
                break
            attempts += 1
            try:
                packet = capture(revision, client)
                state = {
                    "status": "CAPTURED_UNREVIEWED",
                    "packet_sha256": packet["packet_sha256"],
                    "attempted_at": datetime.now(UTC).isoformat(),
                }
                counts["captured"] += 1
            except (OSError, ValueError, KeyError, TypeError) as exc:
                state = {
                    "status": "CAPTURE_FAILED",
                    "error_type": type(exc).__name__,
                    "retry_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                }
                counts["failed"] += 1
            except Exception as exc:
                # Network adapter's FetchError carries no URL/token in public reports.
                from engine.adapters.news import FetchError

                if not isinstance(exc, FetchError):
                    raise
                state = {
                    "status": exc.status,
                    "retry_at": (
                        datetime.now(UTC) + timedelta(seconds=max(300, exc.retry))
                    ).isoformat(),
                }
                counts["failed"] += 1
            save(path, state)
            time.sleep(0.5)
    finally:
        client.close()
    return counts


def cycle(engine, configs, policy, root, factory, *, workers=4, capture_budget=8):
    Settings.from_env()
    register(engine, configs)
    attempts = collect_due(engine, factory, workers=workers)
    registry = available_bundles()
    plan = profile_plan(registry, policy)
    rows, truncated = inbox_rows(engine)
    queue = prioritize(rows, plan, policy, limit=50)
    for item in queue:
        save(
            root / "queue" / (digest([item["revision_id"], item["payload_sha256"]]) + ".json"), item
        )
    save(root / "current-queue.json", queue)
    save(root / "profile-plan.json", plan)
    extraction = extract_queue(engine, queue, root, factory, capture_budget)
    health = status(engine)
    report = {
        "schema": "LOCAL_MARKET_CYCLE_V1",
        "at": datetime.now(UTC).isoformat(),
        "policy_sha256": digest(policy),
        "catalog_sha256": digest(configs),
        "poll_attempts": attempts,
        "sources": health,
        "coverage": coverage(rows, plan, policy),
        "inbox_truncated": truncated,
        "rows_scanned": len(rows),
        "queue_size": len(queue),
        "extraction": extraction,
        "profile_gaps": [c for c in plan["companies"] if not c["ready"]],
        "profiles_complete": plan["profiles_complete"],
        "delivery": "disabled",
        "canonical_events_created": 0,
        "graph_modified": False,
        "release_ready": False,
    }
    name = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json"
    save(root / "runs" / name, report)
    save(root / "latest.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/news-sources-v1.json"))
    parser.add_argument("--policy", type=Path, default=Path("config/product-v1.json"))
    parser.add_argument("--root", type=Path, default=Path("source-cache/product-v1-pipeline"))
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--capture-budget", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 1440 or not 30 <= args.interval <= 3600:
        parser.error("cycles1..1440 and interval30..3600 required")
    os.environ["NEWS_ARTICLE_DIR"] = str(args.root / "articles")
    configs = json.loads(args.config.read_text(encoding="utf-8"))
    configs = [{**c, "enabled": False} if c["kind"] == "x" else c for c in configs]
    policy = json.loads(args.policy.read_text(encoding="utf-8"))

    def factory():
        return MarketClient(user_agent=args.user_agent, capture_dir=args.root / "feed-captures")

    engine = database()
    try:
        with worker_lock(args.root):
            for index in range(args.cycles):
                if index:
                    time.sleep(args.interval)
                r = cycle(
                    engine, configs, policy, args.root, factory, capture_budget=args.capture_budget
                )
                print(
                    json.dumps(
                        {
                            "at": r["at"],
                            "sources_polled": len(r["poll_attempts"]),
                            "coverage": r["coverage"],
                            "extraction": r["extraction"],
                            "delivery": "disabled",
                        }
                    ),
                    flush=True,
                )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
