"""Bounded English event grammar and reviewed scope grounding, local shadow only.

This is a candidate extractor, not general language understanding or causal approval.
Unsupported clauses abstain; no legacy keyword matcher fallback is used.
"""

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from engine.article_cards import substantive_blocks
from engine.company_profiles import available_bundles, paths
from engine.ingestion.contracts import digest

# Typed action phrases, independent of issuers, URLs and individual news examples.
ACTIONS = {
    "halt production of": ("supply_disruption", "DOWN"),
    "resume production of": ("supply_disruption", "UP"),
    "increase production of": ("capacity", "UP"),
    "reduce production of": ("capacity", "DOWN"),
    "begin production of": ("capacity", "UP"),
    "build": ("capacity", "UP"),
    "open": ("capacity", "UP"),
    "cancel orders for": ("demand", "DOWN"),
    "place orders for": ("demand", "UP"),
    "raise prices for": ("input_price", "UP"),
    "cut prices for": ("input_price", "DOWN"),
    "provide funding for": ("financing", "UP"),
    "grant licenses for": ("policy", "UP"),
    "revoke licenses for": ("policy", "DOWN"),
    "sample": ("technology", "UNKNOWN"),
}
PAST = {
    "halted production of": "halt production of",
    "resumed production of": "resume production of",
    "increased production of": "increase production of",
    "reduced production of": "reduce production of",
    "began production of": "begin production of",
    "built": "build",
    "opened": "open",
    "cancelled orders for": "cancel orders for",
    "canceled orders for": "cancel orders for",
    "placed orders for": "place orders for",
    "raised prices for": "raise prices for",
    "cut prices for": "cut prices for",
    "provided funding for": "provide funding for",
    "granted licenses for": "grant licenses for",
    "revoked licenses for": "revoke licenses for",
    "sampled": "sample",
}
UNSAFE = re.compile(
    r"\b(?:not|never|no|if|unless|may|might|could|would|reportedly|according|said|says|"
    r'and|but|or|while|after|before|despite|it|they|we|he|she|which|that)\b|["“”?:]',
    re.I,
)


def extract(text):
    """Exact block-relative spans; only one actor/action/object clause per sentence.

    Past tense means reported action, NOT verified ongoing operation. Future tense
    means proposed, NOT committed. Geography must be explicit and is never inherited.
    """
    if not isinstance(text, str) or len(text) > 100_000:
        raise ValueError("Bounded text required")
    events, audit = [], []
    forms = sorted(set(ACTIONS) | set(PAST), key=len, reverse=True)
    verbs = "|".join(re.escape(x) for x in forms)
    grammar = re.compile(
        r"(?P<actor>[\w &'-]{2,100}?)\s+(?P<plan>plans to |will )?"
        r"(?P<action>" + verbs + r")\s+(?P<object>[\w /()'-]{2,120}?)"
        r"(?:\s+in\s+(?P<location>[\w '-]{2,80}))?",
        re.I,
    )
    for span in re.finditer(r"[^.!?;\n]+", text):
        raw = span.group()
        clause = raw.strip()
        offset = span.start() + len(raw) - len(raw.lstrip())
        match = (
            grammar.fullmatch(clause) if len(clause) <= 400 and not UNSAFE.search(clause) else None
        )
        if not match:
            if clause:
                audit.append(
                    {"text": clause, "start": offset, "reason": "UNSUPPORTED_OR_AMBIGUOUS_CLAUSE"}
                )
            continue
        action = match["action"].lower()
        planned = bool(match["plan"])
        if (planned and action not in ACTIONS) or (not planned and action not in PAST):
            audit.append({"text": clause, "start": offset, "reason": "AMBIGUOUS_TENSE"})
            continue
        canonical = PAST.get(action, action)
        family, direction = ACTIONS[canonical]
        fields = {}
        for name in ["actor", "action", "object", "location"]:
            if match[name] is not None:
                a, b = match.span(name)
                fields[name] = {"text": match[name], "start": offset + a, "end": offset + b}
        events.append(
            {
                "id": digest([offset, clause]),
                "mechanism": family,
                "action": canonical,
                "phase": "PROPOSED" if planned else "REPORTED_ACTION",
                "direction": direction,
                "fields": fields,
                "text": clause,
                "start": offset,
                "end": offset + len(clause),
                "occurrence_time": None,
                "strength": "UNKNOWN",
                "horizon": "UNKNOWN",
            }
        )
    return events, audit


