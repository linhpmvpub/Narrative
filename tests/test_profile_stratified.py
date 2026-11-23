"""Sampling is independent of production match results; scores retain support counts."""


import pytest
from test_profile_relevance import dossier as dossier
from test_profile_relevance import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.evaluation.profile_relevance import (
    evaluate,
    freeze,
    sample_articles,
    stratum,
    write_new,
)
from engine.ingestion.contracts import digest


def test_round_robin_does_not_drop_sparse_topics():
    rows = [{"id": i, "payload": {"title": "New funding round"}} for i in range(20)]
    rows += [{"id": "p", "payload": {"title": "Planning approval"}},
             {"id": "c", "payload": {"title": "Compute capacity expands"}},
             {"id": "o", "payload": {"title": "Sports results"}}]
    selected = sample_articles(rows, 4, True)
    assert [r["id"] for r in selected] == [0, "p", "c", "o"]
    assert sample_articles(rows, 4, False) == rows[:4]
    assert len(sample_articles(rows, 100, True)) == 23
    assert len({r["id"] for r in sample_articles(rows, 23, True)}) == 23


def test_strata_use_frozen_definitions():
    assert stratum({"title": "Capital funding"}) == "finance"
    assert stratum({"title": "Capital funding"}, {"custom": r"funding"}) == "custom"


def test_sampling_records_actual_age_window(db, linked, tmp_path):
    linked[2](age=20)
    with db.connect() as conn, pytest.raises(ValueError, match="No eligible articles"):
        freeze(conn, tmp_path / "old", stratified=True, max_age_days=14)
    linked[2](age=1)
    with db.connect() as conn:
        receipt = freeze(conn, tmp_path / "new", stratified=True, max_age_days=14, count=10)
    assert receipt["clusters"] == 1 and receipt["requested_clusters"] == 10
    assert sum(receipt["sampling_strata"].values()) == 1
    assert receipt["sampling"] == "TOPIC_ROUND_ROBIN_NOT_PREDICTION_SELECTED"


@pytest.mark.parametrize("age", [0, 31])
def test_invalid_age_window_rejected(db, linked, tmp_path, age):
    with db.connect() as conn, pytest.raises(ValueError):
        freeze(conn, tmp_path / "audit", max_age_days=age)


def test_group_scores_and_selected_unknowns(tmp_path):
    packet = [{"id": str(i), "profile_id": "example", "narrative": {"id": "n"},
               "article": {"title": "Finance project"}} for i in range(3)]
    predictions = {"0": True, "1": False, "2": True}
    write_new(tmp_path / "packet.json", packet)
    write_new(tmp_path / "predictions.json", predictions)
    write_new(tmp_path / "freeze.json", {"packet_sha256": digest(packet),
              "predictions_sha256": digest(predictions), "clusters": 3})
    path = tmp_path / "labels.json"
    write_new(path, {"packet_sha256": digest(packet), "reference_kind": "AI_CONSENSUS_REVIEW",
                    "labels": [{"id": str(i), "relevance": label, "rationale": "Synthetic test"}
                               for i, label in enumerate([
                                   "RELEVANT", "RELEVANT", "INSUFFICIENT_CONTEXT"])]})
    result = evaluate(tmp_path, path)
    assert result["tp"] == result["fn"] == result["selected_unresolved"] == 1
    assert result["precision"] == 1 and result["recall"] == 0.5
    assert result["resolved_fraction"] == 2 / 3
    assert result["by_narrative"]["example:n"]["recall"] == 0.5
    assert result["by_stratum"]["finance"]["unresolved"] == 1
