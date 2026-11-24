from datetime import UTC, datetime, timedelta

import pytest
import test_sec_review as sec_fixture
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_reviewed_ingestion import grant, ingest
from test_sec_review import approval, body, decide, headers, save
from test_sec_review import workspace as workspace


@pytest.fixture
def ready_operation(monkeypatch, request, dossier, tmp_path):
    monkeypatch.setattr(sec_fixture, "TEXT", "The ramp of our systems increased this quarter.")
    work = request.getfixturevalue("workspace")
    client, author, reviewer, member, fid, _ = work
    root, data = dossier
    data["identifiers"] = {"CIK": "1571996"}
    data["factor_bindings"] = [{"id": "operating", "factor_id": "p",
        "topic_terms": ["systems"], "context_terms": ["our systems"], "change_terms": ["ramp"],
        "kind": "ISSUER_OPERATING_CONTEXT", "issuer_supply_scope": True, "narrative_ids": ["n"],
        "scope": "Synthetic own-product context", "reviewed_at": data["available_at"],
        "review_until": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "evidence": data["relationships"][0]["evidence"]}]
    seal(root, data)
    registry = tmp_path / "profiles"
    registry.mkdir()
    root.rename(registry / "example")
    monkeypatch.setenv("COMPANY_PROFILE_ROOT", str(registry))
    did = save(client, author, fid, {**body(client, author, fid), "author_kind": "AI"}).json()["id"]
    assert decide(client, reviewer, did, {**approval(), "reviewer_kind": "AI_INDEPENDENT"}).status_code == 200
    assert grant(client, reviewer, fid).status_code == 200
    assert ingest(client, reviewer, did).status_code == 200
    return work, registry


def test_operating_card_is_private_and_separate_from_supplier_roles(ready_operation):
    (client, _, _, member, _, _), _ = ready_operation
    route = "/api/v0/news/reviewed-operations"
    assert client.get(route).status_code == 401
    result = client.get(route, headers=headers(member)).json()
    assert len(result["items"]) == 1 and not result["graph_modified"]
    card = result["items"][0]
    assert card["context_kind"] == "ISSUER_OPERATING_CONTEXT" and card["roles"] == []
    assert card["impact"] == "UNKNOWN" and card["delivery"] == "disabled"
    assert card["reviewer_kind"] == "AI_INDEPENDENT" and card["decision_trace"]
    assert client.get("/api/v0/news/reviewed-roles", headers=headers(member)).json()["items"] == []


@pytest.mark.parametrize("fault", ["permission", "source", "issuer"])
def test_operating_card_rechecks_provenance(ready_operation, fault):
    (client, _, reviewer, member, fid, _), registry = ready_operation
    if fault == "permission":
        assert grant(client, reviewer, fid, version=1, status="revoked").status_code == 200
    elif fault == "source":
        (registry / "example/source.html").write_text("changed")
    else:
        import json

        root = registry / "example"
        data = json.loads((root / "profile-v1.json").read_text())
        data["identifiers"] = {"CIK": "999"}
        seal(root, data)
    assert client.get("/api/v0/news/reviewed-operations", headers=headers(member)).json()["items"] == []
