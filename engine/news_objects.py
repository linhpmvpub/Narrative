"""Bounded source actor -> transaction/purpose -> component object arguments.

Names and object classes are profile data. Claims remain source-reported, not
verified identities, ownership updates, operational outcomes or financial impact.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from engine.news_framework import first
from engine.news_framework import policy as component_policy


@lru_cache(maxsize=1)
def policy():
    return json.loads((Path(__file__).resolve().parent.parent /
                       "config/news-objects-v1.json").read_text(encoding="utf-8"))


def alternatives(terms):
    return "(?:" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + ")"


def span(text, start, end):
    return {"start": start, "end": end, "text": text[start:end]}


@lru_cache(maxsize=1)
def predicates():
    p = policy()
    completion = alternatives(p["completion_verbs"])
    transaction = alternatives(p["transaction_nouns"])
    # Closed the first phase of the transaction by acquiring an asset is a
    # bounded acquisition predicate; arbitrary reported speech is unsupported.
    compound = (completion + r"\s+(?:(?:the|a|an|first|second|final|phase|of|transaction)\s+){0,9}"
                + r"(?:" + transaction + r"\s+of|by\s+(?:acquiring|divesting))")
    return [
        ("OWNERSHIP", re.compile(r"\b(?:" + compound + "|" + alternatives(p["ownership_verbs"]) + r")\b", re.I)),
        ("FINANCING_PURPOSE", re.compile(r"\b" + alternatives(p["allocation_verbs"] + p["raising_verbs"]) + r"\b", re.I)),
    ]


def object_end(text, start):
    end = min(len(text), start + policy()["object_bound_chars"])
    # Purpose/recipient/reporting adjuncts cannot donate an unrelated product.
    stop = re.search(r"[,;.!?\n]|\b(?:for|to|from|with|by|which|that|but|whereas|while|and)\b", text[start:end], re.I)
    if stop:
        return start + stop.start()
    return end if end == len(text) else None  # Do not accept a silently truncated object.


def object_events(scope, text):
    from engine.news_assertions import operator_predicate

    p = policy()
    for kind, pattern in predicates():
        if kind not in scope.event_types:
            continue
        for hit in pattern.finditer(text):
            head = hit.group().split()[0]
            event = dict(event_type=kind, start=hit.start(), end=hit.start() + len(head), text=head, term=head)
            actor = operator_predicate(scope, text, [event])
            if not actor:
                continue
            subject, _, voice, planned = actor
            purpose = None
            if voice == "PASSIVE":
                # The patient object must be before the passive auxiliary.
                auxiliary = re.search(r"\b(?:(?:has|have|had)\s+been|will\s+be|is|are|was|were)\s*$", text[:hit.start()], re.I)
                if not auxiliary:
                    continue
                start, end = 0, auxiliary.start()
                if end > p["object_bound_chars"]:
                    continue
            else:
                start = hit.end()
                if kind == "FINANCING_PURPOSE":
                    tail = text[start:start + p["bridge_bound_chars"]]
                    if head.casefold() in p["raising_verbs"]:
                        connector = re.search(r"\b(?:to|for)\s+(?:" + alternatives(p["purpose_actions"]) + r")\b", tail, re.I)
                        if not connector or not first(p["funding_terms"], tail[:connector.start()]):
                            continue
                        if re.search(r"[,;.!?\n]|\b(?:and|but|while|whereas|for|to|from|with|by|said|says|plans|expects)\b",
                                     tail[:connector.start()], re.I):
                            continue
                        purpose = span(text, start + connector.start(), start + connector.end())
                        start += connector.start()
                        goal_prefix = re.match(r"(?:to|for)\s+", text[start:], re.I)
                        assert goal_prefix is not None  # The connector expression requires it.
                        start += goal_prefix.end()
                    else:
                        prefix = re.match(r"\s+(?:(?:in|into|toward|towards)\s+)?", text[start:], re.I)
                        if not prefix:
                            continue
                        start += prefix.end()
                end = object_end(text, start)
                if end is None:
                    continue
            value = text[start:end]
            if not value.strip() or first(p["financial_objects"] + p["unrelated_assets"], value):
                continue
            # A second actor/clause cannot supply the object of the first action.
            if re.search(r"\b(?:said|says|announced|announces|reported|reports|expects|plans)\b", value, re.I):
                continue
            if kind == "OWNERSHIP" and not first(p["asset_heads"], value):
                continue
            if kind == "FINANCING_PURPOSE" and not first(p["purpose_actions"], value):
                continue
            component = next(((c, h) for c in scope.object_components
                              if (h := first(component_policy()["components"][c], value))), None)
            if not component:
                continue
            c, h = component
            yield {"version": p["version"], "event_type": kind,
                   "subject_span": subject, "predicate_span": span(text, hit.start(), hit.end()),
                   "object_span": span(text, start, end),
                   "component_span": {**h, "start": start + h["start"], "end": start + h["end"]},
                   "object_component": c, "purpose_span": purpose, "voice": voice,
                   "planned": planned, "purpose_outcome": "UNKNOWN",
                   "party_role": ("DISPOSER" if re.search(r"divest", hit.group(), re.I) else "ACQUIRER")
                   if kind == "OWNERSHIP" else "FUNDER",
                   "identity_verified": False, "operational_outcome": "UNKNOWN",
                   "financial_impact": "UNKNOWN", "offset_basis": "RELATIVE_TO_ASSERTION_TEXT"}
