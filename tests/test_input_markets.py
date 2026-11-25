"""Synthetic core schema/routing behavior; no market accuracy claims."""

import copy
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from test_commodity_context import commodity as commodity
from test_commodity_context import dossier as dossier
from test_commodity_context import grounded as grounded
from test_commodity_context import selection as selection
from test_structured_news import replace_article

from engine.commodity_context import evaluate_registry
from engine.core_profile import project
from engine.ingestion.contracts import digest
from engine.input_markets import Registry, install, read, route, source_text, validate


@pytest.fixture
def registry_case(commodity, tmp_path):
    values = commodity()
    root = tmp_path / "sources"
    root.mkdir()
    raw = b"<p>Example product uses Copper.</p><p>Copper Spot quote in USD per tonne.</p>"
    (root / "test.html").write_bytes(raw)
    now = datetime.now(UTC)
    evidence = [{"source_id": "s", "quote": "Example product uses Copper."}]
    r = Registry.model_validate(
        {
            "version": 1,
            "atlas_sha256": digest(values[0]),
            "known_at": now,
            "review_until": now + timedelta(days=30),
            "reviewer_id": "synthetic",
            "reviewer_kind": "AI_OPERATOR",
            "sources": [
                {
                    "id": "s",
                    "url": "https://example.com/spec",
                    "file": "test.html",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "retrieved_at": now,
                    "published_at": None,
                    "status": "CURRENT",
                }
            ],
            "commodities": [
                {"id": "copper", "label": "Copper", "aliases": ["Copper"], "evidence": evidence}
            ],
            "exposures": [
                {
                    "id": "copper-use",
                    "profile_id": "example",
                    "product_node_id": "example/p",
                    "product_label": "Example product",
                    "commodity_id": "copper",
                    "input_label": "Copper",
                    "scope": "Synthetic product only",
                    "evidence": evidence,
                }
            ],
            "markets": [
                {
                    "id": "spot",
                    "commodity_id": "copper",
                    "provider": "Example",
                    "instrument": "Copper",
                    "basis": "SPOT",
                    "currency": "USD",
                    "unit": "tonne",
                    "geography": None,
                    "evidence": [
                        {"source_id": "s", "quote": "Copper Spot quote in USD per tonne."}
                    ],
                }
            ],
            "market_links": [
                {
                    "id": "proxy",
                    "exposure_id": "copper-use",
                    "market_id": "spot",
                    "applicability": "BENCHMARK_PROXY_ONLY",
                    "limitations": "Benchmark only; the company purchase price and product grade remain unverified.",
                }
            ],
        }
    )
    return values, r, root, tmp_path / "registry"


def test_roundtrip_core_profile_and_registry_routing(registry_case):
    values, r, root, out = registry_case
    assert install(r, values[0], root, out)["exposures"] == 1
    loaded = read(out, values[0])
    rows = route(loaded, "copper", market_id="spot")
    assert len(rows) == 1 and not rows[0]["purchase_price_verified"]
    assert rows[0]["price_markets"][0]["applicability"] == "BENCHMARK_PROXY_ONLY"
    core = project(values[0], loaded)
    assert len(core["profiles"][0]["groups"]) == 7
    assert core["profiles"][0]["input_exposure_ids"] == ["copper-use"]
    with pytest.raises(FileExistsError):
        install(r, values[0], root, out)


def test_source_to_card_uses_shared_registry_without_legal_anchor(registry_case):
    values, r, root, out = registry_case
    install(r, values[0], root, out)
    result = evaluate_registry(values[0], values[1], values[2], out, store=values[-1])
    assert len(result["candidate_alerts"]) == 1
    card = result["candidate_alerts"][0]
    assert card["commodity_id"] == "copper" and card["financial_magnitude"] == "UNKNOWN"
    assert card["selected_market_id"] is None and not card["purchase_price_verified"]
    held = evaluate_registry(
        values[0], values[1], values[2], out, store=values[-1], market_id="spot"
    )
    assert (
        not held["candidate_alerts"]
        and held["registry_hold"] == "MARKET_NOT_EXPLICIT_OR_INCOMPATIBLE"
    )


