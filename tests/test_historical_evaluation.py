import json
from datetime import UTC, datetime, timedelta

import pytest

from engine.evaluation.cli import main
from engine.evaluation.historical import Case, Label, Prediction, Split, evaluate, freeze, rate

AT = datetime(2026, 1, 1, tzinfo=UTC)


def case(number=0, **changes):
    at = AT + timedelta(days=number * 10)
    data = dict(
        id=f"case-{number}",
        canonical_key=f"event-{number}",
        event_version=f"v-{number}",
        narrative_version="N01:v1",
        ticker="MU",
        headline="MU synthetic unit test only",
        is_synthetic=True,
        as_of=at,
        narrative_available_at=AT,
        edge_available_at=[AT],
        metric_available_at=[AT],
        evidence=[
            dict(
                url="https://example.invalid/test",
                document_sha256=f"{number:064x}",
                archive_id="test",
                rights="approved",
                rights_reviewer="test-reviewer",
                rights_approved_at=AT,
                published_at=at,
                first_seen_at=at,
                available_at=at,
                retrieved_at=at,
            )
        ],
    )
    return Case.model_validate({**data, **changes})


def label(c, **changes):
    return Label.model_validate(
        dict(
            case_id=c.id,
            reviewer="unit-tester",
            reviewed_at=c.as_of,
            is_new=True,
            is_relevant=True,
            is_material=True,
            valid_path=True,
            hops=2,
            stance="SUPPORTS",
            should_push=True,
            should_digest=False,
            negative_or_irrelevant_or_reprint=False,
            reason="Synthetic unit assertion",
            evidence_urls=[c.evidence[0].url],
            **changes,
        )
    )


def corpus():
    cases = [case(n) for n in range(3)]
    split = Split(
        development_end=AT,
        calibration_end=AT + timedelta(days=10),
        holdout_end=AT + timedelta(days=20),
    )
    labels = [label(c) for c in cases]
    predictions = [
        Prediction(
            case_id=c.id,
            matched=True,
            decision="push",
            policy_version="unit-v1",
            trace_sha256="a" * 64,
        )
        for c in cases
    ]
    return cases, labels, predictions, freeze(cases, split)


@pytest.mark.parametrize(
    "field", ["narrative_available_at", "edge_available_at", "metric_available_at"]
)
def test_future_policy_inputs_rejected(field):
    value = AT + timedelta(seconds=1)
    with pytest.raises(ValueError, match="Future"):
        case(**{field: [value] if field != "narrative_available_at" else value})


@pytest.mark.parametrize(
    "field", ["published_at", "first_seen_at", "available_at", "retrieved_at", "rights_approved_at"]
)
def test_future_source_inputs_rejected(field):
    data = case().model_dump()
    data["evidence"][0][field] = AT + timedelta(seconds=1)
    with pytest.raises(ValueError):
        Case.model_validate(data)


def test_real_dataset_rejects_fixture_url_and_mixed_modes():
    with pytest.raises(ValueError, match="genuine"):
        case(is_synthetic=False)
    cases, _, _, manifest = corpus()
    data = cases[1].model_dump()
    data["is_synthetic"] = False
    data["evidence"][0]["url"] = "https://www.sec.gov/Archives/test-only"
    cases[1] = Case.model_validate(data)
    with pytest.raises(ValueError, match="mix"):
        freeze(cases, Split.model_validate(manifest["split"]))


@pytest.mark.parametrize("kind", ["event", "document"])
def test_canonical_and_document_leakage(kind):
    cases, _, _, manifest = corpus()
    data = cases[1].model_dump()
    if kind == "event":
        data["canonical_key"] = cases[0].canonical_key
    else:
        data["evidence"][0]["document_sha256"] = cases[0].evidence[0].document_sha256
    cases[1] = Case.model_validate(data)
    with pytest.raises(ValueError, match="crosses"):
        freeze(cases, Split.model_validate(manifest["split"]))


def test_frozen_manifest_detects_changes_and_is_order_independent():
    cases, gold, predictions, manifest = corpus()
    assert freeze(list(reversed(cases)), Split.model_validate(manifest["split"])) == manifest
    cases[0] = case(headline="Changed after freeze")
    with pytest.raises(ValueError, match="Frozen"):
        evaluate(cases, gold, predictions, manifest)


@pytest.mark.parametrize(
    "change", ["missing_label", "missing_prediction", "extra_prediction", "duplicate_label"]
)
def test_no_silent_case_exclusions(change):
    cases, gold, predictions, manifest = corpus()
    if change == "missing_label":
        gold.pop()
    elif change == "missing_prediction":
        predictions.pop()
    elif change == "extra_prediction":
        predictions.append(predictions[0].model_copy(update={"case_id": "extra"}))
    else:
        gold.append(gold[0])
    with pytest.raises(ValueError):
        evaluate(cases, gold, predictions, manifest)


