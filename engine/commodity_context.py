"""Commodity -> sourced input usage -> company relevance, without a legal-entity anchor.

Source-span annotations remain reviewer declarations; no automatic semantic truth claim.
"""

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from engine.evaluation.article_relevance import reviewed_body
from engine.ingestion.contracts import digest
from engine.mechanism_scope import contains

DEFAULT = Path(__file__).resolve().parent.parent / "config/commodity-alert-policy.json"


class Span(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=300)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    selection_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    commodity_id: str = Field(min_length=1, max_length=100)
    basis: Literal["PRICE_PAIR", "REPORTED_CHANGE"]
    quote: str = Field(min_length=1, max_length=8000)
    fields: dict[str, Span]
    reviewed_at: AwareDatetime
    reviewer_id: str = Field(min_length=1, max_length=100)
    reviewer_kind: Literal["HUMAN", "AI_OPERATOR"]


class InputBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    commodity_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=2, max_length=100)
    atlas_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    usage_relation_id: str
    source_id: str
    quote: str = Field(min_length=1, max_length=8000)
    reviewed_at: AwareDatetime
    review_until: AwareDatetime
    reviewer_id: str = Field(min_length=1, max_length=100)
    reviewer_kind: Literal["HUMAN", "AI_OPERATOR"]


def load_policy(path=DEFAULT):
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema") != "commodity-alert-policy-v1"
        or type(policy.get("version")) is not int
        or policy["version"] < 1
        or policy.get("delivery") != "disabled"
        or policy.get("comparison") != "STRICTLY_GREATER_MINIMUM_STRONG_AT_OR_ABOVE"
        or policy.get("period_policy") != "EXPLICIT_SOURCE_PERIOD_NO_DEFAULT_WINDOW"
        or policy.get("basis") != "USER_REQUESTED_EXPERIMENTAL_PRICE_MOVE_NOT_COMPANY_IMPACT"
    ):
        raise ValueError("Unsupported commodity policy")
    low, high = (
        Decimal(policy[k]) for k in ["minimum_absolute_change_pct", "strong_absolute_change_pct"]
    )
    if (
        not low.is_finite()
        or not high.is_finite()
        or not 0 < low < high
        or type(policy.get("maximum_period_end_age_days")) is not int
        or not 0 <= policy["maximum_period_end_age_days"] <= 365
    ):
        raise ValueError("Finite positive ordered commodity thresholds required")
    return policy


