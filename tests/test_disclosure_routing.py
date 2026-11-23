"""Issuer context is external provenance, never a self-declared RSS field."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from engine.company_profiles import FactorBinding
from engine.evaluation.archived_profile_relevance import text_prediction
from engine.profile_news import matches


def binding(**updates):
    now = datetime.now(UTC)
    return FactorBinding.model_validate({"id": "supply", "factor_id": "wafer",
        "topic_terms": ["wafers"], "context_terms": ["semiconductor"],
        "kind": "ISSUER_RELATIONSHIP_DISCLOSURE", "disclosure_terms": ["We utilize suppliers"],
        "narrative_ids": ["supply"],
        "scope": "Synthetic issuer exposure, no financial change",
        "reviewed_at": now, "review_until": now + timedelta(days=1),
        "evidence": [{"source_id": "test", "quote": "Synthetic source quote"}], **updates})


TEXT = "We utilize suppliers to produce our semiconductor wafers."


def test_disclosure_without_change_preserves_exact_spans():
    spans = matches(binding(), {"summary": TEXT}, issuer_cik="000123", profile_cik="123")
    assert {s["group"] for s in spans} == {"topic_terms", "context_terms", "disclosure_terms"}
    assert all(TEXT[s["start"]:s["end"]] == s["text"] for s in spans)


@pytest.mark.parametrize("issuer,profile", [(None, "123"), ("456", "123"),
                                           ("123", None), ("0", "000"), ("ticker", "123")])
def test_untrusted_or_other_issuer_withheld(issuer, profile):
    assert not matches(binding(), {"summary": TEXT, "issuer_cik": "123"},
                       issuer_cik=issuer, profile_cik=profile)


@pytest.mark.parametrize("text", [
    "Our competitors utilize suppliers to produce semiconductor wafers.",
    'They said "We utilize suppliers to produce semiconductor wafers."',
    "We do not utilize suppliers to produce semiconductor wafers.",
    "We utilize suppliers, but no longer purchase semiconductor wafers.",
    "We utilize suppliers to manufacture unrelated products.",
    TEXT + " x" * 900,
])
def test_subject_negation_and_product_scope(text):
    assert not matches(binding(), {"summary": text}, issuer_cik="123", profile_cik="123")


@pytest.mark.parametrize("updates", [
    {"change_terms": ["capacity"]}, {"disclosure_terms": []},
    {"disclosure_terms": ["suppliers"]},
    {"term_aliases": {"We utilize suppliers": ["competitors utilize suppliers"]}},
    {"kind": "ECONOMIC_CHANGE"},
    {"narrative_ids": []},
])
def test_contract_keeps_modes_separate(updates):
    with pytest.raises(ValueError):
        binding(**updates)


def test_legacy_economic_rule_still_requires_change():
    old = binding(kind="ECONOMIC_CHANGE", disclosure_terms=[], change_terms=["capacity"])
    assert not matches(old, {"summary": TEXT}, issuer_cik="123", profile_cik="123")


def test_disclosure_cannot_spread_to_unapproved_narrative():
    bundle = SimpleNamespace(factor_bindings=[binding()], identifiers={"CIK": "123"})
    assert not text_prediction(bundle, SimpleNamespace(id="customer-demand"),
                               {"summary": TEXT}, datetime.now(UTC), issuer_cik="123")
