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

from engine.adapters.news import canonical_url, parse_feed
from engine.company_profiles import RELATIONS, available_bundles, paths
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_items, news_revisions, news_sources
from engine.news_capture import read_capture


@lru_cache(maxsize=4096)
def pattern(term):
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)


def matches(binding, payload):
    """Exact original-field spans; context groups must all match, no ticker shortcut."""
    fields = {k: payload.get(k, "") for k in ("title", "summary")}
    def variants(term):
        return [term, *binding.term_aliases.get(term, [])]

    if any(pattern(v).search(s) for t in binding.exclude_terms for v in variants(t)
           for s in fields.values()):
        return []
    spans = []
    for group in ("topic_terms", "context_terms", "change_terms"):
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


def candidate_feed(conn, as_of=None, limit=500):
    at = as_of or datetime.now(UTC)
    if at.tzinfo is None or not 1 <= limit <= 500:
        raise ValueError("Aware cutoff and bounded limit required")
    at = min(at, datetime.now(UTC))
    profiles = available_bundles(at)
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
            for binding in bundle.factor_bindings:
                if not binding.enabled or not binding.reviewed_at <= at < binding.review_until:
                    continue
                if any(v[1] < at - timedelta(days=binding.max_news_age_days) for v in variants):
                    continue
                entity = None
                if binding.entity_reference_id is not None:
                    entity = entity_context(bundle, binding.entity_reference_id, payload, at)
                    if entity is None:
                        continue
                spans = matches(binding, payload)
                if not spans:
                    continue
                for narrative in bundle.narratives:
                    entity_routes = []
                    if entity is not None:
                        entity_routes, _ = paths(bundle, SimpleNamespace(anchors=[entity["node_id"]]),
                                                 narrative, effective_at=at)
                        if not entity_routes:
                            continue
                    routes, truncated = paths(bundle, SimpleNamespace(anchors=[binding.factor_id]),
                                              narrative, effective_at=at)
                    if not routes:
                        continue
                    routes.sort(key=lambda path: (
                        not any(RELATIONS[r.type][0] == "MECHANISM" for r in path), len(path)))
                    route = routes[0]
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
                        "scope": binding.scope, "matches": spans,
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
    result["truncated"] |= len(cards) > 100
    result["items"] = list(cards.values())[:100]
    return result
