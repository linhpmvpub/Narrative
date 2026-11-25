"""Versioned mechanism/data/rule workbench. No LLM, live feed or implicit calibration."""

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from engine.impact_atlas import DIMENSIONS, MECHANISMS, read_snapshot
from engine.impact_events import EventFrame, assess
from engine.ingestion.contracts import digest

DEFAULT = Path(__file__).resolve().parent.parent / "config/mechanism-playbook.json"
COST_FORMULA = "input_cost_share * unhedged_share * reset_share * price_change * (1-pass_through)"
COST_DOMAINS = {
    name: (-1, 10, "fraction_change") if name == "price_change" else (0, 1, "fraction")
    for name in [
        "input_cost_share",
        "unhedged_share",
        "reset_share",
        "price_change",
        "pass_through",
    ]
}
CONDITIONS = [
    "source_and_event_integrity",
    "untruncated_paths",
    "at_least_one_directed_path",
    "phase_operating",
    "event_exposure_scope_independently_reviewed",
    "relation_scoped_parameters_available",
    "causal_magnitude_and_timing_validated",
]
FAILURES = [
    "REJECT_INVALID_INPUT",
    "HOLD_TRUNCATED",
    "NO_PATH",
    "WATCH_PLAN_OR_COMMITMENT",
    "REVIEW_SCOPE",
    "REVIEW_DATA",
    "REVIEW_CAUSALITY",
]


def load(path=DEFAULT):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        data.get("schema") != "mechanism-playbook-v1"
        or data.get("version") != 1
        or data.get("status") != "EXPLICIT_RULES_UNCALIBRATED"
        or data.get("ranking_weights") is not None
        or data.get("delivery") != "disabled"
        or data.get("price_prediction") is not None
        or set(data.get("groups", {})) != set(MECHANISMS)
        or set(data.get("parameters", {})) != set(DIMENSIONS)
    ):
        raise ValueError("Unsupported playbook identity, groups or policy")
    subtypes = set()
    for name, group in data["groups"].items():
        original = MECHANISMS[name]
        if (
            group["channel"] != original["channel"]
            or group["driver_up_channel_sign"] != original["sign"]
            or group["required_parameters"] != original["mitigants"]
        ):
            raise ValueError("Playbook and atlas mechanism semantics diverged")
        for subtype in group["subtypes"]:
            if subtype["id"] in subtypes or not subtype["id"].startswith(name + "."):
                raise ValueError("Duplicate or cross-family subtype")
            subtypes.add(subtype["id"])
        if not group["subtypes"]:
            raise ValueError("Explicit event subtypes required")
    fractions = {
        "exposure_share",
        "supplier_concentration",
        "customer_concentration",
        "pass_through",
        "utilization",
        "yield",
        "market_share",
        "geographic_mix",
    }
    for name, parameter in data["parameters"].items():
        unit = "fraction" if name in fractions else "days" if name.endswith("_days") else "category"
        if (
            parameter["unit"] != unit
            or parameter["unknown_policy"] != "KEEP_UNKNOWN_NEVER_ZERO"
            or parameter["minimum"] != (None if unit == "category" else 0)
            or parameter["maximum"] != (1 if unit == "fraction" else None)
        ):
            raise ValueError("Invalid parameter unit, domain or unknown policy")
    if (
        len(data["rules"]) != 7
        or [r["id"] for r in data["rules"]] != [f"R0{i}" for i in range(1, 8)]
        or [r["condition"] for r in data["rules"]] != CONDITIONS
        or [r["failure"] for r in data["rules"]] != FAILURES
    ):
        raise ValueError("Unsupported executable rule contract")
    bins = data["horizon_bins"]
    if (
        type(bins["short_max_days"]) is not int
        or type(bins["medium_max_days"]) is not int
        or not 0 < bins["short_max_days"] < bins["medium_max_days"]
        or bins["basis"] != "EDITORIAL_BINS_NOT_EMPIRICAL_LAGS"
    ):
        raise ValueError("Invalid editorial horizon bins")
    models = data.get("sensitivity_models", {})
    if set(models) != {"COST_SENSITIVITY_V1"}:
        raise ValueError("Unsupported sensitivity model")
    model = models["COST_SENSITIVITY_V1"]
    if (
        model["formula"] != COST_FORMULA
        or model["status"] != "SCENARIO_ONLY_NOT_CALIBRATED"
        or model["output_unit"] != "fraction_of_same_period_baseline_cost"
        or set(model["inputs"]) != set(COST_DOMAINS)
    ):
        raise ValueError("Sensitivity formula contract changed")
    for name, (lo, hi, unit) in COST_DOMAINS.items():
        field = model["inputs"][name]
        if (field["min"], field["max"], field["unit"]) != (lo, hi, unit):
            raise ValueError("Sensitivity domain or unit changed")
    return data


