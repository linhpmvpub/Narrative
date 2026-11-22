"""Allowlisted shared news cards; no private review notes or historical replay."""

from datetime import UTC, datetime

from engine.news_snapshot import snapshot
from engine.settings import Settings


def reviewed_feed(conn, limit=100):
    now = datetime.now(UTC)
    base = dict(
        as_of=now,
        delivery="disabled",
        mode="REVIEWED_INFORMATIONAL_NEWS",
        impact_eligible=False,
        graph_eligible=False,
        items=[],
        truncated=False,
        examined=0,
        withheld_count=0,
    )
    if not Settings.from_env().dev_informational_feed:
        return {**base, "enabled": False}
    result = snapshot(conn, now, limit)
    cards = []
    for item in result["items"]:
        claim = item["claim"]
        cards.append(
            {
                "event_id": item["event_id"],
                "event_version_id": item["event_version_id"],
                "version": item["version"],
                "headline": item["headline"],
                "excerpt": claim["claim_text"],
                "source_url": item["source_url"],
                "source_revision_id": item["source_revision_id"],
                "source_payload_sha256": item["source_payload_sha256"],
                "published_at": item["published_at"],
                "captured_at": item["captured_at"],
                "available_at": item["available_at"],
                "author_kind": item["author_kind"],
                "reviewer_kind": item["reviewer_kind"],
                "measurement": {
                    k: claim.get(k)
                    for k in (
                        "metric_id",
                        "unit",
                        "period",
                        "old_value",
                        "new_value",
                        "old_basis",
                        "new_basis",
                    )
                },
                "comparison_period": item["comparison_period"],
                "verification": "REVIEWED_EXCERPT_NOT_CAUSAL_VALIDATION",
                "source_rights": item["source_rights"],
                "materiality": "UNKNOWN",
                "impact_eligible": False,
                "graph_eligible": False,
            }
        )
    return {
        **base,
        "enabled": True,
        "items": cards,
        "truncated": result["truncated"],
        "examined": result["examined"],
        "withheld_count": len(result["withheld"]),
    }
