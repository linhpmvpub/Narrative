"""High-recall local discovery and coverage accounting, never economic claims."""

import re
from collections import Counter
from datetime import UTC, datetime

from engine.ingestion.contracts import digest

EVENTS = {
    "shipments": r"\b(shipments?|shipping|deliveries|delivered)\b",
    "capacity": r"\b(capacity|production|fab|factory|packaging)\b",
    "demand": r"\b(demand|orders?|backlog|sales)\b",
    "input_prices": r"\b(prices?|costs?|pricing)\b",
    "funding": r"\b(financing|funding|loan|credit|debt|capex|capital expenditure)\b",
    "regulation": r"\b(license|permit|export controls?|tariffs?|sanctions?|regulation)\b",
    "disruption": r"\b(shortage|outage|earthquake|flood|typhoon|strike|closure|disruption)\b",
    "earnings": r"\b(earnings|revenue|margin|quarterly results)\b",
    "correction": r"\b(corrected|correction|withdrawn|retracted|restated|amended)\b",
    "insider": r"\b(insider|form 4|beneficial ownership)\b",
}
FUTURE = re.compile(r"\b(may|might|could|will|expects?|plans?|forecast|outlook|if)\b", re.I)
NEGATIVE = re.compile(r"\b(not|no|never|cancelled|canceled|withdrawn|halted)\b", re.I)


def literal(term, text):
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I)


def profile_plan(registry, policy):
    companies, lexicon = [], []
    at = datetime.now(UTC)
    for ticker in policy["tickers"]:
        choices = [b for b in registry["items"] if b.ticker == ticker and b.factor_bindings]
        bundle = max(choices, key=lambda b: b.available_at) if choices else None
        for name in policy["company_names"][ticker]:
            lexicon.append({"ticker": ticker, "term": name, "basis": "PUBLIC_COMPANY_NAME"})
        components = {c.key: c.status for c in bundle.components} if bundle else {}
        coverage = {k: components.get(k, "MISSING") for k in policy["required_profile_components"]}
        drivers = sum(
            v == "SOURCED" for k, v in coverage.items() if k not in {"identity", "products"}
        )
        missing = [k for k, v in coverage.items() if v == "MISSING"]
        ready = bool(
            bundle
            and not missing
            and coverage["identity"] == coverage["products"] == "SOURCED"
            and drivers >= 3
        )
        companies.append(
            {
                "ticker": ticker,
                "profile_id": bundle.id if bundle else None,
                "profile_sha256": digest(bundle.model_dump(mode="json")) if bundle else None,
                "components": coverage,
                "sourced_driver_areas": drivers,
                "ready": ready,
                "missing_components": missing,
                "review_required": True,
            }
        )
        if bundle:
            for ref in bundle.entity_references:
                if ref.status != "SOURCE_BACKED" or not ref.reviewed_at <= at < ref.review_until:
                    continue
                for name in ref.names:
                    if len(name) >= 4:
                        lexicon.append(
                            {
                                "ticker": ticker,
                                "term": name,
                                "basis": "PROFILE_ENTITY_MENTION",
                                "profile_id": bundle.id,
                                "reference_id": ref.id,
                            }
                        )
            for binding in bundle.factor_bindings:
                if not binding.enabled or not binding.reviewed_at <= at < binding.review_until:
                    continue
                for name in binding.topic_terms:
                    if len(name) >= 4:
                        lexicon.append(
                            {
                                "ticker": ticker,
                                "term": name,
                                "basis": "PROFILE_TOPIC_MENTION",
                                "profile_id": bundle.id,
                                "binding_id": binding.id,
                            }
                        )
    return {
        "companies": companies,
        "lexicon": lexicon,
        "profiles_complete": all(c["ready"] for c in companies)
        and not registry.get("withheld")
        and not registry.get("truncated")
        and registry["enabled"],
        "discovery_is_not_exposure": True,
        "delivery": "disabled",
    }


