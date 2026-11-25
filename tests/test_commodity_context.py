"""Synthetic price/news/input inventory tests; no real prices or independent labels."""

import copy
import hashlib
import os
from datetime import UTC, datetime, timedelta

import pytest
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_structured_news import grounded as grounded
from test_structured_news import replace_article

from engine.commodity_context import (
    DEFAULT,
    InputBinding,
    Observation,
    evaluate,
    load_policy,
    price_change,
)
from engine.impact_atlas import snapshot
from engine.ingestion.contracts import digest
from engine.scope_review import Store


def observation(selection, quote, values, basis="PRICE_PAIR"):
    return Observation(
        id="synthetic-price",
        selection_sha256=digest(selection),
        commodity_id="copper",
        basis=basis,
        quote=quote,
        fields={
            k: {"start": quote.index(v), "end": quote.index(v) + len(v), "text": v}
            for k, v in values.items()
        },
        reviewed_at=datetime.now(UTC),
        reviewer_id="synthetic-extractor",
        reviewer_kind="AI_OPERATOR",
    )


@pytest.fixture
def commodity(grounded, tmp_path):
    root, profile, s, _ = grounded
    quote = "The example company uses Copper as an input for its processors."
    raw = (root / "source.html").read_bytes() + ("<p>" + quote + "</p>").encode()
    (root / "source.html").write_bytes(raw)
    profile["sources"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    profile["nodes"].append({"id": "copper", "kind": "input", "label": "Copper"})
    profile["relationships"].append(
        {
            "id": "usage",
            "type": "USES_INPUT",
            "from_id": "p",
            "to_id": "copper",
            "scope": "Synthetic processor input",
            "valid_from": "2024-01-01T00:00:00+00:00",
            "known_at": profile["available_at"],
            "status": "SOURCE_BACKED",
            "basis": "SOURCE_REPORTED",
            "evidence": [{"source_id": "s", "quote": quote}],
        }
    )
    profile["narratives"][0]["watched_nodes"] = ["p"]
    seal(root, profile)
    data = snapshot(os.environ["COMPANY_PROFILE_ROOT"])
    now = datetime.now(UTC)
    binding = InputBinding(
        id="synthetic-input",
        commodity_id="copper",
        name="Copper",
        atlas_sha256=digest(data),
        usage_relation_id="example/usage",
        source_id="example/s",
        quote=quote,
        reviewed_at=now,
        review_until=now + timedelta(days=1),
        reviewer_id="synthetic-data-review",
        reviewer_kind="AI_OPERATOR",
    )

    def build(current="112", previous="100", end_days=1, basis="PRICE_PAIR", direction="rose"):
        start = (now - timedelta(days=30)).date().isoformat()
        end = (now - timedelta(days=end_days)).date().isoformat()
        if basis == "PRICE_PAIR":
            text = f"Copper prices in USD per tonne moved from {previous} on {start} to {current} on {end}."
            fields = {
                "commodity": "Copper",
                "previous": previous,
                "current": current,
                "previous_currency": "USD",
                "current_currency": "USD",
                "previous_unit": "tonne",
                "current_unit": "tonne",
                "period_start": start,
                "period_end": end,
            }
        else:
            text = f"Copper prices {direction} {current}% from {start} to {end}."
            fields = {
                "commodity": "Copper",
                "change": current + "%",
                "direction": direction,
                "period_start": start,
                "period_end": end,
            }
        selected = replace_article(s, text)
        ob = observation(selected, text, fields, basis)
        store = Store(tmp_path / (digest(text) + ".sqlite"), create=True)
        store.append(
            "source",
            selected["revision"]["id"],
            {
                "packet_sha256": selected["packet_sha256"],
                "status": "CURRENT",
                "observed_at": datetime.now(UTC).isoformat(),
            },
        )
        return data, ob, selected, [binding], store

    return build


def run(values):
    data, ob, selected, bindings, store = values
    return evaluate(data, ob, selected, bindings, store=store)


@pytest.mark.parametrize(
    "current,count,band",
    [
        ("104.99", 0, "BELOW_OR_AT_THRESHOLD"),
        ("105", 0, "BELOW_OR_AT_THRESHOLD"),
        ("105.01", 1, "NOTICEABLE_PRICE_MOVE"),
        ("108", 1, "NOTICEABLE_PRICE_MOVE"),
        ("110", 1, "STRONG_PRICE_MOVE"),
        ("95", 0, "BELOW_OR_AT_THRESHOLD"),
        ("90", 1, "STRONG_PRICE_MOVE"),
    ],
)
def test_price_threshold_and_input_match_without_any_legal_reference(
    commodity, current, count, band
):
    values = commodity(current)
    assert values[0]["entity_references"] == []
    result = run(values)
    assert len(result["candidate_alerts"]) == count and result["price_move_band"] == band
    if count:
        card = result["candidate_alerts"][0]
        assert card["ticker"] == "TEST" and card["narrative_ids"] == ["example/n"]
        assert card["financial_magnitude"] == "UNKNOWN" and card["probability"] is None
        assert card["delivery"] == "disabled"
        assert card["conditional_cost_pressure"] == ("DOWN" if float(current) < 100 else "UP")


@pytest.mark.parametrize(
    "direction,expected", [("rose", "8"), ("fell", "-8"), ("tăng", "8"), ("giảm", "-8")]
)
def test_explicit_reported_percent_works_without_inventing_price_levels(
    commodity, direction, expected
):
    result = run(commodity("8", basis="REPORTED_CHANGE", direction=direction))
    assert result["measurement"]["signed_change_pct"] == expected
    assert "previous" not in result["measurement"]["source_fields"]
    assert len(result["candidate_alerts"]) == 1


@pytest.mark.parametrize(
    "fault", ["missing", "offset", "zero", "future", "negative", "forecast", "percentage_points"]
)
def test_unusable_price_data_is_held_not_filled(commodity, fault):
    if fault == "zero":
        values = commodity(previous="0")
    elif fault == "future":
        values = commodity(end_days=-1)
    elif fault == "negative":
        values = commodity(previous="-100")
    else:
        values = commodity()
    data, ob, s, bindings, store = values
    if fault == "missing":
        del ob.fields["period_start"]
    elif fault == "offset":
        ob.fields["current"].start += 1
    elif fault in {"forecast", "percentage_points"}:
        quote = ob.quote + (
            " This is a forecast." if fault == "forecast" else " In percentage points."
        )
        s = replace_article(s, quote)
        ob = ob.model_copy(
            update={"quote": quote, "selection_sha256": digest(s), "reviewed_at": datetime.now(UTC)}
        )
        old = store.history("source", s["revision"]["id"])[-1]
        store.append(
            "source",
            s["revision"]["id"],
            {**old["payload"], "packet_sha256": s["packet_sha256"]},
            expected_head=old["sha256"],
        )
    result = evaluate(data, ob, s, bindings, store=store)
    assert result["status"] == "INSUFFICIENT_EVIDENCE" and result["candidate_alerts"] == []


@pytest.mark.parametrize(
    "fault", ["commodity", "quote", "atlas", "expired", "relationship", "name"]
)
def test_wrong_input_or_stale_binding_never_creates_company_alert(commodity, fault):
    values = list(commodity())
    binding = values[3][0]
    changes = {
        "commodity": {"commodity_id": "steel"},
        "quote": {"quote": "Invented company usage"},
        "atlas": {"atlas_sha256": "0" * 64},
        "expired": {"review_until": datetime.now(UTC) - timedelta(days=1)},
        "relationship": {"usage_relation_id": "example/effect"},
        "name": {"name": "Steel"},
    }
    values[3] = [binding.model_copy(update=changes[fault])]
    assert run(values)["candidate_alerts"] == []


def test_old_period_and_withdrawal_do_not_alert(commodity):
    assert run(commodity(end_days=10))["candidate_alerts"] == []
    values = commodity()
    store = values[-1]
    sid = values[2]["revision"]["id"]
    old = store.history("source", sid)[-1]
    store.append(
        "source", sid, {**old["payload"], "status": "WITHDRAWN"}, expected_head=old["sha256"]
    )
    assert run(values)["candidate_alerts"] == []


def test_partial_numeric_token_not_accepted(commodity):
    values = commodity("112")
    ob = values[1]
    original = ob.fields["current"]
    ob.fields["current"] = original.model_copy(update={"start": original.start + 1, "text": "12"})
    with pytest.raises(ValueError):
        price_change(ob, datetime.now(UTC))


def test_truncated_decimal_cannot_change_threshold_decision(commodity):
    ob = commodity("105.01")[1]
    field = ob.fields["current"]
    ob.fields["current"] = field.model_copy(update={"text": "105", "end": field.start + 3})
    with pytest.raises(ValueError, match="Truncated"):
        price_change(ob, datetime.now(UTC))


def test_non_price_metric_not_promoted_to_price_alert(commodity):
    ob = commodity()[1]
    ob = ob.model_copy(update={"quote": ob.quote.replace("prices", "volume")})
    with pytest.raises(ValueError, match="price statement"):
        price_change(ob, datetime.now(UTC))


@pytest.mark.parametrize(
    "field,replacement", [("current_currency", "EUR"), ("current_unit", "pound")]
)
def test_incompatible_explicit_units_are_not_converted(commodity, field, replacement):
    ob = commodity()[1]
    quote = ob.quote + " Current quotation: " + replacement
    fields = {key: span.text for key, span in ob.fields.items()}
    fields[field] = replacement
    candidate = observation({}, quote, fields)
    with pytest.raises(ValueError, match="Same explicit"):
        price_change(candidate, datetime.now(UTC))


def test_relative_period_preserved_without_invented_dates():
    quote = "Copper prices rose 8% over the past week."
    ob = observation(
        {},
        quote,
        {
            "commodity": "Copper",
            "direction": "rose",
            "change": "8%",
            "period": "over the past week",
        },
        "REPORTED_CHANGE",
    )
    now = datetime.now(UTC)
    result = price_change(ob, now, now.isoformat())
    assert result["signed_change_pct"] == "8"
    assert result["period_start"] is None and result["period_end"] is None
    assert result["period_label"] == "over the past week"
    with pytest.raises(ValueError, match="publication timestamp"):
        price_change(ob, now)


def test_versioned_threshold_configuration(commodity, tmp_path):
    import json

    policy = load_policy(DEFAULT)
    policy.update(version=2, minimum_absolute_change_pct="8", strong_absolute_change_pct="12")
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    data, ob, selected, bindings, store = commodity("108")
    assert (
        evaluate(data, ob, selected, bindings, store=store, policy_path=path)["candidate_alerts"]
        == []
    )
    policy["minimum_absolute_change_pct"] = "NaN"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy(path)


def test_registry_binding_cannot_be_ignored_and_race_removes_alerts(commodity, monkeypatch):
    values = commodity()
    store = values[-1]
    sid = values[2]["revision"]["id"]
    old = store.history("source", sid)[-1]
    store.append(
        "source", sid, {**old["payload"], "registry_sha256": "0" * 64}, expected_head=old["sha256"]
    )
    assert run(values)["candidate_alerts"] == []
    fingerprints = iter(["before", "after"])
    monkeypatch.setattr(store, "fingerprint", lambda: next(fingerprints))
    assert run(values)["candidate_alerts"] == []


def test_one_market_event_routes_to_multiple_company_input_inventories(commodity):
    values = list(commodity())
    data = values[0]
    # Synthetic duplicated company graph, not independent issuer evidence.
    for key in ["profiles", "nodes", "relations", "narratives", "sources"]:
        originals = copy.deepcopy(data[key])
        import json

        data[key] += json.loads(
            json.dumps(originals)
            .replace("example/", "other/")
            .replace('"example"', '"other"')
            .replace('"TEST"', '"OTHER"')
        )
    b = values[3][0]
    values[3] = [
        b.model_copy(update={"atlas_sha256": digest(data)}),
        b.model_copy(
            update={
                "id": "other-input",
                "atlas_sha256": digest(data),
                "usage_relation_id": "other/usage",
                "source_id": "other/s",
            }
        ),
    ]
    assert {c["ticker"] for c in run(values)["candidate_alerts"]} == {"TEST", "OTHER"}
