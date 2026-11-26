"""Local, frozen article/narrative relevance audit; never financial impact accuracy.

Reference labels may be AI-authored development judgments, not independent gold.
The packet intentionally omits predictions and literal matching rules.
"""

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from engine.company_profiles import available_bundles
from engine.ingestion.contracts import digest
from engine.models.schema_v13 import news_items, news_revisions, news_sources
from engine.profile_news import candidate_feed, verified_row


def write_new(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def shingles(payload):
    words = re.findall(r"\w+", (payload.get("title", "") + " "
                               + payload.get("summary", "")).casefold())
    return {tuple(words[i:i + 3]) for i in range(max(1, len(words) - 2))} if words else set()


def prior_exposure(packet_paths):
    clusters, texts, hashes = set(), [], []
    for path in packet_paths:
        packet = json.loads(path.read_text(encoding="utf-8"))
        receipt = json.loads(path.with_name("freeze.json").read_text(encoding="utf-8"))
        sha = digest(packet)
        if sha != receipt["packet_sha256"]:
            raise ValueError("Prior exposure packet integrity mismatch")
        hashes.append(sha)
        for row in packet:
            if row["cluster"] not in clusters:
                texts.append(shingles(row["article"]))
            clusters.add(row["cluster"])
    return clusters, texts, hashes


def overlaps(text, previous):
    return any(text and old and len(text & old) / len(text | old) >= 0.8 for old in previous)


STRATA = {
    "finance": r"\b(financ\w*|fund\w*|loan\w*|credit|capital|investment|acquisition|acquire)\b",
    "policy": r"\b(permit\w*|regulat\w*|ban\w*|tax\w*|approval|approved|opposition|planning)\b",
    "capacity": r"\b(compute|computing|capacity|power|construction|build\w*|chip\w*|GPU\w*|wafer\w*)\b",
}


def stratum(payload, definitions=None):
    """Sampling only; deliberately separate from profile rules and predictions."""
    text = payload.get("title", "") + " " + payload.get("summary", "")
    return next((name for name, expression in (definitions or STRATA).items()
                 if re.search(expression, text, re.I)), "other")


def sample_articles(rows, count, stratified):
    if not stratified:
        return rows[:count]
    buckets = {k: [r for r in rows if stratum(r["payload"]) == k]
               for k in [*STRATA, "other"]}
    selected: list = []
    # Round robin by topic; within each topic preserve deterministic recency order.
    while any(buckets.values()) and len(selected) < count:
        for bucket in buckets.values():
            if bucket and len(selected) < count:
                selected.append(bucket.pop(0))
    return selected


def freeze(conn, output: Path, *, count=60, at=None, exclude_packets=(),
           stratified=False, max_age_days=None, prediction_track="feed",
           profile_root=None, scan_limit=500, source_quotas=None, exclude_title_pattern=None):
    if prediction_track not in {"feed", "text_relevance"}:
        raise ValueError("Unknown prediction track")
    if not 1 <= count <= 100:
        raise ValueError("Choose 1..100 article clusters")
    if not 1 <= scan_limit <= 5000:
        raise ValueError("Choose 1..5000 scan rows")
    if source_quotas and (any(type(v) is not int or v < 0 for v in source_quotas.values())
                          or sum(source_quotas.values()) > count):
        raise ValueError("Source quotas must fit the cluster budget")
    max_window = 365 if prediction_track == "text_relevance" else 30
    if max_age_days is not None and not 1 <= max_age_days <= max_window:
        raise ValueError(f"Age window must be 1..{max_window} days")
    at = at or datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Aware, nonfuture cutoff required")
    profiles = available_bundles(at, root=profile_root)
    if not profiles["enabled"] or profiles.get("withheld") or profiles.get("truncated"):
        raise ValueError("Profiles disabled, withheld or truncated")
    prediction = candidate_feed(conn, at, profile_root=profile_root, limit=scan_limit, card_limit=1000)
    if prediction["truncated"]:
        raise ValueError("Truncated routing cannot be evaluated as full coverage")
    rows = conn.execute(select(news_items,
        news_revisions.c.payload.label("revision_payload"), news_revisions.c.received_at,
        news_revisions.c.capture_sha256, news_sources.c.config.label("source_config")).join(
        news_revisions, (news_revisions.c.item_id == news_items.c.id)
        & (news_revisions.c.version == news_items.c.version)).join(
        news_sources, news_sources.c.id == news_items.c.source_id).order_by(
        news_revisions.c.received_at.desc(), news_items.c.id).limit(scan_limit + 1)).mappings().all()
    if len(rows) > scan_limit:
        raise ValueError("Inbox window truncated")
    groups: dict = {}
    blocked: set = set()
    cache: dict = {}
    for r in rows:
        key = r["article_key"]
        try:
            verified_row(r, at, cache)
        except (ValueError, TypeError, KeyError, OSError):
            if r["source_config"].get("enabled"):
                blocked.add(key)
            continue
        if key in groups and any(groups[key]["payload"].get(k) != r["payload"].get(k)
                                 for k in ("title", "summary")):
            blocked.add(key)
        groups.setdefault(key, r)
    prior_clusters, prior_texts, prior_hashes = prior_exposure(exclude_packets)
    articles: list = []
    selected_texts: list = []
    excluded_exposure = excluded_near_duplicates = 0
    excluded_age = excluded_title = 0
    for key, r in groups.items():
        if key in blocked:
            continue
        if exclude_title_pattern and re.search(exclude_title_pattern, r["payload"]["title"], re.I):
            excluded_title += 1
            continue
        if max_age_days is not None and datetime.fromisoformat(r["payload"]["published_at"]) < (
                at - timedelta(days=max_age_days)):
            excluded_age += 1
            continue
        text = shingles(r["payload"])
        if key in prior_clusters or overlaps(text, prior_texts):
            excluded_exposure += 1
            continue
        if overlaps(text, selected_texts):
            excluded_near_duplicates += 1
            continue
        articles.append(r)
        selected_texts.append(text)
    quota_rows = []
    for source, quota in (source_quotas or {}).items():
        quota_rows.extend([r for r in articles if r["source_id"] == source][:quota])
    quota_ids = {r["id"] for r in quota_rows}
    articles = quota_rows + sample_articles([r for r in articles if r["id"] not in quota_ids],
                                            count - len(quota_rows), stratified)
    if not articles:
        raise ValueError("No eligible articles")
    matched = {c["id"] for c in prediction["items"]}
    packet, predictions, feed_predictions = [], {}, {}
    for r in articles:
        for b in profiles["items"]:
            # Historical example-only profiles have no current RSS bindings.
            if not b.factor_bindings:
                continue
            for n in b.narratives:
                key = digest((r["article_key"], b.id, n.id))
                packet.append({"id": key, "cluster": r["article_key"],
                    "item_id": r["id"], "item_version": r["version"],
                    "capture_sha256": r["capture_sha256"],
                    "payload_sha256": r["content_sha256"], "article": r["payload"],
                    "profile_id": b.id, "profile_version": b.version,
                    "profile_sha256": digest(b.model_dump(mode="json")),
                    "ticker": b.ticker, "narrative": n.model_dump(mode="json"),
                    "sources": [s.model_dump(mode="json", exclude={"file"}) for s in b.sources],
                    "components": [c.model_dump() for c in b.components],
                    "entity_references": [v.model_dump(mode="json") for v in b.entity_references],
                    "relationships": [v.model_dump(mode="json") for v in b.relationships],
                    "nodes": [v.model_dump() for v in b.nodes]})
                feed_predictions[key] = key in matched
                if prediction_track == "text_relevance":
                    from engine.profile_routing import binding_decisions
                    predictions[key] = any(binding_decisions(b, n, r["payload"], at))
                else:
                    predictions[key] = key in matched
    if not packet:
        raise ValueError("No narrative pairs")
    current = available_bundles(at, root=profile_root)
    if (current.get("withheld") or current.get("truncated") or not current["enabled"]
            or digest([b.model_dump(mode="json") for b in current["items"]])
            != digest([b.model_dump(mode="json") for b in profiles["items"]])):
        raise ValueError("Profile registry changed during freeze; retry in a new directory")
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "packet.json", packet)
    write_new(output / "predictions.json", predictions)
    if prediction_track == "text_relevance":
        write_new(output / "feed_predictions.json", feed_predictions)
    receipt = {"at": at.isoformat(), "packet_sha256": digest(packet),
        "predictions_sha256": digest(predictions), "clusters": len(articles),
        "pairs": len(packet), "sampling": "LATEST_VALID_DEDUPLICATED_URLS",
        "excluded_conflicting_or_invalid_clusters": len(blocked),
        "excluded_prior_exposure": excluded_exposure,
        "excluded_near_duplicates": excluded_near_duplicates,
        "excluded_age": excluded_age,
        "excluded_title": excluded_title,
        "exclude_title_pattern": exclude_title_pattern,
        "source_quotas": source_quotas,
        "sampling_sources": dict(Counter(r["source_id"] for r in articles)),
        "source_quota_shortfalls": {source: max(0, quota - sum(
            r["source_id"] == source for r in articles)) for source, quota in (source_quotas or {}).items()},
        "scan_limit": scan_limit,
        "max_age_days": max_age_days,
        "sampling_strata": dict(Counter(stratum(r["payload"]) for r in articles)),
        "prior_packet_sha256": prior_hashes,
        "requested_clusters": count,
        "mode": "DEVELOPMENT_RELEVANCE_AUDIT_NOT_INDEPENDENT_GOLD", "delivery": "disabled"}
    receipt["prediction_track"] = prediction_track
    if prediction_track == "text_relevance":
        receipt["feed_predictions_sha256"] = digest(feed_predictions)
        receipt["prediction_scope"] = "Current-profile text relevance; freshness eligibility frozen separately; not historical as-of"
    if stratified:
        receipt["sampling"] = "TOPIC_ROUND_ROBIN_NOT_PREDICTION_SELECTED"
        receipt["strata_definitions"] = STRATA
    write_new(output / "freeze.json", receipt)
    return receipt


