"""Offline adversarial reconciliation and visual algorithm diagnostics."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_development_feed import enabled as enabled
from test_product import client as client
from test_product import headers, subscribe
from test_product import identities as identities

from engine.adapters.http_sources import AcquiredDocument
from engine.development_feed import events, project, versions
from engine.ingestion.incremental import reconcile
from engine.models.schema_v7 import collection_runs, source_cursors

CIK = "0001571996"
URL = "https://data.sec.gov/submissions/CIK" + CIK + ".json"


def row(n, day="2026-01-02", form="8-K"):
    return [f"{CIK}-26-{n:06d}", day, form, f"test{n}.htm"]


def document(rows, *, files=(), when=None, archive=None, ticker="DELL"):
    data = {
        k: [r[i] for r in rows]
        for i, k in enumerate(("accessionNumber", "filingDate", "form", "primaryDocument"))
    }
    if not archive:
        data = {
            "cik": 1571996,
            "tickers": [ticker],
            "filings": {"recent": data, "files": list(files)},
        }
    text = json.dumps(data)
    url = "https://data.sec.gov/submissions/" + archive if archive else URL
    return AcquiredDocument(
        url,
        text,
        when or datetime.now(UTC),
        hashlib.sha256(text.encode()).hexdigest(),
        hashlib.sha256(url.encode()).hexdigest(),
    )


def run(db, doc, archives=(), **kwargs):
    return reconcile(db, "DELL", CIK, doc, archives, **kwargs)


def count(db, table):
    with db.connect() as c:
        return c.scalar(select(func.count()).select_from(table))


def latest(db):
    with db.connect() as c:
        return (
            c.execute(
                select(versions).order_by(
                    versions.c.version_number.desc(), versions.c.available_at.desc()
                )
            )
            .mappings()
            .first()
        )


def test_incremental_backlog_not_limited_to_initial_batch(enabled):
    first = document([row(1)])
    assert run(enabled, first, initial_limit=1)["new_versions"] == 1
    assert run(enabled, first)["replayed"]
    new = document([row(n) for n in range(1, 27)])
    assert run(enabled, new, initial_limit=1)["new_versions"] == 25
    assert count(enabled, events) == 26
    assert run(enabled, document([row(n) for n in range(1, 27)]))["new_versions"] == 0
    with pytest.raises(ValueError, match="Stale"):
        run(enabled, document([row(28)], when=first.retrieved_at))
    assert count(enabled, collection_runs) == 3


def test_missing_then_reappearance_preserves_versions_and_old_asof(enabled, client, identities):
    user = identities[0]
    sid = subscribe(client, user).json()["id"]
    run(enabled, document([row(1), row(2, day="2026-01-01")]))
    project(enabled, user[0])
    before = datetime.now(UTC)
    result = run(enabled, document([row(2, day="2026-01-01")]))
    assert result["missing_unconfirmed"] == [row(1)[0]]
    assert latest(enabled)["normalized_claim"]["source_status"] == "missing_unconfirmed"
    path = f"/api/v0/threads/{sid}/feed"
    items = client.get(path, headers=headers(user)).json()["items"]
    assert any(
        x["effective_source_status"] == "missing_unconfirmed" and x["is_superseded"] for x in items
    )
    assert all(
        x["effective_source_status"] == "active"
        for x in client.get(
            path, headers=headers(user), params={"as_of": before.isoformat()}
        ).json()["items"]
    )
    assert run(enabled, document([row(2, day="2026-01-01")]))["new_versions"] == 0
    assert run(enabled, document([row(1), row(2, day="2026-01-01")]))["new_versions"] == 1
    assert latest(enabled)["normalized_claim"].get("source_status", "active") == "active"
    assert latest(enabled)["version_number"] == 3


def test_rollover_or_empty_response_is_not_withdrawal(enabled):
    run(enabled, document([row(1, day="2025-03-01")]))
    result = run(enabled, document([row(2, day="2026-01-02")]))
    assert result["uncovered"] == [row(1, day="2025-03-01")[0]]
    assert not result["missing_unconfirmed"]
    empty = run(enabled, document([]))
    assert len(empty["uncovered"]) == 2 and empty["new_versions"] == 0


def test_historical_archive_presence_prevents_false_missing(enabled):
    run(enabled, document([row(1, day="2025-03-01")]))
    name = "CIK" + CIK + "-submissions-001.json"
    info = {"name": name, "filingFrom": "2025-03-01", "filingTo": "2025-03-31"}
    archive = document([row(1, day="2025-03-01")], archive=name)
    result = run(enabled, document([row(2)], files=[info]), [archive])
    assert not result["missing_unconfirmed"] and not result["uncovered"]
    assert count(enabled, events) == 2
    # An invalid or incomplete historical page cannot advance checkpoint or publish changes.
    before = count(enabled, collection_runs)
    with pytest.raises(ValueError, match="coverage"):
        run(enabled, document([row(3)], files=[info]), [document([], archive=name)])
    assert count(enabled, collection_runs) == before and count(enabled, events) == 2


def test_archive_correction_cites_actual_archive_capture(enabled):
    run(enabled, document([row(1, day="2025-03-01")]))
    name = "CIK" + CIK + "-submissions-001.json"
    info = {"name": name, "filingFrom": "2025-03-01", "filingTo": "2025-03-31"}
    archive = document([row(1, day="2025-03-01", form="10-Q")], archive=name)
    run(enabled, document([row(2)], files=[info]), [archive])
    from engine.development_feed import documents

    v = latest(enabled)
    assert v["version_number"] == 2
    with enabled.connect() as c:
        d = c.execute(select(documents).where(documents.c.id == v["document_id"])).mappings().one()
        assert d["source_url"] == archive.url
        assert d["metadata"]["capture_sha256"] == archive.content_sha256


@pytest.mark.parametrize("bad", ["identity", "duplicate", "future", "unequal_columns"])
def test_malformed_snapshots_never_advance_checkpoint(enabled, bad):
    run(enabled, document([row(1)]))
    doc = document([row(2)])
    if bad == "identity":
        doc = document([row(2)], ticker="WDC")
    elif bad == "duplicate":
        doc = document([row(2), row(2)])
    elif bad == "future":
        doc = document([row(2)], when=datetime.now(UTC) + timedelta(days=1))
    else:
        data = json.loads(doc.text)
        data["filings"]["recent"]["form"] = []
        text = json.dumps(data)
        doc = AcquiredDocument(
            doc.url,
            text,
            doc.retrieved_at,
            hashlib.sha256(text.encode()).hexdigest(),
            doc.url_sha256,
        )
    with pytest.raises(ValueError):
        run(enabled, doc)
    assert count(enabled, collection_runs) == count(enabled, events) == 1


def test_concurrent_collection_one_checkpoint(enabled):
    doc = document([row(1)])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(enabled, doc), range(2)))
    assert sum(r["new_versions"] for r in results) == 1
    assert count(enabled, source_cursors) == count(enabled, collection_runs) == 1


def test_operator_withdrawal_requires_role_version_evidence_and_is_reversible(
    enabled, client, identities
):
    owner, _, _, admin = identities
    sid = subscribe(client, owner).json()["id"]
    run(enabled, document([row(1)]))
    project(enabled, owner[0])
    v = latest(enabled)
    url = f"/api/v0/admin/development/versions/{v['id']}/lifecycle"
    body = {
        "expected_version": 1,
        "action": "withdrawn",
        "evidence_url": "https://www.sec.gov/test-only-evidence",
        "reason": "Fabricated test withdrawal proof; no actual filing is withdrawn.",
    }
    assert client.post(url, headers=headers(owner), json=body).status_code == 403
    response = client.post(url, headers=headers(admin, "withdraw"), json=body)
    assert response.status_code == 200, response.text
    assert client.post(url, headers=headers(admin, "withdraw"), json=body).json() == response.json()
    assert client.post(url, headers=headers(admin), json=body).status_code == 409
    feed = client.get(f"/api/v0/threads/{sid}/feed", headers=headers(owner)).json()["items"]
    assert feed[0]["effective_source_status"] == "withdrawn" and feed[0]["is_superseded"]
    assert run(enabled, document([row(1)]))["new_versions"] == 0
    project(enabled, owner[0])
    restored = client.post(
        f"/api/v0/admin/development/versions/{response.json()['event_version_id']}/lifecycle",
        headers=headers(admin),
        json={**body, "expected_version": 2, "action": "restored"},
    )
    assert restored.status_code == 200, restored.text
    assert run(enabled, document([row(1)]))["new_versions"] == 0
    assert latest(enabled)["normalized_claim"]["lifecycle_evidence"]["operator_id"] == admin[0]


def test_graph_map_demo_uses_actual_matcher_conditions_and_is_not_price_forecast(client):
    assert client.get("/map").status_code == 200
    graph = client.get("/assets/map-demo.json").json()
    assert graph["is_synthetic"] and len(graph["edges"]) == 40
    assert client.get("/assets/map.html").status_code == 404
    result = client.post(
        "/api/v0/impact-map/demo-scenario",
        json={"ticker": "DELL", "start": "NAND_ASP", "direction": 1},
    ).json()
    assert result["is_synthetic"] and result["price_impact"] == "UNKNOWN"
    path = next(p for p in result["paths"] if [e["id"] for e in p["edges"]] == ["R026", "R027"])
    assert (
        path["conditional_reasons"]
        and path["hypothetical_metric_direction"] == "CONDITIONAL_DECREASE"
    )
    reverse = client.post(
        "/api/v0/impact-map/demo-scenario",
        json={"ticker": "DELL", "start": "NAND_ASP", "direction": -1},
    ).json()
    assert any(
        p["hypothetical_metric_direction"] == "CONDITIONAL_INCREASE" for p in reverse["paths"]
    )
    early = client.post(
        "/api/v0/impact-map/demo-scenario", json={"as_of": "2026-01-01T00:00:00Z"}
    ).json()
    assert early["paths"] == []
    assert (
        client.post("/api/v0/impact-map/demo-scenario", json={"start": "NOT_A_NODE"}).status_code
        == 422
    )


def test_live_map_owner_asof_and_candidate_graph_do_not_fabricate_impact(
    enabled, client, identities
):
    owner, other = identities[:2]
    assert client.get("/api/v0/impact-map").status_code == 401
    subscribe(client, owner)
    before = datetime.now(UTC)
    run(enabled, document([row(1)]))
    project(enabled, owner[0])
    graph = client.get("/api/v0/impact-map", headers=headers(owner)).json()
    assert len(graph["notices"]) == 1 and not graph["is_synthetic"]
    assert graph["notices"][0]["impact"] == "INSUFFICIENT_EVIDENCE"
    assert client.get("/api/v0/impact-map", headers=headers(other)).json()["notices"] == []
    assert (
        client.get(
            "/api/v0/impact-map", headers=headers(owner), params={"as_of": before.isoformat()}
        ).json()["notices"]
        == []
    )
    result = client.post("/api/v0/impact-map/scenario", headers=headers(owner), json={}).json()
    assert result["paths"] == [] and result["price_impact"] == "UNKNOWN"
    assert all(not e["eligible"] for e in graph["edges"])


def test_map_eligibility_badges_follow_asof(client):
    early = client.get("/api/v0/impact-map/demo", params={"as_of": "2026-01-01T00:00:00Z"}).json()
    assert all(not e["eligible"] for e in early["edges"])
    assert early["sample"] is None
    assert all(e["eligible"] for e in client.get("/api/v0/impact-map/demo").json()["edges"])


def test_packaged_map_seed_preserves_original_topology():
    from pathlib import Path

    from engine.web import ROOT

    original = json.loads(
        (Path(__file__).resolve().parents[1] / "config/relationships.json").read_text(
            encoding="utf-8"
        )
    )
    packaged = json.loads((ROOT / "map-seed.json").read_text(encoding="utf-8"))
    assert packaged == original
