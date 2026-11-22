"""Synthetic dossier tests: evidence, temporal routing, corrections and privacy."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.company_profiles import COMPONENTS, ProfileBundle, feed, framework, load_bundle, project

QUOTE = "The example company sells processors and reports that market access affects its revenue."


def seal(root, data, name="profile-v1.json"):
    raw = json.dumps(data).encode()
    (root / name).write_bytes(raw)
    (root / "current.json").write_text(json.dumps({"id": data["id"], "version": data["version"],
        "file": name, "sha256": hashlib.sha256(raw).hexdigest(), "status": "active"}))


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "true")
    monkeypatch.setenv("COMPANY_PROFILE_ROOT", str(tmp_path))
    root = tmp_path / "example"
    root.mkdir()
    raw = ("<html><p>" + QUOTE + "</p></html>").encode()
    (root / "source.html").write_bytes(raw)
    now = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    published = "2024-01-01T00:00:00+00:00"
    evidence = [{"source_id": "s", "quote": QUOTE}]

    def rel(id, type, a, b):
        return {"id": id, "type": type, "from_id": a, "to_id": b, "scope": "Synthetic test",
                "valid_from": published, "known_at": now, "status": "SOURCE_BACKED",
                "basis": "SOURCE_REPORTED", "conditions": ["Only the stated product"],
                "evidence": evidence}

    data = {"id": "example", "version": 1, "company_id": "co", "ticker": "TEST",
        "legal_name": "Synthetic Example", "identifiers": {}, "snapshot_at": published,
        "available_at": now, "description": "Synthetic dossier only", "industry_modules": ["test"],
        "sources": [{"id": "s", "file": "source.html", "url": "https://example.test/source",
                     "sha256": hashlib.sha256(raw).hexdigest(), "published_at": published,
                     "retrieved_at": now}],
        "components": [{"key": "products", "status": "SOURCED", "summary": "Example product",
                        "evidence": evidence}],
        "nodes": [{"id": id, "kind": kind, "label": id} for id, kind in
                  [("co", "company"), ("p", "product"), ("f", "factor"), ("m", "metric")]],
        "relationships": [rel("owns", "SELLS", "co", "p"), rel("applies", "APPLIES_TO", "f", "p"),
                          rel("effect", "AFFECTS_REVENUE", "p", "m")],
        "narratives": [{"id": "n", "version": 1, "title": "Example narrative", "thesis": "Test",
            "company_id": "co", "scope": "Test scope", "horizon": "Historical test",
            "watched_nodes": ["m"], "assumptions": ["Access remains possible"],
            "supporting_evidence": ["Access granted"], "challenging_evidence": ["Access restricted"],
            "reconsider_when": ["Source correction"], "unknowns": ["Price effect unknown"],
            "challenge_event_types": ["ACCESS_RESTRICTED"], "available_at": now}],
        "events": [{"id": "e", "version": 1, "type": "ACCESS_RESTRICTED", "headline": "Test event",
            "summary": "Synthetic only", "anchors": ["f"], "occurred_at": published,
            "available_at": now, "evidence": evidence}]}
    seal(root, data)
    return root, data


def test_profile_to_card_without_price_prediction(dossier):
    root, data = dossier
    b = load_bundle(root)
    result = project(b)
    assert len(result["components"]) == len(COMPONENTS) == 42
    assert result["coverage"] == {"SOURCED": 1, "UNKNOWN": 41}
    card = result["cards"][0]
    assert [r["id"] for r in card["path"]] == ["applies", "effect"]
    assert card["stance"] == "CHALLENGES_ASSUMPTION"
    assert card["price_impact"] == "UNKNOWN" and card["delivery"] == "disabled"
    assert card["global_graph_approved"] is False
    assert "source.html" not in json.dumps(result)
    assert feed(datetime(2024, 1, 1, tzinfo=UTC))["items"] == []
    assert len(feed()["items"]) == 1


@pytest.mark.parametrize("fault", ["quote", "source", "bundle", "withdraw", "version", "escape"])
def test_corrupt_or_withdrawn_source_is_withheld(dossier, fault):
    root, data = dossier
    if fault == "quote":
        data["events"][0]["evidence"] = [{"source_id": "s", "quote": "Invented source text"}]
        seal(root, data)
    elif fault == "source":
        (root / "source.html").write_text("changed")
    elif fault == "bundle":
        with (root / "profile-v1.json").open("a") as stream:
            stream.write(" ")
    else:
        r = json.loads((root / "current.json").read_text())
        if fault == "withdraw":
            r["status"] = "withdrawn"
        elif fault == "version":
            r["version"] = 9
        else:
            r["file"] = "../outside.json"
        (root / "current.json").write_text(json.dumps(r))
    assert feed()["items"] == []
    assert feed()["withheld"] == 1


@pytest.mark.parametrize("status", ["CANDIDATE", "DISPUTED", "REVOKED", "STALE"])
def test_unapproved_mechanism_cannot_produce_card(dossier, status):
    _, data = dossier
    data["relationships"][-1]["status"] = status
    assert project(ProfileBundle.model_validate(data))["cards"] == []


@pytest.mark.parametrize("fault", ["type", "missing", "self", "conditions", "clock", "source_clock",
                                  "narrative_scope", "private_narrative", "future_period"])
def test_contract_rejects_ambiguous_or_invalid_data(dossier, fault):
    _, data = dossier
    if fault == "type":
        data["relationships"][0]["type"] = "AFFECTS_COST"
    elif fault == "missing":
        data["relationships"][0]["to_id"] = "absent"
    elif fault == "self":
        data["relationships"][0]["to_id"] = "co"
    elif fault == "conditions":
        data["relationships"][-1]["conditions"] = []
    elif fault == "clock":
        data["relationships"][-1]["known_at"] = "2020-01-01T00:00:00Z"
    elif fault == "source_clock":
        data["sources"][0]["retrieved_at"] = "2030-01-01T00:00:00Z"
    elif fault == "narrative_scope":
        data["narratives"][0]["company_id"] = "another-company"
    elif fault == "private_narrative":
        data["narratives"][0]["audience"] = "PRIVATE_USER"
    else:
        data["observations"] = [{"id": "o", "node_id": "m", "value": "10", "unit": "USD",
            "period_start": "2023-01-01", "period_end": "2030-01-01", "scope": "Synthetic",
            "basis": "GAAP", "evidence": data["events"][0]["evidence"]}]
    with pytest.raises(ValueError):
        ProfileBundle.model_validate(data)


def test_new_revision_replaces_old_and_expired_path_disappears(dossier):
    root, data = dossier
    old = (root / "profile-v1.json").read_bytes()
    updated = deepcopy(data)
    updated["version"] = 2
    updated["events"][0]["version"] = 2
    updated["relationships"][-1]["valid_from"] = "2023-01-01T00:00:00Z"
    updated["relationships"][-1]["valid_until"] = "2024-01-01T00:00:00Z"
    seal(root, updated, "profile-v2.json")
    result = feed()["items"][0]
    assert result["version"] == 2 and result["cards"] == []
    assert (root / "profile-v1.json").read_bytes() == old


def test_structural_path_does_not_assert_narrative_direction(dossier):
    _, data = dossier
    data["relationships"][-1]["type"] = "HAS_METRIC"
    assert project(ProfileBundle.model_validate(data))["cards"][0]["stance"] == "RELATED_INFORMATION"


def test_profile_api_private_and_read_only(client, identities, dossier):
    from engine.mobile_gateway import allowed

    assert client.get("/api/v0/news/profiles").status_code == 401
    r = client.get("/api/v0/news/profiles", headers=headers(identities[0]))
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    assert "no-store" in r.headers["cache-control"]
    assert "source.html" not in r.text
    assert client.get("/api/v0/news/profiles?as_of=2024-01-01T00:00:00",
                      headers=headers(identities[0])).status_code == 422
    assert allowed("GET", "/api/v0/news/profiles")
    assert not allowed("POST", "/api/v0/news/profiles")


def test_disabled_and_registry(dossier, monkeypatch):
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "false")
    assert feed()["items"] == []
    assert framework()["relationships"]["SELLS"]["family"] == "STRUCTURAL"
    with pytest.raises(ValueError):
        feed(datetime(2025, 1, 1))


def test_disconnected_company_and_direct_metric_anchor(dossier):
    _, data = dossier
    detached = deepcopy(data)
    detached["relationships"][0]["status"] = "REVOKED"
    assert project(ProfileBundle.model_validate(detached))["cards"] == []
    data["relationships"][-1]["type"] = "HAS_METRIC"
    data["events"][0]["anchors"] = ["m"]
    card = project(ProfileBundle.model_validate(data))["cards"][0]
    assert card["path"] == [] and card["stance"] == "RELATED_INFORMATION"


def test_more_than_two_mechanisms_are_not_routed(dossier):
    _, data = dossier
    data["nodes"].extend([{"id": "m2", "kind": "metric", "label": "m2"},
                          {"id": "m3", "kind": "metric", "label": "m3"}])
    for id, a, b in [("margins", "m", "m2"), ("cash", "m2", "m3")]:
        r = deepcopy(data["relationships"][-1])
        r.update(id=id, type="AFFECTS_MARGIN", from_id=a, to_id=b)
        data["relationships"].append(r)
    data["narratives"][0]["watched_nodes"] = ["m3"]
    assert project(ProfileBundle.model_validate(data))["cards"] == []
    data["narratives"][0]["watched_nodes"] = ["m2"]
    assert len(project(ProfileBundle.model_validate(data))["cards"]) == 1


def test_duplicate_paths_bundle_once_and_opposing_rules_are_mixed(dossier):
    _, data = dossier
    duplicate = deepcopy(data["relationships"][-1])
    duplicate["id"] = "alternative"
    data["relationships"].append(duplicate)
    data["narratives"][0]["support_event_types"] = ["ACCESS_RESTRICTED"]
    cards = project(ProfileBundle.model_validate(data))["cards"]
    assert len(cards) == 1 and cards[0]["alternative_paths"] == 1
    assert cards[0]["stance"] == "MIXED"


def test_operator_stage_and_withdraw_preserve_versions(dossier):
    from engine.company_profiles import stage, withdraw

    root, data = dossier
    old = (root / "profile-v1.json").read_bytes()
    with pytest.raises(ValueError):
        stage(root, ProfileBundle.model_validate(data))
    data["version"] = 2
    with pytest.raises(ValueError, match="later availability"):
        stage(root, ProfileBundle.model_validate(data))
    data["available_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    receipt = stage(root, ProfileBundle.model_validate(data))
    assert receipt["version"] == 2 and load_bundle(root).version == 2
    assert (root / "profile-v1.json").read_bytes() == old
    withdraw(root)
    assert feed()["items"] == []


def test_duplicate_profile_identity_and_writer_lock(dossier):
    import shutil

    from engine.company_profiles import stage, writer_lock

    root, data = dossier
    with writer_lock(root), pytest.raises(FileExistsError):
        stage(root, ProfileBundle.model_validate(data))
    assert not (root / "writer.lock").exists()
    shutil.copytree(root, root.parent / "duplicate")
    assert feed()["items"] == [] and feed()["withheld"] == 2


def test_profile_can_exist_before_narratives_or_events(dossier):
    _, data = dossier
    data.pop("events")
    data.pop("narratives")
    result = project(ProfileBundle.model_validate(data))
    assert result["cards"] == result["narratives"] == []
    assert result["coverage"]["SOURCED"] == 1
