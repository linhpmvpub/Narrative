"""Bounded, explainable news grouping. A cluster is a review candidate, not a fact."""

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import func, select

from engine.adapters.news import canonical_url
from engine.db import database
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_revisions
from engine.settings import Settings

VERSION = "news-grouping-v1"
STOP = set(
    "a an the to of in on for and or with from by at as is are says said new latest update news why how what this that it its after before".split()
)
FAMILIES = {
    "earnings": r"\b(earnings|revenue|profit|quarterly results|guidance)\b",
    "acquisition": r"\b(acquisition|acquires?|merger|takeover|buyout)\b",
    "legal": r"\b(lawsuit|sues?|court|antitrust|settlement)\b",
    "monetary_policy": r"\b(interest rates?|rate cut|rate hike|fomc|monetary policy)\b",
    "trade_policy": r"\b(tariffs?|export controls?|export ban)\b",
    "product": r"\b(launches?|unveils?|introduces?)\b",
}
PUBLISHERS = {
    "cnbc.com": ("CNBC", "publisher"),
    "marketwatch.com": ("Dow Jones", "publisher"),
    "wsj.com": ("Dow Jones", "publisher"),
    "federalreserve.gov": ("Federal Reserve", "primary_institution"),
    "ecb.europa.eu": ("ECB", "primary_institution"),
}
X_PUBLISHERS = {
    "cnbc": "CNBC",
    "reuters": "Reuters",
    "business": "Bloomberg",
    "yahoofinance": "Yahoo",
}


def publisher(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if host == "x.com":
        handle = parsed.path.strip("/").split("/")[0].lower()
        return X_PUBLISHERS.get(handle, "unknown"), "social"
    for domain, group in PUBLISHERS.items():
        if host == domain or host.endswith("." + domain):
            return group
    # Unknown domains are not assumed independent from one another.
    return "unknown", "unknown"


def features(row):
    p = row["payload"]
    title = p["title"].casefold()
    tokens = set(re.findall(r"[a-z][a-z0-9]+", title)) - STOP
    families = {k for k, pattern in FAMILIES.items() if re.search(pattern, title)}
    numbers = set(re.findall(r"\b\d+(?:[.,]\d+)*(?:%|\s*(?:billion|million|basis points))?", title))
    direction = set()
    if re.search(
        r"\b(rises?|rose|raises?|raised|increases?|increased|hikes?|higher|growth)\b", title
    ):
        direction.add("up")
    if re.search(r"\b(falls?|fell|cuts?|lower|declines?|declined|decreases?|decreased)\b", title):
        direction.add("down")
    return {
        "tokens": tokens,
        "families": families,
        "numbers": numbers,
        "direction": direction,
        "tickers": set(p.get("ticker_mentions", [])),
        "url": canonical_url(p["url"]),
        "when": datetime.fromisoformat(p["published_at"]) if p.get("published_at") else None,
    }


def related(a, b):
    if a["url"] == b["url"]:
        return "SAME_ARTICLE_URL"
    if not a["when"] or not b["when"] or abs((a["when"] - b["when"]).total_seconds()) > 48 * 3600:
        return None
    if a["tickers"] and b["tickers"] and not a["tickers"] & b["tickers"]:
        return None
    shared = a["tokens"] & b["tokens"]
    union = a["tokens"] | b["tokens"]
    similarity = len(shared) / len(union) if union else 0
    if len(shared) >= 5 and similarity >= 0.8:
        return "NEAR_IDENTICAL_HEADLINE"
    if (
        a["tickers"] & b["tickers"]
        and a["families"] & b["families"]
        and len(shared) >= 4
        and similarity >= 0.55
    ):
        return "SHARED_ISSUER_EVENT_AND_HEADLINE"
    return None


def snapshot_rows(engine, cutoff, limit=500):
    if cutoff.tzinfo is None or cutoff > datetime.now(UTC):
        raise ValueError("Aware, non-future cutoff required")
    ranked = (
        select(
            news_revisions,
            func.row_number()
            .over(partition_by=news_revisions.c.item_id, order_by=news_revisions.c.version.desc())
            .label("rank"),
        )
        .where(news_revisions.c.received_at <= cutoff)
        .subquery()
    )
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(ranked)
                .where(ranked.c.rank == 1)
                .order_by(ranked.c.received_at.desc(), ranked.c.item_id)
                .limit(limit + 1)
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows[:limit]], len(rows) > limit