def price_change(observation, at, published_at=None):
    if not re.search(r"\bprices?\b|\bgiá\b", observation.quote, re.I):
        raise ValueError("Explicit price statement required, not an arbitrary commodity metric")
    relative = observation.basis == "REPORTED_CHANGE" and "period" in observation.fields
    common = {"commodity", "period"} if relative else {"commodity", "period_start", "period_end"}
    required = common | (
        {
            "previous",
            "current",
            "previous_currency",
            "current_currency",
            "previous_unit",
            "current_unit",
        }
        if observation.basis == "PRICE_PAIR"
        else {"change", "direction"}
    )
    if set(observation.fields) != required:
        raise ValueError("Complete explicit price/period fields required; no inferred values")
    values = {}
    for key, span in observation.fields.items():
        if (
            not 0 <= span.start < span.end <= len(observation.quote)
            or observation.quote[span.start : span.end] != span.text
        ):
            raise ValueError("Price field not grounded in exact source offsets")
        if not re.compile(r"(?<!\w)" + re.escape(span.text) + r"(?!\w)").match(
            observation.quote, span.start
        ):
            raise ValueError("Partial price token rejected")
        if key in {"previous", "current", "change"} and (
            (span.start and observation.quote[span.start - 1] in "-+.,0123456789")
            or (span.end < len(observation.quote) and observation.quote[span.end] in "0123456789%")
            or (
                span.end + 1 < len(observation.quote)
                and observation.quote[span.end] in ".,"
                and observation.quote[span.end + 1].isdigit()
            )
        ):
            raise ValueError("Truncated numeric token rejected")
        values[key] = span.text
    start = None
    end = None
    if relative:
        if (
            values["period"].casefold()
            not in {
                "over the past week",
                "over the past month",
                "over the past year",
                "this week",
                "this month",
                "year to date",
                "trong tuần qua",
                "trong tháng qua",
                "từ đầu năm",
            }
            or not published_at
        ):
            raise ValueError(
                "Supported explicit relative period and publication timestamp required"
            )
        publication = datetime.fromisoformat(published_at)
        if publication.tzinfo is None or publication > at:
            raise ValueError("Publication reference must be known and nonfuture")
        freshness_date = publication.date()
    else:
        start, end = (
            date.fromisoformat(values["period_start"]),
            date.fromisoformat(values["period_end"]),
        )
        if not start < end <= at.date():
            raise ValueError("Explicit completed comparison period required")
        freshness_date = end
    if re.search(
        r"\b(?:not|might|could|may|forecast|expected|if|percentage points|between|roughly|approximately|about|nearly|up to|at least|at most)\b|không|có thể|dự báo|nếu|khoảng|tối đa|ít nhất",
        observation.quote,
        re.I,
    ):
        raise ValueError(
            "Uncertain/negated/projection or percentage-point statement requires review"
        )
    if observation.basis == "PRICE_PAIR":
        if (
            values["previous_currency"] != values["current_currency"]
            or values["previous_unit"] != values["current_unit"]
        ):
            raise ValueError("Same explicit currency and unit required; no implicit conversion")
        for name in ["previous", "current"]:
            if not re.fullmatch(r"\d+(?:\.\d+)?", values[name]):
                raise ValueError("Only unambiguous nonnegative decimal prices supported")
        previous, current = Decimal(values["previous"]), Decimal(values["current"])
        if previous <= 0:
            raise ValueError("Baseline price must be positive")
        change = (current - previous) / previous * 100
    else:
        if not re.fullmatch(r"\d+(?:\.\d+)?%", values["change"]):
            raise ValueError("Explicit percent change required, not percentage points")
        direction = values["direction"].casefold()
        if direction not in {
            "rose",
            "increased",
            "up",
            "tăng",
            "fell",
            "decreased",
            "down",
            "giảm",
        }:
            raise ValueError("Unambiguous reported direction required")
        change = Decimal(values["change"][:-1]) * (
            1 if direction in {"rose", "increased", "up", "tăng"} else -1
        )
        if change < -100:
            raise ValueError("Unsupported price decline below minus100percent")
    return {
        "signed_change_pct": str(change),
        "absolute_change_pct": str(abs(change)),
        "period_start": start.isoformat() if start else None,
        "period_end": end.isoformat() if end else None,
        "period_label": values.get("period"),
        "freshness_reference_date": freshness_date.isoformat(),
        "freshness_reference_basis": "SOURCE_PUBLICATION_NOT_INVENTED_PERIOD_ENDPOINT"
        if relative
        else "EXPLICIT_PERIOD_END",
        "basis": observation.basis,
        "source_fields": values,
        "interpretation": "SOURCE_SPANS_REVIEWER_DECLARED_COMPARABILITY",
        "formula": "(current-previous)/previous*100"
        if observation.basis == "PRICE_PAIR"
        else "REPORTED_PERCENT_WITH_EXPLICIT_DIRECTION",
    }


