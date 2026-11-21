"""Financial comparability, provenance, temporal revisions and mobile isolation."""

import hashlib
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_development_feed import enabled as enabled
from test_incremental_map import CIK, document, row, run
from test_product import client as client
from test_product import headers, subscribe
from test_product import identities as identities

from engine.adapters.http_sources import AcquiredDocument
from engine.development_feed import project, versions
from engine.financials import assessments, extract, ingest, known_filings
from engine.models.schema_v8 import financial_snapshots


def fact(value, start, end):
    return {
        "accn": row(1)[0],
        "form": "10-Q",
        "filed": "2026-09-01",
        "start": start,
        "end": end,
        "val": value,
    }


def capture(current=120, prior=100, *, extra=(), unit="USD", when=None):
    rows = [
        fact(prior, "2025-04-01", "2025-06-30"),
        fact(current, "2026-04-01", "2026-06-30"),
        *extra,
    ]
    payload = {"cik": int(CIK), "facts": {"us-gaap": {"Revenues": {"units": {unit: rows}}}}}
    text = json.dumps(payload)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
    return AcquiredDocument(
        url,
        text,
        when or datetime.now(UTC),
        hashlib.sha256(text.encode()).hexdigest(),
        hashlib.sha256(url.encode()).hexdigest(),
    )


@pytest.fixture
def financial_store(enabled):
    run(enabled, document([row(1, day="2026-09-01", form="10-Q")]))
    return enabled


def read(db, at=None):
    with db.connect() as c:
        return assessments(c, "DELL", at or datetime.now(UTC))


def test_same_period_unit_concept_filing_and_precise_sources(financial_store):
    doc = capture(
        extra=[fact(230, "2026-01-01", "2026-06-30"), fact(200, "2025-01-01", "2025-06-30")]
    )
    assert ingest(financial_store, "DELL", CIK, doc)["comparisons"] == 1
    result = read(financial_store)[0]
    assert result["current"]["value"] == "120" and result["prior"]["value"] == "100"
    assert result["period_kind"] == "quarter" and result["percent_change"] == "20.00"
    assert result["source_sha256"] == doc.content_sha256
    assert result["current"]["json_pointer"].endswith("/1")
    assert result["scope"] == "consolidated_entity" and result["stock_price_impact"] == "UNKNOWN"
    assert result["narrative_stance"] == "INSUFFICIENT_EVIDENCE"
    assert ingest(financial_store, "DELL", CIK, doc)["status"] == "duplicate"


@pytest.mark.parametrize("prior", [0, -100])
def test_nonpositive_baseline_does_not_invent_growth_percentage(financial_store, prior):
    ingest(financial_store, "DELL", CIK, capture(prior=prior))
    r = read(financial_store)[0]
    assert r["percent_change"] is None and r["percent_unavailable_reason"] == "nonpositive_prior"


@pytest.mark.parametrize("variant", ["unit", "conflict", "nonfinite", "period", "accession"])
def test_incomparable_facts_are_withheld(financial_store, variant):
    doc = capture()
    if variant == "unit":
        doc = capture(unit="EUR")
    if variant == "conflict":
        doc = capture(extra=[fact(121, "2026-04-01", "2026-06-30")])
    if variant == "nonfinite":
        doc = capture(current="NaN")
    payload = json.loads(doc.text)
    if variant == "period":
        payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["start"] = "2025-01-01"
    if variant == "accession":
        payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["accn"] = row(2)[0]
    text = json.dumps(payload)
    doc = AcquiredDocument(
        doc.url, text, doc.retrieved_at, hashlib.sha256(text.encode()).hexdigest(), doc.url_sha256
    )
    assert ingest(financial_store, "DELL", CIK, doc)["comparisons"] == 0
    assert read(financial_store) == []


def test_snapshot_revisions_asof_empty_retraction_and_stale_input(financial_store):
    first = capture()
    ingest(financial_store, "DELL", CIK, first)
    before = datetime.now(UTC)
    ingest(financial_store, "DELL", CIK, capture(current=130))
    assert read(financial_store, before)[0]["current"]["value"] == "120"
    assert read(financial_store)[0]["current"]["value"] == "130"
    with pytest.raises(ValueError, match="Stale"):
        ingest(financial_store, "DELL", CIK, first)
    ingest(financial_store, "DELL", CIK, capture(current=120))
    assert read(financial_store)[0]["snapshot_version"] == 3
    ingest(financial_store, "DELL", CIK, capture(unit="EUR"))
    assert read(financial_store) == []
    with financial_store.connect() as c:
        assert c.scalar(select(func.count()).select_from(versions)) == 1
        assert c.scalar(select(func.count()).select_from(financial_snapshots)) == 4


