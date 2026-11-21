"""Import frozen blind packets locally; reviewer identity comes from provisioned accounts."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from engine.evaluation.filing_labels import packet
from engine.filing_evidence import snapshots
from engine.financials import known_filings, source_identity
from engine.ingestion.contracts import digest
from engine.models.schema_v2 import database_mode
from engine.models.schema_v10 import assignments, cases, packets


def source_status(conn, case):
    snapshot = (
        conn.execute(select(snapshots).where(snapshots.c.id == case["snapshot_id"]))
        .mappings()
        .first()
    )
    if not snapshot or snapshot["capture_sha256"] != case["source_sha256"]:
        return "SOURCE_UNAVAILABLE"
    current = known_filings(conn, case["ticker"], datetime.now(UTC)).get(case["accession"])
    if not current or current.get("source_status", "active") != "active":
        return "SOURCE_INACTIVE"
    if source_identity(current) != snapshot["payload"]["source_identity"]:
        return "SOURCE_CHANGED"
    latest = conn.scalar(
        select(snapshots.c.id)
        .where(snapshots.c.ticker == case["ticker"], snapshots.c.accession == case["accession"])
        .order_by(snapshots.c.version.desc())
        .limit(1)
    )
    return "CURRENT" if latest == snapshot["id"] else "SUPERSEDED"


def import_packet(engine, blind, users):
    if not blind or len(blind) > 10000 or not users:
        raise ValueError("Cases and assigned accounts required")
    cutoff = datetime.fromisoformat(blind[0]["as_of"])
    if cutoff.tzinfo is None or cutoff > datetime.now(UTC):
        raise ValueError("Invalid frozen cutoff")
    ordered = sorted(blind, key=lambda c: c["id"])
    pid = digest(ordered)
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        conn.execute(select(database_mode).with_for_update()).one()
        expected = sorted(packet(conn, cutoff)["cases"], key=lambda c: c["id"])
        if ordered != expected:
            raise ValueError(
                "Blind cases must exactly match frozen source packet; predictions forbidden"
            )
        if not conn.scalar(select(packets.c.id).where(packets.c.id == pid)):
            conn.execute(
                packets.insert().values(
                    id=pid, created_at=datetime.now(UTC), as_of=cutoff, case_count=len(blind)
                )
            )
            conn.execute(
                cases.insert(), [{"packet_id": pid, "id": c["id"], "payload": c} for c in ordered]
            )
        for uid in set(users):
            if not conn.scalar(
                select(assignments.c.user_id).where(
                    assignments.c.packet_id == pid, assignments.c.user_id == uid
                )
            ):
                conn.execute(assignments.insert().values(packet_id=pid, user_id=uid))
    return {
        "packet_id": pid,
        "cases": len(blind),
        "assigned_accounts": len(set(users)),
        "labels_created": 0,
    }


def main():
    import argparse

    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind-cases", type=Path, required=True)
    parser.add_argument("--user-id", action="append", required=True)
    args = parser.parse_args()
    engine = database()
    try:
        print(
            json.dumps(
                import_packet(
                    engine, json.loads(args.blind_cases.read_text(encoding="utf-8")), args.user_id
                )
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
