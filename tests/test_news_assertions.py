"""Scope is sourced data shared across companies, not a headline exception."""

import hashlib
from datetime import UTC, datetime

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_news_framework import framework
from test_news_framework import ready as ready
from test_profile_news import get
from test_profile_news import linked as linked

from engine.company_profiles import AssertionScope, ProfileBundle, withdraw
from engine.news_assertions import applicability, frame
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


def scope(mode="NAMED_OPERATOR", subject="Orion", relationship="r1"):
    return AssertionScope(mode=mode, subject_terms=[subject], relationship_id=relationship,
                          event_types=["READINESS", "PRODUCTION", "CAPACITY", "CONSTRAINT"])


@pytest.mark.parametrize("text,allowed", [
    ("Orion ships server memory samples.", True),
    ("Orion has recently expanded memory capacity.", True),
    ("Orion plans to expand memory capacity.", True),
    ("OtherVendor ships memory for Orion.", False),
    ("Orion discusses OtherVendor which ships server memory.", False),
    ("A partnership with Orion expands server memory production.", False),
    ("Orion has not shipped memory samples.", False),
    ("Orion might launch new server memory.", False),
])
def test_named_operator_is_not_a_customer_or_comparison(text, allowed):
    assert applicability(scope(), text)["allowed"] == allowed


@pytest.mark.parametrize("text,allowed", [
    ("Orion and Aurora will invest in a new memory factory.", True),
    ("Orion and Aurora extended their memory manufacturing agreement.", True),
    ("Orion and UnknownVendor extended their memory manufacturing agreement.", False),
    ("UnknownVendor extended its agreement with Orion and Aurora.", False),
    ("Orion and Aurora have not signed the new agreement.", False),
])
def test_joint_subjects_need_sourced_names_and_matching_predicate(text, allowed):
    rule = AssertionScope(mode="NAMED_OPERATOR", subject_terms=["Orion", "Aurora"],
                          relationship_id="r1", event_types=["FINANCING", "AGREEMENT"])
    assert applicability(rule, text)["allowed"] == allowed


@pytest.mark.parametrize("text,allowed", [
    ("A vendor ships server memory for Atlas.", True),
    ("A vendor ships server memory for AnotherPlatform.", False),
    ("Global server memory shortages constrain deployments.", True),
    ("Server memory shortages affect one operator.", False),
    ("Global smartphone memory shortages continue.", False),
    ("Atlas is discussed but AnotherPlatform ships server memory.", False),
])
def test_platform_or_explicit_industry_constraint(text, allowed):
    assert applicability(scope("NAMED_PLATFORM_OR_MARKET_CONSTRAINT", "Atlas"), text)["allowed"] == allowed


def setup_scope(ready, subject="Orion"):
    root, data, _, _, _ = ready
    framework(data)
    quote = f"{subject} supplies server memory components for Atlas computing systems."
    path = root / "source.html"
    raw = path.read_bytes() + ("<p>" + quote + "</p>").encode()
    path.write_bytes(raw)
    data["sources"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    b = data["factor_bindings"][0]
    b["evidence"].append({"source_id": "s", "quote": quote})
    relation = next(r for r in data["relationships"] if r["from_id"] == b["factor_id"])
    b["assertion_scope"] = scope(subject=subject, relationship=relation["id"]).model_dump(mode="json")
    b["signal_rule"]["event_types"] = ["READINESS", "PRODUCTION"]
    return root, data, relation


def test_renamed_company_scope_and_later_eligible_window(ready):
    for name in ["Orion", "Aurora"]:
        _, data, _ = setup_scope(ready, name)
        b = ProfileBundle.model_validate(data).factor_bindings[0]
        text = f"OtherVendor ships server memory. {name} ships server memory samples."
        hits = matches(b, {"summary": text})
        assert hits and hits[0]["assertion_scope"]["reason"] == "NAMED_OPERATOR_ACTIVITY"
        assert all(text[h["start"]:h["end"]] == h["text"] for h in hits)
        assert not matches(b, {"title": name, "summary": "OtherVendor ships server memory."})
        assert not matches(b, {"summary": f"{name} ships sensors but OtherVendor ships server memory."})


def test_evidence_and_graph_reference_required(ready):
    _, data, _ = setup_scope(ready)
    data["factor_bindings"][0]["assertion_scope"]["subject_terms"] = ["Invented"]
    with pytest.raises(ValueError, match="literal source evidence"):
        ProfileBundle.model_validate(data)
    data["factor_bindings"][0]["assertion_scope"]["subject_terms"] = ["Orion"]
    data["factor_bindings"][0]["assertion_scope"]["relationship_id"] = "missing"
    with pytest.raises(ValueError, match="sourced incident"):
        ProfileBundle.model_validate(data)


def test_scoped_rss_fullbody_parity_and_withdrawal(db, ready):
    root, data, _ = setup_scope(ready)
    b = ProfileBundle.model_validate(data)
    seal(root, data)
    ready[2](title="Component update", summary="Orion ships server memory samples.")
    card = get(db)["items"][0]
    rows = list(binding_decisions(b, b.narratives[0],
                {"summary": "Orion ships server memory samples."}, datetime.now(UTC)))
    assert rows[0]["matches"][0]["routing_contract"] == card["links"][0]["routing_contract"]
    assert card["links"][0]["routing_contract"]["assertion_scope"]["news_party_verified"] is False
    withdraw(root)
    assert not get(db)["items"]


def test_scoped_path_expiry_is_not_bypassed(ready):
    _, data, relation = setup_scope(ready)
    relation["valid_until"] = data["available_at"]
    b = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b, b.narratives[0],
                    {"summary": "Orion ships server memory samples."}, datetime.now(UTC)))


def test_assertion_phase_and_unknowns_do_not_invent_financial_effect():
    for text, phase in [("Orion will ship memory samples.", "FORWARD_LOOKING"),
                        ("Orion previously shipped memory.", "RETROSPECTIVE"),
                        ("Orion ships memory.", "SOURCE_REPORTED")]:
        f = frame(text)
        assert f["phase"] == phase
        assert f["actor"] == f["recipient"] == f["financial_impact"] == "UNKNOWN"


def test_market_constraint_is_not_described_as_product_readiness(ready):
    _, data, _ = setup_scope(ready)
    rule = data["factor_bindings"][0]
    rule["assertion_scope"]["mode"] = "NAMED_PLATFORM_OR_MARKET_CONSTRAINT"
    rule["assertion_scope"]["subject_terms"] = ["Atlas"]
    rule["signal_rule"]["event_types"] = ["CONSTRAINT"]
    b = ProfileBundle.model_validate(data)
    rows = list(binding_decisions(b, b.narratives[0],
                {"summary": "Global server memory shortages constrain deployments."}, datetime.now(UTC)))
    h = rows[0]["matches"][0]
    assert h["signal_classification"]["event_type"] == "COMPONENT_CONSTRAINT"
    assert h["routing_contract"]["role"] == "INPUT_MARKET_CONTEXT"


def test_legacy_optional_fields_do_not_change_profile_digest(ready):
    b = ProfileBundle.model_validate(framework(ready[1]))
    d = b.model_dump(mode="json")
    assert "assertion_scope" not in d["factor_bindings"][0]
    assert "event_types" not in d["factor_bindings"][0]["signal_rule"]