def inventory(data, book):
    """Do not pool exposures or treat a populated field as mechanism applicability."""
    edges = {r["id"]: r for r in data["relations"]}
    rows = []
    for exposure in data["exposures"]:
        active = edges[exposure["relation_id"]]["eligible_at_snapshot"]
        for group_id, group in book["groups"].items():
            fields = []
            for name in group["required_parameters"]:
                fact = exposure["dimensions"].get(name, {})
                present = active and fact.get("status") == "SOURCED"
                fields.append(
                    {
                        "parameter": name,
                        "unit": book["parameters"][name]["unit"],
                        "status": "SOURCED_CONTEXT" if present else "MISSING",
                        "fact": fact if present else None,
                        "applicable_to_event": "NOT_ASSESSED",
                    }
                )
            rows.append(
                {
                    "profile_id": exposure["profile_id"],
                    "relation_id": exposure["relation_id"],
                    "mechanism_id": group_id,
                    "fields": fields,
                    "missing": [f["parameter"] for f in fields if f["status"] == "MISSING"],
                    "eligible_relation": active,
                }
            )
    return rows


def evaluate(
    data,
    frame,
    selection,
    subtype,
    *,
    book=None,
    article_root=None,
    at=None,
    scope_store=None,
    reviewer_policy=None,
    scope_reviews=None,
    news_conn=None,
):
    from datetime import UTC, datetime

    book = book or load()
    at = at or datetime.now(UTC)
    if frame.mechanism_id not in book["groups"]:
        raise ValueError("R01: unknown event mechanism")
    group = book["groups"][frame.mechanism_id]
    if subtype not in {s["id"] for s in group["subtypes"]}:
        raise ValueError("Subtype must belong to event mechanism")
    # Existing source hash, quote, chronology and directed graph gates remain authoritative.
    base = assess(data, frame, selection, article_root=article_root, at=at)
    from engine.scope_review import check

    lifecycle = None
    if news_conn is not None:
        if scope_store is None:
            raise ValueError("Ingestion lifecycle requires a scope store")
        from engine.scope_sources import sync

        lifecycle = sync(scope_store, news_conn, selection, at)

    bindings = scope_reviews or {}
    ledger_before = scope_store.fingerprint() if scope_store is not None else None
    path_keys = {digest([p["narrative_id"], p["relations"]]) for p in base["paths"]}
    if not set(bindings) <= path_keys:
        raise ValueError("Scope review binding names an unrelated path")
    scope_results = []
    for path in base["paths"]:
        key = digest([path["narrative_id"], path["relations"]])
        result = {"status": "UNKNOWN", "reason": "NO_SCOPE_REVIEW"}
        if key in bindings and scope_store is not None:
            try:
                result = check(
                    scope_store,
                    bindings[key],
                    reviewer_policy,
                    data,
                    frame,
                    selection,
                    path,
                    book,
                    at,
                    registry_sha256=lifecycle["registry_sha256"] if lifecycle else None,
                )
            except (ValueError, OSError) as exc:
                result = {"status": "UNKNOWN", "reason": str(exc)}
        scope_results.append({"path_sha256": key, **result})
    if lifecycle is not None:
        from engine.scope_sources import inspect

        try:
            after = inspect(news_conn, selection, at)
            current = after == lifecycle and after["fresh"] and after["status"] == "CURRENT"
        except ValueError:
            current = False
        if not current:
            scope_results = [
                {
                    "path_sha256": r["path_sha256"],
                    "status": "UNKNOWN",
                    "reason": "INGESTION_CHANGED_SUPERSEDED_DISABLED_OR_STALE",
                }
                for r in scope_results
            ]
    if scope_store is not None and scope_store.fingerprint() != ledger_before:
        scope_results = [
            {
                "path_sha256": r["path_sha256"],
                "status": "UNKNOWN",
                "reason": "LEDGER_CHANGED_DURING_EVALUATION",
            }
            for r in scope_results
        ]
    scoped = bool(scope_results) and all(r["status"] == "PASS" for r in scope_results)
    relation_ids = {rid for path in base["paths"] for rid in path["relations"]}
    requirements = [
        r
        for r in inventory(data, book)
        if r["relation_id"] in relation_ids and r["mechanism_id"] == frame.mechanism_id
    ]
    complete = bool(requirements) and not any(r["missing"] for r in requirements)
    states = [
        "PASS",
        "FAIL" if base["truncated"] else "PASS",
        "PASS" if base["paths"] else "FAIL",
        "PASS" if frame.phase == "OPERATING" else "FAIL",
        "PASS" if scoped else "UNKNOWN",
        "PASS" if complete else "UNKNOWN",
        "UNKNOWN",
    ]
    trace = [{**rule, "result": state} for rule, state in zip(book["rules"], states, strict=True)]
    first = next(r for r in trace if r["result"] != "PASS")
    edges = {edge["id"]: edge for edge in data["relations"]}
    labels = {node["id"]: node["label"] for node in data["nodes"]}
    return {
        "schema": "mechanism-decision-v1",
        "playbook_sha256": digest(book),
        "event_subtype": subtype,
        "mechanism": group,
        "source_assessment": base,
        "data_requirements": requirements,
        "decision_trace": trace,
        "scope_reviews": scope_results,
        "related_context_cards": [
            {
                "kind": "RELATED_CONTEXT",
                "label": "Bối cảnh liên quan — chưa xác minh tác động",
                "narrative_id": path["narrative_id"],
                "relations": path["relations"],
                "relationship_path": [
                    {
                        "id": rid,
                        "type": edges[rid]["type"],
                        "from": labels[edges[rid]["from_id"]],
                        "to": labels[edges[rid]["to_id"]],
                        "evidence": edges[rid]["evidence"],
                    }
                    for rid in path["relations"]
                ],
                "event_id": frame.id,
                "event_quote": frame.source_quote,
                "phase": frame.phase,
                "source_url": base["source_url"],
                "source_packet_sha256": selection["packet_sha256"],
                "scope_review": result,
                "conditions": group["conditions"],
                "why_related": "Đường quan hệ có nguồn và phạm vi bối cảnh được thẩm định; chưa chứng minh truyền tác động",
                "strength": "UNKNOWN",
                "horizon": "UNKNOWN",
                "financial_magnitude": "UNKNOWN",
                "price_prediction": None,
                "delivery": "disabled",
                "active_feed_changed": False,
            }
            for path, result in zip(base["paths"], scope_results, strict=True)
            if result["status"] == "CONTEXT" and not base["truncated"]
        ],
        "source_lifecycle": lifecycle or {"basis": "MANUAL_LOCAL_RESEARCH_ONLY"},
        "review_queue": first["failure"],
        "first_unmet_rule": first["id"],
        "explanation": {
            "why_related": "Directed atlas paths are candidates, not verified economic transmission",
            "driver": group["driver"],
            "channel": group["channel"],
            "conditional_channel_direction": base["conditional_channel_direction"],
            "conditions": group["conditions"],
            "missing_parameter_slots": sum(len(r["missing"]) for r in requirements),
            "strength": "UNKNOWN",
            "horizon": "UNKNOWN",
        },
        "financial_magnitude": "UNKNOWN",
        "price_prediction": None,
        "delivery": "disabled",
        "active_feed_changed": False,
        "independent_scope_and_causality_review": "R05_LOCAL_REVIEW_LEDGER_R07_UNKNOWN",
    }


