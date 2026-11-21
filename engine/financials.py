"""Deterministic SEC XBRL comparisons; consolidated actuals, never stock forecasts."""

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select

from engine.adapters.http_sources import SECSourceAdapter, SourceClient
from engine.development_feed import KIND, events, require_enabled, versions
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v7 import source_cursors
from engine.models.schema_v8 import financial_snapshots as snapshots

METRICS = {
    "REVENUE": (
        "Doanh thu hợp nhất",
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    ),
    "NET_INCOME": ("Lợi nhuận ròng hợp nhất", ("NetIncomeLoss",)),
    "OPERATING_INCOME": ("Lợi nhuận hoạt động hợp nhất", ("OperatingIncomeLoss",)),
    "GROSS_PROFIT": ("Lợi nhuận gộp hợp nhất", ("GrossProfit",)),
}
BASE_KEYS = ("ticker", "cik", "accession", "filing_date", "form", "url")


def source_identity(claim):
    return digest({k: claim[k] for k in BASE_KEYS})


def known_filings(conn, ticker, cutoff):
    result = {}
    for row in conn.execute(
        select(versions)
        .join(events)
        .where(
            events.c.event_type == KIND,
            events.c.issuer_entity_id == "CO_" + ticker,
            versions.c.available_at <= cutoff,
        )
        .order_by(versions.c.version_number)
    ).mappings():
        claim = row["normalized_claim"]
        result[claim["accession"]] = claim
    return result


def duration_kind(days):
    for low, high, name in (
        (80, 100, "quarter"),
        (170, 195, "year_to_date_6m"),
        (260, 290, "year_to_date_9m"),
        (350, 380, "annual"),
    ):
        if low <= days <= high:
            return name
    return None


def extract(payload, ticker, claims):
    """Both operands must have the same accession, concept, unit and duration basis."""
    facts = payload.get("facts", {}).get("us-gaap", {})
    output = []
    for accession, claim in claims.items():
        if claim["form"] not in {"10-K", "10-Q", "10-K/A", "10-Q/A"}:
            continue
        for metric, (label, tags) in METRICS.items():
            alternatives = []
            for priority, tag in enumerate(tags):
                values: dict = {}
                for index, fact in enumerate(facts.get(tag, {}).get("units", {}).get("USD", [])):
                    if (
                        fact.get("accn") != accession
                        or fact.get("form") != claim["form"]
                        or fact.get("filed") != claim["filing_date"]
                    ):
                        continue
                    try:
                        start, end = (
                            date.fromisoformat(fact["start"]),
                            date.fromisoformat(fact["end"]),
                        )
                        val = Decimal(str(fact["val"]))
                        kind = duration_kind((end - start).days + 1)
                        if (
                            not val.is_finite()
                            or isinstance(fact["val"], bool)
                            or not kind
                            or end > date.fromisoformat(claim["filing_date"])
                        ):
                            continue
                        if ticker == "SNDK" and start < date(2025, 2, 21):
                            continue
                    except (KeyError, ValueError, TypeError, InvalidOperation):
                        continue
                    values.setdefault((start, end), []).append((val, index, kind))
                # Conflicting duplicate facts make the concept ambiguous, not a license to choose.
                if any(len({v[0] for v in vals}) != 1 for vals in values.values()):
                    continue
                rows = [
                    (s, e, vals[0][0], vals[0][1], vals[0][2]) for (s, e), vals in values.items()
                ]
                if not rows:
                    continue
                latest_end = max(r[1] for r in rows)
                for current in rows:
                    if current[1] != latest_end:
                        continue
                    priors = [
                        p
                        for p in rows
                        if p[4] == current[4]
                        and 350 <= (current[0] - p[0]).days <= 380
                        and 350 <= (current[1] - p[1]).days <= 380
                        and abs((current[1] - current[0]).days - (p[1] - p[0]).days) <= 7
                    ]
                    if len(priors) != 1:
                        continue
                    prior = priors[0]
                    delta = current[2] - prior[2]
                    percent = (
                        (delta / prior[2] * 100).quantize(Decimal("0.01")) if prior[2] > 0 else None
                    )

                    def operand(r, concept=tag):
                        return {
                            "start": r[0].isoformat(),
                            "end": r[1].isoformat(),
                            "value": str(r[2]),
                            "json_pointer": f"/facts/us-gaap/{concept}/units/USD/{r[3]}",
                        }

                    comparison = {
                        "ticker": ticker,
                        "accession": accession,
                        "metric": metric,
                        "label": label,
                        "concept": "us-gaap:" + tag,
                        "scope": "consolidated_entity",
                        "unit": "USD",
                        "period_kind": current[4],
                        "comparison": "year_over_year_same_filing",
                        "current": operand(current),
                        "prior": operand(prior),
                        "delta": str(delta),
                        "percent_change": str(percent) if percent is not None else None,
                        "percent_unavailable_reason": None
                        if percent is not None
                        else "nonpositive_prior",
                        "reported_direction": "INCREASE"
                        if delta > 0
                        else "DECREASE"
                        if delta < 0
                        else "UNCHANGED",
                        "source_identity": source_identity(claim),
                        "filing_url": claim["url"],
                        "filing_date": claim["filing_date"],
                        "stock_price_impact": "UNKNOWN",
                        "causal_attribution": "NOT_ESTABLISHED",
                        "materiality": "UNKNOWN",
                        "narrative_stance": "INSUFFICIENT_EVIDENCE",
                        "method": "SEC XBRL reported actuals; no manual verification asserted",
                    }
                    alternatives.append(
                        ((current[1], -(current[1] - current[0]).days, -priority), comparison)
                    )
            if alternatives:
                output.append(max(alternatives, key=lambda r: r[0])[1])
    return sorted(output, key=lambda r: (r["accession"], r["metric"]))


