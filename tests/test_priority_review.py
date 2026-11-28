import copy
import json
import os
from datetime import UTC, datetime

import pytest
from test_profile_relevance import dossier as dossier
from test_profile_relevance import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.evaluation.priority_review import evaluate, freeze, read, validate_review
from engine.evaluation.profile_relevance import freeze as freeze_relevance
from engine.evaluation.profile_relevance import write_new


def make_review(packet, receipt, reviewer):
    return {"reference_kind": "AI_INDEPENDENT_REVIEW", "reviewer_id": reviewer,
            "packet_sha256": receipt["packet_sha256"], "rubric_sha256": receipt["rubric_sha256"],
            "reviewed_at": datetime.now(UTC).isoformat(), "predictions_accessed": False,
            "peer_labels_accessed": False, "labels": [
                {"id": r["id"], "relevance": "RELEVANT", "priority": "CONTEXT",
                 "event_groups": ["input_price"], "rationale": "Synthetic source-backed context; no priority claim."}
                for r in packet]}


@pytest.mark.parametrize("company_scope", [False, True])
def test_dual_labels_disagree_without_discarding_relevance(db, linked, tmp_path, company_scope):
    root = tmp_path / "frozen"
    with db.connect() as conn:
        original = freeze_relevance(conn, root, prediction_track="text_relevance", count=4,
                                    source_quotas={"missing-source": 2}, scan_limit=5000,
                                    profile_root=os.environ["COMPANY_PROFILE_ROOT"])
    assert original["source_quota_shortfalls"] == {"missing-source": 2}
    assert original["clusters"] == 1
    blind = tmp_path / "blind"
    receipt = freeze(root, os.environ["COMPANY_PROFILE_ROOT"], blind, company_scope=company_scope)
    packet = read(root / "packet.json")
    compact = read(blind / "packet.json")
    assert "event_groups_values" in compact["rubric"]
    assert not {"predictions", "factor_bindings", "assessment", "policy"} & compact.keys()
    a, b = make_review(packet, receipt, "a"), make_review(packet, receipt, "b")
    if company_scope:
        assert "company_relevance" in compact["rubric"]
        assert "components" in compact["profiles"][0]
        for review in (a, b):
            review["company_labels"] = [{"id": u["id"], "relevance": "RELEVANT",
                                         "rationale": "Synthetic sourced business event"}
                                        for u in compact["company_units"]]
    b["labels"][0]["priority"] = "PRIORITY"
    for name, review in (("a", a), ("b", b)):
        write_new(blind / (name + ".json"), review)
    result = evaluate(root, [blind / "a.json", blind / "b.json"])
    assert result["relevance_disagreements"] == 0
    assert result["priority_disagreements"] == 1
    assert result["variants"]["matched"]["relevance"]["tp"] == 1
    assert result["variants"]["matched"]["priority"]["unresolved"] == 1
    assert result["promotion"] == "NOT_PROMOTED"
    if company_scope:
        assert read(root / "dual-consensus.json")["company"]["disagreements"] == 0
        path = root / "priority-freeze.json"
        original_bytes = path.read_bytes()
        altered = read(path)
        altered["company_units"][0]["pair_ids"] = []
        path.write_text(json.dumps(altered), encoding="utf-8")
        with pytest.raises(ValueError, match="Frozen company units"):
            evaluate(root, [blind / "a.json", blind / "b.json"])
        path.write_bytes(original_bytes)
    predictions = read(root / "priority-predictions.json")
    predictions[packet[0]["id"]]["broader"] = False
    (root / "priority-predictions.json").write_text(json.dumps(predictions), encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen prediction"):
        evaluate(root, [blind / "a.json", blind / "b.json"])


@pytest.mark.parametrize("fault", ["priority_on_negative", "unknown_group", "wrong_rubric", "pre_freeze"])
def test_review_contract_rejects_unsupported_dimensions(fault):
    packet = [{"id": "one", "cluster": "event"}]
    receipt = {"packet_sha256": "synthetic", "rubric_sha256": "rubric", "at": "2026-01-01T00:00:00+00:00"}
    review = make_review(packet, receipt, "a")
    if fault == "priority_on_negative":
        review["labels"][0].update(relevance="NOT_RELEVANT", priority="PRIORITY")
    elif fault == "unknown_group":
        review["labels"][0]["event_groups"] = ["financial_services"]
    elif fault == "wrong_rubric":
        review["rubric_sha256"] = "changed"
    else:
        review["reviewed_at"] = "2025-01-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        validate_review(review, packet, receipt)


def test_article_groups_cannot_change_across_company_labels():
    packet = [{"id": "one", "cluster": "event"}, {"id": "two", "cluster": "event"}]
    receipt = {"packet_sha256": "synthetic", "rubric_sha256": "rubric", "at": "2026-01-01T00:00:00+00:00"}
    review = make_review(packet, receipt, "a")
    bad = copy.deepcopy(review)
    bad["labels"][1]["event_groups"] = ["financing"]
    with pytest.raises(ValueError, match="across narratives"):
        validate_review(bad, packet, receipt)
    validate_review(review, packet, receipt)


def test_archive_sampling_does_not_expand_live_feed_age(db, linked, tmp_path):
    linked[2](age=120)
    with db.connect() as conn:
        with pytest.raises(ValueError, match="Age window"):
            freeze_relevance(conn, tmp_path / "live", max_age_days=180)
        result = freeze_relevance(conn, tmp_path / "archive", max_age_days=180,
                                  prediction_track="text_relevance")
    assert result["clusters"] == 1 and result["prediction_track"] == "text_relevance"
