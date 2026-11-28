"""Read-only RSS topic candidates linked through sourced company factors.

No claim extraction, polarity inference, canonical ingestion or notification.
Every read rechecks current revisions, profile evidence and binding lifetimes.
"""

import os
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from types import SimpleNamespace

from sqlalchemy import and_, select

from engine.activity_events import activity_matches
from engine.adapters.news import canonical_url, parse_feed
from engine.company_profiles import RELATIONS, available_bundles, paths
from engine.ingestion.contracts import digest
from engine.issuer_operations import operating_matches, shipment_matches
from engine.models.contracts import utc
from engine.models.schema_v13 import news_items, news_revisions, news_sources
from engine.news_applicability import assess as assess_applicability
from engine.news_capture import read_capture
from engine.news_framework import eligible_route, signal_matches
from engine.routing_guards import assess as assess_guards
from engine.source_sentences import declared_reference, sentences
from engine.supply_roles import extract_supply_roles, supplier_span, valid_cik


@lru_cache(maxsize=4096)
def pattern(term):
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)


def matches(binding, payload, *, issuer_cik=None, profile_cik=None, legal_name="", bundle=None, at=None):
    """Exact original-field spans; context groups must all match, no ticker shortcut."""
    fields = {k: payload.get(k, "") for k in ("title", "summary")}
    if binding.project_finance:
        from engine.project_finance import matches as finance_matches

        return finance_matches(binding, fields, payload=payload)
    if binding.readiness_context:
        from engine.readiness_context import matches as readiness_matches

        return readiness_matches(binding, fields, context_title=payload.get("context_title", ""), payload=payload)
    if binding.access_constraint:
        from engine.access_constraints import matches as access_matches

        return access_matches(binding, fields, payload=payload)
    if binding.assertion_scope:
        from engine.news_assertions import applicability as assertion_applicability
        from engine.news_assertions import windows

        rule = binding.model_copy(update={"assertion_scope": None})
        for field, text in fields.items():
            for window in windows(text):
                if len(window.group()) > 1200:
                    continue
                scope = binding.assertion_scope
                context, offset = text, 0
                if field == "summary" and isinstance(payload.get("source_offset"), int):
                    candidate, position = payload.get("source_context", ""), payload["source_offset"]
                    if position >= 0 and candidate[position:position + len(text)] == text:
                        context, offset = candidate, position
                reference = declared_reference(scope, context, offset + window.start())
                if reference:
                    scope = scope.model_copy(update={"subject_terms": [*scope.subject_terms, reference["alias"]]})
                trace = assertion_applicability(scope, window.group())
                if reference and trace.get("subject_span") and trace["subject_span"]["text"].casefold() == reference["alias"].casefold():
                    if offset + window.start() + trace["subject_span"]["start"] != reference["reference_span"]["start"]:
                        continue
                    trace["subject_reference"] = reference
                if not trace["allowed"]:
                    continue
                scoped_rule = rule
                if trace.get("subject_reference"):
                    declared_names = {t.casefold() for t in binding.assertion_scope.subject_terms}
                    scoped_rule = scoped_rule.model_copy(update={"topic_terms": [
                        reference["alias"] if t.casefold() in declared_names else t for t in rule.topic_terms]})
                if rule.kind == "SCOPED_ACTIVITY" and trace.get("predicate_span"):
                    # The typed predicate already passed the source-actor contract;
                    # a second legacy verb vocabulary must not veto that same event.
                    scoped_rule = scoped_rule.model_copy(update={"change_terms": [trace["predicate_span"]["text"]]})
                hits = matches(scoped_rule, {field: window.group(), "context_title": payload.get("context_title", fields["title"])},
                               issuer_cik=issuer_cik, profile_cik=profile_cik, legal_name=legal_name, bundle=bundle, at=at)
                if hits:
                    return [{**h, "start": h["start"] + window.start(), "end": h["end"] + window.start(),
                             **({"context_only": True} if trace.get("object_argument") else {}),
                             "assertion_scope": trace} for h in hits]
        return []
    if binding.kind == "CLASSIFIED_CONTEXT":
        return signal_matches(binding.signal_rule, fields)
    if binding.market_scope or binding.routing_guards:
        rule = binding.model_copy(update={"market_scope": None, "routing_guards": []})
        title = payload.get("context_title") or fields["title"]
        for field, text in fields.items():
            for window in sentences(text):
                if len(window.group()) > 1600:
                    continue
                applicability = assess_applicability(binding.market_scope, title, window.group()) if binding.market_scope else None
                guard_trace = assess_guards(binding.routing_guards, title, window.group())
                if (applicability and not applicability["allowed"]) or not guard_trace["allowed"]:
                    continue
                hits = matches(rule, {field: window.group(), "context_title": title},
                               issuer_cik=issuer_cik, profile_cik=profile_cik, legal_name=legal_name, bundle=bundle, at=at)
                if hits:
                    return [{**h, "start": h["start"] + window.start(),
                             "end": h["end"] + window.start(),
                             **({"routing_guard_trace": guard_trace} if binding.routing_guards else {}),
                             **({"applicability": {**applicability, "window_text": window.group(),
                                               "offset_basis": "RELATIVE_TO_WINDOW_TEXT_OR_CONTEXT_TITLE"}} if applicability else {})} for h in hits]
        return []
    scope = binding.relevance_scope
    if scope and any(pattern(t).search(value) for t in scope.excluded_subject_terms
                     for value in [*fields.values(), payload.get("context_title", "")]):
        return []
    if binding.kind == "STRUCTURED_ACTIVITY":
        return activity_matches(binding, fields, bundle=bundle, at=at, context_title=payload.get("context_title", ""))
    groups = ("topic_terms", "context_terms", "change_terms")
    if binding.kind == "SCOPED_ACTIVITY":
        # Three literal groups must co-occur in one sentence/heading. Do not join
        # an issuer's share-price headline with an unrelated customer's project.
        rule = binding.model_copy(update={"kind": "ECONOMIC_CHANGE", "relevance_scope": None})
        for field, text in fields.items():
            for window in sentences(text):
                if len(window.group()) > 1200:
                    continue
                hits = matches(rule, {field: window.group()})
                if hits:
                    return [{**h, "start": h["start"] + window.start(),
                             "end": h["end"] + window.start(),
                             "scope_basis": "SAME_SENTENCE_TOPIC_ACTIVITY_NOT_VERIFIED_PARTY",
                             **({"relevance_role": scope.role,
                                 "context_only": scope.role != "OWN_PRODUCT",
                                 "news_party_verified": False} if scope else {})}
                            for h in hits]
        return []

    if binding.kind == "ISSUER_PRODUCT_SHIPMENTS":
        return shipment_matches(binding, fields["summary"], issuer_cik, profile_cik)
    if binding.kind == "ISSUER_OPERATING_CONTEXT":
        return operating_matches(binding, fields["summary"], issuer_cik, profile_cik)
    if binding.kind == "SUPPLIER_ROLE_DISCLOSURE":
        if (not valid_cik(issuer_cik) or not valid_cik(profile_cik)
                or int(issuer_cik) == int(profile_cik)):
            return []
        for fact in extract_supply_roles(fields["summary"], issuer_cik)["facts"]:
            name = supplier_span(fact, legal_name)
            if not name or not any(pattern(t).search(fact["text"]) for t in binding.disclosure_terms):
                continue
            if any(pattern(t).search(fact["text"]) for t in binding.exclude_terms):
                continue
            spans = []
            for group in ("topic_terms", "context_terms"):
                hit = next((m for t in getattr(binding, group)
                            if (m := pattern(t).search(fact["product"]))), None)
                if hit is None:
                    break
                spans.append({"group": group, "field": "summary",
                    "start": fact["product_start"] + hit.start(),
                    "end": fact["product_start"] + hit.end(), "text": hit.group()})
            if len(spans) == 2:
                return spans + [{"group": "supplier_name", "field": "summary", **name},
                                {"group": "source_role", "field": "summary", **fact}]
        return []
    if binding.kind == "ISSUER_RELATIONSHIP_DISCLOSURE":
        # Trusted caller metadata only: never read an issuer identifier from RSS payload.
        if (not issuer_cik or not profile_cik or not str(issuer_cik).isdigit()
                or not str(profile_cik).isdigit() or int(issuer_cik) <= 0
                or int(issuer_cik) != int(profile_cik)):
            return []
        text = fields["summary"]
        if (not text or len(text) > 1600 or re.search(
                r'["“”]|\b(according to|said|says|competitors?|no longer|not|never|ceased)\b',
                text, re.I)):
            return []
        fields = {"summary": text}
        groups = ("topic_terms", "context_terms", "disclosure_terms")
    def variants(term):
        return [term, *binding.term_aliases.get(term, [])]

    if any(pattern(v).search(s) for t in binding.exclude_terms for v in variants(t)
           for s in fields.values()):
        return []
    spans = []
    for group in groups:
        found = None
        for term in getattr(binding, group):
            for variant in variants(term):
                for field, text in fields.items():
                    match = pattern(variant).search(text)
                    if match:
                        found = {"group": group, "field": field, "start": match.start(),
                                 "end": match.end(), "text": match.group(), "term": term,
                                 "matched_term": variant, "alias_used": variant != term}
                        break
                if found:
                    break
            if found:
                break
        if found is None:
            return []
        spans.append(found)
    return spans