def evaluate(directory: Path, labels_path: Path):
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    packet, predictions, frozen = read("packet.json"), read("predictions.json"), read("freeze.json")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    if frozen.get("prediction_track") == "full_article_relevance":
        from engine.evaluation.article_relevance import verify_frozen
        verify_frozen(directory, packet, frozen)
    if frozen.get("prediction_track") == "text_relevance":
        feed_predictions = read("feed_predictions.json")
        if (digest(feed_predictions) != frozen.get("feed_predictions_sha256")
                or set(feed_predictions) != set(predictions)
                or any(type(v) is not bool for v in feed_predictions.values())):
            raise ValueError("Frozen feed eligibility artifact mismatch")
    if (digest(packet) != frozen["packet_sha256"]
            or digest(predictions) != frozen["predictions_sha256"]
            or labels["packet_sha256"] != frozen["packet_sha256"]):
        raise ValueError("Frozen artifact or label packet mismatch")
    ids = {r["id"] for r in packet}
    votes = labels["labels"]
    if (len(ids) != len(packet) or set(predictions) != ids
            or any(type(v) is not bool for v in predictions.values())
            or len(votes) != len(ids) or {v["id"] for v in votes} != ids):
        raise ValueError("Exactly one prediction and reference per pair required")
    if labels["reference_kind"] not in {"AI_DEVELOPMENT_REVIEW", "HUMAN_REVIEW",
                                        "AI_CONSENSUS_REVIEW"}:
        raise ValueError("Explicit reference provenance required")
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "unresolved": 0}
    by_narrative: dict = {}
    by_stratum: dict = {}
    rows = {r["id"]: r for r in packet}
    selected_unresolved = 0
    errors = []
    for v in votes:
        if not v.get("rationale", "").strip():
            raise ValueError("Reference rationale required")
        target = v["relevance"]
        row = rows[v["id"]]
        narrative = row["profile_id"] + ":" + row["narrative"]["id"]
        topic = stratum(row["article"], frozen.get("strata_definitions"))
        groups = [counts, by_narrative.setdefault(narrative, dict.fromkeys(counts, 0)),
                  by_stratum.setdefault(topic, dict.fromkeys(counts, 0))]
        if target == "INSUFFICIENT_CONTEXT":
            for group in groups:
                group["unresolved"] += 1
            selected_unresolved += int(predictions[v["id"]])
            continue
        if target not in {"RELEVANT", "NOT_RELEVANT"}:
            raise ValueError("Unknown reference label")
        pred = predictions[v["id"]]
        outcome = ("t" if pred == (target == "RELEVANT") else "f") + ("p" if pred else "n")
        for group in groups:
            group[outcome] += 1
        if outcome in {"fp", "fn"}:
            errors.append({"id": v["id"], "outcome": outcome})
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    for group in [*by_narrative.values(), *by_stratum.values()]:
        a, b, c = group["tp"], group["fp"], group["fn"]
        group["precision"] = a / (a + b) if a + b else None
        group["recall"] = a / (a + c) if a + c else None
    return {**counts, "clusters": frozen["clusters"], "pairs": len(packet),
        "selected_unresolved": selected_unresolved,
        "resolved_fraction": (len(packet) - counts["unresolved"]) / len(packet),
        "by_narrative": by_narrative, "by_stratum": by_stratum,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "reference_kind": labels["reference_kind"], "independent_gold": False,
        "prediction_track": frozen.get("prediction_track", "feed"),
        "packet_sha256": frozen["packet_sha256"], "labels_sha256": digest(labels),
        "errors": errors, "delivery": "disabled",
        "limitations": [("Curated full-body convenience sample; pairs are correlated within articles"
                         if frozen.get("prediction_track") == "full_article_relevance" else
                         "Latest-URL convenience sample; pairs are correlated within articles"),
                        "Unknown references excluded, never counted as negatives",
                        "Relevance only, not financial impact or push accuracy"]}


