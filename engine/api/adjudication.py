"""Local operator consensus and revision-bound independent adjudication."""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select

from engine.api.accounts import write
from engine.api.annotations import Numeric
from engine.api.product import Admin, Body, Key, User
from engine.db import database
from engine.evaluation.campaign import progress
from engine.evaluation.consensus import quality, states
from engine.models.schema_v2 import database_mode
from engine.models.schema_v10 import labels, packets
from engine.models.schema_v11 import adjudications
from engine.models.schema_v12 import roster

router = APIRouter(prefix="/api/v0/admin/evaluation", tags=["Independent adjudication"])


class Decision(Body):
    expected_vote_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_decision_version: int = Field(ge=0)
    outcome: Literal["RESOLVED", "DEFERRED"]
    independent_of_extractor: Literal[True]
    reason: str = Field(min_length=10, max_length=4000)
    language: (
        Literal["ISSUER_ATTRIBUTION", "UNCERTAIN_OR_FORWARD_LOOKING", "NO_CAUSAL_CLAIM"] | None
    ) = None
    numeric: Numeric | None = None

    @model_validator(mode="after")
    def valid(self):
        count = int(self.language is not None) + int(self.numeric is not None)
        if count != (1 if self.outcome == "RESOLVED" else 0) or len(self.reason.strip()) < 10:
            raise ValueError(
                "Resolved decisions need one label; deferred decisions need none; rationale required"
            )
        return self


def load(conn, pid, user):
    if user.role != "admin" and not conn.scalar(
        select(roster.c.user_id).where(
            roster.c.packet_id == pid, roster.c.user_id == user.id, roster.c.slot == "adjudicator"
        )
    ):
        raise HTTPException(403, "Assigned adjudicator or operator required")
    try:
        return states(conn, pid)
    except ValueError:
        raise HTTPException(404, "Packet not found") from None


@router.get("/packets")
def list_packets(user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            query = select(packets)
            if user.role != "admin":
                query = query.where(
                    packets.c.id.in_(
                        select(roster.c.packet_id).where(
                            roster.c.user_id == user.id, roster.c.slot == "adjudicator"
                        )
                    )
                )
            return {"items": [dict(r) for r in conn.execute(query).mappings()]}
    finally:
        engine.dispose()


@router.get("/{pid}/cases")
def queue(pid: str, user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            return {
                "items": [
                    {
                        "id": s["case"]["id"],
                        "ticker": s["case"]["ticker"],
                        "kind": s["case"]["kind"],
                        "status": s["status"],
                        "vote_count": len(s["votes"]),
                        "stale_adjudication": s["stale_adjudication"],
                    }
                    for s in load(conn, pid, user)
                ]
            }
    finally:
        engine.dispose()


@router.get("/{pid}/cases/{cid}")
def detail(pid: str, cid: str, user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            s = next((s for s in load(conn, pid, user) if s["case"]["id"] == cid), None)
            if s is None:
                raise HTTPException(404, "Case not found")
            s["self_review_forbidden"] = any(v["user_id"] == user.id for v in s["votes"])
            return s
    finally:
        engine.dispose()


@router.get("/{pid}/quality")
def report(pid: str, user: User):
    from engine.evaluation.agent_pilot import public_summary

    engine = database()
    try:
        with engine.connect() as conn:
            load(conn, pid, user)
            return quality(conn, pid) | {
                "campaign_progress": progress(conn, pid),
                "ai_simulation": public_summary(pid),
            }
    finally:
        engine.dispose()


@router.get("/{pid}/export")
def export(pid: str, user: Admin):
    engine = database()
    try:
        with engine.connect() as conn:
            current = load(conn, pid, user)
            return {
                "packet_id": pid,
                "quality": quality(conn, pid),
                "cases": current,
                "label_revisions": [
                    dict(r)
                    for r in conn.execute(
                        select(labels)
                        .where(labels.c.packet_id == pid)
                        .order_by(labels.c.case_id, labels.c.user_id, labels.c.version)
                    ).mappings()
                ],
                "adjudication_revisions": [
                    dict(r)
                    for r in conn.execute(
                        select(adjudications)
                        .where(adjudications.c.packet_id == pid)
                        .order_by(adjudications.c.case_id, adjudications.c.version)
                    ).mappings()
                ],
                "delivery": "disabled",
            }
    finally:
        engine.dispose()


@router.post("/{pid}/cases/{cid}/adjudications")
def save(pid: str, cid: str, body: Decision, user: User, key: Key = None):
    def action(conn):
        conn.execute(select(database_mode).with_for_update()).one()
        s = next((s for s in load(conn, pid, user) if s["case"]["id"] == cid), None)
        if s is None:
            raise HTTPException(404, "Case not found")
        if any(v["user_id"] == user.id for v in s["votes"]):
            raise HTTPException(403, "A third account must adjudicate")
        if (
            body.expected_vote_hash != s["vote_hash"]
            or body.expected_decision_version != s["decision_version"]
        ):
            raise HTTPException(409, "Votes or decision changed; reload before adjudicating")
        if s["status"] not in {"DISAGREEMENT", "ADJUDICATION_DEFERRED", "ADJUDICATED"}:
            raise HTTPException(409, "Requires current independent disagreeing votes")
        if body.outcome == "RESOLVED" and (
            (s["case"]["kind"] == "causal_language") != (body.language is not None)
        ):
            raise HTTPException(422, "Decision type does not match case")
        now = datetime.now(UTC)
        version = s["decision_version"] + 1
        payload = body.model_dump(mode="json") | {
            "reviewer": user.id,
            "reviewed_at": now.isoformat(),
        }
        conn.execute(
            adjudications.insert().values(
                id=str(uuid4()),
                packet_id=pid,
                case_id=cid,
                version=version,
                vote_hash=s["vote_hash"],
                reviewer_id=user.id,
                payload=payload,
                created_at=now,
            )
        )
        return {"version": version, "delivery": "disabled", "graph_modified": False}

    return write(user, f"adjudication/{pid}/{cid}", key, body.model_dump(mode="json"), action)
