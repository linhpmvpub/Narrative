"""Atomic incremental reconciliation, with conservative absence semantics."""

import hashlib
import json
import re
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import select

from engine.collect_sec import TICKERS, candidates
from engine.development_feed import KIND, apply_rows, events, require_enabled, versions
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v7 import collection_runs, source_cursors


def decoded(capture, expected_url):
    if capture.url != expected_url or capture.retrieved_at.tzinfo is None:
        raise ValueError("Invalid snapshot URL/time")
    if capture.retrieved_at > datetime.now(UTC):
        raise ValueError("Future snapshot")
    if hashlib.sha256(capture.text.encode()).hexdigest() != capture.content_sha256:
        raise ValueError("Snapshot hash mismatch")
    return json.loads(capture.text)


def columns(data):
    keys = ("accessionNumber", "filingDate", "form", "primaryDocument")
    if not all(isinstance(data.get(k), list) for k in keys):
        raise ValueError("Incomplete submission columns")
    if len({len(data[k]) for k in keys}) != 1 or len(data[keys[0]]) > 20000:
        raise ValueError("Invalid submission column lengths")
    rows = list(zip(*(data[k] for k in keys), strict=True))
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError("Duplicate accession in snapshot")
    for accession, filed, _, _ in rows:
        if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
            raise ValueError("Invalid accession")
        date.fromisoformat(filed)
    return rows


