"""Synthetic fresh-sample exclusion and two-review consensus invariants."""

import json
from datetime import UTC, datetime

import pytest
from test_profile_relevance import dossier as dossier
from test_profile_relevance import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.evaluation.profile_relevance import consensus, freeze, overlaps, shingles, write_new
from engine.ingestion.contracts import digest


def test_prior_url_correction_cannot_become_fresh(db, linked, tmp_path):
    first, second = tmp_path / "old", tmp_path / "new"
    with db.connect() as conn:
        freeze(conn, first)
    linked[2](title="Server memory supply changed completely")
    with db.connect() as conn, pytest.raises(ValueError, match="No eligible articles"):
        freeze(conn, second, exclude_packets=[first / "packet.json"])
    assert not second.exists()


def test_near_duplicate_text_has_no_url_dependency():
    a = shingles({"title": "Data center financing project receives new funding from public banks",
                  "summary": "Construction capacity is expanded through new capital commitments."})
    b = shingles({"title": "DATA CENTER financing project receives new funding from public banks!",
                  "summary": "Construction capacity is expanded through new capital commitments."})
    assert overlaps(a, [b])
    assert not overlaps(a, [shingles({"title": "Banks report mortgage loan defaults"})])
    assert not overlaps(set(), [set()])


@pytest.fixture
def reviews(tmp_path):
    # Pure file-level tests: no predictions file exists in the reviewer packet directory.
    packet = [{"id": "one"}, {"id": "two"}]
    write_new(tmp_path / "packet.json", packet)
    write_new(tmp_path / "freeze.json", {"packet_sha256": digest(packet),
                                         "at": "2026-01-01T00:00:00+00:00"})
    paths = []
    for reviewer in ("A", "B"):
        path = tmp_path / (reviewer + ".json")
        write_new(path, {"packet_sha256": digest(packet), "reference_kind": "AI_INDEPENDENT_REVIEW",
                        "reviewer_id": reviewer, "reviewed_at": datetime.now(UTC).isoformat(),
                        "predictions_accessed": False, "peer_labels_accessed": False,
                        "labels": [{"id": id, "relevance": "RELEVANT",
                                    "rationale": "Synthetic scoped relevance judgment."}
                                   for id in ("one", "two")]})
        paths.append(path)
    return tmp_path, paths


def test_consensus_keeps_disagreement_unresolved(reviews):
    root, paths = reviews
    b = json.loads(paths[1].read_text())
    b["labels"][1]["relevance"] = "NOT_RELEVANT"
    paths[1].write_text(json.dumps(b))
    result = consensus(root, paths)
    assert result["disagreements"] == 1 and result["independent_gold"] is False
    assert [v["relevance"] for v in result["labels"]] == ["RELEVANT", "INSUFFICIENT_CONTEXT"]
    assert len(result["review_sha256"]) == 2


@pytest.mark.parametrize("fault", ["same_reviewer", "saw_predictions", "saw_peer", "wrong_packet",
                                   "incomplete", "duplicate", "future", "no_rationale"])
def test_consensus_rejects_invalid_independence_or_coverage(reviews, fault):
    root, paths = reviews
    b = json.loads(paths[1].read_text())
    if fault == "same_reviewer":
        b["reviewer_id"] = "A"
    elif fault == "saw_predictions":
        b["predictions_accessed"] = True
    elif fault == "saw_peer":
        b["peer_labels_accessed"] = True
    elif fault == "wrong_packet":
        b["packet_sha256"] = "0" * 64
    elif fault == "incomplete":
        b["labels"].pop()
    elif fault == "duplicate":
        b["labels"] = [b["labels"][0]] * 2
    elif fault == "future":
        b["reviewed_at"] = "2099-01-01T00:00:00+00:00"
    else:
        b["labels"][0]["rationale"] = ""
    paths[1].write_text(json.dumps(b))
    with pytest.raises(ValueError):
        consensus(root, paths)
