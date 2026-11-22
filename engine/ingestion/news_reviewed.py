"""Explicit, development-only canonical news writes. No impact or dispatch."""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field
from sqlalchemy import select

from engine.ingestion.contracts import EventExtraction, StrictModel, canonical_key, digest
from engine.ingestion.reviewed import documents, events, evidence, fact, links, sources, versions
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v15 import news_promotions as promotions
from engine.news_claims import prepare
from engine.sec_review import require_real
from engine.seed import identifier
from engine.settings import Settings


class IngestBody(StrictModel):
    expected_intake_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    occurrence_window: str = Field(min_length=10, max_length=200)
    identity_confirmed: bool = False
    identity_note: str = Field(min_length=20, max_length=4000)
    action: Literal["new", "duplicate", "correction"]
    target_claim_id: str | None = None


def ingest(conn, actor, claim_id, body):
    settings = Settings.from_env()
    if actor.role != "admin" or not settings.dev_informational_feed:
        raise ValueError("Operator and private development opt-in required")
    conn.execute(select(database_mode).where(database_mode.c.id == 1).with_for_update()).first()
    require_real(conn)
    if not body.identity_confirmed or (body.action == "new") != (body.target_claim_id is None):
        raise ValueError("Confirm event identity and explicit duplicate/correction target")
    intake = prepare(conn, actor, claim_id)  # Locks claim and current source before retry lookup.
    p = intake["payload"]
    if (
        digest(p) != intake["payload_sha256"]
        or intake["payload_sha256"] != body.expected_intake_sha256
    ):
        raise ValueError("Intake changed; prepare and review again")
    now = datetime.now(UTC)
    clocks = [
        datetime.fromisoformat(p[k])
        for k in ("claim_created_at", "review_recorded_at", "recorded_at")
    ]
    if clocks != sorted(clocks) or max(clocks) > now:
        raise ValueError("Invalid claim/review/intake chronology")
    event = EventExtraction.model_validate(p["event"])
    claim = event.claims[0]
    key = canonical_key(
        issuer=event.entity_ids[0],
        event_type=event.event_type,
        metric=claim.metric_id or "qualitative",
        period=claim.period or "unspecified",
        basis=claim.comparison_basis,
        occurrence_window=body.occurrence_window,
    )
    request = body.model_dump(mode="json")
    input_hash = digest([intake["payload_sha256"], request])
    source_id = "news-reviewed:" + p["source_revision_id"]
    source = conn.execute(select(sources).where(sources.c.id == source_id)).mappings().first()
    if source and source["rights_status"] == "blocked":
        raise ValueError("Source explicitly blocked")
    old = (
        conn.execute(select(promotions).where(promotions.c.claim_id == claim_id)).mappings().first()
    )
    if old:
        if old["input_sha256"] != input_hash:
            raise ValueError("Claim already ingested with another identity or approval")
        return {**old["result"], "idempotent_retry": True}
    existing = (
        conn.execute(select(events).where(events.c.canonical_event_key == key)).mappings().first()
    )
    latest = (
        conn.execute(
            select(versions)
            .where(versions.c.event_id == key)
            .order_by(versions.c.version_number.desc())
        )
        .mappings()
        .first()
    )
    target = None
    if body.target_claim_id:
        target = (
            conn.execute(select(promotions).where(promotions.c.claim_id == body.target_claim_id))
            .mappings()
            .first()
        )
        if not target or not latest or target["event_version_id"] != latest["id"]:
            raise ValueError("Target must be an ingested latest version of this canonical event")
        if utc(target["recorded_at"]) >= now:
            raise ValueError("Target must precede this ingestion")
    if existing and (body.action == "new" or existing["is_synthetic"]):
        raise ValueError("Canonical collision requires explicit duplicate/correction")
    if body.action != "new" and not existing:
        raise ValueError("Canonical target does not exist")
    content = {**fact(event), "comparison_period": p.get("comparison_period")}
    if latest:
        prior_event = EventExtraction.model_validate(latest["normalized_claim"]["extraction"])
        if event.available_at < prior_event.available_at:
            raise ValueError("An older capture cannot replace or duplicate the current version")
        same = content == latest["normalized_claim"].get("fact")
        if (body.action == "duplicate" and not same) or (body.action == "correction" and same):
            raise ValueError(
                "Duplicate requires identical facts; correction requires changed facts"
            )
    # A correction can supersede a stale/revoked source; history is retained, not reapproved.
    if not source:
        conn.execute(
            sources.insert().values(
                id=source_id,
                name="Reviewed RSS excerpt",
                origin="news",
                rights_status="pending",
                citation_url=claim.source_url,
                rights_note="Private development only; commercial rights not approved",
                created_at=now,
            )
        )
    doc_id = identifier(source_id)
    if not conn.scalar(select(documents.c.id).where(documents.c.id == doc_id)):
        conn.execute(
            documents.insert().values(
                id=doc_id,
                source_id=source_id,
                external_id=p["source_revision_id"],
                primary_entity_id=event.entity_ids[0],
                source_url=claim.source_url,
                content_sha256=p["source_payload_sha256"],
                published_at=event.published_at,
                first_seen_at=event.available_at,
                available_at=now,
                retrieved_at=event.available_at,
                is_synthetic=False,
                metadata={
                    "source_revision_id": p["source_revision_id"],
                    "source_text_basis": p["source_text_basis"],
                    "recorded_at": now.isoformat(),
                },
            )
        )
    evidence_id = str(uuid4())
    conn.execute(
        evidence.insert().values(
            id=evidence_id,
            document_id=doc_id,
            text_start=claim.source_span.start,
            text_end=claim.source_span.end,
            excerpt=claim.claim_text,
            quoted_claim=claim.claim_text,
            url=claim.source_url,
            verified_by=actor.id,
            verified_at=now,
            created_at=now,
        )
    )
    if not existing:
        conn.execute(
            events.insert().values(
                id=key,
                canonical_event_key=key,
                issuer_entity_id=event.entity_ids[0],
                event_type=event.event_type,
                published_at=event.published_at,
                first_seen_at=event.available_at,
                available_at=now,
                created_at=now,
                is_synthetic=False,
            )
        )
    version_id = latest["id"] if body.action == "duplicate" and latest else str(uuid4())
    if body.action != "duplicate":
        conn.execute(
            versions.insert().values(
                id=version_id,
                event_id=key,
                version_number=latest["version_number"] + 1 if latest else 1,
                factual_headline=event.factual_headline,
                normalized_claim={
                    "fact": content,
                    "extraction": p["event"],
                    "news_claim_id": claim_id,
                    "review_id": p["review_id"],
                    "author_kind": p["author_kind"],
                    "reviewer_kind": p["reviewer_kind"],
                    "materiality": "UNKNOWN",
                    "graph_eligible": False,
                    "source_rights": p["source_rights"],
                    "is_synthetic": False,
                },
                metric_id=claim.metric_id,
                extraction_model="reviewed-news-v1",
                document_id=doc_id,
                evidence_quality=None,
                available_at=now,
                is_correction=body.action == "correction",
                supersedes_version_id=latest["id"] if latest else None,
            )
        )
    conn.execute(links.insert().values(event_version_id=version_id, evidence_id=evidence_id))
    result = dict(
        event_id=key,
        event_version_id=version_id,
        claim_id=claim_id,
        action=body.action,
        recorded_at=now.isoformat(),
        feed_eligible=False,
        graph_eligible=False,
        materiality="UNKNOWN",
        delivery="disabled",
    )
    conn.execute(
        promotions.insert().values(
            claim_id=claim_id,
            review_id=p["review_id"],
            operator_id=actor.id,
            event_version_id=version_id,
            recorded_at=now,
            input_sha256=input_hash,
            request=request,
            result=result,
        )
    )
    return result
