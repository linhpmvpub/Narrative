"""Authenticated shared public-source news inbox; never exposes user labels or secrets."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy import select

from engine.api.accounts import Principal, principal, write
from engine.article_preferences import Preferences
from engine.db import database
from engine.models.contracts import utc
from engine.models.schema_v13 import news_items, news_revisions
from engine.news import status

router = APIRouter(prefix="/api/v0/news", dependencies=[Depends(principal)])


@router.get("/sources")
def source_status():
    engine = database()
    try:
        return {"items": status(engine), "delivery": "disabled", "mode": "NEAR_REAL_TIME_POLLING"}
    finally:
        engine.dispose()


@router.get("")
def feed(
    user: Annotated[Principal, Depends(principal)],
    limit: int = Query(100, ge=1, le=200),
    source: str | None = None,
):
    engine = database()
    try:
        query = select(news_items).order_by(
            news_items.c.payload["published_at"].as_string().desc().nullslast(),
            news_items.c.first_seen_at.desc(),
            news_items.c.id,
        )
        if source:
            query = query.where(news_items.c.source_id == source)
        with engine.connect() as conn:
            rows = conn.execute(query.limit(limit)).mappings().all()
        groups: dict[str, dict] = {}
        for row in rows:
            key = row["article_key"]
            if key in groups:
                groups[key]["also_seen_in"].append(row["source_id"])
                continue
            groups[key] = {
                "id": row["id"],
                "source_id": row["source_id"],
                "version": row["version"],
                "first_seen_at": utc(row["first_seen_at"]),
                "also_seen_in": [],
                **row["payload"],
            }
        return {
            "items": list(groups.values()),
            "scanned": len(rows),
            "limit": limit,
            "delivery": "disabled",
            "graph_modified": False,
            "deduplication": "Same normalized article URL only; independent stories are not merged",
        }
    finally:
        engine.dispose()


@router.get("/clusters")
def clusters():
    from engine.news_clusters import analyze

    engine = database()
    try:
        return analyze(engine)
    finally:
        engine.dispose()


@router.get("/{item_id}/history")
def history(item_id: str):
    engine = database()
    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    select(news_revisions)
                    .where(news_revisions.c.item_id == item_id)
                    .order_by(news_revisions.c.version)
                    .limit(100)
                )
                .mappings()
                .all()
            )
        if not rows:
            raise HTTPException(404, "News item not found")
        return {"items": [{**dict(r), "received_at": utc(r["received_at"])} for r in rows]}
    finally:
        engine.dispose()


@router.get("/reviewed")
def reviewed(limit: int = Query(100, ge=1, le=500)):
    from engine.news_feed import reviewed_feed

    engine = database()
    try:
        with engine.connect() as conn:
            return reviewed_feed(conn, limit)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    finally:
        engine.dispose()


@router.get("/extractions")
def extractions():
    from engine.news_extraction_feed import extraction_feed

    engine = database()
    try:
        with engine.connect() as conn:
            return extraction_feed(conn)
    finally:
        engine.dispose()


@router.get("/impact-cases")
def impact_cases():
    from engine.impact_cases import case_feed

    return case_feed()


@router.get("/profiles")
def company_profiles(as_of: AwareDatetime | None = None):
    from engine.company_profiles import feed

    return feed(as_of)


@router.get("/profile-framework")
def company_profile_framework():
    from engine.company_profiles import framework

    return framework()


@router.get("/profile-rss")
def profile_rss(as_of: AwareDatetime | None = None):
    from engine.profile_news import candidate_feed

    engine = database()
    try:
        with engine.connect() as conn:
            return candidate_feed(conn, as_of)
    finally:
        engine.dispose()


@router.get("/profile-articles")
def profile_articles(user: Annotated[Principal, Depends(principal)],
                     ticker: str | None = None, narrative: str | None = None):
    from engine.article_feed import feed
    from engine.article_preferences import personalize, read

    account_db = database()
    try:
        with account_db.connect() as conn:
            preferences = read(conn, user)
    finally:
        account_db.dispose()
    engine = database(os.getenv("ARTICLE_FEED_DATABASE_URL") or None)
    try:
        with engine.connect() as conn:
            return personalize(feed(conn, ticker=ticker, narrative=narrative), preferences)
    finally:
        engine.dispose()


@router.get("/reviewed-roles")
def reviewed_roles():
    from engine.reviewed_role_feed import role_feed

    engine = database()
    try:
        with engine.connect() as conn:
            return role_feed(conn)
    finally:
        engine.dispose()


@router.get("/reviewed-operations")
def reviewed_operations():
    from engine.reviewed_role_feed import role_feed

    engine = database()
    try:
        with engine.connect() as conn:
            return role_feed(conn, operating=True)
    finally:
        engine.dispose()


@router.get("/article-preferences")
def article_preferences(user: Annotated[Principal, Depends(principal)]):
    from engine.article_preferences import catalog, read
    engine = database()
    try:
        with engine.connect() as conn:
            return {**read(conn, user), "catalog": catalog()}
    finally:
        engine.dispose()


@router.put("/article-preferences")
def save_article_preferences(body: Preferences, user: Annotated[Principal, Depends(principal)],
                             key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
    from engine.article_preferences import save
    return write(user, "article-preferences", key, body.model_dump(), lambda conn: save(conn, user, body))


@router.get("/core")
def core_workspace(include_synthetic: bool = False):
    from engine.core_workspace import build

    manifest = os.environ.get("CORE_WORKSPACE_MANIFEST")
    if not manifest:
        raise HTTPException(503, "Local core workspace is not configured")
    engine = database(os.getenv("CORE_WORKSPACE_DATABASE_URL") or None)
    try:
        with engine.connect() as conn:
            return build(manifest, include_synthetic=include_synthetic, news_conn=conn)
    except (ValueError, OSError, KeyError):
        raise HTTPException(503, "Core evidence unavailable; refresh after local review") from None
    finally:
        engine.dispose()