class GroundingRule(BaseModel):
    """Reviewer-declared actor/object scope, not a global identity assertion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    profile_id: str
    profile_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    relationship_id: str
    actor: str = Field(min_length=2, max_length=100)
    object: str = Field(min_length=2, max_length=120)
    location: str | None = Field(default=None, min_length=2, max_length=80)
    action: str
    source_id: str
    source_quote: str = Field(min_length=10, max_length=8000)
    reviewed_at: AwareDatetime
    review_until: AwareDatetime
    reviewer_id: str = Field(min_length=1)
    reviewer_kind: Literal["HUMAN", "AI_OPERATOR"]
    status: Literal["SOURCE_BACKED", "REVOKED", "DISPUTED"] = "SOURCE_BACKED"


def normalized(value):
    return " ".join(value.casefold().split()) if value is not None else None


def validate_rule(rule, bundle, at):
    if (
        rule.action not in ACTIONS
        or rule.profile_id != bundle.id
        or rule.profile_sha256 != digest(bundle.model_dump(mode="json"))
        or not bundle.available_at <= rule.reviewed_at <= at < rule.review_until
        or not 0 < (rule.review_until - rule.reviewed_at).total_seconds() <= 90 * 86400
    ):
        raise ValueError("Rule profile, action or review window invalid")
    edge = next((e for e in bundle.relationships if e.id == rule.relationship_id), None)
    if edge is None or not any(
        e.source_id == rule.source_id and rule.source_quote in e.quote for e in edge.evidence
    ):
        raise ValueError("Rule must cite evidence on its anchoring relationship")
    # Lexical evidence is necessary, not sufficient: interpretation remains explicitly reviewed.
    for value in [rule.actor, rule.object, rule.location]:
        if value and not re.search(
            r"(?<!\w)" + re.escape(value) + r"(?!\w)", rule.source_quote, re.I
        ):
            raise ValueError("Rule scope names absent from relationship evidence")
    return edge


def build(selections, rules, *, profile_root=None, article_root=None, at=None):
    at = at or datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC) or not 1 <= len(selections) <= 100:
        raise ValueError("Bounded selections and nonfuture aware cutoff required")
    if len(rules) > 500 or len({r.id for r in rules}) != len(rules):
        raise ValueError("Bounded unique rule identities required")
    registry = available_bundles(at, root=profile_root)
    if not registry["enabled"] or registry.get("withheld") or registry.get("truncated"):
        raise ValueError("Complete validated profile registry required")
    bundles = {b.id: b for b in registry["items"]}
    before = digest([b.model_dump(mode="json") for b in registry["items"]])
    validated = []
    for rule in rules:
        if rule.profile_id not in bundles:
            raise ValueError("Unknown rule profile")
        edge = validate_rule(rule, bundles[rule.profile_id], at)
        validated.append((rule, bundles[rule.profile_id], edge))
    cards: list[dict] = []
    audits: list[dict] = []
    seen: set[str] = set()
    for selection in selections:
        key = digest(selection)
        if key in seen:
            continue
        seen.add(key)
        blocks, suppressed = substantive_blocks(selection, at, article_root=article_root)
        for block_index, block in enumerate(blocks):
            if len(cards) > 1000 or len(audits) > 10000:
                raise ValueError("Shadow output limit exceeded; split the batch")
            events, rejected = extract(block["text"])
            audits.extend({"selection_sha256": key, "block": block_index, **a} for a in rejected)
            for event in events:
                matches = []
                for rule, bundle, edge in validated:
                    fields = event["fields"]
                    if (
                        rule.status != "SOURCE_BACKED"
                        or edge.status != "SOURCE_BACKED"
                        or not edge.known_at <= at
                        or not edge.valid_from <= at
                        or (edge.valid_until is not None and at >= edge.valid_until)
                    ):
                        continue
                    if event["action"] != rule.action or any(
                        normalized(fields.get(k, {}).get("text")) != normalized(getattr(rule, k))
                        for k in ["actor", "object", "location"]
                    ):
                        continue
                    matches.append((rule, bundle, edge))
                # Conflicting anchors in one profile must not silently pick the shortest route.
                ambiguous = {
                    b.id
                    for _, b, _ in matches
                    if len({e.from_id for _, bb, e in matches if bb.id == b.id}) > 1
                }
                emitted = 0
                for rule, bundle, edge in matches:
                    if bundle.id in ambiguous:
                        continue
                    for narrative in bundle.narratives:
                        routes, truncated = paths(
                            bundle,
                            SimpleNamespace(anchors=[edge.from_id]),
                            narrative,
                            effective_at=at,
                        )
                        routes = [p for p in routes if edge.id in {e.id for e in p}]
                        if truncated or not routes:
                            continue
                        route = min(routes, key=len)
                        cards.append(
                            {
                                "id": digest(
                                    [key, block_index, event["id"], rule.id, narrative.id]
                                ),
                                "mode": "STRUCTURED_EVENT_REVIEW_CANDIDATE",
                                "ticker": bundle.ticker,
                                "narrative_id": narrative.id,
                                "event": event,
                                "grounding_rule": rule.model_dump(mode="json"),
                                "path": [e.model_dump(mode="json") for e in route],
                                "source_spans": block["source_spans"],
                                "source_block": block["text"],
                                "selection_sha256": key,
                                "source_url": selection["revision"]["payload"]["url"],
                                "source_packet_sha256": selection["packet_sha256"],
                                "profile_sha256": rule.profile_sha256,
                                "financial_magnitude": "UNKNOWN",
                                "horizon": "UNKNOWN",
                                "stance": "RELATED_INFORMATION",
                                "delivery": "disabled",
                                "blockers": [
                                    "Candidate extraction and reviewer scope need independent validation",
                                    "Current profiles; not historical as-of or current publisher approval",
                                    "No verified financial effect, calibrated strength or duration",
                                ],
                            }
                        )
                        if len(cards) > 1000:
                            raise ValueError("Shadow output limit exceeded; split the batch")
                        emitted += 1
                audits.append(
                    {
                        "selection_sha256": key,
                        "block": block_index,
                        "event": event,
                        "reason": "CANDIDATE_ROUTED"
                        if emitted
                        else "NO_UNAMBIGUOUS_SOURCED_SCOPE_PATH",
                        "candidate_cards": emitted,
                        "suppressed_blocks": len(suppressed),
                    }
                )
    current = available_bundles(at, root=profile_root)
    if len(cards) > 1000 or len(audits) > 10000:
        raise ValueError("Shadow output limit exceeded; split the batch")
    if (
        current.get("withheld")
        or current.get("truncated")
        or not current["enabled"]
        or digest([b.model_dump(mode="json") for b in current["items"]]) != before
    ):
        raise ValueError("Profile registry changed during evaluation")
    return {
        "schema": "structured-news-shadow-v1",
        "items": cards,
        "audit": audits,
        "rules_sha256": digest([r.model_dump(mode="json") for r in rules]),
        "profiles_sha256": before,
        "delivery": "disabled",
        "active_feed_changed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["selections", "rules", "profiles", "articles", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    rules = [
        GroundingRule.model_validate(x) for x in json.loads(args.rules.read_text(encoding="utf-8"))
    ]
    result = build(
        json.loads(args.selections.read_text(encoding="utf-8")),
        rules,
        profile_root=args.profiles,
        article_root=args.articles,
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"candidate_cards": len(result["items"]), "delivery": "disabled"}))


if __name__ == "__main__":
    main()
