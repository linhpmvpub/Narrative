import re
from collections import Counter
from datetime import datetime

from engine.adapters.fixture import FixtureEvent


def compare_baselines(records: list[FixtureEvent], replay_result: dict, as_of: datetime) -> dict:
    corpus = [r for r in records if max(r.available_at, r.published_at, r.first_seen_at) <= as_of]
    corpus_ids = {r.event_id for r in corpus}
    pairs = [
        r["decision_trace"]
        for r in replay_result["results"]
        if r["decision_trace"]["event_id"] in corpus_ids
    ]
    b0: list[list[str]] = []
    tickers = {
        "N01": "MU",
        "N02": "MU",
        "N03": "NVDA",
        "N04": "NVDA",
        "N05": "AMD",
        "N06": "AMD",
        "N07": "DELL",
        "N08": "DELL",
        "N09": "SNDK",
        "N10": "SNDK",
    }
    for record in corpus:
        if (as_of - record.available_at).total_seconds() <= 30 * 86400:
            b0.extend(
                [record.event_id, n]
                for n, ticker in tickers.items()
                if re.search(r"\b" + ticker + r"\b", record.headline_factual, re.IGNORECASE)
            )
    return {
        "is_synthetic": True,
        "as_of": as_of.isoformat(),
        "corpus_input_ids": sorted(corpus_ids),
        "corpus_count": len(corpus),
        "pair_count": len(pairs),
        "B0": {
            "method": "ticker keyword in headline plus 30-day recency, no hard gates",
            "matched_pairs": b0,
            "matched_count": len(b0),
        },
        "B1": {
            "status": "UNAVAILABLE",
            "reason": "LLM_MODE=none; no substitute baseline presented as LLM output",
            "matched_count": None,
        },
        "V0": {
            "verified_path_pairs": sum(p["selected_path"] is not None for p in pairs),
            "decisions": dict(Counter(p["decision"] for p in pairs)),
        },
        "historical_evaluation": "PENDING genuine source-backed human labels",
        "precision": None,
        "recall": None,
        "note": "Matching counts compare routing coverage only, not precision or proven investment relevance.",
    }
