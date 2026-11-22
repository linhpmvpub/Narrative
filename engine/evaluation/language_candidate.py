"""Explainable shadow classifier; never promotes issuer statements to causal truth."""

import re

VERSION = "financial-language-shadow-v2.0.1"
FINANCIAL = re.compile(
    r"\b(revenues?|margins?|income|profits?|sales|cash(?: flows?)?|costs?|expenses?|tax(?:es)?|earnings|loss(?:es)?|financial results|operating results|selling prices?|contract liabilities)\b",
    re.I,
)
FUTURE = re.compile(
    r"\b(may|could|would|will|expects?|expected|likely|uncertain|potentially|risk of|in the event|subject to|dependent (?:on|upon)|depends? on|can (?:materially )?(?:impact|affect|increase|reduce))\b",
    re.I,
)
CAUSE = re.compile(
    r"\b(due to|because|attributable to|result(?:ed|ing)? (?:in|from)|driven(?: primarily| mainly| largely)? by|reflect(?:ed|ing)(?!\s+in\b)|primary drivers? of|benefit(?:ed)? .{0,65}? from|partially offset by)\b",
    re.I,
)
DIRECT_EFFECT = re.compile(
    r"\b(reduced|increased|lowered|raised|harmed|affected|improved|decreased|offset)\b.{0,65}\b(income|tax(?:es)?|cash|costs?|expenses?|margins?|profits?|financial results)\b",
    re.I,
)
PAST = re.compile(
    r"\b(?:has|have|had) (?:materially |significantly |adversely )*(?:impacted|affected|reduced|increased|harmed|resulted|led|created)\b",
    re.I,
)
AUDIT = re.compile(
    r"\b(audit evidence|auditor judgment|audit matter|audit procedures|internal control)\b", re.I
)
DISCLOSURE = re.compile(
    r"\b(disclosures?|disclose|table presents|reporting system|tabular)\b", re.I
)
REAL_CHANGE = re.compile(r"\b(increased|decreased|rose|fell|benefit|charge|reduced|raised)\b", re.I)
NEGATED = re.compile(
    r"\b(?:did not|didn't|has not|have not|was not|were not)\b.{0,45}\b(?:increase|decrease|improve|grow|decline|impact|affect|result|driven|caused)",
    re.I,
)


def classify(text):
    """Sentence scope and exact source offsets; broad financial outlook is a separate class."""
    evidence = []
    boundaries = (
        [0] + [m.end() for m in re.finditer(r"(?<=[.!?;])\s+(?=[A-Z•])", text)] + [len(text)]
    )
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        raw = text[start:end]
        start += len(raw) - len(raw.lstrip())
        end -= len(raw) - len(raw.rstrip())
        sentence = text[start:end]
        if not sentence or not FINANCIAL.search(sentence):
            continue
        future = FUTURE.search(sentence)
        cause = CAUSE.search(sentence) or DIRECT_EFFECT.search(sentence)
        past = PAST.search(sentence)
        if AUDIT.search(sentence) and not DIRECT_EFFECT.search(sentence):
            label, rule = "NO_CAUSAL_CLAIM", "AUDIT_PROCEDURE_NOT_FINANCIAL_CAUSE"
        elif DISCLOSURE.search(sentence) and not REAL_CHANGE.search(sentence):
            label, rule = "NO_CAUSAL_CLAIM", "REPORTING_REQUIREMENT_NOT_FINANCIAL_OUTLOOK"
        elif NEGATED.search(sentence) and cause:
            label, rule = "UNCERTAIN_OR_FORWARD_LOOKING", "NEGATED_OR_AMBIGUOUS_CAUSAL_SCOPE"
        elif cause and (not future or (past and FINANCIAL.search(sentence[: future.start()]))):
            label, rule = "ISSUER_ATTRIBUTION", "REALIZED_FINANCIAL_EXPLANATION"
        elif future:
            label, rule = "UNCERTAIN_OR_FORWARD_LOOKING", "FINANCIAL_OUTLOOK_OR_DEPENDENCY"
        else:
            label, rule = "NO_CAUSAL_CLAIM", "FINANCIAL_DESCRIPTION_WITHOUT_CAUSE"
        evidence.append(
            {"start": start, "end": end, "text": sentence, "label": label, "rule": rule}
        )
    present = {e["label"] for e in evidence}
    label = next(
        (v for v in ("ISSUER_ATTRIBUTION", "UNCERTAIN_OR_FORWARD_LOOKING") if v in present),
        "NO_CAUSAL_CLAIM",
    )
    return {
        "version": VERSION,
        "label": label,
        "evidence": evidence,
        "mixed_temporal_claims": {"ISSUER_ATTRIBUTION", "UNCERTAIN_OR_FORWARD_LOOKING"}.issubset(
            present
        ),
        "deployment": "SHADOW_ONLY",
        "independently_verified": False,
        "graph_eligible": False,
        "stock_price_impact": "UNKNOWN",
    }
