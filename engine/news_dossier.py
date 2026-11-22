"""Read-only evidence dossiers. Context is never causal proof or automatic review."""

import re
from datetime import UTC, datetime

from sqlalchemy import select

from engine.filing_evidence import assessment
from engine.financials import assessments, known_filings
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_items, news_revisions
from engine.news_articles import evidence as article_evidence
from engine.news_claims import NAMES, source_text
from engine.news_evidence import capture_evidence
from engine.settings import Settings


def dossier(conn, item_id, ticker, expected_hash):
    if not Settings.from_env().dev_informational_feed:
        raise ValueError("Private development opt-in required")
    if ticker not in NAMES:
        raise ValueError("Unknown pilot ticker")
    current = conn.execute(select(news_items).where(news_items.c.id == item_id)).mappings().first()
    if not current:
        raise ValueError("News item not found")
    row = (
        conn.execute(
            select(news_revisions).where(
                news_revisions.c.item_id == item_id, news_revisions.c.version == current["version"]
            )
        )
        .mappings()
        .one()
    )
    p = row["payload"]
    if digest(p) != expected_hash or digest(current["payload"]) != expected_hash:
        raise ValueError("Source revision changed; reload source")
    text = source_text(p)
    if not (
        re.search(r"\b" + re.escape(NAMES[ticker]) + r"\b", text, re.I)
        or re.search(r"\b" + ticker + r"\b", text)
    ):
        raise ValueError("Selected company not explicitly named in source")
    now = datetime.now(UTC)
    cutoff = utc(row["received_at"])
    published = datetime.fromisoformat(p["published_at"]) if p.get("published_at") else None
    if (
        not published
        or published.tzinfo is None
        or published > cutoff
        or cutoff > now
        or (ticker == "SNDK" and published.date().isoformat() < "2025-02-21")
    ):
        raise ValueError("Invalid source identity or chronology")
    # Only records available before this news capture; newer data cannot fill a historical gap.
    comparisons = assessments(conn, ticker, cutoff)
    current_comparisons = assessments(conn, ticker, now)
    valid = {(x["snapshot_id"], x["accession"], x["metric"]) for x in current_comparisons}
    comparisons = [
        x for x in comparisons if (x["snapshot_id"], x["accession"], x["metric"]) in valid
    ]
    comparisons.sort(key=lambda x: (x["current"]["end"], x["accession"], x["metric"]), reverse=True)
    past_filings = known_filings(conn, ticker, cutoff)
    current_filings = known_filings(conn, ticker, now)
    accessions = sorted(
        (
            a
            for a, c in past_filings.items()
            if c.get("source_status", "active") == "active"
            and a in current_filings
            and current_filings[a].get("source_status", "active") == "active"
        ),
        key=lambda a: (past_filings[a]["filing_date"], a),
        reverse=True,
    )
    segments: list[dict] = []
    for accession in accessions[:5]:
        past = assessment(conn, ticker, accession, cutoff)["segments"]
        latest = assessment(conn, ticker, accession, now)["segments"]
        current_hashes = {digest(x) for x in latest}
        segments.extend(x for x in past if digest(x) in current_hashes)
    blockers = [
        "CLAIM_AND_INDEPENDENT_REVIEW_REQUIRED",
        "NEWS_TO_FINANCIAL_METRIC_LINK_UNVERIFIED",
        "EXPOSURE_NUMERATOR_AND_MATCHED_DENOMINATOR_REQUIRED",
        "CAUSAL_AND_COUNTERFACTUAL_EVIDENCE_REQUIRED",
        "VERIFIED_RELATIONSHIP_PATH_REQUIRED",
    ]
    if not comparisons:
        blockers.append("NO_CURRENT_VALID_FINANCIAL_BASELINE_AVAILABLE_BEFORE_NEWS")
    if not segments:
        blockers.append("NO_CURRENT_VALID_SEGMENT_BASELINE_AVAILABLE_BEFORE_NEWS")
    result = dict(
        kind="NEWS_EVIDENCE_DOSSIER",
        news_verification="UNVERIFIED_RSS",
        ticker=ticker,
        generated_at=now.isoformat(),
        source={
            "item_id": item_id,
            "revision_id": row["id"],
            "version": row["version"],
            "payload_sha256": expected_hash,
            "url": p["url"],
            "text": text,
            "published_at": published.isoformat(),
            "captured_at": cutoff.isoformat(),
        },
        evidence_cutoff=cutoff.isoformat(),
        raw_source_evidence=capture_evidence(row),
        article_evidence=article_evidence(row),
        financial_context=comparisons[:12],
        segment_context=segments[:20],
        limits={"financial": 12, "filings": 5, "segments": 20},
        truncated=len(comparisons) > 12 or len(accessions) > 5 or len(segments) > 20,
        context_role="BASELINE_ONLY_NOT_NEWS_CAUSAL_EVIDENCE",
        exposure="UNKNOWN",
        materiality="UNKNOWN",
        causal_attribution="NOT_ESTABLISHED",
        blockers=blockers,
        graph_eligible=False,
        impact_eligible=False,
        delivery="disabled",
    )
    result["dossier_sha256"] = digest(result)
    return result
