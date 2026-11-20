"""Security regressions use only local test data and mocked transport."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_foundations import add_evidence

from engine.api import app, authenticate
from engine.api.accounts import provision
from engine.api.security import MAX_BODY_BYTES, SecurityBoundary
from engine.models.schema_v4 import metadata
from engine.storybook.product import observations


@pytest.mark.parametrize(
    "headers,chunks,status",
    [
        ([(b"content-length", b"65537")], [b""], 413),
        ([], [b"x" * 32768, b"y" * 32769], 413),
        ([(b"content-length", b"1")], [b"x" * 65537], 413),
        ([(b"content-length", b"-1")], [b""], 400),
        ([(b"content-length", b"1"), (b"content-length", b"1")], [b"x"], 400),
        ([(b"content-length", b"2")], [b"x"], 400),
        ([], [b"x" * MAX_BODY_BYTES], 200),
    ],
)
def test_request_limit_enforces_actual_stream_before_application(headers, chunks, status):
    called, sent = [], []

    async def downstream(scope, receive, send):
        called.append(True)
        message = await receive()
        assert len(message["body"]) == MAX_BODY_BYTES
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    messages = [
        {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
        for i, chunk in enumerate(chunks)
    ]

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    asyncio.run(SecurityBoundary(downstream)({"type": "http", "headers": headers}, receive, send))
    assert bool(called) == (status == 200)
    assert sent[0]["status"] == status
    assert dict(sent[0]["headers"])[b"cache-control"] == b"no-store"


def test_no_store_headers_on_private_public_and_errors(db):
    _, token = provision(db, "security-test")
    auth = {"Authorization": "Bearer " + token, "Idempotency-Key": "private-share"}
    with TestClient(app) as client:
        response = client.post(
            "/api/v0/subscriptions",
            headers=auth,
            json={"thread_kind": "stock", "target_id": "CO_MU", "confirmed": True},
        )
        sid = response.json()["id"]
        share = client.post(
            f"/api/v0/threads/{sid}/sharing", headers=auth, json={"is_public": True}
        )
        public_path = share.json()["path"]
        responses = [
            response,
            share,
            client.get(public_path),
            client.get(f"/api/v0/threads/{sid}/story", headers=auth),
            client.get("/api/v0/subscriptions"),
            client.post("/api/v0/narratives", headers=auth, json={}),
            client.post("/api/v0/narratives", headers=auth, content=b"x" * 65537),
        ]
        for response in responses:
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["referrer-policy"] == "no-referrer"
            assert response.headers["x-content-type-options"] == "nosniff"
        assert responses[-1].status_code == 413
        assert responses[-2].status_code == 422
        auth["Idempotency-Key"] = "revoke"
        client.post(f"/api/v0/threads/{sid}/sharing", headers=auth, json={"is_public": False})
        assert client.get(public_path).status_code == 404


def test_non_ascii_catalog_credentials_fail_authentication_instead_of_crashing(db, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "catalog-only")
    with pytest.raises(HTTPException) as error:
        authenticate(HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-\u00e9"))
    assert error.value.status_code == 401


@pytest.mark.parametrize(
    "bad_field", ["url", "verified_by", "whitespace_reviewer", "text_end", "source_clock", None]
)
def test_financial_observations_require_reviewed_matching_citation(db, bad_field):
    eid = add_evidence(db)
    metrics = metadata.tables["rie_metric_observations"]
    evidence = metadata.tables["rie_evidence"]
    sources = metadata.tables["rie_sources"]
    with db.begin() as conn:
        conn.execute(
            metrics.insert().values(
                id=str(uuid4()),
                entity_id="CO_MU",
                metric_id="MU_REVENUE",
                period_end=date(2026, 1, 1),
                value=1,
                unit="test-only",
                first_available_at=datetime.now(UTC) - timedelta(seconds=1),
                evidence_id=eid,
                adjustment_metadata={"unit_test": True},
            )
        )
        if bad_field == "source_clock":
            conn.execute(sources.update().values(created_at=datetime.now(UTC) + timedelta(days=1)))
        elif bad_field == "whitespace_reviewer":
            conn.execute(evidence.update().where(evidence.c.id == eid).values(verified_by="   "))
        elif bad_field:
            bad_values = {"url": "javascript:alert(1)", "verified_by": "", "text_end": 0}
            conn.execute(
                evidence.update()
                .where(evidence.c.id == eid)
                .values(**{bad_field: bad_values[bad_field]})
            )
    with db.connect() as conn:
        rows = observations(conn, {"stock_entity_id": "CO_MU"}, datetime.now(UTC))
    assert len(rows) == (0 if bad_field else 1)


def test_validation_and_database_errors_do_not_echo_private_input(db):
    _, token = provision(db, "security-errors")
    secret = "private-feedback-not-for-response"
    with TestClient(app) as client:
        response = client.post(
            "/api/v0/subscriptions",
            headers={"Authorization": "Bearer " + token},
            json={"thread_kind": secret, "target_id": "CO_MU", "confirmed": True},
        )
        assert response.status_code == 422
        assert secret not in response.text and token not in response.text
    with db.connect() as conn:
        assert not conn.execute(select(metadata.tables["rie_subscriptions"])).first()
