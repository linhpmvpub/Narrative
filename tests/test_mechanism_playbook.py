"""Synthetic mechanism/data/rule contracts, not financial accuracy evidence."""

import copy
import json
import os
from decimal import Decimal

import pytest
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_impact_events import frame
from test_profile_news import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.impact_atlas import snapshot
from engine.mechanism_playbook import cost_scenario, evaluate, horizon_band, inventory, load


def test_catalog_has_explicit_groups_and_no_calibrated_weights():
    b = load()
    assert len(b["groups"]) == 7 and len(b["parameters"]) == 30
    assert sum(len(g["subtypes"]) for g in b["groups"].values()) == 21
    assert len(b["rules"]) == 7 and b["ranking_weights"] is None
    assert b["parameters"]["inventory_days"]["unit"] == "days"


@pytest.mark.parametrize(
    "fault", ["weights", "delivery", "unit", "direction", "subtype", "rule", "bins"]
)
def test_invalid_catalog_rejected(tmp_path, fault):
    b = copy.deepcopy(load())
    if fault == "weights":
        b["ranking_weights"] = {"relevance": 0.8}
    elif fault == "delivery":
        b["delivery"] = "enabled"
    elif fault == "unit":
        b["parameters"]["inventory_days"]["unit"] = "USD"
    elif fault == "direction":
        b["groups"]["input_price"]["driver_up_channel_sign"] = -1
    elif fault == "subtype":
        b["groups"]["capacity"]["subtypes"][0]["id"] = "demand.orders"
    elif fault == "rule":
        b["rules"][4]["condition"] = "always_pass"
    else:
        b["horizon_bins"]["medium_max_days"] = 30
    p = tmp_path / "book.json"
    p.write_text(json.dumps(b))
    with pytest.raises(ValueError):
        load(p)


def test_source_to_rules_to_trace_keeps_scope_and_impact_unknown(linked, dossier, selection):
    data = snapshot(os.environ["COMPANY_PROFILE_ROOT"])
    result = evaluate(data, frame(selection), selection, "input_price.spot")
    assert result["source_assessment"]["paths"]
    assert result["first_unmet_rule"] == "R05" and result["review_queue"] == "REVIEW_SCOPE"
    assert result["decision_trace"][0]["result"] == "PASS"
    assert result["explanation"]["conditional_channel_direction"] == "DOWN"
    assert result["explanation"]["missing_parameter_slots"] > 0
    assert result["financial_magnitude"] == "UNKNOWN" and result["delivery"] == "disabled"
    planned = frame(selection).model_copy(update={"phase": "PROPOSED"})
    assert evaluate(data, planned, selection, "input_price.spot")["first_unmet_rule"] == "R04"
    with pytest.raises(ValueError):
        evaluate(data, frame(selection), selection, "financing.commitment")
    bad = frame(selection).model_copy(update={"source_quote": "Invented price change"})
    with pytest.raises(ValueError):
        evaluate(data, bad, selection, "input_price.spot")
    for edge in data["relations"]:
        edge["eligible_at_snapshot"] = False
    assert (
        evaluate(data, frame(selection), selection, "input_price.spot")["first_unmet_rule"] == "R03"
    )


def test_no_cross_relation_parameter_pooling(linked, dossier):
    data = snapshot(os.environ["COMPANY_PROFILE_ROOT"])
    e = data["exposures"][0]
    e["dimensions"]["pass_through"] = {
        "status": "SOURCED",
        "id": "synthetic",
        "value": ".5",
        "unit": "fraction",
    }
    rows = inventory(data, load())
    own = next(
        r
        for r in rows
        if r["relation_id"] == e["relation_id"] and r["mechanism_id"] == "input_price"
    )
    assert "pass_through" not in own["missing"]
    assert all(
        "pass_through" in r["missing"]
        for r in rows
        if r["relation_id"] != e["relation_id"] and r["mechanism_id"] == "input_price"
    )
    for edge in data["relations"]:
        if edge["id"] == e["relation_id"]:
            edge["eligible_at_snapshot"] = False
    own = next(
        r
        for r in inventory(data, load())
        if r["relation_id"] == e["relation_id"] and r["mechanism_id"] == "input_price"
    )
    assert "pass_through" in own["missing"]


def values():
    return dict(
        input_cost_share=".2",
        unhedged_share=".5",
        reset_share=".8",
        price_change=".1",
        pass_through=".25",
    )


def test_explicit_cost_sensitivity_not_profit_or_price_forecast():
    result = cost_scenario(values())
    assert Decimal(result["net_incremental_cost_fraction_of_baseline_cost"]) == Decimal("0.006")
    assert result["basis"] == "OPERATOR_SCENARIO_NOT_SOURCED_FINANCIAL_ESTIMATE"
    assert result["financial_magnitude"] == "UNKNOWN" and result["price_prediction"] is None
    assert (
        Decimal(
            cost_scenario({**values(), "unhedged_share": 0})[
                "net_incremental_cost_fraction_of_baseline_cost"
            ]
        )
        == 0
    )
    assert Decimal(
        cost_scenario({**values(), "price_change": "-.1"})[
            "net_incremental_cost_fraction_of_baseline_cost"
        ]
    ) == Decimal("-0.006")


@pytest.mark.parametrize("bad", [None, "NaN", "Infinity", True, "-0.01", "1.01"])
def test_unknown_or_invalid_fraction_never_silently_zero(bad):
    with pytest.raises(ValueError):
        cost_scenario({**values(), "input_cost_share": bad})


def test_incomplete_scenario_rejected():
    v = values()
    del v["reset_share"]
    with pytest.raises(ValueError):
        cost_scenario(v)


@pytest.mark.parametrize("fault", ["formula", "unit", "bounds", "status"])
def test_scenario_configuration_cannot_disagree_with_executor(tmp_path, fault):
    b = load()
    model = b["sensitivity_models"]["COST_SENSITIVITY_V1"]
    if fault == "formula":
        model["formula"] = "price_change"
    elif fault == "unit":
        model["inputs"]["input_cost_share"]["unit"] = "USD"
    elif fault == "bounds":
        model["inputs"]["pass_through"]["max"] = 100
    else:
        model["status"] = "CALIBRATED"
    p = tmp_path / "book.json"
    p.write_text(json.dumps(b))
    with pytest.raises(ValueError):
        load(p)


@pytest.mark.parametrize(
    "interval,expected",
    [
        ((None, None), "UNKNOWN"),
        ((0, 90), "SHORT"),
        ((91, 365), "MEDIUM"),
        ((366, 400), "LONG"),
        ((60, 120), "CROSSES_BANDS"),
    ],
)
def test_editorial_horizon_bins_not_inferred_lags(interval, expected):
    assert horizon_band(*interval) == expected


@pytest.mark.parametrize("interval", [(None, 90), (90, None), (-1, 10), (10, 1), (True, 90)])
def test_invalid_horizon_interval(interval):
    with pytest.raises(ValueError):
        horizon_band(*interval)
