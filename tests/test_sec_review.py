"""Operator review acceptance uses fabricated local text, never approves real filings."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from engine.api import app
from engine.api.accounts import provision
from engine.ingestion.service import initialize_demo
from engine.models.schema_v5 import drafts, filings, metadata, reviews
from engine.sec_review import import_collection, initialize_review_store, plain_text, sha

TEXT = "Revenue increased."


def collection(
    tmp_path, *, accession="0001571996-26-000001", retrieved="2026-11-01T12:00:00+00:00"
):
    folder = tmp_path / accession
    folder.mkdir()
    html = (
        '<html><script>alert("untrusted")</script><style>secret CSS</style><p>'
        + TEXT
        + "</p></html>"
    )
    (folder / "filing.html").write_text(html, encoding="utf-8")
    row = dict(
        ticker="DELL",
        cik="0001571996",
        accession=accession,
        url=f"https://www.sec.gov/Archives/edgar/data/1571996/{accession.replace('-', '')}/filing.htm",
        is_synthetic=False,
        file="filing.html",
        content_sha256=sha(html),
        retrieved_at=retrieved,
        first_available_to_engine_at=retrieved,
        filing_date="2026-11-01",
    )
    (folder / "collection.json").write_text(
        json.dumps(
            {
                "is_synthetic": False,
                "identities": {"DELL": {"cik": "0001571996", "index_and_submissions_agree": True}},
                "filings": [row],
            }
        ),
        encoding="utf-8",
    )
    return folder


def headers(token, key="test"):
    return {"Authorization": "Bearer " + token, "Idempotency-Key": key}


@pytest.fixture
def workspace(db, tmp_path):
    initialize_review_store(db)
    folder = collection(tmp_path)
    import_collection(db, folder)
    _, author = provision(db, "operators", admin=True)
    _, reviewer = provision(db, "operators", admin=True)
    _, member = provision(db, "operators")
    with TestClient(app) as client:
        yield client, author, reviewer, member, sha("0001571996-26-000001"), folder


def body(client, token, fid, version=0):
    source = client.get("/api/v0/admin/sec/filings/" + fid, headers=headers(token)).json()
    return {
        "expected_version": version,
        "occurrence_window": "FY2026-Q3",
        "event": {
            "source_document_id": fid,
            "entity_ids": ["CO_DELL"],
            "event_type": "earnings",
            "factual_headline": "Test-only qualitative change",
            "published_at": "2026-11-01T10:00:00Z",
            "available_at": source["retrieved_at"],
            "claims": [
                {
                    "claim_text": TEXT,
                    "metric_id": None,
                    "unit": None,
                    "period": "FY2026-Q3",
                    "comparison_basis": "qualitative; no numeric comparison",
                    "old_value": None,
                    "new_value": None,
                    "source_span": {"start": 0, "end": len(TEXT)},
                    "source_url": source["source_url"],
                }
            ],
            "uncertainties": ["Fabricated text used only in automated tests"],
        },
    }


def approval(version=1):
    return dict(
        decision="approved",
        expected_version=version,
        note="Independent test-only review",
        rights_basis="Fabricated text for tests only",
        identity_confirmed=True,
        citation_confirmed=True,
        comparison_confirmed=True,
    )


def save(client, token, fid, payload, key="save"):
    return client.post(
        "/api/v0/admin/sec/filings/" + fid + "/drafts", headers=headers(token, key), json=payload
    )


def decide(client, token, did, payload, key="review"):
    return client.post(
        "/api/v0/admin/sec/drafts/" + did + "/reviews", headers=headers(token, key), json=payload
    )


def test_import_idempotency_isolation_and_plaintext(workspace, db):
    client, author, _, _, fid, folder = workspace
    assert import_collection(db, folder)["inserted"] == 0
    data = client.get("/api/v0/admin/sec/filings/" + fid, headers=headers(author)).json()
    assert data["source_text"] == TEXT
    assert data["feed_eligible"] is False and data["manifest"]["rights_status"] == "pending_review"
    assert plain_text("<ix:hidden>secret</ix:hidden><p>A &amp; B</p>") == "A & B"
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(filings)) == 1
        assert conn.scalar(select(func.count()).select_from(metadata.tables["rie_events"])) == 0


def test_demo_store_cannot_import_real_sources(db, tmp_path):
    initialize_demo(db)
    with pytest.raises(ValueError, match="synthetic"):
        initialize_review_store(db)
    with pytest.raises(ValueError, match="separate"):
        import_collection(db, collection(tmp_path))


@pytest.mark.parametrize("mutation", ["hash", "path", "url", "future", "identity"])
def test_import_rejects_tampering_atomically(db, tmp_path, mutation):
    initialize_review_store(db)
    folder = collection(tmp_path)
    manifest = json.loads((folder / "collection.json").read_text())
    row = manifest["filings"][0]
    if mutation == "hash":
        row["content_sha256"] = "0" * 64
    if mutation == "path":
        row["file"] = "../outside.html"
    if mutation == "url":
        row["url"] = "https://example.com/untrusted"
    if mutation == "future":
        row["retrieved_at"] = "2099-01-01T00:00:00Z"
    if mutation == "identity":
        row["cik"] = "0000000001"
    (folder / "collection.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        import_collection(db, folder)
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(filings)) == 0


def test_admin_only_and_no_future_review_leak(workspace):
    client, author, _, member, fid, _ = workspace
    for path in ["/api/v0/admin/sec/filings", "/api/v0/admin/sec/filings/" + fid]:
        assert client.get(path).status_code == 401
        assert client.get(path, headers=headers(member)).status_code == 403
    assert client.get("/review").status_code == 200
    assert client.get("/assets/sec_review.py").status_code == 404
    past = "2020-01-01T00:00:00Z"
    assert (
        client.get(
            "/api/v0/admin/sec/filings", params={"as_of": past}, headers=headers(author)
        ).json()["items"]
        == []
    )
    assert (
        client.get(
            "/api/v0/admin/sec/filings/" + fid, params={"as_of": past}, headers=headers(author)
        ).status_code
        == 404
    )


@pytest.mark.parametrize("mutation", ["quote", "issuer", "capture", "numeric", "metric"])
def test_draft_fails_closed(workspace, mutation):
    client, author, _, _, fid, _ = workspace
    payload = body(client, author, fid)
    event = payload["event"]
    claim = event["claims"][0]
    if mutation == "quote":
        claim["claim_text"] = "Invented statement"
    if mutation == "issuer":
        event["entity_ids"] = ["CO_SNDK"]
    if mutation == "capture":
        event["available_at"] = "2026-11-01T11:00:00Z"
    if mutation == "numeric":
        claim["new_value"] = 100
    if mutation == "metric":
        claim["metric_id"] = "SNDK_GROSS_MARGIN"
    assert save(client, author, fid, payload).status_code == 422


def test_review_versions_retries_and_no_publication(workspace, db):
    client, author, reviewer, _, fid, _ = workspace
    payload = body(client, author, fid)
    response = save(client, author, fid, payload)
    assert response.status_code == 200, response.text
    did = response.json()["id"]
    assert save(client, author, fid, payload).json() == response.json()
    assert save(client, reviewer, fid, payload, "stale").status_code == 409
    assert decide(client, author, did, approval()).status_code == 403
    bad = approval()
    bad["rights_basis"] = ""
    assert decide(client, reviewer, did, bad).status_code == 422
    before = datetime.now(UTC)
    response = decide(client, reviewer, did, approval())
    assert response.status_code == 200, response.text
    assert response.json()["feed_eligible"] is False
    assert decide(client, reviewer, did, approval()).json() == response.json()
    assert decide(client, reviewer, did, approval(), "new-review").status_code == 409
    old = client.get(
        "/api/v0/admin/sec/filings/" + fid,
        params={"as_of": before.isoformat()},
        headers=headers(author),
    ).json()
    assert old["versions"][0]["review"] is None
    changed = body(client, author, fid, 1)
    assert save(client, author, fid, changed, "v2").status_code == 200
    assert decide(client, reviewer, did, approval(), "stale-review").status_code == 409
    data = client.get("/api/v0/admin/sec/filings/" + fid, headers=headers(author)).json()
    assert len(data["versions"]) == 2 and data["versions"][0]["review"]["decision"] == "approved"
    assert data["versions"][1]["review"] is None
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(drafts)) == 2
        assert conn.scalar(select(func.count()).select_from(reviews)) == 1
        for name in ("rie_events", "rie_user_cards"):
            assert conn.scalar(select(func.count()).select_from(metadata.tables[name])) == 0


@pytest.mark.parametrize("kind", ["correction_of", "duplicate_of"])
def test_linked_events_require_current_approved_earlier_same_identity(
    workspace, db, tmp_path, kind
):
    client, author, reviewer, _, fid, _ = workspace
    old = save(client, author, fid, body(client, author, fid)).json()["id"]
    folder = collection(
        tmp_path, accession="0001571996-26-000002", retrieved="2026-11-02T12:00:00+00:00"
    )
    import_collection(db, folder)
    second = sha("0001571996-26-000002")
    payload = body(client, author, second)
    payload[kind] = old
    assert save(client, author, second, payload).status_code == 422
    assert decide(client, reviewer, old, approval()).status_code == 200
    bad = json.loads(json.dumps(payload))
    bad["occurrence_window"] = "different quarter"
    assert save(client, author, second, bad).status_code == 422
    assert save(client, author, second, payload).status_code == 200


def test_import_conflict_does_not_overwrite_original_capture(workspace, db):
    _, _, _, _, _, folder = workspace
    manifest = json.loads((folder / "collection.json").read_text())
    row = manifest["filings"][0]
    row["retrieved_at"] = row["first_available_to_engine_at"] = "2026-11-02T12:00:00+00:00"
    (folder / "collection.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="overwritten"):
        import_collection(db, folder)


def test_registered_metric_and_write_key_conflict(workspace):
    client, author, _, _, fid, _ = workspace
    payload = body(client, author, fid)
    payload["event"]["claims"][0]["metric_id"] = "DELL_ISG_MARGIN"
    assert save(client, author, fid, payload).status_code == 200
    payload["event"]["factual_headline"] = "Changed payload under the same key"
    assert save(client, author, fid, payload).status_code == 409


def test_concurrent_operators_cannot_overwrite_draft(workspace, db):
    client, author, reviewer, _, fid, _ = workspace
    payload = body(client, author, fid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda token: save(client, token, fid, payload, "concurrent"), [author, reviewer]
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 409]
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(drafts)) == 1
