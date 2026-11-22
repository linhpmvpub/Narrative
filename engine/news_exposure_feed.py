"""Allowlisted, currently valid approved baseline shares, never graph edges."""

from datetime import UTC, datetime

from sqlalchemy import select

from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.news_claims import claims
from engine.news_exposure import DraftBody, ReviewBody, canonical_candidates, drafts, latest_review
from engine.settings import Settings


def approved_shares(conn, cutoff, *, event_version_ids=None, limit=500):
    if cutoff.tzinfo is None or cutoff > datetime.now(UTC):
        raise ValueError("Aware nonfuture cutoff required")
    if not 1 <= limit <= 500:
        raise ValueError("Invalid exposure candidate limit")
    empty = {
        "items": [],
        "truncated": False,
        "examined": 0,
        "policy": "CURRENT_VALID_APPROVAL_RECORDED_BY_CUTOFF",
        "graph_modified": False,
    }
    if not Settings.from_env().dev_informational_feed or event_version_ids == []:
        return empty
    query = (
        select(drafts)
        .where(drafts.c.created_at <= cutoff)
        .order_by(drafts.c.created_at.desc(), drafts.c.id)
    )
    # Select by indexed claim membership rather than sharing private draft records with clients.
    if event_version_ids is not None:
        from engine.models.schema_v15 import news_promotions

        query = query.where(
            drafts.c.claim_id.in_(
                select(news_promotions.c.claim_id).where(
                    news_promotions.c.event_version_id.in_(event_version_ids)
                )
            )
        )
    rows = conn.execute(query.limit(limit + 1)).mappings().all()
    output = []
    seen = set()
    contexts = {}
    for row in rows[:limit]:
        try:
            review = latest_review(conn, row["id"])
            if (
                not review
                or review["decision"] != "approved"
                or review["reviewer_id"] == row["author_id"]
                or utc(review["recorded_at"]) > cutoff
                or utc(review["recorded_at"]) < utc(row["created_at"])
            ):
                continue
            proof = ReviewBody.model_validate(review["payload"])
            if proof.decision != "approved" or not all(
                (
                    proof.periods_units_scope_confirmed,
                    proof.news_link_reviewed,
                    proof.baseline_not_effect_confirmed,
                )
            ):
                continue
            payload = row["payload"]
            if digest(payload) != row["input_sha256"]:
                continue
            body = DraftBody.model_validate({k: payload[k] for k in DraftBody.model_fields})
            if payload["pair_sha256"] != payload["pair"]["pair_sha256"]:
                continue
            if row["claim_id"] not in contexts:
                claim = (
                    conn.execute(select(claims).where(claims.c.id == row["claim_id"]))
                    .mappings()
                    .one()
                )
                contexts[row["claim_id"]] = canonical_candidates(conn, claim)
            current = contexts[row["claim_id"]]
            if (
                payload["event_version_id"] != current["event_version_id"]
                or payload["pair"] not in current["pairs"]
            ):
                continue
            pair = payload["pair"]
            n, d = pair["numerator"], pair["denominator"]
            key = (current["event_version_id"], pair["pair_sha256"])
            if key in seen:
                continue
            seen.add(key)

            def operand(x):
                return {
                    k: x[k]
                    for k in (
                        "ticker",
                        "accession",
                        "concept",
                        "unit",
                        "scope",
                        "current",
                        "source_url",
                        "filing_url",
                        "source_sha256",
                        "snapshot_id",
                        "snapshot_version",
                        "available_at",
                    )
                }

            output.append(
                {
                    "event_version_id": current["event_version_id"],
                    "ticker": n["ticker"],
                    "segment": n["segment"],
                    "pair_sha256": pair["pair_sha256"],
                    "percent": pair["percent"],
                    "kind": "BASELINE_SEGMENT_REVENUE_SHARE",
                    "numerator": operand(n),
                    "denominator": operand(d),
                    "reviewed_at": utc(review["recorded_at"]).isoformat(),
                    "author_kind": body.author_kind,
                    "reviewer_kind": proof.reviewer_kind,
                    "affected_fraction": "UNKNOWN",
                    "materiality": "UNKNOWN",
                    "causal_attribution": "NOT_ESTABLISHED",
                    "graph_eligible": False,
                    "impact_eligible": False,
                }
            )
        except (ValueError, KeyError, TypeError):
            continue
    return {
        **empty,
        "items": output,
        "truncated": len(rows) > limit,
        "examined": min(len(rows), limit),
    }
