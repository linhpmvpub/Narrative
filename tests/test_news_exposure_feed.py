"""Approved exposure projection with current validity and conservative time filtering."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_news_claims import setup as setup
from test_news_exposure import context
from test_news_ingestion import enabled as enabled
from test_news_ingestion import ready, send
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.models.schema_v16 import exposure_drafts, exposure_reviews
from engine.news_exposure_feed import approved_shares


@pytest.fixture
def exposure(client, identities, setup, enabled, monkeypatch):
    import engine.news_exposure as module

    c = context()
    for operand in c["segment_context"] + c["financial_context"]:
        operand.update(
            source_url="https://www.sec.gov/synthetic",
            filing_url="https://www.sec.gov/filing",
            source_sha256="f" * 64,
            snapshot_version=1,
            available_at="2026-10-01T00:00:00Z",
        )
    monkeypatch.setattr(module, "dossier", lambda *args: c)
    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    url = f"/api/v0/news-claims/{claim}/exposure"
    pair = client.get(url, headers=headers(identities[0])).json()["pairs"][0]
    draft = client.post(
        url,
        json=dict(
            pair_sha256=pair["pair_sha256"],
            author_kind="AI_SIMULATED",
            news_link_rationale="PRIVATE linkage explanation must stay private.",
            limitations="PRIVATE limitations must stay private.",
        ),
        headers=headers(identities[0]),
    ).json()["id"]
    proof = dict(
        expected_version=0,
        decision="approved",
        reviewer_kind="AI_SIMULATED",
        periods_units_scope_confirmed=True,
        news_link_reviewed=True,
        baseline_not_effect_confirmed=True,
        rationale="PRIVATE reviewer notes must stay private.",
    )
    return claim, draft, proof, c


def approve(client, identities, exposure):
    r = client.post(
        f"/api/v0/news-claims/exposure/{exposure[1]}/reviews",
        json=exposure[2],
        headers=headers(identities[3]),
    )
    assert r.status_code == 200, r.text


def test_feed_map_allowlist_and_cutoff(db, client, identities, exposure):
    before = datetime.now(UTC)
    with db.connect() as conn:
        assert approved_shares(conn, before)["items"] == []
    approve(client, identities, exposure)
    now = datetime.now(UTC)
    with db.connect() as conn:
        assert approved_shares(conn, before)["items"] == []
        result = approved_shares(conn, now)
    share = result["items"][0]
    assert share["percent"] == "25.0000" and not share["graph_eligible"]
    assert not any(
        key in str(result)
        for key in ["PRIVATE", "author_id", "reviewer_id", "news_link_rationale", "limitations"]
    )
    feed = client.get("/api/v0/news/reviewed", headers=headers(identities[2])).json()
    assert feed["items"][0]["baseline_shares"] == result["items"]
    graph = client.get("/api/v0/impact-map", headers=headers(identities[2])).json()
    assert graph["baseline_exposure"]["items"] == result["items"]
    assert not any(e["eligible"] for e in graph["edges"])
    assert all(n["type"] != "baseline_share" for n in graph["nodes"])
    client.post(
        f"/api/v0/news-claims/exposure/{exposure[1]}/reviews",
        json={**exposure[2], "decision": "revoked", "expected_version": 1},
        headers=headers(identities[3]),
    )
    with db.connect() as conn:
        assert approved_shares(conn, now)["items"] == []
    assert (
        client.get("/api/v0/news/reviewed", headers=headers(identities[0])).json()["items"][0][
            "baseline_shares"
        ]
        == []
    )


@pytest.mark.parametrize("change", ["evidence", "hash", "proof", "self_review", "future_review"])
def test_invalid_approval_withheld(db, client, identities, exposure, change):
    approve(client, identities, exposure)
    with db.begin() as conn:
        if change == "evidence":
            exposure[3]["segment_context"][0]["current"]["value"] = "30"
        elif change == "hash":
            conn.execute(exposure_drafts.update().values(input_sha256="0" * 64))
        elif change == "self_review":
            conn.execute(exposure_reviews.update().values(reviewer_id=identities[0][0]))
        elif change == "future_review":
            conn.execute(
                exposure_reviews.update().values(recorded_at=datetime.now(UTC) + timedelta(days=1))
            )
        else:
            payload = conn.scalar(select(exposure_reviews.c.payload))
            payload["baseline_not_effect_confirmed"] = False
            conn.execute(exposure_reviews.update().values(payload=payload))
    with db.connect() as conn:
        assert approved_shares(conn, datetime.now(UTC))["items"] == []


def test_optin_limit_and_unknown_claim(db, client, identities, exposure, monkeypatch):
    approve(client, identities, exposure)
    with db.connect() as conn:
        assert approved_shares(conn, datetime.now(UTC), event_version_ids=[])["items"] == []
        with pytest.raises(ValueError):
            approved_shares(conn, datetime.now(UTC), limit=501)
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "false")
    with db.connect() as conn:
        assert approved_shares(conn, datetime.now(UTC))["items"] == []


def test_duplicate_pair_dedup_and_explicit_candidate_limit(db, client, identities, exposure):
    approve(client, identities, exposure)
    with db.connect() as conn:
        payload = conn.scalar(select(exposure_drafts.c.payload))
    body = {
        k: payload[k] for k in ("pair_sha256", "author_kind", "news_link_rationale", "limitations")
    }
    draft = client.post(
        f"/api/v0/news-claims/{exposure[0]}/exposure", json=body, headers=headers(identities[0])
    ).json()["id"]
    r = client.post(
        f"/api/v0/news-claims/exposure/{draft}/reviews",
        json=exposure[2],
        headers=headers(identities[3]),
    )
    assert r.status_code == 200, r.text
    with db.connect() as conn:
        assert len(approved_shares(conn, datetime.now(UTC))["items"]) == 1
        limited = approved_shares(conn, datetime.now(UTC), limit=1)
        assert limited["truncated"] and limited["examined"] == 1
