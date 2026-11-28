"""Bounded source-window activity assessment; editorial priority is not impact size."""

import re

from engine.editorial_priority import exclusion, scoped
from engine.operating_developments import assess as operating_development
from engine.source_sentences import sentences


def assess(item, links, policy):
    windows: list[dict] = []
    editorial, typed_signals = [], []
    audit = {"matched_links": len(links), "context_only_links": 0,
             "scoped_assertion_links": 0, "eligible_windows": 0}
    for link in links:
        matches = link.get("matches", [])
        audit["scoped_assertion_links"] += int(any(m.get("assertion_scope") for m in matches))
        decision = scoped(item, matches)
        if decision is not None:
            editorial.append(decision)
            if decision["eligible"]:
                typed_signals.append({**decision["source_window"], "driver_direction": "UNKNOWN",
                    "entity_resolved": bool(link.get("entity_context")),
                    "phase": decision["phase"], "event_type": decision["event_type"],
                    "source_duration": None, "event_horizon": "UNKNOWN", "horizon_basis": "NOT_ESTIMATED",
                    "editorial_basis": decision["reason"]})
        if matches and all(m.get("context_only") for m in matches):
            audit["context_only_links"] += 1
            continue
        if decision is not None:
            continue  # Rejected scope cannot be rescued by a generic change word.
        for field in ("title", "summary"):
            spans = [m for m in matches if m["field"] == field]
            if not spans:
                continue
            text = item["headline"] if field == "title" else item["excerpt"]
            start, end = min(m["start"] for m in spans), max(m["end"] for m in spans)
            for sentence in sentences(text):
                if sentence.start() <= start and end <= sentence.end():
                    windows.append(
                        {
                            "field": field,
                            "start": sentence.start(),
                            "end": sentence.end(),
                            "text": sentence.group(),
                            "entity_resolved": bool(link.get("entity_context")),
                            **({"activity_assertion": spans[0]["activity_assertion"]}
                               if spans[0].get("activity_assertion") else {}),
                        }
                    )
    audit["eligible_windows"] = len(windows)
    signals = list(typed_signals)
    for window in windows:
        text = window["text"].lower()
        if reason := exclusion(text):
            editorial.append({"eligible": False, "reason": reason, "source_window": window})
            continue
        if re.search(r"\b(no|not|never|without|unchanged|denied)\b", text):
            editorial.append({"eligible": False, "reason": "NEGATED_OR_UNCHANGED_WINDOW", "source_window": window})
            continue
        development = operating_development(window, policy)
        editorial.append(development)
        if not development["eligible"]:
            continue
        duration = re.search(r"\bfor (\d{1,3}) (days?|weeks?|months?|years?)\b", text)
        event_horizon = "UNKNOWN"
        if duration:
            amount, unit = int(duration[1]), duration[2].rstrip("s")
            short, medium = {"day": (90, 365), "week": (13, 52), "month": (3, 12), "year": (0, 1)}[
                unit
            ]
            event_horizon = "SHORT" if amount <= short else "MEDIUM" if amount <= medium else "LONG"
        signals.append(
            {
                **window,
                "driver_direction": development["driver_direction"],
                "phase": development["phase"],
                "event_type": development["event_type"],
                "editorial_basis": development["reason"],
                "operating_development": development,
                "source_duration": duration[0] if duration else None,
                "event_horizon": event_horizon,
                "horizon_basis": "SOURCE_DURATION_EDITORIAL_BIN_NOT_COMPANY_IMPACT_LAG",
            }
        )
    resolved = any(link.get("entity_context") for link in links)
    event_resolved = any(signal.get("entity_resolved") for signal in signals)
    sponsored = bool(
        re.search(r"\b(sponsored|advertorial|partner content)\b", item["headline"], re.I)
    )
    weights = policy["priority_weights"]
    score = (
        weights["sourced_path"]
        + weights["resolved_entity"] * event_resolved
        + weights["concrete_change"] * bool(signals)
        - weights["sponsored_penalty"] * sponsored
    )
    tier = (
        "COMPANY_CONTEXT"
        if event_resolved
        else "SECTOR_CHANGE_CONTEXT"
        if signals
        else "BACKGROUND_THEME"
    )
    if sponsored:
        tier = "SPONSORED_RESEARCH"
    return {
        "tier": tier,
        "editorial_score": score,
        "score_basis": "UNCALIBRATED_RELEVANCE_NOT_FINANCIAL_IMPACT",
        "signals": signals,
        "editorial_decisions": editorial,
        "resolved_entity": resolved,
        "event_entity_resolved": event_resolved,
        "priority_audit": {**audit, "concrete_signals": len(signals),
                           "weights_changed": False, "delivery": "disabled"},
        "sponsored": sponsored,
        "direction": "UNKNOWN",
        "horizon": "UNKNOWN",
        "reason": "Resolved relationship entity"
        if event_resolved
        else "Scoped source development within narrative; financial effect unknown"
        if typed_signals
        else "Source action and operating object; financial effect unknown"
        if signals
        else "Related entity without a qualifying development" if resolved
        else "Topic match without a specific change assertion",
    }
