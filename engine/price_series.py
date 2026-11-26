"""Append-only observation revisions and comparable-period price movements."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from engine.ingestion.contracts import digest
from engine.price_board import INSTRUMENT, parse


def append(root, raw, *, at=None, status="CURRENT", source_url=None):
    at = at or datetime.now(UTC)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    record = parse(raw, at, allow_history=True)
    if status not in {"CURRENT", "WITHDRAWN"}:
        raise ValueError("Unsupported lifecycle status")
    if source_url and source_url != record["source_url"]:
        raise ValueError("Provider adapter URL mismatch")
    sha = hashlib.sha256(raw).hexdigest()
    capture = root / (sha + ".html")
    if capture.exists() and capture.read_bytes() != raw:
        raise ValueError("Capture changed")
    if not capture.exists():
        with capture.open("xb") as stream:
            stream.write(raw)
    # Retrieval timing does not change the economic observation or create churn.
    economic = {k: v for k, v in record.items() if k != "retrieved_at"}
    record_hash = digest([economic, status])
    with sqlite3.connect(root / "series.sqlite") as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS revisions (seq INTEGER PRIMARY KEY, observed_at TEXT, record_hash TEXT, payload TEXT, capture TEXT, status TEXT, known_at TEXT)"
        )
        conn.execute("BEGIN IMMEDIATE")
        last = conn.execute(
            "SELECT record_hash FROM revisions WHERE observed_at=? ORDER BY seq DESC LIMIT 1",
            (record["observed_at"],),
        ).fetchone()
        if last and last[0] == record_hash:
            return {"changed": False, "record_hash": record_hash}
        conn.execute(
            "INSERT INTO revisions(observed_at,record_hash,payload,capture,status,known_at) VALUES(?,?,?,?,?,?)",
            (record["observed_at"], record_hash, json.dumps(economic), sha, status, at.isoformat()),
        )
    return {"changed": True, "record_hash": record_hash}


def observations(root, *, at=None):
    at = at or datetime.now(UTC)
    root = Path(root)
    if not (root / "series.sqlite").is_file():
        return []
    with sqlite3.connect(
        (root / "series.sqlite").resolve().as_uri() + "?mode=ro", uri=True
    ) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM revisions ORDER BY seq").fetchall()
    current = {}
    for row in rows:
        if datetime.fromisoformat(row["known_at"]) > at:
            continue
        raw = (root / (row["capture"] + ".html")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["capture"]:
            raise ValueError("Series capture changed")
        record = json.loads(row["payload"])
        parsed = parse(raw, datetime.fromisoformat(row["known_at"]), allow_history=True)
        economic = {k: v for k, v in parsed.items() if k != "retrieved_at"}
        if record != economic or digest([record, row["status"]]) != row["record_hash"]:
            raise ValueError("Series observation changed")
        current[row["observed_at"]] = {
            **record,
            "status": row["status"],
            "record_hash": row["record_hash"],
            "capture_sha256": row["capture"],
        }
    return sorted(current.values(), key=lambda r: r["observed_at"])


def compare(root, *, at=None, days=1, metadata=None):
    at = at or datetime.now(UTC)
    if days not in {1, 7, 30}:
        raise ValueError("Supported windows: 1,7,30 days")
    rows = observations(root, at=at)
    result = {
        "window_days": days,
        "status": "INSUFFICIENT_HISTORY",
        "delivery": "disabled",
        "financial_magnitude": "UNKNOWN",
    }
    if len(rows) < 2:
        return result
    end = rows[-1]
    end_time = datetime.fromisoformat(end["observed_at"])
    if end["status"] != "CURRENT" or not timedelta(0) <= at - end_time <= timedelta(days=7):
        return {**result, "status": "LATEST_WITHDRAWN_OR_STALE"}
    target = end_time - timedelta(days=days)
    candidates = [
        r
        for r in rows[:-1]
        if target - timedelta(days=3) <= datetime.fromisoformat(r["observed_at"]) <= target
    ]
    if not candidates:
        return result
    start = candidates[-1]
    if start["status"] != "CURRENT":
        return {**result, "status": "BASELINE_WITHDRAWN"}
    if any(start[k] != end[k] for k in ["provider", "instrument", "basis", "source_url"]):
        raise ValueError("Incompatible price endpoints")
    change = (
        Decimal(end["session_average"].replace(",", ""))
        / Decimal(start["session_average"].replace(",", ""))
        - 1
    ) * 100
    result.update(
        start=start,
        end=end,
        signed_change_pct=str(change),
        period_start=start["observed_at"],
        period_end=end["observed_at"],
        comparison_basis="SAME_PUBLISHER_INSTRUMENT_QUOTED_VALUES",
        currency=None,
        unit=None,
        status="QUOTED_VALUE_COMPARISON_UNITS_UNVERIFIED",
    )
    if metadata is None:
        return result
    # Keep direct declarations separate from user-authorized one-step cross-source inference.
    m = json.loads(Path(metadata).read_text(encoding="utf-8"))
    basis_kind = m.get("basis_kind", "SOURCE_DECLARED")
    if basis_kind not in {"SOURCE_DECLARED", "CROSS_SOURCE_INFERRED"}:
        raise ValueError("Unsupported metadata basis")
    if basis_kind == "CROSS_SOURCE_INFERRED" and (
        m.get("inference_steps") != 1 or not m.get("notes")
    ):
        raise ValueError("Only explicit one-step inference supported")
    raw = (Path(metadata).parent / m["file"]).resolve()
    if not raw.is_relative_to(Path(metadata).parent.resolve()):
        raise ValueError("Metadata path outside directory")
    from engine.input_markets import source_text

    body = raw.read_bytes()
    text = source_text(body)
    if (
        hashlib.sha256(body).hexdigest() != m["sha256"]
        or m["quote"] not in text
        or m["instrument"] != INSTRUMENT
        or m["basis"] != "SPOT"
        or any(m[k] not in m["quote"] for k in ["instrument", "currency", "unit"])
        or not datetime.fromisoformat(m["known_at"])
        <= at
        < datetime.fromisoformat(m["review_until"])
    ):
        raise ValueError("Unverified price metadata")
    result.update(
        currency=m["currency"],
        unit=m["unit"],
        metadata_sha256=digest(m),
        metadata_basis=basis_kind,
        metadata_notes=m.get("notes"),
        metadata_source_url=m.get("source_url"),
        unit_verified=basis_kind == "SOURCE_DECLARED",
        status="ABOVE_THRESHOLD" if abs(change) > 5 else "BELOW_OR_AT_THRESHOLD",
        price_move_band="STRONG"
        if abs(change) >= 10
        else "WATCH"
        if abs(change) > 5
        else "BELOW_OR_AT_THRESHOLD",
    )
    return result


def cards(comparison, registry, data):
    """Only unit-verified threshold crossings become scoped input-price candidates."""
    from engine.input_markets import route

    if comparison["status"] != "ABOVE_THRESHOLD":
        return []
    market = next(
        (
            m
            for m in registry.markets
            if m.commodity_id == "dram-ddr5"
            and m.instrument == comparison["end"]["instrument"]
            and m.basis == comparison["end"]["basis"]
        ),
        None,
    )
    if market is None:
        return []
    if (market.currency and market.currency != comparison["currency"]) or (
        market.unit and market.unit != comparison["unit"]
    ):
        return []
    profiles = {p["id"]: p for p in data["profiles"]}
    result = []
    for row in route(registry, market.commodity_id, market_id=market.id):
        e = row["exposure"]
        profile = profiles[e["profile_id"]]
        result.append(
            {
                "kind": "COMMODITY_PRICE_ALERT_CANDIDATE",
                "ticker": profile["ticker"],
                "company_id": profile["company_id"],
                "commodity_id": market.commodity_id,
                "commodity": comparison["end"]["instrument"],
                "product": e["product_label"],
                "scope": e["scope"],
                "usage_relation_id": "input-registry/" + e["id"],
                "usage_evidence": e["evidence"],
                "usage_source_urls": [
                    str(s.url)
                    for s in registry.sources
                    if s.id in {v["source_id"] for v in e["evidence"]}
                ],
                "narrative_ids": [
                    n["id"]
                    for n in data["narratives"]
                    if n["profile_id"] == e["profile_id"]
                    and e["product_node_id"] in n["watched_nodes"]
                ],
                "price_markets": row["price_markets"],
                "selected_market_id": market.id,
                "measurement": comparison,
                "price_move_band": comparison["price_move_band"],
                "source_quote": comparison["start"]["quote"] + " → " + comparison["end"]["quote"],
                "source_url": comparison["end"]["source_url"],
                "source_packet_sha256": digest(comparison),
                "conditional_cost_pressure": "UP"
                if Decimal(comparison["signed_change_pct"]) > 0
                else "DOWN",
                "financial_magnitude": "UNKNOWN",
                "horizon": "UNKNOWN",
                "purchase_price_verified": False,
                "metadata_basis": comparison.get("metadata_basis"),
                "unit_verified": comparison.get("unit_verified", False),
                "delivery": "disabled",
            }
        )
    return result
