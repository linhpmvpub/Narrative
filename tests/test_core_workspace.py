"""Core UI projection regressions, using synthetic source fixtures only."""

import copy
import json

import pytest
from test_commodity_context import commodity as commodity
from test_commodity_context import dossier as dossier
from test_commodity_context import grounded as grounded
from test_commodity_context import selection as selection
from test_input_markets import registry_case as registry_case
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine import core_workspace
from engine.commodity_context import evaluate_registry
from engine.core_workspace import build, bundle, local_path
from engine.input_markets import install


def test_product_bundle_keeps_evidence_and_revision_boundaries(registry_case):
    values, registry, sources, output = registry_case
    install(registry, values[0], sources, output)
    card = evaluate_registry(values[0], values[1], values[2], output, store=values[-1])[
        "candidate_alerts"
    ][0]
    second = {
        **card,
        "product": "Second product",
        "scope": "Second scope",
        "usage_relation_id": "second",
    }
    rows = bundle("event", "SYNTHETIC", [card, second, card])
    assert len(rows) == 1 and len(rows[0]["products"]) == 2
    assert rows[0]["financial_magnitude"] == "UNKNOWN"
    assert rows[0]["products"][0]["usage_evidence"] == card["usage_evidence"]
    for key, value in [
        ("source_packet_sha256", "new-revision"),
        ("selected_market_id", "other-market"),
        ("measurement", {"signed_change_pct": "20"}),
    ]:
        assert len(bundle("event", "SYNTHETIC", [card, {**second, key: value}])) == 2
    assert bundle("other", "SYNTHETIC", [card])[0]["id"] != rows[0]["id"]


def test_workspace_live_refresh_and_synthetic_default(registry_case, monkeypatch):
    values, registry, sources, output = registry_case
    install(registry, values[0], sources, output)
    root = output.parent
    manifest = root / "workspace.json"
    (root / "observation.json").write_text(values[1].model_dump_json())
    (root / "selection.json").write_text(json.dumps(values[2]))
    event = {
        "id": "one",
        "mode": "SYNTHETIC",
        "observation": "observation.json",
        "selection": "selection.json",
        "articles": ".",
        "store": "store.sqlite",
    }
    manifest.write_text(json.dumps({"atlas": ".", "registry": output.name, "events": [event]}))
    monkeypatch.setattr(core_workspace, "read_snapshot", lambda p: values[0])
    monkeypatch.setattr(core_workspace, "Store", lambda p: values[-1])
    # Existing fixture resolver owns its isolated capture path.
    real_evaluate = evaluate_registry

    def evaluate(*args, **kwargs):
        kwargs.pop("article_root")
        return real_evaluate(*args, **kwargs)

    monkeypatch.setattr(core_workspace, "evaluate_registry", evaluate)
    assert build(manifest)["cards"] == []
    result = build(manifest, include_synthetic=True)
    assert len(result["cards"]) == 1 and len(result["paths"]) == 1
    store = values[-1]
    sid = values[2]["revision"]["id"]
    old = store.history("source", sid)[-1]
    state = {**old["payload"], "status": "WITHDRAWN"}
    store.append("source", sid, state, expected_head=old["sha256"])
    assert build(manifest, include_synthetic=True)["cards"] == []
    (output / "sources/test.html").write_text("tampered")
    with pytest.raises(ValueError):
        build(manifest)


def test_manifest_paths_and_duplicate_events(tmp_path):
    with pytest.raises(ValueError):
        local_path(tmp_path, "../outside")
    event = {
        "id": "same",
        "mode": "SYNTHETIC",
        "observation": "x",
        "selection": "x",
        "articles": "x",
        "store": "x",
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"atlas": ".", "registry": ".", "events": [event, copy.deepcopy(event)]})
    )
    with pytest.raises(ValueError, match="Duplicate"):
        build(manifest)


def test_core_auth_and_disabled_default(client, identities, monkeypatch):
    monkeypatch.delenv("CORE_WORKSPACE_MANIFEST", raising=False)
    assert client.get("/api/v0/news/core").status_code == 401
    response = client.get("/api/v0/news/core", headers=headers(identities[0]))
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/core").status_code == 200
    assert client.get("/assets/core.js").status_code == 200


def test_core_endpoint_refresh_and_failure_clear(client, identities, monkeypatch):
    monkeypatch.setenv("CORE_WORKSPACE_MANIFEST", "local-private-manifest")
    calls = []

    def current(manifest, *, include_synthetic, news_conn):
        assert news_conn is not None
        calls.append(include_synthetic)
        return {"cards": [], "delivery": "disabled", "synthetic_included": include_synthetic}

    monkeypatch.setattr(core_workspace, "build", current)
    for suffix in ("", "?include_synthetic=true"):
        response = client.get("/api/v0/news/core" + suffix, headers=headers(identities[0]))
        assert response.status_code == 200
    assert calls == [False, True]

    def corrupt(*args, **kwargs):
        raise ValueError("private filesystem details")

    monkeypatch.setattr(core_workspace, "build", corrupt)
    response = client.get("/api/v0/news/core", headers=headers(identities[0]))
    assert response.status_code == 503
    assert "private filesystem" not in response.text
