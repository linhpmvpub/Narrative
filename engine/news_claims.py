"""Review exact RSS excerpts; prepare a revalidated intake, never promote implicitly."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field
from sqlalchemy import select

from engine.identity import validate_metric_issuer
from engine.ingestion.contracts import (
    EventExtraction,
    NumericOrQualitativeClaim,
    StrictModel,
    canonical_key,
    digest,
)
from engine.models.contracts import utc
from engine.models.schema_v1 import metadata
from engine.models.schema_v13 import news_items, news_revisions
from engine.models.schema_v14 import news_claim_intakes as intakes
from engine.models.schema_v14 import news_claim_reviews as reviews
from engine.models.schema_v14 import news_claims as claims
from engine.settings import Settings

NAMES = {
    "MU": "micron",
    "NVDA": "nvidia",
    "AMD": "advanced micro devices",
    "DELL": "dell",
    "SNDK": "sandisk",
}


class ClaimBody(StrictModel):
    revision_id: str
    expected_payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    ticker: Literal["MU", "NVDA", "AMD", "DELL", "SNDK"]
    event_type: Literal[
        "earnings", "guidance", "capacity", "contract", "legal", "product", "management"
    ]
    author_kind: Literal["human_declared", "AI_SIMULATED"]
    claim: NumericOrQualitativeClaim
    comparison_period: str | None = None
    uncertainties: list[Annotated[str, Field(min_length=5, max_length=1000)]] = Field(
        min_length=1, max_length=10
    )


class ReviewBody(StrictModel):
    expected_review_version: int = Field(ge=0)
    decision: Literal["approved", "rejected", "revoked"]
    reviewer_kind: Literal["human_declared", "AI_SIMULATED"]
    identity_confirmed: bool = False
    citation_confirmed: bool = False
    comparison_confirmed: bool = False
    rationale: str = Field(min_length=20, max_length=4000)


def source_text(payload):
    return payload["title"] + "\n" + payload.get("summary", "")


def latest_review(conn, claim_id, at=None):
    return (
        conn.execute(
            select(reviews)
            .where(
                reviews.c.claim_id == claim_id, reviews.c.recorded_at <= (at or datetime.now(UTC))
            )
            .order_by(reviews.c.version.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )


def validate(conn, body, now, *, historical=False):
    row = (
        conn.execute(select(news_revisions).where(news_revisions.c.id == body.revision_id))
        .mappings()
        .first()
    )
    if not row or utc(row["received_at"]) > now:
        raise ValueError("Source revision missing or unavailable")
    if historical:
        query = (
            select(news_revisions)
            .where(news_revisions.c.item_id == row["item_id"], news_revisions.c.received_at <= now)
            .order_by(news_revisions.c.version.desc())
            .limit(1)
        )
    else:
        query = select(news_items).where(news_items.c.id == row["item_id"]).with_for_update()
    current = conn.execute(query).mappings().one()
    if current["version"] != row["version"] or digest(current["payload"]) != digest(row["payload"]):
        raise ValueError("Source revision changed; create a new claim")
    p = row["payload"]
    if digest(p) != body.expected_payload_sha256 or not p.get("published_at"):
        raise ValueError("Source hash or publication time missing/mismatched")
    published = datetime.fromisoformat(p["published_at"])
    if published.tzinfo is None or published > utc(row["received_at"]) or published > now:
        raise ValueError("Invalid source chronology")
    if body.ticker == "SNDK" and published.date().isoformat() < "2025-02-21":
        raise ValueError("Sandisk source precedes separation")
    passage = body.claim.claim_text
    if not (
        re.search(r"\b" + re.escape(NAMES[body.ticker]) + r"\b", passage, re.I)
        or re.search(r"\b" + body.ticker + r"\b", passage)
    ):
        raise ValueError("Claim excerpt must explicitly identify the selected company")
    claim = body.claim
    if claim.metric_id:
        if not conn.scalar(
            select(metadata.tables["rie_entities"].c.id).where(
                metadata.tables["rie_entities"].c.id == claim.metric_id,
                metadata.tables["rie_entities"].c.entity_type == "financial_metric",
            )
        ):
            raise ValueError("Unknown metric")
        validate_metric_issuer("CO_" + body.ticker, claim.metric_id, published.date())
    if claim.old_value is not None and claim.new_value is None:
        raise ValueError("Comparison requires a current numeric operand")
    if claim.new_value is not None or claim.old_value is not None:
        numbers = {
            Decimal(n.replace(",", ""))
            for n in re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?", passage)
        }
        if any(v is not None and v not in numbers for v in (claim.old_value, claim.new_value)):
            raise ValueError(
                "Numeric operands must occur literally in the cited excerpt; no inferred scales"
            )
        if not claim.period or claim.period.casefold() not in passage.casefold():
            raise ValueError("Current period must occur in the cited excerpt")
        if not claim.unit or claim.unit.casefold() not in passage.casefold():
            raise ValueError("Unit must occur literally in the cited excerpt")
        if claim.old_value is not None and (
            not body.comparison_period
            or body.comparison_period == claim.period
            or body.comparison_period.casefold() not in passage.casefold()
        ):
            raise ValueError("Distinct comparison period must occur in the cited excerpt")
    event = EventExtraction(
        source_document_id="news-revision:" + row["id"],
        entity_ids=["CO_" + body.ticker],
        event_type=body.event_type,
        factual_headline=p["title"][:280],
        published_at=published,
        available_at=utc(row["received_at"]),
        claims=[claim],
        uncertainties=body.uncertainties,
    )
    event.validate_source(source_text(p), p["url"])
    return row, event


def create(conn, actor, body):
    Settings.from_env()
    now = datetime.now(UTC)
    validate(conn, body, now)
    payload = body.model_dump(mode="json")
    id = str(uuid4())
    conn.execute(
        claims.insert().values(
            id=id,
            revision_id=body.revision_id,
            author_id=actor.id,
            created_at=now,
            payload=payload,
            input_sha256=digest(payload),
        )
    )
    return {"id": id, "status": "PENDING_REVIEW", "delivery": "disabled"}


def review(conn, actor, claim_id, body):
    Settings.from_env()
    if actor.role != "admin":
        raise ValueError("Operator review required")
    draft = (
        conn.execute(select(claims).where(claims.c.id == claim_id).with_for_update())
        .mappings()
        .first()
    )
    if not draft:
        raise ValueError("Claim not found")
    old = latest_review(conn, claim_id)
    version = old["version"] if old else 0
    if version != body.expected_review_version:
        raise ValueError("Review version changed; reload")
    if body.decision == "approved":
        if actor.id == draft["author_id"]:
            raise ValueError("Author cannot approve own claim")
        if not all((body.identity_confirmed, body.citation_confirmed, body.comparison_confirmed)):
            raise ValueError("Identity, citation and comparison confirmation required")
        validate(conn, ClaimBody.model_validate(draft["payload"]), datetime.now(UTC))
    if body.decision == "revoked" and (not old or old["decision"] != "approved"):
        raise ValueError("Only current approval may be revoked")
    id = str(uuid4())
    conn.execute(
        reviews.insert().values(
            id=id,
            claim_id=claim_id,
            version=version + 1,
            reviewer_id=actor.id,
            recorded_at=datetime.now(UTC),
            decision=body.decision,
            payload=body.model_dump(mode="json"),
        )
    )
    return {
        "id": id,
        "version": version + 1,
        "decision": body.decision,
        "canonical_events_created": 0,
    }


def prepare(conn, actor, claim_id):
    Settings.from_env()
    if actor.role != "admin":
        raise ValueError("Operator intake required")
    draft = (
        conn.execute(select(claims).where(claims.c.id == claim_id).with_for_update())
        .mappings()
        .first()
    )
    if not draft:
        raise ValueError("Claim not found")
    approved = latest_review(conn, claim_id)
    if (
        not approved
        or approved["decision"] != "approved"
        or approved["reviewer_id"] == draft["author_id"]
    ):
        raise ValueError("Current independent-account approval required")
    if digest(draft["payload"]) != draft["input_sha256"]:
        raise ValueError("Claim payload changed")
    proof = ReviewBody.model_validate(approved["payload"])
    now = datetime.now(UTC)
    if (
        proof.decision != "approved"
        or not all((proof.identity_confirmed, proof.citation_confirmed, proof.comparison_confirmed))
        or utc(draft["created_at"]) > utc(approved["recorded_at"])
        or utc(approved["recorded_at"]) > now
    ):
        raise ValueError("Invalid approval proof or chronology")
    body = ClaimBody.model_validate(draft["payload"])
    row, event = validate(conn, body, datetime.now(UTC))
    old = (
        conn.execute(
            select(intakes).where(
                intakes.c.claim_id == claim_id, intakes.c.review_id == approved["id"]
            )
        )
        .mappings()
        .first()
    )
    if old:
        p = old["payload"]
        if (
            digest(p) != old["payload_sha256"]
            or p["event"] != event.model_dump(mode="json")
            or p["review_id"] != approved["id"]
            or p["claim_id"] != claim_id
            or p["source_payload_sha256"] != body.expected_payload_sha256
            or p.get("comparison_period") != body.comparison_period
        ):
            raise ValueError("Intake receipt provenance mismatch")
        return {"id": old["id"], "payload_sha256": old["payload_sha256"], "payload": old["payload"]}
    payload = {
        "kind": "REVIEWED_NEWS_INTAKE",
        "claim_id": claim_id,
        "review_id": approved["id"],
        "source_revision_id": row["id"],
        "claim_created_at": utc(draft["created_at"]).isoformat(),
        "review_recorded_at": utc(approved["recorded_at"]).isoformat(),
        "source_payload_sha256": body.expected_payload_sha256,
        "source_text": source_text(row["payload"]),
        "source_text_basis": "RSS_TITLE_NEWLINE_SUMMARY_V1",
        "event": event.model_dump(mode="json"),
        "comparison_period": body.comparison_period,
        "author_kind": body.author_kind,
        "reviewer_kind": approved["payload"]["reviewer_kind"],
        "canonical_key_candidate": canonical_key(
            issuer=event.entity_ids[0],
            event_type=event.event_type,
            metric=body.claim.metric_id or "qualitative",
            period=body.claim.period or "unspecified",
            basis=body.claim.comparison_basis,
            occurrence_window=event.published_at.date().isoformat(),
        ),
        "canonical_identity_review_required": True,
        "recorded_at": datetime.now(UTC).isoformat(),
        "source_rights": "PRIVATE_DEVELOPMENT_ONLY_NOT_APPROVAL",
        "materiality": "UNKNOWN",
        "graph_eligible": False,
        "canonical_events_created": 0,
        "delivery": "disabled",
    }
    id = str(uuid4())
    conn.execute(
        intakes.insert().values(
            id=id,
            claim_id=claim_id,
            review_id=approved["id"],
            created_at=datetime.now(UTC),
            payload=payload,
            payload_sha256=digest(payload),
        )
    )
    return {"id": id, "payload_sha256": digest(payload), "payload": payload}
