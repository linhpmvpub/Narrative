"""Synthetic one-step constraints, not independent evaluation of LLM knowledge."""

import copy
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier

from engine.impact_atlas import snapshot
from engine.knowledge_priors import Rule, build, install, load_rules, lookup, read


@pytest.fixture
def atlas(dossier):
    root, _ = dossier
    data = snapshot(root.parent)
    edge = copy.deepcopy(data["relations"][0])
    edge.update(
        type="USES_INPUT",
        basis="SOURCE_REPORTED",
        status="SOURCE_BACKED",
        eligible_at_snapshot=True,
    )
    nodes = {n["id"]: n for n in data["nodes"]}
    nodes[edge["to_id"]]["kind"] = "input"
    data["relations"] = [edge]
    return data


def test_fill_missing_without_promoting_or_overwriting_atlas(atlas):
    original = copy.deepcopy(atlas)
    bundle = build(atlas, load_rules(), author="synthetic-LLM")
    assert atlas == original
    assert len(bundle["priors"]) == 1
    row = bundle["priors"][0]
    assert row["status"] == "LLM_PRIOR_UNVERIFIED" and row["inference_steps"] == 1
    assert row["lower"] is None and row["upper"] is None
    assert not row["can_be_inference_premise"] and not row["verified_impact"]
    assert (
        lookup(bundle, atlas, row["relation_id"], row["dimension"])["origin"]
        == "LLM_PRIOR_UNVERIFIED"
    )


@pytest.mark.parametrize("status", ["SOURCED", "DISPUTED", "NOT_APPLICABLE"])
def test_existing_data_wins_and_is_not_filled(atlas, status):
    edge = atlas["relations"][0]
    exp = next(e for e in atlas["exposures"] if e["relation_id"] == edge["id"])
    exp["dimensions"]["input_cost_sensitivity"] = {"status": status, "value": "existing"}
    bundle = build(atlas, load_rules(), author="test")
    assert not bundle["priors"]
    assert lookup(bundle, atlas, edge["id"], "input_cost_sensitivity")["origin"] == "ATLAS"


@pytest.mark.parametrize(
    "change",
    [
        {"status": "CANDIDATE"},
        {"basis": "CONDITIONAL_MECHANISM"},
        {"basis": "LLM_PRIOR_UNVERIFIED"},
        {"eligible_at_snapshot": False},
        {"evidence": []},
        {"valid_until": "2020-01-01T00:00:00+00:00"},
    ],
)
def test_no_inference_from_inference_or_ineligible_premise(atlas, change):
    atlas["relations"][0].update(change)
    assert not build(atlas, load_rules(), author="test")["priors"]


def test_prior_database_cannot_be_used_as_atlas(atlas):
    bundle = build(atlas, load_rules(), author="test")
    with pytest.raises(ValueError):
        # Explicit schema prevents priors being reused as source facts.
        build({**bundle, "as_of": bundle["created_at"]}, load_rules(), author="test")


def test_changed_atlas_and_tampered_derivation_are_not_consumed(atlas):
    bundle = build(atlas, load_rules(), author="test")
    row = bundle["priors"][0]
    newer = copy.deepcopy(atlas)
    newer["relations"][0]["status"] = "WITHDRAWN"
    assert lookup(bundle, newer, row["relation_id"], row["dimension"])["origin"] == "UNKNOWN"
    bundle["priors"][0]["inference_steps"] = 2
    with pytest.raises(ValueError, match="one-step"):
        lookup(bundle, atlas, row["relation_id"], row["dimension"])


def test_conflicting_rules_do_not_win_by_order(atlas):
    rules = load_rules()
    other = rules[0].model_copy(update={"id": "alternative", "category": "DIFFERENT"})
    with pytest.raises(ValueError, match="Conflicting"):
        build(atlas, [rules[0], other], author="test")


@pytest.mark.parametrize(
    "change", [{"common_knowledge": False}, {"clarity": "AMBIGUOUS"}, {"knowledge_basis": "guess"}]
)
def test_uncommon_or_vague_rule_is_rejected(change):
    raw = load_rules()[0].model_dump(mode="json")
    with pytest.raises(ValueError):
        Rule.model_validate({**raw, **change})


def numeric_rule():
    raw = load_rules()[0].model_dump(mode="json")
    # Synthetic interval contract only. This is not a real BOM or production default.
    return {
        **raw,
        "dimension": "exposure_share",
        "unit": "fraction",
        "category": None,
        "lower": "0.2",
        "upper": "0.4",
        "denominator": "Synthetic total product input cost",
        "estimation_method": "Synthetic fixture interval from an explicitly declared representative product recipe, not company disclosures.",
    }


def test_numeric_interval_keeps_denominator_and_estimation_label(atlas):
    bundle = build(atlas, [numeric_rule()], author="synthetic")
    row = bundle["priors"][0]
    assert (row["lower"], row["upper"]) == ("0.2", "0.4")
    assert row["denominator"] and row["status"] == "LLM_PRIOR_UNVERIFIED"
    assert "value" not in row


@pytest.mark.parametrize(
    "change",
    [
        {"lower": "NaN"},
        {"upper": "1.1"},
        {"lower": "0.4"},
        {"denominator": None},
        {"estimation_method": None},
    ],
)
def test_invalid_or_unexplained_numeric_estimate_is_rejected(change):
    with pytest.raises(ValueError):
        Rule.model_validate({**numeric_rule(), **change})


def test_old_prior_not_available_before_knowledge_or_after_expiry(atlas):
    old = datetime.now(UTC) - timedelta(days=100)
    atlas["as_of"] = old.isoformat()
    edge = atlas["relations"][0]
    edge["known_at"] = (old - timedelta(days=1)).isoformat()
    edge["valid_from"] = (old - timedelta(days=1)).isoformat()
    bundle = build(atlas, load_rules(), author="test", at=old)
    row = bundle["priors"][0]
    assert lookup(bundle, atlas, row["relation_id"], row["dimension"])["origin"] == "UNKNOWN"


def test_local_sqlite_export_keeps_priors_separate_and_immutable(atlas, tmp_path):
    bundle = build(atlas, load_rules(), author="test")
    output = tmp_path / "priors"
    assert install(bundle, output)["priors"] == 1
    with sqlite3.connect(output / "priors.db") as conn:
        row = json.loads(conn.execute("SELECT payload FROM priors").fetchone()[0])
        assert row["status"] == "LLM_PRIOR_UNVERIFIED"
    assert json.loads((output / "priors.json").read_text()) == bundle
    assert read(output) == bundle
    with pytest.raises(FileExistsError):
        install(bundle, output)
    (output / "priors.db").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact changed"):
        read(output)
