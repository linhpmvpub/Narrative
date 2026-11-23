"""Synthetic archive provenance, exposure and stage-isolation checks."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal as seal_profile

from engine.company_profiles import ProfileBundle
from engine.evaluation.archived_profile_relevance import (
    evaluate,
    freeze,
    select_passages,
    text_prediction,
)
from engine.ingestion.contracts import digest


@pytest.fixture
def archive(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    text = ("TSMC supplies processors to the example issuer under a manufacturing agreement. "
            "The company discusses capacity allocation, delivery delays and the uncertainty "
            "of receiving enough components to meet customer requirements.")
    raw = ("<p>" + text + "</p>").encode()
    (root / "source.html").write_bytes(raw)
    collection = {"sources": [{"file": "source.html", "source_sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": datetime.now(UTC).isoformat(), "filing_date": "2023-01-01",
        "ticker": "TEST", "cluster_key": "TEST:2022"}]}
    (root / "collection.json").write_text(json.dumps(collection))
    (root / "blind-input.json").write_text(json.dumps({"cases": [{"passages": []}]}))
    seal(root)
    return root, text


def seal(root):
    receipt = {key: hashlib.sha256((root / name).read_bytes()).hexdigest()
               for name, key in (("collection.json", "collection_sha256"),
                                 ("blind-input.json", "packet_sha256"))}
    (root / "freeze-receipt.json").write_text(json.dumps(receipt))


def test_archive_sampling_preserves_text_and_underfill(archive):
    root, text = archive
    rows, _, _ = select_passages(root, 24)
    assert len(rows) == 1 and rows[0]["article"]["summary"] == text
    assert rows[0]["sampling_stratum"] == "named_party"


@pytest.mark.parametrize("fault", ["source", "receipt", "escape", "future", "exposed"])
def test_rejects_corruption_clock_escape_and_exposed_text(archive, fault):
    root, text = archive
    if fault == "source":
        (root / "source.html").write_text("changed")
    elif fault == "receipt":
        (root / "collection.json").write_text('{}')
    elif fault == "exposed":
        (root / "blind-input.json").write_text(json.dumps({"cases": [
            {"passages": [{"text": text}]}]}))
        seal(root)
    else:
        data = json.loads((root / "collection.json").read_text())
        data["sources"][0]["file" if fault == "escape" else "retrieved_at"] = (
            "../outside.html" if fault == "escape" else "2999-01-01T00:00:00+00:00")
        (root / "collection.json").write_text(json.dumps(data))
        seal(root)
    with pytest.raises(ValueError):
        select_passages(root, 24)


def test_text_stage_does_not_invent_profile_bindings(dossier):
    _, data = dossier
    bundle = ProfileBundle.model_validate(data)
    assert not text_prediction(bundle, bundle.narratives[0],
                               {"title": "TSMC supplies chips", "summary": ""}, datetime.now(UTC))


def test_freeze_is_separate_immutable_text_challenge(archive, dossier, tmp_path, monkeypatch):
    root, _ = archive
    profile_root, data = dossier
    data["factor_bindings"] = [{"id": "sample", "factor_id": "f", "topic_terms": ["TSMC"],
        "context_terms": ["capacity"], "change_terms": ["delays"],
        "scope": "Synthetic benchmark", "reviewed_at": data["available_at"],
        "review_until": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "evidence": data["relationships"][0]["evidence"]}]
    seal_profile(profile_root, data)
    registry = tmp_path / "profiles"
    registry.mkdir()
    profile_root.rename(registry / "example")
    monkeypatch.setenv("COMPANY_PROFILE_ROOT", str(registry))
    output = tmp_path / "result"
    receipt = freeze(root, output, 24)
    packet = json.loads((output / "packet.json").read_text())
    prediction = json.loads((output / "predictions.json").read_text())
    assert receipt["strict_production_replay_eligible"] is False
    assert receipt["clusters"] == 1 and receipt["packet_sha256"] == digest(packet)
    assert receipt["predictions_sha256"] == digest(prediction)
    assert any(prediction.values())
    assert all("prediction" not in row and "factor_bindings" not in row for row in packet)
    assert packet[0]["document_previously_exposed"] is True
    labels = output / "labels.json"
    labels.write_text(json.dumps({"packet_sha256": digest(packet),
        "reference_kind": "AI_DEVELOPMENT_REVIEW", "labels": [
            {"id": row["id"], "relevance": "RELEVANT", "rationale": "Synthetic test"}
            for row in packet]}))
    result = evaluate(output, labels)
    assert result["tp"] >= 1 and result["strict_production_replay_eligible"] is False
    assert "by_topic_stratum" in result and "Latest-URL" not in str(result["limitations"])
    with pytest.raises(FileExistsError):
        freeze(root, output, 24)
