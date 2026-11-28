import hashlib
import json
from datetime import UTC, datetime

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_core_activity import activity
from test_profile_news import get
from test_profile_news import linked as linked

from engine.company_profiles import ActivityRule, FactorBinding, ProfileBundle, withdraw
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.market_developments import classify
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


@pytest.mark.parametrize("name", ["Orion", "Cobalt"])
@pytest.mark.parametrize("sentence,phase", [
    ("{name} pitches underwater data centers powered by offshore wind.", "FORWARD_LOOKING"),
    ("{name} plans an orbital AI compute test.", "EXPERIMENTAL_PLAN"),
    ("{name} launches a pilot data center.", "EXPERIMENTAL_ACTIVITY"),
    ("{name} files to build two data center buildings at a new site.", "FORWARD_LOOKING"),
    ("{name} opens a new data center.", "SOURCE_REPORTED_ACTIVITY"),
    ("{name} is a growing data center operator.", "BACKGROUND"),
])
def test_source_phases_without_company_order_inference(name, sentence, phase):
    text = sentence.format(name=name)
    d = classify(text)
    assert d and d["phase"] == phase
    assert d["editorial_eligible"] == (phase != "BACKGROUND")
    assert d["financial_impact"] == "UNKNOWN" and not d["company_order_verified"]
    for key in ["action_span", "object_span"]:
        if key in d:
            s = d[key]
            assert text[s["start"]:s["end"]] == s["text"]


@pytest.mark.parametrize("text", [
    "Orion proposes new rules for data centers.",
    "Orion opens a school for data center operators.",
    "Orion showcases GPUs installed inside a data center server.",
    "Orion did not plan a new data center.",
    "Orion could build a data center.",
    "Orion plans a hospital while data centers remain unchanged.",
    "An overview of plans for data center operators.",
    "Orion launches application software for data centers.",
    "Data center stocks rise after a company launches a product.",
    "Orion expands its influence across the AI infrastructure landscape.",
    "Orion will expand its role in AI infrastructure.",
    "Building monitoring switches in data centers.",
    "An alliance is helping expand AI infrastructure.",
    "Orion plans to support AI infrastructure.",
    "An initiative supports national priorities to build AI infrastructure.",
    "A vision to deploy AI compute systems.",
])
def test_wrong_object_uncertain_and_demo_do_not_create_development(text):
    assert classify(text) is None


def setup(linked):
    root, data, _, _, _ = linked
    quote = "Our server business depends on customers expanding data centers."
    p = root / "source.html"
    raw = p.read_bytes() + ("<p>" + quote + "</p>").encode()
    p.write_bytes(raw)
    data["sources"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    b = data["factor_bindings"][0]
    b.update(kind="STRUCTURED_ACTIVITY", change_terms=[], narrative_ids=["n"],
             activity_rule={"version": "activity-assertions-v2", "market": "DATA_CENTER",
                            "event_types": ["INFRASTRUCTURE_DEVELOPMENT"]},
             evidence=[{"source_id": "s", "quote": quote}])
    data["routing_policies"] = [{"narrative_id": "n", "intents": ["DEPLOYMENT"], "scope_note": "Sourced server-market context"}]
    return root, data


def test_route_and_lifecycle_requirements_and_renamed_profiles(db, linked):
    root, data = setup(linked)
    text = "An operator plans an orbital AI compute test."
    outputs = []
    for name in ["Orion", "Cobalt"]:
        data.update(ticker=name.upper(), legal_name=name)
        b = ProfileBundle.model_validate(data)
        routed = list(binding_decisions(b, b.narratives[0], {"summary": text}, datetime.now(UTC)))
        assert routed
        outputs.append(routed[0]["matches"])
    assert outputs[0] == outputs[1]
    seal(root, data)
    linked[2](title="Infrastructure update", summary=text)
    card = get(db)["items"][0]
    a = assess({"headline": card["headline"], "excerpt": card["excerpt"]}, card["links"], json.loads(POLICY.read_text(encoding="utf-8")))
    assert a["signals"][0]["phase"] == "EXPERIMENTAL_PLAN"
    assert a["direction"] == a["horizon"] == "UNKNOWN"
    assert card["delivery"] == "disabled"
    data["routing_policies"][0]["intents"] = ["COMPETITION"]
    b = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b, b.narratives[0], {"summary": text}, datetime.now(UTC)))
    data["routing_policies"][0]["intents"] = ["DEPLOYMENT"]
    for e in data["relationships"]:
        e["valid_until"] = data["available_at"]
    b = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b, b.narratives[0], {"summary": text}, datetime.now(UTC)))
    withdraw(root)
    assert not get(db)["items"]


def test_no_cross_field_donation_or_unsupported_market_evidence(linked):
    _, data = setup(linked)
    b = FactorBinding.model_validate(data["factor_bindings"][0])
    assert not matches(b, {"title": "AI compute", "summary": "An operator plans a new school."})
    b = b.model_dump(mode="json")
    b["evidence"] = [{"source_id": "s", "quote": "We manufacture cooling components."}]
    with pytest.raises(ValueError, match="literal source evidence"):
        FactorBinding.model_validate(b)
    with pytest.raises(ValueError, match="outside market scope"):
        ActivityRule(market="DATA_CENTER", event_types=["INFRASTRUCTURE_DEVELOPMENT"])


@pytest.mark.parametrize("name,resource", [("Orion", "minerals"), ("Cobalt", "chemicals")])
def test_financing_input_access_and_contracts_are_source_claims(name, resource):
    for text, event in [
        (f"{name} invests in {resource} processing.", "INPUT_FINANCING_PURPOSE"),
        (f"{name} expands access to critical {resource} for manufacturing.", "SUPPLY_ACCESS"),
        (f"{name} has completed strategic customer agreements for material supply.", "CUSTOMER_AGREEMENT"),
    ]:
        r = activity(text)
        s = r["signals"][0]
        assert s["event_type"] == event
        assert s["driver_direction"] == r["direction"] == r["horizon"] == "UNKNOWN"
        assert s["operating_development"]["contract_terms"] == "NOT_INFERRED"


@pytest.mark.parametrize("text", [
    "Orion invests in shares of a minerals processing company.",
    "Orion invests in scholarships while minerals processing continues.",
    "Orion announces a conference about customer agreements.",
    "Orion completed a guide to supply agreements.",
    "Orion did not sign customer agreements.",
    "Existing customer agreements provide visibility into production.",
])
def test_generic_finance_and_descriptions_do_not_become_contract_events(text):
    assert not activity(text)["signals"]
