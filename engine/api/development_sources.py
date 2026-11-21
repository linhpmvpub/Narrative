"""Operator-attested filing lifecycle; source rights do not gate development."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import Field, HttpUrl, model_validator

from engine.api.accounts import write
from engine.api.product import Admin, Body, Key
from engine.ingestion.incremental import attest_lifecycle

router = APIRouter(prefix="/api/v0/admin/development", tags=["Development source lifecycle"])


class LifecycleBody(Body):
    expected_version: int = Field(ge=1)
    action: Literal["withdrawn", "restored"]
    evidence_url: HttpUrl
    reason: str = Field(min_length=20, max_length=2000)

    @model_validator(mode="after")
    def source(self):
        if (
            self.evidence_url.scheme != "https"
            or self.evidence_url.host not in {"www.sec.gov", "sec.gov", "data.sec.gov"}
            or self.evidence_url.username
            or self.evidence_url.password
        ):
            raise ValueError("SEC evidence link required")
        if len(self.reason.strip()) < 20:
            raise ValueError("Explain the source evidence")
        return self


@router.post("/versions/{version_id}/lifecycle")
def lifecycle(version_id: UUID, body: LifecycleBody, user: Admin, key: Key = None):
    def action(conn):
        try:
            return attest_lifecycle(
                conn,
                str(version_id),
                body.expected_version,
                body.action,
                user.id,
                str(body.evidence_url),
                body.reason,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    return write(
        user, "development-lifecycle:" + str(version_id), key, body.model_dump(mode="json"), action
    )
