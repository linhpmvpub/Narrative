"""Bounded source-window activity assessment; editorial priority is not impact size."""

import re


def assess(item, links, policy):
    windows: list[dict] = []
    for link in links:
        matches = link.get("matches", [])
        if matches and all(m.get("context_only") for m in matches):
            continue
        for field in ("title", "summary"):
            spans = [m for m in matches if m["field"] == field]
            if not spans:
                continue
            text = item["headline"] if field == "title" else item["excerpt"]
            start, end = min(m["start"] for m in spans), max(m["end"] for m in spans)
            for sentence in re.finditer(r"[^.!?;\n]+", text):
                if sentence.start() <= start and end <= sentence.end():
                    windows.append(
                        {
                            "field": field,
                            "start": sentence.start(),
                            "end": sentence.end(),
                            "text": sentence.group(),
                            **({"activity_assertion": spans[0]["activity_assertion"]}
                               if spans[0].get("activity_assertion") else {}),
                        }
                    )
    signals = []
    for window in windows:
        text = window["text"].lower()
        assertion = window.get("activity_assertion")
        if assertion:
            signals.append({**window, "driver_direction": "UNKNOWN",
                            "phase": assertion["phase"], "source_duration": None,
                            "event_horizon": "UNKNOWN", "horizon_basis": "NOT_ESTIMATED"})
            continue
        if re.search(r"\b(no|not|never|without|unchanged|denied)\b", text):
            continue
        directions = [
            direction
            for direction, terms in policy["change_terms"].items()
            if any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in terms)
        ]
        if len(directions) != 1:
            continue
        phase = (
            "FORWARD_LOOKING"
            if any(re.search(r"\b" + word + r"\b", text) for word in policy["phase_terms"])
            else "SOURCE_REPORTED_CHANGE"
        )
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
                "driver_direction": directions[0],
                "phase": phase,
                "source_duration": duration[0] if duration else None,
                "event_horizon": event_horizon,
                "horizon_basis": "SOURCE_DURATION_EDITORIAL_BIN_NOT_COMPANY_IMPACT_LAG",
            }
        )
    resolved = any(link.get("entity_context") for link in links)
    sponsored = bool(
        re.search(r"\b(sponsored|advertorial|partner content)\b", item["headline"], re.I)
    )
    weights = policy["priority_weights"]
    score = (
        weights["sourced_path"]
        + weights["resolved_entity"] * resolved
        + weights["concrete_change"] * bool(signals)
        - weights["sponsored_penalty"] * sponsored
    )
    tier = (
        "COMPANY_CONTEXT"
        if resolved
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
        "sponsored": sponsored,
        "direction": "UNKNOWN",
        "horizon": "UNKNOWN",
        "reason": "Resolved relationship entity"
        if resolved
        else "Same-window economic change language"
        if signals
        else "Topic match without a specific change assertion",
    }