@pytest.mark.parametrize(
    "case",
    [
        "bad_quote",
        "wrong_product",
        "wrong_alias",
        "ambiguous_alias",
        "wrong_market_unit",
        "cross_commodity",
        "future_capture",
        "path_escape",
    ],
)
def test_unfounded_or_mismatched_records_rejected(registry_case, case):
    values, r, root, _ = registry_case
    raw = r.model_dump(mode="json")
    if case == "bad_quote":
        raw["exposures"][0]["evidence"][0]["quote"] = "Invented fact"
    if case == "wrong_product":
        raw["exposures"][0]["product_node_id"] = "other/p"
    if case == "wrong_alias":
        raw["exposures"][0]["input_label"] = "Aluminium"
    if case == "ambiguous_alias":
        raw["commodities"][0]["aliases"].append("copper")
    if case == "wrong_market_unit":
        raw["markets"][0]["unit"] = "barrel"
    if case == "cross_commodity":
        raw["markets"][0]["commodity_id"] = "hbm3"
    if case == "future_capture":
        raw["sources"][0]["retrieved_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    if case == "path_escape":
        raw["sources"][0]["file"] = "../test.html"
    with pytest.raises(ValueError):
        validate(raw, values[0], root)


def test_withdrawal_alias_precision_and_expiry(registry_case):
    values, r, root, _ = registry_case
    validated = validate(r, values[0], root)
    assert not route(validated, "Copper")  # Canonical ID only; no fuzzy inference.
    assert not route(validated, "copper", market_id="hbm-spot")
    assert not route(validated, "copper", at=r.review_until)
    raw = r.model_dump(mode="json")
    raw["sources"][0]["status"] = "WITHDRAWN"
    assert not route(validate(raw, values[0], root), "copper")


def test_immutable_source_or_atlas_change_invalidates_registry(registry_case):
    values, r, root, out = registry_case
    install(r, values[0], root, out)
    changed = copy.deepcopy(values[0])
    changed["nodes"][0]["label"] = "Changed"
    with pytest.raises(ValueError, match="atlas/time"):
        read(out, changed)
    (out / "sources/test.html").write_bytes(b"changed")
    with pytest.raises(ValueError, match="artifact changed"):
        read(out, values[0])


def test_html_table_text_preserves_rows_and_ignores_script():
    assert (
        source_text(b"<table><tr><td>H100</td><td>HBM3</td></tr></table><script>fake</script>")
        == "H100 HBM3"
    )


@pytest.mark.parametrize("price,count", [("104", 0), ("105", 0), ("105.01", 1), ("90", 1)])
def test_registry_retains_price_move_thresholds(registry_case, commodity, price, count):
    original, r, root, out = registry_case
    install(r, original[0], root, out)
    values = commodity(price)
    result = evaluate_registry(values[0], values[1], values[2], out, store=values[-1])
    assert len(result["candidate_alerts"]) == count


def test_explicit_spot_market_stays_proxy_and_withdrawal_removes_card(registry_case):
    values, r, root, out = registry_case
    install(r, values[0], root, out)
    data, ob, selected, _, store = values
    quote = ob.quote + " Copper Spot market."
    selected = replace_article(selected, quote)
    ob = ob.model_copy(
        update={
            "quote": quote,
            "selection_sha256": digest(selected),
            "reviewed_at": datetime.now(UTC),
        }
    )
    sid = selected["revision"]["id"]
    old = store.history("source", sid)[-1]
    state = {
        "packet_sha256": selected["packet_sha256"],
        "status": "CURRENT",
        "observed_at": datetime.now(UTC).isoformat(),
    }
    store.append("source", sid, state, expected_head=old["sha256"])
    result = evaluate_registry(data, ob, selected, out, store=store, market_id="spot")
    assert len(result["candidate_alerts"]) == 1
    assert (
        result["candidate_alerts"][0]["benchmark_grade_geography_applicability"]
        == "BENCHMARK_PROXY_ONLY"
    )
    old = store.history("source", sid)[-1]
    store.append("source", sid, {**state, "status": "WITHDRAWN"}, expected_head=old["sha256"])
    assert not evaluate_registry(data, ob, selected, out, store=store, market_id="spot")[
        "candidate_alerts"
    ]
