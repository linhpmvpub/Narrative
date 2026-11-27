"""Generic asset/purpose attribution, including near misses and lifecycle parity."""

from datetime import UTC, datetime

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_news_assertions import setup_scope
from test_news_framework import ready as ready
from test_profile_news import get
from test_profile_news import linked as linked

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import AssertionScope, ProfileBundle, withdraw
from engine.news_assertions import applicability
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


def scope(name="Orion", component="MEMORY", event="OWNERSHIP"):
    return AssertionScope(mode="NAMED_OPERATOR", subject_terms=[name], relationship_id="edge",
                          event_types=[event], object_components=[component])


@pytest.mark.parametrize("text,role,phase", [
    ("Orion acquired Aurora's NAND business.", "ACQUIRER", "SOURCE_REPORTED"),
    ("Orion has completed the acquisition of Aurora's memory assets.", "ACQUIRER", "SOURCE_REPORTED"),
    ("Orion closed the first phase of the transaction by acquiring Aurora's SSD business.", "ACQUIRER", "SOURCE_REPORTED"),
    ("Orion plans to acquire a memory factory.", "ACQUIRER", "FORWARD_LOOKING"),
    ("The memory facility was acquired by Orion.", "ACQUIRER", "SOURCE_REPORTED"),
    ("The memory division will be divested by Orion.", "DISPOSER", "FORWARD_LOOKING"),
    ("Orion divested its memory division.", "DISPOSER", "SOURCE_REPORTED"),
])
def test_explicit_transaction_arguments_and_exact_spans(text, role, phase):
    result = applicability(scope(), text)
    assert result["allowed"] and result["assertion"]["phase"] == phase
    a = result["object_argument"]
    assert a["party_role"] == role and a["financial_impact"] == a["operational_outcome"] == "UNKNOWN"
    for key in ["subject_span", "predicate_span", "object_span", "component_span"]:
        s = a[key]
        assert text[s["start"]:s["end"]] == s["text"]
    assert not a["identity_verified"]


@pytest.mark.parametrize("text", [
    "Aurora acquired Orion's memory business.",
    "Orion was acquired by Aurora for its memory business.",
    "Orion acquired software assets for memory production.",
    "Orion acquired software assets and Aurora develops memory products.",
    "Orion acquired memory company shares.",
    "Orion acquired an office of a memory business.",
    "Orion could acquire a memory business.",
    "Orion has not acquired a memory business.",
    "Orion said Aurora acquired memory assets.",
    "Orion acquired knowledge about memory.",
    "The memory business was acquired.",
])
def test_ownership_not_recipient_stock_trade_unrelated_asset_or_other_clause(text):
    assert not applicability(scope(), text)["allowed"]


@pytest.mark.parametrize("text", [
    "Orion plans to invest in NAND manufacturing.",
    "Orion funds development of memory products.",
    "Orion raised capital to develop memory products.",
    "Orion issued bonds for construction of a memory plant.",
    "Memory product development was funded by Orion.",
])
def test_explicit_financing_purpose_never_implies_operational_result(text):
    r = applicability(scope(event="FINANCING_PURPOSE"), text)
    assert r["allowed"]
    a = r["object_argument"]
    assert a["party_role"] == "FUNDER" and a["purpose_outcome"] == "UNKNOWN"
    assert text[a["object_span"]["start"]:a["object_span"]["end"]] == a["object_span"]["text"]


@pytest.mark.parametrize("text", [
    "Orion raised capital for general corporate purposes.",
    "Orion raised capital and Aurora plans to develop memory products.",
    "Orion raised capital for schools to develop memory products.",
    "Orion raised capital to develop software for memory manufacturers.",
    "Orion invests in memory company shares.",
    "Orion funded memory debt refinancing.",
    "Orion funds a school with memory product donations.",
    "Orion develops memory products.",
    "Aurora funds memory development for Orion.",
])
def test_financing_without_the_right_explicit_purpose_is_withheld(text):
    assert not applicability(scope(event="FINANCING_PURPOSE"), text)["allowed"]


def test_renamed_actors_and_non_memory_products():
    for name in ["Alpha Devices", "Beta Components"]:
        assert applicability(scope(name, "COOLING"), f"{name} acquired a liquid cooling business.")["allowed"]
        assert not applicability(scope(name, "MEMORY"), f"{name} acquired a liquid cooling business.")["allowed"]


def test_overlong_object_is_not_silently_truncated():
    text = "Orion acquired memory assets " + "additional qualification " * 20
    assert not applicability(scope(), text)["allowed"]


def configured(ready):
    root, data, relation = setup_scope(ready)
    b = data["factor_bindings"][0]
    b.update(kind="SCOPED_ACTIVITY", signal_rule=None, topic_terms=["Orion"],
             context_terms=["memory"], change_terms=["price"])
    b["assertion_scope"] = scope().model_copy(update={"relationship_id": relation["id"]}).model_dump(mode="json")
    return root, data, relation


def test_object_schema_requires_source_support_and_preserves_old_serialization(ready):
    _, data, _ = configured(ready)
    b = data["factor_bindings"][0]
    b["assertion_scope"]["object_components"] = ["COOLING"]
    with pytest.raises(ValueError, match="Object component requires literal source"):
        ProfileBundle.model_validate(data)
    with pytest.raises(ValueError, match="Object events require"):
        AssertionScope(mode="NAMED_OPERATOR", subject_terms=["Orion"],
                       relationship_id="edge", event_types=["OWNERSHIP"])
    old = AssertionScope(mode="NAMED_OPERATOR", subject_terms=["Orion"], relationship_id="edge", event_types=["READINESS"])
    assert "object_components" not in old.model_dump(mode="json")


def test_rss_article_graph_and_withdrawal_share_object_contract(db, ready):
    root, data, relation = configured(ready)
    text = "Orion completed the acquisition of Aurora's memory business."
    bundle = ProfileBundle.model_validate(data)
    seal(root, data)
    ready[2](title="Asset update", summary=text)
    feed = get(db)["items"][0]
    card = next(article_decisions(bundle, bundle.narratives[0], "Asset update", [{"text": text, "source_spans": []}], datetime.now(UTC)))
    assert feed["links"][0]["routing_contract"] == card["matches"][0]["routing_contract"]
    assert all(h["context_only"] for h in card["matches"])
    assert not matches(bundle.factor_bindings[0], {"title": "Orion memory", "summary": "Aurora acquired software assets."})
    relation["valid_until"] = data["available_at"]
    expired = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(expired, expired.narratives[0], {"summary": text}, datetime.now(UTC)))
    withdraw(root)
    assert not get(db)["items"]
