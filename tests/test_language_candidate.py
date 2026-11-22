"""Synthetic semantic boundaries and prospective leakage gates, not fitted gold labels."""

import copy
from datetime import UTC, datetime

import pytest

from engine.evaluation.language_audit import audit, protocol, screen_future, verify_baseline
from engine.evaluation.language_candidate import classify
from engine.ingestion.contracts import digest


@pytest.mark.parametrize(
    "text,label",
    [
        ("Revenue increased due to stronger demand.", "ISSUER_ATTRIBUTION"),
        ("Revenue increased because orders recovered.", "ISSUER_ATTRIBUTION"),
        ("Tax credits reduced income tax expense this year.", "ISSUER_ATTRIBUTION"),
        ("The tax benefit reflected research credits.", "ISSUER_ATTRIBUTION"),
        (
            "Cash increased due to customer advances. Future sales may decline.",
            "ISSUER_ATTRIBUTION",
        ),
        ("Revenue rose due to pricing. We did not open an office.", "ISSUER_ATTRIBUTION"),
        ("Revenue may grow as customers renew subscriptions.", "UNCERTAIN_OR_FORWARD_LOOKING"),
        ("We expect sales to remain stable next quarter.", "UNCERTAIN_OR_FORWARD_LOOKING"),
        ("Revenue is dependent upon customer acceptance.", "UNCERTAIN_OR_FORWARD_LOOKING"),
        ("Revenue did not increase due to higher prices.", "UNCERTAIN_OR_FORWARD_LOOKING"),
        (
            "Auditor judgment over revenue was required due to automated processing.",
            "NO_CAUSAL_CLAIM",
        ),
        ("Revenue was $120 million compared with $100 million.", "NO_CAUSAL_CLAIM"),
        ("Revenue is recognized when control transfers to the customer.", "NO_CAUSAL_CLAIM"),
        ("Revenue increased twelve percent.", "NO_CAUSAL_CLAIM"),
        ("Management may open a new office next year.", "NO_CAUSAL_CLAIM"),
        ("", "NO_CAUSAL_CLAIM"),
        ("We expect to provide additional income tax disclosures next year.", "NO_CAUSAL_CLAIM"),
        ("The table presents expenses reflected in operating income.", "NO_CAUSAL_CLAIM"),
        ("Contract liabilities increased due to customer advances.", "ISSUER_ATTRIBUTION"),
        (
            "Forecast errors risk excess inventory, potentially resulting in loss of sales.",
            "UNCERTAIN_OR_FORWARD_LOOKING",
        ),
        ("Margins did not improve due to higher prices.", "UNCERTAIN_OR_FORWARD_LOOKING"),
    ],
)
def test_semantic_boundaries_and_exact_trace(text, label):
    result = classify(text)
    assert result["label"] == label
    assert result["deployment"] == "SHADOW_ONLY" and not result["graph_eligible"]
    assert not result["independently_verified"] and result["stock_price_impact"] == "UNKNOWN"
    for e in result["evidence"]:
        assert text[e["start"] : e["end"]] == e["text"]


def test_audit_sentence_does_not_hide_realized_financial_sentence():
    result = classify(
        "Audit evidence over revenue required judgment due to automation. Revenue rose due to demand. Sales may decline."
    )
    assert result["label"] == "ISSUER_ATTRIBUTION" and result["mixed_temporal_claims"]
    assert result["evidence"][0]["rule"] == "AUDIT_PROCEDURE_NOT_FINANCIAL_CAUSE"


def fixtures():
    seen = {
        "kind": "causal_language",
        "accession": "old",
        "source_sha256": "old-hash",
        "text": "Revenue increased due to a strong recovery in domestic demand during the latest reporting period",
    }
    plan = protocol([seen], datetime(2025, 1, 1, tzinfo=UTC))
    new = {
        "accession": "new",
        "source_sha256": "new-hash",
        "available_at": "2025-02-01T12:00:00+00:00",
        "filing_date": "2025-02-01",
        "text": "A manufacturing outage reduced operating income because spare parts were unavailable",
    }
    return seen, plan, new