def evaluate(
    data,
    observation,
    selection,
    bindings,
    *,
    store,
    article_root=None,
    news_conn=None,
    at=None,
    policy_path=DEFAULT,
):
    at = at or datetime.now(UTC)
    policy = load_policy(policy_path)
    if (
        at.tzinfo is None
        or at > datetime.now(UTC)
        or digest(selection) != observation.selection_sha256
    ):
        raise ValueError("Observation selection/time mismatch")
    packet, body = reviewed_body(selection, at, article_root=article_root)
    if (
        observation.quote not in body
        or not datetime.fromisoformat(selection["body_review"]["reviewed_at"])
        <= observation.reviewed_at
        <= at
        or datetime.fromisoformat(packet["retrieved_at"]) > observation.reviewed_at
        or datetime.fromisoformat(data["as_of"]) > at
        or data["delivery"] != "disabled"
    ):
        raise ValueError("Observation quote/review or atlas chronology invalid")
    lifecycle = None
    if news_conn is not None:
        from engine.scope_sources import sync

        lifecycle = sync(store, news_conn, selection, at)
    before = store.fingerprint()
    history = store.history("source", selection["revision"]["id"])
    if not history:
        raise ValueError("Source lifecycle state must be registered")
    state = history[-1]["payload"]
    source_ok = (
        state["status"] == "CURRENT"
        and state["packet_sha256"] == selection["packet_sha256"]
        and datetime.fromisoformat(state["observed_at"]) <= at
    )
    if state.get("registry_sha256"):
        source_ok = (
            source_ok
            and lifecycle is not None
            and lifecycle["registry_sha256"] == state["registry_sha256"]
        )
    if lifecycle:
        source_ok = source_ok and lifecycle["fresh"] and lifecycle["status"] == "CURRENT"
    try:
        measurement = price_change(
            observation, at, selection["revision"]["payload"].get("published_at")
        )
    except ValueError as exc:
        return {
            "mode": "LOCAL_COMMODITY_RELEVANCE_NOT_VERIFIED_IMPACT",
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": str(exc),
            "candidate_alerts": [],
            "delivery": "disabled",
            "active_feed_changed": False,
            "financial_magnitude": "UNKNOWN",
            "policy": policy,
            "observation_sha256": digest(observation.model_dump(mode="json")),
        }
    amount = Decimal(measurement["absolute_change_pct"])
    large = amount > Decimal(policy["minimum_absolute_change_pct"])
    recent = (
        at.date() - date.fromisoformat(measurement["freshness_reference_date"])
    ).days <= policy["maximum_period_end_age_days"]
    band = (
        "STRONG_PRICE_MOVE"
        if amount >= Decimal(policy["strong_absolute_change_pct"])
        else "NOTICEABLE_PRICE_MOVE"
        if large
        else "BELOW_OR_AT_THRESHOLD"
    )
    nodes = {n["id"]: n for n in data["nodes"]}
    edges = {r["id"]: r for r in data["relations"]}
    profiles = {p["id"]: p for p in data["profiles"]}
    if len(bindings) > 1000 or len({b.id for b in bindings}) != len(bindings):
        raise ValueError("Bounded unique commodity bindings required")
    cards = []
    skipped = []
    seen = set()
    for binding in bindings:
        if binding.commodity_id != observation.commodity_id:
            continue
        try:
            if (
                binding.atlas_sha256 != digest(data)
                or not binding.reviewed_at <= at < binding.review_until
                or not 0
                < (binding.review_until - binding.reviewed_at).total_seconds()
                <= 90 * 86400
                or datetime.fromisoformat(data["as_of"]) > binding.reviewed_at
            ):
                raise ValueError("Input binding atlas/version/review expired")
            edge = edges.get(binding.usage_relation_id)
            if (
                edge is None
                or edge["type"] not in {"USES_INPUT", "DEPENDS_ON"}
                or nodes[edge["to_id"]]["kind"] != "input"
                or nodes[edge["from_id"]]["kind"] not in {"product", "segment", "facility"}
                or nodes[edge["from_id"]]["profile_id"] != edge["profile_id"]
                or nodes[edge["to_id"]]["profile_id"] != edge["profile_id"]
                or edge["status"] != "SOURCE_BACKED"
                or not edge["eligible_at_snapshot"]
                or datetime.fromisoformat(edge["valid_from"]) > at
                or (edge["valid_until"] and at >= datetime.fromisoformat(edge["valid_until"]))
            ):
                raise ValueError("Sourced current product-to-input usage required")
            if not any(
                e["source_id"] == binding.source_id and binding.quote in e["quote"]
                for e in edge["evidence"]
            ):
                raise ValueError("Input quote not on usage relationship")
            if binding.name.casefold() != measurement["source_fields"][
                "commodity"
            ].casefold() or not contains(binding.quote, binding.name):
                raise ValueError("Commodity name must match news and sourced input inventory")
            profile = profiles[edge["profile_id"]]
            if (profile["id"], edge["id"]) in seen:
                continue
            seen.add((profile["id"], edge["id"]))
            if not source_ok or not large or not recent:
                continue
            cards.append(
                {
                    "kind": "COMMODITY_PRICE_ALERT_CANDIDATE",
                    "ticker": profile["ticker"],
                    "company_id": profile["company_id"],
                    "commodity_id": binding.commodity_id,
                    "commodity": binding.name,
                    "product": nodes[edge["from_id"]]["label"],
                    "usage_relation_id": edge["id"],
                    "usage_evidence": edge["evidence"],
                    "narrative_ids": [
                        n["id"]
                        for n in data["narratives"]
                        if n["profile_id"] == profile["id"]
                        and set(n["watched_nodes"]) & {edge["from_id"], edge["to_id"]}
                    ],
                    "relevance": "DIRECT_SOURCED_INPUT_MATCH",
                    "price_move_band": band,
                    "measurement": measurement,
                    "source_quote": observation.quote,
                    "source_url": packet["url"],
                    "source_packet_sha256": selection["packet_sha256"],
                    "source_epoch": history[-1]["version"],
                    "conditional_cost_pressure": "UP"
                    if Decimal(measurement["signed_change_pct"]) > 0
                    else "DOWN",
                    "impact_basis": "INPUT_COST_PRESSURE_IF_PURCHASE_PRICES_TRANSMIT",
                    "mitigants_to_check": [
                        "input_cost_share",
                        "inventory",
                        "hedging",
                        "contract_reset",
                        "pass_through",
                        "substitutes",
                    ],
                    "benchmark_grade_geography_applicability": "UNVERIFIED",
                    "financial_magnitude": "UNKNOWN",
                    "horizon": "UNKNOWN",
                    "probability": None,
                    "policy_sha256": digest(policy),
                    "binding_sha256": digest(binding.model_dump(mode="json")),
                    "mode": "LOCAL_RESEARCH_DRY_RUN",
                    "delivery": "disabled",
                }
            )
        except ValueError as exc:
            skipped.append({"binding_id": binding.id, "reason": str(exc)})
    if lifecycle:
        from engine.scope_sources import inspect

        try:
            source_ok = source_ok and inspect(news_conn, selection, at) == lifecycle
        except ValueError:
            source_ok = False
    if store.fingerprint() != before:
        source_ok = False
    if not source_ok:
        cards = []
    return {
        "mode": "LOCAL_COMMODITY_RELEVANCE_NOT_VERIFIED_IMPACT",
        "policy": policy,
        "measurement": measurement,
        "price_move_band": band,
        "period_recent": recent,
        "source_current": bool(source_ok),
        "source_lifecycle": lifecycle or {"basis": "MANUAL_LOCAL_RESEARCH_ONLY"},
        "candidate_alerts": cards,
        "skipped_bindings": skipped,
        "delivery": "disabled",
        "active_feed_changed": False,
        "legal_entity_anchor_required": False,
        "financial_magnitude": "UNKNOWN",
        "price_prediction": None,
        "observation_sha256": digest(observation.model_dump(mode="json")),
        "atlas_sha256": digest(data),
    }


