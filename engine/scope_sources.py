"""Bridge current RSS ingestion revisions to local scope-review source epochs.

Poll freshness is not full-article freshness or proof of publisher availability.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_items, news_revisions, news_sources
from engine.scope_review import Store

MAX_POLL_AGE_SECONDS = 3600


def inspect(conn, selection, at):
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Nonfuture aware lifecycle cutoff required")
    supplied = selection["revision"]
    supplied_at = datetime.fromisoformat(supplied["received_at"])
    if supplied_at.tzinfo is None:
        raise ValueError("Aware pinned ingestion timestamp required")
    revision = (
        conn.execute(select(news_revisions).where(news_revisions.c.id == supplied["id"]))
        .mappings()
        .first()
    )
    if (
        revision is None
        or digest(revision["payload"]) != digest(supplied["payload"])
        or (utc(revision["received_at"]) != supplied_at)
    ):
        raise ValueError("Pinned ingestion revision missing or altered")
    item = (
        conn.execute(select(news_items).where(news_items.c.id == revision["item_id"]))
        .mappings()
        .one()
    )
    rows = (
        conn.execute(
            select(news_revisions)
            .where(news_revisions.c.item_id == item["id"])
            .order_by(news_revisions.c.version)
            .limit(10001)
        )
        .mappings()
        .all()
    )
    if len(rows) > 10000 or [r["version"] for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("Incomplete ingestion revision history")
    latest = rows[-1]
    if (
        latest["version"] != item["version"]
        or digest(latest["payload"]) != item["content_sha256"]
        or digest(item["payload"]) != item["content_sha256"]
        or any(utc(r["received_at"]) > at for r in rows)
        or [utc(r["received_at"]) for r in rows] != sorted(utc(r["received_at"]) for r in rows)
    ):
        raise ValueError("Inconsistent or future current ingestion state")
    source = (
        conn.execute(select(news_sources).where(news_sources.c.id == item["source_id"]))
        .mappings()
        .one()
    )
    if source["config"].get("kind") != "rss":
        raise ValueError("R05 ingestion bridge v1 supports RSS sources only")
    fingerprint = digest(
        {
            "source": source["id"],
            "source_url": source["config"].get("url"),
            "source_kind": source["config"].get("kind"),
            "item": item["id"],
            "revisions": [
                [r["id"], r["version"], digest(r["payload"]), utc(r["received_at"]).isoformat()]
                for r in rows
            ],
        }
    )
    fresh = (
        source["config"].get("enabled") is True
        and source["failures"] == 0
        and source["last_success"] is not None
        and 0 <= (at - utc(source["last_success"])).total_seconds() <= MAX_POLL_AGE_SECONDS
    )
    return {
        "registry_sha256": fingerprint,
        "status": "CURRENT" if latest["id"] == revision["id"] else "DISPUTED",
        "fresh": fresh,
        "latest_revision_id": latest["id"],
        "max_poll_age_seconds": MAX_POLL_AGE_SECONDS,
        "basis": "INGESTION_REVISION_AND_RSS_POLL_NOT_FULL_ARTICLE_REVALIDATION",
    }


def sync(store, conn, selection, at):
    state = inspect(conn, selection, at)
    sid = selection["revision"]["id"]
    history = store.history("source", sid)
    old = history[-1] if history else None
    payload = {
        "packet_sha256": selection["packet_sha256"],
        "status": state["status"],
        "registry_sha256": state["registry_sha256"],
        "observed_at": at.isoformat(),
    }
    # An ingest poll cannot revoke an explicit operator withdrawal/dispute.
    if old and old["payload"]["status"] in {"WITHDRAWN", "DISPUTED"}:
        payload["status"] = old["payload"]["status"]
    fields = ["packet_sha256", "status", "registry_sha256"]
    if old is None or any(old["payload"].get(k) != payload[k] for k in fields):
        store.append("source", sid, payload, expected_head=old["sha256"] if old else None)
    return state


def main():
    from engine.db import database
    from engine.news_articles import read_packet
    from engine.settings import Settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--articles", type=Path, required=True)
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    read_packet(selection["revision"], selection["packet_sha256"], root=args.articles)
    engine = database(Settings.from_env().database_url)
    try:
        with engine.connect() as conn:
            result = sync(Store(args.store), conn, selection, datetime.now(UTC))
    finally:
        engine.dispose()
    print(json.dumps({**result, "delivery": "disabled"}))


if __name__ == "__main__":
    main()
