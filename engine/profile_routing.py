"""Shared source-identified profile routing for archive and reviewed-source projections."""

from types import SimpleNamespace

from engine.company_profiles import paths
from engine.news_framework import eligible_route
from engine.profile_news import entity_context, matches
from engine.supply_roles import extract_supply_roles, valid_cik


def binding_decisions(bundle, narrative, article, at, *, issuer_cik=None):
    roles = extract_supply_roles(article.get("summary", ""), issuer_cik)
    if roles["routing_withheld"]:
        return
    for binding in bundle.factor_bindings:
        if roles["issuer_supply_context"] and binding.kind != "SUPPLIER_ROLE_DISCLOSURE":
            if (not binding.issuer_supply_scope or not valid_cik(bundle.identifiers.get("CIK"))
                    or int(issuer_cik) != int(bundle.identifiers["CIK"])):
                continue
        if binding.narrative_ids and narrative.id not in binding.narrative_ids:
            continue
        if not binding.enabled or not binding.reviewed_at <= at < binding.review_until:
            continue
        spans = matches(binding, article, issuer_cik=issuer_cik,
                        profile_cik=bundle.identifiers.get("CIK"), legal_name=bundle.legal_name)
        if not spans:
            continue
        if binding.entity_reference_id:
            ref = entity_context(bundle, binding.entity_reference_id, article, at)
            if not ref or not paths(bundle, SimpleNamespace(anchors=[ref["node_id"]]),
                                    narrative, effective_at=at)[0]:
                continue
        routes, truncated = paths(bundle, SimpleNamespace(anchors=[binding.factor_id]),
                                  narrative, effective_at=at)
        if binding.relevance_scope and binding.relevance_scope.relationship_id:
            routes = [route for route in routes if any(
                r.id == binding.relevance_scope.relationship_id for r in route)]
        if routes:
            qualified_route = eligible_route(bundle, narrative, sorted(routes, key=len), spans)
            if qualified_route is None:
                continue
            route, contract = qualified_route
            qualified = [{**s, "routing_contract": contract} for s in spans] if contract else spans
            yield {"binding": binding, "matches": qualified, "roles": roles["facts"],
                   "path": route, "paths_truncated": truncated}
