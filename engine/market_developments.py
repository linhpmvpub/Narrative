"""Opt-in infrastructure market developments over a sourced profile route.

Only original sentence evidence is used. A proposal/test is never commercial
operation, a source party is not a verified customer, and background is not priority.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from engine.source_role import assess as source_role
from engine.source_sentences import sentences


@lru_cache(maxsize=1)
def policy():
    return json.loads((Path(__file__).resolve().parent.parent /
                       "config/market-developments-v1.json").read_text(encoding="utf-8"))


def span(m):
    return {"start": m.start(), "end": m.end(), "text": m.group()}


def classify(text):
    p = policy()
    if len(text) > p["max_window_chars"] or re.search(p["negation"], text, re.I):
        return None
    fallback = None
    for asset in re.finditer(p["assets"], text, re.I):
        # Same-clause operating object; neither a title nor another clause donates it.
        starts = list(re.finditer(p["boundary"], text[:asset.start()], re.I))
        left = starts[-1].end() if starts else 0
        following = re.search(p["boundary"], text[asset.end():], re.I)
        right = asset.end() + following.start() if following else len(text)
        clause = text[left:right]
        if re.search(p["nonoperating"], clause, re.I):
            continue
        actions = list(re.finditer(p["actions"], text, re.I))
        for action in actions:
            if not left <= action.start() < asset.start() or asset.end() - action.end() > p["object_bound_chars"]:
                continue
            bridge = text[action.end():asset.start()]
            if re.search(p["object_boundary"], bridge, re.I):
                continue
            if re.search(r"\b(?:support|promote|understand|discuss|study|analyze)\b", bridge, re.I):
                continue
            before = text[left:action.start()]
            if re.search(r"\b(?:can|may|would|designed to|used to|help(?:s|ing)?(?: to)?)\s*$", before, re.I):
                continue
            if re.search(r"\bto\s*$", before, re.I) and not re.search(
                    r"\b(?:plans?|planned|files?|filed|intends?|agreed|committed|proposes?|proposed)\b", before, re.I):
                continue  # A purpose infinitive is not an operator's decision.
            planned = bool(re.search(p["plans"], clause, re.I))
            experimental = bool(re.search(p["experiments"], clause, re.I))
            descriptive = source_role(text, action.start(), asset.end(),
                                      predicate_start=action.start())["role"] == "INCIDENTAL_DESCRIPTION"
            result = {"version": p["version"], "event_type": "INFRASTRUCTURE_BACKGROUND" if descriptive else "INFRASTRUCTURE_DEVELOPMENT",
                    "phase": "BACKGROUND" if descriptive else "EXPERIMENTAL_PLAN" if experimental and planned else
                    "EXPERIMENTAL_ACTIVITY" if experimental else "FORWARD_LOOKING" if planned else "SOURCE_REPORTED_ACTIVITY",
                    "editorial_eligible": not descriptive, "action_span": span(action), "object_span": span(asset),
                    "text": text, "financial_impact": "UNKNOWN", "company_order_verified": False,
                    "identity_verified": False, "offset_basis": "RELATIVE_TO_SOURCE_WINDOW_TEXT"}
            if not descriptive:
                return result
            fallback = fallback or result
        background = re.search(p["background"], clause, re.I)
        if background and not any(left <= a.start() < right for a in actions):
            fallback = fallback or {"version": p["version"], "event_type": "INFRASTRUCTURE_BACKGROUND",
                    "phase": "BACKGROUND", "editorial_eligible": False, "object_span": span(asset),
                    "text": text, "financial_impact": "UNKNOWN", "company_order_verified": False,
                    "identity_verified": False, "offset_basis": "RELATIVE_TO_SOURCE_WINDOW_TEXT"}
    return fallback


def matches(binding, fields, *, bundle=None, at=None, context_title=""):
    for field, text in fields.items():
        for sentence in sentences(text):
            if any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", sentence.group(), re.I)
                   for t in binding.exclude_terms):
                continue
            development = classify(sentence.group())
            if development:
                action = development.get("action_span")
                obj = development["object_span"]
                role = source_role(sentence.group(), action["start"] if action else obj["start"], obj["end"],
                    predicate_start=action["start"] if action else None,
                    headline=fields.get("title", "") or context_title, is_headline=field == "title",
                    focus_patterns=(policy()["assets"], policy()["actions"]))
                if not role["allowed"]:
                    continue
                if binding.infrastructure_scope:
                    from engine.infrastructure_scope import assess

                    scope = assess(binding.infrastructure_scope, development, bundle, at)
                    if not scope["allowed"]:
                        continue  # Another independently supported sentence may still qualify.
                    development = {**development, "infrastructure_scope": scope}
                spans = [development["object_span"]]
                if development.get("action_span"):
                    spans.append(development["action_span"])
                return [{**s, "start": s["start"] + sentence.start(),
                         "end": s["end"] + sentence.start(), "field": field,
                         "group": "market_development", "news_party_verified": False,
                         "source_role": role,
                         **({"context_only": True} if role["role"] == "FOCUSED_DESCRIPTION" else {}),
                         "relevance_role": "MARKET_DEVELOPMENT_CONTEXT",
                         "activity_assertion": {**development, "market": "DATA_CENTER",
                                                "vendor_scope": "UNSPECIFIED"}}
                        for s in spans]
    return []
