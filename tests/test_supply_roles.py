"""Synthetic role-bound routing, ambiguity and direction tests."""

from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier

from engine.company_profiles import FactorBinding, ProfileBundle
from engine.evaluation.archived_profile_relevance import text_prediction
from engine.profile_news import matches
from engine.supply_roles import extract_supply_roles, supplier_span


def rule():
    now = datetime.now(UTC)
    return FactorBinding(id="supplier", factor_id="memory", topic_terms=["memory"],
        context_terms=["memory"], kind="SUPPLIER_ROLE_DISCLOSURE",
        disclosure_terms=["We purchase"], narrative_ids=["memory-supply"],
        scope="Synthetic supplier product context", reviewed_at=now,
        review_until=now + timedelta(days=1), evidence=[{"source_id": "test", "quote": "Test"}])


TEXT = "We purchase memory from Example Technology, Inc., Another Corporation and Third Ltd."


def test_roles_preserve_direction_product_and_original_spans():
    data = extract_supply_roles(TEXT, "000123")
    fact = data["facts"][0]
    assert data["issuer_supply_context"] and fact["buyer_cik"] == "123"
    assert fact["product"] == "memory" and not fact["relationship_verified"]
    assert TEXT[fact["start"]:fact["end"]] == fact["text"]
    spans = matches(rule(), {"summary": TEXT}, issuer_cik="123", profile_cik="456",
                    legal_name="EXAMPLE TECHNOLOGY INC")
    assert spans and all(TEXT[s["start"]:s["end"]] == s["text"] for s in spans)


@pytest.mark.parametrize("text", [
    "We may purchase memory from Example Technology, Inc.",
    "We do not purchase memory from Example Technology, Inc.",
    'They said "We purchase memory from Example Technology, Inc."',
    "Our competitors purchase memory from Example Technology, Inc.",
    "We purchase memory from an affiliate of Example Technology, Inc.",
    "We purchase memory and wafers from Example Technology, Inc.",
    "We purchase memory from Example Technology Holdings, Inc.",
    "We purchase wafers from Example Technology, Inc.",
    "We sell memory to Example Technology, Inc.",
    "We purchase memory from Different Company. Example Technology sells chips.",
    "We purchase memory from Different Company. Example Technology, Inc. also sells chips.",
])
def test_ambiguous_wrong_product_or_wrong_role_is_withheld(text):
    assert not matches(rule(), {"summary": text}, issuer_cik="123", profile_cik="456",
                       legal_name="EXAMPLE TECHNOLOGY INC")


@pytest.mark.parametrize("issuer,target", [(None, "456"), ("123", None),
                                           ("123", "123"), ("bad", "456")])
def test_source_context_is_not_payload_identity(issuer, target):
    assert not matches(rule(), {"summary": TEXT, "issuer_cik": "123"}, issuer_cik=issuer,
                       profile_cik=target, legal_name="EXAMPLE TECHNOLOGY INC")


def test_single_word_brand_does_not_resolve_legal_entity():
    fact = extract_supply_roles(TEXT, "123")["facts"][0]
    assert supplier_span(fact, "Example") is None


@pytest.mark.parametrize("fault", [None, "expired", "revoked_path", "wrong_product_node"])
def test_supplier_role_requires_reviewed_product_and_current_route(dossier, fault):
    _, data = dossier
    data.update(legal_name="EXAMPLE TECHNOLOGY INC", identifiers={"CIK": "456"})
    binding = rule().model_dump(mode="json")
    binding.update(factor_id="p", narrative_ids=["n"], reviewed_at=data["available_at"],
                   evidence=data["relationships"][0]["evidence"])
    if fault == "expired":
        binding["review_until"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    if fault == "revoked_path":
        data["relationships"][-1]["status"] = "REVOKED"
    if fault == "wrong_product_node":
        binding["factor_id"] = "f"
    data["factor_bindings"] = [binding]
    if fault == "wrong_product_node":
        with pytest.raises(ValueError, match="product node"):
            ProfileBundle.model_validate(data)
        return
    bundle = ProfileBundle.model_validate(data)
    result = text_prediction(bundle, bundle.narratives[0], {"summary": TEXT},
                             datetime.now(UTC), issuer_cik="123")
    assert result is (fault is None)


@pytest.mark.parametrize("target,scoped,expected", [("123", True, True),
                                                   ("123", False, False),
                                                   ("456", True, False)])
def test_economic_binding_cannot_borrow_another_issuers_supply_context(dossier, target, scoped, expected):
    _, data = dossier
    data["identifiers"] = {"CIK": target}
    binding = rule().model_dump(mode="json")
    binding.update(kind="ECONOMIC_CHANGE", disclosure_terms=[], change_terms=["purchase"],
        issuer_supply_scope=scoped, factor_id="f", narrative_ids=["n"],
        reviewed_at=data["available_at"], evidence=data["relationships"][0]["evidence"])
    data["factor_bindings"] = [binding]
    bundle = ProfileBundle.model_validate(data)
    assert text_prediction(bundle, bundle.narratives[0], {"summary": TEXT},
                           datetime.now(UTC), issuer_cik="123") is expected
