"""Synthetic claims only; never fabricate production reviews."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_news import CONFIG, rss
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.adapters.news import parse_feed
from engine.models.schema_v13 import news_items
from engine.models.schema_v14 import news_claim_intakes, news_claim_reviews
from engine.news import register, save_rows


@pytest.fixture
def setup(db, client, identities):
    register(db, [CONFIG])
    rows = parse_feed(rss(), datetime.now(UTC))[0]
    with db.begin() as conn:
        save_rows(
            conn,
            {"id": CONFIG["id"], "config": CONFIG},
            rows,
            "a" * 64,
            datetime.now(UTC) - timedelta(minutes=1),
        )
        item = conn.scalar(select(news_items.c.id))
    source = client.get("/api/v0/news-claims/source/" + item, headers=headers(identities[0])).json()
    payload = {
        "revision_id": source["revision_id"],
        "expected_payload_sha256": source["payload_sha256"],
        "ticker": "MU",
        "event_type": "earnings",
        "author_kind": "AI_SIMULATED",
        "claim": {
            "claim_text": source["text"],
            "source_span": {"start": 0, "end": len(source["text"])},
            "source_url": source["url"],
            "metric_id": None,
            "unit": None,
            "period": None,
            "comparison_basis": "Qualitative synthetic source excerpt",
            "old_value": None,
            "new_value": None,
        },
        "uncertainties": ["Synthetic test only; causal impact unknown"],
    }
    return item, payload, rows


def approval(**changes):
    return {
        "expected_review_version": 0,
        "decision": "approved",
        "reviewer_kind": "AI_SIMULATED",
        "identity_confirmed": True,
        "citation_confirmed": True,
        "comparison_confirmed": True,
        "rationale": "Synthetic independent reviewer checked the quoted evidence.",
        **changes,
    }


def create(client, identities, payload, author=0):
    response = client.post("/api/v0/news-claims", json=payload, headers=headers(identities[author]))
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_review_intake_revocation_and_ownership(client, identities, db, setup):
    _, payload, _ = setup
    id = create(client, identities, payload)
    assert client.get("/api/v0/news-claims").status_code == 401
    assert client.get("/api/v0/news-claims", headers=headers(identities[1])).json()["items"] == []
    assert (
        client.post(
            "/api/v0/news-claims/" + id + "/reviews",
            json=approval(),
            headers=headers(identities[0]),
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v0/news-claims/" + id + "/prepare", headers=headers(identities[3])
        ).status_code
        == 409
    )
    reviewed = client.post(
        "/api/v0/news-claims/" + id + "/reviews", json=approval(), headers=headers(identities[3])
    )
    assert reviewed.status_code == 200, reviewed.text
    assert (
        client.post(
            "/api/v0/news-claims/" + id + "/reviews",
            json=approval(),
            headers=headers(identities[3]),
        ).status_code
        == 409
    )
    key = headers(identities[3], "prepare-stable-key")
    first = client.post("/api/v0/news-claims/" + id + "/prepare", headers=key)
    assert first.status_code == 200, first.text
    assert first.json()["payload"]["canonical_events_created"] == 0
    assert first.json()["payload"]["canonical_identity_review_required"]
    assert client.post("/api/v0/news-claims/" + id + "/prepare", headers=key).json() == first.json()
    revoke = client.post(
        "/api/v0/news-claims/" + id + "/reviews",
        json=approval(expected_review_version=1, decision="revoked"),
        headers=headers(identities[3]),
    )
    assert revoke.status_code == 200
    assert client.post("/api/v0/news-claims/" + id + "/prepare", headers=key).status_code == 409
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(news_claim_intakes)) == 1
        assert conn.scalar(select(func.count()).select_from(news_claim_reviews)) == 2
    from engine.mobile_gateway import allowed

    assert not allowed("GET", "/news-review")
    assert not allowed("POST", "/api/v0/news-claims")


def test_self_approval_and_proof_required(client, identities, setup):
    _, payload, _ = setup
    id = create(client, identities, payload, author=3)
    assert (
        client.post(
            "/api/v0/news-claims/" + id + "/reviews",
            json=approval(),
            headers=headers(identities[3]),
        ).status_code
        == 409
    )
    id = create(client, identities, payload)
    assert (
        client.post(
            "/api/v0/news-claims/" + id + "/reviews",
            json=approval(citation_confirmed=False),
            headers=headers(identities[3]),
        ).status_code
        == 409
    )


def test_source_correction_invalidates_approved_intake(client, identities, db, setup):
    _, payload, rows = setup
    id = create(client, identities, payload)
    assert (
        client.post(
            "/api/v0/news-claims/" + id + "/reviews",
            json=approval(),
            headers=headers(identities[3]),
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v0/news-claims/" + id + "/prepare", headers=headers(identities[3])
        ).status_code
        == 200
    )
    rows[0]["title"] = "Micron corrected quarterly statement"
    with db.begin() as conn:
        save_rows(conn, {"id": CONFIG["id"], "config": CONFIG}, rows, "b" * 64, datetime.now(UTC))
    assert (
        client.post(
            "/api/v0/news-claims/" + id + "/prepare", headers=headers(identities[3])
        ).status_code
        == 409
    )
    assert (
        client.get("/api/v0/news-claims", headers=headers(identities[0])).json()["items"][0][
            "status"
        ]
        == "stale_or_invalid"
    )


@pytest.mark.parametrize("change", ["quote", "hash", "company", "url", "offset"])
def test_source_binding_rejects_changed_claim(client, identities, setup, change):
    _, body, _ = setup
    payload = deepcopy(body)
    if change == "quote":
        payload["claim"]["claim_text"] = "Micron invented statement"
    if change == "hash":
        payload["expected_payload_sha256"] = "0" * 64
    if change == "company":
        payload["ticker"] = "NVDA"
    if change == "url":
        payload["claim"]["source_url"] = "https://other.example/a"
    if change == "offset":
        payload["claim"]["source_span"]["end"] += 1
    assert (
        client.post("/api/v0/news-claims", json=payload, headers=headers(identities[0])).status_code
        == 409
    )


def test_numeric_operands_periods_and_idempotency(client, identities, db, setup):
    item, _, rows = setup
    rows[0]["title"] = "Micron revenue Q3 2026 was 20 USD compared with 10 USD in Q3 2025"
    with db.begin() as conn:
        save_rows(conn, {"id": CONFIG["id"], "config": CONFIG}, rows, "b" * 64, datetime.now(UTC))
    source = client.get("/api/v0/news-claims/source/" + item, headers=headers(identities[0])).json()
    basis = {
        "concept": "MU_REVENUE",
        "unit": "USD",
        "duration": "quarter",
        "fiscal_calendar": "Micron",
        "accounting_basis": "GAAP",
        "observation_kind": "actual",
    }
    payload = {
        "revision_id": source["revision_id"],
        "expected_payload_sha256": source["payload_sha256"],
        "ticker": "MU",
        "event_type": "earnings",
        "author_kind": "AI_SIMULATED",
        "comparison_period": "Q3 2025",
        "uncertainties": ["Synthetic numeric evidence"],
        "claim": {
            "claim_text": source["text"],
            "source_span": {"start": 0, "end": len(source["text"])},
            "source_url": source["url"],
            "metric_id": "MU_REVENUE",
            "unit": "USD",
            "period": "Q3 2026",
            "comparison_basis": "Year over year",
            "old_value": "10",
            "new_value": "20",
            "old_basis": basis,
            "new_basis": basis,
        },
    }
    key = headers(identities[0], "same-claim-request")
    result = client.post("/api/v0/news-claims", json=payload, headers=key)
    assert result.status_code == 200, result.text
    assert client.post("/api/v0/news-claims", json=payload, headers=key).json() == result.json()
    for change in ["operand", "period", "metric", "comparison"]:
        bad = deepcopy(payload)
        if change == "operand":
            bad["claim"]["new_value"] = "999"
        if change == "period":
            bad["claim"]["period"] = "Q4 2026"
        if change == "metric":
            bad["claim"]["metric_id"] = "NVDA_DATA_CENTER_REVENUE"
            for side in ["old_basis", "new_basis"]:
                bad["claim"][side]["concept"] = "NVDA_DATA_CENTER_REVENUE"
        if change == "comparison":
            bad["comparison_period"] = "Q3 2026"
        assert (
            client.post("/api/v0/news-claims", json=bad, headers=headers(identities[0])).status_code
            == 409
        )