def build(rows, cutoff, *, truncated=False):
    # First-fit complete-link: every pair must match. No transitive similarity bridges.
    ordered = sorted(rows, key=lambda r: r["item_id"])
    groups: list[list[dict]] = []
    extracted = {r["item_id"]: features(r) for r in ordered}
    for row in ordered:
        for group in groups:
            if all(
                related(extracted[row["item_id"]], extracted[other["item_id"]]) for other in group
            ):
                group.append(row)
                break
        else:
            groups.append([row])
    clusters = []
    for group in groups:
        evidence, reasons, flags = [], set(), set()
        for i, row in enumerate(group):
            p = row["payload"]
            pub, origin_kind = publisher(p["url"])
            evidence.append(
                {
                    "item_id": row["item_id"],
                    "version": row["version"],
                    "revision_id": row["id"],
                    "capture_sha256": row["capture_sha256"],
                    "payload_sha256": digest(p),
                    "received_at": utc(row["received_at"]).isoformat(),
                    "published_at": p.get("published_at"),
                    "url": p["url"],
                    "title": p["title"],
                    "publisher_group": pub,
                    "origin_kind": origin_kind,
                }
            )
            for other in group[:i]:
                a, b = extracted[row["item_id"]], extracted[other["item_id"]]
                reasons.add(related(a, b))
                if a["numbers"] and b["numbers"] and a["numbers"] != b["numbers"]:
                    flags.add("NUMERIC_DIFFERENCE_REQUIRES_CONTEXT")
                if a["direction"] and b["direction"] and a["direction"] != b["direction"]:
                    flags.add("DIRECTION_DIFFERENCE_REQUIRES_CONTEXT")
        known_publishers = sorted(
            {e["publisher_group"] for e in evidence if e["publisher_group"] != "unknown"}
        )
        urls = {canonical_url(e["url"]) for e in evidence}
        tickers = sorted(set().union(*(extracted[r["item_id"]]["tickers"] for r in group)))
        blockers = [
            "STRUCTURED_CLAIM_NOT_REVIEWED",
            "SOURCE_SPANS_AND_COMPARISON_NOT_VERIFIED",
            "COMPANY_EXPOSURE_AND_MATERIALITY_UNKNOWN",
            "CAUSAL_PATH_NOT_APPROVED",
        ]
        if not tickers:
            blockers.append("NO_RESOLVED_PILOT_COMPANY")
        if flags:
            blockers.append("POTENTIAL_CONFLICT_REQUIRES_REVIEW")
        member_digest = digest(
            [
                {
                    k: e[k]
                    for k in (
                        "item_id",
                        "version",
                        "revision_id",
                        "capture_sha256",
                        "payload_sha256",
                    )
                }
                for e in evidence
            ]
        )
        clusters.append(
            {
                "id": digest([VERSION, member_digest]),
                "membership_sha256": member_digest,
                "title": evidence[0]["title"],
                "members": evidence,
                "member_count": len(evidence),
                "unique_articles": len(urls),
                "publisher_groups": known_publishers,
                "publisher_group_count": len(known_publishers),
                "reporting_independence": "NOT_ESTABLISHED",
                "grouping_reasons": sorted(reasons),
                "potential_conflicts": sorted(flags),
                "ticker_mentions": tickers,
                "status": "REVIEW_CANDIDATE",
                "claim_verified": False,
                "latest_received_at": max(e["received_at"] for e in evidence),
                "impact_handoff": {
                    "ready": False,
                    "target": "REVIEWED_CLAIM_INTAKE",
                    "blockers": blockers,
                    "priority": "CONFLICT_REVIEW"
                    if flags
                    else "MULTI_PUBLISHER_REVIEW"
                    if len(known_publishers) > 1
                    else "SOURCE_REVIEW",
                    "impact": "UNKNOWN",
                    "graph_eligible": False,
                },
            }
        )
    clusters.sort(key=lambda c: (c["latest_received_at"], c["id"]), reverse=True)
    return {
        "algorithm": VERSION,
        "as_of": cutoff.isoformat(),
        "items": clusters,
        "source_items": len(rows),
        "cluster_count": len(clusters),
        "truncated": truncated,
        "snapshot_sha256": digest([VERSION, clusters]),
        "delivery": "disabled",
        "canonical_events_created": 0,
        "graph_modified": False,
    }


def analyze(engine, cutoff=None):
    cutoff = cutoff or datetime.now(UTC)
    rows, truncated = snapshot_rows(engine, cutoff)
    return build(rows, cutoff, truncated=truncated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/news-cluster-summary.json"))
    args = parser.parse_args()
    Settings.from_env()
    engine = database()
    try:
        result = analyze(engine)
    finally:
        engine.dispose()
    private = Path("source-cache/news-clusters")
    private.mkdir(parents=True, exist_ok=True)
    path = private / (result["snapshot_sha256"] + ".json")
    if not path.exists():
        with path.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    summary = {
        k: result[k]
        for k in (
            "algorithm",
            "as_of",
            "source_items",
            "cluster_count",
            "truncated",
            "snapshot_sha256",
            "delivery",
            "canonical_events_created",
            "graph_modified",
        )
    }
    summary.update(
        multi_article_clusters=sum(c["unique_articles"] > 1 for c in result["items"]),
        multi_publisher_clusters=sum(c["publisher_group_count"] > 1 for c in result["items"]),
        potential_conflict_clusters=sum(bool(c["potential_conflicts"]) for c in result["items"]),
        impact_ready_clusters=sum(c["impact_handoff"]["ready"] for c in result["items"]),
    )
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
