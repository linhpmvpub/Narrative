"""Bounded public DDR5 spot-board capture. Unknown units never become price alerts."""

import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from engine.input_markets import source_text

URL = "https://www.trendforce.com/price/dram/dram_spot"
INSTRUMENT = "DDR5 16Gb (2Gx8) 4800/5600"


def parse(raw, at, *, allow_history=False):
    text = source_text(raw)
    if "Last Update" not in text or "DRAM Spot Price" not in text:
        raise ValueError("Missing spot board")
    legacy = "Last Update:" in text
    section = (
        text.split("Last Update:", 1)[1].lstrip() if legacy else text.split("Last Update ", 1)[1]
    )
    if not all(label in section for label in ("Daily High", "Daily Low", "Session Average")):
        raise ValueError("Unknown price columns")
    stamp = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(GMT\+8\)", section)
    if legacy:
        old = re.match(r"([A-Za-z]{3}\.\d{1,2} \d{4} \d{2}:\d{2}) \(GMT\+8\)", section)
        stamp_text = (
            datetime.strptime(old[1], "%b.%d %Y %H:%M").strftime("%Y-%m-%d %H:%M") if old else None
        )
    else:
        stamp_text = stamp[1] if stamp else None
    if stamp_text is None:
        raise ValueError("Spot-board timestamp absent")
    observed = datetime.strptime(stamp_text, "%Y-%m-%d %H:%M").replace(
        tzinfo=timezone(timedelta(hours=8))
    )
    if observed > at or (not allow_history and at - observed > timedelta(days=7)):
        raise ValueError("Future or stale spot board")
    # Exact instrument and five named price columns; never read module/contract rows.
    row = re.search(
        re.escape(INSTRUMENT) + r"\s+((?:\d[\d,]*\.\d+\s+){4}\d[\d,]*\.\d+)",
        section.split("DRAM Contract Price", 1)[0],
    )
    if row is None:
        raise ValueError("Exact DDR5 chip row unavailable")
    values = row[1].split()
    if any(Decimal(v.replace(",", "")) <= 0 for v in values):
        raise ValueError("Nonpositive price")
    return {
        "provider": "TrendForce",
        "instrument": INSTRUMENT,
        "basis": "SPOT",
        "observed_at": observed.isoformat(),
        "retrieved_at": at.isoformat(),
        "session_average": values[4],
        "quote": row[0],
        "source_url": "https://www.dramexchange.com/" if legacy else URL,
        "currency": None,
        "unit": None,
        "comparison_period": None,
        "status": "OBSERVATION_ONLY_UNITS_AND_COMPARISON_REQUIRED",
        "delivery": "disabled",
    }


def ingest(raw, root, at=None):
    at = at or datetime.now(UTC)
    record = parse(raw, at)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(raw).hexdigest()
    capture = root / (sha + ".html")
    if capture.exists():
        if capture.read_bytes() != raw:
            raise ValueError("Capture changed")
    else:
        with capture.open("xb") as stream:
            stream.write(raw)
    with sqlite3.connect(root / "observations.sqlite") as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS observations (instrument TEXT, observed_at TEXT, capture_sha256 TEXT, payload TEXT, PRIMARY KEY(instrument,observed_at,capture_sha256))"
        )
        conn.execute(
            "INSERT OR IGNORE INTO observations VALUES (?,?,?,?)",
            (INSTRUMENT, record["observed_at"], sha, json.dumps(record)),
        )
    return {**record, "capture_sha256": sha}
