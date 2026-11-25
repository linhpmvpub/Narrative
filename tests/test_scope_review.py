"""Synthetic operator votes only; these tests are not independent labels or accuracy evidence."""

import copy
import hashlib
import os
from datetime import UTC, datetime, timedelta

import pytest
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_structured_news import grounded as grounded
from test_structured_news import replace_article
from test_structured_scope import identified as identified

from engine.impact_atlas import snapshot
from engine.impact_events import EventFrame, assess
from engine.ingestion.contracts import digest
from engine.mechanism_playbook import evaluate, load
from engine.scope_review import Proposal, Store, check


@pytest.fixture
def scoped(identified, tmp_path):
    return make_scoped(identified, tmp_path)


def make_scoped(
    identified,
    tmp_path,
    quote="Alpha Foundry raised prices for wafers from Fab A in Texas during 2026.",
):
    root, profile, selection, _ = identified
    raw = (root / "source.html").read_bytes() + ("<p>" + quote + "</p>").encode()
    (root / "source.html").write_bytes(raw)
    profile["sources"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    profile["relationships"][1]["evidence"] = [{"source_id": "s", "quote": quote}]
    profile["entity_references"][0]["evidence"] = [{"source_id": "s", "quote": quote}]
    seal(root, profile)
    selection = replace_article(selection, quote)
    data = snapshot(os.environ["COMPANY_PROFILE_ROOT"])
    frame = EventFrame(
        id="synthetic-scope",
        version=1,
        mechanism_id="input_price",
        factor_id="example/supplier",
        direction="UP",
        phase="OPERATING",
        scope="synthetic",
        source_quote=quote,
        selection_sha256=digest(selection),
        available_at=datetime.now(UTC),
        reviewed_at=datetime.now(UTC),
        reviewer_id="extractor",
        reviewer_kind="AI_OPERATOR",
    )
    path = assess(data, frame, selection)["paths"][0]
    book = load()
    store = Store(tmp_path / "reviews.sqlite", create=True)
    store.append(
        "source",
        selection["revision"]["id"],
        {
            "packet_sha256": selection["packet_sha256"],
            "status": "CURRENT",
            "observed_at": datetime.now(UTC).isoformat(),
        },
    )
    now = datetime.now(UTC)
    proposal = dict(
        id="synthetic",
        author_id="author",
        event_sha256=digest(frame.model_dump(mode="json")),
        selection_sha256=digest(selection),
        atlas_sha256=digest(data),
        playbook_sha256=digest(book),
        source_epoch=1,
        narrative_id=path["narrative_id"],
        route=path["relations"],
        identity_reference_id="example/actor-ref",
        source_id="example/s",
        exposure_quote=quote,
        facets={
            k: {"event_term": v, "exposure_term": v}
            for k, v in {
                "legal_entity": "Alpha Foundry",
                "product": "wafers",
                "facility": "Fab A",
                "geography": "Texas",
                "period": "2026",
            }.items()
        },
        effective_from=(now - timedelta(minutes=2)).isoformat(),
        effective_until=(now - timedelta(minutes=1)).isoformat(),
        created_at=now.isoformat(),
        review_until=(now + timedelta(days=1)).isoformat(),
    )
    policy = {"reviewers": {"synthetic-a": "AI_INDEPENDENT", "synthetic-b": "AI_INDEPENDENT"}}
    review = dict(
        proposal=proposal,
        votes=[
            dict(
                reviewer_id=r,
                proposal_sha256=digest(proposal),
                decision="APPROVE",
                reviewed_at=now.isoformat(),
            )
            for r in policy["reviewers"]
        ],
        status="REVIEWED",
        recorded_at=now.isoformat(),
    )
    return store, policy, data, frame, selection, path, book, review


def record_and_check(values):
    store, policy, data, frame, selection, path, book, review = values
    # Re-pin after deliberate proposal mutation, so tests exercise semantic gates.
    for v in review["votes"]:
        v["proposal_sha256"] = digest(
            Proposal.model_validate(review["proposal"]).model_dump(mode="json")
        )
    store.append("review", "synthetic", review)
    return check(store, "synthetic", policy, data, frame, selection, path, book, datetime.now(UTC))


def test_source_to_scope_to_rules(scoped):
    assert record_and_check(scoped)["status"] == "PASS"
    store, policy, data, frame, selection, path, book, _ = scoped
    result = evaluate(
        data,
        frame,
        selection,
        "input_price.spot",
        scope_store=store,
        reviewer_policy=policy,
        scope_reviews={digest([path["narrative_id"], path["relations"]]): "synthetic"},
    )
    assert result["decision_trace"][4]["result"] == "PASS"
    assert result["first_unmet_rule"] == "R06"
    assert result["decision_trace"][6]["result"] == "UNKNOWN"
    assert result["financial_magnitude"] == "UNKNOWN" and result["delivery"] == "disabled"
    assert not result["scope_reviews"][0]["human_gold"]


@pytest.mark.parametrize(
    "fault",
    [
        "event",
        "atlas",
        "book",
        "selection",
        "route",
        "narrative",
        "identity",
        "facet_missing",
        "facet_mismatch",
        "substring",
        "interval",
        "expiry",
        "revoked",
        "one_vote",
        "duplicate",
        "self",
        "extractor",
        "reject",
        "unauthorized",
        "bad_policy",
    ],
)
def test_invalid_reviews_fail_closed(scoped, fault):
    store, policy, data, frame, selection, path, book, review = scoped
    p = review["proposal"]
    hashes = {
        "event": "event_sha256",
        "atlas": "atlas_sha256",
        "book": "playbook_sha256",
        "selection": "selection_sha256",
    }
    if fault in hashes:
        p[hashes[fault]] = "0" * 64
    elif fault == "route":
        p["route"] = ["wrong"]
    elif fault == "narrative":
        p["narrative_id"] = "wrong"
    elif fault == "identity":
        p["identity_reference_id"] = "wrong"
    elif fault == "facet_missing":
        del p["facets"]["facility"]
    elif fault == "facet_mismatch":
        p["facets"]["product"]["event_term"] = "Texas"
    elif fault == "substring":
        p["facets"]["period"] = {"event_term": "202", "exposure_term": "202"}
    elif fault == "interval":
        p["effective_from"] = "2000-01-01T00:00:00+00:00"
    elif fault == "expiry":
        p["review_until"] = p["created_at"]
    elif fault == "revoked":
        review["status"] = "REVOKED"
    elif fault == "one_vote":
        review["votes"].pop()
    elif fault == "duplicate":
        review["votes"][1] = copy.deepcopy(review["votes"][0])
    elif fault == "self":
        p["author_id"] = "synthetic-a"
    elif fault == "extractor":
        review["votes"][0]["reviewer_id"] = "extractor"
    elif fault == "reject":
        review["votes"][0]["decision"] = "REJECT"
    elif fault == "unauthorized":
        policy["reviewers"].pop("synthetic-a")
    elif fault == "bad_policy":
        policy["reviewers"] = []
    with pytest.raises(ValueError):
        record_and_check(scoped)


@pytest.mark.parametrize("status", ["WITHDRAWN", "DISPUTED", "CURRENT"])
def test_source_new_epoch_invalidates_old_review_even_if_same_packet(scoped, status):
    record_and_check(scoped)
    store, policy, data, frame, selection, path, book, _ = scoped
    sid = selection["revision"]["id"]
    old = store.history("source", sid)[-1]
    store.append("source", sid, {**old["payload"], "status": status}, expected_head=old["sha256"])
    with pytest.raises(ValueError, match="Source changed"):
        check(store, "synthetic", policy, data, frame, selection, path, book, datetime.now(UTC))


def test_ledger_stale_write_tamper_and_revocation(scoped):
    record_and_check(scoped)
    store, policy, data, frame, selection, path, book, review = scoped
    with pytest.raises(ValueError, match="Stale"):
        store.append("review", "synthetic", review)
    old = store.history("review", "synthetic")[-1]
    review["status"] = "REVOKED"
    store.append("review", "synthetic", review, expected_head=old["sha256"])
    assert len(store.history("review", "synthetic")) == 2
    with pytest.raises(ValueError):
        check(store, "synthetic", policy, data, frame, selection, path, book, datetime.now(UTC))
    conn = store.connect()
    with conn:
        conn.execute("UPDATE records SET payload='{}' WHERE kind='review' AND version=1")
    conn.close()
    with pytest.raises(ValueError, match="integrity"):
        store.history("review", "synthetic")


def test_unreviewed_other_path_and_concurrent_change_hold_gate(scoped, monkeypatch):
    record_and_check(scoped)
    store, policy, data, frame, selection, path, book, _ = scoped
    base = assess(data, frame, selection)
    base["paths"].append({**path, "narrative_id": "other"})
    monkeypatch.setattr("engine.mechanism_playbook.assess", lambda *a, **kw: base)
    args = dict(
        scope_store=store,
        reviewer_policy=policy,
        scope_reviews={digest([path["narrative_id"], path["relations"]]): "synthetic"},
    )
    result = evaluate(data, frame, selection, "input_price.spot", **args)
    assert result["first_unmet_rule"] == "R05"
    assert [r["status"] for r in result["scope_reviews"]] == ["PASS", "UNKNOWN"]
    fingerprints = iter(["before", "after"])
    monkeypatch.setattr(store, "fingerprint", lambda: next(fingerprints))
    result = evaluate(data, frame, selection, "input_price.spot", **args)
    assert all(r["reason"] == "LEDGER_CHANGED_DURING_EVALUATION" for r in result["scope_reviews"])


def test_vote_hash_must_cover_canonical_proposal(scoped):
    store, policy, data, frame, selection, path, book, review = scoped
    review["votes"][0]["proposal_sha256"] = "0" * 64
    store.append("review", "synthetic", review)
    with pytest.raises(ValueError, match="vote"):
        check(store, "synthetic", policy, data, frame, selection, path, book, datetime.now(UTC))


def test_fully_populated_context_does_not_approve_financial_impact(scoped, monkeypatch):
    record_and_check(scoped)
    store, policy, data, frame, selection, path, book, _ = scoped
    monkeypatch.setattr(
        "engine.mechanism_playbook.inventory",
        lambda *a: [
            {"relation_id": path["relations"][0], "mechanism_id": "input_price", "missing": []}
        ],
    )
    result = evaluate(
        data,
        frame,
        selection,
        "input_price.spot",
        scope_store=store,
        reviewer_policy=policy,
        scope_reviews={digest([path["narrative_id"], path["relations"]]): "synthetic"},
    )
    assert result["first_unmet_rule"] == "R07"
    assert result["financial_magnitude"] == "UNKNOWN"


def test_proposal_hash_cli_uses_normalized_serialization(scoped, monkeypatch, capsys, tmp_path):
    import json

    from engine.scope_review import main

    proposal = scoped[-1]["proposal"]
    path = tmp_path / "proposal.json"
    path.write_text(json.dumps(proposal), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["scope_review", "proposal-hash", "--input", str(path)])
    main()
    assert json.loads(capsys.readouterr().out)["proposal_sha256"] == digest(
        Proposal.model_validate(proposal).model_dump(mode="json")
    )
