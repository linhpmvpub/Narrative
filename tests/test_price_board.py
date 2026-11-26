import sqlite3
from datetime import UTC, datetime

import pytest

from engine.price_board import ingest, parse

RAW = b"<p>DRAM Spot Price Last Update 2026-11-26 18:10 (GMT+8) Item Daily High Daily Low Session High Session Low Session Average Session Change DDR5 16Gb (2Gx8) 4800/5600 71.45 45.60 71.45 45.60 60.767 0.00 % DRAM Contract Price</p>"
AT = datetime(2026, 11, 26, 12, tzinfo=UTC)


def test_board_keeps_unknown_units_and_idempotent_capture(tmp_path):
    first = ingest(RAW, tmp_path, AT)
    ingest(RAW, tmp_path, AT)
    ingest(RAW.replace(b"60.767", b"61.000"), tmp_path, AT)
    assert first["currency"] is None and first["comparison_period"] is None
    assert first["session_average"] == "60.767"
    with sqlite3.connect(tmp_path / "observations.sqlite") as conn:
        assert conn.execute("SELECT count(*) FROM observations").fetchone()[0] == 2


@pytest.mark.parametrize(
    "bad",
    [
        RAW.replace(b"DDR5", b"DDR4"),
        RAW.replace(b"2026-11-26", b"2026-11-27"),
        RAW.replace(b"2026-11-26", b"2026-10-26"),
    ],
)
def test_board_rejects_wrong_instrument_future_stale(bad):
    with pytest.raises(ValueError):
        parse(bad, AT)
