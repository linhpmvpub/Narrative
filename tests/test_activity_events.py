"""Synthetic event groups, role ambiguity, provenance and scope regressions."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_profile_news import get
from test_profile_news import linked as linked

from engine.company_profiles import FactorBinding, ProfileBundle, withdraw
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


def rule(market="DATA_CENTER", events=None, **extra):
    now = datetime.now(UTC)
    return FactorBinding.model_validate({
        "id": "activity", "factor_id": "f", "topic_terms": ["activity"],
        "context_terms": ["market"], "kind": "STRUCTURED_ACTIVITY", "narrative_ids": ["n"],
        "activity_rule": {"market": market, "event_types": events or ["FACILITY_PROJECT"], **extra},
        "scope": "Synthetic conditional market relevance, never an order",
        "reviewed_at": now, "review_until": now + timedelta(days=20),
        "evidence": [{"source_id": "s", "quote": "Example supplies processors for Aurora systems."}],
    })


@pytest.mark.parametrize("text,phase", [
    ("An operator plans a new 12 MW data center campus.", "FORWARD_LOOKING"),
    ("A developer announces its first data centre facility.", "SOURCE_REPORTED_ACTIVITY"),
    ("Developers invest in a 15MW data center development.", "SOURCE_REPORTED_ACTIVITY"),
    ("A company seeks an investment partner for a data center project.", "SEEKING_FINANCING"),
])
def test_project_phase_and_original_spans(text, phase):
    spans = matches(rule(events=["FACILITY_PROJECT", "PROJECT_FINANCING"]), {"summary": text})
    assert spans and spans[0]["activity_assertion"]["phase"] == phase
    for span in spans:
        assert text[span["start"]:span["end"]] == span["text"]
    activity = assess({"headline": "Update", "excerpt": text}, [{"matches": spans}],
                      json.loads(POLICY.read_text(encoding="utf-8")))
    assert activity["tier"] == "SECTOR_CHANGE_CONTEXT"
    assert activity["signals"][0]["driver_direction"] == "UNKNOWN"
    assert activity["direction"] == activity["horizon"] == "UNKNOWN"


@pytest.mark.parametrize("text", [
    "An operator did not build a new data center facility.",
    "An operator cancelled construction of a data center campus.",
    "Rumors suggest an operator plans a new data center campus.",
    "An operator could build a new data center facility.",
    "Data center demand is strong. An operator builds a school.",
    "Data center market overview and long term potential.",
    "A company announces data center quarterly earnings.",
    "The government proposes new rules for large data centers.",
])
def test_nonassertions_do_not_create_project(text):
    assert not matches(rule(), {"summary": text})


def test_operator_is_not_hardware_vendor():
    binding = rule("AI_COMPUTE", ["COMPUTE_DEPLOYMENT"], vendor_names=["Example"])
    text = "800 GPUs deployed by Acme Cloud for Blue Labs."
    spans = matches(binding, {"summary": text})
    assert spans[0]["activity_assertion"]["vendor_scope"] == "UNSPECIFIED"
    assert spans[0]["activity_assertion"]["company_order_verified"] is False
    assert not matches(binding, {"summary": "New AI infrastructure deployed, built with Rival GPUs."})
    assert matches(binding, {"summary": "New AI infrastructure deployed, built with Example GPUs."})
    assert not matches(binding, {"summary": "Rival supports national AI infrastructure ambitions."})
    spans = matches(binding, {"summary": "A cloud operator to deploy 1000 GPUs at a data center."})
    assert spans[0]["activity_assertion"]["phase"] == "FORWARD_LOOKING"


def test_product_integration_requires_sourced_product_not_generic_ai():
    binding = rule("NAMED_PRODUCT", ["PRODUCT_INTEGRATION"], product_terms=["Aurora"])
    assert matches(binding, {"summary": "New technology will complement Aurora systems."})
    assert not matches(binding, {"summary": "New technology will complement AI infrastructure."})
    with pytest.raises(ValueError, match="literal source evidence"):
        rule("NAMED_PRODUCT", ["PRODUCT_INTEGRATION"], product_terms=["Unsourced"])
    with pytest.raises(ValueError, match="outside market scope"):
        rule("DATA_CENTER", ["PRODUCT_INTEGRATION"])


def test_legacy_serialization_stays_identical(linked):
    _, data, _, _, _ = linked
    old = FactorBinding.model_validate(data["factor_bindings"][0]).model_dump(mode="json")
    assert "activity_rule" not in old
    assert FactorBinding.model_validate(old).model_dump(mode="json") == old


def test_rss_and_shared_routing_use_same_source_bound_rule(db, linked):
    root, data, insert, _, _ = linked
    binding = rule().model_dump(mode="json")
    binding.update(reviewed_at=data["available_at"], evidence=data["relationships"][0]["evidence"])
    data["factor_bindings"] = [binding]
    seal(root, data)
    text = "An operator plans a new 12 MW data center campus."
    insert(title="Project update", summary=text)
    card = get(db)["items"][0]
    bundle = ProfileBundle.model_validate(data)
    decision = next(binding_decisions(bundle, bundle.narratives[0], {"summary": text}, datetime.now(UTC)))
    assert card["links"][0]["matches"] == decision["matches"]
    assert card["delivery"] == "disabled" and card["impact"] == "UNKNOWN"
    withdraw(root)
    assert not get(db)["items"]
