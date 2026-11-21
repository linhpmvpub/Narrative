"""Real-source pathway acceptance with fabricated local evidence, no real approvals."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update
from test_sec_review import (
    approval,
    body,
    collection,
    decide,
    headers,
    save,
)
from test_sec_review import workspace as workspace

from engine.models.contracts import utc
from engine.models.schema_v5 import drafts, filings, reviews
from engine.models.schema_v6 import metadata, permissions
from engine.sec_review import import_collection, sha


def grant(client, token, fid, *, version=0, status="approved", **overrides):
    payload = dict(
        expected_permission_version=version,
        status=status,
        cik="0001571996",
        evidence_url="https://www.sec.gov/privacy.htm",
        rights_note="Fabricated test source: permitted for test use only",
        identity_note="Test-only company and capture identity confirmed",
        identity_confirmed=True,
        valid_until=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    payload.update(overrides)
    return client.post(
        f"/api/v0/admin/sec/filings/{fid}/permissions",
        json=payload,
        headers=headers(token, f"permission-{version}-{status}"),
    )


def ingest(client, token, did, *, version=1, permission=1, at=None, key="ingest"):
    return client.post(
        f"/api/v0/admin/sec/drafts/{did}/ingest",
        headers=headers(token, key),
        json={
            "expected_version": version,
            "expected_permission_version": permission,
            "as_of": (at or datetime.now(UTC)).isoformat(),
        },
    )


def ready(workspace, *, approve=True, permit=True):
    client, author, reviewer, _, fid, _ = workspace
    did = save(client, author, fid, body(client, author, fid)).json()["id"]
    if approve:
        response = decide(client, reviewer, did, approval())
        assert response.status_code == 200, response.text
    if permit:
        response = grant(client, reviewer, fid)
        assert response.status_code == 200, response.text
    return did


def count(db, name):
    with db.connect() as conn:
        return conn.scalar(select(func.count()).select_from(metadata.tables[name]))


def assert_no_canonical(db):
    for name in (
        "rie_events",
        "rie_event_versions",
        "rie_documents",
        "rie_evidence",
        "rie_sec_promotions",
    ):
        assert count(db, name) == 0, name


def snapshot(client, token, at=None):
    return client.get(
        "/api/v0/admin/sec/events",
        headers=headers(token),
        params={"as_of": at.isoformat()} if at else {},
    ).json()["items"]


def test_approved_ingestion_provenance_and_no_backdating(workspace, db):
    client, author, _, _, fid, _ = workspace
    did = ready(workspace)
    cutoff = datetime.now(UTC)
    result = ingest(client, author, did, at=cutoff)
    assert result.status_code == 200, result.text
    data = result.json()
    assert (
        data["status"] == "ingested"
        and data["delivery"] == "disabled"
        and not data["feed_eligible"]
    )
    assert snapshot(client, author, cutoff) == []
    visible = snapshot(client, author)
    assert len(visible) == 1 and visible[0]["event_version_id"] == data["event_version_id"]
    with db.connect() as conn:
        event = conn.execute(select(metadata.tables["rie_events"])).mappings().one()
        version = conn.execute(select(metadata.tables["rie_event_versions"])).mappings().one()
        ev = conn.execute(select(metadata.tables["rie_evidence"])).mappings().one()
        doc = conn.execute(select(metadata.tables["rie_documents"])).mappings().one()
        assert not event["is_synthetic"] and event["occurred_at"] is None
        assert utc(version["available_at"]) >= cutoff
        assert utc(doc["available_at"]) < cutoff
        assert (
            version["evidence_quality"] is None
            and version["normalized_claim"]["materiality"] == "UNKNOWN"
        )
        assert ev["verified_by"] and ev["quoted_claim"] == "Revenue increased."
        assert doc["metadata"]["filing_id"] == fid and doc["source_url"] == ev["url"]
    for name in ("rie_alerts", "rie_user_cards", "rie_match_decisions", "rie_story_entries"):
        assert count(db, name) == 0
    again = ingest(client, author, did, at=cutoff)
    assert again.json() == data
    retry = ingest(client, author, did, key="retry-new-key")
    assert retry.status_code == 200 and retry.json()["idempotent_retry"]
    assert count(db, "rie_sec_promotions") == count(db, "rie_event_versions") == 1


@pytest.mark.parametrize("missing", ["review", "permission"])
def test_requires_distinct_review_and_permission(workspace, db, missing):
    did = ready(workspace, approve=missing != "review", permit=missing != "permission")
    client, author, *_ = workspace
    assert ingest(client, author, did).status_code == 409
    assert_no_canonical(db)


@pytest.mark.parametrize(
    "problem",
    [
        "stale_draft",
        "revoked",
        "expired",
        "future_permission",
        "future_review",
        "stale_permission",
        "future_cutoff",
        "old_cutoff",
        "text",
        "payload",
        "identity",
        "proof",
    ],
)
def test_revalidates_before_any_canonical_write(workspace, db, problem):
    client, author, reviewer, _, fid, _ = workspace
    did = ready(workspace)
    at = None
    if problem == "stale_draft":
        assert save(client, author, fid, body(client, author, fid, 1), "v2").status_code == 200
    if problem == "revoked":
        assert grant(client, reviewer, fid, version=1, status="revoked").status_code == 200
    if problem == "stale_permission":
        assert grant(client, reviewer, fid, version=1).status_code == 200
    if problem == "future_cutoff":
        at = datetime.now(UTC) + timedelta(days=1)
    if problem == "old_cutoff":
        at = datetime(2026, 11, 1, tzinfo=UTC)
    with db.begin() as conn:
        if problem == "expired":
            conn.execute(
                update(permissions).values(valid_until=datetime.now(UTC) - timedelta(seconds=1))
            )
        if problem == "future_permission":
            conn.execute(
                update(permissions).values(recorded_at=datetime.now(UTC) + timedelta(days=1))
            )
        if problem == "future_review":
            conn.execute(update(reviews).values(reviewed_at=datetime.now(UTC) + timedelta(days=1)))
        if problem == "text":
            conn.execute(update(filings).values(source_text="Tampered source"))
        if problem == "payload":
            payload = conn.scalar(select(drafts.c.payload))
            payload["event"]["claims"][0]["claim_text"] = "Invented claim"
            conn.execute(update(drafts).values(payload=payload))
        if problem == "identity":
            payload = conn.scalar(select(permissions.c.payload))
            payload["cik"] = "0000000001"
            conn.execute(update(permissions).values(payload=payload))
        if problem == "proof":
            payload = conn.scalar(select(reviews.c.payload))
            payload["citation_confirmed"] = False
            conn.execute(update(reviews).values(payload=payload))
    response = ingest(client, author, did, at=at)
    assert response.status_code == 409, response.text
    assert_no_canonical(db)


def test_permission_authorization_history_and_revocation_snapshot(workspace, db):
    client, author, reviewer, member, fid, _ = workspace
    assert grant(client, member, fid).status_code == 403
    assert grant(client, reviewer, fid, cik="0000000001").status_code == 422
    assert grant(client, reviewer, fid, identity_confirmed=False).status_code == 422
    did = ready(workspace)
    path = f"/api/v0/admin/sec/drafts/{did}/ingest"
    assert client.post(path, json={}).status_code == 401
    assert ingest(client, member, did).status_code == 403
    assert ingest(client, author, did).status_code == 200
    before = datetime.now(UTC)
    assert len(snapshot(client, author, before)) == 1
    assert grant(client, reviewer, fid, version=1, status="revoked").status_code == 200
    assert snapshot(client, author) == []
    assert len(snapshot(client, author, before)) == 1
    assert ingest(client, author, did, key="after-revocation").status_code == 409
    assert count(db, "rie_event_versions") == 1


def second(workspace, db, tmp_path, *, target, kind, text="Revenue increased.", number=2):
    client, author, reviewer, _, _, _ = workspace
    accession = f"0001571996-26-{number:06d}"
    folder = collection(
        tmp_path, accession=accession, retrieved=f"2026-11-{number:02d}T12:00:00+00:00"
    )
    manifest = json.loads((folder / "collection.json").read_text())
    html = "<p>" + text + "</p>"
    (folder / "filing.html").write_text(html)
    manifest["filings"][0]["content_sha256"] = sha(html)
    (folder / "collection.json").write_text(json.dumps(manifest))
    import_collection(db, folder)
    fid = sha(accession)
    payload = body(client, author, fid)
    payload[kind] = target
    claim = payload["event"]["claims"][0]
    claim["claim_text"] = text
    claim["source_span"]["end"] = len(text)
    response = save(client, author, fid, payload)
    assert response.status_code == 200, response.text
    did = response.json()["id"]
    assert decide(client, reviewer, did, approval()).status_code == 200
    assert grant(client, reviewer, fid).status_code == 200
    return did


def test_correction_and_old_reprint_preserve_temporal_versions(workspace, db, tmp_path):
    client, author, *_ = workspace
    original = ready(workspace)
    first = ingest(client, author, original).json()
    before = datetime.now(UTC)
    correction = second(
        workspace, db, tmp_path, target=original, kind="correction_of", text="Revenue decreased."
    )
    response = ingest(client, author, correction)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "versioned_correction"
    assert snapshot(client, author)[0]["version"] == 2
    assert snapshot(client, author, before)[0]["version"] == 1
    reprint = second(workspace, db, tmp_path, target=original, kind="duplicate_of", number=3)
    response = ingest(client, author, reprint)
    assert response.status_code == 200, response.text
    assert (
        response.json()["status"] == "duplicate"
        and response.json()["event_version_id"] == first["event_version_id"]
    )
    assert count(db, "rie_event_versions") == 2 and count(db, "rie_events") == 1
    assert snapshot(client, author)[0]["version"] == 2


@pytest.mark.parametrize(
    "kind,text", [("duplicate_of", "Revenue decreased."), ("correction_of", "Revenue increased.")]
)
def test_review_does_not_override_reprint_correction_rules(workspace, db, tmp_path, kind, text):
    client, author, *_ = workspace
    original = ready(workspace)
    assert ingest(client, author, original).status_code == 200
    did = second(workspace, db, tmp_path, target=original, kind=kind, text=text)
    response = ingest(client, author, did)
    assert response.status_code == 409, response.text
    assert count(db, "rie_event_versions") == 1 and count(db, "rie_documents") == 1


def test_concurrent_ingestion_deduplicates_across_operators(workspace, db):
    client, author, reviewer, *_ = workspace
    did = ready(workspace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda token: ingest(client, token, did), [author, reviewer]))
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert len({r.json()["event_version_id"] for r in results}) == 1
    assert (
        count(db, "rie_events")
        == count(db, "rie_event_versions")
        == count(db, "rie_sec_promotions")
        == 1
    )
