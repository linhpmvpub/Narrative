"""Reusable issuer contracts: literal subjects, events and bounded objects."""

import pytest

from engine.company_assessment import assess
from engine.company_discovery import issuer_matches


@pytest.mark.parametrize("name", ["Fjord", "Cedar Devices"])
@pytest.mark.parametrize("tail,family,phase", [
    (" reports quarterly revenue increased 12%", "FINANCIAL_PERFORMANCE", "SOURCE_REPORTED"),
    (" sees sales nearly triple", "FINANCIAL_PERFORMANCE", "SOURCE_REPORTED"),
    ("'s net income fell 9%", "FINANCIAL_PERFORMANCE", "SOURCE_REPORTED"),
    (" operating margin declined", "FINANCIAL_PERFORMANCE", "SOURCE_REPORTED"),
    (" halts server shipments to several markets", "SHIPMENT_CHANGE", "SOURCE_REPORTED"),
    (" resumed its chip deliveries", "SHIPMENT_CHANGE", "SOURCE_REPORTED"),
    (" will suspend wafer exports", "SHIPMENT_CHANGE", "FORWARD_LOOKING"),
    (" expands its manufacturing capacity", "CAPACITY_CHANGE", "SOURCE_REPORTED"),
    (" plans to build a new semiconductor factory", "CAPACITY_CHANGE", "FORWARD_LOOKING"),
    (" to close its packaging plant", "CAPACITY_CHANGE", "FORWARD_LOOKING"),
])
def test_named_subject_event_object_and_original_offsets(name, tail, family, phase):
    text = "Source: " + name + tail + "."
    found = list(issuer_matches([name], {"summary": text}))
    assert len(found) == 1
    match = found[0]
    assert match["event_family"] == family
    event = match["issuer_event"]
    assert event["phase"] == phase
    for span in [match, event["actor"], event["predicate"], event["object"], event["source_window"]]:
        assert text[span["start"]:span["end"]] == span["text"]
    assert event["actor"]["text"] == name
    assert event["financial_effect"] == "UNKNOWN" and event["delivery"] == "disabled"


@pytest.mark.parametrize("text", [
    "Fjord shares doubled after Cedar revenue grew",
    "Fjord's stock rose 12%",
    "Fjord reports Cedar sales doubled",
    "Fjord's customer reports revenue doubled",
    "Fjord and Cedar: Cedar halts chip shipments",
    "Fjord says Cedar expands manufacturing capacity",
    "Fjord supplies Cedar, which closes a factory",
    "Fjord halts speculation about shipments",
    "Fjord expands its software capabilities",
    "Fjord doubles memory bandwidth",
    "Fjord could halt chip shipments",
    "Fjord does not halt chip shipments",
    "Fjord plans not to close a factory",
    "If Fjord expands capacity, prices could fall",
    "Whether Fjord closes a plant remains uncertain",
    "How Fjord expands capacity",
    "Fjord halts shipments?",
    "The issuer denies that Fjord halts shipments",
    "Fjord denies that Cedar reports revenue grew",
    "BlueFjord halts shipments",
    "Fjord reports financial results?",
])
def test_no_cross_subject_theme_price_or_unasserted_event(text):
    assert not list(issuer_matches(["Fjord"], {"title": text}))


def test_no_cross_field_join_and_alias_overlap():
    assert not list(issuer_matches(["Fjord"], {"title": "Fjord", "summary": "halts shipments"}))
    text = "Cedar Devices halts shipments. Cedar Devices expands capacity."
    found = list(issuer_matches(["Devices", "Cedar Devices"], {"summary": text}))
    assert len(found) == 2
    assert all(m["issuer_event"]["actor"]["text"] == "Cedar Devices" for m in found)


def test_multiple_independent_events_keep_distinct_evidence():
    text = "Fjord halts chip shipments but Fjord expands manufacturing capacity."
    found = list(issuer_matches(["Fjord"], {"title": text}))
    assert {m["event_family"] for m in found} == {"SHIPMENT_CHANGE", "CAPACITY_CHANGE"}
    assert len(found) == 2


def assessment(text, tamper=False):
    found = list(issuer_matches(["Fjord"], {"summary": text}))
    assert found
    if tamper:
        found[0]["issuer_event"]["source_window"]["text"] = "Altered source sentence"
    discovery = {"kind": "ISSUER_EVENT", "rule_id": "synthetic", "matches": found,
                 "source_unit": {"summary": text}, "path": []}
    return assess({"headline": "Operating bulletin", "excerpt": text}, [discovery])


def test_attention_uses_unchanged_event_sentence_and_preserves_plan():
    result = assessment("A rumor about another sector was denied. Fjord plans to expand manufacturing capacity.")
    assert result["priority"]
    assert result["signals"][0]["phase"] == "FORWARD_LOOKING"
    assert result["direction"] == result["financial_magnitude"] == result["horizon"] == "UNKNOWN"
    assert not result["narratives_used"]


@pytest.mark.parametrize("text", [
    "Rumors suggest Fjord halts chip shipments",
    "Previously, Fjord expanded manufacturing capacity",
    "Fjord halts shipments according to a hypothetical scenario",
])
def test_uncertainty_in_same_sentence_keeps_context_without_attention(text):
    result = assessment(text)
    assert result["relevant"] and not result["priority"]
    assert not result["signals"]


def test_tampered_event_sentence_cannot_create_attention():
    result = assessment("Fjord halts chip shipments", tamper=True)
    assert not result["priority"] and not result["signals"]
    assert result["decisions"][0]["reason"] == "SOURCE_SPAN_MISMATCH"
