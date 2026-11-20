"""Offline evaluation contracts. Human labels are never policy inputs."""

import math
import re
from collections import Counter, defaultdict
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from engine.ingestion.contracts import digest


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Evidence(Strict):
    url: HttpUrl
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    archive_id: str = Field(min_length=1)
    rights: Literal["approved"]
    rights_reviewer: str = Field(min_length=1)
    rights_approved_at: AwareDatetime
    published_at: AwareDatetime
    first_seen_at: AwareDatetime
    available_at: AwareDatetime
    retrieved_at: AwareDatetime


class Case(Strict):
    id: str = Field(min_length=1)
    canonical_key: str = Field(min_length=1)
    event_version: str = Field(min_length=1)
    narrative_version: str = Field(min_length=1)
    ticker: Literal["MU", "NVDA", "AMD", "DELL", "SNDK"]
    headline: str = Field(min_length=1)
    is_synthetic: bool
    as_of: AwareDatetime
    evidence: list[Evidence] = Field(min_length=1)
    narrative_available_at: AwareDatetime
    edge_available_at: list[AwareDatetime]
    metric_available_at: list[AwareDatetime]

    @model_validator(mode="after")
    def no_future_inputs(self):
        dates = [self.narrative_available_at, *self.edge_available_at, *self.metric_available_at]
        for source in self.evidence:
            if source.available_at < max(source.published_at, source.first_seen_at):
                raise ValueError("Source availability precedes publication/first sighting")
            dates.extend(
                [
                    source.published_at,
                    source.first_seen_at,
                    source.available_at,
                    source.retrieved_at,
                    source.rights_approved_at,
                ]
            )
            if not self.is_synthetic and (
                source.url.scheme != "https"
                or str(source.url.host).endswith((".invalid", ".example", ".test"))
                or source.url.host in ("example.com", "example.org", "example.net", "localhost")
            ):
                raise ValueError("Historical corpus requires genuine HTTPS source URLs")
        if any(d > self.as_of for d in dates):
            raise ValueError("Future source/rights/edge/narrative/metric input")
        return self


class Label(Strict):
    case_id: str
    reviewer: str = Field(min_length=1)
    reviewed_at: AwareDatetime
    is_new: bool
    is_relevant: bool
    is_material: bool
    valid_path: bool
    hops: int = Field(ge=0, le=2)
    stance: Literal["SUPPORTS", "CHALLENGES", "MIXED", "NO_CHANGE", "INSUFFICIENT_EVIDENCE"]
    should_push: bool
    should_digest: bool
    negative_or_irrelevant_or_reprint: bool
    reason: str = Field(min_length=1)
    evidence_urls: list[HttpUrl] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent(self):
        if self.should_push and (
            not all((self.is_new, self.is_relevant, self.is_material, self.valid_path))
            or self.should_digest
        ):
            raise ValueError("Push label requires new relevant material evidence and valid path")
        if self.negative_or_irrelevant_or_reprint and self.should_push:
            raise ValueError("Negative/reprint cannot be a positive push label")
        return self


class Split(Strict):
    development_end: AwareDatetime
    calibration_end: AwareDatetime
    holdout_end: AwareDatetime

    @model_validator(mode="after")
    def ordered(self):
        if not self.development_end < self.calibration_end < self.holdout_end:
            raise ValueError("Split boundaries must increase")
        return self

    def partition(self, case):
        if case.as_of <= self.development_end:
            return "development"
        if case.as_of <= self.calibration_end:
            return "calibration"
        if case.as_of <= self.holdout_end:
            return "holdout"
        raise ValueError("Case beyond frozen corpus end")


class Prediction(Strict):
    case_id: str
    matched: bool
    decision: Literal["push", "digest", "storybook", "suppressed", "review_required"]
    policy_version: str = Field(min_length=1)
    trace_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def consistent(self):
        if self.decision in ("push", "digest") and not self.matched:
            raise ValueError("Unmatched case cannot be pushed or digested")
        return self


def indexed(items, field):
    result = {getattr(item, field): item for item in items}
    if len(result) != len(items):
        raise ValueError("Duplicate " + field)
    return result


