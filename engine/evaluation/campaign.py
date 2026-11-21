"""Prepare real-reviewer account slots without inventing identities or labels."""

import hashlib
import json
import secrets
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from engine.evaluation.consensus import states
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v4 import tokens, users
from engine.models.schema_v10 import assignments, labels, packets
from engine.models.schema_v11 import predictions
from engine.models.schema_v12 import roster

SLOTS = ("reviewer_a", "reviewer_b", "adjudicator")


def hashed(value):
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(engine, pid, directory: Path):
    """Transactional provisioning; secrets only in an ignored local handoff directory."""
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        conn.execute(select(database_mode).with_for_update()).one()
        existing = conn.execute(select(roster).where(roster.c.packet_id == pid)).mappings().all()
        if existing:
            if {r["slot"] for r in existing} != set(SLOTS):
                raise ValueError("Incomplete roster requires operator recovery")
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            if manifest["packet_id"] != pid:
                raise ValueError("Handoff directory belongs to another packet")
            for r in existing:
                credential = (directory / (r["slot"] + ".txt")).read_text().strip()
                active = (
                    conn.execute(
                        select(tokens).where(
                            tokens.c.user_id == r["user_id"],
                            tokens.c.token_hash == hashed(credential),
                        )
                    )
                    .mappings()
                    .first()
                )
                if (
                    manifest["accounts"].get(r["slot"]) != r["user_id"]
                    or not active
                    or active["revoked"]
                    or utc(active["expires_at"]) <= datetime.now(UTC)
                ):
                    raise ValueError(
                        "Credential unavailable/expired; explicit operator rotation required"
                    )
            return {"status": "existing", "accounts": 3, "labels_created": 0}
        if not conn.scalar(select(packets.c.id).where(packets.c.id == pid)) or not conn.scalar(
            select(predictions.c.packet_id).where(predictions.c.packet_id == pid)
        ):
            raise ValueError("Import packet and freeze predictions first")
        if conn.scalar(select(labels.c.id).where(labels.c.packet_id == pid).limit(1)):
            raise ValueError("Existing labels require explicit roster reconciliation")
        # No existing labels can be orphaned: this campaign replaces preview assignments only.
        conn.execute(assignments.delete().where(assignments.c.packet_id == pid))
        directory.mkdir(parents=True, exist_ok=False)
        now = datetime.now(UTC)
        manifest = {
            "packet_id": pid,
            "accounts": {},
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "identity_status": "UNCLAIMED_ROLE_SLOTS",
            "delivery": "disabled",
        }
        for slot in SLOTS:
            uid, credential = str(uuid4()), secrets.token_urlsafe(32)
            conn.execute(
                users.insert().values(id=uid, tenant_id="annotation-" + uid, role="member")
            )
            conn.execute(
                tokens.insert().values(
                    token_hash=hashed(credential),
                    user_id=uid,
                    expires_at=now + timedelta(days=30),
                    revoked=False,
                )
            )
            conn.execute(
                roster.insert().values(packet_id=pid, slot=slot, user_id=uid, created_at=now)
            )
            if slot != "adjudicator":
                conn.execute(assignments.insert().values(packet_id=pid, user_id=uid))
            (directory / (slot + ".txt")).write_text(credential + "\n", encoding="utf-8")
            manifest["accounts"][slot] = uid
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"status": "prepared", "accounts": 3, "labels_created": 0}


def progress(conn, pid):
    current = states(conn, pid)
    people = (
        conn.execute(select(roster).where(roster.c.packet_id == pid).order_by(roster.c.slot))
        .mappings()
        .all()
    )
    reviewers = []
    for person in people:
        if person["slot"] == "adjudicator":
            continue
        votes = [(s, v) for s in current for v in s["votes"] if v["user_id"] == person["user_id"]]
        valid = [
            (s, v)
            for s, v in votes
            if s["source_status"] == "CURRENT" and s["status"] != "INVALID_LABELS"
        ]
        active = conn.scalar(
            select(tokens.c.user_id)
            .where(
                tokens.c.user_id == person["user_id"],
                tokens.c.revoked.is_(False),
                tokens.c.expires_at > datetime.now(UTC),
            )
            .limit(1)
        )
        reviewers.append(
            {
                "slot": person["slot"],
                "total": len(current),
                "submitted": len(votes),
                "current_source_completed": len(valid),
                "remaining": len(current) - len(valid),
                "source_blocked": sum(s["source_status"] != "CURRENT" for s in current),
                "actionable_remaining": sum(s["source_status"] == "CURRENT" for s in current)
                - len(valid),
                "by_kind": dict(Counter(s["case"]["kind"] for s, v in valid)),
                "last_saved_at": max(utc(v["created_at"]) for s, v in votes).isoformat()
                if votes
                else None,
                "credential_active": bool(active),
            }
        )
    counts = dict(Counter(s["status"] for s in current))
    return {
        "packet_id": pid,
        "configured": len(people) == 3,
        "total_cases": len(current),
        "required_independent_labels": 2 * len(current),
        "reviewers": reviewers,
        "cases_with_two_votes": sum(len(s["votes"]) >= 2 for s in current),
        "states": counts,
        "unresolved_disagreements": counts.get("DISAGREEMENT", 0)
        + counts.get("ADJUDICATION_DEFERRED", 0),
        "stale_decisions": sum(s["stale_adjudication"] for s in current),
        "identity_verification": "operator_must_confirm_distinct_humans",
        "delivery": "disabled",
    }


def main():
    import argparse

    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--prepare", type=Path)
    args = parser.parse_args()
    engine = database()
    try:
        if args.prepare:
            # Prevent accidental public credential artifacts.
            import subprocess

            target = args.prepare.resolve()
            secrets_root = Path("secrets").resolve()
            if not target.is_relative_to(secrets_root) or target == secrets_root:
                parser.error("Handoff must be a new directory underneath ignored secrets/")
            ignored = subprocess.run(
                ["git", "check-ignore", "--quiet", str(target / "manifest.json")]
            )
            if ignored.returncode:
                parser.error("Handoff directory must be Git-ignored")
            print(json.dumps(prepare(engine, args.packet, target)))
        else:
            with engine.connect() as conn:
                print(json.dumps(progress(conn, args.packet), indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