def entity_context(bundle, reference_id, payload, at):
    """Profile-local reference only. Ambiguous overlapping names fail closed."""
    active = [r for r in bundle.entity_references if r.status == "SOURCE_BACKED"
              and r.reviewed_at <= at < r.review_until]
    ref = next((r for r in active if r.id == reference_id), None)
    if ref is None or not ref.names:
        return None
    edges = {r.id: r for r in bundle.relationships}
    for rid in ref.relationship_ids:
        r = edges[rid]
        if (r.status != "SOURCE_BACKED" or r.known_at > at or r.valid_from > at
                or (r.valid_until is not None and at >= r.valid_until)):
            return None
    fields = {k: payload.get(k, "") for k in ("title", "summary")}
    hits = []
    for name in ref.names:
        for field, text in fields.items():
            match = pattern(name).search(text)
            if match:
                for other in active:
                    if other.id == ref.id:
                        continue
                    for other_name in other.names:
                        if any(m.start() < match.end() and match.start() < m.end()
                               for m in pattern(other_name).finditer(text)):
                            return None
                hits.append({"field": field, "start": match.start(), "end": match.end(),
                             "text": match.group(), "name": name})
    if not hits:
        return None
    return {"reference_id": ref.id, "label": ref.label, "node_id": ref.node_id,
            "identity_level": ref.identity_level, "resolution": ref.resolution,
            "identity_merged": False, "news_party_verified": False,
            "scope": ref.scope, "unknowns": ref.unknowns, "matches": hits,
            "relationship_ids": ref.relationship_ids,
            "review_until": ref.review_until.isoformat(),
            "evidence": [e.model_dump() for e in ref.evidence]}