def consensus(directory: Path, review_paths):
    """Two declared independent reviews; disagreements remain unresolved, never majority-guessed."""
    if len(review_paths) != 2:
        raise ValueError("Exactly two independent review files required")
    packet = json.loads((directory / "packet.json").read_text(encoding="utf-8"))
    frozen = json.loads((directory / "freeze.json").read_text(encoding="utf-8"))
    if digest(packet) != frozen["packet_sha256"]:
        raise ValueError("Packet changed")
    ids = {r["id"] for r in packet}
    reviewers, reviews, hashes = set(), [], []
    for path in review_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        reviewed_at = datetime.fromisoformat(data["reviewed_at"])
        if (data["packet_sha256"] != frozen["packet_sha256"]
                or data["reference_kind"] != "AI_INDEPENDENT_REVIEW"
                or data.get("predictions_accessed") is not False
                or data.get("peer_labels_accessed") is not False
                or not data.get("reviewer_id", "").strip()
                or data["reviewer_id"] in reviewers
                or reviewed_at.tzinfo is None
                or not datetime.fromisoformat(frozen["at"]) <= reviewed_at <= datetime.now(UTC)):
            raise ValueError("Independent reviewer identity, time or declarations invalid")
        votes = data["labels"]
        if len(votes) != len(ids) or {v["id"] for v in votes} != ids:
            raise ValueError("Review coverage incomplete or duplicated")
        for v in votes:
            if (v["relevance"] not in {"RELEVANT", "NOT_RELEVANT", "INSUFFICIENT_CONTEXT"}
                    or not v.get("rationale", "").strip()):
                raise ValueError("Invalid reference label")
        reviewers.add(data["reviewer_id"])
        reviews.append({v["id"]: v for v in votes})
        hashes.append(digest(data))
    labels, disagreements = [], 0
    for row in packet:
        a, b = (r[row["id"]] for r in reviews)
        agree = a["relevance"] == b["relevance"]
        disagreements += int(not agree)
        labels.append({"id": row["id"],
                       "relevance": a["relevance"] if agree else "INSUFFICIENT_CONTEXT",
                       "rationale": "Reviewer A: " + a["rationale"] + " Reviewer B: " + b["rationale"]})
    return {"packet_sha256": frozen["packet_sha256"], "reference_kind": "AI_CONSENSUS_REVIEW",
            "reviewer_ids": sorted(reviewers), "review_sha256": hashes,
            "disagreements": disagreements, "independent_gold": False,
            "independence_basis": "Declared separate contexts, not filesystem isolation or human truth",
            "labels": labels}


def main():
    import argparse

    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "evaluate", "consensus"])
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--exclude-packet", type=Path, action="append", default=[])
    parser.add_argument("--review", type=Path, action="append", default=[])
    parser.add_argument("--stratified", action="store_true")
    parser.add_argument("--max-age-days", type=int)
    parser.add_argument("--prediction-track", choices=["feed", "text_relevance"], default="feed")
    args = parser.parse_args()
    if args.action == "freeze":
        db = database()
        try:
            with db.connect() as conn:
                result = freeze(conn, args.directory, count=args.count,
                                exclude_packets=args.exclude_packet, stratified=args.stratified,
                                max_age_days=args.max_age_days, prediction_track=args.prediction_track)
        finally:
            db.dispose()
    elif args.action == "consensus":
        result = consensus(args.directory, args.review)
        write_new(args.directory / "consensus.json", result)
        result = {"pairs": len(result["labels"]), "disagreements": result["disagreements"],
                  "reference_kind": result["reference_kind"], "delivery": "disabled"}
    else:
        if not args.labels:
            parser.error("--labels required")
        result = evaluate(args.directory, args.labels)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
