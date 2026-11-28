"""Editorial selection is separate from relevance, identity and financial effect."""

import copy
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_news_assertions import setup_scope
from test_news_framework import ready as ready
from test_profile_news import linked as linked

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import AssertionScope, ProfileBundle, available_bundles, withdraw
from engine.core_activity import assess
from engine.core_decisions import POLICY, feed
from engine.ingestion.contracts import digest
from engine.models.schema_v13 import news_sources
from engine.news_assertions import applicability
from engine.profile_routing import binding_decisions


def scoped_result(text, name="Orion", component="MEMORY", event="READINESS",
                  phase=None, role="COMPETITION_CONTEXT", intents=None):
    scope = AssertionScope(mode="NAMED_OPERATOR", subject_terms=[name], relationship_id="edge",
                           event_types=[event], object_components=[component] if event in {"OWNERSHIP", "FINANCING_PURPOSE"} else [])
    trace = applicability(scope, text)
    if phase:
        trace["assertion"]["phase"] = phase
    match = {"field": "summary", "start": 0, "end": len(text), "text": text,
             "context_only": True, "assertion_scope": trace,
             "routing_contract": {"allowed": True, "role": role,
                                  "intents": intents if intents is not None else ["COMPETITION"]}}
    item = {"headline": "Source update", "excerpt": text}
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    return assess(item, [{"matches": [match]}], policy)


@pytest.mark.parametrize("name,product,component", [("Orion", "memory", "MEMORY"), ("Aurora", "liquid cooling", "COOLING")])
@pytest.mark.parametrize("template,event,phase", [
    ("{name} unveils new {product} products", "READINESS", "SOURCE_REPORTED"),
    ("{name} plans to expand {product} capacity", "CAPACITY", "FORWARD_LOOKING"),
    ("{name} ships {product} samples", "PRODUCTION", "SOURCE_REPORTED"),
    ("{name} acquired a {product} business", "OWNERSHIP", "SOURCE_REPORTED"),
    ("{name} raised capital to develop {product} products", "FINANCING_PURPOSE", "SOURCE_REPORTED"),
])
def test_scoped_event_can_be_priority_while_financial_effect_stays_unknown(name, product, component, template, event, phase):
    text = template.format(name=name, product=product)
    r = scoped_result(text, name, component, event)
    assert r["tier"] == "SECTOR_CHANGE_CONTEXT"
    assert r["editorial_decisions"][0]["eligible"]
    assert r["signals"][0]["event_type"] == event
    assert r["signals"][0]["phase"] == phase
    assert r["signals"][0]["text"] == text
    assert r["direction"] == r["horizon"] == r["signals"][0]["driver_direction"] == "UNKNOWN"


@pytest.mark.parametrize("text,event,reason", [
    ("Orion unveiled new memory products last year", "READINESS", "RETROSPECTIVE_SOURCE_WINDOW"),
    ("Orion produces server memory", "PRODUCTION", "ONGOING_OPERATION_WITHOUT_CHANGE"),
    ("Orion builds memory boards", "CAPACITY", "CAPACITY_OBJECT_REQUIRED"),
    ("Orion invests in memory products", "FINANCING", "CONCRETE_EVENT_ARGUMENT_REQUIRED"),
    ("Orion unveils a guide to server memory", "READINESS", "ROUTINE_SOURCE_WINDOW"),
    ("Orion might unveil memory products", "READINESS", "SOURCE_SCOPE_REQUIRED"),
    ("OtherVendor unveils memory products for Orion", "READINESS", "SOURCE_SCOPE_REQUIRED"),
])
def test_context_is_retained_without_blanket_promotion(text, event, reason):
    r = scoped_result(text, event=event)
    assert r["tier"] == "BACKGROUND_THEME" and not r["signals"]
    assert r["editorial_decisions"][0]["reason"] == reason


def test_route_phase_and_source_window_are_required():
    text = "Orion unveils new memory products"
    assert scoped_result(text, intents=["SUPPLY"])["tier"] == "BACKGROUND_THEME"
    assert scoped_result(text, phase="UNKNOWN")["tier"] == "BACKGROUND_THEME"
    assert scoped_result(text, role="INPUT_READINESS_CONTEXT", intents=["SUPPLY"])["tier"] == "SECTOR_CHANGE_CONTEXT"


def test_entity_mention_is_not_an_event_and_cannot_outrank_one():
    p = json.loads(POLICY.read_text(encoding="utf-8"))
    text = "An overview of server memory"
    link = {"entity_context": {"node_id": "supplier"}, "matches": [
        {"field": "summary", "start": 0, "end": len(text)}]}
    r = assess({"headline": "Update", "excerpt": text}, [link], p)
    assert r["resolved_entity"] and r["tier"] == "BACKGROUND_THEME"
    assert r["editorial_score"] < scoped_result("Orion unveils memory products")["editorial_score"]


