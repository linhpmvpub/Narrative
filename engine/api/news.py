"""Authenticated shared public-source news inbox; never exposes user labels or secrets."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from engine.api.accounts import Principal, principal
from engine.db import database
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
                "first_seen_at": row["first_seen_at"],
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
        return {"items": [dict(r) for r in rows]}
    finally:
        engine.dispose()
