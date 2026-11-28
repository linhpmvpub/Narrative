"""Sourced company candidates before narrative attribution. Always research context.

No ticker branches, inferred suppliers, canonical events or delivery authorization.
Profile rules own names, exact exposure paths and business scope; code owns syntax.
"""

from engine.issuer_events import matches as issuer_matches

MEMBERSHIP = {"SELLS", "HAS_SEGMENT", "HAS_METRIC"}


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
        entity = None
        if rule.kind == "ISSUER_EVENT":
            spans = list(issuer_matches(rule.names, article))
        else:
            binding, route, membership = validate_exposure(bundle, rule)
            if not binding.enabled or not binding.reviewed_at <= at < binding.review_until:
                continue
            if any(r.status != "SOURCE_BACKED" or r.known_at > at or not r.valid_from <= at
                   or r.valid_until is not None and at >= r.valid_until for r in [*route, *membership]):
                continue
            if binding.entity_reference_id:
                entity = entity_context(bundle, binding.entity_reference_id, article, at)
                if entity is None:
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
                       "source_unit": {"title": article.get("title", ""), "summary": article.get("summary", "")},
                       "entity_context": entity,
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


def source_decisions(value, bundle, at, *, article_root=None):
    """Shared RSS/reviewed full-body entry point, with original unit spans."""
    if not bundle.company_discovery:
        return []
    article = value["article"]
    if "source_observation" not in value:
        return decisions(bundle, article, at)
    from engine.article_cards import substantive_blocks
    from engine.source_sentences import source_units

    blocks, _ = substantive_blocks(value["source_observation"], at, article_root=article_root)
    result = decisions(bundle, {"title": article.get("title", "")}, at)
    for block in blocks:
        for unit in source_units(block["text"]):
            for decision in decisions(bundle, {**unit, "context_title": article.get("title", "")}, at):
                result.append({**decision, "body_unit": unit, "source_spans": block["source_spans"]})
    return result
