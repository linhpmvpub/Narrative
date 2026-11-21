"""Synthetic campaign accounts: scoped permissions, idempotency, meaningful progress."""

import json

import pytest
from sqlalchemy import func, select
from test_annotations import assigned as assigned
from test_annotations import base, body, language
from test_development_feed import enabled as enabled
from test_financials_mobile import financial_store as financial_store
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.evaluation.campaign import prepare, progress
from engine.evaluation.consensus import freeze
from engine.evaluation.filing_labels import packet
from engine.models.schema_v4 import tokens, users
from engine.models.schema_v10 import assignments, labels
from engine.models.schema_v12 import roster


@pytest.fixture
def campaign(assigned, financial_store, tmp_path):
    from datetime import datetime

    pid, rows = assigned
    with financial_store.connect() as conn:
        pack = packet(conn, datetime.fromisoformat(rows[0]["as_of"]))
    freeze(financial_store, pack)
    folder = tmp_path / "credentials"
    prepare(financial_store, pid, folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    people = {
        slot: (uid, (folder / (slot + ".txt")).read_text().strip())
        for slot, uid in manifest["accounts"].items()
    }
    return pid, rows, folder, people


def test_prepare_repeat_and_scoped_accounts(campaign, financial_store, client, identities):
    pid, rows, folder, people = campaign
    assert prepare(financial_store, pid, folder)["status"] == "existing"
    with financial_store.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(roster)) == 3
        assert conn.scalar(select(func.count()).select_from(assignments)) == 2
        assert conn.scalar(select(func.count()).select_from(labels)) == 0
        roles = (
            conn.execute(
                select(users.c.role).where(users.c.id.in_([u[0] for u in people.values()]))
            )
            .scalars()
            .all()
        )
        assert roles == ["member"] * 3
    a, b, judge = (people[k] for k in ("reviewer_a", "reviewer_b", "adjudicator"))
    url = f"/api/v0/admin/evaluation/{pid}"
    assert client.get(url + "/quality", headers=headers(a)).status_code == 403
    assert client.get(url + "/quality", headers=headers(judge)).status_code == 200
    assert client.get(url + "/export", headers=headers(judge)).status_code == 403
    assert (
        client.get(f"/api/v0/annotations/{pid}/export", headers=headers(judge)).status_code == 403
    )
    assert (
        client.get(
            "/api/v0/admin/evaluation/" + "0" * 64 + "/quality", headers=headers(judge)
        ).status_code
        == 403
    )
    for person in (judge, identities[0]):
        assert client.get(base(pid, rows[0]["id"]), headers=headers(person)).status_code == 404
    for person in (a, b):
        assert client.get(base(pid, rows[0]["id"]), headers=headers(person)).status_code == 200
        assert (
            client.get("/api/v0/admin/evaluation/packets", headers=headers(person)).json()["items"]
            == []
        )


def test_progress_revisions_blinding_and_adjudication(campaign, financial_store, client):
    pid, rows, folder, people = campaign
    c = language(rows)
    a, b, judge = (people[k] for k in ("reviewer_a", "reviewer_b", "adjudicator"))
    url = base(pid, c["id"]) + "/labels"
    for version in (0, 1):
        assert (
            client.post(url, headers=headers(a), json=body(c, expected_version=version)).status_code
            == 200
        )
    with financial_store.connect() as conn:
        p = progress(conn, pid)
    assert p["reviewers"][0]["submitted"] == 1 and p["cases_with_two_votes"] == 0
    assert p["required_independent_labels"] == 8
    assert client.get(base(pid, c["id"]), headers=headers(b)).json()["my_label"] is None
    assert (
        client.post(
            url, headers=headers(b), json=body(c, language="ISSUER_ATTRIBUTION")
        ).status_code
        == 200
    )
    evaluation = f"/api/v0/admin/evaluation/{pid}"
    s = client.get(evaluation + "/cases/" + c["id"], headers=headers(judge)).json()
    result = client.post(
        evaluation + "/cases/" + c["id"] + "/adjudications",
        headers=headers(judge),
        json={
            "expected_vote_hash": s["vote_hash"],
            "expected_decision_version": 0,
            "outcome": "RESOLVED",
            "independent_of_extractor": True,
            "reason": "Synthetic adjudication based on independent source review",
            "language": "NO_CAUSAL_CLAIM",
        },
    )
    assert result.status_code == 200
    p = client.get(evaluation + "/quality", headers=headers(judge)).json()["campaign_progress"]
    assert p["cases_with_two_votes"] == 1 and p["states"]["ADJUDICATED"] == 1
    assert p["unresolved_disagreements"] == 0
    client.post(url, headers=headers(a), json=body(c, expected_version=2))
    p = client.get(evaluation + "/quality", headers=headers(judge)).json()["campaign_progress"]
    assert p["stale_decisions"] == 1 and p["unresolved_disagreements"] == 1
    from engine.filing_evidence import snapshots

    with financial_store.begin() as conn:
        conn.execute(snapshots.delete())
    with financial_store.connect() as conn:
        p = progress(conn, pid)
    assert p["reviewers"][0]["submitted"] == 1
    assert p["reviewers"][0]["current_source_completed"] == 0
    assert p["reviewers"][0]["source_blocked"] == 4
    assert p["reviewers"][0]["actionable_remaining"] == 0
    assert p["states"]["SOURCE_EXCLUDED"] == 4


def test_revoked_credential_and_existing_labels_fail_closed(campaign, financial_store):
    pid, rows, folder, people = campaign
    with financial_store.begin() as conn:
        conn.execute(
            tokens.update().where(tokens.c.user_id == people["reviewer_a"][0]).values(revoked=True)
        )
    with pytest.raises(ValueError, match="rotation"):
        prepare(financial_store, pid, folder)
    with financial_store.connect() as conn:
        assert progress(conn, pid)["reviewers"][0]["credential_active"] is False


def test_prepare_requires_predictions_and_preserves_existing_labels(
    assigned, financial_store, client, identities, tmp_path
):
    from datetime import datetime

    pid, rows = assigned
    with pytest.raises(ValueError, match="freeze"):
        prepare(financial_store, pid, tmp_path / "missing")
    with financial_store.connect() as conn:
        freeze_pack = packet(conn, datetime.fromisoformat(rows[0]["as_of"]))
    freeze(financial_store, freeze_pack)
    c = language(rows)
    client.post(base(pid, c["id"]) + "/labels", headers=headers(identities[0]), json=body(c))
    with pytest.raises(ValueError, match="reconciliation"):
        prepare(financial_store, pid, tmp_path / "blocked")
    with financial_store.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(labels)) == 1
        assert conn.scalar(select(func.count()).select_from(assignments)) == 1
        assert conn.scalar(select(func.count()).select_from(roster)) == 0
