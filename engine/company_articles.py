"""Company cards from current, explicitly reviewed full article selections."""

from datetime import datetime

from engine.company_discovery import source_decisions
from engine.ingestion.contracts import digest


def candidates(selections, bundles, at, article_root):
    cards = []
    seen = set()
    for selection in selections:
        article = selection["revision"]["payload"]
        if article["url"] in seen:
            raise ValueError("Duplicate complete-body selection")
        seen.add(article["url"])
        age = (at - datetime.fromisoformat(article["published_at"])).total_seconds() / 86400
        for bundle in bundles:
            hits = [h for h in source_decisions({"article": article, "source_observation": selection},
                    bundle, at, article_root=article_root) if 0 <= age <= h["max_news_age_days"]]
            if not hits:
                continue
            best = next((h for h in hits if h.get("body_unit")), hits[0])
            excerpt = best["source_unit"].get("summary") or article.get("summary", "")
            cards.append({"id": digest([article["url"], bundle.id]), "ticker": bundle.ticker,
                "profile_id": bundle.id, "profile_version": bundle.version,
                "headline": article["title"], "excerpt": excerpt, "url": article["url"],
                "published_at": article["published_at"], "company_discovery": hits,
                "news_revisions": [], "source_representation": "REVIEWED_COMPLETE_BODY",
                "body_evidence": {"packet_sha256": selection["packet_sha256"],
                                  "selection_sha256": digest(selection),
                                  "revision_id": selection["revision"]["id"]},
                "revision_sha256": digest([selection, bundle.version, hits]),
                "verification": "CURRENT_REVIEWED_BODY_NOT_FACT_VERIFICATION",
                "narratives": [], "links": [], "mechanisms": {}, "direction": "UNKNOWN",
                "financial_magnitude": "UNKNOWN", "horizon": "UNKNOWN", "delivery": "disabled",
                "graph_eligible": False,
                "decision_trace": ["Current reviewed complete body with exact source spans",
                                   "Company scope independent of narratives", "No canonical fact or financial effect inferred"]})
    return cards
