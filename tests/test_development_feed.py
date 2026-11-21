"""Fabricated SEC metadata only; all network remains blocked by conftest."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_product import client as client
from test_product import headers, subscribe
from test_product import identities as identities

from engine.adapters.http_sources import AcquiredDocument
from engine.development_feed import cards, events, ingest_submissions, project, sources, versions
from engine.ingestion.service import initialize_demo
from engine.models.schema_v6 import metadata
from engine.sec_review import initialize_review_store


def capture(*, form="8-K", when=None, accession="0001571996-26-000001", ticker="DELL"):
    payload = {
        "cik": 1571996,
        "tickers": [ticker],
        "filings": {
            "recent": {
                "accessionNumber": [accession],
                "filingDate": ["2026-01-02"],
                "form": [form],
                "primaryDocument": ["test.htm"],
            }
        },
    }
    text = json.dumps(payload)
    url = "https://data.sec.gov/submissions/CIK0001571996.json"
    return AcquiredDocument(
        url,
        text,
        when or datetime.now(UTC),
        hashlib.sha256(text.encode()).hexdigest(),
        hashlib.sha256(url.encode()).hexdigest(),
    )


@pytest.fixture
def enabled(db, monkeypatch):
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "true")
    initialize_review_store(db)
    return db


def test_opt_in_and_synthetic_isolation(db, monkeypatch):
    monkeypatch.delenv("DEV_INFORMATIONAL_FEED", raising=False)
    with pytest.raises(ValueError, match="DEV_INFORMATIONAL_FEED"):
        ingest_submissions(db, "DELL", "0001571996", capture())
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "true")
    initialize_demo(db)
    with pytest.raises(ValueError, match="non-synthetic"):
        ingest_submissions(db, "DELL", "0001571996", capture())


def test_retry_correction_and_stale_capture(enabled):
    first = capture()
    initial = ingest_submissions(enabled, "DELL", "0001571996", first)[0]
    assert ingest_submissions(enabled, "DELL", "0001571996", first)[0]["status"] == "duplicate"
    correction = ingest_submissions(enabled, "DELL", "0001571996", capture(form="10-Q"))[0]
    assert correction["status"] == "corrected"
    with pytest.raises(ValueError, match="Stale"):
        ingest_submissions(enabled, "DELL", "0001571996", first)
    with enabled.connect() as conn:
        rows = conn.execute(select(versions).order_by(versions.c.version_number)).mappings().all()
        assert len(rows) == 2 and rows[1]["supersedes_version_id"] == initial["event_version_id"]
        assert conn.scalar(select(func.count()).select_from(events)) == 1
        assert conn.scalar(select(sources.c.rights_status)) == "pending"
        for name in (
            "rie_sec_reviews",
            "rie_sec_permissions",
            "rie_alerts",
            "rie_metric_observations",
        ):
            assert conn.scalar(select(func.count()).select_from(metadata.tables[name])) == 0


@pytest.mark.parametrize("change", ["future", "hash", "url", "identity"])
def test_invalid_capture_no_partial_event(enabled, change):
    doc = capture()
    if change == "future":
        doc = replace(doc, retrieved_at=datetime.now(UTC) + timedelta(days=1))
    elif change == "hash":
        doc = replace(doc, content_sha256="0" * 64)
    elif change == "url":
        doc = replace(doc, url="https://evil.example/")
    else:
        doc = capture(ticker="WDC")
    with pytest.raises(ValueError):
        ingest_submissions(enabled, "DELL", "0001571996", doc)
    with enabled.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(events)) == 0


def test_private_feed_asof_public_exclusion_and_disabled(enabled, client, identities, monkeypatch):
    owner, other = identities[:2]
    stock = subscribe(client, owner).json()["id"]
    narrative = subscribe(client, owner, "N08", "narrative").json()["id"]
    unrelated = subscribe(client, owner, "CO_AMD").json()["id"]
    share = client.post(
        f"/api/v0/threads/{stock}/sharing", headers=headers(owner), json={"is_public": True}
    ).json()["path"]
    before = datetime.now(UTC)
    ingest_submissions(enabled, "DELL", "0001571996", capture())
    assert client.post("/api/v0/development-feed/refresh").status_code == 401
    assert (
        client.post("/api/v0/development-feed/refresh", headers=headers(other)).json()[
            "new_private_links"
        ]
        == 0
    )
    assert (
        client.post("/api/v0/development-feed/refresh", headers=headers(owner)).json()[
            "new_private_links"
        ]
        == 2
    )
    assert project(enabled) == 0
    path = f"/api/v0/threads/{stock}/feed"
    assert client.get(path, headers=headers(other)).status_code == 404
    assert (
        client.get(path, headers=headers(owner), params={"as_of": before.isoformat()}).json()[
            "items"
        ]
        == []
    )
    first = client.get(path, headers=headers(owner)).json()["items"][0]
    assert first["decision_trace"]["stance"] == "INSUFFICIENT_EVIDENCE"
    assert first["decision_trace"]["score"] is None
    assert first["card"]["private_only"] and first["card"]["delivery_status"] == "disabled"
    assert set(first["related_thread_ids"]) == {stock, narrative}
    assert (
        client.get(f"/api/v0/threads/{unrelated}/feed", headers=headers(owner)).json()["items"]
        == []
    )
    assert client.get(share).json()["items"] == []
    ingest_submissions(enabled, "DELL", "0001571996", capture(form="10-Q"))
    assert project(enabled) == 2
    feed = client.get(path, headers=headers(owner), params={"limit": 1}).json()
    page = client.get(
        path,
        headers=headers(owner),
        params={"limit": 1, "as_of": feed["as_of"], "cursor": feed["next_cursor"]},
    ).json()
    assert page["items"][0]["correction_of"] == first["id"]
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "false")
    assert client.get(path, headers=headers(owner)).json()["items"] == []
    assert client.get(share).json()["items"] == []


def test_concurrent_ingestion_and_projection(enabled, client, identities):
    subscribe(client, identities[0])
    doc = capture()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: ingest_submissions(enabled, "DELL", "0001571996", doc), range(2))
        )
    assert sorted(r[0]["status"] for r in results) == ["created", "duplicate"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda _: project(enabled, identities[0][0]), range(2))) == 1
    with enabled.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(cards)) == 1


def test_later_capture_can_restore_earlier_metadata(enabled):
    first = capture()
    ingest_submissions(enabled, "DELL", "0001571996", first)
    ingest_submissions(enabled, "DELL", "0001571996", capture(form="10-Q"))
    restored = capture()
    assert restored.content_sha256 == first.content_sha256
    assert ingest_submissions(enabled, "DELL", "0001571996", restored)[0]["status"] == "corrected"
    assert ingest_submissions(enabled, "DELL", "0001571996", restored)[0]["status"] == "duplicate"
    with enabled.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(versions)) == 3
