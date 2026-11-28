"""Versioned editorial event eligibility over accepted source/graph assertions.

No tickers, source identities, labels, numerical impact or notification decisions.
Freshness, corrections and withdrawal remain mandatory at the feed boundary.
"""

import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def policy():
    return json.loads((Path(__file__).resolve().parent.parent /
                       "config/editorial-priority-v1.json").read_text(encoding="utf-8"))


def exclusion(text):
    for kind in ("uncertain", "retrospective", "routine"):
        if any(re.search(p, text, re.I) for p in policy()[kind + "_patterns"]):
            return kind.upper() + "_SOURCE_WINDOW"
    return None


def mentions(text, terms):
    return any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text, re.I) for t in terms)


def scoped(item, matches):
    """None means legacy; a rejected scoped decision must not fall back to keywords."""
    hit = next((m for m in matches if m.get("assertion_scope")), None)
    if hit is None:
        return None
    scope = hit["assertion_scope"]
    frame = scope.get("assertion", {})
    route = hit.get("routing_contract", {})
    argument = scope.get("object_argument", {})
    predicate = scope.get("predicate_span") or {}
    event = argument.get("event_type") or predicate.get("event_type")
    if scope.get("reason") == "EXPLICIT_SHARED_MARKET_CONSTRAINT":
        event = "CONSTRAINT"
    result = {"version": policy()["version"], "eligible": False, "event_type": event,
              "phase": frame.get("phase", "UNKNOWN"), "role": route.get("role", "UNKNOWN"),
              "intents": route.get("intents", []), "scope_reason": scope.get("reason"),
              "relationship_id": scope.get("relationship_id"), "reason": "SOURCE_SCOPE_REQUIRED",
              "financial_impact": "UNKNOWN", "delivery": "disabled",
              "freshness_basis": "CONTENT_ONLY_REQUIRES_CALLER_LIFECYCLE_GATES"}
    if not scope.get("allowed"):
        return result
    if not route.get("allowed") or not set(route.get("intents", [])) & set(policy()["roles"].get(route.get("role"), [])):
        return {**result, "reason": "DECLARED_NARRATIVE_ROUTE_REQUIRED"}
    # Validate the unchanged source window against the actual matched field.
    field = hit["field"]
    text = item["headline"] if field == "title" else item["excerpt"]
    value = frame.get("text", "")
    spans = [m for m in matches if m["field"] == field]
    window = next((m for m in re.finditer(re.escape(value), text)
                   if value and all(m.start() <= s["start"] < s["end"] <= m.end() for s in spans)), None)
    if window is None:
        return {**result, "reason": "SOURCE_WINDOW_MISMATCH"}
    result["source_window"] = {"field": field, "start": window.start(), "end": window.end(),
                               "text": window.group(), "offset_basis": "RELATIVE_TO_MATCH_FIELD"}
    if reason := exclusion(value):
        return {**result, "reason": reason}
    if frame.get("phase") not in policy()["phases"] or frame.get("negation"):
        return {**result, "reason": "PHASE_OR_NEGATION_WITHHELD"}
    if event not in policy()["events"]:
        return {**result, "reason": "CONCRETE_EVENT_ARGUMENT_REQUIRED"}
    if (event == "PRODUCTION" and predicate.get("text", "").casefold() in policy()["ongoing_production_predicates"]
            and frame.get("phase") != "FORWARD_LOOKING" and not mentions(value, policy()["change_markers"])):
        return {**result, "reason": "ONGOING_OPERATION_WITHOUT_CHANGE"}
    if event == "CAPACITY" and not mentions(value, policy()["capacity_objects"]):
        return {**result, "reason": "CAPACITY_OBJECT_REQUIRED"}
    if event == "CONSTRAINT" and not mentions(value, policy()["physical_constraints"]):
        return {**result, "reason": "PRICE_COMPARISON_THRESHOLD_REQUIRED"}
    if scope.get("reason") in policy()["actor_reasons"]:
        if not scope.get("subject_span") or not predicate:
            return {**result, "reason": "ACTOR_PREDICATE_REQUIRED"}
    elif scope.get("reason") == "EXPLICIT_SHARED_MARKET_CONSTRAINT":
        if route.get("role") not in {"INPUT_READINESS_CONTEXT", "INPUT_MARKET_CONTEXT"}:
            return {**result, "reason": "SHARED_MARKET_ROUTE_REQUIRED"}
    else:
        return {**result, "reason": "NAMED_PLATFORM_IS_NOT_OPERATOR_ASSERTION"}
    return {**result, "eligible": True, "reason": "SCOPED_DEVELOPMENT_WITHIN_NARRATIVE",
            "source_assertion": scope}