def horizon_band(min_days, max_days, book=None):
    """Editorial display of an externally supplied interval, not inferred event timing."""
    book = book or load()
    if min_days is None and max_days is None:
        return "UNKNOWN"
    if type(min_days) is not int or type(max_days) is not int or not 0 <= min_days <= max_days:
        raise ValueError("Complete nonnegative ordered day interval required")
    bins = book["horizon_bins"]

    def band(value):
        return (
            "SHORT"
            if value <= bins["short_max_days"]
            else "MEDIUM"
            if value <= bins["medium_max_days"]
            else "LONG"
        )

    return band(min_days) if band(min_days) == band(max_days) else "CROSSES_BANDS"


def cost_scenario(values, book=None):
    """Illustrative sensitivity, NEVER a sourced estimate or margin/stock forecast.

    Five explicit assumptions over one baseline cost pool and period. reset_share is
    conditional on the unhedged slice. pass_through is realized recovery of that slice's
    incremental cost. No silent zeros, interactions or alternative denominator inference.
    """
    book = book or load()
    model = book["sensitivity_models"]["COST_SENSITIVITY_V1"]
    names = set(model["inputs"])
    if set(values) != names:
        raise ValueError("All five explicit scenario assumptions required")
    numbers = {}
    for name, raw in values.items():
        if isinstance(raw, bool):
            raise ValueError("Boolean is not a numeric assumption")
        try:
            value = Decimal(str(raw))
        except InvalidOperation as exc:
            raise ValueError("Finite numeric assumption required") from exc
        if (
            not value.is_finite()
            or not model["inputs"][name]["min"] <= value <= model["inputs"][name]["max"]
        ):
            raise ValueError("Scenario assumption outside declared domain")
        numbers[name] = value
    result = (
        numbers["input_cost_share"]
        * numbers["unhedged_share"]
        * numbers["reset_share"]
        * numbers["price_change"]
        * (1 - numbers["pass_through"])
    )
    return {
        "formula_id": "COST_SENSITIVITY_V1",
        "assumptions": {k: str(v) for k, v in numbers.items()},
        "net_incremental_cost_fraction_of_baseline_cost": str(result),
        "basis": "OPERATOR_SCENARIO_NOT_SOURCED_FINANCIAL_ESTIMATE",
        "formula": model["formula"],
        "unit": model["output_unit"],
        "model_assumptions": model["assumptions"],
        "delivery": "disabled",
        "financial_magnitude": "UNKNOWN",
        "price_prediction": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inventory", "evaluate", "cost-scenario"])
    parser.add_argument("--playbook", type=Path, default=DEFAULT)
    parser.add_argument("--atlas", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--articles", type=Path)
    parser.add_argument("--subtype")
    parser.add_argument("--scope-store", type=Path)
    parser.add_argument("--scope-reviews", type=Path)
    parser.add_argument("--reviewer-policy", type=Path)
    parser.add_argument(
        "--news-current",
        action="store_true",
        help="Require current ingestion revision and RSS poll freshness",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    book = load(args.playbook)
    if args.action == "cost-scenario":
        if args.input is None:
            parser.error("--input required")
        result = cost_scenario(json.loads(args.input.read_text(encoding="utf-8")), book=book)
        result["playbook_sha256"] = digest(book)
    else:
        if args.atlas is None:
            parser.error("--atlas required")
        data = read_snapshot(args.atlas)
        if args.action == "inventory":
            result = {
                "playbook": book,
                "playbook_sha256": digest(book),
                "atlas_sha256": digest(data),
                "items": inventory(data, book),
                "delivery": "disabled",
            }
        else:
            if not all([args.input, args.selection, args.articles, args.subtype]):
                parser.error("--input --selection --articles --subtype required")
            from engine.scope_review import Store

            supplied = [args.scope_store, args.scope_reviews, args.reviewer_policy]
            if any(supplied) and not all(supplied):
                parser.error("--scope-store --scope-reviews --reviewer-policy required together")
            from contextlib import ExitStack

            from engine.db import database
            from engine.settings import Settings

            with ExitStack() as stack:
                news_conn = None
                if args.news_current:
                    engine = database(Settings.from_env().database_url)
                    stack.callback(engine.dispose)
                    news_conn = stack.enter_context(engine.connect())
                result = evaluate(
                    data,
                    EventFrame.model_validate_json(args.input.read_bytes()),
                    json.loads(args.selection.read_text(encoding="utf-8")),
                    args.subtype,
                    book=book,
                    article_root=args.articles,
                    scope_store=Store(args.scope_store) if args.scope_store else None,
                    scope_reviews=json.loads(args.scope_reviews.read_text(encoding="utf-8"))
                    if args.scope_reviews
                    else None,
                    reviewer_policy=json.loads(args.reviewer_policy.read_text(encoding="utf-8"))
                    if args.reviewer_policy
                    else None,
                    news_conn=news_conn,
                )
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({"delivery": "disabled", "output": str(args.output)}))


if __name__ == "__main__":
    main()
