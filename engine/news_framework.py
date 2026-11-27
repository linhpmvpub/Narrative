"""Company-independent signal classification and narrative/graph contract.

Source lifecycle and graph validity stay with their existing owners. This layer
does not resolve an actor, create a canonical fact, infer impact or authorize push.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

POLICY = Path(__file__).resolve().parent.parent / "config/news-routing-v1.json"


@lru_cache(maxsize=1)
def policy():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def literal(term, text):
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I)


def first(terms, text):
    for term in terms:
        if hit := literal(term, text):
            return {"start": hit.start(), "end": hit.end(), "text": hit.group(), "term": term}
    return None


@lru_cache(maxsize=2048)
def classify(window):
    """Reusable source-only classification, independent of company and labels."""
    p = policy()
    components = {k: h for k, terms in p["components"].items() if (h := first(terms, window))}
    markets = {k: h for k, terms in p["markets"].items() if (h := first(terms, window))}
    action = first(p["readiness_actions"], window)
    denial = first(p["negations"], window)
    return {"version": p["version"], "window_text": window,
            "components": components, "markets": markets, "action": action,
            "negation": denial,
            "event_type": "COMPONENT_READINESS" if components and action and not denial else "UNCLASSIFIED",
            "offset_basis": "RELATIVE_TO_WINDOW_TEXT", "financial_impact": "UNKNOWN"}


def signal_matches(rule, fields):
    for field, text in fields.items():
        for sentence in re.finditer(r"[^.!?;\n]+", text):
            if len(sentence.group()) > 1200:
                continue
            signal = classify(sentence.group())
            component = next((signal["components"][c] for c in rule.components
                              if c in signal["components"]), None)
            market = signal["markets"].get(rule.market)
            if signal["event_type"] != "COMPONENT_READINESS" or not component or not market:
                continue
            # The positive market must come from this assertion, never the title.
            spans = [component, market, signal["action"]]
            return [{**s, "start": s["start"] + sentence.start(),
                     "end": s["end"] + sentence.start(), "field": field,
                     "group": group, "signal_classification": signal,
                     "context_only": True, "news_party_verified": False,
                     "relevance_role": "INPUT_READINESS_CONTEXT"}
                    for group, s in zip(("component", "market", "activity"), spans, strict=True)]
    return []


def route_contract(bundle, narrative, route, spans):
    """One contract for RSS and full-body paths; no ticker/headline condition."""
    declared = next((p for p in bundle.routing_policies if p.narrative_id == narrative.id), None)
    competition = any(r.type == "COMPETES_WITH" for r in route)
    readiness = any(s.get("relevance_role") == "INPUT_READINESS_CONTEXT" for s in spans)
    role = "COMPETITION_CONTEXT" if competition else "INPUT_READINESS_CONTEXT" if readiness else "DIRECT_CONTEXT"
    if declared is None and not readiness:
        return None  # Legacy profiles preserve their original representation/behavior.
    allowed = declared is not None and (
        "COMPETITION" in declared.intents if competition else
        bool(set(declared.intents) & {"SUPPLY", "DEPLOYMENT"}) if readiness else True)
    return {"version": policy()["version"], "allowed": bool(allowed), "role": role,
            "intents": declared.intents if declared else [],
            "reason": "SOURCED_ROUTE_WITHIN_NARRATIVE" if allowed else "ROUTE_OUTSIDE_DECLARED_NARRATIVE",
            "explanation": policy()["route_explanations"][role],
            "relation_types": [r.type for r in route], "financial_impact": "UNKNOWN",
            "stages": ["SOURCE_VERSION_CHECKED", "FACTOR_MATCHED", "SOURCED_GRAPH_ROUTE",
                       "NARRATIVE_SCOPE_CHECKED", "CONTEXT_EXPLAINED", "DELIVERY_DISABLED"]}


def eligible_route(bundle, narrative, routes, spans):
    """A rejected short path must not hide another valid sourced path."""
    for route in routes:
        contract = route_contract(bundle, narrative, route, spans)
        if contract is None or contract["allowed"]:
            return route, contract
    return None
