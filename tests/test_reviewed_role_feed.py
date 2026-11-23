"""Synthetic reviewed SEC -> role card, without real approvals or delivery."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import test_sec_review as sec_fixture
from sqlalchemy import select, update
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_reviewed_ingestion import grant, ingest
from test_sec_review import approval, body, decide, headers, save
from test_sec_review import workspace as workspace

from engine.ingestion.reviewed import events, evidence, versions
from engine.models.schema_v5 import filings, reviews

TEXT = "We purchase memory from Synthetic Example, Inc."


@pytest.fixture
def ready_role(monkeypatch, request, dossier, tmp_path):
    monkeypatch.setattr(sec_fixture, "TEXT", TEXT)
    work = request.getfixturevalue("workspace")
    client, author, reviewer, member, fid, _ = work
    root, data = dossier
    data["identifiers"] = {"CIK": "456"}
    data["factor_bindings"] = [{"id": "supplier", "factor_id": "p", "topic_terms": ["memory"],
        "context_terms": ["memory"], "kind": "SUPPLIER_ROLE_DISCLOSURE",
        "disclosure_terms": ["We purchase"], "narrative_ids": ["n"],
        "scope": "Synthetic product context", "reviewed_at": data["available_at"],
        "review_until": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "evidence": data["relationships"][0]["evidence"]}]
    seal(root, data)
    registry = tmp_path / "profiles"
    registry.mkdir()
    root.rename(registry / "example")
    monkeypatch.setenv("COMPANY_PROFILE_ROOT", str(registry))
    draft = {**body(client, author, fid), "author_kind": "AI"}
    did = save(client, author, fid, draft).json()["id"]
    assert decide(client, reviewer, did, {**approval(), "reviewer_kind": "AI_INDEPENDENT"}).status_code == 200
    assert grant(client, reviewer, fid).status_code == 200
    response = ingest(client, reviewer, did)
    assert response.status_code == 200, response.text
    return work, did, response.json(), registry


def get(ready):
    work = ready[0]
    return work[0].get("/api/v0/news/reviewed-roles", headers=headers(work[3]))


def test_reviewed_source_roles_are_private_read_only_and_explainable(ready_role):
    response = get(ready_role)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["items"]) == 1 and result["delivery"] == "disabled"
    card = result["items"][0]
    assert card["issuer"] == "DELL" and card["ticker"] == "TEST"
    assert card["reviewer_kind"] == "AI_INDEPENDENT"
    assert card["roles"][0]["buyer_cik"] == "1571996"
    assert card["roles"][0]["product"] == "memory"
    assert card["source_span"]["start"] == 0 and card["decision_trace"]
    assert card["roles"][0]["relationship_verified"] is False
    assert not result["graph_modified"] and card["impact"] == "UNKNOWN"
    assert all(word not in response.text for word in ("reviewer_id", "rights_basis", "operator_id"))
    assert ready_role[0][0].get("/api/v0/news/reviewed-roles").status_code == 401


@pytest.mark.parametrize("fault", ["permission", "source_text", "review", "canonical", "evidence",
                                  "new_unreviewed_draft", "profile_source", "expired_profile"])
def test_current_invalidity_hides_card_without_falling_back(db, ready_role, fault):
    work, did, _, registry = ready_role
    client, author, reviewer, _, fid, _ = work
    if fault == "permission":
        assert grant(client, reviewer, fid, version=1, status="revoked").status_code == 200
    elif fault == "new_unreviewed_draft":
        assert save(client, author, fid, body(client, author, fid, version=1), key="new").status_code == 200
    elif fault == "profile_source":
        (registry / "example" / "source.html").write_text("changed")
    elif fault == "expired_profile":
        import json

        root = registry / "example"
        data = json.loads((root / "profile-v1.json").read_text())
        data["factor_bindings"][0]["review_until"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        seal(root, data)
    else:
        with db.begin() as conn:
            if fault == "source_text":
                conn.execute(update(filings).where(filings.c.id == fid).values(source_text="changed"))
            elif fault == "review":
                conn.execute(update(reviews).where(reviews.c.draft_id == did).values(decision="rejected"))
            elif fault == "evidence":
                conn.execute(update(evidence).values(excerpt="changed"))
            else:
                row = conn.execute(select(versions)).mappings().one()
                value = dict(row["normalized_claim"])
                value["fact"] = {}
                conn.execute(update(versions).where(versions.c.id == row["id"]).values(normalized_claim=value))
    response = get(ready_role)
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


@pytest.mark.parametrize("fault", ["new_canonical", "withdrawn_source", "missing_source"])
def test_new_lifecycle_or_canonical_version_never_falls_back(db, ready_role, fault):
    with db.begin() as conn:
        version = dict(conn.execute(select(versions)).mappings().one())
        version["id"] = str(uuid4())
        version["available_at"] = datetime.now(UTC)
        version["normalized_claim"] = {"source_status": "withdrawn" if fault != "missing_source"
                                       else "missing_unconfirmed"}
        if fault == "new_canonical":
            version["version_number"] += 1
        else:
            filing = conn.execute(select(filings)).mappings().one()
            event = dict(conn.execute(select(events)).mappings().one())
            event["id"] = "development_sec_notice:" + filing["ticker"] + ":" + filing["accession"]
            event["canonical_event_key"] = event["id"]
            conn.execute(events.insert().values(**event))
            version["event_id"] = event["id"]
        conn.execute(versions.insert().values(**version))
    assert get(ready_role).json()["items"] == []
