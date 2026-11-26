import hashlib
import json
from datetime import UTC, datetime

import pytest
from test_commodity_context import commodity as commodity
from test_commodity_context import dossier as dossier
from test_commodity_context import grounded as grounded
from test_commodity_context import selection as selection
from test_input_markets import registry_case as registry_case
from test_price_board import RAW

from engine.price_series import append, compare, observations

AT = datetime(2026, 11, 26, 12, tzinfo=UTC)


def test_series_comparison_correction_withdrawal_and_integrity(tmp_path):
    old = RAW.replace(b"2026-11-26", b"2026-11-25").replace(b"60.767", b"50.000")
    append(tmp_path, old, at=AT)
    append(tmp_path, RAW, at=AT)
    assert not append(tmp_path, RAW, at=AT)["changed"]
    r = compare(tmp_path, at=AT)
    assert r["status"] == "QUOTED_VALUE_COMPARISON_UNITS_UNVERIFIED"
    assert r["signed_change_pct"] == "21.53400"
    assert compare(tmp_path, at=AT, days=7)["status"] == "INSUFFICIENT_HISTORY"
    metadata = tmp_path / "metadata.json"
    text = "DDR5 16Gb (2Gx8) 4800/5600 SPOT quoted in USD per chip."
    raw = text.encode()
    (tmp_path / "units.html").write_bytes(raw)
    metadata.write_text(
        json.dumps(
            {
                "file": "units.html",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "quote": text,
                "instrument": "DDR5 16Gb (2Gx8) 4800/5600",
                "basis": "SPOT",
                "currency": "USD",
                "unit": "chip",
                "known_at": "2026-11-25T00:00:00+00:00",
                "review_until": "2026-12-25T00:00:00+00:00",
            }
        )
    )
    assert compare(tmp_path, at=AT, metadata=metadata)["status"] == "ABOVE_THRESHOLD"
    inferred = json.loads(metadata.read_text())
    inferred.update(
        basis_kind="CROSS_SOURCE_INFERRED",
        inference_steps=1,
        notes="Same instrument only; secondary unit convention, not independently verified price.",
    )
    metadata.write_text(json.dumps(inferred))
    result = compare(tmp_path, at=AT, metadata=metadata)
    assert result["metadata_basis"] == "CROSS_SOURCE_INFERRED" and not result["unit_verified"]
    inferred["inference_steps"] = 2
    metadata.write_text(json.dumps(inferred))
    with pytest.raises(ValueError, match="one-step"):
        compare(tmp_path, at=AT, metadata=metadata)
    inferred["inference_steps"] = 1
    metadata.write_text(json.dumps(inferred))
    corrected = RAW.replace(b"60.767", b"51.000")
    append(tmp_path, corrected, at=AT)
    assert len(observations(tmp_path, at=AT)) == 2
    assert compare(tmp_path, at=AT, metadata=metadata)["status"] == "BELOW_OR_AT_THRESHOLD"
    append(tmp_path, corrected, at=AT, status="WITHDRAWN")
    assert compare(tmp_path, at=AT)["status"] == "LATEST_WITHDRAWN_OR_STALE"
    (tmp_path / (hashlib.sha256(old).hexdigest() + ".html")).write_bytes(b"changed")
    with pytest.raises(ValueError, match="capture"):
        observations(tmp_path, at=AT)


def test_board_legacy_timestamp_stays_same_instrument():
    from engine.price_board import parse

    raw = RAW.replace(b"Last Update 2026-11-26", b"Last Update: Nov.26 2026")
    assert parse(raw, AT)["source_url"] == "https://www.dramexchange.com/"


def test_historical_ingestion_does_not_make_stale_latest_current(tmp_path):
    old = RAW.replace(b"2026-11-26", b"2026-10-26")
    append(tmp_path, old, at=AT)
    append(tmp_path, RAW, at=AT)
    assert compare(tmp_path, at=AT, days=30)["period_start"].startswith("2026-10-26")


def test_threshold_card_routes_only_the_exact_registered_input(registry_case):
    from engine.input_markets import Registry, validate
    from engine.price_board import INSTRUMENT
    from engine.price_series import cards

    values, original, sources, _ = registry_case
    r = original.model_dump(mode="json")
    text = f"Example product uses DDR5. {INSTRUMENT} Spot quote in USD per die."
    raw = text.encode()
    (sources / "test.html").write_bytes(raw)
    r["sources"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    e = [{"source_id": "s", "quote": "Example product uses DDR5."}]
    r["commodities"][0].update(id="dram-ddr5", label="DDR5", aliases=["DDR5"], evidence=e)
    r["exposures"][0].update(commodity_id="dram-ddr5", input_label="DDR5", evidence=e)
    r["markets"][0].update(
        commodity_id="dram-ddr5",
        instrument=INSTRUMENT,
        unit="die",
        evidence=[{"source_id": "s", "quote": f"{INSTRUMENT} Spot quote in USD per die."}],
    )
    registry = validate(Registry.model_validate(r), values[0], sources)
    comparison = {
        "status": "ABOVE_THRESHOLD",
        "end": {
            "instrument": INSTRUMENT,
            "basis": "SPOT",
            "quote": "synthetic end",
            "source_url": "https://example.com",
        },
        "start": {"quote": "synthetic start"},
        "currency": "USD",
        "unit": "die",
        "price_move_band": "STRONG",
        "signed_change_pct": "12",
        "metadata_basis": "CROSS_SOURCE_INFERRED",
        "unit_verified": False,
    }
    result = cards(comparison, registry, values[0])
    assert len(result) == 1 and result[0]["ticker"] == "TEST"
    assert result[0]["financial_magnitude"] == "UNKNOWN" and not result[0]["unit_verified"]
    comparison["status"] = "BELOW_OR_AT_THRESHOLD"
    assert cards(comparison, registry, values[0]) == []
