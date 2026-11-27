"""Generic source-actor grammar, including patient/recipient counterexamples."""

import pytest
from test_company_profiles import dossier as dossier
from test_news_assertions import setup_scope
from test_news_framework import ready as ready
from test_profile_news import linked as linked

from engine.company_profiles import AssertionScope, ProfileBundle
from engine.news_assertions import applicability
from engine.profile_news import matches


def rule(names=None):
    return AssertionScope(mode="NAMED_OPERATOR", subject_terms=names or ["Orion", "Aurora"],
                          relationship_id="edge", event_types=["READINESS", "PRODUCTION", "CAPACITY", "FINANCING", "AGREEMENT"])


@pytest.mark.parametrize("text,voice,phase", [
    ("Orion and Aurora to invest in memory manufacturing.", "ACTIVE", "FORWARD_LOOKING"),
    ("Orion and Aurora have jointly developed server memory.", "ACTIVE", "SOURCE_REPORTED"),
    ("Orion today demonstrated server memory.", "ACTIVE", "SOURCE_REPORTED"),
    ("Orion plans to expand memory capacity.", "ACTIVE", "FORWARD_LOOKING"),
    ("Memory production was expanded by Orion.", "PASSIVE", "SOURCE_REPORTED"),
    ("Memory production will be expanded by Aurora.", "PASSIVE", "FORWARD_LOOKING"),
    ("OtherVendor ships components and Orion ships server memory.", "ACTIVE", "SOURCE_REPORTED"),
])
def test_plans_joint_predicates_and_explicit_passive_agents(text, voice, phase):
    a = applicability(rule(), text)
    assert a["allowed"] and a["voice"] == voice and a["assertion"]["phase"] == phase
    for span in [a["subject_span"], a["predicate_span"]]:
        assert text[span["start"]:span["end"]] == span["text"]
    assert a["financial_impact"] == "UNKNOWN" and not a["news_party_verified"]


@pytest.mark.parametrize("text", [
    "Orion was supplied by OtherVendor with server memory.",
    "OtherVendor ships server memory to Orion.",
    "Memory production was expanded for Orion.",
    "The supplier of Orion ships server memory.",
    "A partnership with Orion expands server memory capacity.",
    "Orion expects OtherVendor to expand server memory capacity.",
    "Orion has not expanded server memory capacity.",
    "Server memory production was expanded.",
])
def test_patient_recipient_reporter_and_unknown_agent_are_withheld(text):
    assert not applicability(rule(), text)["allowed"]


def test_typed_predicate_replaces_duplicate_legacy_verb_gate(ready):
    _, data, _ = setup_scope(ready)
    b = data["factor_bindings"][0]
    b.update(kind="SCOPED_ACTIVITY", topic_terms=["Orion"], context_terms=["memory"],
             change_terms=["price"], signal_rule=None)
    binding = ProfileBundle.model_validate(data).factor_bindings[0]
    hits = matches(binding, {"summary": "Orion today demonstrated server memory."})
    assert hits and hits[0]["assertion_scope"]["predicate_span"]["text"] == "demonstrated"
    assert not matches(binding, {"summary": "Orion today demonstrated software."})
    assert not matches(binding, {"title": "Orion memory", "summary": "OtherVendor demonstrated memory."})


def test_names_are_only_profile_data():
    for name in ["Alpha Devices", "Beta Components"]:
        assert applicability(rule([name]), f"{name} to invest in memory production.")["allowed"]
        assert not applicability(rule([name]), f"OtherVendor ships memory to {name}.")["allowed"]
