"""Global-operator review API; approvals remain staging receipts, never live facts."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select, update

from engine.api.accounts import write
from engine.api.product import Admin, Body, Key
from engine.db import database
from engine.identity import validate_metric_issuer
from engine.ingestion.contracts import EventExtraction, canonical_key
from engine.models.contracts import utc
from engine.models.schema_v5 import drafts, filings, metadata, reviews
from engine.sec_review import require_real

router = APIRouter(prefix="/api/v0/admin/sec", tags=["SEC review"])


class DraftBody(Body):
    author_kind: Literal["HUMAN", "AI", "UNSPECIFIED"] = "UNSPECIFIED"
    expected_version: int = Field(ge=0)
    event: EventExtraction
    occurrence_window: str = Field(min_length=1, max_length=100)
    correction_of: str | None = Field(default=None, max_length=64)
    duplicate_of: str | None = Field(default=None, max_length=64)


class ReviewBody(Body):
    reviewer_kind: Literal["HUMAN", "AI_INDEPENDENT", "UNSPECIFIED"] = "UNSPECIFIED"
    decision: Literal["approved", "rejected"]
    expected_version: int = Field(ge=1)
    note: str = Field(min_length=10, max_length=2000)
    rights_basis: str = Field(default="", max_length=2000)
    identity_confirmed: bool = False
    citation_confirmed: bool = False
    comparison_confirmed: bool = False

    @model_validator(mode="after")
    def approval_proof(self):
        if len(self.note.strip()) < 10:
            raise ValueError("Review explanation required")
        if self.decision == "approved" and (
            len(self.rights_basis.strip()) < 10
            or not all(
                (self.identity_confirmed, self.citation_confirmed, self.comparison_confirmed)
            )
        ):
            raise ValueError("Independent source, rights, citation and comparison review required")
        return self


def real(conn):
    try:
        require_real(conn)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


def dated(row):
    return {key: utc(value) if isinstance(value, datetime) else value for key, value in row.items()}


def filing(conn, filing_id, at):
    real(conn)
    row = (
        conn.execute(select(filings).where(filings.c.id == filing_id, filings.c.imported_at <= at))
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Filing not available at this time")
    return row


def receipt(conn, draft_id, at):
    row = (
        conn.execute(
            select(reviews).where(reviews.c.draft_id == draft_id, reviews.c.reviewed_at <= at)
        )
        .mappings()
        .first()
    )
    return dated(row) if row else None


def history(conn, filing_id, at):
    return [
        {**dated(d), "review": receipt(conn, d["id"], at)}
        for d in conn.execute(
            select(drafts)
            .where(drafts.c.filing_id == filing_id, drafts.c.created_at <= at)
            .order_by(drafts.c.version)
        ).mappings()
    ]


@router.get("/filings")
def list_filings(
    user: Admin,
    as_of: AwareDatetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    at = min(as_of or datetime.now(UTC), datetime.now(UTC))
    engine = database()
    try:
        with engine.connect() as conn:
            real(conn)
            items = []
            for row in conn.execute(
                select(
                    filings.c.id,
                    filings.c.ticker,
                    filings.c.accession,
                    filings.c.source_url,
                    filings.c.retrieved_at,
                )
                .where(filings.c.imported_at <= at)
                .order_by(filings.c.id)
                .offset(offset)
                .limit(limit)
            ).mappings():
                versions = history(conn, row["id"], at)
                latest = versions[-1] if versions else None
                items.append(
                    dated(
                        {
                            k: row[k]
                            for k in ("id", "ticker", "accession", "source_url", "retrieved_at")
                        }
                    )
                )
                items[-1].update(
                    version=latest["version"] if latest else 0,
                    status=(
                        latest["review"]["decision"]
                        if latest and latest["review"]
                        else "draft"
                        if latest
                        else "pending"
                    ),
                )
            return {"items": items, "as_of": at, "feed_publications": 0}
    finally:
        engine.dispose()


@router.get("/filings/{filing_id}")
def get_filing(filing_id: str, user: Admin, as_of: AwareDatetime | None = None):
    at = min(as_of or datetime.now(UTC), datetime.now(UTC))
    engine = database()
    try:
        with engine.connect() as conn:
            row = dated(filing(conn, filing_id, at))
            versions = history(conn, filing_id, at)
            row["revision"] = versions[-1]["version"] if versions else 0
            return {
                **row,
                "versions": versions,
                "as_of": at,
                "delivery": "disabled",
                "feed_eligible": False,
            }
    finally:
        engine.dispose()


def validate_link(conn, row, body, key, now):
    if body.correction_of and body.duplicate_of:
        raise HTTPException(422, "Choose correction or duplicate, not both")
    target = body.correction_of or body.duplicate_of
    if not target:
        return
    old = conn.execute(select(drafts).where(drafts.c.id == target)).mappings().first()
    approval = receipt(conn, target, now)
    if not old or not approval or approval["decision"] != "approved":
        raise HTTPException(422, "Reference must be an independently approved draft")
    source = filing(conn, old["filing_id"], now)
    if (
        old["canonical_key"] != key
        or old["filing_id"] == row["id"]
        or source["revision"] != old["version"]
        or utc(source["retrieved_at"]) >= utc(row["retrieved_at"])
    ):
        raise HTTPException(422, "Reference must be the current earlier capture of the same event")


@router.post("/filings/{filing_id}/drafts")
def create_draft(filing_id: str, body: DraftBody, user: Admin, key: Key = None):
    def action(conn):
        now = datetime.now(UTC)
        row = filing(conn, filing_id, now)
        event = body.event
        if (
            event.source_document_id != filing_id
            or event.entity_ids != ["CO_" + row["ticker"]]
            or event.available_at != utc(row["retrieved_at"])
            or event.published_at.date().isoformat() != row["manifest"]["filing_date"]
            or len(event.claims) != 1
        ):
            raise HTTPException(
                422, "Draft requires matching document, issuer, capture time and one cited claim"
            )
        claim = event.claims[0]
        try:
            event.validate_source(row["source_text"], row["source_url"])
            if claim.metric_id:
                entity = (
                    conn.execute(
                        select(metadata.tables["rie_entities"]).where(
                            metadata.tables["rie_entities"].c.id == claim.metric_id
                        )
                    )
                    .mappings()
                    .first()
                )
                if not entity or entity["entity_type"] != "financial_metric":
                    raise ValueError("Unknown metric")
                validate_metric_issuer(
                    event.entity_ids[0], claim.metric_id, event.published_at.date()
                )
            canonical = canonical_key(
                issuer=event.entity_ids[0],
                event_type=event.event_type,
                metric=claim.metric_id or "qualitative",
                period=claim.period or "unknown",
                basis=claim.comparison_basis,
                occurrence_window=body.occurrence_window,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        validate_link(conn, row, body, canonical, now)
        changed = conn.execute(
            update(filings)
            .where(filings.c.id == filing_id, filings.c.revision == body.expected_version)
            .values(revision=body.expected_version + 1)
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Draft changed; reload before saving")
        draft_id = str(uuid4())
        conn.execute(
            drafts.insert().values(
                id=draft_id,
                filing_id=filing_id,
                version=body.expected_version + 1,
                author_id=user.id,
                created_at=now,
                canonical_key=canonical,
                payload=body.model_dump(mode="json"),
            )
        )
        return {
            "id": draft_id,
            "version": body.expected_version + 1,
            "status": "draft",
            "feed_eligible": False,
        }

    return write(user, f"sec-draft:{filing_id}", key, body.model_dump(mode="json"), action)


@router.post("/drafts/{draft_id}/reviews")
def review_draft(draft_id: str, body: ReviewBody, user: Admin, key: Key = None):
    def action(conn):
        now = datetime.now(UTC)
        real(conn)
        draft = conn.execute(select(drafts).where(drafts.c.id == draft_id)).mappings().first()
        if not draft:
            raise HTTPException(404, "Draft not found")
        # Lock the filing across operators and concurrent draft edits.
        row = (
            conn.execute(
                select(filings).where(filings.c.id == draft["filing_id"]).with_for_update()
            )
            .mappings()
            .one()
        )
        if row["revision"] != body.expected_version or draft["version"] != row["revision"]:
            raise HTTPException(409, "Review requires the current draft version")
        if draft["author_id"] == user.id:
            raise HTTPException(403, "A different operator must review the extraction")
        if receipt(conn, draft_id, now):
            raise HTTPException(
                409, "Immutable review already recorded; create a new draft version"
            )
        if body.decision == "approved":
            validate_link(
                conn, row, DraftBody.model_validate(draft["payload"]), draft["canonical_key"], now
            )
        review_id = str(uuid4())
        conn.execute(
            reviews.insert().values(
                id=review_id,
                draft_id=draft_id,
                reviewer_id=user.id,
                reviewed_at=now,
                decision=body.decision,
                payload=body.model_dump(mode="json"),
            )
        )
        return {
            "id": review_id,
            "decision": body.decision,
            "feed_eligible": False,
            "delivery": "disabled",
        }

    return write(user, f"sec-review:{draft_id}", key, body.model_dump(mode="json"), action)
