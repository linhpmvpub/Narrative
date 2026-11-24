from datetime import UTC, datetime, timedelta

import pytest

from engine.company_profiles import FactorBinding
from engine.profile_news import matches


def rule(**changes):
    at = datetime.now(UTC)
    phrase = "Initial shipments of next-generation Example accelerators"
    return FactorBinding(**{**dict(id="shipments", factor_id="product",
        kind="ISSUER_PRODUCT_SHIPMENTS", topic_terms=["Example accelerators"],
        context_terms=[phrase], change_terms=["shipments"], issuer_supply_scope=True,
        narrative_ids=["product-availability"], scope="Synthetic product context only",
        reviewed_at=at, review_until=at+timedelta(days=1),
        evidence=[{"source_id":"s", "quote":phrase}]), **changes})


def test_literal_issuer_bullet_preserves_offsets():
    text = "Product highlights; Initial shipments of next-generation Example accelerators."
    spans = matches(rule(), {"summary":text}, issuer_cik="123", profile_cik="000123")
    assert spans and all(text[s["start"]:s["end"]] == s["text"] for s in spans)
    assert not spans[0]["impact_eligible"] and not spans[0]["foundry_exposure_verified"]


@pytest.mark.parametrize("text", [
    "We expect initial shipments of next-generation Example accelerators.",
    "No initial shipments of next-generation Example accelerators.",
    "Initial shipments of next-generation Example accelerators may start.",
    "A competitor reported initial shipments of next-generation Example accelerators.",
    "Customers reported initial shipments of next-generation Example accelerators.",
    '"Initial shipments of next-generation Example accelerators."',
    "Initial shipments of something else. Example accelerators are available.",
    "Strong sales growth for Example accelerators.",
    "Initial shipments of next-generation Example accelerators were cancelled.",
    "Initial shipments of next-generation Example accelerators are scheduled next year.",
])
def test_no_future_negation_attribution_or_sales_shortcut(text):
    assert not matches(rule(), {"summary":text}, issuer_cik="123", profile_cik="123")


@pytest.mark.parametrize("issuer", [None,"456","bad"])
def test_trusted_matching_issuer_required(issuer):
    assert not matches(rule(), {"summary":rule().context_terms[0], "issuer_cik":"123"},
                       issuer_cik=issuer, profile_cik="123")


@pytest.mark.parametrize("changes", [{"topic_terms":["accelerators"]},
    {"context_terms":["sales growth"]}, {"change_terms":["sales"]},
    {"issuer_supply_scope":False}, {"narrative_ids":[]}, {"evidence":[{"source_id":"s","quote":"Other evidence"}]}])
def test_rule_requires_exact_sourced_product_phrase(changes):
    with pytest.raises(ValueError):
        rule(**changes)
