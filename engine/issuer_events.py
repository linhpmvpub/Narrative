"""Bounded issuer event contracts over literal source sentences, never price forecasts."""

import json
import re
from functools import lru_cache
from pathlib import Path

from engine.ingestion.contracts import digest
from engine.source_sentences import sentences


@lru_cache(maxsize=1)
def catalog():
    value = json.loads((Path(__file__).resolve().parents[1] /
                        "config/issuer-events-v1.json").read_text(encoding="utf-8"))
    if value["version"] != "ISSUER_EVENTS_V1" or value["delivery"] != "disabled":
        raise ValueError("Disabled versioned issuer-event catalog required")
    if len({r["id"] for r in value["rules"]}) != len(value["rules"]):
        raise ValueError("Unique issuer event contracts required")
    return value


def matches(names, article):
    policy = catalog()
    for field in ("title", "summary"):
        text = article.get(field, "")
        candidates = []
        for sentence in sentences(text):
            if len(sentence.group()) > 1200:
                continue
            for name in sorted(names, key=len, reverse=True):
                for rule in policy["rules"]:
                    pattern = r"(?<!\w)(?P<actor>" + re.escape(name) + r")(?!\w)" + rule["tail"]
                    for hit in re.finditer(pattern, sentence.group(), re.I):
                        prefix = sentence.group()[:hit.start()]
                        if (re.search(r"\b(?:not|never|no|fake|falsely)\b", hit.group(), re.I)
                                or re.search(r"\b(?:if|whether|how)\s*$", prefix, re.I)
                                or re.search(r"\b(?:denies?|denied|untrue|false)\b[^,;:]{0,60}$", prefix, re.I)
                                or text[sentence.end():].startswith("?")):
                            continue
                        start, end = sentence.start() + hit.start(), sentence.start() + hit.end()

                        def span(group, hit=hit, sentence=sentence):
                            if group not in hit.re.groupindex or hit[group] is None:
                                return None
                            return {"start": sentence.start() + hit.start(group),
                                    "end": sentence.start() + hit.end(group), "text": hit[group]}

                        phase = "FORWARD_LOOKING" if hit.groupdict().get("plan") else "SOURCE_REPORTED"
                        candidates.append({"field": field, "start": start, "end": end, "text": hit.group(),
                            "event_family": rule["family"], "context_only": True,
                            "news_party_verified": False,
                            "issuer_event": {"version": policy["version"], "policy_sha256": digest(policy),
                                "contract_id": rule["id"], "business_variable": rule["business_variable"],
                                "actor": span("actor"), "predicate": span("action"), "object": span("object"),
                                "phase": phase, "source_window": {"field": field,
                                    "start": sentence.start(), "end": sentence.end(), "text": sentence.group()},
                                "offset_basis": "RELATIVE_TO_MATCH_FIELD",
                                "claim_status": "SOURCE_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
                                "financial_effect": "UNKNOWN", "delivery": "disabled"}})
        # Retain the longest exact contract at each location. Short aliases and
        # general result declarations must not duplicate the same metric change.
        retained: list[tuple[int, int]] = []
        for candidate in sorted(candidates, key=lambda c: (c["start"], -c["end"])):
            if not any(a <= candidate["start"] and candidate["end"] <= b for a, b in retained):
                retained.append((candidate["start"], candidate["end"]))
                yield candidate