def discover(payload, plan, policy):
    text = payload.get("title", "") + "\n" + payload.get("summary", "")
    mentions = []
    for entry in plan["lexicon"]:
        match = literal(entry["term"], text)
        if match:
            mentions.append(
                {**entry, "start": match.start(), "end": match.end(), "text": match.group()}
            )
    # Only exact uppercase/cashtag symbols; never lowercase common words such as 'mu'.
    for ticker in policy["tickers"]:
        match = re.search(r"(?<!\w)\$?" + ticker + r"(?!\w)", text)
        if match:
            mentions.append(
                {
                    "ticker": ticker,
                    "term": ticker,
                    "basis": "TICKER_MENTION_ONLY",
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(),
                }
            )
    families = [
        family
        for family, terms in policy["family_terms"].items()
        if any(literal(t, text) for t in terms)
    ]
    signals = []
    if not payload.get("filing_metadata_only"):
        for kind, pattern in EVENTS.items():
            match = re.search(pattern, text, re.I)
            if match:
                context = text[max(0, match.start() - 120) : match.end() + 180]
                flags = []
                if FUTURE.search(context):
                    flags.append("FORWARD_OR_CONDITIONAL")
                if NEGATIVE.search(context):
                    flags.append("NEGATED_OR_CANCELLED")
                if re.search(r'["“”]', context):
                    flags.append("QUOTED_OR_MIXED_ATTRIBUTION")
                signals.append(
                    {
                        "type": kind,
                        "start": match.start(),
                        "end": match.end(),
                        "text": match.group(),
                        "flags": flags,
                        "status": "UNVERIFIED_TEXT_SIGNAL",
                    }
                )
    return {
        "candidate_companies": sorted({m["ticker"] for m in mentions}),
        "mentions": mentions,
        "families": families,
        "event_signals": signals,
        "filing_metadata_only": bool(payload.get("filing_metadata_only")),
        "review_required": True,
        "graph_eligible": False,
        "impact": "UNKNOWN",
        "delivery": "disabled",
    }


def prioritize(rows, plan, policy, limit=50):
    """Round robin by company/theme; keep exploratory items rather than ticker-only filtering."""
    if not 1 <= limit <= 200:
        raise ValueError("Review queue budget must be 1..200")
    buckets: dict[str, list] = {}
    seen_articles = set()
    for row in rows:
        if row["article_key"] in seen_articles:
            continue
        seen_articles.add(row["article_key"])
        result = discover(row["payload"], plan, policy)
        item = {
            "revision_id": row["revision_id"],
            "item_id": row["item_id"],
            "version": row["version"],
            "article_key": row["article_key"],
            "payload_sha256": digest(row["payload"]),
            "capture_sha256": row["capture_sha256"],
            "source_id": row["source_id"],
            "url": row["payload"]["url"],
            "discovery": result,
        }
        keys = (
            result["candidate_companies"]
            or ["theme:" + f for f in result["families"]]
            or ["unclassified"]
        )
        for key in keys:
            buckets.setdefault(key, []).append(item)
    output: list[dict] = []
    picked: set[str] = set()
    while any(buckets.values()) and len(output) < limit:
        for bucket in buckets.values():
            while bucket:
                item = bucket.pop(0)
                if item["article_key"] not in picked:
                    picked.add(item["article_key"])
                    output.append(item)
                    break
            if len(output) >= limit:
                break
    return output


def coverage(rows, plan, policy):
    companies: Counter[str] = Counter()
    direct: Counter[str] = Counter()
    families: Counter[str] = Counter()
    events: Counter[str] = Counter()
    articles = set()
    for row in rows:
        if row["article_key"] in articles:
            continue
        articles.add(row["article_key"])
        d = discover(row["payload"], plan, policy)
        companies.update(d["candidate_companies"])
        direct.update(
            {
                m["ticker"]
                for m in d["mentions"]
                if m["basis"] in {"PUBLIC_COMPANY_NAME", "TICKER_MENTION_ONLY"}
            }
        )
        families.update(d["families"])
        events.update(x["type"] for x in d["event_signals"])
    return {
        "unique_article_urls": len(articles),
        "company_discovery_candidates": dict(companies),
        "direct_company_mentions": dict(direct),
        "family_mentions": dict(families),
        "candidate_event_signals": dict(events),
        "missing_company_mentions": [t for t in policy["tickers"] if not companies[t]],
        "missing_family_mentions": [f for f in policy["narrative_families"] if not families[f]],
        "not_relevance_recall": True,
    }
