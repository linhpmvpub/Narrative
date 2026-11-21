"""Blind annotation: assigned cases, own revisions, no predictions or other votes."""

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import func, select

from engine.annotations import source_status
from engine.api.accounts import write
from engine.api.product import Admin, Body, Key, User
from engine.db import database
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v10 import assignments, cases, labels, packets

router = APIRouter(prefix="/api/v0/annotations", tags=["Blind human annotation"])


class Numeric(Body):
    verdict: Literal["COMPARABLE", "NOT_COMPARABLE", "UNCERTAIN"]
    current_value: str | None = Field(default=None, max_length=80)
    prior_value: str | None = Field(default=None, max_length=80)
    unit: Literal["USD"] = "USD"
    current_start: date | None = None
    current_end: date | None = None
    prior_start: date | None = None
    prior_end: date | None = None

    @model_validator(mode="after")
    def valid(self):
        if self.verdict == "COMPARABLE":
            if not all(
                (
                    self.current_value,
                    self.prior_value,
                    self.current_start,
                    self.current_end,
                    self.prior_start,
                    self.prior_end,
                )
            ):
                raise ValueError("Independent operand transcription required")
            assert self.current_start and self.current_end and self.prior_start and self.prior_end
            if self.current_start > self.current_end or self.prior_start > self.prior_end:
                raise ValueError("Invalid period")
        for value in (self.current_value, self.prior_value):
            if value is not None:
                try:
                    number = Decimal(value)
                    if not number.is_finite() or abs(number) > Decimal("1e30"):
                        raise ValueError("Finite bounded amount required")
                except InvalidOperation:
                    raise ValueError("Invalid decimal") from None
        return self


class LabelBody(Body):
    expected_version: int = Field(ge=0)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    independent_of_extractor: Literal[True]
    reason: str = Field(min_length=10, max_length=4000)
    language: (
        Literal["ISSUER_ATTRIBUTION", "UNCERTAIN_OR_FORWARD_LOOKING", "NO_CAUSAL_CLAIM"] | None
    ) = None
    numeric: Numeric | None = None

    @model_validator(mode="after")
    def one_label(self):
        if (self.language is None) == (self.numeric is None) or len(self.reason.strip()) < 10:
            raise ValueError("One label type and substantive rationale required")
        return self


def authorized(conn, pid, user):
    if not conn.scalar(
        select(assignments.c.user_id).where(
            assignments.c.packet_id == pid, assignments.c.user_id == user.id
        )
    ):
        raise HTTPException(404, "Assignment not found")


