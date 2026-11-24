from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier

from engine.company_profiles import FactorBinding, ProfileBundle
from engine.evaluation.archived_profile_relevance import text_prediction
from engine.profile_news import matches


def rule(**changes):
    now = datetime.now(UTC)
    data = dict(id="operations", factor_id="product", kind="ISSUER_OPERATING_CONTEXT",
        topic_terms=["systems"], context_terms=["our systems"], change_terms=["ramp", "increased"],
        issuer_supply_scope=True, narrative_ids=["n"], scope="Synthetic own-product context",
        reviewed_at=now, review_until=now + timedelta(days=1),
        evidence=[{"source_id": "s", "quote": "Synthetic evidence"}])
    return FactorBinding(**{**data, **changes})


def test_same_issuer_same_sentence_preserves_original_offsets():
    text = "Revenue was $12.5 billion, driven by the ramp of our systems and higher demand."
    spans = matches(rule(), {"summary": text}, issuer_cik="000123", profile_cik="123")
    assert spans and all(text[s["start"]:s["end"]] == s["text"] for s in spans)
    assert not spans[-1]["impact_eligible"] and not spans[-1]["identity_merged"]


@pytest.mark.parametrize("text", [
    "Our systems are available. A competitor announced a ramp.",
    "We expect the ramp of our systems next year.",
    "If demand improves, we increased output of our systems.",
    "Our systems did not see a ramp.",
    "There was no ramp of our systems.",
    'The customer said "the ramp of our systems increased".',
    "“The ramp of our systems increased,” said the CEO.",
    "'The ramp of our systems increased.'",
    "‘The ramp of our systems increased.’",
    "Our competitor reported increased systems demand.",
    "They increased output of our systems.",
    "The systems ramp increased.",
])
def test_ambiguity_quotes_cross_sentence_and_external_subject_withheld(text):
    assert not matches(rule(), {"summary": text}, issuer_cik="123", profile_cik="123")


@pytest.mark.parametrize("issuer,profile", [(None, "123"), ("123", None), ("1", "123"),
                                           ("bad", "123"), ("0", "0")])
def test_payload_identity_cannot_enable_rule(issuer, profile):
    assert not matches(rule(), {"summary": "The ramp of our systems increased.",
                               "issuer_cik": "123"}, issuer_cik=issuer, profile_cik=profile)


@pytest.mark.parametrize("changes", [{"narrative_ids": []}, {"issuer_supply_scope": False},
    {"entity_reference_id": "party"}, {"context_terms": ["systems"]},
    {"term_aliases": {"systems": ["widgets"]}}, {"change_terms": []},
    {"disclosure_terms": ["we purchase"]}])
def test_rule_requires_explicit_product_context_and_scope(changes):
    with pytest.raises(ValueError):
        rule(**changes)


def test_plants_is_not_mistaken_for_planned_future_activity():
    binding = rule(context_terms=["our plants"], change_terms=["expanded"])
    text = "Output of systems from our plants expanded this quarter."
    assert matches(binding, {"summary": text}, issuer_cik="123", profile_cik="123")


def test_profile_product_anchor_and_temporal_path_required(dossier):
    _, data = dossier
    data["identifiers"] = {"CIK": "123"}
    product = next(n for n in data["nodes"] if n["kind"] == "product")
    n = data["narratives"][0]
    binding = rule(factor_id=product["id"], narrative_ids=[n["id"]],
                   reviewed_at=data["available_at"], evidence=data["relationships"][0]["evidence"])
    data["factor_bindings"] = [binding.model_dump(mode="json")]
    bundle = ProfileBundle.model_validate(data)
    at = datetime.now(UTC)
    article = {"summary": "The ramp of our systems increased."}
    assert text_prediction(bundle, bundle.narratives[0], article, at, issuer_cik="123")
    assert not text_prediction(bundle, bundle.narratives[0], article, at, issuer_cik="456")
    assert not text_prediction(bundle, bundle.narratives[0], article, at + timedelta(days=3),
                               issuer_cik="123")
    data["factor_bindings"][0]["factor_id"] = "f"
    with pytest.raises(ValueError):
        ProfileBundle.model_validate(data)
