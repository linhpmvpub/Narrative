"""Attach one-step knowledge as explanation only; compare identical commodity decisions."""

from copy import deepcopy
from datetime import UTC, datetime

from engine.ingestion.contracts import digest
from engine.knowledge_priors import build, lookup


def audit(data, bundle, *, at=None):
    at = at or datetime.now(UTC)
    if bundle["atlas_sha256"] != digest(data):
        raise ValueError("Prior atlas changed; rebuild before evaluation")
    rebuilt = build(
        data,
        bundle["rules"],
        author=bundle["author"],
        at=datetime.fromisoformat(bundle["created_at"]),
    )
    if digest(rebuilt) != digest(bundle):
        raise ValueError("Prior derivation changed")
    rows = []
    for prior in bundle["priors"]:
        result = lookup(bundle, data, prior["relation_id"], prior["dimension"], at=at)
        rows.append(
            {
                "prior_id": prior["id"],
                "relation_id": prior["relation_id"],
                "dimension": prior["dimension"],
                "available": result["origin"] == "LLM_PRIOR_UNVERIFIED",
                "source_check": "PREMISE_IN_PINNED_ATLAS_NOT_INDEPENDENT_CONCLUSION_SUPPORT",
                "source_ids": sorted({e["source_id"] for e in prior["premise_evidence"]}),
                "conclusion_verified": False,
            }
        )
    return {
        "atlas_sha256": digest(data),
        "prior_bundle_sha256": digest(bundle),
        "rows": rows,
        "independent_labels": 0,
        "delivery": "disabled",
    }


def compare(result, data, bundle, *, at=None):
    """Consume a fresh commodity evaluator result, never enable alerts from a prior."""
    at = at or datetime.now(UTC)
    if (
        result.get("delivery") != "disabled"
        or result.get("mode") != "LOCAL_COMMODITY_RELEVANCE_NOT_VERIFIED_IMPACT"
    ):
        raise ValueError("Disabled commodity workbench result required")
    if result.get("atlas_sha256", digest(data)) != digest(data):
        raise ValueError("Result atlas mismatch")
    before = deepcopy(result)
    after = deepcopy(result)
    report = audit(data, bundle, at=at)
    eligible = {
        r["relation_id"]
        for r in report["rows"]
        if r["available"] and r["dimension"] == "input_cost_sensitivity"
    }
    notes = 0
    for card in after.get("candidate_alerts", []):
        if "knowledge_context" in card:
            raise ValueError("Already enriched result; do not chain annotations")
        if not result.get("source_current") or not result.get("period_recent"):
            raise ValueError("Candidate cannot carry stale source/period")
        relation_id = card["usage_relation_id"]
        if relation_id not in eligible:
            continue
        prior = lookup(bundle, data, relation_id, "input_cost_sensitivity", at=at)["value"]
        # No numeric estimate propagation; explanatory condition is the existing one-step prior.
        if prior["unit"] != "category":
            continue
        card["knowledge_context"] = {
            "label": "Tri thức LLM — chưa xác minh",
            "status": prior["status"],
            "prior_id": prior["id"],
            "rule_id": prior["rule_id"],
            "rule_version": prior["rule_version"],
            "category": prior["category"],
            "basis": prior["knowledge_basis"],
            "scope": prior["scope"],
            "conditions": prior["conditions"],
            "exceptions": prior["exceptions"],
            "premise_evidence": prior["premise_evidence"],
            "evidence_role": "SUPPORTS_RELATIONSHIP_NOT_LLM_CONCLUSION",
            "inference_steps": 1,
            "used_for_score": False,
            "used_for_financial_magnitude": False,
        }
        notes += 1
    stripped = deepcopy(after)
    for card in stripped.get("candidate_alerts", []):
        card.pop("knowledge_context", None)
    if stripped != before:
        raise ValueError("Explanation enrichment changed a decision")
    return {
        "without_priors": before,
        "with_priors": after,
        "comparison": {
            "candidate_count_without": len(before.get("candidate_alerts", [])),
            "candidate_count_with": len(after.get("candidate_alerts", [])),
            "candidate_delta": 0,
            "cards_with_explanation": notes,
            "decision_fields_unchanged": True,
            "accuracy_improvement": "NOT_MEASURED",
            "independent_labels": 0,
        },
        "prior_audit": report,
        "delivery": "disabled",
    }