def test_identity_and_hash_must_match(financial_store):
    doc = capture()
    with pytest.raises(ValueError):
        ingest(financial_store, "MU", CIK, doc)
    bad = AcquiredDocument(doc.url, doc.text, doc.retrieved_at, "0" * 64, doc.url_sha256)
    with pytest.raises(ValueError, match="hash"):
        ingest(financial_store, "DELL", CIK, bad)


def test_feed_map_owner_and_source_invalidation(financial_store, client, identities):
    owner, other, _, admin = identities
    sid = subscribe(client, owner).json()["id"]
    project(financial_store, owner[0])
    before = datetime.now(UTC)
    ingest(financial_store, "DELL", CIK, capture())
    path = f"/api/v0/threads/{sid}/feed"
    item = client.get(path, headers=headers(owner)).json()["items"][0]
    assert len(item["financial_assessments"]) == 1
    assert (
        client.get(path, headers=headers(owner), params={"as_of": before.isoformat()}).json()[
            "items"
        ][0]["financial_assessments"]
        == []
    )
    graph = client.get("/api/v0/impact-map", headers=headers(owner)).json()
    assert any(n["type"] == "reported_metric" for n in graph["nodes"])
    assert graph["notices"][0]["impact"] == "REPORTED_FINANCIAL_CHANGE"
    assert client.get("/api/v0/impact-map", headers=headers(other)).json()["notices"] == []
    with financial_store.connect() as c:
        vid = c.scalar(select(versions.c.id))
    response = client.post(
        f"/api/v0/admin/development/versions/{vid}/lifecycle",
        headers=headers(admin),
        json={
            "expected_version": 1,
            "action": "withdrawn",
            "evidence_url": "https://www.sec.gov/test-only",
            "reason": "Fabricated withdrawal evidence used only by this offline test.",
        },
    )
    assert response.status_code == 200
    assert (
        client.get(path, headers=headers(owner)).json()["items"][0]["financial_assessments"] == []
    )
    assert (
        client.get("/api/v0/impact-map", headers=headers(owner)).json()["notices"][0][
            "economic_observations"
        ]
        == []
    )


def test_sandisk_comparisons_do_not_cross_spin(financial_store):
    with financial_store.connect() as c:
        claims = known_filings(c, "DELL", datetime.now(UTC))
    claim = next(iter(claims.values()))
    claim = {**claim, "ticker": "SNDK"}
    payload = json.loads(capture().text)
    payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"] = [
        fact(120, "2026-01-01", "2026-03-31"),
        fact(100, "2025-01-01", "2025-03-31"),
    ]
    assert extract(payload, "SNDK", {claim["accession"]: claim}) == []


def test_gateway_restricts_routes_and_preserves_auth(monkeypatch):
    import engine.mobile_gateway as gateway

    gateway.buckets.clear()
    seen = []

    async def forward(method, path, query, headers, body):
        seen.append((method, path, headers))
        return httpx.Response(
            401,
            json={"message": "Authentication required"},
            headers={"set-cookie": "should-not-forward=1"},
        )

    monkeypatch.setattr(gateway, "forward", forward)
    with TestClient(gateway.app) as c:
        assert c.get("/api/v0/client-capabilities").json()["read_only"] is True
        for path in [
            "/api/v0/admin/sec/events",
            "/docs",
            "/openapi.json",
            "/api/v0/public/stories/x",
            "/secrets/a.txt",
        ]:
            assert c.get(path).status_code == 404
        assert not seen
        response = c.get(
            "/api/v0/impact-map", headers={"Authorization": "Bearer sample", "Cookie": "private=1"}
        )
        assert response.status_code == 401 and "set-cookie" not in response.headers
        assert seen[0][2] == {"authorization": "Bearer sample"}
        assert c.post("/api/v0/subscriptions", json={}).status_code == 404
        assert c.post("/api/v0/impact-map/demo-scenario", content=b"x" * 65537).status_code == 413