def test_new_source_requires_future_blind_review_not_automatic_promotion():
    _, plan, new = fixtures()
    result = screen_future(new, plan, datetime(2025, 3, 1, tzinfo=UTC))
    assert result["eligible_for_new_review"] and result["source_verification_still_required"]
    assert not plan["promotion_allowed"] and plan["prediction_freeze_before_labels"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"accession": "old"}, "SOURCE_ALREADY_EXPOSED"),
        ({"source_sha256": "old-hash"}, "SOURCE_ALREADY_EXPOSED"),
        ({"available_at": "2024-12-01T12:00:00+00:00"}, "CAPTURE_NOT_AFTER_FREEZE"),
        ({"available_at": "2025-02-01T12:00:00"}, "CAPTURE_NOT_AFTER_FREEZE"),
        ({"available_at": "2025-04-01T12:00:00+00:00"}, "CAPTURE_IN_FUTURE"),
        ({"filing_date": "2024-12-01"}, "FILING_NOT_AFTER_FREEZE"),
        ({"filing_date": "2025-04-01"}, "FILING_IN_FUTURE"),
        ({"filing_date": "bad"}, "MISSING_VALID_SOURCE_TIMES"),
        ({"text": ""}, "INSUFFICIENT_TEXT"),
    ],
)
def test_time_and_source_reuse_rejected(change, reason):
    _, plan, new = fixtures()
    result = screen_future(new | change, plan, datetime(2025, 3, 1, tzinfo=UTC))
    assert reason in result["reasons"] and not result["eligible_for_new_review"]


def test_cross_accession_boilerplate_and_candidate_drift():
    seen, plan, new = fixtures()
    assert (
        "EXACT_TEXT_REUSE"
        in screen_future(new | {"text": seen["text"].upper() + "."}, plan)["reasons"]
    )
    assert (
        "NEAR_TEXT_REUSE" in screen_future(new | {"text": seen["text"] + " today"}, plan)["reasons"]
    )
    plan["candidate_sha256"] = "changed"
    assert "CANDIDATE_CHANGED_AFTER_FREEZE" in screen_future(new, plan)["reasons"]


def test_posthoc_audit_does_not_mutate_baseline_or_publish_source_text():
    cases = [
        {
            "id": "a",
            "kind": "causal_language",
            "split": "holdout",
            "text": "Revenue may decline next year.",
            "source_sha256": "0" * 64,
        },
        {
            "id": "b",
            "kind": "causal_language",
            "split": "development",
            "text": "Auditor judgment over revenue was required due to automation.",
            "source_sha256": "1" * 64,
        },
    ]
    pid = digest(cases)
    sealed = {"cases": cases, "predictions": {"a": "NO_CAUSAL_CLAIM", "b": "ISSUER_ATTRIBUTION"}}
    original = copy.deepcopy(sealed)
    a = {
        "packet_id": pid,
        "evaluation_track": "AI_SIMULATED",
        "profile": "retail_investor",
        "blind_to_predictions": True,
        "labels": [
            {
                "case_id": c["id"],
                "source_sha256": c["source_sha256"],
                "language": "UNCERTAIN_OR_FORWARD_LOOKING" if c["id"] == "a" else "NO_CAUSAL_CLAIM",
                "numeric": None,
                "reason": "Synthetic reviewer inspected the source",
            }
            for c in cases
        ],
    }
    b = copy.deepcopy(a)
    b["profile"] = "fund_manager"
    expert = {
        "packet_id": pid,
        "evaluation_track": "AI_SIMULATED",
        "profile": "financial_expert",
        "blind_to_predictions": True,
        "decisions": [],
    }
    result, details = audit({"packet_id": pid, "cases": cases}, a, b, sealed, expert)
    assert sealed == original and result["human_accuracy"] is None
    assert result["splits"]["holdout"]["fixed_against_ai"] == 1
    assert len(details) == 2 and "Revenue may decline" not in str(result)
    assert result["deployment"] == "SHADOW_ONLY" and not result["graph_modified"]


def test_prediction_tampering_rejected_against_original_freeze_receipt():
    sealed = {
        "cases": [{"id": "a"}],
        "predictions": {"a": "NO_CAUSAL_CLAIM"},
        "extractor": "synthetic-v1",
        "as_of": "2025-01-01T00:00:00+00:00",
    }
    receipt = {
        "packet_id": digest(sealed["cases"]),
        "prediction_sha256": digest({k: sealed[k] for k in ("predictions", "extractor", "as_of")}),
    }
    assert verify_baseline(sealed, receipt) == receipt["prediction_sha256"]
    sealed["predictions"]["a"] = "ISSUER_ATTRIBUTION"
    with pytest.raises(ValueError, match="freeze receipt"):
        verify_baseline(sealed, receipt)
