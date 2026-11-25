"""Synthetic paired behavior checks, not blind relevance labels."""

from copy import deepcopy

import pytest
from test_commodity_context import commodity as commodity
from test_commodity_context import dossier as dossier
from test_commodity_context import grounded as grounded
from test_commodity_context import run
from test_commodity_context import selection as selection

from engine.knowledge_priors import build, load_rules
from engine.prior_context import audit, compare


@pytest.mark.parametrize(
    "price,count",
    [("104", 0), ("105", 0), ("105.01", 1), ("108", 1), ("110", 1), ("95", 0), ("90", 1)],
)
def test_explanations_do_not_change_thresholds_or_magnitude(commodity, price, count):
    values = commodity(price)
    baseline = run(values)
    original = deepcopy(baseline)
    priors = build(values[0], load_rules(), author="synthetic")
    result = compare(baseline, values[0], priors)
    assert baseline == original
    assert result["comparison"]["candidate_count_with"] == count
    assert result["comparison"]["cards_with_explanation"] == count
    assert result["comparison"]["decision_fields_unchanged"]
    if count:
        card = result["with_priors"]["candidate_alerts"][0]
        assert card["knowledge_context"]["status"] == "LLM_PRIOR_UNVERIFIED"
        assert card["financial_magnitude"] == "UNKNOWN" and card["probability"] is None
        with pytest.raises(ValueError, match="Already enriched"):
            compare(result["with_priors"], values[0], priors)


def test_withdrawn_source_cannot_be_rescued_by_prior(commodity):
    values = commodity()
    store = values[-1]
    sid = values[2]["revision"]["id"]
    old = store.history("source", sid)[-1]
    store.append(
        "source", sid, {**old["payload"], "status": "WITHDRAWN"}, expected_head=old["sha256"]
    )
    result = compare(run(values), values[0], build(values[0], load_rules(), author="test"))
    assert result["comparison"]["candidate_count_with"] == 0
    assert result["comparison"]["cards_with_explanation"] == 0


def test_changed_prior_or_atlas_cannot_be_attached(commodity):
    values = commodity()
    priors = build(values[0], load_rules(), author="test")
    changed = deepcopy(values[0])
    changed["relations"][0]["scope"] = "changed"
    with pytest.raises(ValueError, match="atlas changed"):
        audit(changed, priors)
    priors["priors"][0]["inference_steps"] = 2
    with pytest.raises(ValueError, match="derivation changed"):
        compare(run(values), values[0], priors)


def test_no_prior_does_not_hide_source_backed_candidates(commodity):
    values = commodity()
    result = compare(run(values), values[0], build(values[0], [], author="test"))
    assert result["comparison"]["candidate_count_with"] == 1
    assert result["comparison"]["cards_with_explanation"] == 0


def test_audit_does_not_call_source_quote_independent_support(commodity):
    values = commodity()
    report = audit(values[0], build(values[0], load_rules(), author="test"))
    assert report["rows"]
    assert all(not r["conclusion_verified"] for r in report["rows"])
    assert report["independent_labels"] == 0