def reconcile(engine, ticker, cik, capture, archives=(), *, initial_limit=10):
    require_enabled()
    if ticker not in TICKERS or not 1 <= initial_limit <= 20:
        raise ValueError("Invalid pilot scope")
    payload = decoded(capture, f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
    if str(payload.get("cik", "")).zfill(10) != cik or ticker not in payload.get("tickers", []):
        raise ValueError("Issuer mismatch")
    recent = payload["filings"]["recent"]
    raw = columns(recent)
    origins = {r[0]: capture for r in raw}
    coverage = []
    if raw:
        coverage.append((min(date.fromisoformat(r[1]) for r in raw), capture.retrieved_at.date()))
    files = {x["name"]: x for x in payload["filings"].get("files", [])}
    provenance = [
        {
            "url": capture.url,
            "sha256": capture.content_sha256,
            "captured_at": capture.retrieved_at.isoformat(),
        }
    ]
    if len(archives) > 10:
        raise ValueError("Archive budget exceeded; checkpoint not advanced")
    for archive in archives:
        name = archive.url.rsplit("/", 1)[-1]
        if name not in files or not re.fullmatch(r"CIK[0-9]{10}-submissions-[0-9]{3}\.json", name):
            raise ValueError("Unlisted archive")
        if not name.startswith("CIK" + cik + "-"):
            raise ValueError("Archive issuer mismatch")
        data = decoded(archive, "https://data.sec.gov/submissions/" + name)
        history = columns(data)
        start, end = (date.fromisoformat(files[name][k]) for k in ("filingFrom", "filingTo"))
        if (
            not history
            or start > end
            or any(not start <= date.fromisoformat(r[1]) <= end for r in history)
        ):
            raise ValueError("Incomplete archive coverage")
        raw.extend(history)
        for row in history:
            origins.setdefault(row[0], archive)
        coverage.append((start, end))
        provenance.append(
            {
                "url": archive.url,
                "sha256": archive.content_sha256,
                "captured_at": archive.retrieved_at.isoformat(),
            }
        )
    by_accession: dict = {}
    for row in raw:
        if row[0] in by_accession and by_accession[row[0]] != row:
            raise ValueError("Conflicting overlapping archive records")
        if date.fromisoformat(row[1]) > capture.retrieved_at.date():
            raise ValueError("Future filing metadata")
        by_accession[row[0]] = row
    merged = {
        k: [r[i] for r in by_accession.values()]
        for i, k in enumerate(("accessionNumber", "filingDate", "form", "primaryDocument"))
    }
    parsed = candidates(
        ticker,
        cik,
        {"cik": cik, "tickers": [ticker], "filings": {"recent": merged}},
        date(2025, 2, 21),
        capture.retrieved_at.date(),
        20000,
    )
    signature = digest(provenance)
    run_id = digest([ticker, signature])
    now = datetime.now(UTC)
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        if conn.scalar(select(database_mode.c.mode).with_for_update()) != "production":
            raise ValueError("Separate non-synthetic database required")
        cursor = (
            conn.execute(select(source_cursors).where(source_cursors.c.ticker == ticker))
            .mappings()
            .first()
        )
        old_run = conn.scalar(
            select(collection_runs.c.result).where(collection_runs.c.id == run_id)
        )
        if old_run is not None:
            return {**old_run, "replayed": True, "new_versions": 0}
        if cursor and (cursor["cik"] != cik or capture.retrieved_at <= utc(cursor["captured_at"])):
            raise ValueError("Stale collection snapshot or changed issuer")
        latest = {}
        for version in conn.execute(
            select(versions)
            .join(events)
            .where(events.c.event_type == KIND, events.c.issuer_entity_id == "CO_" + ticker)
            .order_by(versions.c.version_number)
        ).mappings():
            latest[version["event_id"]] = version
        known = {r["normalized_claim"]["accession"]: r["normalized_claim"] for r in latest.values()}
        floor = (
            cursor["floor_date"]
            if cursor
            else min(
                (date.fromisoformat(r["filing_date"]) for r in known.values()),
                default=min(
                    (date.fromisoformat(r["filing_date"]) for r in parsed[:initial_limit]),
                    default=date(2025, 2, 21),
                ),
            )
        )
        eligible = [
            r
            for r in parsed
            if date.fromisoformat(r["filing_date"]) >= floor or r["accession"] in known
        ]
        # Withdrawal is an explicit operator attestation; automatic presence cannot erase it.
        eligible = [
            r for r in eligible if known.get(r["accession"], {}).get("source_status") != "withdrawn"
        ]
        missing, uncovered = [], []
        for accession, claim in known.items():
            if accession in by_accession or claim.get("source_status") == "withdrawn":
                continue
            filed = date.fromisoformat(claim["filing_date"])
            if not any(start <= filed <= end for start, end in coverage):
                uncovered.append(accession)
                continue
            missing.append(accession)
            if claim.get("source_status") != "missing_unconfirmed":
                eligible.append(
                    {
                        **claim,
                        "source_status": "missing_unconfirmed",
                        "lifecycle_evidence": {
                            "kind": "absence_in_covered_snapshot",
                            "snapshots": provenance,
                            "observed_at": capture.retrieved_at.isoformat(),
                        },
                    }
                )
        receipts = []
        for row in eligible:
            receipts.extend(apply_rows(conn, [row], origins.get(row["accession"], capture), now))
        result = {
            "ticker": ticker,
            "replayed": False,
            "new_versions": sum(r["status"] != "duplicate" for r in receipts),
            "versions": receipts,
            "missing_unconfirmed": missing,
            "uncovered": uncovered,
            "floor_date": floor.isoformat(),
            "snapshots": provenance,
            "delivery": "disabled",
        }
        values = dict(
            ticker=ticker,
            cik=cik,
            floor_date=floor,
            captured_at=capture.retrieved_at,
            snapshot_hash=signature,
        )
        if cursor:
            conn.execute(
                source_cursors.update().where(source_cursors.c.ticker == ticker).values(**values)
            )
        else:
            conn.execute(source_cursors.insert().values(**values))
        conn.execute(
            collection_runs.insert().values(
                id=run_id,
                ticker=ticker,
                captured_at=capture.retrieved_at,
                recorded_at=now,
                result=result,
            )
        )
        return result


def collect_company(engine, client, ticker, cik, *, initial_limit=10):
    from engine.adapters.http_sources import SECSourceAdapter

    capture = SECSourceAdapter(client).submissions(cik)
    payload = json.loads(capture.text)
    with engine.connect() as conn:
        floor = conn.scalar(
            select(source_cursors.c.floor_date).where(source_cursors.c.ticker == ticker)
        )
        if floor is None:
            dates = conn.scalars(
                select(versions.c.normalized_claim)
                .join(events)
                .where(events.c.event_type == KIND, events.c.issuer_entity_id == "CO_" + ticker)
            )
            floor = min((date.fromisoformat(r["filing_date"]) for r in dates), default=None)
    archives = []
    if floor:
        files = [
            f
            for f in payload["filings"].get("files", [])
            if date.fromisoformat(f["filingTo"]) >= floor
        ]
        if len(files) > 10:
            raise ValueError("Archive budget exceeded; checkpoint not advanced")
        for f in files:
            name = f["name"]
            if not re.fullmatch(r"CIK" + cik + r"-submissions-[0-9]{3}\.json", name):
                raise ValueError("Invalid archive path")
            archives.append(client.fetch("https://data.sec.gov/submissions/" + name))
    return reconcile(engine, ticker, cik, capture, archives, initial_limit=initial_limit)


def attest_lifecycle(conn, vid, expected_version, action, operator, url, reason):
    """Audited operator evidence, distinct from automated absence detection."""
    require_enabled()
    conn.execute(select(database_mode.c.id).with_for_update()).all()
    old = (
        conn.execute(
            select(versions).join(events).where(versions.c.id == vid, events.c.event_type == KIND)
        )
        .mappings()
        .first()
    )
    if not old:
        raise ValueError("Development event version not found")
    latest = conn.scalar(
        select(versions.c.version_number)
        .where(versions.c.event_id == old["event_id"])
        .order_by(versions.c.version_number.desc())
        .limit(1)
    )
    if latest != expected_version or old["version_number"] != expected_version:
        raise ValueError("Stale event version")
    claim = dict(old["normalized_claim"])
    if action == "withdrawn":
        claim["source_status"] = "withdrawn"
    else:
        if claim.get("source_status") != "withdrawn":
            raise ValueError("Only a confirmed withdrawal can be explicitly restored")
        claim["source_status"] = "active"
    now = datetime.now(UTC)
    claim["lifecycle_evidence"] = {
        "kind": "operator_attestation",
        "operator_id": operator,
        "url": url,
        "reason": reason,
        "recorded_at": now.isoformat(),
    }
    new_id = str(uuid4())
    headline = f"{claim['ticker']}: hồ sơ {claim['form']} ngày {claim['filing_date']}"
    headline = ("Đã xác nhận rút · " if action == "withdrawn" else "Đã khôi phục · ") + headline
    conn.execute(
        versions.insert().values(
            id=new_id,
            event_id=old["event_id"],
            version_number=latest + 1,
            factual_headline=headline,
            normalized_claim=claim,
            document_id=old["document_id"],
            extraction_model="operator-source-lifecycle-v1",
            available_at=now,
            is_correction=True,
            supersedes_version_id=vid,
        )
    )
    return {
        "event_version_id": new_id,
        "version": latest + 1,
        "source_status": claim["source_status"],
        "delivery": "disabled",
    }
