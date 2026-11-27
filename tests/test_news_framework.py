"""Generic role/scope contracts must survive renamed companies and source changes."""

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_profile_news import get
from test_profile_news import linked as linked

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import FactorBinding, ProfileBundle, withdraw
from engine.news_framework import classify, eligible_route, route_contract
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


@pytest.fixture
def ready(linked):
    root, data, _, _, _ = linked
    quote = "The synthetic company depends on server memory components for its products."
    path = root / "source.html"
    raw = path.read_bytes() + ("<p>" + quote + "</p>").encode()
    path.write_bytes(raw)
    data["sources"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    data["factor_bindings"][0]["evidence"] = [{"source_id": "s", "quote": quote}]
    return linked


def framework(data):
    d = dict(data["factor_bindings"][0])
    d.update(kind="CLASSIFIED_CONTEXT", signal_rule={"components": ["MEMORY"]},
             change_terms=[], narrative_ids=["n"])
    data["factor_bindings"] = [d]
    data["routing_policies"] = [{"narrative_id": "n", "intents": ["SUPPLY"],
                                 "scope_note": "Synthetic server-input supply context."}]
    return data


@pytest.mark.parametrize("text,expected", [
    ("A manufacturer unveils DDR5 memory for servers.", True),
    ("A supplier ships memory samples for data centers.", True),
    ("Memory is now available for AI inference.", True),
    ("A supplier showcases DDR5 for smartphones.", False),
    ("A supplier could introduce server memory.", False),
    ("A supplier has not launched server memory.", False),
    ("A supplier announces an investor webcast about server memory.", False),
    ("A data center operator ordered servers.", False),
])
def test_source_signal_requires_component_market_and_development(ready, text, expected):
    _, data, _, _, _ = ready
    b = ProfileBundle.model_validate(framework(data))
    hits = matches(b.factor_bindings[0], {"summary": text})
    assert bool(hits) == expected
    for h in hits:
        assert text[h["start"]:h["end"]] == h["text"]
        assert h["context_only"] and not h["news_party_verified"]


def test_no_title_or_cross_sentence_donation(ready):
    _, data, _, _, _ = ready
    b = ProfileBundle.model_validate(framework(data)).factor_bindings[0]
    assert not matches(b, {"title": "Server memory", "summary": "A supplier ships samples."})
    assert not matches(b, {"summary": "A supplier ships memory. Data centers need capacity."})


def test_renamed_companies_receive_identical_signal_and_graph_decisions(ready):
    _, data, _, _, _ = ready
    framework(data)
    outputs = []
    for name in ["Alpha Hardware", "Beta Systems"]:
        data["ticker"], data["legal_name"] = name.split()[0], name
        b = ProfileBundle.model_validate(data)
        output = list(binding_decisions(b, b.narratives[0],
                      {"summary": "A vendor unveils server memory."}, datetime.now(UTC)))
        assert output
        outputs.append(output[0]["matches"])
    assert outputs[0] == outputs[1]


def test_competition_requires_competition_intent_and_valid_alternative_is_not_hidden(ready):
    _, data, _, _, _ = ready
    b = ProfileBundle.model_validate(framework(data))
    n = b.narratives[0]
    rival = [SimpleNamespace(type="COMPETES_WITH")]
    direct = [SimpleNamespace(type="AFFECTS_SUPPLY")]
    assert not route_contract(b, n, rival, []) ["allowed"]
    assert eligible_route(b, n, [rival, direct], [])[0] == direct
    data["routing_policies"][0]["intents"] = ["COMPETITION"]
    b = ProfileBundle.model_validate(data)
    assert route_contract(b, n, rival, [])["role"] == "COMPETITION_CONTEXT"
    assert route_contract(b, n, rival, [])["allowed"]


def test_unknown_component_evidence_and_missing_policy_fail_closed(ready):
    _, data, _, _, _ = ready
    framework(data)
    data["factor_bindings"][0]["signal_rule"]["components"] = ["COOLING"]
    with pytest.raises(ValueError, match="literal source evidence"):
        ProfileBundle.model_validate(data)
    data["factor_bindings"][0]["signal_rule"]["components"] = ["MEMORY"]
    data["routing_policies"] = []
    with pytest.raises(ValueError, match="declared narrative policies"):
        ProfileBundle.model_validate(data)


def test_legacy_serialization_unchanged(ready):
    _, data, _, _, _ = ready
    assert "routing_policies" not in ProfileBundle.model_validate(data).model_dump(mode="json")
    assert "signal_rule" not in FactorBinding.model_validate(data["factor_bindings"][0]).model_dump(mode="json")


def test_rss_full_body_contract_and_withdrawal(db, ready):
    root, data, insert, _, _ = ready
    b = ProfileBundle.model_validate(framework(data))
    seal(root, data)
    insert(title="Component update", summary="A supplier ships server memory samples.")
    card = get(db)["items"][0]
    contract = card["links"][0]["routing_contract"]
    assert contract["role"] == "INPUT_READINESS_CONTEXT" and contract["allowed"]
    rows = list(article_decisions(b, b.narratives[0], "Component update",
                [{"text": "A supplier ships server memory samples.", "source_spans": []}], datetime.now(UTC)))
    assert rows[0]["matches"][0]["routing_contract"] == contract
    assert card["delivery"] == "disabled" and card["impact"] == "UNKNOWN"
    withdraw(root)
    assert not get(db)["items"]


def test_expired_dependency_cannot_be_replaced_by_signal(ready):
    _, data, _, _, _ = ready
    framework(data)
    for r in data["relationships"]:
        r["valid_until"] = data["available_at"]
    b = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b, b.narratives[0],
                    {"summary": "A supplier ships server memory samples."}, datetime.now(UTC)))


def test_classification_has_no_issuer_input():
    result = classify("A manufacturer launches liquid cooling for data centers.")
    assert result["event_type"] == "COMPONENT_READINESS"
    assert "COOLING" in result["components"] and result["financial_impact"] == "UNKNOWN"