def test_metrics_denominators_unknowns_and_holdout():
    cases, gold, predictions, manifest = corpus()
    predictions[2] = predictions[2].model_copy(update={"matched": False, "decision": "suppressed"})
    result = evaluate(cases, gold, predictions, manifest)
    holdout = result["partitions"]["holdout"]["V0"]
    assert holdout["pairs"] == 1
    assert holdout["push"]["fn"] == 1
    assert holdout["push"]["precision"]["value"] is None
    assert holdout["two_hop_match_recall"]["value"] == 0
    assert holdout["cost_usd"]["total"] is None
    assert holdout["factual_error_rate"] is None
    assert result["B1"]["status"] == "UNAVAILABLE"
    assert result["release_decision"] == "NO_GO"
    assert result["partitions"]["holdout"]["B0"]["push"] is None
    assert rate(0, 0)["wilson_95"] is None
    assert rate(9, 10)["wilson_95"][0] < 0.9 < rate(9, 10)["wilson_95"][1]


def test_unrelated_label_citation_and_policy_mixing_rejected():
    cases, gold, predictions, manifest = corpus()
    gold[0] = gold[0].model_copy(update={"evidence_urls": ["https://unrelated.invalid/"]})
    with pytest.raises(ValueError, match="outside"):
        evaluate(cases, gold, predictions, manifest)
    gold[0] = label(cases[0])
    predictions[0] = predictions[0].model_copy(update={"policy_version": "another"})
    with pytest.raises(ValueError, match="one frozen policy"):
        evaluate(cases, gold, predictions, manifest)


def test_cli_workspace_freeze_label_template_and_report(tmp_path, monkeypatch):
    def run(*args):
        monkeypatch.setattr("sys.argv", ["evaluation", *map(str, args)])
        main()

    workspace = tmp_path / "dataset"
    run("init", workspace)
    assert json.loads((workspace / "status.json").read_text())["historical_events"] == 0
    cases, gold, predictions, manifest = corpus()
    case_path = workspace / "cases.jsonl"
    case_path.write_text("\n".join(c.model_dump_json() for c in cases))
    split_path = workspace / "split.json"
    split_path.write_text(json.dumps(manifest["split"]))
    frozen = workspace / "manifest.json"
    run("freeze", "--cases", case_path, "--split", split_path, "--output", frozen)
    with pytest.raises(SystemExit):
        run("freeze", "--cases", case_path, "--split", split_path, "--output", frozen)
    template = workspace / "labels-template.jsonl"
    run("label-template", "--cases", case_path, "--output", template)
    assert json.loads(template.read_text().splitlines()[0])["should_push"] is None
    label_path = workspace / "labels.jsonl"
    label_path.write_text("\n".join(g.model_dump_json() for g in gold))
    prediction_path = workspace / "predictions.json"
    prediction_path.write_text(
        json.dumps(
            {
                "dataset_sha256": manifest["dataset_sha256"],
                "items": [p.model_dump(mode="json") for p in predictions],
            }
        )
    )
    output = workspace / "report.json"
    run(
        "evaluate",
        "--cases",
        case_path,
        "--labels",
        label_path,
        "--predictions",
        prediction_path,
        "--manifest",
        frozen,
        "--output",
        output,
    )
    assert json.loads(output.read_text())["is_synthetic"] is True


def test_event_negative_composition_does_not_count_irrelevant_pairs_as_negative_events():
    cases, gold, predictions, manifest = corpus()
    extra = case(id="extra-pair", narrative_version="N02:v1")
    cases.append(extra)
    gold.append(
        label(extra).model_copy(
            update={
                "is_relevant": False,
                "should_push": False,
                "negative_or_irrelevant_or_reprint": True,
            }
        )
    )
    predictions.append(
        predictions[0].model_copy(
            update={"case_id": extra.id, "matched": False, "decision": "suppressed"}
        )
    )
    manifest = freeze(cases, Split.model_validate(manifest["split"]))
    result = evaluate(cases, gold, predictions, manifest)
    assert result["events"] == 3 and result["pairs"] == 4
    assert result["corpus_checks"]["30_percent_negatives"] is False


def test_empty_duplicate_pairs_and_unmeasured_values_fail_closed():
    cases, _, _, manifest = corpus()
    split = Split.model_validate(manifest["split"])
    with pytest.raises(ValueError, match="empty"):
        freeze([], split)
    with pytest.raises(ValueError, match="Repeated"):
        freeze([*cases, case(id="different-id")], split)
    with pytest.raises(ValueError):
        Prediction(
            case_id="test",
            matched=True,
            decision="push",
            policy_version="unit",
            trace_sha256="a" * 64,
            cost_usd=float("nan"),
        )
