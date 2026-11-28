"""Shared boundaries and explicit source aliases, without inferred pronouns."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from test_company_profiles import dossier as dossier
from test_news_assertions import setup_scope
from test_news_framework import ready as ready
from test_news_objects import configured
from test_profile_news import linked as linked

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import ProfileBundle
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.evaluation import priority_review
from engine.profile_news import matches
from engine.profile_routing import binding_decisions
from engine.source_sentences import sentences, source_units


@pytest.mark.parametrize("text,expected", [
    ("Orion Inc. ships 1.5 TB server memory. Another update.",
     ["Orion Inc. ships 1.5 TB server memory", " Another update"]),
    ("Orion Corp. plans to expand U.S. memory capacity.",
     ["Orion Corp. plans to expand U.S. memory capacity"]),
    ("Visit https://example.test/report.v2. Other news.",
     ["Visit https://example.test/report.v2", " Other news"]),
    ("Contact ir@example.test. Other news.", ["Contact ir@example.test", " Other news"]),
    ("Reported by Orion Inc. OtherVendor ships memory.",
     ["Reported by Orion Inc", " OtherVendor ships memory"]),
    ("Memory rises 5.5%; supplies fall!\nUnrelated?", ["Memory rises 5.5%", " supplies fall", "Unrelated"]),
])
def test_boundaries_preserve_literal_offsets(text, expected):
    chunks = list(sentences(text))
    assert [s.group() for s in chunks] == expected
    assert all(text[s.start():s.end()] == s.group() for s in chunks)


@pytest.mark.parametrize("name", ["Orion", "Aurora"])
@pytest.mark.parametrize("suffix", ["Inc.", "Corp.", "Ltd."])
def test_legal_suffix_rss_and_body_parity(ready, name, suffix):
    _, data, _ = setup_scope(ready, name)
    bundle = ProfileBundle.model_validate(data)
    text = f"{name} {suffix} ships 1.5 TB server memory samples."
    hits = matches(bundle.factor_bindings[0], {"summary": text})
    cards = list(article_decisions(bundle, bundle.narratives[0], "Update",
                 [{"text": text, "source_spans": []}], datetime.now(UTC)))
    assert hits and cards
    assert all(text[h["start"]:h["end"]] == h["text"] for h in hits)


@pytest.mark.parametrize("name", ["Orion", "Aurora"])
def test_declared_alias_one_hop_keeps_quote_and_paragraph_offsets(ready, name):
    _, data, _ = setup_scope(ready, name)
    bundle = ProfileBundle.model_validate(data)
    text = f'{name} Inc. (the “Company”) published an update. The Company ships server memory samples.'
    direct = matches(bundle.factor_bindings[0], {"summary": text})
    units = list(source_units(text))
    unit = matches(bundle.factor_bindings[0], units[-1])
    cards = list(article_decisions(bundle, bundle.narratives[0], "Update",
                 [{"text": text, "source_spans": []}], datetime.now(UTC)))
    assert direct and unit and cards
    ref = direct[0]["assertion_scope"]["subject_reference"]
    assert ref == unit[0]["assertion_scope"]["subject_reference"]
    for key in ["antecedent", "declaration", "reference_span"]:
        span = ref[key]
        assert text[span["start"]:span["end"]] == span["text"]
    assert ref["antecedent"]["text"] == name
    assert cards[0]["paragraph"] == text
    assert all(text[m["start"]:m["end"]] == m["text"] for m in cards[0]["matches"])
    assert direct[0]["assertion_scope"]["financial_impact"] == "UNKNOWN"


@pytest.mark.parametrize("text", [
    'Orion announced an update. The Company ships server memory samples.',
    'OtherVendor (the “Company”) announced an update. The Company ships server memory samples.',
    'Orion (the “Company”) announced an update. It ships server memory samples.',
    'Orion (the “Company”) announced an update. Other news. The Company ships server memory samples.',
    'Orion (the “Company”) announced an update.\nThe Company ships server memory samples.',
    'Orion (the “Company”) and OtherVendor (the “Company”) announced an update. The Company ships server memory samples.',
    'Orion (the “Company”) announced an update but OtherVendor joined. The Company ships server memory samples.',
    'Orion (the “Company”) announced an update. OtherVendor ships server memory for the Company.',
    'Orion (the “Company”) announced an update. The Company has not shipped server memory samples.',
    'Orion (the “Company”) announced an update. The Company ships smartphone memory samples.',
])
def test_no_implicit_or_ambiguous_actor_donation(ready, text):
    _, data, _ = setup_scope(ready)
    b = ProfileBundle.model_validate(data).factor_bindings[0]
    assert not matches(b, {"summary": text})


def test_no_title_or_unmatched_context_reference(ready):
    _, data, _ = setup_scope(ready)
    b = ProfileBundle.model_validate(data).factor_bindings[0]
    assert not matches(b, {"title": 'Orion (the “Company”) announced news.',
                          "summary": "The Company ships server memory samples."})
    assert not matches(b, {"summary": "The Company ships server memory samples.",
                          "source_context": 'Orion (the “Company”) unrelated text.', "source_offset": 0})


def test_explicit_alias_flows_through_object_topic_gate(ready):
    _, data, relation = configured(ready)
    bundle = ProfileBundle.model_validate(data)
    text = 'Orion (the “Company”) published an update. The Company acquired memory assets.'
    direct = matches(bundle.factor_bindings[0], {"summary": text})
    assert direct and direct[0]["assertion_scope"]["reason"] == "OWNERSHIP_OBJECT"
    assert all(m["context_only"] for m in direct)
    assert all(text[m["start"]:m["end"]] == m["text"] for m in direct)
    cards = list(article_decisions(bundle, bundle.narratives[0], "Update",
                 [{"text": text, "source_spans": []}], datetime.now(UTC)))
    assert cards and cards[0]["matches"][0]["assertion_scope"] == direct[0]["assertion_scope"]
    relation["valid_until"] = data["available_at"]
    expired = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(expired, expired.narratives[0], {"summary": text}, datetime.now(UTC)))


def test_priority_review_keeps_body_audit_when_title_wins_score_tie(monkeypatch):
    monkeypatch.setattr("engine.article_cards.substantive_blocks", lambda *a: (
        [{"text": "Orion ships memory samples."}], []))
    def links(bundle, narrative, unit, at):
        if unit.get("summary"):
            yield {"binding": SimpleNamespace(entity_reference_id=None), "path": [],
                   "paths_truncated": False, "matches": [{"field": "summary", "start": 0,
                   "end": 5, "context_only": True, "assertion_scope": {"allowed": True}}]}
    monkeypatch.setattr(priority_review, "binding_decisions", links)
    matched, assessment = priority_review.decisions(
        {"article": {"title": "Update"}, "source_observation": {}}, None, None, datetime.now(UTC),
        json.loads(POLICY.read_text(encoding="utf-8")))
    assert matched and assessment["tier"] == "BACKGROUND_THEME"
    assert assessment["priority_audit"]["matched_links"] == 0
    assert assessment["review_audit"]["context_only_links"] == 1
    assert assessment["review_audit"]["scoped_assertion_links"] == 1


def test_priority_audit_explains_context_without_promoting_it():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    text = "Orion Inc. expanded memory capacity by 5.5%"
    hit = {"field": "summary", "start": 0, "end": len(text),
           "context_only": True, "assertion_scope": {"allowed": True}}
    result = assess({"headline": "Update", "excerpt": text}, [{"matches": [hit]}], policy)
    assert result["tier"] == "BACKGROUND_THEME" and result["direction"] == "UNKNOWN"
    assert result["priority_audit"]["context_only_links"] == 1
    assert result["priority_audit"]["scoped_assertion_links"] == 1
    assert result["priority_audit"]["concrete_signals"] == 0
    hit["context_only"] = False
    result = assess({"headline": "Update", "excerpt": text}, [{"matches": [hit]}], policy)
    assert result["priority_audit"]["eligible_windows"] == 1
