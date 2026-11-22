"""Synthetic audit integrity and denominator tests; no real article labels in Git."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_profile_news import linked as linked

from engine.evaluation.profile_relevance import evaluate, freeze, write_new
from engine.ingestion.contracts import digest
from engine.news import register


@pytest.fixture(autouse=True)
def separate_profile_store(linked, tmp_path, monkeypatch):
    # Keep captures/audit output outside the profile registry, as in deployment.
    registry = tmp_path / "profiles"
    registry.mkdir()
    linked[0].rename(registry / "example")
    monkeypatch.setenv("COMPANY_PROFILE_ROOT", str(registry))


def reference(root, relevance="RELEVANT"):
    packet = json.loads((root / "packet.json").read_text())
    data = {"packet_sha256": digest(packet), "reference_kind": "AI_DEVELOPMENT_REVIEW",
            "labels": [{"id": r["id"], "relevance": relevance,
                        "rationale": "Synthetic test judgment"} for r in packet]}
    path = root / "labels.json"
    write_new(path, data)
    return path


def test_freeze_deduplicates_and_omits_predictions(db, linked, tmp_path):
    root = tmp_path / "audit"
    second = {**linked[3], "id": "synthetic_b", "name": "Synthetic RSS B"}
    register(db, [second])
    linked[2](source=second)
    with db.connect() as conn:
        receipt = freeze(conn, root)
        assert receipt["clusters"] == receipt["pairs"] == 1
        with pytest.raises(FileExistsError):
            freeze(conn, root)
    packet = (root / "packet.json").read_text()
    assert '"topic_terms"' not in packet and '"predicted"' not in packet
    assert '"sources"' in packet and '"item_version"' in packet
    result = evaluate(root, reference(root))
    assert result["tp"] == 1 and result["precision"] == result["recall"] == 1
    assert result["independent_gold"] is False


@pytest.mark.parametrize("label", ["NOT_RELEVANT", "INSUFFICIENT_CONTEXT"])
def test_negative_and_unknown_are_not_interchangeable(db, linked, tmp_path, label):
    root = tmp_path / "audit"
    with db.connect() as conn:
        freeze(conn, root)
    result = evaluate(root, reference(root, label))
    if label == "NOT_RELEVANT":
        assert result["fp"] == 1 and result["precision"] == 0 and result["recall"] is None
    else:
        assert result["unresolved"] == 1 and result["tn"] == 0
        assert result["precision"] is None and result["recall"] is None


@pytest.mark.parametrize("fault", ["packet", "predictions", "labels_hash", "duplicate",
                                    "missing", "rationale", "provenance"])
def test_audit_rejects_corrupt_or_incomplete_inputs(db, linked, tmp_path, fault):
    root = tmp_path / "audit"
    with db.connect() as conn:
        freeze(conn, root)
    label_path = reference(root)
    if fault in {"packet", "predictions"}:
        (root / (fault + ".json")).write_text("{}")
    else:
        data = json.loads(label_path.read_text())
        if fault == "labels_hash":
            data["packet_sha256"] = "0" * 64
        elif fault == "duplicate":
            data["labels"] *= 2
        elif fault == "missing":
            data["labels"] = []
        elif fault == "rationale":
            data["labels"][0]["rationale"] = ""
        else:
            data["reference_kind"] = "UNKNOWN"
        label_path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        evaluate(root, label_path)


def test_frozen_scores_survive_later_news_correction(db, linked, tmp_path):
    root = tmp_path / "audit"
    with db.connect() as conn:
        freeze(conn, root)
    labels = reference(root)
    linked[2](title="Unrelated football update", summary="Sports only")
    assert evaluate(root, labels)["tp"] == 1


def test_disabled_feed_cannot_freeze(db, linked, tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "false")
    with db.connect() as conn, pytest.raises(ValueError):
        freeze(conn, tmp_path / "audit")


def test_future_cutoff_rejected(db, linked, tmp_path):
    with db.connect() as conn, pytest.raises(ValueError):
        freeze(conn, tmp_path / "audit", at=datetime.now(UTC) + timedelta(days=1))


def test_conflicting_duplicates_excluded(db, linked, tmp_path):
    second = {**linked[3], "id": "synthetic_b", "name": "Synthetic RSS B"}
    register(db, [second])
    linked[2](source=second, title="Conflicting current version")
    with db.connect() as conn, pytest.raises(ValueError, match="No eligible articles"):
        freeze(conn, tmp_path / "audit")
