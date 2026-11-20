from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from engine.graph.matcher import Edge, PathResult, match_paths
from engine.ingestion.contracts import digest


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Observation(Contract):
    metric_id: str
    direction: Literal[-1, 0, 1] | None
    evidence_url: str
    available_at: AwareDatetime


class Materiality(Contract):
    value: float = Field(ge=0, le=1)
    metric_id: str
    rubric_version: str = Field(min_length=1)
    scale: str = Field(min_length=1)
    horizon: str = Field(min_length=1)
    evidence_url: str = Field(min_length=1)


class EventInput(Contract):
    event_id: str
    event_version_id: str | None
    canonical_key: str
    issuer: str
    event_type: str
    headline: str
    published_at: AwareDatetime
    first_seen_at: AwareDatetime
    available_at: AwareDatetime
    is_synthetic: bool
    rights: Literal["approved", "approved_fixture_only", "pending", "blocked"]
    evidence_urls: tuple[str, ...]
    source_span_valid: bool
    identity_valid: bool
    observations: tuple[Observation, ...]
    evidence_quality: float | None = Field(default=None, ge=0, le=1)
    materiality: Materiality | None = None
    is_correction: bool = False
    duplicate: bool = False
    delivered: bool = False
    period_valid: bool = True
    core_numbers_conflict: bool = False
    unverified_contract_claim: bool = False
    confirmed_conditions: tuple[str, ...] = ()


class NarrativeInput(Contract):
    id: str
    version_id: str
    ticker: str
    available_at: AwareDatetime
    # Expected metric direction if the thesis holds, distinct from stock direction.
    outcomes: dict[str, Literal[-1, 1]]
    hypothesis_polarity: Literal["favorable", "adverse"]
    watch_next: str
    is_synthetic: bool


WEIGHTS = {"R": 0.25, "M": 0.20, "N": 0.20, "Q": 0.15, "T": 0.10, "U": 0.10}
HALF_LIVES_DAYS = {
    "FILING": 90,
    "CAPEX": 45,
    "COMPONENT_COST": 14,
    "MEMORY_PRICING": 14,
    "NAND_PRICE": 14,
    "PRICE_ONLY": 1,
    "default": 30,
}
POLICY: dict = {
    "name": "rie-v0.3",
    "algorithm_revision": "gates-and-stance-v3",
    "weights": WEIGHTS,
    "half_lives_days": HALF_LIVES_DAYS,
    "push": 80,
    "digest": 60,
    "quality_digest": 0.70,
    "quality_push": 0.80,
    "max_hops": 2,
    "correction_novelty": 0.7,
    "unknown_materiality": "review_required",
    "path_decay": 0.85,
}
POLICY_VERSION = POLICY["name"] + "-" + digest(POLICY)[:12]