def verified_row(row, at, capture_cache):
    p, config = row["payload"], row["source_config"]
    if config.get("kind") != "rss" or not config.get("enabled") or p.get("kind") != "rss":
        raise ValueError("RSS source disabled or unsupported")
    if p.get("withdrawn") or p.get("status") in {"WITHDRAWN", "RETRACTED"}:
        raise ValueError("Source marked withdrawn")
    text = p.get("title", "") + " " + p.get("summary", "")
    if re.search(r"\bthis (?:story|article|report) (?:has been|was|is) (?:retracted|withdrawn)\b",
                 text, re.I):
        raise ValueError("Explicit publisher withdrawal notice")
    if (digest(p) != row["content_sha256"] or p != row["revision_payload"]
            or digest(canonical_url(p["url"])) != row["article_key"]):
        raise ValueError("Current RSS revision integrity mismatch")
    pub = datetime.fromisoformat(p["published_at"])
    received, first = utc(row["received_at"]), utc(row["first_seen_at"])
    if pub.tzinfo is None or pub > at or received > at or first > received:
        raise ValueError("Unknown/future RSS time")
    if not p.get("title") or len(p["title"]) > 1000 or len(p.get("summary", "")) > 6000:
        raise ValueError("Invalid bounded RSS excerpt")
    sha = row["capture_sha256"]
    if sha not in capture_cache:
        try:
            body = read_capture(os.getenv("NEWS_CAPTURE_DIR", "source-cache/rss-captures"), sha)
            capture_cache[sha] = body
        except FileNotFoundError:
            capture_cache[sha] = None
        except (OSError, ValueError):
            capture_cache[sha] = False
    body = capture_cache[sha]
    proof = "NOT_ARCHIVED"
    if body is False:
        raise ValueError("Corrupt archived RSS")
    if body is not None:
        key = (sha, received.isoformat())
        if key not in capture_cache:
            capture_cache[key] = parse_feed(body, received)[0]
        rows = capture_cache[key]
        exact = [v for v in rows if all(v.get(k) == p.get(k) for k in
                 ("external_id", "url", "title", "summary", "published_at"))]
        if not exact:
            raise ValueError("RSS revision does not match archived response")
        proof = "RAW_RSS_MATCH_NOT_FACT_VERIFICATION"
    return pub, received, proof


