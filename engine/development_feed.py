"""Opt-in private SEC filing notices, without source/graph/materiality approval.

Only metadata is copied. These canonical notices are not extracted economic claims.
No scoring, financial observations, graph approval, sharing or dispatcher calls.
"""

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from engine.adapters.http_sources import SECSourceAdapter, SourceClient
from engine.api.accounts import transaction
from engine.collect_sec import candidates, identities
from engine.db import database
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v6 import metadata
from engine.settings import Settings

KIND = "development_sec_notice"
SOURCE = "development-sec-metadata"
events, versions, documents, sources, cards, links, subs, users, narratives = (
    metadata.tables[name]
    for name in (
        "rie_events",
        "rie_event_versions",
        "rie_documents",
        "rie_sources",
        "rie_user_cards",
        "rie_card_threads",
        "rie_subscriptions",
        "rie_users",
        "rie_narratives",
    )
)


def require_enabled():
    if not Settings.from_env().dev_informational_feed:
        raise ValueError("DEV_INFORMATIONAL_FEED=true required")


def ingest_submissions(engine, ticker, cik, capture, *, per_company=10):
    """Validate SEC identity/time, then atomically version bounded filing metadata."""
    require_enabled()
    now = datetime.now(UTC)
    if not 1 <= per_company <= 20 or capture.retrieved_at.tzinfo is None:
        raise ValueError("Invalid scope or capture time")
    if capture.retrieved_at > now:
        raise ValueError("Future capture")
    if capture.url != f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json":
        raise ValueError("Unexpected SEC endpoint")
    import hashlib

    if hashlib.sha256(capture.text.encode()).hexdigest() != capture.content_sha256:
        raise ValueError("Capture hash mismatch")
    rows = candidates(
        ticker,
        cik,
        json.loads(capture.text),
        date(2025, 2, 21),
        capture.retrieved_at.date(),
        per_company,
    )
    results = []
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        mode = conn.scalar(select(database_mode.c.mode).with_for_update())
        if mode != "production":
            raise ValueError("Separate non-synthetic database required")
        # Same serialization lock used by reviewed ingestion; never modify its sources.
        if not conn.scalar(select(sources.c.id).where(sources.c.id == SOURCE)):
            conn.execute(
                sources.insert().values(
                    id=SOURCE,
                    name="SEC development metadata",
                    origin="https://data.sec.gov",
                    rights_status="pending",
                    citation_url=capture.url,
                    rights_note="User-authorized private development bypass; no approval granted",
                    created_at=now,
                )
            )
        for row in rows:
            key = KIND + ":" + ticker + ":" + row["accession"]
            claim = {
                k: row[k] for k in ("ticker", "cik", "accession", "filing_date", "form", "url")
            }
            claim["mode"] = KIND
            old = (
                conn.execute(
                    select(versions)
                    .where(versions.c.event_id == key)
                    .order_by(versions.c.version_number.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if old and old["normalized_claim"] == claim:
                results.append({"event_version_id": old["id"], "status": "duplicate"})
                continue
            # An old cached response cannot revert a newer version.
            if old:
                previous_capture = conn.scalar(
                    select(documents.c.retrieved_at).where(documents.c.id == old["document_id"])
                )
                if capture.retrieved_at <= utc(previous_capture):
                    raise ValueError("Stale capture cannot correct a newer notice")
            headline = f"{ticker}: hồ sơ {row['form']} nộp SEC ngày {row['filing_date']}"
            # Only a date is known; stored midnight is explicitly date precision, never knowledge time.
            published = datetime.fromisoformat(row["filing_date"]).replace(tzinfo=UTC)
            docid = str(uuid4())
            conn.execute(
                documents.insert().values(
                    id=docid,
                    source_id=SOURCE,
                    external_id=row["accession"],
                    primary_entity_id="CO_" + ticker,
                    filing_form=row["form"],
                    source_url=capture.url,
                    title=headline,
                    # This document is a metadata capture receipt, not the raw SEC JSON.
                    # Include capture time so A -> B -> A preserves all three receipts.
                    content_sha256=digest(
                        [claim, capture.content_sha256, capture.retrieved_at.isoformat()]
                    ),
                    published_at=published,
                    first_seen_at=capture.retrieved_at,
                    available_at=now,
                    retrieved_at=capture.retrieved_at,
                    is_synthetic=False,
                    metadata={
                        "mode": KIND,
                        "published_precision": "date",
                        "capture_sha256": capture.content_sha256,
                        "content_hash_basis": "notice_and_capture_receipt_v1",
                        "filing_url": row["url"],
                    },
                )
            )
            if not old:
                conn.execute(
                    events.insert().values(
                        id=key,
                        canonical_event_key=key,
                        issuer_entity_id="CO_" + ticker,
                        event_type=KIND,
                        published_at=published,
                        first_seen_at=capture.retrieved_at,
                        available_at=now,
                        is_synthetic=False,
                        created_at=now,
                    )
                )
            vid = str(uuid4())
            conn.execute(
                versions.insert().values(
                    id=vid,
                    event_id=key,
                    version_number=old["version_number"] + 1 if old else 1,
                    factual_headline=headline,
                    normalized_claim=claim,
                    document_id=docid,
                    extraction_model="sec-submissions-metadata-v1",
                    available_at=now,
                    is_correction=bool(old),
                    supersedes_version_id=old["id"] if old else None,
                )
            )
            results.append({"event_version_id": vid, "status": "corrected" if old else "created"})
    return results


def project(engine, user_id=None):
    """Idempotent per-owner snapshots, direct issuer only; never a causal match."""
    require_enabled()
    count = 0
    with engine.connect() as conn:
        ids = (
            list(conn.scalars(select(users.c.id).where(users.c.id == user_id)))
            if user_id
            else list(conn.scalars(select(users.c.id)))
        )
    for uid in ids:
        with transaction(engine, uid) as conn:
            now = datetime.now(UTC)
            subscriptions = (
                conn.execute(
                    select(subs).where(
                        subs.c.user_id == uid,
                        subs.c.disabled_at.is_(None),
                        subs.c.created_at <= now,
                    )
                )
                .mappings()
                .all()
            )
            notices = (
                conn.execute(
                    select(versions, events.c.issuer_entity_id)
                    .join(events)
                    .where(events.c.event_type == KIND, versions.c.available_at <= now)
                    .order_by(versions.c.available_at, versions.c.version_number)
                )
                .mappings()
                .all()
            )
            for sub in subscriptions:
                entity = sub["stock_entity_id"] or conn.scalar(
                    select(narratives.c.ticker_entity_id).where(
                        narratives.c.id == sub["narrative_id"]
                    )
                )
                for notice in notices:
                    if notice["issuer_entity_id"] != entity:
                        continue
                    vid, key = notice["id"], notice["event_id"]
                    cid = digest([uid, key, vid])
                    if conn.execute(
                        select(links.c.card_id).where(
                            links.c.card_id == cid,
                            links.c.thread_id == sub["id"],
                        )
                    ).first():
                        continue
                    if not conn.scalar(select(cards.c.id).where(cards.c.id == cid)):
                        previous = conn.scalar(
                            select(cards.c.id).where(
                                cards.c.user_id == uid,
                                cards.c.event_version_id == notice["supersedes_version_id"],
                            )
                        )
                        conn.execute(
                            cards.insert().values(
                                id=cid,
                                user_id=uid,
                                canonical_key=key,
                                event_version_id=vid,
                                correction_of=previous,
                            )
                        )
                    claim = notice["normalized_claim"]
                    trace = {
                        "mode": KIND,
                        "event_version_id": vid,
                        "canonical_event_key": key,
                        "decision": "private_information",
                        "stance": "INSUFFICIENT_EVIDENCE",
                        "match": "direct_issuer_only",
                        "selected_path": None,
                        "source_rights": "pending",
                        "graph": "not_evaluated",
                        "materiality": "UNKNOWN",
                        "score": None,
                        "delivery": "disabled",
                        "bypassed_gates": ["source_rights", "verified_graph", "materiality"],
                        "reason": "User-authorized development feed; not an impact assessment",
                    }
                    card = {
                        "mode": KIND,
                        "is_synthetic": False,
                        "primary_ticker": claim["ticker"],
                        "headline": notice["factual_headline"],
                        "what_changed": notice["factual_headline"],
                        "why_connected": "Cùng công ty đang theo dõi; chưa đánh giá quan hệ nhân quả.",
                        "narrative_stance": "INSUFFICIENT_EVIDENCE",
                        "what_to_watch": "Mở hồ sơ gốc và kiểm duyệt nội dung trước khi đánh giá tác động.",
                        "what_is_uncertain": [
                            "Quyền nguồn chưa duyệt",
                            "Graph chưa xác minh",
                            "Materiality chưa đánh giá",
                            "Chỉ có metadata hồ sơ",
                        ],
                        "evidence_urls": [claim["url"]],
                        "source_published_at": claim["filing_date"],
                        "published_precision": "date",
                        "source_available_at": utc(notice["available_at"]).isoformat(),
                        "delivery_status": "disabled",
                        "private_only": True,
                    }
                    conn.execute(
                        links.insert().values(
                            card_id=cid,
                            thread_id=sub["id"],
                            available_at=now,
                            recorded_at=now,
                            source_at=notice["available_at"],
                            snapshot={"is_synthetic": False, "decision_trace": trace, "card": card},
                        )
                    )
                    count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--cache", type=Path, default=Path("source-cache/development-feed"))
    parser.add_argument("--per-company", type=int, default=10, choices=range(1, 21))
    args = parser.parse_args()
    require_enabled()
    engine = database()
    client = SourceClient(user_agent=args.user_agent, cache_dir=args.cache)
    result: dict = {"mode": KIND, "delivery": "disabled", "companies": {}, "errors": {}}
    try:
        registry = identities(
            json.loads(client.fetch("https://www.sec.gov/files/company_tickers.json").text)
        )
        for ticker, identity in registry.items():
            try:
                capture = SECSourceAdapter(client).submissions(identity["cik"])
                result["companies"][ticker] = ingest_submissions(
                    engine, ticker, identity["cik"], capture, per_company=args.per_company
                )
            except (ValueError, RuntimeError) as exc:
                result["errors"][ticker] = str(exc)
        result["new_private_links"] = project(engine)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    finally:
        client.close()
        engine.dispose()
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
