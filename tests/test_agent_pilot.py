"""AI outputs cannot silently become independent human quality claims."""

import copy
import hashlib
import json

import pytest

from engine.evaluation.agent_pilot import disputes, evaluate, prepare_input
from engine.ingestion.contracts import digest


def inputs():
    cases = [
        {"id": "a", "source_sha256": "0" * 64, "kind": "causal_language", "split": "holdout"},
        {"id": "b", "source_sha256": "1" * 64, "kind": "causal_language", "split": "development"},
    ]
    pid = digest(cases)
    pack = {"packet_id": pid, "cases": cases}
    a = {
        "evaluation_track": "AI_SIMULATED",
        "profile": "retail_investor",
        "packet_id": pid,
        "blind_to_predictions": True,
        "labels": [
            {
                "case_id": c["id"],
                "source_sha256": c["source_sha256"],
                "reason": "Synthetic independently read source rationale",
                "language": "NO_CAUSAL_CLAIM",
                "numeric": None,
            }
            for c in cases
        ],
    }
    b = copy.deepcopy(a)
    b["profile"] = "fund_manager"
    b["labels"][0]["language"] = "ISSUER_ATTRIBUTION"
    sealed = {"cases": cases, "predictions": {"a": "ISSUER_ATTRIBUTION", "b": "NO_CAUSAL_CLAIM"}}
    return pack, a, b, sealed


def test_ai_scores_are_separate_and_disagreements_require_expert():
    pack, a, b, sealed = inputs()
    report = evaluate(pack, a, b, sealed)
    assert report["human_labels_created"] == 0 and report["human_accuracy"] is None
    assert report["independent_human_validation"] is False
    assert report["pending_adjudications"] == 1
    assert report["holdout_diagnostics"]["causal_language"]["agreement_with_ai_reference"] is None
    conflict = disputes(pack, a, b)["disagreements"][0]
    expert = {
        "evaluation_track": "AI_SIMULATED",
        "profile": "financial_expert",
        "packet_id": pack["packet_id"],
        "blind_to_predictions": True,
        "decisions": [
            {**b["labels"][0], "vote_hash": conflict["vote_hash"], "outcome": "RESOLVED"}
        ],
    }
    report = evaluate(pack, a, b, sealed, expert)
    assert report["status"] == "AI_REVIEW_COMPLETE"
    assert report["holdout_diagnostics"]["causal_language"]["agreement_with_ai_reference"] == 1
    assert report["human_accuracy"] is None and not report["graph_modified"]
    a["labels"][0]["reason"] = "Changed synthetic reviewer rationale invalidates adjudication"
    with pytest.raises(ValueError, match="stale"):
        evaluate(pack, a, b, sealed, expert)


@pytest.mark.parametrize(
    "change", ["human_track", "missing_case", "hash", "packet", "leaked_prediction"]
)
def test_ai_provenance_and_coverage_required(change):
    pack, a, b, sealed = inputs()
    if change == "human_track":
        a["evaluation_track"] = "HUMAN"
    if change == "missing_case":
        a["labels"].pop()
    if change == "hash":
        a["labels"][0]["source_sha256"] = "2" * 64
    if change == "packet":
        sealed["cases"][0]["split"] = "development"
    if change == "leaked_prediction":
        a["blind_to_predictions"] = False
    with pytest.raises(ValueError):
        evaluate(pack, a, b, sealed)


def test_ai_deferred_is_not_a_reference_label():
    pack, a, b, sealed = inputs()
    conflict = disputes(pack, a, b)["disagreements"][0]
    expert = {
        "evaluation_track": "AI_SIMULATED",
        "profile": "financial_expert",
        "packet_id": pack["packet_id"],
        "blind_to_predictions": True,
        "decisions": [
            {
                **a["labels"][0],
                "language": None,
                "numeric": None,
                "vote_hash": conflict["vote_hash"],
                "outcome": "DEFERRED",
            }
        ],
    }
    report = evaluate(pack, a, b, sealed, expert)
    assert report["deferred_disagreements"] == 1 and report["ai_reference_cases"] == 1
    assert report["holdout_diagnostics"]["causal_language"]["scored"] == 0


def test_blind_agent_input_checks_original_capture_hash(tmp_path):
    source = tmp_path / "DELL-synthetic.html"
    source.write_text("<root>\nOriginal source\n</root>", encoding="utf-8")
    case = {
        "id": "synthetic",
        "ticker": "DELL",
        "accession": "synthetic",
        "snapshot_id": "s1",
        "kind": "causal_language",
        "source_sha256": hashlib.sha256(source.read_text().encode()).hexdigest(),
    }
    blind = tmp_path / "blind.json"
    blind.write_text(json.dumps([case]))
    target = tmp_path / "agent-input.json"
    assert prepare_input(blind, tmp_path, target)["predictions_included"] is False
    assert prepare_input(blind, tmp_path, target)["cases"] == 1
    source.write_text("<root>Changed source</root>")
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare_input(blind, tmp_path, target)
