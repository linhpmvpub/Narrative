"""Offline text-routing challenge with CURRENT profiles, never point-in-time replay."""

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from engine.company_profiles import available_bundles
from engine.evaluation.profile_relevance import evaluate as evaluate_pairs
from engine.evaluation.profile_relevance import overlaps, shingles, write_new
from engine.evaluation.prospective import Paragraphs
from engine.ingestion.contracts import digest
from engine.profile_routing import binding_decisions

TRACK = "ARCHIVED_TEXT_CURRENT_PROFILE_CHALLENGE"
# Sampling vocabulary is fixed independently of profile rules and predictions.
PARTY = re.compile(r"\b(TSMC|Taiwan Semiconductor|GlobalFoundries|OpenAI|Microsoft|"
                   r"Samsung|Intel|WDC|Western Digital|Sandisk)\b", re.I)
SCOPE = re.compile(r"\b(affiliate|subsidiar\w*|competitor\w*|customer\w*|supplier\w*)\b", re.I)


def text_prediction(bundle, narrative, article, at, *, issuer_cik=None):
    """Shared literal/identity/path primitives only; excludes ingestion and age gates."""
    return next(binding_decisions(bundle, narrative, article, at, issuer_cik=issuer_cik), None) is not None


def select_passages(archive, count, exclude_packets=()):
    """One excerpt/issuer-period; exclude previous passages and near duplicates."""
    if not 1 <= count <= 100:
        raise ValueError("Choose 1..100 source clusters")
    collection = json.loads((archive / "collection.json").read_text(encoding="utf-8"))
    old = json.loads((archive / "blind-input.json").read_text(encoding="utf-8"))
    receipt = json.loads((archive / "freeze-receipt.json").read_text(encoding="utf-8"))
    for name, key in (("collection.json", "collection_sha256"),
                      ("blind-input.json", "packet_sha256")):
        if hashlib.sha256((archive / name).read_bytes()).hexdigest() != receipt[key]:
            raise ValueError("Archive receipt mismatch")
    prior = [shingles({"summary": p["text"]}) for c in old["cases"] for p in c["passages"]]
    excluded_documents = set()
    for path in exclude_packets:
        packet = json.loads(path.read_text(encoding="utf-8"))
        frozen = json.loads(path.with_name("freeze.json").read_text(encoding="utf-8"))
        if digest(packet) != frozen["packet_sha256"]:
            raise ValueError("Excluded packet changed")
        for row in packet:
            excluded_documents.add(row["archive_source"]["source_sha256"])
            prior.append(shingles(row["article"]))
    seen = list(prior)
    candidates: dict[str, list] = {"named_party": [], "identity_scope": [], "control": []}
    excluded = 0
    for source in sorted(collection["sources"], key=lambda s: (s["filing_date"], s["ticker"])):
        if source["source_sha256"] in excluded_documents:
            continue
        path = (archive / source["file"]).resolve()
        if not path.is_relative_to(archive.resolve()):
            raise ValueError("Source escapes archive")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["source_sha256"]:
            raise ValueError("Archive source changed")
        acquired = datetime.fromisoformat(source["retrieved_at"])
        if acquired.tzinfo is None or acquired > datetime.now(UTC):
            raise ValueError("Invalid acquisition clock")
        parser = Paragraphs()
        parser.feed(raw.decode("utf-8"))
        parser.flush()
        for index, text in enumerate(dict.fromkeys(parser.rows)):
            if not 160 <= len(text) <= 1600 or not re.search(r"[a-z]{3} [a-z]{3}", text):
                continue
            article = {"title": "", "summary": text}
            fingerprint = shingles(article)
            if overlaps(fingerprint, prior):
                excluded += 1
                continue
            group = "named_party" if PARTY.search(text) else (
                "identity_scope" if SCOPE.search(text) else "control")
            candidates[group].append({"source": source, "paragraph_index": index,
                                      "article": article, "sampling_stratum": group})
    selected: list = []
    clusters: set = set()
    while any(candidates.values()) and len(selected) < count:
        for bucket in candidates.values():
            while bucket and len(selected) < count:
                row = bucket.pop(0)
                key = row["source"]["cluster_key"]
                fingerprint = shingles(row["article"])
                if key in clusters or overlaps(fingerprint, seen):
                    continue
                selected.append(row)
                clusters.add(key)
                seen.append(fingerprint)
                break
    if not selected:
        raise ValueError("No unused source passages")
    return selected, excluded, digest(collection)


