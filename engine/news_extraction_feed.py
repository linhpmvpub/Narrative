"""Explicitly unverified extraction feed; never a canonical or impact input."""

from datetime import UTC, datetime

from sqlalchemy import select

from engine.ingestion.contracts import digest
from engine.ingestion.reviewed import sources
from engine.models.schema_v13 import news_items, news_revisions
from engine.news_articles import evidence
from engine.news_numeric_candidates import candidates
from engine.settings import Settings


def extraction_feed(conn):
    if not Settings.from_env().dev_informational_feed:
        return {"enabled": False, "items": [], "delivery": "disabled"}
    rows = (
        conn.execute(
            select(news_revisions)
            .join(news_items, news_items.c.id == news_revisions.c.item_id)
            .where(news_items.c.version == news_revisions.c.version)
            .order_by(news_revisions.c.received_at.desc(), news_revisions.c.id)
            .limit(201)
        )
        .mappings()
        .all()
    )
    blocked_ids = set(
        conn.scalars(select(sources.c.id).where(sources.c.rights_status == "blocked"))
    )
    blocked_urls = {
        r["payload"]["url"]
        for r in conn.execute(
            select(news_revisions).where(
                news_revisions.c.id.in_(
                    [
                        x.removeprefix("news-reviewed:")
                        for x in blocked_ids
                        if x.startswith("news-reviewed:")
                    ]
                )
            )
        ).mappings()
    }
    output, seen, withheld = [], set(), 0
    for row in rows[:200]:
        if row["payload"]["url"] in blocked_urls:
            withheld += 1
            continue
        packets = evidence(row)
        if packets["truncated"] or any(
            p["status"] != "INTEGRITY_CHECKED_UNREVIEWED" for p in packets["items"]
        ):
            withheld += 1
            continue
        latest: dict[tuple, dict] = {}
        for packet in packets["items"]:
            key = (packet["url"], packet["relation"])
            if key not in latest or packet["retrieved_at"] > latest[key]["retrieved_at"]:
                latest[key] = packet
        for packet in latest.values():
            try:
                extracted = candidates(row, packet["packet_sha256"])
            except (ValueError, OSError, KeyError, TypeError):
                withheld += 1
                continue
            for candidate in extracted["items"]:
                entry_key = digest([packet["url"], candidate["fields"]])
                if entry_key in seen:
                    continue
                seen.add(entry_key)
                output.append(
                    {
                        "id": entry_key,
                        "status": "UNVERIFIED_EXTRACTION",
                        "source_url": packet["url"],
                        "source_relation": packet["relation"],
                        "available_at": packet["retrieved_at"],
                        "source_sha256": packet["body_sha256"],
                        "fields": candidate["fields"],
                        "currency_symbol": candidate["currency_symbol"],
                        "currency": "UNKNOWN",
                        "period_normalization": "UNRESOLVED",
                        "scope": "UNVERIFIED",
                        "impact_eligible": False,
                        "graph_eligible": False,
                    }
                )
    return {
        "enabled": True,
        "as_of": datetime.now(UTC).isoformat(),
        "items": output[:100],
        "truncated": len(rows) > 200 or len(output) > 100,
        "withheld_count": withheld,
        "verification": "UNVERIFIED_EXTRACTION_ONLY",
        "delivery": "disabled",
    }
