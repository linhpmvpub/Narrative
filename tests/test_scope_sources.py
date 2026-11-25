"""Synthetic RSS revision bridge; not publisher withdrawal detection or accuracy evidence."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, update
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_scope_review import scoped as scoped
from test_structured_news import grounded as grounded
from test_structured_scope import identified as identified

from engine.ingestion.contracts import digest
from engine.mechanism_playbook import evaluate
from engine.models.schema_v13 import news_items, news_revisions, news_sources
from engine.news import register, save_rows
from engine.scope_review import Proposal
from engine.scope_sources import inspect, sync


@pytest.fixture
def bound(scoped, db):
    store, policy, data, frame, selection, path, book, review = scoped
    config = {
        "id": "scope-synthetic",
        "name": "Synthetic",
        "kind": "rss",
        "category": "markets",
        "url": "https://publisher.example/feed",
        "interval_seconds": 60,
        "enabled": True,
    }
    register(db, [config])
    revision = selection["revision"]
    iid = digest([config["id"], "one"])
    with db.begin() as conn:
        conn.execute(
            update(news_sources)
            .where(news_sources.c.id == config["id"])
            .values(last_success=datetime.now(UTC))
        )
        conn.execute(
            news_items.insert().values(
                id=iid,
                source_id=config["id"],
                external_id="one",
                first_seen_at=datetime.fromisoformat(revision["received_at"]),
                version=1,
                content_sha256=digest(revision["payload"]),
                article_key=digest(revision["payload"]["url"]),
                payload=revision["payload"],
            )
        )
        conn.execute(
            news_revisions.insert().values(
                id=revision["id"],
                item_id=iid,
                version=1,
                received_at=datetime.fromisoformat(revision["received_at"]),
                capture_sha256="0" * 64,
                payload=revision["payload"],
            )
        )
        sync(store, conn, selection, datetime.now(UTC))
    now = datetime.now(UTC).isoformat()
    review["proposal"].update(source_epoch=2, created_at=now)
    review["recorded_at"] = now
    for vote in review["votes"]:
        vote.update(
            reviewed_at=now,
            proposal_sha256=digest(
                Proposal.model_validate(review["proposal"]).model_dump(mode="json")
            ),
        )
    store.append("review", "synthetic", review)
    return scoped, db, config, iid


def decision(bound, *, conn=None):
    scoped, db, config, iid = bound
    store, policy, data, frame, selection, path, book, review = scoped
    return evaluate(
        data,
        frame,
        selection,
        "input_price.spot",
        scope_store=store,
        reviewer_policy=policy,
        scope_reviews={digest([path["narrative_id"], path["relations"]]): "synthetic"},
        news_conn=conn,
    )


def test_bound_source_passes_without_epoch_churn_and_requires_db(bound):
    scoped, db, _, _ = bound
    store, _, _, _, selection, *_ = scoped
    with db.connect() as conn:
        assert decision(bound, conn=conn)["first_unmet_rule"] == "R06"
        assert decision(bound, conn=conn)["first_unmet_rule"] == "R06"
    assert len(store.history("source", selection["revision"]["id"])) == 2
    assert decision(bound)["first_unmet_rule"] == "R05"


def test_ingestion_correction_invalidates_approval_and_revert_cannot_resurrect(bound):
    scoped, db, config, _ = bound
    store, _, _, _, selection, *_ = scoped
    original = selection["revision"]["payload"]
    for title in ["Corrected synthetic news", original["title"]]:
        with db.begin() as conn:
            source = (
                conn.execute(select(news_sources).where(news_sources.c.id == config["id"]))
                .mappings()
                .one()
            )
            save_rows(
                conn,
                source,
                [{**original, "external_id": "one", "title": title}],
                "1" * 64,
                datetime.now(UTC),
            )
        with db.connect() as conn:
            result = decision(bound, conn=conn)
            assert result["first_unmet_rule"] == "R05"
            assert result["source_lifecycle"]["status"] == "DISPUTED"
    assert len(store.history("source", selection["revision"]["id"])) == 4


@pytest.mark.parametrize(
    "fault", ["stale", "future_poll", "disabled", "never_polled", "failed_poll"]
)
def test_poll_freshness_holds_review_without_churning_epoch(bound, fault):
    scoped, db, config, _ = bound
    changes = {"last_success": datetime.now(UTC) - timedelta(hours=2)}
    if fault == "future_poll":
        changes = {"last_success": datetime.now(UTC) + timedelta(hours=1)}
    if fault == "never_polled":
        changes = {"last_success": None}
    if fault == "disabled":
        changes = {"config": {**config, "enabled": False}}
    if fault == "failed_poll":
        changes = {"failures": 1}
    with db.begin() as conn:
        conn.execute(
            update(news_sources).where(news_sources.c.id == config["id"]).values(**changes)
        )
    with db.connect() as conn:
        assert decision(bound, conn=conn)["first_unmet_rule"] == "R05"
    assert len(scoped[0].history("source", scoped[4]["revision"]["id"])) == 2


def test_poll_does_not_undo_operator_withdrawal(bound):
    scoped, db, _, _ = bound
    store, _, _, _, selection, *_ = scoped
    sid = selection["revision"]["id"]
    old = store.history("source", sid)[-1]
    store.append(
        "source", sid, {**old["payload"], "status": "WITHDRAWN"}, expected_head=old["sha256"]
    )
    with db.connect() as conn:
        assert decision(bound, conn=conn)["first_unmet_rule"] == "R05"
    assert store.history("source", sid)[-1]["payload"]["status"] == "WITHDRAWN"


@pytest.mark.parametrize("fault", ["missing", "tampered", "future_revision", "wrong_received"])
def test_missing_or_inconsistent_registry_fails_closed(bound, fault):
    scoped, db, _, iid = bound
    selection = scoped[4]
    with db.begin() as conn:
        if fault == "missing":
            conn.execute(delete(news_revisions).where(news_revisions.c.item_id == iid))
        elif fault == "tampered":
            conn.execute(
                update(news_items).where(news_items.c.id == iid).values(content_sha256="0" * 64)
            )
        elif fault == "future_revision":
            conn.execute(
                update(news_revisions)
                .where(news_revisions.c.item_id == iid)
                .values(received_at=datetime.now(UTC) + timedelta(hours=1))
            )
        else:
            selection["revision"]["received_at"] = (
                datetime.now(UTC) - timedelta(days=1)
            ).isoformat()
    with db.connect() as conn, pytest.raises(ValueError):
        inspect(conn, selection, datetime.now(UTC))


def test_registry_mutation_between_checks_holds_gate(bound, monkeypatch):
    import engine.scope_sources as bridge

    original = bridge.inspect
    count = 0

    def changing(*args):
        nonlocal count
        count += 1
        result = original(*args)
        if count == 2:
            result["registry_sha256"] = "0" * 64
        return result

    monkeypatch.setattr(bridge, "inspect", changing)
    with bound[1].connect() as conn:
        assert decision(bound, conn=conn)["first_unmet_rule"] == "R05"


def test_bound_source_cannot_be_downgraded_to_manual_mode(bound):
    scoped = bound[0]
    store, selection = scoped[0], scoped[4]
    sid = selection["revision"]["id"]
    old = store.history("source", sid)[-1]
    value = dict(old["payload"])
    del value["registry_sha256"]
    with pytest.raises(ValueError, match="Cannot remove"):
        store.append("source", sid, value, expected_head=old["sha256"])


def test_source_identity_change_invalidates_epoch(bound):
    scoped, db, config, _ = bound
    with db.begin() as conn:
        conn.execute(
            update(news_sources)
            .where(news_sources.c.id == config["id"])
            .values(config={**config, "url": "https://other.example/feed"})
        )
    with db.connect() as conn:
        assert decision(bound, conn=conn)["first_unmet_rule"] == "R05"
    assert len(scoped[0].history("source", scoped[4]["revision"]["id"])) == 3


def test_unsupported_source_adapter_does_not_claim_rss_verification(bound):
    scoped, db, config, _ = bound
    with db.begin() as conn:
        conn.execute(
            update(news_sources)
            .where(news_sources.c.id == config["id"])
            .values(config={**config, "kind": "x"})
        )
    with db.connect() as conn, pytest.raises(ValueError, match="RSS"):
        inspect(conn, scoped[4], datetime.now(UTC))
