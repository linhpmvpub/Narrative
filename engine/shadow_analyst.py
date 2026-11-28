"""Read-only company analyst contracts. Structural validity is not semantic truth.

Experimental output never enters canonical events, profiles, feed or delivery.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.company_discovery import validate_exposure
from engine.ingestion.contracts import digest

VERSION = "COMPANY_SHADOW_V1"
POLICY = {"version": VERSION, "issuer_attention": 3, "exposure_attention": 2,
          "context": 1, "financial_magnitude": "UNKNOWN", "horizon": "UNKNOWN"}


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    company_id: str = Field(min_length=1, max_length=100)
    relevance: Literal["RELEVANT", "NOT_RELEVANT", "INSUFFICIENT_CONTEXT"]
    attention: Literal["PRIORITY", "CONTEXT", "NONE", "INSUFFICIENT_CONTEXT"]
    group: Literal["results", "supply", "input_price", "capacity", "demand", "financing",
                   "policy", "competition", "technology", "governance", "other", "UNKNOWN"]
    phase: Literal["REPORTED", "PLAN", "SPECULATION", "BACKGROUND", "UNKNOWN"]
    negated: bool
    quote: str = Field(max_length=2500)
    actor: str = Field(max_length=240)
    route_id: str = Field(max_length=220)
    rationale: str = Field(min_length=1, max_length=1200)


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decisions: list[Decision] = Field(min_length=1, max_length=20)


def catalog(bundles, at):
    """All reviewed company routes, independent of today's news pattern acceptance."""
    result = []
    for bundle in sorted(bundles.values(), key=lambda b: b.id):
        if at < bundle.available_at:
            continue
        nodes = {n.id: n.model_dump(mode="json") for n in bundle.nodes}
        sources = {s.id: s for s in bundle.sources}
        for rule in bundle.company_discovery:
            if not rule.enabled or not rule.reviewed_at <= at < rule.review_until:
                continue
            edges, binding, entity = [], None, None
            evidence = list(rule.evidence)
            if rule.kind == "FACTOR_EXPOSURE":
                binding, path, membership = validate_exposure(bundle, rule)
                edges = [*path, *membership]
                if (not binding.enabled or not binding.reviewed_at <= at < binding.review_until
                        or any(e.status != "SOURCE_BACKED" or e.known_at > at or e.valid_from > at
                               or e.valid_until is not None and at >= e.valid_until for e in edges)):
                    continue
                evidence += [*binding.evidence, *(e for edge in edges for e in edge.evidence)]
                if binding.entity_reference_id:
                    entity = next(e for e in bundle.entity_references if e.id == binding.entity_reference_id)
                    if (entity.status != "SOURCE_BACKED" or not entity.reviewed_at <= at < entity.review_until):
                        continue
                    evidence += entity.evidence
            # Unknown publication remains explicitly unknown, not a fabricated date.
            if any(sources[e.source_id].retrieved_at > at or
                   sources[e.source_id].published_at is not None and sources[e.source_id].published_at > at
                   for e in evidence):
                continue
            ids = {e.source_id for e in evidence}
            item = {"id": bundle.id + ":" + rule.id, "company_id": bundle.company_id,
                    "profile_id": bundle.id, "kind": rule.kind, "scope": rule.scope,
                    "names": rule.names, "intents": rule.intents,
                    "relation_ids": rule.relation_ids, "membership_ids": rule.membership_ids,
                    "edges": [e.model_dump(mode="json") for e in edges],
                    "nodes": [nodes[k] for k in sorted({v for e in edges for v in (e.from_id, e.to_id)})],
                    "evidence": [e.model_dump(mode="json") for e in evidence],
                    "sources": [{"id": k, "url": str(sources[k].url), "sha256": sources[k].sha256,
                                 "published_at": sources[k].model_dump(mode="json")["published_at"]}
                                for k in sorted(ids)],
                    "entity_scope": entity.model_dump(mode="json") if entity else None,
                    "binding_scope": binding.scope if binding else None,
                    "market_scope": binding.market_scope if binding else None,
                    "terms": rule.names if not binding else
                             [*binding.topic_terms, *binding.context_terms, nodes[binding.factor_id]["label"]],
                    "reviewed_at": rule.reviewed_at.isoformat(), "review_until": rule.review_until.isoformat()}
            item["sha256"] = digest(item)
            result.append(item)
    return result


def words(text):
    return set(re.findall(r"[a-z0-9]{3,}", text.casefold())) - {
        "the", "and", "for", "with", "from", "that", "this", "company", "companies", "has", "are"}


