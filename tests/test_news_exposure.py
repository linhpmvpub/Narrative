"""Exposure ratios are baseline shares, not causal effects."""

from copy import deepcopy

import pytest
from test_news_claims import setup as setup
from test_news_ingestion import enabled as enabled
from test_news_ingestion import ready, send
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.news_exposure import matched_pairs


def context():
    common = dict(
        ticker="MU",
        accession="a1",
        concept="us-gaap:Revenues",
        unit="USD",
        period_kind="quarter",
        source_identity="same-source",
        metric="REVENUE",
        current=dict(start="2026-07-01", end="2026-09-30", value="100"),
    )
    d = {**deepcopy(common), "scope": "consolidated_entity", "snapshot_id": "financial-1"}
    n = {
        **deepcopy(common),
        "scope": "reported_segment",
        "segment": "MemoryMember",
        "dimensions": [["us-gaap:StatementBusinessSegmentsAxis", "MemoryMember"]],
        "snapshot_id": "segment-1",
    }
    n["current"]["value"] = "25"
    return {"financial_context": [d], "segment_context": [n], "truncated": False}


def test_baseline_share():
    result = matched_pairs(context())
    assert len(result) == 1 and result[0]["percent"] == "25.0000"
    assert result[0]["affected_fraction"] == "UNKNOWN" and not result[0]["impact_eligible"]


@pytest.mark.parametrize(
    "change",
    [
        "period",
        "unit",
        "issuer",
        "accession",
        "concept",
        "scope",
        "negative",
        "zero",
        "over",
        "nan",
    ],
)
def test_incompatible_or_invalid_operands(change):
    c = context()
    n = c["segment_context"][0]
    d = c["financial_context"][0]
    if change == "period":
        n["current"]["start"] = "2026-01-01"
    elif change == "unit":
        n["unit"] = "EUR"
    elif change == "issuer":
        n["ticker"] = "NVDA"
    elif change == "accession":
        n["accession"] = "other"
    elif change == "concept":
        n["concept"] = "us-gaap:SalesRevenueNet"
    elif change == "scope":
        n["scope"] = "geography"
    elif change == "negative":
        n["current"]["value"] = "-1"
    elif change == "zero":
        d["current"]["value"] = "0"
    elif change == "over":
        n["current"]["value"] = "101"
    elif change == "nan":
        n["current"]["value"] = "NaN"
    assert matched_pairs(c) == []


def test_draft_review_revocation_and_stale_evidence(
    db, client, identities, setup, enabled, monkeypatch
):
    import engine.news_exposure as module

    c = context()
    monkeypatch.setattr(module, "dossier", lambda *args: c)
    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    url = f"/api/v0/news-claims/{claim}/exposure"
    response = client.get(url, headers=headers(identities[0]))
    assert response.status_code == 200, response.text
    pair = response.json()["pairs"][0]
    draftbody = dict(
        pair_sha256=pair["pair_sha256"],
        author_kind="AI_SIMULATED",
        news_link_rationale="Synthetic link for testing; not verified causality.",
        limitations="Baseline only, affected fraction remains unknown.",
    )
    created = client.post(url, json=draftbody, headers=headers(identities[0]))
    assert created.status_code == 200, created.text
    id = created.json()["id"]
    reviewurl = f"/api/v0/news-claims/exposure/{id}/reviews"
    proof = dict(
        expected_version=0,
        decision="approved",
        reviewer_kind="AI_SIMULATED",
        periods_units_scope_confirmed=True,
        news_link_reviewed=True,
        baseline_not_effect_confirmed=True,
        rationale="Synthetic evidence review only; no price impact asserted.",
    )
    assert client.post(reviewurl, json=proof, headers=headers(identities[0])).status_code == 403
    assert (
        client.post(
            reviewurl,
            json={**proof, "baseline_not_effect_confirmed": False},
            headers=headers(identities[3]),
        ).status_code
        == 409
    )
    approved = client.post(reviewurl, json=proof, headers=headers(identities[3]))
    assert approved.status_code == 200, approved.text
    assert approved.json()["materiality"] == "UNKNOWN"
    assert client.post(reviewurl, json=proof, headers=headers(identities[3])).status_code == 409
    assert client.get(url, headers=headers(identities[2])).status_code == 409
    assert (
        client.get(url, headers=headers(identities[0])).json()["drafts"][0]["status"] == "approved"
    )
    c["segment_context"][0]["current"]["value"] = "30"
    assert client.get(url, headers=headers(identities[0])).json()["drafts"][0]["status"] == "stale"
    assert client.post(url, json=draftbody, headers=headers(identities[0])).status_code == 409
    assert (
        client.post(
            reviewurl,
            json={**proof, "expected_version": 1, "decision": "revoked"},
            headers=headers(identities[3]),
        ).status_code
        == 200
    )
    from sqlalchemy import func, select

    from engine.models.schema_v16 import exposure_reviews

    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(exposure_reviews)) == 2


def test_admin_cannot_self_approve(client, identities, setup, enabled, monkeypatch):
    import engine.news_exposure as module

    monkeypatch.setattr(module, "dossier", lambda *args: context())
    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    url = f"/api/v0/news-claims/{claim}/exposure"
    pair = client.get(url, headers=headers(identities[3])).json()["pairs"][0]
    draft = client.post(
        url,
        json=dict(
            pair_sha256=pair["pair_sha256"],
            author_kind="AI_SIMULATED",
            news_link_rationale="Synthetic link for a test only.",
            limitations="Baseline not actual affected revenue.",
        ),
        headers=headers(identities[3]),
    ).json()
    r = client.post(
        f"/api/v0/news-claims/exposure/{draft['id']}/reviews",
        json=dict(
            expected_version=0,
            decision="approved",
            reviewer_kind="AI_SIMULATED",
            periods_units_scope_confirmed=True,
            news_link_reviewed=True,
            baseline_not_effect_confirmed=True,
            rationale="Synthetic test of same-account denial.",
        ),
        headers=headers(identities[3]),
    )
    assert r.status_code == 409 and "Independent-account" in r.text


def test_known_consolidation_dimension_only():
    c = context()
    c["segment_context"][0]["dimensions"].append(
        ["srt:ConsolidationItemsAxis", "us-gaap:OperatingSegmentsMember"]
    )
    assert len(matched_pairs(c)) == 1
    c["segment_context"][0]["dimensions"].append(["GeographyAxis", "ChinaMember"])
    assert matched_pairs(c) == []
