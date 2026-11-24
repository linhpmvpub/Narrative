"""Synthetic benchmark integrity and denominator tests, not model accuracy."""

import copy
import hashlib
import json

import pytest

from engine.evaluation.extraction_benchmark import (
    evaluate,
    freeze,
    score,
    validate_labels,
    verify,
)


def span(text, value):
    a = text.index(value)
    return {"start": a, "end": a + len(value), "text": value}


@pytest.fixture
def sample():
    text = (
        "Alpha expanded factories. Prices fell. "
        + "Source context without an additional event. " * 5
    )
    case = {
        "id": "case-1",
        "text": text,
        "title": "Synthetic",
        "source_url": "https://example.org/synthetic",
        "published_at": "2020-01-01T00:00:00Z",
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "expected_secret": "must not reach blind packet",
    }
    first = {
        "actor": span(text, "Alpha"),
        "predicate": span(text, "expanded"),
        "object": span(text, "factories"),
        "polarity": "AFFIRMED",
        "phase": "REPORTED_ACTION",
        "attributed": "NO",
    }
    second = {
        "actor": span(text, "Prices"),
        "predicate": span(text, "fell"),
        "object": None,
        "polarity": "AFFIRMED",
        "phase": "REPORTED_ACTION",
        "attributed": "NO",
    }
    prediction = {**first, "delivery": "disabled", "review_flags": []}
    labels = {
        "reviewer_id": "a",
        "reviewer_kind": "AI_INDEPENDENT",
        "cases": [
            {"id": case["id"], "status": "REVIEWED", "assertions": [first, second], "comment": ""}
        ],
    }
    return [case], {"case-1": [prediction]}, labels


def test_source_first_denominator_preserves_misses(sample):
    cases, pred, labels = sample
    result = score(cases, pred, labels)
    assert (result["predicate_tp"], result["predicate_fp"], result["predicate_fn"]) == (1, 0, 1)
    assert result["predicate_precision"] == 1 and result["predicate_recall"] == 0.5
    assert result["null_object_gold"] == 1 and result["null_object_matched"] == 0
    assert result["actor_exact"] == 1 and result["phase_exact"] == 1


def test_unsure_not_negative_or_zero_recall(sample):
    cases, pred, labels = sample
    labels["cases"][0]["status"] = "UNSURE"
    result = score(cases, pred, labels)
    assert result["unsure_cases_excluded"] == 1 and result["predicate_fn"] == 0
    assert result["predicate_precision"] is None and result["predicate_recall"] is None


def test_duplicate_prediction_cannot_match_twice(sample):
    cases, pred, labels = sample
    pred["case-1"] *= 2
    result = score(cases, pred, labels)
    assert (
        result["predicate_tp"] == 1 and result["predicate_fp"] == 1 and result["predicate_fn"] == 1
    )


def test_freeze_blind_whitelist_and_separate_labels(tmp_path, sample):
    cases, pred, labels = sample
    root = tmp_path / "frozen"
    pin = freeze(cases, pred, root, protocol={"synthetic": True})
    files, receipt = verify(root, pin)
    assert "expected_secret" not in files["blind.json"][0]
    assert not receipt["human_gold"] and receipt["delivery"] == "disabled"
    other = copy.deepcopy(labels)
    other["reviewer_id"] = "b"
    result = evaluate(root, pin, labels, other)
    assert result["exact_case_agreements"] == 1 and not result["consensus_gold_created"]
    other["cases"][0]["assertions"][0]["phase"] = "UNKNOWN"
    assert evaluate(root, pin, labels, other)["cases_requiring_adjudication"] == ["case-1"]
    with pytest.raises(FileExistsError):
        freeze(cases, pred, root, protocol={})
    with pytest.raises(ValueError, match="Distinct"):
        evaluate(root, pin, labels, labels)


@pytest.mark.parametrize(
    "name", ["blind.json", "sources.json", "predictions.json", "protocol.json", "receipt.json"]
)
def test_frozen_tampering_rejected(tmp_path, sample, name):
    cases, pred, _ = sample
    root = tmp_path / "freeze"
    pin = freeze(cases, pred, root, protocol={})
    p = root / name
    data = json.loads(p.read_text())
    if isinstance(data, list):
        data[0]["text"] = "changed"
    else:
        data["changed"] = True
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(root, pin)


@pytest.mark.parametrize(
    "fault", ["missing_case", "duplicate_assertion", "span", "category", "extra", "provenance"]
)
def test_bad_labels_rejected(sample, fault):
    cases, _, labels = sample
    if fault == "missing_case":
        labels["cases"] = []
    elif fault == "duplicate_assertion":
        labels["cases"][0]["assertions"] *= 2
    elif fault == "span":
        labels["cases"][0]["assertions"][0]["actor"]["text"] = "Beta"
    elif fault == "category":
        labels["cases"][0]["assertions"][0]["phase"] = "COMMITTED"
    elif fault == "extra":
        labels["cases"][0]["assertions"][0]["predicted"] = True
    else:
        labels["reviewer_kind"] = "IMPLEMENTER"
    with pytest.raises(ValueError):
        validate_labels(labels, cases)


def test_prior_passage_and_live_prediction_rejected(tmp_path, sample):
    cases, pred, _ = sample
    with pytest.raises(ValueError, match="exposed"):
        freeze(
            cases,
            pred,
            tmp_path / "x",
            protocol={},
            excluded_text_hashes=[hashlib.sha256(cases[0]["text"].encode()).hexdigest()],
        )
    pred["case-1"][0]["delivery"] = "enabled"
    with pytest.raises(ValueError, match="Disabled"):
        freeze(cases, pred, tmp_path / "x", protocol={})


def test_uncertainty_flag_counts_do_not_claim_promotion(sample):
    cases, pred, labels = sample
    a = labels["cases"][0]["assertions"][0]
    a["polarity"] = "CONDITIONAL"
    a["attributed"] = "YES"
    result = score(cases, pred, labels)
    assert result["uncertainty_flags_on_matched_only"]["CONDITIONAL"] == {
        "matched_gold": 1,
        "flagged": 0,
    }
    assert result["delivery"] == "disabled"


def test_predicate_phrase_cannot_silently_change_alignment_denominator(sample):
    cases, _, labels = sample
    labels["cases"][0]["assertions"][0]["predicate"] = span(cases[0]["text"], "expanded factories")
    with pytest.raises(ValueError, match="One lexical"):
        validate_labels(labels, cases)
