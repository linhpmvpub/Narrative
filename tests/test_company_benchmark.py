"""Freeze integrity, separate company truth and repeatable regression reporting."""

from copy import deepcopy

import pytest
from test_company_discovery import discovery as discovery
from test_company_profiles import dossier as dossier

from engine.evaluation import company_benchmark as cb
from engine.evaluation.benchmark import read, write


@pytest.fixture
def benchmark(discovery, tmp_path):
    root, data, _ = discovery
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    root.rename(profiles / root.name)
    rows = [{"id": str(i), "ticker": data["ticker"], "event_cluster": str(i),
             "input": {"profile_id": data["id"], "article": {"title": title, "summary": ""}}}
            for i, title in enumerate(["Fjord reports financial results", "Community festival opens"])]
    source = tmp_path / "source.json"
    write(source, {"synthetic": True})
    freeze = tmp_path / "freeze"
    sha = cb.freeze(rows, profiles, freeze, provenance=[source])["sha256"]
    reviews = []
    for name in ("reviewer-a", "reviewer-b"):
        path = tmp_path / (name + ".json")
        write(path, {"reviewer_id": name, "reviewer_kind": "AI",
            "packet_sha256": read(freeze / "freeze.json")["review_packet_sha256"],
            "labels": [{"id": str(i), "relevance": "RELEVANT" if i == 0 else "NOT_RELEVANT",
                        "priority": "PRIORITY" if i == 0 else "NONE", "groups": ["other"],
                        "rationale": "Synthetic reference."} for i in range(2)]})
        reviews.append(path)
    reference = tmp_path / "reference.json"
    refsha = cb.reference(freeze, sha, reviews, reference)["sha256"]
    return {"freeze": str(freeze), "freeze_sha256": sha, "reference": str(reference),
            "reference_sha256": refsha, "profiles": str(profiles), "run": str(tmp_path / "run")}


def execute(p, **kw):
    return cb.run(p["freeze"], p["freeze_sha256"], p["reference"], p["reference_sha256"],
                  p["profiles"], p["run"], **kw)


def test_company_benchmark_matches_locked_predictions_and_gate(benchmark):
    p = benchmark
    result = execute(p)
    assert result["score"] == 100 and not result["comparison"]["changes"]
    assert result["dimensions"]["relevance"]["overall"]["tp"] == 1
    assert cb.check(p)["current"]
    later = {**p, "run": p["run"] + "-later"}
    assert execute(later, baseline=p["run"])["comparison"]["changes"] == []
    with pytest.raises(ValueError, match="Immutable"):
        execute(p)


@pytest.mark.parametrize("kind", ["freeze", "source", "labels", "review", "outputs", "runtime"])
def test_company_benchmark_fails_on_changed_evidence(benchmark, kind, monkeypatch):
    from pathlib import Path

    p = benchmark
    execute(p)
    root = Path(p["freeze"]).parent
    if kind == "runtime":
        original = cb.state
        def changed(*args):
            data, bundles = original(*args)
            return {**data, "runtime": {}}, bundles
        monkeypatch.setattr(cb, "state", changed)
    else:
        path = {"freeze": root / "freeze/freeze.json", "source": root / "source.json",
                "labels": root / "reference.json", "review": root / "reviewer-a.json",
                "outputs": root / "run/report.json"}[kind]
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        cb.check(p)


def test_unknowns_are_not_negative_truth_or_rescaled_score():
    rows = [{"id": "1", "ticker": "TEST", "event_cluster": "e"}]
    pred = [{"id": "1", "selected": True, "priority": True}]
    labels = [{"id": "1", "relevance": "INSUFFICIENT_CONTEXT", "priority": "INSUFFICIENT_CONTEXT", "groups": ["UNKNOWN"]}]
    result = cb.score(rows, pred, labels)
    assert result["score"] is None and result["reference_ceiling"] == 0
    assert result["dimensions"]["relevance"]["overall"]["unresolved"] == 1
    assert result["dimensions"]["relevance"]["overall"]["fp"] == 0


def test_combined_gate_requires_current_company_reference(benchmark, monkeypatch, tmp_path):
    from engine.evaluation import quality_gate

    execute(benchmark)
    monkeypatch.setattr(quality_gate, "check", lambda *args: {"current": True})
    pointer = tmp_path / "pointer.json"
    write(pointer, {"suite": "legacy", "suite_sha256": "legacy", "profiles": "legacy",
                    "run": "legacy", "company_benchmark": benchmark})
    assert quality_gate.gate(pointer)["company_benchmark"]["current"]
    reference = tmp_path / "reference.json"
    reference.write_bytes(reference.read_bytes() + b" ")
    with pytest.raises(ValueError):
        quality_gate.gate(pointer)


@pytest.mark.parametrize("fault", ["peer_identity", "missing", "duplicate", "priority", "packet"])
def test_reviews_must_be_complete_distinct_and_consistent(benchmark, fault, tmp_path):
    root = tmp_path
    a, b = read(root / "reviewer-a.json"), read(root / "reviewer-b.json")
    if fault == "peer_identity":
        b["reviewer_id"] = a["reviewer_id"]
    elif fault == "missing":
        b["labels"].pop()
    elif fault == "duplicate":
        b["labels"][1] = deepcopy(b["labels"][0])
    elif fault == "priority":
        b["labels"][1]["priority"] = "PRIORITY"
    else:
        b["packet_sha256"] = "0"*64
    write(root / "changed-review.json", b)
    with pytest.raises(ValueError):
        cb.reference(benchmark["freeze"], benchmark["freeze_sha256"],
                     [root / "reviewer-a.json", root / "changed-review.json"], root / "new-reference.json")
