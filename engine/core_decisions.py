"""Evidence-bound RSS context decisions, distinct from quantified price alerts."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from engine.company_profiles import available_bundles
from engine.core_activity import assess
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_sources
from engine.profile_news import candidate_feed

POLICY = Path(__file__).resolve().parents[1] / "config/core-decisions-v1.json"


def project(items, policy):
    grouped: dict = {}
    for item in items:
        links = [
            link
            for link in item["links"]
            if not link["paths_truncated"] and len(link["path"]) <= policy["max_hops"]
        ]
        if not links:
            continue
        key = digest([item["url"], item["profile_id"]])
        card = grouped.setdefault(
            key,
            {
                "id": key,
                "ticker": item["ticker"],
                "profile_id": item["profile_id"],
                "headline": item["headline"],
                "excerpt": item["excerpt"],
                "url": item["url"],
                "published_at": item["published_at"],
                "news_revisions": item["news_revisions"],
                "narratives": [],
                "links": [],
                "mechanisms": {},
                "verification": item["verification"],
                "direction": "UNKNOWN",
                "financial_magnitude": "UNKNOWN",
                "horizon": "UNKNOWN",
                "priority": "RELATED_CONTEXT_NOT_ALERT",
                "delivery": "disabled",
                "decision_trace": list(item["decision_trace"]),
                "policy_sha256": digest(policy),
            },
        )
        narrative = {"id": item["narrative_id"], "title": item["narrative_title"]}
        if narrative not in card["narratives"]:
            card["narratives"].append(narrative)
        for link in links:
            if link not in card["links"]:
                card["links"].append(link)
            for edge in link["path"]:
                name = policy["relations"].get(edge["type"])
                if name:
                    card["mechanisms"][name] = policy["groups"][name]
        card["assessment"] = assess(item, card["links"], policy)
        card["priority"] = card["assessment"]["tier"]
        card["revision_sha256"] = digest(
            [card["news_revisions"], card["links"], card["narratives"]]
        )
    return sorted(
        grouped.values(),
        key=lambda c: (c["assessment"]["editorial_score"], c["published_at"], c["id"]),
        reverse=True,
    )


def feed(conn, data, profile_root):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if policy["delivery"] != "disabled" or policy["schema"] != "CORE_DECISION_V1":
        raise ValueError("Invalid core policy")
    current = available_bundles(root=profile_root)
    pinned = {p["id"]: p["sha256"] for p in data["profiles"]}
    matching = {
        b.id for b in current["items"] if pinned.get(b.id) == digest(b.model_dump(mode="json"))
    }
    result = candidate_feed(
        conn,
        profile_root=profile_root,
        limit=policy["scan_limit"],
        card_limit=policy["card_limit"],
        include_company=True,
    )
    now = datetime.now(UTC)
    sources = {s["id"]: s for s in conn.execute(select(news_sources)).mappings()}

    def eligible(item):
        if item["profile_id"] not in matching:
            return False
        return all(
            r["capture_proof"] == "RAW_RSS_MATCH_NOT_FACT_VERIFICATION"
            and sources[r["source_id"]]["last_success"] is not None
            and 0
            <= (now - utc(sources[r["source_id"]]["last_success"])).total_seconds()
            <= policy["max_source_age_seconds"]
            for r in item["news_revisions"]
        )

    selected = [item for item in result["items"] if eligible(item)]
    company = [item for item in result.get("company_items", []) if eligible(item)]
    after = available_bundles(root=profile_root)
    if [digest(b.model_dump(mode="json")) for b in after["items"]] != [
        digest(b.model_dump(mode="json")) for b in current["items"]
    ]:
        raise ValueError("Profiles changed during projection")
    cards = project(selected, policy)
    discoveries = {c["id"]: c for c in company}
    assigned = {c["id"] for c in cards}
    for card in cards:
        if card["id"] in discoveries:
            card["company_discovery"] = discoveries[card["id"]]["company_discovery"]
            card["revision_sha256"] = digest(
                [card["revision_sha256"], discoveries[card["id"]]["revision_sha256"]]
            )
        relation_ids = {
            card["profile_id"] + "/" + edge["id"] for link in card["links"] for edge in link["path"]
        }
        card["exposure_parameters"] = [
            f for f in data.get("exposure_facts", []) if f["relation_id"] in relation_ids
        ]
        card["financial_context"] = [
            f for f in data.get("financial_context", []) if f["profile_id"] == card["profile_id"]
        ]
    return {
        "company_context": sorted(
            [c for c in company if c["id"] not in assigned],
            key=lambda c: (c["published_at"], c["id"]),
            reverse=True,
        ),
        "items": [
            c for c in cards if c["priority"] not in {"BACKGROUND_THEME", "SPONSORED_RESEARCH"}
        ],
        "background": [
            c for c in cards if c["priority"] in {"BACKGROUND_THEME", "SPONSORED_RESEARCH"}
        ],
        "examined": result["examined"],
        "withheld": result["withheld"],
        "truncated": result["truncated"],
        "pinned_profiles": len(matching),
        "delivery": "disabled",
        "ranking": policy["ranking"],
        "mode": "RSS_CONTEXT_NOT_VERIFIED_IMPACT",
    }
