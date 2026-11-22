"""Read-only operator snapshots of news canonical versions available at a cutoff."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from engine.ingestion.contracts import canonical_key, digest
from engine.ingestion.news_reviewed import IngestBody
from engine.ingestion.reviewed import events, fact, sources, versions
from engine.models.contracts import utc
from engine.models.schema_v15 import news_promotions as promotions
from engine.news_claims import ClaimBody, ReviewBody, claims, intakes, latest_review, validate
from engine.sec_review import require_real
from engine.settings import Settings


def validated_version(conn, version, at):
    claim_id = version["normalized_claim"].get("news_claim_id")
    draft = conn.execute(select(claims).where(claims.c.id == claim_id)).mappings().first()
    receipt = (
        conn.execute(
            select(promotions).where(
                promotions.c.claim_id == claim_id, promotions.c.recorded_at <= at
            )
        )
        .mappings()
        .first()
    )
    if not draft or not receipt or receipt["event_version_id"] != version["id"]:
        raise ValueError("Missing primary claim or ingestion receipt at cutoff")
    approved = latest_review(conn, claim_id, at)
    if (
        not approved
        or approved["decision"] != "approved"
        or approved["id"] != receipt["review_id"]
        or approved["reviewer_id"] == draft["author_id"]
    ):
        raise ValueError("Primary claim approval unavailable or replaced at cutoff")
    proof = ReviewBody.model_validate(approved["payload"])
    if proof.decision != "approved" or not all(
        (proof.identity_confirmed, proof.citation_confirmed, proof.comparison_confirmed)
    ):
        raise ValueError("Invalid approval proof")
    body = ClaimBody.model_validate(draft["payload"])
    if digest(draft["payload"]) != draft["input_sha256"]:
        raise ValueError("Claim integrity mismatch")
    row, event = validate(conn, body, at, historical=True)
    intake = (
        conn.execute(
            select(intakes).where(
                intakes.c.claim_id == claim_id,
                intakes.c.review_id == approved["id"],
                intakes.c.created_at <= at,
            )
        )
        .mappings()
        .first()
    )
    if not intake:
        raise ValueError("Intake unavailable at cutoff")
    payload = intake["payload"]
    clocks = [
        utc(row["received_at"]),
        utc(draft["created_at"]),
        utc(approved["recorded_at"]),
        utc(intake["created_at"]),
        utc(receipt["recorded_at"]),
    ]
    if clocks != sorted(clocks) or clocks[-1] > at or utc(version["available_at"]) != clocks[-1]:
        raise ValueError("Source/review/ingestion chronology mismatch")
    request = IngestBody.model_validate(receipt["request"])
    if (
        digest(payload) != intake["payload_sha256"]
        or request.expected_intake_sha256 != intake["payload_sha256"]
        or digest([intake["payload_sha256"], receipt["request"]]) != receipt["input_sha256"]
        or payload["event"] != event.model_dump(mode="json")
        or payload["claim_id"] != claim_id
        or payload["review_id"] != approved["id"]
        or payload["source_revision_id"] != row["id"]
        or payload["source_payload_sha256"] != body.expected_payload_sha256
        or payload.get("comparison_period") != body.comparison_period
        or not request.identity_confirmed
        or request.action == "duplicate"
    ):
        raise ValueError("Ingestion provenance mismatch")
    claim = event.claims[0]
    expected_key = canonical_key(
        issuer=event.entity_ids[0],
        event_type=event.event_type,
        metric=claim.metric_id or "qualitative",
        period=claim.period or "unspecified",
        basis=claim.comparison_basis,
        occurrence_window=request.occurrence_window,
    )
    if (
        version["event_id"] != expected_key
        or version["normalized_claim"]["extraction"] != payload["event"]
        or version["normalized_claim"]["fact"]
        != {**fact(event), "comparison_period": body.comparison_period}
    ):
        raise ValueError("Canonical content or identity mismatch")
    source = (
        conn.execute(select(sources).where(sources.c.id == "news-reviewed:" + row["id"]))
        .mappings()
        .first()
    )
    # Source rights are not temporal yet. Enforce current blocks, never infer past approval.
    if not source or source["rights_status"] == "blocked":
        raise ValueError("Source currently blocked or missing")
    return dict(
        event_id=version["event_id"],
        event_version_id=version["id"],
        version=version["version_number"],
        claim_id=claim_id,
        review_id=approved["id"],
        source_revision_id=row["id"],
        source_url=claim.source_url,
        source_payload_sha256=body.expected_payload_sha256,
        headline=event.factual_headline,
        claim=body.claim.model_dump(mode="json"),
        comparison_period=body.comparison_period,
        uncertainties=body.uncertainties,
        published_at=event.published_at,
        captured_at=event.available_at,
        available_at=utc(version["available_at"]),
        author_kind=body.author_kind,
        reviewer_kind=proof.reviewer_kind,
        occurrence_window=request.occurrence_window,
        source_rights="PRIVATE_DEVELOPMENT_ONLY_NOT_APPROVAL",
        materiality="UNKNOWN",
        feed_eligible=False,
        graph_eligible=False,
    )


def snapshot(conn, at, limit=100):
    settings = Settings.from_env()
    if not settings.dev_informational_feed:
        raise ValueError("Private development opt-in required")
    require_real(conn)
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Cutoff must have timezone and cannot be in the future")
    if not 1 <= limit <= 500:
        raise ValueError("Limit must be between 1 and 500")
    at = at.astimezone(UTC)
    latest = (
        select(versions.c.event_id, func.max(versions.c.version_number).label("number"))
        .where(versions.c.available_at <= at)
        .group_by(versions.c.event_id)
        .subquery()
    )
    rows = (
        conn.execute(
            select(versions)
            .join(
                latest,
                (versions.c.event_id == latest.c.event_id)
                & (versions.c.version_number == latest.c.number),
            )
            .join(events, events.c.id == versions.c.event_id)
            .where(
                events.c.is_synthetic.is_(False),
                events.c.available_at <= at,
                versions.c.extraction_model == "reviewed-news-v1",
            )
            .order_by(versions.c.available_at.desc(), versions.c.id)
            .limit(limit + 1)
        )
        .mappings()
        .all()
    )
    items, withheld = [], []
    for row in rows[:limit]:
        try:
            items.append(validated_version(conn, row, at))
        except (ValueError, KeyError, TypeError) as exc:
            withheld.append(
                {"event_id": row["event_id"], "event_version_id": row["id"], "reason": str(exc)}
            )
    return dict(
        as_of=at,
        items=items,
        withheld=withheld,
        truncated=len(rows) > limit,
        examined=min(len(rows), limit),
        limit=limit,
        delivery="disabled",
        source_block_policy="CURRENT_BLOCK_OVERRIDES_HISTORICAL_SNAPSHOT",
        feed_eligible=False,
        graph_eligible=False,
    )