def ingest(engine, ticker, cik, capture):
    require_enabled()
    now = datetime.now(UTC)
    expected = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    if capture.url != expected or capture.retrieved_at.tzinfo is None or capture.retrieved_at > now:
        raise ValueError("Invalid companyfacts capture URL/time")
    if hashlib.sha256(capture.text.encode()).hexdigest() != capture.content_sha256:
        raise ValueError("Capture hash mismatch")
    payload = json.loads(capture.text)
    if int(payload.get("cik", -1)) != int(cik) or not isinstance(payload.get("facts"), dict):
        raise ValueError("Issuer/facts mismatch")
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        if conn.scalar(select(database_mode.c.mode).with_for_update()) != "production":
            raise ValueError("Non-synthetic source store required")
        identity = conn.scalar(
            select(source_cursors.c.cik).where(source_cursors.c.ticker == ticker)
        )
        if identity != cik:
            raise ValueError("Collect verified issuer submissions before financial facts")
        previous = (
            conn.execute(
                select(snapshots)
                .where(snapshots.c.ticker == ticker)
                .order_by(snapshots.c.version.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if previous and capture.retrieved_at < utc(previous["captured_at"]):
            raise ValueError("Stale financial capture")
        claims = known_filings(conn, ticker, now)
        comparisons = extract(payload, ticker, claims)
        data = {"comparisons": comparisons, "method_version": "sec-comparisons-v1"}
        if (
            previous
            and previous["capture_sha256"] == capture.content_sha256
            and previous["payload"] == data
        ):
            return {"status": "duplicate", "id": previous["id"], "comparisons": len(comparisons)}
        if previous and capture.retrieved_at <= utc(previous["captured_at"]):
            raise ValueError("Conflicting financial snapshot at same capture time")
        sid = digest([ticker, capture.content_sha256, capture.retrieved_at.isoformat(), data])
        conn.execute(
            snapshots.insert().values(
                id=sid,
                ticker=ticker,
                cik=cik,
                version=previous["version"] + 1 if previous else 1,
                capture_sha256=capture.content_sha256,
                source_url=capture.url,
                captured_at=capture.retrieved_at,
                available_at=now,
                payload=data,
            )
        )
        return {"status": "created", "id": sid, "comparisons": len(comparisons)}


def assessments(conn, ticker, cutoff, *, accession=None):
    from engine.settings import Settings

    if not Settings.from_env().dev_informational_feed:
        return []
    snapshot = (
        conn.execute(
            select(snapshots)
            .where(snapshots.c.ticker == ticker, snapshots.c.available_at <= cutoff)
            .order_by(snapshots.c.version.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not snapshot:
        return []
    claims = known_filings(conn, ticker, cutoff)
    result = []
    for comparison in snapshot["payload"]["comparisons"]:
        if accession and comparison["accession"] != accession:
            continue
        claim = claims.get(comparison["accession"])
        if (
            not claim
            or claim.get("source_status", "active") != "active"
            or source_identity(claim) != comparison["source_identity"]
        ):
            continue
        result.append(
            {
                **comparison,
                "snapshot_id": snapshot["id"],
                "snapshot_version": snapshot["version"],
                "source_url": snapshot["source_url"],
                "source_sha256": snapshot["capture_sha256"],
                "captured_at": utc(snapshot["captured_at"]).isoformat(),
                "available_at": utc(snapshot["available_at"]).isoformat(),
            }
        )
    return result


def main():
    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--cache", type=Path, default=Path("source-cache/financial-facts"))
    args = parser.parse_args()
    require_enabled()
    engine = database()
    client = SourceClient(user_agent=args.user_agent, cache_dir=args.cache)
    report: dict = {"companies": {}, "errors": {}, "delivery": "disabled"}
    try:
        with engine.connect() as conn:
            identities = list(conn.execute(select(source_cursors)).mappings())
        for identity in identities:
            ticker = identity["ticker"]
            try:
                capture = SECSourceAdapter(client).companyfacts(identity["cik"])
                report["companies"][ticker] = ingest(engine, ticker, identity["cik"], capture)
            except (ValueError, RuntimeError) as exc:
                report["errors"][ticker] = str(exc)
        print(json.dumps(report, indent=2))
    finally:
        client.close()
        engine.dispose()
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