def freeze(archive: Path, output: Path, count=24, exclude_packets=()):
    selected, excluded, collection_sha = select_passages(archive, count, exclude_packets)
    return freeze_selected(selected, output, count, excluded, collection_sha, exclude_packets)


def freeze_selected(selected, output, count, excluded, collection_sha, exclude_packets=(),
                    *, document_previously_exposed=True, extra_receipt=None):
    """Seal a prevalidated source selection before any independent review."""
    at = datetime.now(UTC)
    registry = available_bundles(at)
    if not registry["enabled"] or registry.get("withheld") or registry.get("truncated"):
        raise ValueError("Incomplete current profile registry")
    profiles = [b for b in registry["items"] if b.factor_bindings]
    packet, predictions = [], {}
    for row in selected:
        source = row["source"]
        cluster = digest((source["cluster_key"], source["source_sha256"]))
        for b in profiles:
            for n in b.narratives:
                key = digest((cluster, row["paragraph_index"], b.id, n.id))
                packet.append({"id": key, "cluster": cluster, "article": row["article"],
                    "archive_source": {k: v for k, v in source.items() if k != "file"},
                    "paragraph_index": row["paragraph_index"],
                    "text_sha256": digest(row["article"]["summary"]),
                    "sampling_stratum": row["sampling_stratum"],
                    "document_previously_exposed": document_previously_exposed, "track": TRACK,
                    "profile_id": b.id, "profile_version": b.version,
                    "profile_sha256": digest(b.model_dump(mode="json")), "ticker": b.ticker,
                    "narrative": n.model_dump(mode="json"),
                    "sources": [s.model_dump(mode="json", exclude={"file"}) for s in b.sources],
                    "components": [c.model_dump() for c in b.components],
                    "entity_references": [r.model_dump(mode="json") for r in b.entity_references],
                    "relationships": [r.model_dump(mode="json") for r in b.relationships],
                    "nodes": [v.model_dump() for v in b.nodes]})
                predictions[key] = text_prediction(b, n, row["article"], at,
                                                   issuer_cik=source.get("cik"))
    if not packet:
        raise ValueError("No narrative pairs")
    current = available_bundles(at)
    if (not current["enabled"] or current.get("withheld") or current.get("truncated")
            or digest([b.model_dump(mode="json") for b in registry["items"]])
            != digest([b.model_dump(mode="json") for b in current["items"]])):
        raise ValueError("Profile registry changed")
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "packet.json", packet)
    write_new(output / "predictions.json", predictions)
    receipt = {"at": at.isoformat(), "track": TRACK, "delivery": "disabled",
        "packet_sha256": digest(packet), "predictions_sha256": digest(predictions),
        "collection_sha256": collection_sha, "clusters": len(selected), "pairs": len(packet),
        "excluded_packet_sha256": [digest(json.loads(p.read_text(encoding="utf-8")))
                                   for p in exclude_packets],
        "requested_clusters": count, "excluded_previously_labelled_passages": excluded,
        "sampling_strata": dict(Counter(r["sampling_stratum"] for r in selected)),
        "sampling": "FIXED_PARTY_SCOPE_CONTROL_ROUND_ROBIN_ONE_PER_ISSUER_PERIOD",
        "strict_production_replay_eligible": False, "independent_gold": False,
        "limitations": ["Current profile knowledge applied to old text; not point-in-time replay",
                        "Documents exposed previously; new excerpts are not an unseen holdout",
                        "Text-routing stage only; ingestion and news age gates not evaluated",
                        "Sampling strata are not relevance labels; correlated issuer periods"]}
    if extra_receipt:
        receipt.update(extra_receipt)
    write_new(output / "freeze.json", receipt)
    return receipt


def evaluate(output: Path, labels: Path):
    receipt = json.loads((output / "freeze.json").read_text(encoding="utf-8"))
    if receipt.get("track") != TRACK or receipt.get("strict_production_replay_eligible") is not False:
        raise ValueError("Not an archived current-profile challenge")
    result = evaluate_pairs(output, labels)
    result.update(track=TRACK, strict_production_replay_eligible=False,
                  limitations=receipt["limitations"] + [
                      "AI consensus is not human gold; unresolved labels excluded from precision/recall"])
    result["by_topic_stratum"] = result.pop("by_stratum")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--exclude-packet", type=Path, action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(evaluate(args.output, args.labels) if args.labels else
                     freeze(args.archive, args.output, args.count, args.exclude_packet), indent=2))