def own(conn, pid, cid, uid):
    return (
        conn.execute(
            select(labels)
            .where(labels.c.packet_id == pid, labels.c.case_id == cid, labels.c.user_id == uid)
            .order_by(labels.c.version.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )


def case(conn, pid, cid, user):
    authorized(conn, pid, user)
    row = conn.execute(
        select(cases.c.payload).where(cases.c.packet_id == pid, cases.c.id == cid)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Case not found")
    return row


@router.get("/packets")
def list_packets(user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            return {
                "items": [
                    {"id": r.id, "case_count": r.case_count, "as_of": utc(r.as_of)}
                    for r in conn.execute(
                        select(packets).join(assignments).where(assignments.c.user_id == user.id)
                    )
                ]
            }
    finally:
        engine.dispose()


@router.get("/{pid}/cases")
def list_cases(
    pid: str,
    user: User,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    engine = database()
    try:
        with engine.connect() as conn:
            authorized(conn, pid, user)
            rows = conn.execute(
                select(cases.c.payload)
                .where(cases.c.packet_id == pid)
                .order_by(cases.c.id)
                .offset(offset)
                .limit(limit)
            ).scalars()
            saved_versions = dict(
                conn.execute(
                    select(labels.c.case_id, func.max(labels.c.version))
                    .where(labels.c.packet_id == pid, labels.c.user_id == user.id)
                    .group_by(labels.c.case_id)
                ).all()
            )
            items = []
            for c in rows:
                items.append(
                    {k: c[k] for k in ("id", "kind", "ticker", "accession")}
                    | {
                        "my_version": saved_versions.get(c["id"], 0),
                        "preview": c.get(
                            "text",
                            c.get("concept", "")
                            + " · "
                            + ", ".join(pair[1] for pair in c.get("dimensions", [])),
                        )[:140],
                    }
                )
            return {"items": items, "next_offset": offset + limit if len(items) == limit else None}
    finally:
        engine.dispose()


@router.get("/{pid}/cases/{cid}")
def get_case(pid: str, cid: str, user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            c = case(conn, pid, cid, user)
            saved = own(conn, pid, cid, user.id)
            return {
                "case": c,
                "source_status": source_status(conn, c),
                "my_label": saved["payload"] if saved else None,
                "my_version": saved["version"] if saved else 0,
            }
    finally:
        engine.dispose()


@router.post("/{pid}/cases/{cid}/labels")
def save(pid: str, cid: str, body: LabelBody, user: User, key: Key = None):
    def action(conn):
        conn.execute(select(database_mode).with_for_update()).one()
        c = case(conn, pid, cid, user)
        if source_status(conn, c) != "CURRENT":
            raise HTTPException(
                409, "Source changed/inactive; refresh the assignment before labeling"
            )
        if body.source_sha256 != c["source_sha256"]:
            raise HTTPException(409, "Source hash mismatch")
        if (c["kind"] == "causal_language") != (body.language is not None):
            raise HTTPException(422, "Label type does not match case")
        previous = own(conn, pid, cid, user.id)
        version = previous["version"] if previous else 0
        if body.expected_version != version:
            raise HTTPException(409, "Label version changed; reload before editing")
        payload = body.model_dump(mode="json")
        payload["reviewer"] = user.id
        payload["reviewed_at"] = datetime.now(UTC).isoformat()
        conn.execute(
            labels.insert().values(
                id=str(uuid4()),
                packet_id=pid,
                case_id=cid,
                user_id=user.id,
                version=version + 1,
                payload=payload,
                created_at=datetime.now(UTC),
            )
        )
        return {"version": version + 1, "delivery": "disabled", "graph_modified": False}

    return write(user, f"annotation/{pid}/{cid}", key, body.model_dump(mode="json"), action)


@router.get("/{pid}/export")
def export(pid: str, user: Admin):
    # Global operator only, unavailable through the mobile gateway. Never an annotator route.
    engine = database()
    try:
        with engine.connect() as conn:
            revisions = [
                {"case_id": r["case_id"], "version": r["version"], **r["payload"]}
                for r in conn.execute(
                    select(labels).where(labels.c.packet_id == pid).order_by(labels.c.created_at)
                ).mappings()
            ]
            frozen = {
                r["id"]: r["payload"]
                for r in conn.execute(select(cases).where(cases.c.packet_id == pid)).mappings()
            }
            latest: dict = {}
            for revision in revisions:
                key = (revision["case_id"], revision["reviewer"])
                if key not in latest or revision["version"] > latest[key]["version"]:
                    latest[key] = revision
            language_labels = []
            excluded = []
            for revision in latest.values():
                c = frozen[revision["case_id"]]
                status = source_status(conn, c)
                if c["split"] != "holdout" or status != "CURRENT" or revision["language"] is None:
                    excluded.append(
                        {
                            "case_id": c["id"],
                            "reviewer": revision["reviewer"],
                            "source_status": status,
                            "split": c["split"],
                            "kind": c["kind"],
                        }
                    )
                    continue
                language_labels.append(
                    {
                        **{
                            k: revision[k]
                            for k in (
                                "case_id",
                                "reviewer",
                                "reviewed_at",
                                "source_sha256",
                                "independent_of_extractor",
                                "reason",
                            )
                        },
                        "label": revision["language"],
                    }
                )
            return {
                "packet_id": pid,
                "revisions": revisions,
                "latest_labels": list(latest.values()),
                "holdout_language_labels": language_labels,
                "excluded_from_language_evaluation": excluded,
                "adjudication": "PENDING_SEPARATE_REVIEW",
                "delivery": "disabled",
            }
    finally:
        engine.dispose()