def retrieve(source, routes, *, per_company=2, max_chars=16000):
    """Bounded lexical reverse-exposure retrieval; zero-hit routes stay absent/observable.

    No narrative, reference labels, deterministic selections or article-specific branches.
    """
    if not 1 <= per_company <= 5 or not 1000 <= max_chars <= 20000:
        raise ValueError("Bounded retrieval required")
    query = words(source)
    found = []
    counts: dict = {}
    for route in routes:
        overlap = sorted(query & words(" ".join(route["terms"])))
        if overlap:
            found.append((len(overlap), route["id"], route, overlap))
    selected: list = []
    for count, _, route, overlap in sorted(found, key=lambda row: (-row[0], row[1])):
        key = (route["company_id"], route["kind"])
        if counts.get(key, 0) >= (1 if route["kind"] == "ISSUER_EVENT" else per_company):
            continue
        item = {"route": route, "retrieval_overlap": overlap, "retrieval_score": count}
        # Keep complete routes/evidence; never cut a quote or silently truncate model context.
        if len(json.dumps(model_routes([*selected, item]), ensure_ascii=False).encode()) > max_chars:
            continue
        counts[key] = counts.get(key, 0) + 1
        selected.append(item)
    return selected


def model_routes(retrieved):
    """Compact, sourced model context; full graph/pins remain in local experiment files."""
    return [{"id": r["id"], "company_id": r["company_id"], "kind": r["kind"],
             "scope": r["scope"], "names": r["names"], "binding_scope": r["binding_scope"],
             "market_scope": r["market_scope"], "intents": r["intents"],
             "nodes": r["nodes"], "entity_scope": {k: v for k, v in r["entity_scope"].items()
                 if k in {"id", "label", "identity_level", "resolution", "node_id", "names", "scope", "unknowns"}}
                 if r["entity_scope"] else None,
             "edges": [{k: e[k] for k in ("id", "type", "from_id", "to_id", "scope", "conditions", "unknowns")}
                       for e in r["edges"]],
             "evidence": list({digest(e): e for e in r["evidence"]}.values())}
            for r in (item["route"] for item in retrieved)]


def validate(proposal, source, companies, retrieved, *, graph):
    expected = {c["company_id"] for c in companies}
    if len(proposal.decisions) != len(expected) or {d.company_id for d in proposal.decisions} != expected:
        raise ValueError("Complete unique target-company decisions required")
    routes = {i["route"]["id"]: i["route"] for i in retrieved}
    result = []
    for d in proposal.decisions:
        faults = []
        selected = d.relevance == "RELEVANT"
        if ((selected and d.attention == "NONE") or
                (d.relevance == "NOT_RELEVANT" and d.attention != "NONE") or
                (d.relevance == "INSUFFICIENT_CONTEXT" and d.attention != "INSUFFICIENT_CONTEXT")):
            faults.append("INCONSISTENT_ATTENTION")
        offset = source.find(d.quote) if d.quote else -1
        if selected and (not d.quote.strip() or offset < 0 or source.count(d.quote) != 1):
            faults.append("MISSING_OR_AMBIGUOUS_SOURCE_QUOTE")
        if selected and (not d.actor.strip() or d.actor not in d.quote):
            faults.append("UNSUPPORTED_ACTOR_SPAN")
        route = routes.get(d.route_id)
        if graph and selected:
            if route is None or route["company_id"] != d.company_id:
                faults.append("MISSING_OR_WRONG_COMPANY_ROUTE")
            elif route["kind"] == "ISSUER_EVENT" and not any(
                    re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", d.actor, re.I) for name in route["names"]):
                faults.append("ISSUER_NOT_IN_ACTOR")
        if not graph and d.route_id:
            faults.append("GENERIC_ARM_CANNOT_CITE_PRIVATE_GRAPH")
        accepted = selected and not faults
        # The model proposes event attributes; code owns policy, never a learned impact weight.
        priority = (accepted and d.attention == "PRIORITY" and d.phase in {"REPORTED", "PLAN"}
                    and d.group not in {"other", "UNKNOWN"} and not d.negated)
        tier = (POLICY["issuer_attention"] if route and route["kind"] == "ISSUER_EVENT"
                else POLICY["exposure_attention"]) if priority else POLICY["context"] if accepted else 0
        result.append({"company_id": d.company_id, "selected": bool(accepted), "priority": bool(priority),
            "raw_relevance": d.relevance, "raw_attention": d.attention, "validation_faults": faults,
            "status": "WITHHELD" if faults else "ABSTAINED" if d.relevance == "INSUFFICIENT_CONTEXT" else "VALIDATED_STRUCTURE_ONLY",
            "source_span": {"start": offset, "end": offset + len(d.quote), "text": d.quote} if accepted else None,
            "route_id": route["id"] if graph and accepted and route else None,
            "route_sha256": route["sha256"] if graph and accepted and route else None,
            "attention_tier": tier, "phase": d.phase, "group": d.group, "negated": d.negated,
            "explanation": {"source_statement": d.quote, "conditional_scope": route["scope"] if graph and route else None,
                            "status": "SOURCE_QUOTE_AND_DB_SCOPE_NOT_VERIFIED_IMPACT"} if accepted else None,
            "direction": "UNKNOWN", "financial_magnitude": "UNKNOWN", "horizon": "UNKNOWN",
            "semantic_correctness": "UNMEASURED", "delivery": "disabled"})
    return result
