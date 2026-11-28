"""Priority selects operating developments, not isolated change vocabulary."""

import json

import pytest
from test_activity_events import rule
from test_core_activity import activity

from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.profile_news import matches


@pytest.mark.parametrize("operator,product", [("Orion", "memory"), ("Cobalt", "cooling")])
@pytest.mark.parametrize("template,selected", [
    ("{o} expands {p} production capacity.", True),
    ("{o} plans to expand {p} production capacity.", True),
    ("{o} raised funds to expand {p} production capacity.", True),
    ("{o} expands its influence across the {p} industry.", False),
    ("{o} will expand its role in the {p} industry.", False),
    ("{p}: A product that uses new methods to increase capacity.", False),
    ("{o} makes {p} products designed to increase capacity.", False),
    ("{o} expands marketing for {p} production capacity.", False),
    ("{o} expands its influence, while {p} production is stable.", False),
    ("{o} reports {p} demand increased.", True),
    ("{o} reports {p} prices fell.", True),
    ("{o} increased investment in {p} manufacturing.", True),
    ("{o} did not expand {p} capacity.", False),
])
def test_reusable_operating_object_contract(operator, product, template, selected):
    text = template.format(o=operator, p=product)
    result = activity(text, {"id": "sourced-entity"})
    assert bool(result["signals"]) == selected
    assert result["direction"] == result["horizon"] == "UNKNOWN"
    for signal in result["signals"]:
        evidence = signal["operating_development"]
        for key in ("action_span", "object_span", "purpose_action_span"):
            if key in evidence:
                s = evidence[key]
                assert evidence["source_window"]["text"][s["start"]:s["end"]] == s["text"]
        assert evidence["identity_verified"] is False
        assert evidence["financial_impact"] == "UNKNOWN"


def test_funding_purpose_and_plan_are_not_realized_capacity():
    result = activity("Orion raised capital to expand cooling capacity.")
    signal = result["signals"][0]
    assert signal["event_type"] == "CAPITAL_ALLOCATION"
    assert signal["phase"] == "FORWARD_LOOKING"
    assert signal["driver_direction"] == "UNKNOWN"
    assert signal["operating_development"]["action_span"]["text"] == "raised"
    assert signal["operating_development"]["purpose_action_span"]["text"] == "expand"
    plan = activity("Orion plans to expand cooling capacity.")["signals"][0]
    assert plan["phase"] == "FORWARD_LOOKING"


@pytest.mark.parametrize("text,selected", [
    ("Orion deployed 120 GPUs for a new AI compute cluster.", True),
    ("Orion plans to deploy GPUs for AI compute.", True),
    ("AI compute servers were deployed by Orion.", True),
    ("1,200 GPUs deployed by Orion for Cobalt's AI compute.", True),
    ("Orion to deploy up to 2 gigawatts of GPUs for AI compute.", True),
    ("Orion showcased a prototype installed inside an AI compute server.", False),
    ("Orion demonstrated GPUs deployed inside an AI compute testbed.", False),
    ("Orion has a device designed to deploy GPUs for AI compute.", False),
])
def test_demonstration_is_not_operational_deployment(text, selected):
    spans = matches(rule("AI_COMPUTE", ["COMPUTE_DEPLOYMENT"]), {"summary": text})
    assert spans  # Relevance is preserved even when editorial priority is withheld.
    result = assess({"headline": "Update", "excerpt": text}, [{"matches": spans}],
                    json.loads(POLICY.read_text(encoding="utf-8")))
    assert bool(result["signals"]) == selected
    assert result["direction"] == result["horizon"] == "UNKNOWN"


def test_project_apposition_does_not_cross_an_independent_clause():
    binding = rule(events=["FACILITY_PROJECT"])
    for text, selected in [
        ("Orion announces North, its first data center in the region.", True),
        ("Orion announces a guide, while Cobalt operates a data center facility.", False),
    ]:
        spans = matches(binding, {"summary": text})
        assert spans
        r = assess({"headline": "Update", "excerpt": text}, [{"matches": spans}],
                   json.loads(POLICY.read_text(encoding="utf-8")))
        assert bool(r["signals"]) == selected


def test_entity_bonus_cannot_be_borrowed_from_another_link():
    item = {"headline": "Orion overview", "excerpt": "Cooling demand increased."}
    unrelated = {"entity_context": {"id": "sourced-entity"},
                 "matches": [{"field": "title", "start": 0, "end": 5}]}
    change = {"matches": [{"field": "summary", "start": 0, "end": 7}]}
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    result = assess(item, [unrelated, change], policy)
    assert result["resolved_entity"] is True
    assert result["event_entity_resolved"] is False
    assert result["tier"] == "SECTOR_CHANGE_CONTEXT"
    assert result["editorial_score"] == 50
    change["entity_context"] = {"id": "sourced-entity"}
    assert assess(item, [unrelated, change], policy)["editorial_score"] == 90


def test_without_graph_link_no_priority_even_for_explicit_change():
    result = assess({"headline": "Orion expands cooling production", "excerpt": ""}, [],
                    json.loads(POLICY.read_text(encoding="utf-8")))
    assert not result["signals"]
    assert result["tier"] == "BACKGROUND_THEME"
