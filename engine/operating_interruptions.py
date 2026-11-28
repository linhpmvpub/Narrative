"""Explicit interruption of a matched operating asset, not company impact.

Consumes a source-local matched window; cannot create relevance or graph edges.
Active and reduced/passive headlines share the same bounded object contract.
"""

import re

from engine.operating_developments import literal, policy, prefix, span


def assess(text):
    rules = policy()["interruptions"]
    for action in re.finditer(rules["actions"], text, re.I):
        left, before = prefix(text, action.start())
        if re.search(rules["non_assertion"], before, re.I) or "?" in text:
            continue
        planned = bool(re.search(r"\b(?:will(?: be)?|plans? to|expects? to|expected to)\s*$", before, re.I))
        if re.search(r"\bto\s*$", before, re.I) and not planned:
            continue
        # Passive/reduced headline: the operating object immediately precedes
        # the predicate, not a resource mentioned elsewhere in the sentence.
        objects = list(re.finditer(r"\b(?:" + "|".join(re.escape(t) for t in
                       sorted(rules["objects"], key=len, reverse=True)) + r")\b", before, re.I))
        obj = next((m for m in reversed(objects) if re.fullmatch(
            r"\s*(?:(?:has|have|had|is|are|was|were|been|being|now|temporarily|indefinitely|will|be)\s+)*",
            before[m.end():], re.I)), None)
        offset, voice = left, "PASSIVE_OR_REDUCED_HEADLINE"
        if obj is None:
            if not before.strip():
                continue  # 'Paused construction' alone may just be an adjective.
            end = min(len(text), action.end() + policy()["object_bound_chars"])
            stop = re.search(r"[,;!?]|\b(?:for|to|from|with|by|which|that|but|whereas|while|and|of|at|about)\b",
                             text[action.end():end], re.I)
            end = action.end() + stop.start() if stop else end
            obj = literal(rules["objects"], text[action.end():end])
            offset, voice = action.end(), "ACTIVE"
            if obj and not re.fullmatch(rules["object_modifiers"], text[offset:offset + obj.start()], re.I):
                continue
        if obj is None:
            continue
        return {"event_type": "OPERATING_INTERRUPTION",
                "phase": "FORWARD_LOOKING" if planned else "SOURCE_REPORTED_INTERRUPTION",
                "action_span": span(text, action.start(), action.end()),
                "object_span": span(text, offset + obj.start(), offset + obj.end()),
                "voice": voice, "driver_direction": "UNKNOWN",
                "operational_outcome": "SOURCE_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
                "company_exposure": "NOT_INFERRED", "contract_terms": "NOT_INFERRED"}
    return None
