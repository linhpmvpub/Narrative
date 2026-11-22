"""Synthetic source/review tests in isolated databases only."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from test_news import CONFIG
from test_news_claims import approval, create
from test_news_claims import setup as setup
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.ingestion.reviewed import events, sources, versions
from engine.models.schema_v2 import database_mode
from engine.models.schema_v15 import news_promotions
from engine.news import save_rows


@pytest.fixture
def enabled(db, monkeypatch):
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "true")
    with db.begin() as conn:
        conn.execute(database_mode.insert().values(id=1, mode="production"))


def ready(client, identities, payload):
    claim = create(client, identities, payload)
    response = client.post(
        f"/api/v0/news-claims/{claim}/reviews", json=approval(), headers=headers(identities[3])
    )
    assert response.status_code == 200, response.text
    intake = client.post(
        f"/api/v0/news-claims/{claim}/prepare", headers=headers(identities[3])
    ).json()
    return claim, dict(
        expected_intake_sha256=intake["payload_sha256"],
        occurrence_window="2026-11-22:test-event",
        identity_confirmed=True,
        identity_note="Synthetic explicit event identity review for test",
        action="new",
    )


def send(client, identities, claim, body):
    return client.post(
        f"/api/v0/news-claims/{claim}/ingest", json=body, headers=headers(identities[3])
    )


def test_new_duplicate_correction_and_stale_target(db, client, identities, setup, enabled):
    item, payload, rows = setup
    claim, body = ready(client, identities, payload)
    before = datetime.now(UTC)
    first = send(client, identities, claim, body)
    assert first.status_code == 200, first.text
    assert not first.json()["feed_eligible"]
    assert send(client, identities, claim, body).json()["idempotent_retry"]
    second, b2 = ready(client, identities, payload)
    assert send(client, identities, second, b2).status_code == 409
    b2.update(action="duplicate", target_claim_id=claim)
    assert (
        send(client, identities, second, b2).json()["event_version_id"]
        == first.json()["event_version_id"]
    )
    changed = deepcopy(rows)
    changed[0]["title"] += " corrected"
    with db.begin() as conn:
        save_rows(
            conn, {"id": CONFIG["id"], "config": CONFIG}, changed, "b" * 64, datetime.now(UTC)
        )
    assert send(client, identities, claim, body).status_code == 409
    source = client.get("/api/v0/news-claims/source/" + item, headers=headers(identities[0])).json()
    payload.update(
        revision_id=source["revision_id"], expected_payload_sha256=source["payload_sha256"]
    )
    payload["claim"].update(
        claim_text=source["text"], source_span={"start": 0, "end": len(source["text"])}
    )
    third, b3 = ready(client, identities, payload)
    b3.update(action="duplicate", target_claim_id=claim)
    assert send(client, identities, third, b3).status_code == 409
    b3["action"] = "correction"
    correction = send(client, identities, third, b3)
    assert correction.status_code == 200, correction.text
    fourth, b4 = ready(client, identities, payload)
    b4.update(action="duplicate", target_claim_id=claim)
    assert send(client, identities, fourth, b4).status_code == 409
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(events)) == 1
        assert conn.scalar(select(func.count()).select_from(versions)) == 2
        assert conn.scalar(select(func.count()).select_from(news_promotions)) == 3
        assert conn.scalar(select(sources.c.rights_status)) == "pending"
        assert (
            conn.scalar(
                select(func.count()).select_from(versions).where(versions.c.available_at < before)
            )
            == 0
        )
        latest = (
            conn.execute(select(versions).order_by(versions.c.version_number.desc()))
            .mappings()
            .first()
        )
        assert latest["supersedes_version_id"] == first.json()["event_version_id"]


def test_revocation_retry_identity_roles_and_optin(
    db, client, identities, setup, enabled, monkeypatch
):
    claim, body = ready(client, identities, setup[1])
    assert (
        client.post(
            f"/api/v0/news-claims/{claim}/ingest", json=body, headers=headers(identities[0])
        ).status_code
        == 403
    )
    assert send(client, identities, claim, {**body, "identity_confirmed": False}).status_code == 409
    assert (
        send(client, identities, claim, {**body, "expected_intake_sha256": "0" * 64}).status_code
        == 409
    )
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "false")
    assert send(client, identities, claim, body).status_code == 409
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "true")
    assert send(client, identities, claim, body).status_code == 200
    assert (
        send(
            client, identities, claim, {**body, "occurrence_window": "another event identity"}
        ).status_code
        == 409
    )
    client.post(
        f"/api/v0/news-claims/{claim}/reviews",
        json=approval(expected_review_version=1, decision="revoked"),
        headers=headers(identities[3]),
    )
    assert send(client, identities, claim, body).status_code == 409
    listing = client.get("/api/v0/news-claims", headers=headers(identities[3])).json()
    assert listing["items"][0]["ingestion_status"] == "withheld"
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(news_promotions)) == 1


def test_atomic_failure_blocked_source_and_concurrent_retry(db, client, identities, setup, enabled):
    from concurrent.futures import ThreadPoolExecutor

    claim, body = ready(client, identities, setup[1])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: send(client, identities, claim, body), range(2)))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert responses[0].json()["event_version_id"] == responses[1].json()["event_version_id"]
    with db.begin() as conn:
        assert conn.scalar(select(func.count()).select_from(versions)) == 1
        conn.execute(sources.update().values(rights_status="blocked"))
    assert send(client, identities, claim, body).status_code == 409
    listing = client.get("/api/v0/news-claims", headers=headers(identities[3])).json()
    assert listing["items"][0]["ingestion_status"] == "withheld"


def test_same_fact_correction_and_tampered_intake(db, client, identities, setup, enabled):
    from engine.models.schema_v14 import news_claim_intakes

    claim, body = ready(client, identities, setup[1])
    assert send(client, identities, claim, body).status_code == 200
    other, other_body = ready(client, identities, setup[1])
    other_body.update(action="correction", target_claim_id=claim)
    assert send(client, identities, other, other_body).status_code == 409
    with db.begin() as conn:
        conn.execute(
            news_claim_intakes.update()
            .where(news_claim_intakes.c.claim_id == other)
            .values(payload_sha256="0" * 64)
        )
    assert send(client, identities, other, other_body).status_code == 409
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(versions)) == 1
        assert conn.scalar(select(func.count()).select_from(news_promotions)) == 1
