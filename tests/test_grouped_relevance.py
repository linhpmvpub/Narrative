import hashlib
import json

import pytest

from engine.atlas_freeze import runtime_fingerprint
from engine.evaluation.grouped_relevance import (
    candidate_selected,
    connected_clusters,
    evaluate,
    metrics,
    search,
)
from engine.ingestion.contracts import digest


def row(i, **kw):
    return {"id": str(i), "cluster": str(i), "event_cluster": str(i),
            "article": {"title": str(i), "summary": ""}, "split": "calibration",
            "track": "rss", "label": "RELEVANT", "matched": True,
            "resolved_entity": False, "concrete_change": True, "sponsored": False, **kw}


def test_transitive_identity_keeps_all_event_variants_together():
    rows = [row(1, article={"url": "https://example.com/a", "title": "one"}),
            row(2, article={"url": "https://example.com/a", "title": "two"},
                archive_source={"cluster_key": "issuer:period"}),
            row(3, article={"url": "https://example.com/b", "title": "three"},
                archive_source={"cluster_key": "issuer:period"}), row(4)]
    clusters = connected_clusters(rows)
    assert clusters[0] == clusters[1] == clusters[2]
    assert clusters[3] != clusters[0]
    assert connected_clusters(list(reversed(rows))) == list(reversed(clusters))


def test_unknown_and_correlated_pairs_do_not_inflate_support():
    rows = [row(i, event_cluster="one") for i in range(20)]
    rows += [row(21, label="INSUFFICIENT_CONTEXT"), row(22, label="NOT_RELEVANT")]
    result = metrics(rows, lambda r: True)
    assert result["positive_clusters"] == 1
    assert result["precision"] == 20 / 21
    assert result["selected_unresolved"] == 1
    assert metrics([], lambda r: True)["recall"] is None


def test_weight_search_rejects_validation_and_sparse_positive_clusters():
    weights = {"resolved_entity": 40, "concrete_change": 30,
               "sourced_path": 20, "sponsored_penalty": 20}
    grid = {k: [v] for k, v in weights.items()} | {"threshold": [20, 50]}
    with pytest.raises(ValueError, match="calibration"):
        search([row(1, split="development_validation")], grid, weights)
    sparse = [row(i, event_cluster="one") for i in range(20)]
    assert search(sparse, grid, weights)["weights"] is None
    candidate = search([row(i) for i in range(10)], grid, weights)
    assert candidate["weights"] == weights
    assert not candidate_selected(row(1, sponsored=True), weights, 0)
    assert not candidate_selected(row(1, matched=False), weights, 0)


def test_changed_frozen_rows_are_rejected_before_label_reads(tmp_path):
    rows = [row(1)]
    (tmp_path / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    (tmp_path / "freeze.json").write_text(json.dumps({"rows_sha256": digest([])}), encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen replay"):
        evaluate(tmp_path)


def test_near_duplicate_cluster_cannot_cross_split():
    words = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho"
    clusters = connected_clusters([row(1, article={"summary": words}),
                                   row(2, article={"summary": words + " sigma"})])
    assert clusters[0] == clusters[1]


def test_replay_checks_original_labels_and_preserves_unknowns(tmp_path):
    def save(path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    original = tmp_path / "original"
    original.mkdir()
    packet = [{"id": "p", "article": {"title": "Synthetic capacity item"},
               "profile_id": "synthetic", "narrative": {"id": "capacity"}}]
    predictions = {"p": True}
    labels = {"packet_sha256": digest(packet), "reference_kind": "AI_CONSENSUS_REVIEW",
              "reviewer_ids": ["synthetic-a", "synthetic-b"],
              "labels": [{"id": "p", "relevance": "INSUFFICIENT_CONTEXT", "rationale": "Synthetic ambiguity"}]}
    old_freeze = {"packet_sha256": digest(packet), "predictions_sha256": digest(predictions), "clusters": 1}
    for name, data in (("packet", packet), ("predictions", predictions),
                       ("consensus", labels), ("freeze", old_freeze)):
        save(original / (name + ".json"), data)
    receipt = {"directory": str(original), "freeze_sha256": digest(old_freeze),
               "label_file_sha256": hashlib.sha256((original / "consensus.json").read_bytes()).hexdigest()}
    replay = tmp_path / "replay"
    replay.mkdir()
    rows = [row(1, **packet[0], cohort="original", reference_id="p", ticker="AMD",
                groups=["capacity"], baseline_selected=True)]
    weights = {"resolved_entity": 40, "concrete_change": 30,
               "sourced_path": 20, "sponsored_penalty": 20}
    plan = {"weights_grid": {k: [v] for k, v in weights.items()} | {"threshold": [20]}}
    frozen = {"rows_sha256": digest(rows), "plan": plan, "plan_sha256": digest(plan),
              "runtime": runtime_fingerprint(), "receipts": [receipt], "excluded": {},
              "policy": {"priority_weights": weights}}
    save(replay / "rows.json", rows)
    save(replay / "freeze.json", frozen)
    result = evaluate(replay)
    assert result["tracks"]["rss"]["routing"]["overall"]["selected_unresolved"] == 1
    assert result["candidate"]["weights"] is None
    assert result["release_accepted"] is False
    labels["labels"][0]["relevance"] = "RELEVANT"
    save(original / "consensus.json", labels)
    with pytest.raises(ValueError, match="reference labels changed"):
        evaluate(replay, output=tmp_path / "tampered")