def candidate_feed(conn, as_of=None, limit=500, *, profile_root=None, card_limit=100, include_company=False, include_narratives=True):
    at = as_of or datetime.now(UTC)
    if at.tzinfo is None or not 1 <= limit <= 5000 or not 1 <= card_limit <= 1000:
        raise ValueError("Aware cutoff and bounded limit required")
    at = min(at, datetime.now(UTC))
    profiles = available_bundles(at, root=profile_root)
    result = {"items": [], "enabled": profiles["enabled"], "as_of": at.isoformat(),
              "delivery": "disabled", "graph_modified": False, "examined": 0,
              "withheld": 0, "profiles_withheld": profiles.get("withheld", 0),
              "truncated": profiles.get("truncated", False),
              "mode": "RSS_FACTOR_TOPIC_CANDIDATES_NOT_VERIFIED_IMPACT"}
    if not profiles["enabled"]:
        return result
    query = select(news_items, news_revisions.c.id.label("revision_id"),
                   news_revisions.c.payload.label("revision_payload"),
                   news_revisions.c.received_at, news_revisions.c.capture_sha256,
                   news_sources.c.config.label("source_config")).join(
        news_revisions, and_(news_revisions.c.item_id == news_items.c.id,
                             news_revisions.c.version == news_items.c.version)).join(
        news_sources, news_sources.c.id == news_items.c.source_id).order_by(
        news_revisions.c.received_at.desc(), news_items.c.id).limit(limit + 1)
    rows = conn.execute(query).mappings().all()
    result["truncated"] |= len(rows) > limit
    groups: dict = defaultdict(list)
    blocked = set()
    cache: dict = {}
    for row in rows[:limit]:
        result["examined"] += 1
        try:
            pub, received, proof = verified_row(row, at, cache)
            groups[row["article_key"]].append((row, pub, received, proof))
        except (ValueError, TypeError, KeyError, OSError):
            # An inactive duplicate source is not a publisher retraction. Other
            # integrity/withdrawal conflicts conservatively block the same URL.
            if row["source_config"].get("enabled"):
                blocked.add(row["article_key"])
            result["withheld"] += 1
    cards: dict = {}
    company_cards = []
    for article_key, variants in groups.items():
        if article_key in blocked or len({digest([v[0]["payload"]["title"],
            v[0]["payload"].get("summary", "")]) for v in variants}) > 1:
            result["withheld"] += len(variants)
            continue
        row, pub, received, _ = variants[0]
        payload = row["payload"]
        for bundle in profiles["items"]:
            nodes = {n.id: n.label for n in bundle.nodes}
            source_map = {s.id: s for s in bundle.sources}
            if include_company:
                from engine.company_discovery import decisions as company_decisions

                discovery = [d for d in company_decisions(bundle, payload, at)
                             if all(v[1] >= at - timedelta(days=d["max_news_age_days"]) for v in variants)]
                if discovery:
                    revisions = [{"item_id": v[0]["id"], "version": v[0]["version"],
                                  "revision_id": v[0]["revision_id"], "source_id": v[0]["source_id"],
                                  "payload_sha256": v[0]["content_sha256"], "capture_proof": v[3]}
                                 for v in variants]
                    company_cards.append({"id": digest([payload["url"], bundle.id]),
                        "ticker": bundle.ticker, "profile_id": bundle.id, "profile_version": bundle.version,
                        "headline": payload["title"], "excerpt": payload.get("summary", ""),
                        "url": payload["url"], "published_at": pub.isoformat(),
                        "news_revisions": revisions, "company_discovery": discovery,
                        "narratives": [], "links": [], "mechanisms": {},
                        "revision_sha256": digest([revisions, discovery, bundle.version]),
                        "verification": "SOURCED_COMPANY_SCOPE_UNVERIFIED_NEWS",
                        "priority": "COMPANY_CONTEXT_UNASSIGNED", "direction": "UNKNOWN",
                        "financial_magnitude": "UNKNOWN", "horizon": "UNKNOWN", "delivery": "disabled",
                        "graph_eligible": False,
                        "decision_trace": ["Current source revision and captured RSS checked",
                            "Reviewed company scope is independent of watched narratives",
                            "No canonical event, narrative assignment or financial effect inferred"]})
            if not include_narratives:
                continue
            for binding in bundle.factor_bindings:
                if binding.company_only:
                    continue
                if not binding.enabled or not binding.reviewed_at <= at < binding.review_until:
                    continue
                if any(v[1] < at - timedelta(days=binding.max_news_age_days) for v in variants):
                    continue
                entity = None
                if binding.entity_reference_id is not None:
                    entity = entity_context(bundle, binding.entity_reference_id, payload, at)
                    if entity is None:
                        continue
                spans = matches(binding, payload, bundle=bundle, at=at)
                if not spans:
                    continue
                for narrative in bundle.narratives:
                    if binding.narrative_ids and narrative.id not in binding.narrative_ids:
                        continue
                    entity_routes = []
                    if entity is not None:
                        entity_routes, _ = paths(bundle, SimpleNamespace(anchors=[entity["node_id"]]),
                                                 narrative, effective_at=at)
                        if not entity_routes:
                            continue
                    routes, truncated = paths(bundle, SimpleNamespace(anchors=[binding.factor_id]),
                                              narrative, effective_at=at)
                    if binding.relevance_scope and binding.relevance_scope.relationship_id:
                        routes = [route for route in routes if any(
                            r.id == binding.relevance_scope.relationship_id for r in route)]
                    if not routes:
                        continue
                    routes.sort(key=lambda path: (
                        not any(RELATIONS[r.type][0] == "MECHANISM" for r in path), len(path)))
                    qualified_route = eligible_route(bundle, narrative, routes, spans)
                    if qualified_route is None:
                        continue
                    route, contract = qualified_route
                    qualified_spans = [{**s, "routing_contract": contract} for s in spans] if contract else spans
                    key = (article_key, bundle.id, narrative.id)
                    citations = {e.source_id for e in binding.evidence}
                    citations.update(e.source_id for r in route for e in r.evidence)
                    entity_route = min(entity_routes, key=len) if entity_routes else []
                    if entity is not None:
                        citations.update(e["source_id"] for e in entity["evidence"])
                        citations.update(e.source_id for r in entity_route for e in r.evidence)
                    if key not in cards:
                        cards[key] = {"id": digest(key), "ticker": bundle.ticker,
                            "profile_id": bundle.id, "profile_version": bundle.version,
                            "profile_snapshot_at": bundle.snapshot_at.isoformat(),
                            "narrative_id": narrative.id, "narrative_version": narrative.version,
                            "narrative_title": narrative.title, "headline": payload["title"],
                            "excerpt": payload.get("summary", ""), "url": payload["url"],
                            "published_at": pub.isoformat(),
                            "available_at": max(bundle.available_at, binding.reviewed_at,
                                                *(v[2] for v in variants)).isoformat(),
                            "source_timestamp_basis": "SOURCE_REPORTED_NOT_VERIFIED_ORIGINAL_PUBLICATION",
                            "news_revisions": [{"item_id": v[0]["id"], "version": v[0]["version"],
                                "revision_id": v[0]["revision_id"],
                                "payload_sha256": v[0]["content_sha256"],
                                "source_id": v[0]["source_id"], "source_name": v[0]["payload"]["source_name"],
                                "capture_proof": v[3]} for v in variants],
                            "links": [], "unknowns": list(narrative.unknowns),
                            "stance": "RELATED_INFORMATION", "impact": "UNKNOWN",
                            "verification": "RSS_UNVERIFIED_TOPIC_MATCH_PROFILE_SOURCE_BACKED",
                            "delivery": "disabled", "graph_eligible": False,
                            "decision_trace": ["Current RSS revision and source status rechecked",
                                "All curated literal term groups matched with exact spans",
                                "Binding evidence and review expiry rechecked",
                                "Bounded sourced route at read-time, not old snapshot time",
                                "No polarity, magnitude, company-specific event or push inferred"]}
                    cards[key]["links"].append({"binding_id": binding.id,
                        "factor_id": binding.factor_id, "factor": nodes[binding.factor_id],
                        "scope": binding.scope, "matches": qualified_spans,
                        **({"routing_contract": contract} if contract else {}),
                        **({"relevance_role": binding.relevance_scope.role}
                           if binding.relevance_scope else {}),
                        "entity_context": entity,
                        "entity_context_path": [{"id": r.id, "from": nodes[r.from_id],
                            "to": nodes[r.to_id], "type": r.type, "scope": r.scope,
                            "evidence": [e.model_dump() for e in r.evidence]} for r in entity_route],
                        "profile_evidence": [e.model_dump() for e in binding.evidence],
                        "review_until": binding.review_until.isoformat(),
                        "path": [{"id": r.id, "from": nodes[r.from_id], "to": nodes[r.to_id],
                            "family": RELATIONS[r.type][0], "type": r.type, "basis": r.basis,
                            "scope": r.scope, "conditions": r.conditions,
                            "unknowns": r.unknowns, "evidence": [e.model_dump() for e in r.evidence]}
                            for r in route], "paths_truncated": truncated,
                        "sources": [{"id": sid, "url": str(source_map[sid].url),
                            "sha256": source_map[sid].sha256,
                            "published_at": source_map[sid].published_at.isoformat()}
                            for sid in sorted(citations)]})
    result["truncated"] |= len(cards) > card_limit
    result["items"] = list(cards.values())[:card_limit]
    if include_company:
        result["company_items"] = company_cards[:card_limit]
        result["truncated"] |= len(company_cards) > card_limit
    return result
