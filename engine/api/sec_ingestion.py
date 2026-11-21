"""Explicit operator source permission and canonical ingestion endpoints."""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, Field, HttpUrl, model_validator
from sqlalchemy import select, update

from engine.api.accounts import write
from engine.api.product import Admin, Body, Key
from engine.api.sec_review import dated, real
from engine.db import database
from engine.ingestion.reviewed import ingest_reviewed, latest_permission, reviewed_versions_as_of
from engine.models.schema_v5 import filings
from engine.models.schema_v6 import metadata, permissions

router = APIRouter(prefix="/api/v0/admin/sec", tags=["Reviewed ingestion"])


class PermissionBody(Body):
    expected_permission_version: int = Field(ge=0)
    status: Literal["approved", "revoked"]
    cik: str = Field(pattern=r"^\d{10}$")
    evidence_url: HttpUrl
    rights_note: str = Field(min_length=10, max_length=2000)
    identity_note: str = Field(min_length=10, max_length=2000)
    identity_confirmed: bool
    valid_until: AwareDatetime

    @model_validator(mode="after")
    def proof(self):
        if (
            self.evidence_url.scheme != "https"
            or self.evidence_url.host not in {"www.sec.gov", "sec.gov"}
            or self.evidence_url.username
            or self.evidence_url.password
            or len(self.rights_note.strip()) < 10
            or len(self.identity_note.strip()) < 10
            or (self.status == "approved" and not self.identity_confirmed)
        ):
            raise ValueError("Explicit SEC source rights and issuer identity proof required")
        return self


class IngestBody(Body):
    expected_version: int = Field(ge=1)
    expected_permission_version: int = Field(ge=1)
    as_of: AwareDatetime


@router.post("/filings/{filing_id}/permissions")
def set_permission(filing_id: str, body: PermissionBody, user: Admin, key: Key = None):
    def action(conn):
        real(conn)
        row = (
            conn.execute(select(filings).where(filings.c.id == filing_id).with_for_update())
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Filing not found")
        now = datetime.now(UTC)
        old = latest_permission(conn, filing_id, now)
        if (old["version"] if old else 0) != body.expected_permission_version:
            raise HTTPException(409, "Source permission changed; reload")
        if body.cik != row["manifest"]["cik"] or (
            body.status == "approved" and body.valid_until <= now
        ):
            raise HTTPException(422, "Capture identity mismatch or permission already expired")
        permission_id = str(uuid4())
        conn.execute(
            permissions.insert().values(
                id=permission_id,
                filing_id=filing_id,
                version=body.expected_permission_version + 1,
                status=body.status,
                operator_id=user.id,
                recorded_at=now,
                valid_until=body.valid_until,
                capture_hash=row["content_sha256"],
                payload=body.model_dump(mode="json"),
            )
        )
        source = metadata.tables["rie_sources"]
        conn.execute(
            update(source)
            .where(source.c.id == "sec-reviewed:" + filing_id)
            .values(
                rights_status="approved" if body.status == "approved" else "blocked",
                rights_note=body.rights_note,
            )
        )
        return dict(
            id=permission_id,
            version=body.expected_permission_version + 1,
            status=body.status,
            recorded_at=now.isoformat(),
            delivery="disabled",
        )

    return write(user, "sec-permission:" + filing_id, key, body.model_dump(mode="json"), action)


@router.get("/filings/{filing_id}/permissions")
def get_permissions(filing_id: str, user: Admin, as_of: AwareDatetime | None = None):
    at = min(as_of or datetime.now(UTC), datetime.now(UTC))
    engine = database()
    try:
        with engine.connect() as conn:
            real(conn)
            return {
                "items": [
                    dated(row)
                    for row in conn.execute(
                        select(permissions)
                        .where(
                            permissions.c.filing_id == filing_id, permissions.c.recorded_at <= at
                        )
                        .order_by(permissions.c.version)
                    ).mappings()
                ],
                "as_of": at,
            }
    finally:
        engine.dispose()


@router.post("/drafts/{draft_id}/ingest")
def ingest(draft_id: str, body: IngestBody, user: Admin, key: Key = None):
    def action(conn):
        try:
            return ingest_reviewed(
                conn,
                draft_id,
                body.expected_version,
                body.expected_permission_version,
                body.as_of,
                user.id,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    return write(user, "sec-ingest:" + draft_id, key, body.model_dump(mode="json"), action)


@router.get("/events")
def canonical_events(user: Admin, as_of: AwareDatetime | None = None):
    at = min(as_of or datetime.now(UTC), datetime.now(UTC))
    engine = database()
    try:
        with engine.connect() as conn:
            real(conn)
            return {"items": reviewed_versions_as_of(conn, at), "as_of": at, "delivery": "disabled"}
    finally:
        engine.dispose()
