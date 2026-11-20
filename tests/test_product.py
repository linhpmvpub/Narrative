"""Offline product acceptance: authorization, temporal history and private sharing."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from engine.adapters.fixture import FixtureSourceAdapter
from engine.api import app
from engine.api.accounts import hashed, provision
from engine.graph.demo import install_context
from engine.ingestion.service import initialize_demo
from engine.models.schema_v4 import cards, feedback, metadata, tokens
from engine.replay import replay
from engine.storybook.product import project

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.fixture
def client(db):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def identities(db):
    return [
        provision(db, tenant, admin=admin)
        for tenant, admin in (("one", False), ("one", False), ("two", False), ("ops", True))
    ]


def headers(identity, key=None):
    return {"Authorization": "Bearer " + identity[1], "Idempotency-Key": key or str(uuid4())}


def subscribe(client, identity, target="CO_DELL", kind="stock", key=None):
    return client.post(
        "/api/v0/subscriptions",
        headers=headers(identity, key),
        json={"thread_kind": kind, "target_id": target, "confirmed": True},
    )


def draft(**changes):
    return {
        "primary_ticker": "DELL",
        "title": "Private title",
        "thesis": "Private hypothesis",
        "horizon_months": 12,
        "driver_ids": ["NAND_ASP"],
        "supporting_evidence": "Private supporting note",
        "challenging_evidence": "Lower costs",
        "disconfirmation": "Private secret monitoring rule",
        "outcomes": {"DELL_ISG_MARGIN": -1},
        "hypothesis_polarity": "adverse",
        "max_hops": 2,
        **changes,
    }


def demo(db, as_of=NOW):
    initialize_demo(db)
    context = install_context(
        db,
        ROOT / "config",
        ROOT / "fixtures/demo_verified_relationships.json",
        ROOT / "fixtures/p3_demo_policy.json",
    )
    records = FixtureSourceAdapter().read(ROOT / "fixtures/events.jsonl")
    result = replay(db, records, as_of, context)
    project(db, records, result)
    return records, result


def test_authentication_and_operator_boundaries(client, db, identities, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "legacy")
    assert (
        client.get("/api/v0/stocks", headers={"Authorization": "Bearer legacy"}).status_code == 200
    )
    assert (
        client.get("/api/v0/subscriptions", headers={"Authorization": "Bearer legacy"}).status_code
        == 401
    )
    assert client.get("/api/v0/subscriptions").status_code == 401
    for identity in identities[:3]:
        assert (
            client.get("/api/v0/admin/review-queue", headers=headers(identity)).status_code == 403
        )
        assert (
            client.post(
                "/api/v0/admin/fixtures/replay",
                headers=headers(identity),
                json={"demo": True, "as_of": NOW.isoformat()},
            ).status_code
            == 403
        )
    assert (
        client.get("/api/v0/admin/review-queue", headers=headers(identities[3])).status_code == 200
    )
    with db.begin() as conn:
        conn.execute(
            tokens.update()
            .where(tokens.c.token_hash == hashed(identities[0][1]))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        conn.execute(
            tokens.update()
            .where(tokens.c.token_hash == hashed(identities[1][1]))
            .values(revoked=True)
        )
    for identity in identities[:2]:
        assert client.get("/api/v0/subscriptions", headers=headers(identity)).status_code == 401


def test_entitlements_idempotency_and_ownership(client, identities):
    user = identities[0]
    first = subscribe(client, user, key="retry")
    assert first.status_code == 200, first.text
    assert subscribe(client, user, key="retry").json() == first.json()
    assert subscribe(client, user, "CO_MU", key="retry").status_code == 409
    assert subscribe(client, user, "CO_MU").status_code == 200
    assert subscribe(client, user, "CO_NVDA").status_code == 200
    assert subscribe(client, user, "CO_AMD").status_code == 409
    assert subscribe(client, user, "N08", "narrative").status_code == 200
    assert subscribe(client, user, "N07", "narrative").status_code == 409
    sid = first.json()["id"]
    for other in identities[1:3]:
        assert client.get(f"/api/v0/threads/{sid}/feed", headers=headers(other)).status_code == 404
        assert (
            client.delete(f"/api/v0/subscriptions/{sid}", headers=headers(other)).status_code == 404
        )
        assert (
            client.post(
                f"/api/v0/threads/{sid}/sharing", headers=headers(other), json={"is_public": True}
            ).status_code
            == 404
        )
    assert client.delete(f"/api/v0/subscriptions/{sid}", headers=headers(user)).status_code == 200
    assert subscribe(client, user, "CO_AMD").status_code == 200


def test_concurrent_subscription_cap(client, identities):
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(
                lambda stock: subscribe(client, identities[0], stock),
                ["CO_MU", "CO_DELL", "CO_AMD", "CO_NVDA"],
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 409]


@pytest.mark.parametrize(
    "change",
    [
        {"driver_ids": ["NAND_ASP"] * 4},
        {"driver_ids": ["NAND_ASP"] * 2},
        {"driver_ids": ["UNKNOWN"]},
        {"disconfirmation": ""},
        {"horizon_months": 0},
        {"max_hops": 3},
        {"outcomes": {"MU_REVENUE": 1}},
        {"thesis": " "},
    ],
)
def test_compiler_rejects_invalid_scope(client, identities, change):
    assert (
        client.post(
            "/api/v0/narratives", headers=headers(identities[0]), json=draft(**change)
        ).status_code
        == 422
    )


def test_narrative_approval_immutable_versions_and_private_catalog(client, db, identities):
    user = identities[0]
    created = client.post("/api/v0/narratives", headers=headers(user), json=draft())
    assert created.status_code == 200, created.text
    nid = created.json()["id"]
    assert subscribe(client, user, nid, "narrative").status_code == 409
    assert subscribe(client, identities[1], nid, "narrative").status_code == 404
    assert (
        client.post(
            f"/api/v0/narratives/{nid}/approve",
            headers=headers(identities[2]),
            json={"confirmed": True, "expected_version": 1},
        ).status_code
        == 404
    )
    approved = client.post(
        f"/api/v0/narratives/{nid}/approve",
        headers=headers(user),
        json={"confirmed": True, "expected_version": 1},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["version"] == 2
    assert subscribe(client, user, nid, "narrative").status_code == 200
    edited = client.put(
        f"/api/v0/narratives/{nid}",
        headers=headers(user),
        json={**draft(thesis="New private thesis"), "expected_version": 2},
    )
    assert edited.status_code == 200
    assert edited.json()["version"] == 3
    assert (
        client.put(
            f"/api/v0/narratives/{nid}",
            headers=headers(user),
            json={**draft(), "expected_version": 2},
        ).status_code
        == 409
    )
    versions = metadata.tables["rie_narrative_versions"]
    with db.connect() as conn:
        rows = list(
            conn.execute(
                select(versions)
                .where(versions.c.narrative_id == nid)
                .order_by(versions.c.version_number)
            ).mappings()
        )
    assert [r["thesis"] for r in rows] == [
        "Private hypothesis",
        "Private hypothesis",
        "New private thesis",
    ]
    assert [bool(r["approved_by"]) for r in rows] == [False, True, False]
    catalog = client.get("/api/v0/narratives/templates", headers=headers(user))
    assert len(catalog.json()["items"]) == 10
    assert "Private" not in catalog.text


def test_feed_bundling_feedback_corrections_and_sharing(client, db, identities):
    user = identities[0]
    stock = subscribe(client, user, "CO_SNDK").json()["id"]
    narrative = subscribe(client, user, "N09", "narrative").json()["id"]
    records, result = demo(db)
    assert project(db, records, result) == 0
    feed = client.get(
        f"/api/v0/threads/{stock}/story", headers=headers(user), params={"as_of": NOW.isoformat()}
    ).json()
    assert feed["is_public"] is False
    assert feed["price_series"] == "unavailable"
    assert feed["financial_observations"] == []
    items = feed["items"]
    assert [i["card"]["source_available_at"] for i in items] == sorted(
        i["card"]["source_available_at"] for i in items
    )
    assert items and all(i["is_synthetic"] and i["card"]["evidence_urls"] for i in items)
    assert all(i["card"]["event_id"] not in {"F029", "F030", "F025", "F027", "F028"} for i in items)
    original = next(i for i in items if i["card"]["event_id"] == "F017")
    correction = next(i for i in items if i["card"]["event_id"] == "F031")
    assert correction["correction_of"] == original["id"]
    assert set(original["related_thread_ids"]) == {stock, narrative}
    earlier = client.get(
        f"/api/v0/threads/{stock}/feed",
        headers=headers(user),
        params={"as_of": "2026-10-01T00:00:00Z"},
    )
    assert earlier.json()["items"] == []
    first = client.get(
        f"/api/v0/threads/{stock}/feed",
        headers=headers(user),
        params={"as_of": NOW.isoformat(), "limit": 1},
    ).json()
    second = client.get(
        f"/api/v0/threads/{stock}/feed",
        headers=headers(user),
        params={"as_of": NOW.isoformat(), "limit": 1, "cursor": first["next_cursor"]},
    ).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert (
        client.get(
            f"/api/v0/threads/{narrative}/feed",
            headers=headers(user),
            params={"as_of": NOW.isoformat(), "cursor": first["next_cursor"]},
        ).status_code
        == 422
    )
    cid = original["id"]
    for other in identities[1:3]:
        assert (
            client.post(
                f"/api/v0/alerts/{cid}/feedback", headers=headers(other), json={"label": "WRONG"}
            ).status_code
            == 404
        )
    for label in ["NOT_RELEVANT", "WRONG"]:
        response = client.post(
            f"/api/v0/alerts/{cid}/feedback",
            headers=headers(user, label),
            json={"label": label, "reason": "Private feedback secret"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["global_truth_changed"] is False
    assert (
        client.post(
            f"/api/v0/alerts/{cid}/feedback",
            headers=headers(user, "WRONG"),
            json={"label": "WRONG", "reason": "Private feedback secret"},
        ).status_code
        == 200
    )
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(feedback)).scalar_one() == 2
        queue = metadata.tables["rie_review_queue"]
        assert (
            conn.execute(
                select(func.count()).select_from(queue).where(queue.c.item_id == cid)
            ).scalar_one()
            == 1
        )
        edges = metadata.tables["rie_relationships"]
        assert (
            conn.execute(
                select(func.count()).select_from(edges).where(edges.c.status != "candidate")
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                select(func.count()).select_from(cards).where(cards.c.id == cid)
            ).scalar_one()
            == 1
        )
    assert client.get("/api/v0/public/stories/unknown").status_code == 404
    share = client.post(
        f"/api/v0/threads/{stock}/sharing", headers=headers(user), json={"is_public": True}
    ).json()
    public = client.get(share["path"])
    assert public.status_code == 200
    for forbidden in ("Private", user[0], cid, stock, "decision_trace", "what_to_watch"):
        assert forbidden not in public.text
    client.post(
        f"/api/v0/threads/{stock}/sharing", headers=headers(user), json={"is_public": False}
    )
    assert client.get(share["path"]).status_code == 404


def test_admin_replay_requires_demo_and_relation_review_requires_proof(client, identities):
    admin = identities[3]
    denied = client.post(
        "/api/v0/admin/fixtures/replay",
        headers=headers(admin),
        json={"demo": True, "as_of": NOW.isoformat()},
    )
    assert denied.status_code == 422
    assert (
        client.post(
            "/api/v0/admin/relations/R026/review",
            headers=headers(admin),
            json={"action": "approve", "reason": "Test", "routing_basis": "Test"},
        ).status_code
        == 422
    )
    rejected = client.post(
        "/api/v0/admin/relations/R026/review",
        headers=headers(admin, "reject"),
        json={"action": "reject", "reason": "Unsupported"},
    )
    assert rejected.status_code == 200, rejected.text
    assert (
        client.post(
            "/api/v0/admin/relations/R026/review",
            headers=headers(admin, "reject"),
            json={"action": "reject", "reason": "Unsupported"},
        ).json()
        == rejected.json()
    )


def test_error_payload_and_openapi(client, identities):
    response = client.post("/api/v0/subscriptions", headers=headers(identities[0]), json={})
    assert response.status_code == 422
    assert {"code", "message", "request_id"} <= response.json().keys()
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v0/threads/{thread_id}/story" in paths
    assert "/api/v0/admin/relations/{relation_id}/review" in paths


def test_custom_scope_replay_and_no_backdated_narrative(client, db, identities):
    user = identities[0]
    created = client.post("/api/v0/narratives", headers=headers(user), json=draft()).json()
    nid = created["id"]
    approval = client.post(
        f"/api/v0/narratives/{nid}/approve",
        headers=headers(user),
        json={"confirmed": True, "expected_version": 1},
    ).json()
    sid = subscribe(client, user, nid, "narrative").json()["id"]
    demo(db)
    assert client.get(f"/api/v0/threads/{sid}/feed", headers=headers(user)).json()["items"] == []
    now = datetime.now(UTC)
    records = FixtureSourceAdapter().read(ROOT / "fixtures/events.jsonl")
    context = install_context(
        db,
        ROOT / "config",
        ROOT / "fixtures/demo_verified_relationships.json",
        ROOT / "fixtures/p3_demo_policy.json",
    )
    result = replay(db, records, now, context)
    project(db, records, result)
    feed = client.get(f"/api/v0/threads/{sid}/feed", headers=headers(user)).json()
    sample = next(i for i in feed["items"] if i["card"]["event_id"] == "F021")
    assert sample["decision_trace"]["narrative_version_id"] == approval["version_id"]
    assert [e["edge_id"] for e in sample["card"]["graph_path"]] == ["R026", "R027"]
    # A second owner's one-hop scope cannot match the two-hop F021 cost chain.
    other = identities[1]
    created = client.post(
        "/api/v0/narratives", headers=headers(other), json=draft(max_hops=1)
    ).json()
    nid2 = created["id"]
    client.post(
        f"/api/v0/narratives/{nid2}/approve",
        headers=headers(other),
        json={"confirmed": True, "expected_version": 1},
    )
    sid2 = subscribe(client, other, nid2, "narrative").json()["id"]
    later = datetime.now(UTC)
    result = replay(db, records, later, context)
    project(db, records, result)
    limited = client.get(f"/api/v0/threads/{sid2}/feed", headers=headers(other)).json()["items"]
    assert not any(i["card"]["event_id"] == "F021" for i in limited)
    share = client.post(
        f"/api/v0/threads/{sid}/sharing", headers=headers(user), json={"is_public": True}
    ).json()
    public = client.get(share["path"])
    assert "Private" not in public.text
    assert "compiled_scope" not in public.text


def test_admin_replay_populates_synthetic_sample_and_is_retry_safe(client, db, identities):
    user, admin = identities[0], identities[3]
    sid = subscribe(client, user, "N08", "narrative").json()["id"]
    initialize_demo(db)
    for attempt in range(2):
        result = client.post(
            "/api/v0/admin/fixtures/replay",
            headers=headers(admin),
            json={"demo": True, "as_of": NOW.isoformat()},
        )
        assert result.status_code == 200, result.text
        assert result.json()["delivery"] == "disabled"
        if attempt:
            assert result.json()["new_thread_entries"] == 0
    items = client.get(f"/api/v0/threads/{sid}/story", headers=headers(user)).json()["items"]
    sample = next(i for i in items if i["card"]["event_id"] == "F021")
    assert sample["card"]["narrative_stance"] == "INSUFFICIENT_EVIDENCE"
    assert sample["card"]["conditional_economic_effect"] == "ADVERSE_IF_CONDITIONS_HOLD"
    with db.connect() as conn:
        for table in ("rie_alerts", "rie_dispatch_plans"):
            assert (
                conn.execute(select(func.count()).select_from(metadata.tables[table])).scalar_one()
                == 0
            )


def test_required_idempotency_and_bad_cursor(client, identities):
    user = identities[0]
    sid = subscribe(client, user).json()["id"]
    missing = client.post(
        "/api/v0/subscriptions",
        headers={"Authorization": "Bearer " + user[1]},
        json={"thread_kind": "stock", "target_id": "CO_MU", "confirmed": True},
    )
    assert missing.status_code == 422
    for cursor in ["!", "W10=", "bnVsbA=="]:
        assert (
            client.get(
                f"/api/v0/threads/{sid}/feed", headers=headers(user), params={"cursor": cursor}
            ).status_code
            == 422
        )