def test_named_platform_is_not_a_verified_operator():
    scope = AssertionScope(mode="NAMED_PLATFORM_OR_MARKET_CONSTRAINT", subject_terms=["Atlas"],
                           relationship_id="edge", event_types=["READINESS"])
    text = "UnknownVendor unveils server memory for Atlas"
    trace = applicability(scope, text)
    hit = {"field": "summary", "start": 0, "end": len(text), "context_only": True,
           "assertion_scope": trace, "routing_contract": {"allowed": True,
           "role": "INPUT_READINESS_CONTEXT", "intents": ["SUPPLY"]}}
    r = assess({"headline": "Update", "excerpt": text}, [{"matches": [hit]}], json.loads(POLICY.read_text(encoding="utf-8")))
    assert r["tier"] == "BACKGROUND_THEME"
    assert not r["editorial_decisions"][0]["eligible"]


@pytest.mark.parametrize("text,eligible", [
    ("Global server memory shortages constrain deployments", True),
    ("Global server memory markets face higher prices", False),
    ("Global server memory markets face price increases of 1%", False),
])
def test_shared_market_constraints_do_not_bypass_commodity_price_comparison(text, eligible):
    scope = AssertionScope(mode="NAMED_PLATFORM_OR_MARKET_CONSTRAINT", subject_terms=["Atlas"],
                           relationship_id="edge", event_types=["CONSTRAINT"])
    trace = applicability(scope, text)
    assert trace["allowed"]
    hit = {"field": "summary", "start": 0, "end": len(text), "context_only": True,
           "assertion_scope": trace, "routing_contract": {"allowed": True,
           "role": "INPUT_MARKET_CONTEXT", "intents": ["SUPPLY"]}}
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    r = assess({"headline": "Update", "excerpt": text}, [{"matches": [hit]}], policy)
    assert r["editorial_decisions"][0]["eligible"] == eligible
    if not eligible:
        assert r["editorial_decisions"][0]["reason"] == "PRICE_COMPARISON_THRESHOLD_REQUIRED"
    hit["routing_contract"].update(role="COMPETITION_CONTEXT", intents=["COMPETITION"])
    assert assess({"headline": "Update", "excerpt": text}, [{"matches": [hit]}], policy)["tier"] == "BACKGROUND_THEME"


def test_live_rss_article_and_reviewer_use_the_same_priority_contract(db, ready):
    root, data, relation = setup_scope(ready)
    seal(root, data)
    bundle = ProfileBundle.model_validate(data)
    text = "Orion introduces server memory samples"
    ready[2](title="Component update", summary=text)
    with db.begin() as conn:
        conn.execute(update(news_sources).values(last_success=datetime.now(UTC)))
    pinned = {"profiles": [{"id": b.id, "sha256": digest(b.model_dump(mode="json"))} for b in available_bundles()["items"]]}
    with db.connect() as conn:
        live = feed(conn, pinned, root.parent)
    assert live["items"]
    card = live["items"][0]
    assert card["assessment"]["editorial_decisions"][0]["eligible"]
    assert card["financial_magnitude"] == "UNKNOWN" and card["delivery"] == "disabled"
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    routed = list(binding_decisions(bundle, bundle.narratives[0], {"summary": text}, datetime.now(UTC)))
    archive = list(article_decisions(bundle, bundle.narratives[0], "Update", [{"text": text, "source_spans": []}], datetime.now(UTC)))
    assert archive and routed
    evaluated = assess({"headline": "Update", "excerpt": text}, [{"matches": routed[0]["matches"]}], policy)
    assert evaluated["tier"] == card["priority"]
    bad = copy.deepcopy(routed[0]["matches"])
    for m in bad:
        m["assertion_scope"]["assertion"]["text"] = "Invented source assertion"
    assert not assess({"headline": "Update", "excerpt": text}, [{"matches": bad}], policy)["signals"]
    with db.begin() as conn:
        conn.execute(update(news_sources).values(last_success=datetime.now(UTC) - timedelta(hours=2)))
    with db.connect() as conn:
        assert not feed(conn, pinned, root.parent)["items"]
    relation["valid_until"] = data["available_at"]
    expired = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(expired, expired.narratives[0], {"summary": text}, datetime.now(UTC)))
    withdraw(root)
    with db.connect() as conn:
        assert not feed(conn, pinned, root.parent)["items"]