def freeze(cases: list[Case], split: Split) -> dict:
    indexed(cases, "id")
    if not cases:
        raise ValueError("Cannot freeze an empty corpus")
    if len({c.is_synthetic for c in cases}) != 1:
        raise ValueError("Do not mix synthetic and historical cases")
    groups: dict[str, set[str]] = defaultdict(set)
    pairs = set()
    for case in cases:
        partition = split.partition(case)
        groups[case.canonical_key].add(partition)
        groups["event-version:" + case.event_version].add(partition)
        # A source reused under another event ID cannot cross a dataset boundary.
        for evidence in case.evidence:
            groups["document:" + evidence.document_sha256].add(partition)
        pair = (case.event_version, case.narrative_version)
        if pair in pairs:
            raise ValueError("Repeated event-version/narrative-version pair")
        pairs.add(pair)
    if any(len(parts) > 1 for parts in groups.values()):
        raise ValueError("Canonical event or source document crosses chronological splits")
    payload = {
        "cases": [c.model_dump(mode="json") for c in sorted(cases, key=lambda c: c.id)],
        "split": split.model_dump(mode="json"),
    }
    return {
        "version": "historical-eval-v1",
        "dataset_sha256": digest(payload),
        "is_synthetic": cases[0].is_synthetic,
        "partitions": {c.id: split.partition(c) for c in sorted(cases, key=lambda c: c.id)},
        "split": split.model_dump(mode="json"),
    }


def rate(successes: int, total: int) -> dict:
    if not total:
        return {"numerator": successes, "denominator": 0, "value": None, "wilson_95": None}
    p, z = successes / total, 1.959963984540054
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return {
        "numerator": successes,
        "denominator": total,
        "value": p,
        "wilson_95": [max(0, center - radius), min(1, center + radius)],
    }


def confusion(actual, predicted):
    tp = sum(a and p for a, p in zip(actual, predicted, strict=True))
    fp = sum(not a and p for a, p in zip(actual, predicted, strict=True))
    fn = sum(a and not p for a, p in zip(actual, predicted, strict=True))
    tn = len(actual) - tp - fp - fn
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": rate(tp, tp + fp),
        "recall": rate(tp, tp + fn),
    }


def summarize(cases, labels, predictions):
    gold = [labels[c.id] for c in cases]
    pred = [predictions[c.id] for c in cases]
    material = [i for i, label in enumerate(gold) if label.is_material and label.is_relevant]
    two_hop = [
        i
        for i, label in enumerate(gold)
        if label.is_relevant and label.valid_path and label.hops == 2
    ]
    latencies = sorted(p.latency_ms for p in pred if p.latency_ms is not None)
    costs = [p.cost_usd for p in pred if p.cost_usd is not None]
    return {
        "pairs": len(cases),
        "events": len({c.canonical_key for c in cases}),
        "relevance": confusion([g.is_relevant for g in gold], [p.matched for p in pred]),
        "push": confusion([g.should_push for g in gold], [p.decision == "push" for p in pred]),
        "material_pair_match_recall": rate(sum(pred[i].matched for i in material), len(material)),
        "two_hop_match_recall": rate(sum(pred[i].matched for i in two_hop), len(two_hop)),
        "decisions": dict(Counter(p.decision for p in pred)),
        "latency_ms": {
            "observed": len(latencies),
            "expected": len(pred),
            "p95": latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
        },
        "cost_usd": {
            "observed": len(costs),
            "expected": len(pred),
            "total": sum(costs) if len(costs) == len(pred) and pred else None,
        },
        "duplicate_delivery_rate": None,
        "factual_error_rate": None,
        "unsupported_metrics_reason": "Requires delivery records and independent output-fact review",
    }


