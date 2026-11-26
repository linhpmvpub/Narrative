"""Local, exposed-corpus relevance calibration. Never a fresh holdout or impact model."""

import hashlib
import itertools
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from engine.adapters.news import canonical_url
from engine.atlas_freeze import runtime_fingerprint
from engine.company_profiles import available_bundles
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.evaluation.profile_relevance import evaluate as evaluate_original
from engine.evaluation.profile_relevance import overlaps, shingles, write_new
from engine.ingestion.contracts import digest
from engine.profile_news import entity_context
from engine.profile_routing import binding_decisions

# Sampling strata, not inferred causal mechanisms. A story may have several topics.
TOPICS = {
    "supply_disruption": r"\b(shortage|disrupt\w*|supply|supplier|logistics|outage)\b",
    "input_price": r"\b(prices?|pricing|costs?|commodity|commodities|inflation)\b",
    "capacity": r"\b(capacity|buildout|construction|deployment|facilit\w*|factories|factory)\b",
    "demand": r"\b(demand|orders?|sales|revenue|customers?)\b",
    "technology": r"\b(technology|chips?|processors?|gpu|gpus|memory|semiconductor\w*)\b",
    "financing": r"\b(financ\w*|funding|debt|loan\w*|investment|capital)\b",
    "policy": r"\b(licen[cs]\w*|permit\w*|regulat\w*|tariff\w*|export|sanctions?)\b",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def connected_clusters(rows):
    """Conservative transitive grouping: never split aliases/near-duplicate chains."""
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    keys: dict = {}
    texts: dict = {}
    for i, row in enumerate(rows):
        article, archive = row["article"], row.get("archive_source", {})
        aliases = [("cluster", row["cluster"])]
        if article.get("url"):
            aliases.append(("url", canonical_url(article["url"])))
        for key in ("source_sha256", "cluster_key"):
            if archive.get(key):
                aliases.append((key, archive[key]))
        aliases.append(("text", digest([article.get("title", ""), article.get("summary", "")])))
        for alias in aliases:
            if alias in keys:
                parent[find(i)] = find(keys[alias])
            keys[alias] = i
        fingerprint = aliases[-1]
        if fingerprint not in texts:
            text = shingles(article)
            for j, previous in texts.values():
                if text and previous and overlaps(text, [previous]):
                    parent[find(i)] = find(j)
            texts[fingerprint] = (i, text)
    members: dict = {}
    for i, row in enumerate(rows):
        members.setdefault(find(i), []).append(row["id"])
    ids = {k: digest(sorted(v)) for k, v in members.items()}
    return [ids[find(i)] for i in range(len(rows))]


def metrics(rows, prediction):
    counts = dict.fromkeys(["tp", "fp", "tn", "fn", "unresolved"], 0)
    positive: set[str] = set()
    negative: set[str] = set()
    selected_positive: set[str] = set()
    selected_unresolved = 0
    for row in rows:
        pred, label = bool(prediction(row)), row["label"]
        if label == "INSUFFICIENT_CONTEXT":
            counts["unresolved"] += 1
            selected_unresolved += pred
            continue
        if label not in {"RELEVANT", "NOT_RELEVANT"}:
            raise ValueError("Unknown reference label")
        truth = label == "RELEVANT"
        (positive if truth else negative).add(row["event_cluster"])
        if truth and pred:
            selected_positive.add(row["event_cluster"])
        counts[("t" if pred == truth else "f") + ("p" if pred else "n")] += 1
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    return {**counts, "pairs": len(rows), "clusters": len({r["event_cluster"] for r in rows}),
            "positive_clusters": len(positive), "negative_clusters": len(negative),
            "selected_positive_clusters": len(selected_positive),
            "selected_unresolved": selected_unresolved,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "unresolved_fraction": counts["unresolved"] / len(rows) if rows else None}


def report(rows, prediction):
    return {"overall": metrics(rows, prediction),
            "by_group": {g: metrics([r for r in rows if g in r["groups"]], prediction)
                         for g in [*TOPICS, "other"]},
            "by_ticker": {t: metrics([r for r in rows if r["ticker"] == t], prediction)
                          for t in ("AMD", "DELL", "MU", "NVDA", "SNDK")}}


def group_gaps(result, criteria):
    """Counts are diagnostics only: exposed data cannot establish independent support."""
    gaps = {}
    for group in criteria["groups"]:
        m = result["by_group"][group]
        checks = {
            "clusters": m["clusters"] >= criteria["minimum_independent_event_clusters_per_group"],
            "positive_clusters": m["positive_clusters"] >= criteria["minimum_resolved_positive_clusters_per_group"],
            "negative_clusters": m["negative_clusters"] >= criteria["minimum_resolved_negative_clusters_per_group"],
            "precision": m["precision"] is not None and m["precision"] >= criteria["minimum_precision"],
            "recall": m["recall"] is not None and m["recall"] >= criteria["minimum_recall"],
            "unresolved": m["unresolved_fraction"] is not None
            and m["unresolved_fraction"] <= criteria["maximum_unresolved_fraction"],
        }
        gaps[group] = [k for k, ok in checks.items() if not ok]
    return gaps


def prepare(cohorts, profile_root, output, plan):
    """Lock current predictions/features/splits before reading reference labels."""
    output = Path(output)
    if output.exists():
        raise ValueError("New output directory required")
    at = datetime.now(UTC)
    before = runtime_fingerprint()
    registry = available_bundles(at, root=Path(profile_root))
    if not registry["enabled"] or registry["withheld"] or registry["truncated"]:
        raise ValueError("Complete source-validated profile registry required")
    bundles = {b.id: b for b in registry["items"]}
    policy = read(POLICY)
    rows, receipts = [], []
    excluded: Counter[str] = Counter()
    for directory in sorted(map(Path, cohorts)):
        packet, frozen = read(directory / "packet.json"), read(directory / "freeze.json")
        predictions = read(directory / "predictions.json")
        if (digest(packet) != frozen["packet_sha256"]
                or digest(predictions) != frozen["predictions_sha256"]):
            raise ValueError("Prior frozen artifacts changed")
        receipts.append({"directory": str(directory.resolve()), "freeze_sha256": digest(frozen),
                         "packet_sha256": digest(packet),
                         "label_file_sha256": hashlib.sha256(
                             (directory / "consensus.json").read_bytes()).hexdigest()})
        for row in packet:
            bundle = bundles.get(row["profile_id"])
            narrative = next((n for n in bundle.narratives if n.id == row["narrative"]["id"]),
                             None) if bundle else None
            if not narrative or narrative.model_dump(mode="json") != row["narrative"]:
                excluded["changed_or_missing_narrative"] += 1
                continue
            article = row["article"]
            track = ("full_article" if "article_basis" in row else
                     "archive" if "archive_source" in row else "rss")
            links = []
            # Full-body source boundaries differ from RSS windows: audit original
            # predictions separately, never mix them into the RSS weight search.
            if track != "full_article":
                for d in binding_decisions(bundle, narrative, article, at,
                                           issuer_cik=row.get("archive_source", {}).get("cik")):
                    if d["paths_truncated"] or len(d["path"]) > policy["max_hops"]:
                        continue
                    ref = d["binding"].entity_reference_id
                    links.append({"matches": d["matches"],
                                  "entity_context": entity_context(bundle, ref, article, at)
                                  if ref else None})
            activity = assess({"headline": article.get("title", ""),
                               "excerpt": article.get("summary", "")}, links, policy)
            text = article.get("title", "") + " " + article.get("summary", "")
            groups = [g for g, pattern in TOPICS.items() if re.search(pattern, text, re.I)]
            rows.append({**row, "id": digest([directory.name, row["id"]]),
                         "reference_id": row["id"], "cohort": directory.name, "track": track,
                         "groups": groups or ["other"], "matched": bool(links),
                         "baseline_selected": bool(links) and activity["tier"] not in
                         {"BACKGROUND_THEME", "SPONSORED_RESEARCH"},
                         "activity": activity, "resolved_entity": any(
                             link["entity_context"] for link in links),
                         "concrete_change": bool(activity["signals"]),
                         "sponsored": activity["sponsored"]})
    clusters = connected_clusters(rows)
    for row, cluster in zip(rows, clusters, strict=True):
        row["event_cluster"] = cluster
        row["split"] = "calibration" if int(cluster[:8], 16) % 10 < 7 else "development_validation"
    if runtime_fingerprint() != before:
        raise ValueError("Runtime changed during prediction freeze")
    after = available_bundles(at, root=Path(profile_root))
    hashes = [digest(b.model_dump(mode="json")) for b in registry["items"]]
    if hashes != [digest(b.model_dump(mode="json")) for b in after["items"]]:
        raise ValueError("Profiles changed during freeze")
    output.mkdir(parents=True)
    frozen = {"at": at.isoformat(), "rows_sha256": digest(rows), "receipts": receipts,
              "profile_sha256": hashes, "runtime": before, "policy": policy,
              "plan": plan, "plan_sha256": digest(plan), "topics": TOPICS,
              "excluded": dict(excluded), "data_status": "EXPOSED_DEVELOPMENT_ONLY",
              "delivery": "disabled"}
    write_new(output / "rows.json", rows)
    write_new(output / "freeze.json", frozen)
    return {"pairs": len(rows), "clusters": len(set(clusters)), "excluded": dict(excluded),
            "freeze_sha256": digest(frozen)}


def candidate_selected(row, weights, threshold):
    # Sponsorship is a visibility policy, never overridden by a fitted score.
    if not row["matched"] or row["sponsored"]:
        return False
    score = (weights["sourced_path"] + weights["resolved_entity"] * row["resolved_entity"]
             + weights["concrete_change"] * row["concrete_change"])
    return score >= threshold


def search(rows, grid, baseline_weights):
    """Only calibration rows enter selection; validation must be passed separately."""
    if any(r["split"] != "calibration" or r["track"] != "rss" for r in rows):
        raise ValueError("Only RSS calibration rows may select weights")
    candidates = []
    keys = list(baseline_weights)
    for values in itertools.product(*(grid[k] for k in keys)):
        weights = dict(zip(keys, values, strict=True))
        for threshold in grid["threshold"]:
            m = metrics(rows, lambda r, w=weights, t=threshold: candidate_selected(r, w, t))
            if (m["precision"] is not None and m["precision"] >= 0.85
                    and m["selected_positive_clusters"] >= 10):
                distance = sum(abs(weights[k] - baseline_weights[k]) for k in keys)
                candidates.append((m["recall"], m["precision"], -distance, -threshold,
                                   weights, threshold, m))
    if not candidates:
        return {"status": "NO_SUPPORTED_CANDIDATE", "weights": None, "threshold": None}
    best = max(candidates, key=lambda c: c[:4])
    return {"status": "OFFLINE_RELEVANCE_CANDIDATE_NOT_PROMOTED", "weights": best[4],
            "threshold": best[5], "calibration": best[6]}


def evaluate(directory, *, output=None):
    directory = Path(directory)
    frozen, rows = read(directory / "freeze.json"), read(directory / "rows.json")
    if digest(rows) != frozen["rows_sha256"] or digest(frozen["plan"]) != frozen["plan_sha256"]:
        raise ValueError("Frozen replay or plan changed")
    criteria_path = POLICY.parent / "impact-group-acceptance.json"
    if hashlib.sha256(criteria_path.read_bytes()).hexdigest() != frozen["runtime"].get(
            "config/impact-group-acceptance.json"):
        raise ValueError("Predeclared group criteria changed")
    criteria = read(criteria_path)
    references, historical = {}, {}
    for receipt in frozen["receipts"]:
        root = Path(receipt["directory"])
        if (digest(read(root / "freeze.json")) != receipt["freeze_sha256"]
                or hashlib.sha256((root / "consensus.json").read_bytes()).hexdigest()
                != receipt["label_file_sha256"]):
            raise ValueError("Original receipt or reference labels changed")
        result = evaluate_original(root, root / "consensus.json")
        labels = read(root / "consensus.json")
        if (labels["reference_kind"] != "AI_CONSENSUS_REVIEW"
                or len(set(labels.get("reviewer_ids", []))) != 2):
            raise ValueError("Two-reviewer consensus provenance required")
        references[root.name] = {v["id"]: v["relevance"] for v in labels["labels"]}
        historical[root.name] = {k: v for k, v in result.items() if k != "errors"}
    # Identical target and excerpt repeated across cohorts gets one vote. Conflicting
    # previous references stay unresolved; no convenient latest/majority selection.
    unique: dict = {}
    for row in rows:
        key = digest([row["track"], row["profile_id"], row["narrative"], row["article"].get("title"),
                      row["article"].get("summary")])
        label = references[row["cohort"]][row["reference_id"]]
        if key in unique:
            if unique[key]["label"] != label:
                unique[key]["label"] = "INSUFFICIENT_CONTEXT"
        else:
            unique[key] = {**row, "label": label}
    labelled = list(unique.values())
    rss = [r for r in labelled if r["track"] == "rss"]
    calibration = [r for r in rss if r["split"] == "calibration"]
    validation = [r for r in rss if r["split"] == "development_validation"]
    candidate = search(calibration, frozen["plan"]["weights_grid"],
                       frozen["policy"]["priority_weights"])
    result = {"schema": "GROUPED_RELEVANCE_REVIEW_V1", "delivery": "disabled",
              "data_status": "EXPOSED_DEVELOPMENT_ONLY_NOT_FRESH_HOLDOUT",
              "reference_kind": "PRIOR_TWO_AGENT_AI_CONSENSUS_NOT_HUMAN_GOLD",
              "freeze_sha256": digest(frozen), "excluded": frozen["excluded"],
              "duplicates_collapsed": len(rows) - len(labelled), "historical": historical,
              "candidate": candidate, "release_accepted": False,
              "deployment": "UNCHANGED_NO_PROMOTION_FROM_EXPOSED_LABELS",
              "tracks": {}}
    for track in ("rss", "archive"):
        selected = [r for r in labelled if r["track"] == track]
        result["tracks"][track] = {
            "routing": report(selected, lambda r: r["matched"]),
            "priority": report(selected, lambda r: r["baseline_selected"])}
    result["rss_splits"] = {
        name: {"routing": report(part, lambda r: r["matched"]),
               "baseline": report(part, lambda r: r["baseline_selected"]),
               "candidate": report(part, lambda r: candidate_selected(
                   r, candidate["weights"], candidate["threshold"])) if candidate["weights"] else None}
        for name, part in (("calibration", calibration), ("development_validation", validation))}
    result["criteria"] = criteria
    result["group_diagnostic_gaps"] = {
        "routing": group_gaps(result["tracks"]["rss"]["routing"], criteria),
        "priority": group_gaps(result["tracks"]["rss"]["priority"], criteria),
    }
    result["calibration_feature_support"] = [
        {"resolved_entity": entity, "concrete_change": change, "sponsored": sponsored,
         **metrics([r for r in calibration if r["matched"]
                    and (r["resolved_entity"], r["concrete_change"], r["sponsored"])
                    == (entity, change, sponsored)], lambda r: True)}
        for entity, change, sponsored in itertools.product((False, True), repeat=3)]
    result["weight_identifiability"] = (
        "Sourced-path weight is constant for eligible cards; sponsorship is a hard exclusion. "
        "Several weight/threshold combinations select identical cards. Selected weights are "
        "not separately estimated relationship strengths; tie-break retains baseline values.")
    result["limitations"] = [
        "All prior cohorts exposed; the validation split is NOT a new blind holdout",
        "Current-profile text replay excludes feed freshness/lifecycle eligibility",
        "Exact narrative equality does not erase changes in profile evidence since review",
        "Connected lexical/URL/document clusters are conservative, not verified economic identity",
        "Multi-label topic strata overlap and are not verified causal mechanisms",
        "Full-body predictions remain in historical reports, not RSS fitting",
        "Relevance labels cannot calibrate financial magnitude, lag or personal push utility",
        "Prior reviewer declarations are provenance, not independent human validation"]
    destination = Path(output) if output is not None else directory
    if output is not None:
        destination.mkdir(parents=True, exist_ok=False)
    write_new(destination / "labelled-replay.json", labelled)
    write_new(destination / "evaluation.json", result)
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "evaluate"])
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--cohort-root", type=Path, default=Path("source-cache"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.plan is None or args.profiles is None:
            parser.error("--plan and --profiles required")
        plan = read(args.plan)
        result = prepare([args.cohort_root / name for name in plan["cohorts"]],
                         args.profiles, args.directory, plan)
    else:
        report_result = evaluate(args.directory, output=args.output)
        result = {"candidate": report_result["candidate"], "delivery": "disabled",
                  "data_status": report_result["data_status"], "release_accepted": False}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
