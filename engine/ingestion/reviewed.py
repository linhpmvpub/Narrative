"""Reviewed SEC -> canonical records. No scoring, feed projection or dispatch."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from engine.identity import validate_metric_issuer
from engine.ingestion.contracts import EventExtraction, canonical_key, digest
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v5 import drafts, filings, reviews
from engine.models.schema_v6 import metadata, permissions, promotions
from engine.sec_review import require_real, sha
from engine.seed import identifier
from engine.settings import Settings

sources, documents, events, versions, evidence, links = (
    metadata.tables[n]
    for n in (
        "rie_sources",
        "rie_documents",
        "rie_events",
        "rie_event_versions",
        "rie_evidence",
        "rie_event_evidence",
    )
)


def latest_permission(conn, filing_id, at):
    return (
        conn.execute(
            select(permissions)
            .where(permissions.c.filing_id == filing_id, permissions.c.recorded_at <= at)
            .order_by(permissions.c.version.desc())
        )
        .mappings()
        .first()
    )


def permission_at(conn, filing, at):
    permission = latest_permission(conn, filing["id"], at)
    if (
        not permission
        or permission["status"] != "approved"
        or utc(permission["valid_until"]) <= at
        or permission["capture_hash"] != filing["content_sha256"]
        or permission["payload"]["cik"] != filing["manifest"]["cik"]
        or permission["payload"].get("status") != "approved"
        or permission["payload"].get("identity_confirmed") is not True
        or len(permission["payload"].get("rights_note", "").strip()) < 10
        or len(permission["payload"].get("identity_note", "").strip()) < 10
    ):
        raise ValueError(
            "Source rights/identity permission missing, expired, revoked or mismatched"
        )
    return permission


def validate_reviewed(conn, draft, filing, at, *, current=True):
    """Revalidate stored input rather than trusting a past API acknowledgement."""
    latest = conn.execute(
        select(drafts.c.version)
        .where(drafts.c.filing_id == filing["id"], drafts.c.created_at <= at)
        .order_by(drafts.c.version.desc())
    ).scalar()
    if latest != draft["version"] or (current and filing["revision"] != draft["version"]):
        raise ValueError("Extraction is not the latest reviewed filing version")
    review = (
        conn.execute(
            select(reviews).where(reviews.c.draft_id == draft["id"], reviews.c.reviewed_at <= at)
        )
        .mappings()
        .first()
    )
    if (
        not review
        or review["decision"] != "approved"
        or review["reviewer_id"] == draft["author_id"]
    ):
        raise ValueError("Independent approved review required at cutoff")
    proof = review["payload"]
    if (
        proof.get("expected_version") != draft["version"]
        or proof.get("decision") != "approved"
        or len(proof.get("rights_basis", "").strip()) < 10
        or not all(
            proof.get(k) is True
            for k in ("identity_confirmed", "citation_confirmed", "comparison_confirmed")
        )
    ):
        raise ValueError("Incomplete review proof")
    event = EventExtraction.model_validate(draft["payload"]["event"])
    if (
        event.source_document_id != filing["id"]
        or event.entity_ids != ["CO_" + filing["ticker"]]
        or len(event.claims) != 1
        or event.available_at != utc(filing["retrieved_at"])
        or event.published_at.date().isoformat() != filing["manifest"]["filing_date"]
        or filing["manifest"].get("is_synthetic") is not False
        or filing["content_sha256"] != filing["manifest"]["content_sha256"]
        or filing["source_url"] != filing["manifest"]["url"]
        or sha(filing["source_text"]) != filing["text_sha256"]
    ):
        raise ValueError("Source capture, issuer or text provenance mismatch")
    clocks = [
        utc(filing["retrieved_at"]),
        utc(filing["imported_at"]),
        utc(draft["created_at"]),
        utc(review["reviewed_at"]),
    ]
    if clocks != sorted(clocks) or max(clocks + [event.published_at, event.available_at]) > at:
        raise ValueError("Source, draft or review is not available at cutoff")
    event.validate_source(filing["source_text"], filing["source_url"])
    claim = event.claims[0]
    if claim.metric_id:
        nodes = metadata.tables["rie_entities"]
        kind = conn.scalar(select(nodes.c.entity_type).where(nodes.c.id == claim.metric_id))
        if kind != "financial_metric":
            raise ValueError("Unknown financial metric")
        validate_metric_issuer(event.entity_ids[0], claim.metric_id, event.published_at.date())
    if filing["ticker"] == "SNDK" and event.published_at.date().isoformat() < "2025-02-21":
        raise ValueError("Sandisk identity precedes separation")
    canonical = canonical_key(
        issuer=event.entity_ids[0],
        event_type=event.event_type,
        metric=claim.metric_id or "qualitative",
        period=claim.period or "unknown",
        basis=claim.comparison_basis,
        occurrence_window=draft["payload"]["occurrence_window"],
    )
    if canonical != draft["canonical_key"]:
        raise ValueError("Canonical identity changed after review")
    return event, review


def fact(event):
    """Economic content only; document URL/offsets/headline do not define a reprint."""
    claim = event.claims[0].model_dump(mode="json")
    return {k: v for k, v in claim.items() if k not in {"source_span", "source_url"}}


def ingest_reviewed(
    conn, draft_id, expected_version, expected_permission_version, as_of, operator_id
):
    Settings.from_env()  # Fail closed even when called outside the API.
    if as_of.tzinfo is None:
        raise ValueError("Cutoff requires timezone")
    as_of = as_of.astimezone(UTC)
    if as_of > datetime.now(UTC):
        raise ValueError("Future ingestion cutoff is prohibited")
    # Shared ingestion lock serializes canonical dedup, including cross-filing races.
    conn.execute(select(database_mode).where(database_mode.c.id == 1).with_for_update()).first()
    require_real(conn)
    draft = conn.execute(select(drafts).where(drafts.c.id == draft_id)).mappings().first()
    if not draft or draft["version"] != expected_version:
        raise ValueError("Draft missing or expected version mismatched")
    correction = draft["payload"].get("correction_of")
    duplicate = draft["payload"].get("duplicate_of")
    if correction and duplicate:
        raise ValueError("Cannot be both correction and duplicate")
    target_id = correction or duplicate
    target = (
        conn.execute(select(drafts).where(drafts.c.id == target_id)).mappings().first()
        if target_id
        else None
    )
    if target_id and not target:
        raise ValueError("Referenced extraction does not exist")
    filing_ids = sorted({draft["filing_id"]} | ({target["filing_id"]} if target else set()))
    locked = {
        r["id"]: r
        for r in conn.execute(
            select(filings)
            .where(filings.c.id.in_(filing_ids))
            .order_by(filings.c.id)
            .with_for_update()
        ).mappings()
    }
    now = datetime.now(UTC)
    filing = locked[draft["filing_id"]]
    event, review = validate_reviewed(conn, draft, filing, as_of)
    permission = permission_at(conn, filing, as_of)
    current = permission_at(conn, filing, now)
    if current["id"] != permission["id"] or current["version"] != expected_permission_version:
        raise ValueError("Permission changed; reload current approval")
    if utc(permission["recorded_at"]) < utc(filing["imported_at"]):
        raise ValueError("Permission cannot precede capture import")
    input_hash = digest(
        [draft["payload"], review["id"], filing["content_sha256"], filing["text_sha256"]]
    )
    source_id = "sec-reviewed:" + filing["id"]
    source = conn.execute(select(sources).where(sources.c.id == source_id)).mappings().first()
    if source and source["rights_status"] != "approved":
        raise ValueError("Source is blocked or pending")
    old = (
        conn.execute(select(promotions).where(promotions.c.draft_id == draft_id)).mappings().first()
    )
    if old:
        if old["input_hash"] != input_hash:
            raise ValueError("Previously ingested extraction has changed")
        return {**old["result"], "idempotent_retry": True}

    target_receipt = None
    if target:
        target_filing = locked[target["filing_id"]]
        validate_reviewed(conn, target, target_filing, as_of)
        permission_at(conn, target_filing, as_of)
        permission_at(conn, target_filing, now)
        if (
            target["filing_id"] == filing["id"]
            or target["canonical_key"] != draft["canonical_key"]
            or utc(target_filing["retrieved_at"]) >= utc(filing["retrieved_at"])
        ):
            raise ValueError("Reference must be an earlier capture of the same canonical event")
        target_receipt = (
            conn.execute(
                select(promotions).where(
                    promotions.c.draft_id == target_id, promotions.c.recorded_at <= as_of
                )
            )
            .mappings()
            .first()
        )
        if not target_receipt:
            raise ValueError("Referenced extraction must already be ingested at cutoff")

    existing = (
        conn.execute(select(events).where(events.c.canonical_event_key == draft["canonical_key"]))
        .mappings()
        .first()
    )
    latest = (
        conn.execute(
            select(versions)
            .where(versions.c.event_id == existing["id"])
            .order_by(versions.c.version_number.desc())
        )
        .mappings()
        .first()
        if existing
        else None
    )
    prior = (
        conn.execute(select(versions).where(versions.c.id == target_receipt["event_version_id"]))
        .mappings()
        .one()
        if target_receipt
        else None
    )
    if existing and (
        existing["is_synthetic"]
        or existing["issuer_entity_id"] != event.entity_ids[0]
        or existing["event_type"] != event.event_type
    ):
        raise ValueError("Canonical issuer/type conflict")
    if prior and (not existing or prior["event_id"] != existing["id"]):
        raise ValueError("Referenced version belongs to another canonical event")
    if existing and not target:
        raise ValueError("Canonical event exists; explicit duplicate/correction review required")
    if correction and (
        prior is None
        or not latest
        or latest["id"] != prior["id"]
        or fact(event) == prior["normalized_claim"]["fact"]
    ):
        raise ValueError("Correction requires changed facts and the latest canonical version")
    if duplicate and (prior is None or fact(event) != prior["normalized_claim"]["fact"]):
        raise ValueError("Reprint changes facts; review an explicit correction")

    if not source:
        conn.execute(
            sources.insert().values(
                id=source_id,
                name="SEC reviewed capture " + filing["accession"],
                origin="sec",
                rights_status="approved",
                citation_url=filing["source_url"],
                rights_note=permission["payload"]["rights_note"],
                created_at=now,
            )
        )
    doc_id = identifier("sec-document:" + filing["id"])
    if not conn.scalar(select(documents.c.id).where(documents.c.id == doc_id)):
        conn.execute(
            documents.insert().values(
                id=doc_id,
                source_id=source_id,
                external_id=filing["accession"],
                primary_entity_id=event.entity_ids[0],
                filing_form=filing["manifest"].get("form"),
                source_url=filing["source_url"],
                content_sha256=filing["content_sha256"],
                published_at=event.published_at,
                first_seen_at=filing["retrieved_at"],
                available_at=filing["retrieved_at"],
                retrieved_at=filing["retrieved_at"],
                is_synthetic=False,
                metadata={
                    "filing_id": filing["id"],
                    "text_sha256": filing["text_sha256"],
                    "text_transform": "html-to-text-v1",
                    "recorded_at": now.isoformat(),
                },
            )
        )
    claim = event.claims[0]
    evidence_id = str(uuid4())
    conn.execute(
        evidence.insert().values(
            id=evidence_id,
            document_id=doc_id,
            text_start=claim.source_span.start,
            text_end=claim.source_span.end,
            excerpt=claim.claim_text,
            quoted_claim=claim.claim_text,
            url=filing["source_url"],
            verified_by=review["reviewer_id"],
            verified_at=review["reviewed_at"],
            created_at=now,
        )
    )
    event_id = existing["id"] if existing else draft["canonical_key"]
    if not existing:
        conn.execute(
            events.insert().values(
                id=event_id,
                canonical_event_key=draft["canonical_key"],
                issuer_entity_id=event.entity_ids[0],
                event_type=event.event_type,
                occurred_at=None,
                published_at=event.published_at,
                first_seen_at=filing["retrieved_at"],
                available_at=now,
                created_at=now,
                is_synthetic=False,
            )
        )
    version_id = (
        prior["id"] if duplicate and prior is not None else identifier("sec-version:" + draft_id)
    )
    if not duplicate:
        conn.execute(
            versions.insert().values(
                id=version_id,
                event_id=event_id,
                version_number=latest["version_number"] + 1 if latest else 1,
                factual_headline=event.factual_headline,
                normalized_claim={
                    "fact": fact(event),
                    "extraction": event.model_dump(mode="json"),
                    "draft_id": draft_id,
                    "review_id": review["id"],
                    "permission_id": permission["id"],
                    "materiality": "UNKNOWN",
                    "is_synthetic": False,
                },
                metric_id=claim.metric_id,
                extraction_model="human-reviewed-sec-v1",
                document_id=doc_id,
                evidence_quality=None,
                available_at=now,
                is_correction=bool(correction),
                supersedes_version_id=prior["id"] if correction and prior is not None else None,
            )
        )
    conn.execute(links.insert().values(event_version_id=version_id, evidence_id=evidence_id))
    result = dict(
        event_id=event_id,
        event_version_id=version_id,
        draft_id=draft_id,
        status="duplicate" if duplicate else "versioned_correction" if correction else "ingested",
        recorded_at=now.isoformat(),
        as_of=as_of.isoformat(),
        is_synthetic=False,
        feed_eligible=False,
        delivery="disabled",
    )
    conn.execute(
        promotions.insert().values(
            draft_id=draft_id,
            review_id=review["id"],
            permission_id=permission["id"],
            operator_id=operator_id,
            event_version_id=version_id,
            document_id=doc_id,
            evidence_id=evidence_id,
            input_hash=input_hash,
            as_of=as_of,
            recorded_at=now,
            result=result,
        )
    )
    return result


def reviewed_versions_as_of(conn, as_of):
    """Operator snapshot only; latest invalid version is withheld, never rolled back."""
    require_real(conn)
    if as_of.tzinfo is None:
        raise ValueError("Snapshot requires timezone")
    rows = conn.execute(
        select(versions)
        .join(events, versions.c.event_id == events.c.id)
        .where(events.c.is_synthetic.is_(False), versions.c.available_at <= as_of)
        .order_by(versions.c.event_id, versions.c.version_number)
    ).mappings()
    latest = {r["event_id"]: r for r in rows}
    result = []
    for version in latest.values():
        draft_id = version["normalized_claim"].get("draft_id")
        promotion = (
            conn.execute(
                select(promotions).where(
                    promotions.c.draft_id == draft_id, promotions.c.recorded_at <= as_of
                )
            )
            .mappings()
            .first()
        )
        if not promotion:
            continue
        draft = conn.execute(select(drafts).where(drafts.c.id == draft_id)).mappings().one()
        filing = (
            conn.execute(select(filings).where(filings.c.id == draft["filing_id"])).mappings().one()
        )
        try:
            validate_reviewed(conn, draft, filing, as_of, current=False)
            permission_at(conn, filing, as_of)
        except ValueError:
            continue
        result.append(
            {
                "event_id": version["event_id"],
                "event_version_id": version["id"],
                "version": version["version_number"],
                "headline": version["factual_headline"],
                "claim": version["normalized_claim"],
                "available_at": utc(version["available_at"]),
                "source_url": filing["source_url"],
                "review_id": promotion["review_id"],
                "permission_id": promotion["permission_id"],
                "feed_eligible": False,
            }
        )
    return result
