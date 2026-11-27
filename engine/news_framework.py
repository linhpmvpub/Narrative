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
            assertion = None
            selected_event = None
            if rule.event_types:
                from engine.news_assertions import frame

                assertion = frame(sentence.group())
                selected_event = next((e for e in rule.event_types if e in assertion["activities"]), None)
                action = assertion["activities"].get(selected_event)
                signal = {**signal, "action": action, "event_type": "COMPONENT_" + selected_event
                          if selected_event and not assertion["negation"] else "UNCLASSIFIED"}
            component = next((signal["components"][c] for c in rule.components
                              if c in signal["components"]), None)
            market = signal["markets"].get(rule.market)
            if signal["event_type"] == "UNCLASSIFIED" or not component or not market:
                continue
            # The positive market must come from this assertion, never the title.
            spans = [component, market, signal["action"]]
            return [{**s, "start": s["start"] + sentence.start(),
                     "end": s["end"] + sentence.start(), "field": field,
                     "group": group, "signal_classification": signal,
                     **({"source_assertion": assertion} if assertion else {}),
                     "context_only": True, "news_party_verified": False,
                     "relevance_role": "INPUT_MARKET_CONTEXT" if selected_event == "CONSTRAINT" else "INPUT_READINESS_CONTEXT"}
                    for group, s in zip(("component", "market", "activity"), spans, strict=True)]
    return []


def route_contract(bundle, narrative, route, spans):
    """One contract for RSS and full-body paths; no ticker/headline condition."""
    declared = next((p for p in bundle.routing_policies if p.narrative_id == narrative.id), None)
    competition = any(r.type == "COMPETES_WITH" for r in route)
    input_role = next((s["relevance_role"] for s in spans if s.get("relevance_role") in {
        "INPUT_READINESS_CONTEXT", "INPUT_MARKET_CONTEXT"}), None)
    readiness = input_role is not None
    role = "COMPETITION_CONTEXT" if competition else input_role if readiness else "DIRECT_CONTEXT"
    if declared is None and not readiness:
        return None  # Legacy profiles preserve their original representation/behavior.
    allowed = declared is not None and (
        "COMPETITION" in declared.intents if competition else
        bool(set(declared.intents) & {"SUPPLY", "DEPLOYMENT"}) if readiness else True)
    scoped = next((s["assertion_scope"] for s in spans if s.get("assertion_scope")), None)
    explanation = policy()["route_explanations"][role]
    if scoped:
        explanation += " " + {
            "NAMED_OPERATOR_ACTIVITY": "Nguồn nêu hoạt động của bên có tên trong phạm vi quan hệ; chưa xác minh giao dịch với công ty.",
            "NAMED_PLATFORM_CONTEXT": "Nguồn nêu nền tảng thuộc phạm vi đang theo dõi; chưa xác minh tương thích hay triển khai thực tế.",
            "EXPLICIT_SHARED_MARKET_CONSTRAINT": "Nguồn nêu ràng buộc của thị trường chung; mức ảnh hưởng riêng tới công ty chưa xác định.",
            "OWNERSHIP_OBJECT": "Nguồn gắn bên có tên với giao dịch tài sản thuộc nhóm sản phẩm liên quan; chưa xác minh thay đổi nguồn cung hoặc tác động tài chính.",
            "FINANCING_PURPOSE_OBJECT": "Nguồn nêu mục đích phân bổ vốn gắn với sản phẩm hoặc hoạt động liên quan; chưa chứng minh triển khai, sản lượng hay lợi nhuận.",
        }[scoped["reason"]]
    return {"version": policy()["version"], "allowed": bool(allowed), "role": role,
            "intents": declared.intents if declared else [],
            "reason": "SOURCED_ROUTE_WITHIN_NARRATIVE" if allowed else "ROUTE_OUTSIDE_DECLARED_NARRATIVE",
            "explanation": explanation,
            **({"assertion_scope": scoped} if scoped else {}),
            "relation_types": [r.type for r in route], "financial_impact": "UNKNOWN",
            "stages": ["SOURCE_VERSION_CHECKED", "FACTOR_MATCHED", "SOURCED_GRAPH_ROUTE",
                       "NARRATIVE_SCOPE_CHECKED", "CONTEXT_EXPLAINED", "DELIVERY_DISABLED"]}


def eligible_route(bundle, narrative, routes, spans):
    """A rejected short path must not hide another valid sourced path."""
    for route in routes:
        required = {s["assertion_scope"]["relationship_id"] for s in spans if s.get("assertion_scope")}
        if required and not required <= {r.id for r in route}:
            continue
        contract = route_contract(bundle, narrative, route, spans)
        if contract is None or contract["allowed"]:
            return route, contract
    return None
