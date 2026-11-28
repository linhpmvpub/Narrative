import json
from datetime import UTC, datetime

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal

from engine.company_profiles import ProfileBundle
from engine.evaluation import benchmark as b
from engine.evaluation.quality_gate import gate, relevant


@pytest.fixture
def suite(dossier, tmp_path):
    root, data = dossier
    # Keep output outside the registry tree being fingerprinted.
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    root.rename(profiles / root.name)
    root = profiles / root.name
    bundle = ProfileBundle.model_validate(data)
    row = {"id": "one", "label": "NOT_RELEVANT", "priority": "NONE",
           "ticker": "TEST", "event_cluster": "event1", "groups": ["capacity"], "track": "rss",
           "input": {"profile_id": bundle.id, "narrative": bundle.narratives[0].model_dump(mode="json"),
                     "article": {"title": "Unrelated exhibition", "summary": "A public event."}}}
    rows, reference = tmp_path / "rows.json", tmp_path / "reference.json"
    b.write(rows, [row])
    b.write(reference, {"synthetic": True})
    spec, path = tmp_path / "spec.json", tmp_path / "suite.json"
    b.write(spec, {"version": "synthetic-v1", "as_of": datetime.now(UTC).isoformat(),
                  "limitations": ["Synthetic integrity test"], "cohorts": [
                      {"id": "tiny", "rows": str(rows), "provenance": [str(reference)]}]})
    expected = b.create(spec, path)["suite_sha256"]
    return path, expected, profiles, tmp_path / "run", root, data


def test_actual_run_check_and_same_pair_comparison(suite):
    path, expected, profiles, output, _, _ = suite
    result = b.run(path, expected, profiles, output)
    assert result["cohorts"]["tiny"]["relevance"]["overall"]["tn"] == 1
    assert result["cohorts"]["tiny"]["priority"]["overall"]["tn"] == 1
    assert b.check(path, expected, profiles, output)["current"]
    pointer = path.with_name("pointer.json")
    b.write(pointer, dict(suite=str(path), suite_sha256=expected, profiles=str(profiles), run=str(output)))
    assert gate(pointer)["current"]
    second = b.run(path, expected, profiles, output.with_name("second"), output)
    assert second["comparison"]["changes"] == []
    with pytest.raises(ValueError, match="immutable"):
        b.run(path, expected, profiles, output)


@pytest.mark.parametrize("fault", ["source", "database", "runtime", "labels", "report", "suite"])
def test_stale_and_tampered_inputs_fail_closed(suite, monkeypatch, fault):
    path, expected, profiles, output, root, data = suite
    b.run(path, expected, profiles, output)
    if fault == "source":
        (root / "source.html").write_text("modified evidence")
    elif fault == "database":
        data["description"] = "New profile content"
        seal(root, data)
    elif fault == "runtime":
        monkeypatch.setattr(b, "runtime_fingerprint", lambda: {"changed.py": "new"})
    else:
        target = {"labels": path.parent / "rows.json", "report": output / "report.json", "suite": path}[fault]
        target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError):
        b.check(path, expected, profiles, output)


def test_target_change_requires_new_suite(suite):
    path, expected, profiles, output, root, data = suite
    data["narratives"][0]["scope"] = "Different evaluation question"
    seal(root, data)
    with pytest.raises(ValueError, match="target changed"):
        b.run(path, expected, profiles, output)
    assert not output.exists()


def test_priority_is_not_relevance_and_unknowns_are_preserved():
    rows = [dict(id="a", ticker="RENAMED", groups=["UNKNOWN"], event_cluster="x",
                 label="RELEVANT", priority="CONTEXT", selected=True, main=True),
            dict(id="b", ticker="RENAMED", groups=["policy"], event_cluster="x",
                 label="INSUFFICIENT_CONTEXT", priority="INSUFFICIENT_CONTEXT", selected=True, main=True)]
    assert b.dimension(rows, "relevance")["overall"]["tp"] == 1
    score = b.dimension(rows, "priority")
    assert score["overall"]["fp"] == 1 and score["overall"]["selected_unresolved"] == 1
    assert "RENAMED" in score["by_company"] and "UNKNOWN" in score["by_group"]
    assert b.dimension([{**rows[0], "priority": None}], "priority")["status"].startswith("NOT_MEASURED")


def test_changed_decisions_show_costs_not_just_net_counts():
    row = dict(id="x", ticker="TEST", groups=["policy"], event_cluster="x", track="rss",
               label="RELEVANT", priority="CONTEXT", selected=False, main=False)
    result = b.comparison({"c": [row]}, {"c": [{**row, "selected": True, "main": True}]})
    assert result["improvements"] == result["regressions"] == 1
    with pytest.raises(ValueError, match="Reference changed"):
        b.comparison({"c": [row]}, {"c": [{**row, "label": "NOT_RELEVANT"}]})


def test_mid_run_change_does_not_publish_result(suite, monkeypatch):
    path, expected, profiles, output, _, _ = suite
    predict = b.predict
    def mutate(*args):
        monkeypatch.setattr(b, "runtime_fingerprint", lambda: {"mutated": "yes"})
        return predict(*args)
    monkeypatch.setattr(b, "predict", mutate)
    with pytest.raises(ValueError, match="during benchmark"):
        b.run(path, expected, profiles, output)
    assert not output.exists()


def test_full_body_cache_pin_and_environment_restore(suite, monkeypatch):
    path, expected, _, _, _, _ = suite
    spec = b.read(path.parent / "spec.json")
    cache = path.parent / "articles"
    cache.mkdir()
    (cache / "body.txt").write_text("Synthetic source")
    spec["cohorts"][0]["article_dir"] = str(cache)
    (path.parent / "spec.json").write_text(json.dumps(spec))
    new = path.with_name("new-suite.json")
    expected = b.create(path.parent / "spec.json", new)["suite_sha256"]
    (cache / "body.txt").write_text("Changed source")
    with pytest.raises(ValueError, match="source cache"):
        b.load_suite(new, expected)
    monkeypatch.setenv("SEND_NOTIFICATIONS", "true")
    with b.local_environment():
        assert b.os.environ["SEND_NOTIFICATIONS"] == "false"
    assert b.os.environ["SEND_NOTIFICATIONS"] == "true"


def test_commit_gate_scope_includes_data_config_and_dependencies():
    assert all(relevant(p) for p in ["engine/profile_news.py", "config/core-profile-v1.json",
                                    "requirements-validated.txt", "pyproject.toml"])
    assert not relevant("codex/CHECKPOINT.md")
    assert not relevant("reports/quality-benchmark-review.json")
