"""Local, frozen article/narrative relevance audit; never financial impact accuracy.

Reference labels may be AI-authored development judgments, not independent gold.
The packet intentionally omits predictions and literal matching rules.
"""

import json
from datetime import UTC, datetime
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


def freeze(conn, output: Path, *, count=60, at=None):
    if not 1 <= count <= 100:
        raise ValueError("Choose 1..100 article clusters")
    at = at or datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Aware, nonfuture cutoff required")
    profiles = available_bundles(at)
    if not profiles["enabled"] or profiles.get("withheld") or profiles.get("truncated"):
        raise ValueError("Profiles disabled, withheld or truncated")
    prediction = candidate_feed(conn, at)
    if prediction["truncated"]:
        raise ValueError("Truncated routing cannot be evaluated as full coverage")
    rows = conn.execute(select(news_items,
        news_revisions.c.payload.label("revision_payload"), news_revisions.c.received_at,
        news_revisions.c.capture_sha256, news_sources.c.config.label("source_config")).join(
        news_revisions, (news_revisions.c.item_id == news_items.c.id)
        & (news_revisions.c.version == news_items.c.version)).join(
        news_sources, news_sources.c.id == news_items.c.source_id).order_by(
        news_revisions.c.received_at.desc(), news_items.c.id).limit(501)).mappings().all()
    if len(rows) > 500:
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
    articles = [r for key, r in groups.items() if key not in blocked][:count]
    if not articles:
        raise ValueError("No eligible articles")
    matched = {c["id"] for c in prediction["items"]}
    packet, predictions = [], {}
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
                    "relationships": [v.model_dump(mode="json") for v in b.relationships],
                    "nodes": [v.model_dump() for v in b.nodes]})
                predictions[key] = key in matched
    if not packet:
        raise ValueError("No narrative pairs")
    current = available_bundles(at)
    if (current.get("withheld") or current.get("truncated") or not current["enabled"]
            or digest([b.model_dump(mode="json") for b in current["items"]])
            != digest([b.model_dump(mode="json") for b in profiles["items"]])):
        raise ValueError("Profile registry changed during freeze; retry in a new directory")
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "packet.json", packet)
    write_new(output / "predictions.json", predictions)
    receipt = {"at": at.isoformat(), "packet_sha256": digest(packet),
        "predictions_sha256": digest(predictions), "clusters": len(articles),
        "pairs": len(packet), "sampling": "LATEST_VALID_DEDUPLICATED_URLS",
        "excluded_conflicting_or_invalid_clusters": len(blocked),
        "mode": "DEVELOPMENT_RELEVANCE_AUDIT_NOT_INDEPENDENT_GOLD", "delivery": "disabled"}
    write_new(output / "freeze.json", receipt)
    return receipt


def evaluate(directory: Path, labels_path: Path):
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    packet, predictions, frozen = read("packet.json"), read("predictions.json"), read("freeze.json")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
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
    if labels["reference_kind"] not in {"AI_DEVELOPMENT_REVIEW", "HUMAN_REVIEW"}:
        raise ValueError("Explicit reference provenance required")
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "unresolved": 0}
    errors = []
    for v in votes:
        if not v.get("rationale", "").strip():
            raise ValueError("Reference rationale required")
        target = v["relevance"]
        if target == "INSUFFICIENT_CONTEXT":
            counts["unresolved"] += 1
            continue
        if target not in {"RELEVANT", "NOT_RELEVANT"}:
            raise ValueError("Unknown reference label")
        pred = predictions[v["id"]]
        outcome = ("t" if pred == (target == "RELEVANT") else "f") + ("p" if pred else "n")
        counts[outcome] += 1
        if outcome in {"fp", "fn"}:
            errors.append({"id": v["id"], "outcome": outcome})
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    return {**counts, "clusters": frozen["clusters"], "pairs": len(packet),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "reference_kind": labels["reference_kind"], "independent_gold": False,
        "packet_sha256": frozen["packet_sha256"], "labels_sha256": digest(labels),
        "errors": errors, "delivery": "disabled",
        "limitations": ["Latest-URL convenience sample; pairs are correlated within articles",
                        "Unknown references excluded, never counted as negatives",
                        "Relevance only, not financial impact or push accuracy"]}


def main():
    import argparse

    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "evaluate"])
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--count", type=int, default=60)
    args = parser.parse_args()
    if args.action == "freeze":
        db = database()
        try:
            with db.connect() as conn:
                result = freeze(conn, args.directory, count=args.count)
        finally:
            db.dispose()
    else:
        if not args.labels:
            parser.error("--labels required")
        result = evaluate(args.directory, args.labels)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
