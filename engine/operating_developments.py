"""Bounded action/operating-object evidence for legacy editorial selection.

This does not change relevance, establish an actor's identity, or create facts.
Descriptions, purposes and demonstrations are not realized operating changes.
"""

import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def policy():
    return json.loads((Path(__file__).resolve().parent.parent /
                       "config/operating-developments-v1.json").read_text(encoding="utf-8"))


def span(text, start, end):
    return {"start": start, "end": end, "text": text[start:end]}


def literal(terms, text):
    return re.search(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")(?!\w)", text, re.I)


def tail(text, start):
    end = min(len(text), start + policy()["object_bound_chars"])
    stop = re.search(policy()["object_boundary"], text[start:end], re.I)
    return start + stop.start() if stop else end


def prefix(text, end):
    boundaries = list(re.finditer(policy()["clause_boundary"], text[:end], re.I))
    start = boundaries[-1].end() if boundaries else 0
    return start, text[start:end]


def descriptive(value):
    # A definition followed by a relative/purpose clause describes capability.
    return bool(re.search(r"(?:[:]|\b(?:is|are)\s+(?:a|an)\b).*?\b(?:that|which|to)\b", value, re.I))


def structured_end(text, start, apposition=False):
    """Allow quantity complements and a project's explicit possessive apposition."""
    end = min(len(text), start + policy()["object_bound_chars"])
    expression = r"[,;!?]|\b(?:for|from|with|by|which|that|but|whereas|while|and|across|alongside|to|of)\b"
    for boundary in re.finditer(expression, text[start:end], re.I):
        offset = start + boundary.start()
        if boundary.group().lower() == "to" and re.search(r"\bup\s+$", text[start:offset], re.I):
            continue
        if boundary.group().lower() == "of" and re.search(r"\d[\w .]*\s$", text[start:offset]):
            continue
        if apposition and boundary.group() == "," and re.match(r"\s*(?:its|their|a|an)\b", text[offset + 1:], re.I):
            continue
        return offset
    return end