def evaluate(
    event: EventInput,
    narrative: NarrativeInput,
    edges: list[Edge],
    nodes: set[str],
    as_of: datetime,
    *,
    demo: bool = False,
    user_fit: float = 1.0,
    max_hops: int = 2,
) -> dict:
    if as_of.tzinfo is None or not 0 <= user_fit <= 1 or not 0 <= max_hops <= 2:
        raise ValueError("Aware as_of and bounded user fit required")
    quality = event.evidence_quality
    provenance = (
        bool(event.evidence_urls)
        and event.source_span_valid
        and all(o.evidence_url in event.evidence_urls for o in event.observations)
    )
    dates = [
        event.published_at,
        event.first_seen_at,
        event.available_at,
        narrative.available_at,
    ] + [o.available_at for o in event.observations]
    gates = {
        "source_rights": event.rights
        == ("approved_fixture_only" if demo and event.is_synthetic else "approved"),
        "synthetic_isolation": not event.is_synthetic or (demo and narrative.is_synthetic),
        "narrative_mode": narrative.is_synthetic == event.is_synthetic,
        "provenance": provenance,
        "available_as_of": all(t <= as_of for t in dates)
        and event.available_at >= max(event.published_at, event.first_seen_at),
        "identity": event.identity_valid and event.issuer in nodes,
        "novelty": not event.duplicate and not event.delivered,
        "comparison_basis": event.period_valid,
        "core_numbers_consistent": not event.core_numbers_conflict,
        "contract_claim_evidenced": not event.unverified_contract_claim,
        "quality_digest": quality is not None and quality >= 0.70,
        "quality_push": quality is not None and quality >= 0.80,
        "materiality_known": event.materiality is not None,
    }
    if event.materiality is not None:
        gates["materiality_known"] = (
            event.materiality.metric_id in {o.metric_id for o in event.observations}
            and event.materiality.evidence_url in event.evidence_urls
        )
    trace: dict = {
        "event_id": event.event_id,
        "event_version_id": event.event_version_id,
        "canonical_event_key": event.canonical_key,
        "narrative_id": narrative.id,
        "narrative_version_id": narrative.version_id,
        "as_of": as_of.isoformat(),
        "is_synthetic": event.is_synthetic,
        "policy_version": POLICY_VERSION,
        "policy_snapshot": POLICY,
        "extraction_version": "validated-observations-v1",
        "input_sha256": digest(
            {
                "event": event.model_dump(mode="json"),
                "narrative": narrative.model_dump(mode="json"),
                "edges": [e.model_dump(mode="json") for e in sorted(edges, key=lambda e: e.id)],
                "user_fit": user_fit,
            }
        ),
        "gate_results": gates,
        "reasons": [],
        "selected_path": None,
        "alternates": [],
        "score_components": {
            "R": None,
            "M": None,
            "N": None,
            "Q": quality,
            "T": None,
            "U": user_fit,
        },
        "score": None,
        "score_bounds": None,
        "materiality": event.materiality.model_dump(mode="json") if event.materiality else None,
        "stance": "INSUFFICIENT_EVIDENCE",
        "conditional_stance": None,
        "economic_effect": "UNCERTAIN",
        "realized_outcome": "NOT_ESTABLISHED",
        "observations": [o.model_dump(mode="json") for o in event.observations],
        "conditional_reasons": [],
        "evidence_urls": list(event.evidence_urls),
        "decision": "review_required",
        "send_recommendation": False,
        "delivery_status": "disabled",
        "sent_at": None,
    }

    def finish(decision: str, reason: str) -> dict:
        trace["decision"] = decision
        trace["reasons"].append(reason)
        trace["send_recommendation"] = decision == "push" and not event.is_synthetic
        return trace

    for key, reason in (
        ("synthetic_isolation", "synthetic_live_forbidden"),
        ("narrative_mode", "mode_mismatch"),
        ("source_rights", "source_rights_not_approved"),
        ("available_as_of", "future_available_at"),
        ("identity", "invalid_identity"),
        ("novelty", "duplicate_or_delivered"),
        ("contract_claim_evidenced", "unsupported_contract_claim"),
    ):
        if not gates[key]:
            return finish("suppressed", reason)
    for key, reason in (
        ("provenance", "missing_provenance"),
        ("comparison_basis", "incompatible_period"),
        ("core_numbers_consistent", "contradictory_core_numbers"),
    ):
        if not gates[key]:
            return finish("review_required", reason)
    if not gates["quality_digest"]:
        return finish(
            "review_required" if quality is None else "suppressed",
            "unknown_evidence_quality" if quality is None else "low_evidence_quality",
        )
    if event.event_type == "PRICE_ONLY":
        if event.issuer != "CO_" + narrative.ticker:
            return finish("suppressed", "no_relevant_path")
        trace.update(stance="NO_CHANGE", economic_effect="NONE")
        return finish("storybook", "price_does_not_establish_fundamentals")

    candidates: list[tuple[Observation, PathResult]] = []
    for obs in event.observations:
        if obs.metric_id not in nodes:
            return finish("review_required", "unknown_observation_entity")
        paths = match_paths(
            edges,
            nodes=nodes,
            start=obs.metric_id,
            targets=set(narrative.outcomes),
            as_of=as_of,
            source_confidence=quality or 0,
            synthetic=event.is_synthetic,
            max_hops=max_hops,
        )
        # Zero-hop requires issuer-owned metric, not a fixture's ticker label on a sector event.
        paths = [
            p
            for p in paths
            if p.edges
            or (
                event.issuer == "CO_" + narrative.ticker
                and obs.metric_id.startswith(narrative.ticker + "_")
            )
        ]
        candidates.extend((obs, path) for path in paths)
    gates["verified_path"] = bool(candidates)
    if not candidates:
        reachable = {o.metric_id for o in event.observations}
        for _ in range(2):
            reachable |= {e.to_entity for e in edges if e.from_entity in reachable}
        if not reachable.intersection(narrative.outcomes):
            return finish("suppressed", "no_relevant_path")
        future_graph = any(
            e.from_entity in {o.metric_id for o in event.observations} and e.recorded_at > as_of
            for e in edges
        )
        return finish(
            "suppressed" if future_graph else "review_required",
            "graph_lookahead" if future_graph else "no_verified_path",
        )
    candidates.sort(
        key=lambda pair: (
            -pair[1].relevance,
            -pair[1].confidence,
            len(pair[1].edges),
            tuple(e.id for e in pair[1].edges),
            pair[0].metric_id,
        )
    )
    selected = candidates[0][1]
    trace["selected_path"] = selected.model_dump(mode="json")
    trace["alternates"] = [p.model_dump(mode="json") for _, p in candidates[1:]]
    # One best path per observation prevents correlated alternatives adding support.
    outcomes, hypothetical, unresolved = set(), set(), set()
    seen = set()
    for obs, path in candidates:
        observation_key = (obs.metric_id, obs.direction, obs.evidence_url)
        if observation_key in seen:
            continue
        seen.add(observation_key)
        pending = set(path.conditional_reasons) - set(event.confirmed_conditions)
        # Unknown/conditional direction cannot be resolved by a boolean alone.
        pending |= {c for c in path.conditional_reasons if c.startswith("direction_unresolved:")}
        if obs.direction is None or path.sign not in ("positive", "negative"):
            pending.add("direction_not_established")
        elif obs.direction == 0:
            outcomes.add("NO_CHANGE")
        else:
            transmitted = obs.direction * (-1 if path.sign == "negative" else 1)
            stance = "SUPPORTS" if transmitted == narrative.outcomes[path.target] else "CHALLENGES"
            hypothetical.add(stance)
            if not pending:
                outcomes.add(stance)
        unresolved |= pending
    sides = outcomes & {"SUPPORTS", "CHALLENGES"}
    stance = (
        "MIXED"
        if len(sides) == 2
        else next(iter(sides))
        if sides and not unresolved
        else "NO_CHANGE"
        if outcomes == {"NO_CHANGE"} and not unresolved
        else "INSUFFICIENT_EVIDENCE"
    )
    trace["stance"] = stance
    trace["conditional_stance"] = (
        next(iter(hypothetical)) if len(hypothetical) == 1 and unresolved else None
    )
    trace["conditional_reasons"] = sorted(unresolved)
    gates["direction_and_conditions"] = not unresolved and stance != "INSUFFICIENT_EVIDENCE"
    if stance in ("SUPPORTS", "CHALLENGES"):
        favorable = (stance == "SUPPORTS") == (narrative.hypothesis_polarity == "favorable")
        trace["economic_effect"] = "FAVORABLE" if favorable else "ADVERSE"
    elif stance == "NO_CHANGE":
        trace["economic_effect"] = "NONE"
    trace["evidence_urls"] = sorted(
        set(trace["evidence_urls"])
        | {url for _, p in candidates for edge in p.edges for url in edge.evidence_urls}
    )
    half_life = HALF_LIVES_DAYS.get(event.event_type, HALF_LIVES_DAYS["default"])
    timeliness = 2 ** (-max(0, (as_of - event.available_at).total_seconds()) / (half_life * 86400))
    components = {
        "R": selected.relevance,
        "M": event.materiality.value if gates["materiality_known"] and event.materiality else None,
        "N": 0.7 if event.is_correction else 1.0,
        "Q": quality,
        "T": timeliness,
        "U": user_fit,
    }
    trace["score_components"] = components
    subtotal = 100 * sum(
        WEIGHTS[key] * value for key, value in components.items() if value is not None
    )
    trace["timeliness_basis"] = {"half_life_days": half_life, "clock": "available_at"}
    if not gates["materiality_known"]:
        trace["score_bounds"] = [round(subtotal, 3), round(subtotal + 20, 3)]
        return finish("review_required", "unknown_materiality")
    trace["score"] = round(subtotal, 3)
    if unresolved or stance == "INSUFFICIENT_EVIDENCE":
        return finish("review_required", "unverified_direction_or_conditions")
    if subtotal >= 80 and gates["quality_push"] and stance in ("SUPPORTS", "CHALLENGES", "MIXED"):
        return finish("push", "push_candidate_all_gates_passed")
    return finish("digest" if subtotal >= 60 else "storybook", "score_threshold")


