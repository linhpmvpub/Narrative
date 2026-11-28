"""Bounded source assertions and data-declared graph applicability, not facts."""

import json
import re
from functools import lru_cache
from pathlib import Path

from engine.news_framework import classify, first, literal
from engine.source_sentences import LEGAL_SUFFIX, sentences


@lru_cache(maxsize=1)
def policy():
    return json.loads((Path(__file__).resolve().parent.parent /
                       "config/news-assertions-v1.json").read_text(encoding="utf-8"))


def windows(text):
    # Contrast clauses cannot donate a subject or market to each other.
    for sentence in sentences(text):
        cursor = sentence.start()
        for boundary in re.finditer(r"\b(but|whereas|while)\b", sentence.group(), re.I):
            end = sentence.start() + boundary.start()
            if chunk := re.compile(r"[\s\S]+").match(text, cursor, end):
                yield chunk
            cursor = sentence.start() + boundary.end()
        if chunk := re.compile(r"[\s\S]+").match(text, cursor, sentence.end()):
            yield chunk


@lru_cache(maxsize=4096)
def frame(text):
    p = policy()
    signal = classify(text)
    events = {k: h for k, terms in p["activities"].items() if (h := first(terms, text))}
    candidates = sorted((dict(event_type=k, start=m.start(), end=m.end(), text=m.group(), term=t)
                         for k, terms in p["activities"].items() for t in terms
                         for m in re.finditer(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text, re.I)),
                        key=lambda h: (h["start"], -h["end"]))
    negation = first(p["negations"], text)
    phase = ("RETROSPECTIVE" if first(p["retrospective"], text) else
             "FORWARD_LOOKING" if first(p["planned"], text) else "SOURCE_REPORTED")
    return {"version": p["version"], "text": text, "components": signal["components"],
            "markets": signal["markets"], "activities": events, "activity_candidates": candidates, "phase": phase,
            "negation": negation, "actor": "UNKNOWN", "recipient": "UNKNOWN",
            "platform": "UNKNOWN", "reference_period": "UNKNOWN",
            "offset_basis": "RELATIVE_TO_ASSERTION_TEXT", "financial_impact": "UNKNOWN"}


def operator_predicate(scope, text, candidates):
    """Bounded active/planned/passive grammar over names declared in source data."""
    names = "|".join(re.escape(t) for t in sorted(scope.subject_terms, key=len, reverse=True))
    auxiliary = r"(?:(?:has|have|had|is|are|was|were|will|now|also|recently|already|successfully|jointly|today|each|to|plans|plan|expects|expect|intends|intend)\b[\s,]*)*"
    for term in scope.subject_terms:
        for hit in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I):
            subject = {"start": hit.start(), "end": hit.end(), "text": hit.group(), "term": term}
            for event in candidates:
                # Noun labels such as 'mass production' are useful classification
                # context but cannot themselves establish an active predicate.
                if " " in event["term"]:
                    continue
                if hit.end() <= event["start"]:
                    if re.search(r"\b(for|with|to|from|by|of|between)\s*$", text[:hit.start()], re.I):
                        continue
                    gap = text[hit.end():event["start"]]
                    if len(gap) > 160:
                        continue
                    gap = re.sub(r"^\s*,?\s*" + LEGAL_SUFFIX, "", gap, flags=re.I)
                    gap = re.sub(r'''^\s*\(\s*(?:the\s+)?["“'](?:the\s+)?(?:Company|Group)["”']\s*\)''', "", gap, flags=re.I)
                    gap = re.sub(r"^(?:\s*(?:,|and|&)\s*(?:" + names + r")(?!\w))+", "", gap, flags=re.I)
                    if re.fullmatch(r"[\s,]*" + auxiliary, gap, re.I):
                        if event["text"].lower().endswith("ed") and re.search(r"\b(is|are|was|were|been|be)\s*$", gap, re.I):
                            continue  # Passive patient is not the by-agent.
                        return subject, event, "ACTIVE", bool(re.search(r"\b(to|will|plans?|expects?|intends?)\b", gap, re.I))
                elif event["end"] <= hit.start():
                    # Only explicit passive predicates with a by-agent. Recipient
                    # phrases, nominal capacity and agentless passives stay unknown.
                    prefix = text[:event["start"]]
                    if (event["text"].lower().endswith("ed")
                            and re.search(r"\b(?:is|are|was|were|been|be)\s*$", prefix, re.I)
                            and re.fullmatch(r"\s+by\s+", text[event["end"]:hit.start()], re.I)):
                        return subject, event, "PASSIVE", bool(re.search(r"\bwill\s+be\s*$", prefix, re.I))
    return None


def applicability(scope, text):
    """A literal bridge is conditional scope evidence, not verified actor identity."""
    f = frame(text)
    events = {k: h for k, h in f["activities"].items() if k in scope.event_types}
    subject = first(scope.subject_terms, text)
    predicate, voice = None, "UNKNOWN"
    industry = first(policy()["industry_scope"], text)
    constraint = f["activities"].get("CONSTRAINT")
    reason, allowed = "SCOPE_NOT_ESTABLISHED", False
    argument = None
    if scope.object_components and not f["negation"]:
        from engine.news_objects import object_events

        argument = next(object_events(scope, text), None)
        if argument:
            subject, predicate, voice = argument["subject_span"], argument["predicate_span"], argument["voice"]
            f = {**f, "phase": "FORWARD_LOOKING" if argument["planned"] else f["phase"]}
            allowed, reason = True, argument["event_type"] + "_OBJECT"
    if not allowed and events and not f["negation"]:
        if scope.mode == "NAMED_OPERATOR":
            match = operator_predicate(scope, text, [e for e in f["activity_candidates"] if e["event_type"] in events])
            if match:
                subject, predicate, voice, planned = match
                f = {**f, "phase": "FORWARD_LOOKING" if planned else f["phase"]}
                allowed, reason = True, "NAMED_OPERATOR_ACTIVITY"
        elif subject and not re.search(r"\b(but|whereas|while)\b", text, re.I):
            allowed, reason = True, "NAMED_PLATFORM_CONTEXT"
        elif (industry and constraint and "CONSTRAINT" in scope.event_types
              and f["components"] and f["markets"]):
            allowed, reason = True, "EXPLICIT_SHARED_MARKET_CONSTRAINT"
    return {"allowed": allowed, "reason": reason, "mode": scope.mode,
            "relationship_id": scope.relationship_id, "subject_span": subject,
            "predicate_span": predicate, "voice": voice,
            **({"object_argument": argument} if argument else {}),
            "industry_span": industry, "assertion": f, "news_party_verified": False,
            "financial_impact": "UNKNOWN"}


def evidence_supports(terms, evidence):
    return all(any(literal(t, e.quote) for e in evidence) for t in terms)