def evaluate(cases, labels, predictions, manifest):
    split = Split.model_validate(manifest["split"])
    if manifest != freeze(cases, split):
        raise ValueError("Frozen manifest differs; do not silently change holdout")
    by_case = indexed(cases, "id")
    gold, pred = indexed(labels, "case_id"), indexed(predictions, "case_id")
    if set(by_case) != set(gold) or set(by_case) != set(pred):
        raise ValueError("Labels and predictions must cover exactly the same complete corpus")
    if len({p.policy_version for p in predictions}) != 1:
        raise ValueError("Evaluate one frozen policy version at a time")
    for case in cases:
        label = gold[case.id]
        if not set(map(str, label.evidence_urls)) <= {str(e.url) for e in case.evidence}:
            raise ValueError("Label cites evidence outside the frozen case")
        if label.reviewed_at < case.as_of:
            raise ValueError("Gold review predates evaluated information cutoff")
    baseline = {}
    for c in cases:
        recent = (c.as_of - max(e.available_at for e in c.evidence)).total_seconds() <= 30 * 86400
        match = recent and bool(re.search(r"\b" + c.ticker + r"\b", c.headline, re.I))
        baseline[c.id] = Prediction(
            case_id=c.id,
            matched=match,
            decision="storybook" if match else "suppressed",
            policy_version="B0-keyword-recency-v1",
            trace_sha256=digest(c.model_dump(mode="json")),
        )
    partitions = {}
    for part in ("development", "calibration", "holdout"):
        subset = [c for c in cases if split.partition(c) == part]
        b0 = summarize(subset, gold, baseline)
        # Keyword matching is not a notification policy; do not infer push intent.
        b0["push"] = None
        partitions[part] = {"B0": b0, "V0": summarize(subset, gold, pred)}
    events = {c.canonical_key for c in cases}
    # An irrelevant narrative pair must not turn a positive event into a hard negative.
    negatives = {
        event
        for event in events
        if all(
            gold[c.id].negative_or_irrelevant_or_reprint for c in cases if c.canonical_key == event
        )
    }
    indirect = {
        c.canonical_key
        for c in cases
        if gold[c.id].is_relevant and gold[c.id].valid_path and gold[c.id].hops == 2
    }
    return {
        "version": "historical-eval-v1",
        "dataset_sha256": manifest["dataset_sha256"],
        "labels_sha256": digest(
            [g.model_dump(mode="json") for g in sorted(labels, key=lambda x: x.case_id)]
        ),
        "predictions_sha256": digest(
            [p.model_dump(mode="json") for p in sorted(predictions, key=lambda x: x.case_id)]
        ),
        "is_synthetic": manifest["is_synthetic"],
        "pairs": len(cases),
        "events": len(events),
        "corpus_checks": {
            "50_to_100_events": 50 <= len(events) <= 100,
            "five_tickers": {c.ticker for c in cases} == {"MU", "NVDA", "AMD", "DELL", "SNDK"},
            "30_percent_negatives": len(negatives) / len(events) >= 0.3,
            "20_two_hop_events": len(indirect) >= 20,
            "all_splits_nonempty": all(
                any(split.partition(c) == p for c in cases)
                for p in ("development", "calibration", "holdout")
            ),
        },
        "partitions": partitions,
        "holdout_by_ticker": {
            ticker: summarize(
                [c for c in cases if c.ticker == ticker and split.partition(c) == "holdout"],
                gold,
                pred,
            )
            for ticker in ("MU", "NVDA", "AMD", "DELL", "SNDK")
        },
        "quality_disagreements": [
            {
                "case_id": c.id,
                "partition": split.partition(c),
                "relevance_mismatch": gold[c.id].is_relevant != pred[c.id].matched,
                "push_mismatch": gold[c.id].should_push != (pred[c.id].decision == "push"),
            }
            for c in cases
            if gold[c.id].is_relevant != pred[c.id].matched
            or gold[c.id].should_push != (pred[c.id].decision == "push")
        ],
        "B1": {"status": "UNAVAILABLE", "reason": "LLM_MODE=none"},
        "release_decision": "NO_GO",
        "release_reason": "Tooling alone cannot attest source authenticity, pre-tuning holdout freeze, trace integrity or production readiness",
        "interval_note": "Wilson intervals are descriptive per pair; correlated event/narrative pairs are not independent trials",
    }
