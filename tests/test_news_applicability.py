"""Cross-domain near misses and valid conversion from components/apps to demand."""

import json
from datetime import UTC, datetime

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_profile_news import get
from test_profile_news import linked as linked

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import FactorBinding, ProfileBundle, withdraw
from engine.news_applicability import assess
from engine.profile_news import matches


@pytest.mark.parametrize("title,sentence", [
    ("Memory technical specification", "AI workloads need more memory capacity near compute cores."),
    ("Software library release", "The library shifts simulation tasks onto GPUs."),
    ("New application", "The application enables developers to deploy servers."),
    ("Memory standard", "Operators may deploy new servers."),
    ("Software platform", "The operator did not order new servers."),
    ("Memory technology", "Demand for near-compute memory capacity is increasing."),
    ("Memory technology", "This overview discusses server prices."),
    ("New GPU architecture", "The GPU can accelerate AI computing."),
])
def test_capability_or_component_capacity_is_not_infrastructure_demand(title, sentence):
    result = assess("INFRASTRUCTURE_DEMAND", title, sentence)
    assert not result["allowed"] and result["financial_impact"] == "UNKNOWN"


@pytest.mark.parametrize("title,sentence", [
    ("New memory standard", "The operator ordered 500 servers."),
    ("Application rollout", "Cloud operators installed additional GPU clusters."),
    ("Software growth", "Demand for additional AI compute capacity increased."),
    ("Memory shortages", "AI server OEMs hiking prices by 45%."),
    ("Memory constraints", "Server costs increased."),
    ("Software rollout", "200 servers were deployed."),
    ("GPU rollout", "The partnership will deploy up to 3 gigawatts of new accelerator GPUs."),
])
def test_real_same_sentence_infrastructure_assertion_remains_eligible(title, sentence):
    result = assess("INFRASTRUCTURE_DEMAND", title, sentence)
    assert result["allowed"] and result["bridge"]
    bridge = result["bridge"]
    assert sentence[bridge["start"]:bridge["end"]] == bridge["text"]


def test_unknown_is_not_rejection_and_input_path_is_not_globally_filtered():
    assert assess("INFRASTRUCTURE_DEMAND", "Project update", "A site opens.")["allowed"]
    assert assess("COMPONENT_MARKET", "Memory standard", "Memory capacity grew.")["allowed"]
    assert assess("APPLICATION_SOFTWARE", "Software library", "A library is released.")["allowed"]
    assert not assess("INFRASTRUCTURE_DEMAND", "Library deploys servers", "AI workloads expand.")["allowed"]


def binding(data):
    d = dict(data["factor_bindings"][0])
    d.update(kind="SCOPED_ACTIVITY", narrative_ids=["n"], market_scope="INFRASTRUCTURE_DEMAND")
    return FactorBinding.model_validate(d)


def test_scope_window_and_span_provenance(linked):
    _, data, _, _, _ = linked
    b = binding(data)
    title = "Memory market overview"
    text = "Memory supply for servers improves. The operator ordered 500 servers to secure memory supply."
    hits = matches(b, {"title": title, "summary": text})
    assert hits
    for hit in hits:
        assert text[hit["start"]:hit["end"]] == hit["text"]
        assert hit["applicability"]["basis"] == "EXPLICIT_INFRASTRUCTURE_ASSERTION"
    assert not matches(b, {"title": "Server orders increase", "summary": "Memory supply outlook."})


def test_legacy_hash_and_no_scope_donation(linked):
    _, data, _, _, _ = linked
    old = FactorBinding.model_validate(data["factor_bindings"][0])
    assert "market_scope" not in old.model_dump(mode="json")
    assert matches(old, {"title": "Server memory supply update"})
    assert not matches(binding(data), {"summary": "Server memory supply update.", "context_title": "A new software library"})


def test_source_to_card_scope_and_withdrawal(db, linked):
    root, data, insert, _, _ = linked
    data["factor_bindings"] = [binding(data).model_dump(mode="json")]
    seal(root, data)
    insert(title="Memory specification", summary="Server memory supply roadmap.")
    assert not get(db)["items"]
    insert(title="Memory supply update", summary="Operators ordered 500 servers to address memory supply.")
    card = get(db)["items"][0]
    assert card["links"][0]["matches"][0]["applicability"]["allowed"]
    assert card["delivery"] == "disabled" and card["impact"] == "UNKNOWN"
    withdraw(root)
    assert not get(db)["items"]


def test_market_scope_requires_explicit_target(linked):
    _, data, _, _, _ = linked
    d = json.loads(binding(data).model_dump_json())
    d["narrative_ids"] = []
    with pytest.raises(ValueError, match="explicit narratives"):
        FactorBinding.model_validate(d)


def test_full_article_projection_keeps_window_relative_evidence(linked):
    _, data, _, _, _ = linked
    data["factor_bindings"] = [binding(data).model_dump(mode="json")]
    b = ProfileBundle.model_validate(data)
    text = "Memory supply overview. Operators ordered 500 servers to address memory supply."
    rows = list(article_decisions(b, b.narratives[0], "Memory update",
                                 [{"text": text, "source_spans": []}], datetime.now(UTC)))
    assert rows
    for span in rows[0]["matches"]:
        assert text[span["start"]:span["end"]] == span["text"]
        trace = span["applicability"]
        bridge = trace["bridge"]
        assert trace["window_text"][bridge["start"]:bridge["end"]] == bridge["text"]
