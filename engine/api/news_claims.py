"""Private news claim authoring and local operator review; no automatic promotion."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from engine.api.accounts import transaction, write
from engine.api.product import Admin, Key, User
from engine.db import database
from engine.ingestion.contracts import digest
from engine.ingestion.news_reviewed import IngestBody, ingest
from engine.ingestion.reviewed import sources, versions
from engine.models.contracts import utc
from engine.models.schema_v13 import news_items, news_revisions
from engine.models.schema_v15 import news_promotions
from engine.news_claims import (
    ClaimBody,
    ReviewBody,
    claims,
    create,
    latest_review,
    prepare,
    review,
    source_text,
    validate,
)
from engine.news_snapshot import snapshot

router = APIRouter(prefix="/api/v0/news-claims")


@router.get("/source/{item_id}")
def source(item_id: str, user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            row = (
                conn.execute(
                    select(news_revisions)
                    .join(news_items, news_items.c.id == news_revisions.c.item_id)
                    .where(
                        news_items.c.id == item_id, news_revisions.c.version == news_items.c.version
                    )
                )
                .mappings()
                .first()
            )
        if not row:
            raise HTTPException(404, "News source not found")
        return {
            "item_id": item_id,
            "revision_id": row["id"],
            "version": row["version"],
            "text": source_text(row["payload"]),
            "url": row["payload"]["url"],
            "payload_sha256": digest(row["payload"]),
            "received_at": utc(row["received_at"]),
            "source_text_basis": "RSS_TITLE_NEWLINE_SUMMARY_V1",
            "role": user.role,
        }
    finally:
        engine.dispose()


@router.get("")
def list_claims(user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            query = select(claims).order_by(claims.c.created_at.desc()).limit(100)
            if user.role != "admin":
                query = query.where(claims.c.author_id == user.id)
            result = []
            for draft in conn.execute(query).mappings():
                latest = latest_review(conn, draft["id"])
                state = latest["decision"] if latest else "pending"
                reason = None
                try:
                    validate(conn, ClaimBody.model_validate(draft["payload"]), datetime.now(UTC))
                except ValueError as exc:
                    state, reason = "stale_or_invalid", str(exc)
                receipt = (
                    conn.execute(
                        select(news_promotions).where(news_promotions.c.claim_id == draft["id"])
                    )
                    .mappings()
                    .first()
                )
                ingestion_status = "not_ingested"
                if receipt:
                    blocked = (
                        conn.scalar(
                            select(sources.c.rights_status).where(
                                sources.c.id == "news-reviewed:" + draft["revision_id"]
                            )
                        )
                        == "blocked"
                    )
                    current_version = conn.scalar(
                        select(versions.c.id)
                        .where(versions.c.event_id == receipt["result"]["event_id"])
                        .order_by(versions.c.version_number.desc())
                        .limit(1)
                    )
                    ingestion_status = (
                        "withheld"
                        if blocked or state != "approved" or latest["id"] != receipt["review_id"]
                        else "superseded"
                        if current_version != receipt["event_version_id"]
                        else "recorded_not_impact_eligible"
                    )
                result.append(
                    {
                        "id": draft["id"],
                        "author_id": draft["author_id"],
                        "created_at": utc(draft["created_at"]),
                        "payload": draft["payload"],
                        "status": state,
                        "blocker": reason,
                        "ingestion_receipt": receipt["result"] if receipt else None,
                        "ingestion_identity": receipt["request"] if receipt else None,
                        "ingestion_status": ingestion_status,
                        "review_version": latest["version"] if latest else 0,
                        "latest_review": latest["payload"] if latest else None,
                    }
                )
        return {
            "items": result,
            "role": user.role,
            "current_user_id": user.id,
            "delivery": "disabled",
        }
    finally:
        engine.dispose()


def safe(action):
    try:
        return action()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("")
def create_claim(body: ClaimBody, user: User, key: Key = None):
    return safe(
        lambda: write(
            user,
            "news-claim-create",
            key,
            body.model_dump(mode="json"),
            lambda conn: create(conn, user, body),
        )
    )


@router.post("/{claim_id}/reviews")
def review_claim(claim_id: str, body: ReviewBody, user: Admin, key: Key = None):
    return safe(
        lambda: write(
            user,
            "news-claim-review:" + claim_id,
            key,
            body.model_dump(mode="json"),
            lambda conn: review(conn, user, claim_id, body),
        )
    )


@router.post("/{claim_id}/prepare")
def prepare_claim(claim_id: str, user: Admin):
    # Always revalidate; cached API idempotency responses must not bypass revocation.
    engine = database()
    try:
        with transaction(engine, user.id) as conn:
            return safe(lambda: prepare(conn, user, claim_id))
    finally:
        engine.dispose()


@router.post("/{claim_id}/ingest")
def ingest_claim(claim_id: str, body: IngestBody, user: Admin):
    engine = database()
    try:
        with transaction(engine, user.id) as conn:
            return safe(lambda: ingest(conn, user, claim_id, body))
    finally:
        engine.dispose()


@router.get("/canonical")
def canonical_snapshot(
    user: Admin, as_of: datetime | None = None, limit: int = Query(default=100, ge=1, le=500)
):
    engine = database()
    try:
        with engine.connect() as conn:
            return safe(lambda: snapshot(conn, as_of or datetime.now(UTC), limit))
    finally:
        engine.dispose()
