"""Reviewed baseline segment shares; never estimated news damage or price impact."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import uuid4

from pydantic import Field
from sqlalchemy import select

from engine.filing_evidence import AXIS
from engine.ingestion.contracts import StrictModel, digest
from engine.ingestion.reviewed import versions
from engine.models.schema_v13 import news_revisions
from engine.models.schema_v15 import news_promotions
from engine.models.schema_v16 import exposure_drafts as drafts
from engine.models.schema_v16 import exposure_reviews as reviews
from engine.news_claims import claims
from engine.news_dossier import dossier
from engine.news_snapshot import validated_version
from engine.settings import Settings


def matched_pairs(context):
    result = []
    for n in context["segment_context"]:
        for d in context["financial_context"]:
            if (
                n.get("scope") != "reported_segment"
                or d.get("scope") != "consolidated_entity"
                or not n.get("segment")
                or sum(
                    axis == AXIS and member == n.get("segment")
                    for axis, member in n.get("dimensions", [])
                )
                != 1
                or any(
                    axis != AXIS
                    and (axis, member)
                    != ("srt:ConsolidationItemsAxis", "us-gaap:OperatingSegmentsMember")
                    for axis, member in n.get("dimensions", [])
                )
                or n.get("metric") != "REVENUE"
                or d.get("metric") != "REVENUE"
            ):
                continue
            if any(
                not n.get(k) or n[k] != d.get(k)
                for k in (
                    "ticker",
                    "accession",
                    "concept",
                    "unit",
                    "period_kind",
                    "source_identity",
                )
            ):
                continue
            if any(n["current"].get(k) != d["current"].get(k) for k in ("start", "end")):
                continue
            try:
                numerator, denominator = (
                    Decimal(n["current"]["value"]),
                    Decimal(d["current"]["value"]),
                )
                if (
                    not numerator.is_finite()
                    or not denominator.is_finite()
                    or not 0 <= numerator <= denominator
                    or denominator <= 0
                ):
                    continue
            except (InvalidOperation, ValueError, TypeError):
                continue
            pair = {
                "numerator": n,
                "denominator": d,
                "percent": str((numerator / denominator * 100).quantize(Decimal("0.0001"))),
                "kind": "BASELINE_SEGMENT_REVENUE_SHARE",
                "affected_fraction": "UNKNOWN",
                "materiality": "UNKNOWN",
                "impact_eligible": False,
            }
            pair["pair_sha256"] = digest(pair)
            result.append(pair)
    return list({x["pair_sha256"]: x for x in result}.values())


def candidates(conn, actor, claim_id):
    if not Settings.from_env().dev_informational_feed:
        raise ValueError("Private development opt-in required")
    claim = (
        conn.execute(select(claims).where(claims.c.id == claim_id).with_for_update())
        .mappings()
        .first()
    )
    if not claim or (actor.role != "admin" and actor.id != claim["author_id"]):
        raise ValueError("Claim unavailable to this account")
    return canonical_candidates(conn, claim)


def canonical_candidates(conn, claim):
    """Internal evidence validation; callers enforce authorization or approved projection."""
    if not Settings.from_env().dev_informational_feed:
        raise ValueError("Private development opt-in required")
    claim_id = claim["id"]
    receipt = (
        conn.execute(select(news_promotions).where(news_promotions.c.claim_id == claim_id))
        .mappings()
        .first()
    )
    if not receipt:
        raise ValueError("Canonical ingestion required before exposure review")
    version = (
        conn.execute(select(versions).where(versions.c.id == receipt["event_version_id"]))
        .mappings()
        .one()
    )
    latest = conn.scalar(
        select(versions.c.id)
        .where(versions.c.event_id == version["event_id"])
        .order_by(versions.c.version_number.desc())
        .limit(1)
    )
    if version["id"] != latest or version["normalized_claim"].get("news_claim_id") != claim_id:
        raise ValueError("Only current primary canonical claim may receive exposure review")
    validated_version(conn, version, datetime.now(UTC))
    revision = (
        conn.execute(select(news_revisions).where(news_revisions.c.id == claim["revision_id"]))
        .mappings()
        .one()
    )
    context = dossier(
        conn,
        revision["item_id"],
        claim["payload"]["ticker"],
        claim["payload"]["expected_payload_sha256"],
    )
    return {
        "claim_id": claim_id,
        "event_version_id": version["id"],
        "pairs": matched_pairs(context),
        "context_truncated": context["truncated"],
        "materiality": "UNKNOWN",
        "delivery": "disabled",
    }


class DraftBody(StrictModel):
    pair_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    author_kind: Literal["human_declared", "AI_SIMULATED"]
    news_link_rationale: str = Field(min_length=20, max_length=4000)
    limitations: str = Field(min_length=20, max_length=4000)


class ReviewBody(StrictModel):
    expected_version: int = Field(ge=0)
    decision: Literal["approved", "rejected", "revoked"]
    reviewer_kind: Literal["human_declared", "AI_SIMULATED"]
    periods_units_scope_confirmed: bool = False
    news_link_reviewed: bool = False
    baseline_not_effect_confirmed: bool = False
    rationale: str = Field(min_length=20, max_length=4000)


def create(conn, actor, claim_id, body):
    current = candidates(conn, actor, claim_id)
    pair = next((p for p in current["pairs"] if p["pair_sha256"] == body.pair_sha256), None)
    if not pair:
        raise ValueError("Selected evidence pair missing, incompatible or stale")
    payload = {
        **body.model_dump(mode="json"),
        "pair": pair,
        "event_version_id": current["event_version_id"],
    }
    id = str(uuid4())
    conn.execute(
        drafts.insert().values(
            id=id,
            claim_id=claim_id,
            author_id=actor.id,
            created_at=datetime.now(UTC),
            payload=payload,
            input_sha256=digest(payload),
        )
    )
    return {"id": id, "status": "pending", "materiality": "UNKNOWN", "delivery": "disabled"}


def validate_draft(conn, actor, draft):
    if digest(draft["payload"]) != draft["input_sha256"]:
        raise ValueError("Draft integrity mismatch")
    current = candidates(conn, actor, draft["claim_id"])
    if (
        draft["payload"]["event_version_id"] != current["event_version_id"]
        or draft["payload"]["pair"] not in current["pairs"]
    ):
        raise ValueError("Exposure evidence changed; create a new draft")


def latest_review(conn, id):
    return (
        conn.execute(
            select(reviews)
            .where(reviews.c.draft_id == id)
            .order_by(reviews.c.version.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )


def review(conn, actor, id, body):
    Settings.from_env()
    if actor.role != "admin":
        raise ValueError("Operator review required")
    draft = (
        conn.execute(select(drafts).where(drafts.c.id == id).with_for_update()).mappings().first()
    )
    if not draft:
        raise ValueError("Draft not found")
    old = latest_review(conn, id)
    version = old["version"] if old else 0
    if body.expected_version != version:
        raise ValueError("Review version changed")
    if body.decision == "approved":
        if actor.id == draft["author_id"]:
            raise ValueError("Independent-account review required")
        if not all(
            (
                body.periods_units_scope_confirmed,
                body.news_link_reviewed,
                body.baseline_not_effect_confirmed,
            )
        ):
            raise ValueError("Explicit evidence and baseline limitations confirmations required")
        validate_draft(conn, actor, draft)
    if body.decision == "revoked" and (not old or old["decision"] != "approved"):
        raise ValueError("Only current approval may be revoked")
    conn.execute(
        reviews.insert().values(
            id=str(uuid4()),
            draft_id=id,
            version=version + 1,
            reviewer_id=actor.id,
            recorded_at=datetime.now(UTC),
            decision=body.decision,
            payload=body.model_dump(mode="json"),
        )
    )
    return {
        "version": version + 1,
        "decision": body.decision,
        "materiality": "UNKNOWN",
        "impact_eligible": False,
        "delivery": "disabled",
    }