def assess(window, core_policy):
    text = window["text"]
    base = {"version": policy()["version"], "eligible": False,
            "reason": "OPERATING_ACTION_OBJECT_REQUIRED", "source_window": window,
            "financial_impact": "UNKNOWN", "identity_verified": False,
            "offset_basis": "RELATIVE_TO_SOURCE_WINDOW_TEXT", "delivery": "disabled"}
    activity = window.get("activity_assertion")
    if activity and activity.get("version") == "market-developments-v1":
        from engine.market_developments import classify

        checked = classify(text)
        if not checked or any(checked.get(k) != activity.get(k) for k in checked):
            return {**base, "reason": "SOURCE_WINDOW_MISMATCH"}
        return {**base, **checked, "eligible": checked["editorial_eligible"],
                "reason": "EXPLICIT_MARKET_DEVELOPMENT" if checked["editorial_eligible"] else "MARKET_BACKGROUND_ONLY",
                "driver_direction": "UNKNOWN"}
    if descriptive(text):
        return {**base, "reason": "PRODUCT_DESCRIPTION_NOT_OPERATING_CHANGE"}
    if activity:
        return structured(base, text, activity)
    from engine.operating_purposes import assess as purpose

    if development := purpose(text):
        return {**base, **development, "eligible": True, "reason": "EXPLICIT_OPERATING_PURPOSE_OBJECT"}
    for direction, terms in core_policy["change_terms"].items():
        for action in re.finditer(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b", text, re.I):
            left, before = prefix(text, action.start())
            future = bool(re.search(policy()["planning_pattern"], before, re.I))
            infinitive = bool(re.search(r"\bto\s*$", before, re.I))
            allocation = re.search(policy()["allocation_pattern"], before, re.I)
            funded_purpose = bool(infinitive and allocation and literal(policy()["funding"], before))
            if infinitive and not future and not funded_purpose:
                continue
            if re.search(r"\b(?:can|could|might|designed to|used to|in order to)\s*$", before, re.I):
                continue
            end = tail(text, action.end())
            for kind, objects in policy()["objects"].items():
                obj = literal(objects, text[action.end():end])
                start = action.end()
                if obj is None:
                    # Intransitive change: the operating metric is the subject.
                    hits = list(re.finditer(r"\b(?:" + "|".join(re.escape(t) for t in objects) + r")\b", before, re.I))
                    obj = next((m for m in reversed(hits) if re.fullmatch(
                        r"\s*(?:(?:has|have|had|is|are|was|were|will|also|now|sharply|significantly)\s+)*", before[m.end():], re.I)), None)
                    start = left
                if obj is None:
                    continue
                if funded_purpose:
                    assert allocation is not None
                    return {**base, "eligible": True, "reason": "EXPLICIT_OPERATING_PURPOSE",
                            "event_type": "CAPITAL_ALLOCATION", "phase": "FORWARD_LOOKING",
                            "driver_direction": "UNKNOWN", "action_span": span(text, left + allocation.start(), left + allocation.end()),
                            "purpose_action_span": span(text, action.start(), action.end()),
                            "object_span": span(text, start + obj.start(), start + obj.end()), "object_kind": kind}
                return {**base, "eligible": True, "reason": "EXPLICIT_OPERATING_CHANGE",
                        "event_type": kind + "_CHANGE", "phase": "FORWARD_LOOKING" if future else "SOURCE_REPORTED_CHANGE",
                        "driver_direction": direction, "action_span": span(text, action.start(), action.end()),
                        "object_span": span(text, start + obj.start(), start + obj.end()), "object_kind": kind}
    return base


def structured(base, text, activity):
    kind = activity["event_type"]
    if kind == "COMPUTE_DEPLOYMENT" and re.search(policy()["demonstration_pattern"], text, re.I):
        return {**base, "reason": "DEMONSTRATION_NOT_OPERATING_DEPLOYMENT"}
    definitions = {
        "COMPUTE_DEPLOYMENT": (r"\b(?:deploy(?:s|ed|ing)?|install(?:s|ed)?|commission(?:s|ed)?|launch(?:es|ed)?)\b", policy()["hardware"]),
        "FACILITY_PROJECT": (r"\b(?:announc(?:e|es|ed)|plans?|proposes?|builds?|building|construction|develop(?:s|ed|ment|ing)?|invest(?:s|ed|ing)?|opens?|opening)\b", policy()["facilities"]),
        "PROJECT_FINANCING": (r"\b(?:seeks?|seeking|secur(?:es|ed)|commits?|invest(?:s|ed|ment|ing)?)\b", policy()["funding"]),
        "PRODUCT_INTEGRATION": (r"\b(?:integrat(?:e|es|ed|ing)|complement(?:s|ing)?|incorporat(?:e|es|ed|ing))\b", []),
    }
    if kind not in definitions:
        return base
    pattern, objects = definitions[kind]
    for action in re.finditer(pattern, text, re.I):
        left, before = prefix(text, action.start())
        future = bool(re.search(policy()["planning_pattern"], before, re.I))
        if re.search(r"\bto\s*$", before, re.I) and not future:
            # A named operator 'to deploy' headline is an explicit plan; reduced
            # purpose clauses ('designed to deploy') are not operating actions.
            if re.search(r"\b(?:designed|used|ability|able|order|aims?)\b", before, re.I):
                continue
            future = True
        if re.search(r"\b(?:can|could|might|including|featuring)\s*$", before, re.I):
            continue
        end = structured_end(text, action.end(), apposition=kind == "FACILITY_PROJECT")
        obj = literal(objects, text[action.end():end]) if objects else re.search(r"\S.{1,100}", text[action.end():end])
        start = action.end()
        if obj is None and kind == "COMPUTE_DEPLOYMENT":
            # Passive deployment needs an auxiliary or an explicit 'by' agent,
            # not a component mentioned inside a product description.
            passive = re.search(r"\b(?:was|were|is|are|been|be)\s*$", before, re.I)
            explicit_agent = re.match(r"\s+by\b", text[action.end():], re.I)
            if passive or explicit_agent:
                obj = literal(objects, before[:passive.start()] if passive else before)
                start = left
        if obj is None:
            continue
        return {**base, "eligible": True, "reason": "EXPLICIT_OPERATING_ACTION_OBJECT",
                "event_type": kind, "phase": "FORWARD_LOOKING" if future else activity["phase"],
                "driver_direction": "UNKNOWN", "action_span": span(text, action.start(), action.end()),
                "object_span": span(text, start + obj.start(), start + obj.end())}
    return base
