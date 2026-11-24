"""Personal relevance ordering never changes source/graph eligibility."""
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from engine.models.schema_v17 import article_preferences as table

DEFAULT = {"tickers": [], "narratives": [], "following_only": False, "include_archive": True}


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=0)
    tickers: list[str] = Field(max_length=10)
    narratives: list[str] = Field(max_length=40)
    following_only: bool = False
    include_archive: bool = True


def catalog():
    from engine.article_feed import root_dir
    from engine.company_profiles import available_bundles

    try:
        state = json.loads((root_dir() / "current.json").read_text(encoding="utf-8"))
        registry = available_bundles(root=state["profiles"])
        if not registry["enabled"] or registry.get("withheld") or registry.get("truncated"):
            raise ValueError("Profile catalog unavailable")
        return {"available": True, "tickers": sorted({b.ticker for b in registry["items"]}),
                "narratives": [{"id": b.id + ":" + n.id, "title": n.title, "ticker": b.ticker}
                               for b in registry["items"] for n in b.narratives]}
    except (OSError, ValueError, KeyError, TypeError):
        return {"available": False, "tickers": [], "narratives": []}


def read(conn, user):
    row = conn.execute(select(table).where(table.c.user_id == user.id)).mappings().first()
    return {"version": row["version"] if row else 0,
            **(row["payload"] if row else DEFAULT), "delivery": "disabled"}


def save(conn, user, body):
    current = read(conn, user)
    if current["version"] != body.expected_version:
        raise HTTPException(409, "Preferences changed; reload before saving")
    choices = catalog()
    allowed_tickers = set(choices["tickers"]) | set(current["tickers"])
    allowed_narratives = {n["id"] for n in choices["narratives"]} | set(current["narratives"])
    if not set(body.tickers) <= allowed_tickers or not set(body.narratives) <= allowed_narratives:
        raise HTTPException(422, "Choose available company/narrative identifiers")
    payload = {"tickers": sorted(set(body.tickers)), "narratives": sorted(set(body.narratives)),
               "following_only": body.following_only, "include_archive": body.include_archive}
    values = {"payload": payload, "version": current["version"] + 1, "updated_at": datetime.now(UTC)}
    if current["version"]:
        conn.execute(table.update().where(table.c.user_id == user.id).values(**values))
    else:
        conn.execute(table.insert().values(user_id=user.id, **values))
    return {"version": values["version"], **payload, "delivery": "disabled"}


def personalize(result, preferences):
    cards = []
    for original in result["items"]:
        card = dict(original)
        key = card["profile_id"] + ":" + card["narrative_id"]
        priority = 2 if key in preferences["narratives"] else 1 if card["ticker"] in preferences["tickers"] else 0
        if preferences["following_only"] and not priority:
            continue
        if not preferences["include_archive"] and card["freshness"] == "ARCHIVE_CONTEXT":
            continue
        card["personal_priority"] = priority
        card["priority_reason"] = ["DISCOVERY", "COMPANY_FOLLOWED", "NARRATIVE_FOLLOWED"][priority]
        cards.append(card)
    cards.sort(key=lambda c: (c["personal_priority"], c["freshness"] == "WITHIN_RULE_WINDOW",
                             c["coverage"] == "COMPANY_MENTION_NOT_VERIFIED_IMPACT",
                             datetime.fromisoformat(c["published_at"]).astimezone(UTC),
                             c["id"]), reverse=True)
    return {**result, "items": cards, "preferences_version": preferences["version"],
            "ranking_basis": "PERSONAL_RELEVANCE_NOT_FINANCIAL_IMPORTANCE"}
