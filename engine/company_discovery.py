"""Sourced company candidates before narrative attribution. Always research context.

No ticker branches, inferred suppliers, canonical events or delivery authorization.
Profile rules own names, exact exposure paths and business scope; code owns syntax.
"""

import re

from engine.source_sentences import sentences

MEMBERSHIP = {"SELLS", "HAS_SEGMENT", "HAS_METRIC"}
ISSUER_EVENTS = {
    "FINANCIAL_RESULTS": r"\s+(?:reports?|announces?|posts?)\s+(?:[\w-]+\s+){0,9}(?:financial results|earnings|revenue|net income)\b",
    "FINANCING": r"\s+(?:raises?|secures?|issues?|repays?|refinances?)\s+[^.;!?]{0,90}\b(?:debt|bonds?|loans?|funding|financing|credit facility)\b",
    "GOVERNANCE": r"\s+(?:appoints?|names?|removes?|dismisses?)\s+[^.;!?]{0,90}\b(?:CEO|CFO|chief executive|chief financial|director|board chair)\b",
    "CREDIT_RISK": r"(?:['’]s)?\s+credit (?:rating|outlook)\s+(?:(?:could|may|might|will|be|was|is|has|been|by|a|one|notch)\s+){0,7}(?:cut|downgraded|upgraded|lowered|raised)\b",
}


def validate_exposure(bundle, rule):
    binding = next((b for b in bundle.factor_bindings if b.id == rule.binding_id), None)
    edges = {r.id: r for r in bundle.relationships}
    if binding is None or any(k not in edges for k in [*rule.relation_ids, *rule.membership_ids]):
        raise ValueError("Discovery binding and exact graph edges required")
    path = [edges[k] for k in rule.relation_ids]
    ownership = [edges[k] for k in rule.membership_ids]
    if (path[0].from_id != binding.factor_id or ownership[0].from_id != bundle.company_id
            or path[-1].to_id != ownership[-1].to_id
            or any(r.type not in MEMBERSHIP for r in ownership)):
        raise ValueError("Discovery exposure must reach a company-owned product/segment/metric")
    for route in (path, ownership):
        if (len({route[0].from_id, *(r.to_id for r in route)}) != len(route) + 1
                or any(a.to_id != b.from_id for a, b in zip(route, route[1:], strict=False))):
            raise ValueError("Exact simple ordered discovery path required")
    if binding.relevance_scope and binding.relevance_scope.relationship_id:
        if binding.relevance_scope.relationship_id not in rule.relation_ids:
            raise ValueError("Discovery cannot bypass the binding's exact mechanism")
    return binding, path, ownership


def issuer_matches(names, article):
    for field in ("title", "summary"):
        text = article.get(field, "")
        for sentence in sentences(text):
            if len(sentence.group()) > 1200:
                continue
            for name in sorted(names, key=len, reverse=True):
                for family, tail in ISSUER_EVENTS.items():
                    hit = re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)" + tail, sentence.group(), re.I)
                    if (hit and not re.search(r"\b(?:not|never|no|fake|falsely)\b", hit.group(), re.I)
                            and not re.search(r"\b(?:if|whether|how)\s*$", sentence.group()[:hit.start()], re.I)
                            and not text[sentence.end():].startswith("?")):
                        yield {"field": field, "start": sentence.start() + hit.start(),
                               "end": sentence.start() + hit.end(), "text": hit.group(),
                               "event_family": family, "context_only": True,
                               "news_party_verified": False}


def decisions(bundle, article, at):
    """Current-profile text relevance; callers own source lifecycle/freshness."""
    if at < bundle.available_at:
        return []
    from engine.news_framework import eligible_route
    from engine.profile_news import entity_context, matches

    nodes = {n.id: n.label for n in bundle.nodes}
    sources = {s.id: s for s in bundle.sources}
    result = []
    for rule in bundle.company_discovery:
        if not rule.enabled or not rule.reviewed_at <= at < rule.review_until:
            continue
        route, membership, contract = [], [], None
        if rule.kind == "ISSUER_EVENT":
            spans = list(issuer_matches(rule.names, article))
        else:
            binding, route, membership = validate_exposure(bundle, rule)
            if not binding.enabled or not binding.reviewed_at <= at < binding.review_until:
                continue
            if any(r.status != "SOURCE_BACKED" or r.known_at > at or not r.valid_from <= at
                   or r.valid_until is not None and at >= r.valid_until for r in [*route, *membership]):
                continue
            if binding.entity_reference_id and not entity_context(bundle, binding.entity_reference_id, article, at):
                continue
            spans = matches(binding, article, bundle=bundle, at=at)
            if not spans:
                continue
            qualified = eligible_route(bundle, None, [route], spans, company_scope=rule)
            if qualified is None:
                continue
            _, contract = qualified
        if not spans:
            continue
        evidence = [*rule.evidence, *(e for r in [*route, *membership] for e in r.evidence)]
        source_ids = {e.source_id for e in evidence}
        def serialize(edge):
            return {"id": edge.id, "from": nodes[edge.from_id], "to": nodes[edge.to_id],
                    "type": edge.type, "scope": edge.scope, "conditions": edge.conditions,
                    "evidence": [e.model_dump() for e in edge.evidence]}
        result.append({"rule_id": rule.id, "kind": rule.kind, "scope": rule.scope,
                       "matches": spans, "path": [serialize(r) for r in route],
                       "membership_path": [serialize(r) for r in membership],
                       "company": nodes[bundle.company_id], "routing_contract": contract,
                       "evidence": [e.model_dump() for e in rule.evidence],
                       "sources": [{"id": k, "url": str(sources[k].url), "sha256": sources[k].sha256}
                                   for k in sorted(source_ids)],
                       "max_news_age_days": min(rule.max_news_age_days, binding.max_news_age_days)
                       if rule.kind == "FACTOR_EXPOSURE" else rule.max_news_age_days,
                       "explanation": "Nguồn nêu diễn biến gắn với tên doanh nghiệp trong hồ sơ. Chưa xác minh thông tin hoặc tác động tài chính."
                       if rule.kind == "ISSUER_EVENT" else
                       "Yếu tố trong tin có đường liên hệ với sản phẩm của công ty theo hồ sơ có nguồn. Đây là bối cảnh có điều kiện, chưa xác minh đơn hàng hay tác động.",
                       "direction": "UNKNOWN", "financial_magnitude": "UNKNOWN", "horizon": "UNKNOWN",
                       "delivery": "disabled"})
    return result


def source_decisions(value, bundle, at):
    """Shared RSS/reviewed full-body entry point, with original unit spans."""
    if not bundle.company_discovery:
        return []
    article = value["article"]
    if "source_observation" not in value:
        return decisions(bundle, article, at)
    from engine.article_cards import substantive_blocks
    from engine.source_sentences import source_units

    blocks, _ = substantive_blocks(value["source_observation"], at)
    result = decisions(bundle, {"title": article.get("title", "")}, at)
    for block in blocks:
        for unit in source_units(block["text"]):
            for decision in decisions(bundle, {**unit, "context_title": article.get("title", "")}, at):
                result.append({**decision, "body_unit": unit, "source_spans": block["source_spans"]})
    return result