def evaluate_registry(data, observation, selection, registry_root, *, market_id=None, **kwargs):
    """Shared commodity registry, retaining the existing source/measurement gates."""
    from engine.input_markets import read, route

    registry = read(registry_root, data)
    result = evaluate(data, observation, selection, [], **kwargs)
    result["input_registry_sha256"] = digest(registry.model_dump(mode="json"))
    result["input_registry_version"] = registry.version
    commodity = next((c for c in registry.commodities if c.id == observation.commodity_id), None)
    if result.get("status") == "INSUFFICIENT_EVIDENCE":
        return result
    if commodity is None or result["measurement"]["source_fields"]["commodity"].casefold() not in {
        a.casefold() for a in commodity.aliases
    }:
        result["registry_hold"] = "UNKNOWN_OR_MISMATCHED_COMMODITY"
        return result
    if market_id:
        market = next((m for m in registry.markets if m.id == market_id), None)
        if (
            market is None
            or market.commodity_id != commodity.id
            or not contains(observation.quote, market.instrument)
            or not contains(observation.quote.casefold(), market.basis.casefold())
        ):
            result["registry_hold"] = "MARKET_NOT_EXPLICIT_OR_INCOMPATIBLE"
            return result
        fields = result["measurement"]["source_fields"]
        if observation.basis == "PRICE_PAIR" and (
            (market.currency and fields["current_currency"] != market.currency)
            or (market.unit and fields["current_unit"] != market.unit)
        ):
            result["registry_hold"] = "MARKET_UNIT_MISMATCH"
            return result
    if (
        not result["source_current"]
        or not result["period_recent"]
        or result["price_move_band"] == "BELOW_OR_AT_THRESHOLD"
    ):
        return result
    profiles = {p["id"]: p for p in data["profiles"]}
    sources = {s.id: s for s in registry.sources}
    for row in route(registry, commodity.id, market_id=market_id, at=kwargs.get("at")):
        e = row["exposure"]
        p = profiles[e["profile_id"]]
        result["candidate_alerts"].append(
            {
                "kind": "COMMODITY_PRICE_ALERT_CANDIDATE",
                "ticker": p["ticker"],
                "company_id": p["company_id"],
                "commodity_id": commodity.id,
                "commodity": commodity.label,
                "product": e["product_label"],
                "scope": e["scope"],
                "usage_relation_id": "input-registry/" + e["id"],
                "usage_evidence": e["evidence"],
                "usage_source_urls": sorted(
                    {str(sources[x["source_id"]].url) for x in e["evidence"]}
                ),
                "narrative_ids": [
                    n["id"]
                    for n in data["narratives"]
                    if n["profile_id"] == p["id"] and e["product_node_id"] in n["watched_nodes"]
                ],
                "relevance": "DIRECT_SOURCED_PRODUCT_INPUT_MATCH",
                "price_move_band": result["price_move_band"],
                "measurement": result["measurement"],
                "source_quote": observation.quote,
                "source_url": selection["revision"]["payload"]["url"],
                "source_packet_sha256": selection["packet_sha256"],
                "price_markets": row["price_markets"],
                "selected_market_id": market_id,
                "benchmark_grade_geography_applicability": "BENCHMARK_PROXY_ONLY"
                if market_id
                else "NOT_SELECTED",
                "conditional_cost_pressure": "UP"
                if Decimal(result["measurement"]["signed_change_pct"]) > 0
                else "DOWN",
                "impact_basis": "INPUT_COST_PRESSURE_IF_PURCHASE_PRICES_TRANSMIT",
                "financial_magnitude": "UNKNOWN",
                "horizon": "UNKNOWN",
                "probability": None,
                "purchase_price_verified": False,
                "delivery": "disabled",
            }
        )
    return result