def render_card(event: EventInput, narrative: NarrativeInput, trace: dict) -> dict:
    path = trace["selected_path"]
    nodes = (
        [path["edges"][0]["from_entity"]] + [e["to_entity"] for e in path["edges"]]
        if path and path["edges"]
        else [path["target"]]
        if path
        else []
    )
    condition_text = {
        "contracted_cost_rises": "Contracted component costs actually rise with market input prices.",
        "cost_not_offset": "Realized pricing, vendor rebates and product mix do not offset the higher costs.",
        "direction_not_established": "The evidence does not establish the direction of the economic effect.",
    }
    uncertainties = [
        condition_text.get(
            reason, "The direction of an intermediate relationship remains unverified."
        )
        for reason in trace["conditional_reasons"]
    ]
    conditional_effect = None
    if trace["conditional_stance"] in ("SUPPORTS", "CHALLENGES"):
        favorable = (trace["conditional_stance"] == "SUPPORTS") == (
            narrative.hypothesis_polarity == "favorable"
        )
        conditional_effect = (
            "FAVORABLE_IF_CONDITIONS_HOLD" if favorable else "ADVERSE_IF_CONDITIONS_HOLD"
        )
    return {
        "is_synthetic": event.is_synthetic,
        "event_id": event.event_id,
        "narrative_id": narrative.id,
        "primary_ticker": narrative.ticker,
        "headline": ("SYNTHETIC: " if event.is_synthetic else "") + event.headline,
        "what_changed": event.headline,
        "why_connected": " -> ".join(nodes) or "No verified path available",
        "graph_path": [
            {
                "edge_id": e["id"],
                "from": e["from_entity"],
                "to": e["to_entity"],
                "family": e["family"],
                "status": "synthetic_verified_demo_only" if e["is_synthetic"] else e["status"],
                "evidence_urls": e["evidence_urls"],
            }
            for e in path["edges"]
        ]
        if path
        else [],
        "narrative_stance": trace["stance"],
        "conditional_stance": trace["conditional_stance"],
        "economic_effect": trace["economic_effect"],
        "conditional_economic_effect": conditional_effect,
        "status": trace["decision"],
        "what_is_uncertain": uncertainties
        + (
            ["Materiality is unknown; no numerical impact is inferred."]
            if trace["materiality"] is None
            else []
        )
        + (
            ["Synthetic evidence does not establish a real company outcome."]
            if event.is_synthetic
            else []
        ),
        "what_to_watch": "Check the next disclosure for: " + narrative.watch_next,
        "evidence_urls": trace["evidence_urls"],
        "source_published_at": event.published_at.isoformat(),
        "source_available_at": event.available_at.isoformat(),
        "delivery_status": "disabled",
        "reason_for_not_sending": "Live notification delivery is disabled."
        + (" This event and its evidence are synthetic." if event.is_synthetic else "")
        + (
            " Required economic conditions remain unverified."
            if trace["conditional_reasons"]
            else ""
        ),
        "sent_at": None,
    }
