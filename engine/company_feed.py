"""Primary company news feed. Narrative projection is not a dependency."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from engine.company_assessment import project
from engine.company_profiles import available_bundles
from engine.core_decisions import POLICY
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_sources
from engine.profile_news import candidate_feed


def feed(conn, data, profile_root, *, article_feed_root=None):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    current = available_bundles(root=profile_root)
    pins = {p["id"]: p["sha256"] for p in data["profiles"]}
    matching = {b.id for b in current["items"] if pins.get(b.id) == digest(b.model_dump(mode="json"))}
    result = candidate_feed(conn, profile_root=profile_root, limit=policy["scan_limit"],
                            card_limit=policy["card_limit"], include_company=True, include_narratives=False)
    sources = {s["id"]: s for s in conn.execute(select(news_sources)).mappings()}
    now = datetime.now(UTC)
    checked = None
    full_cards = []
    body_urls = set()
    if article_feed_root is not None:
        from engine.adapters.news import canonical_url
        from engine.article_feed import current_selections
        from engine.company_articles import candidates

        checked = current_selections(conn, article_feed_root)
        if Path(checked["state"]["profiles"]).resolve() != Path(profile_root).resolve():
            raise ValueError("Reviewed article registry differs from company workspace")
        body_urls = {canonical_url(e["selection"]["revision"]["payload"]["url"])
                     for e in checked["state"]["entries"]}
        full_cards = candidates(checked["selections"], [b for b in current["items"] if b.id in matching],
                                now, checked["state"]["articles"])
    cards = []
    for item in [*result.get("company_items", []), *full_cards]:
        full_body = item.get("source_representation") == "REVIEWED_COMPLETE_BODY"
        if body_urls and not full_body and canonical_url(item["url"]) in body_urls:
            continue  # Changed/stale complete bodies cannot fall back to an old RSS excerpt.
        if item["profile_id"] not in matching or (not full_body and not all(
            r["capture_proof"] == "RAW_RSS_MATCH_NOT_FACT_VERIFICATION"
            and sources[r["source_id"]]["last_success"] is not None
            and 0 <= (now - utc(sources[r["source_id"]]["last_success"])).total_seconds()
            <= policy["max_source_age_seconds"] for r in item["news_revisions"]
        )):
            continue
        card = project(item)
        ids = {card["profile_id"] + "/" + e["id"] for d in card["company_discovery"] for e in d["path"]}
        card["exposure_parameters"] = [f for f in data.get("exposure_facts", []) if f["relation_id"] in ids]
        card["financial_context"] = [f for f in data.get("financial_context", []) if f["profile_id"] == card["profile_id"]]
        cards.append(card)
    if checked and (Path(article_feed_root) / "current.json").read_bytes() != checked["raw"]:
        raise ValueError("Article source state changed during company projection")
    if [digest(b.model_dump(mode="json")) for b in available_bundles(root=profile_root)["items"]] != [
        digest(b.model_dump(mode="json")) for b in current["items"]
    ]:
        raise ValueError("Profiles changed during company projection")
    cards.sort(key=lambda c: (c["assessment"]["rank"], c["published_at"], c["id"]), reverse=True)
    return {"items": [c for c in cards if c["assessment"]["priority"]],
            "background": [c for c in cards if not c["assessment"]["priority"]],
            "company_context": [], "examined": result["examined"], "withheld": result["withheld"],
            "truncated": result["truncated"], "pinned_profiles": len(matching),
            "profiles_without_company_scope": sorted(b.id for b in current["items"] if not b.company_discovery),
            "delivery": "disabled", "mode": "COMPANY_INTELLIGENCE_V1",
            "reviewed_articles": len(checked["selections"]) if checked else 0,
            "held_reviewed_articles": len(checked["blocked_urls"]) if checked else 0,
            "ranking": "ORDINAL_COMPANY_ATTENTION_NOT_FINANCIAL_IMPACT", "narratives_used": False}
