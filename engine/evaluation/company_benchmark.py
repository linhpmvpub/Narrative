"""Frozen direct-company reference, independent AI reviews and reproducible replay."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from engine.company_assessment import assess
from engine.company_discovery import source_decisions
from engine.evaluation.benchmark import local_environment, pin, read, state, tree, verify_pin, write
from engine.evaluation.company_quality import LABELS
from engine.evaluation.grouped_relevance import metrics
from engine.ingestion.contracts import digest

POLICY: dict = {"version": "COMPANY_EFFECTIVENESS_V1", "weights": {"relevance": 0.6, "priority": 0.4},
          "formula": "100 * sum(weight * F1 * resolved_fraction)",
          "meaning": "Fixed-reference company development index, not impact probability or release acceptance"}
PRIORITIES = {"PRIORITY", "CONTEXT", "NONE", "INSUFFICIENT_CONTEXT"}
GROUPS = {"results", "supply", "input_price", "capacity", "demand", "financing", "policy",
          "competition", "technology", "governance", "other", "UNKNOWN"}
RUBRIC = {
    "relevance": "RELEVANT: defensible direct or conditional connection to supplied company business scope; no narrative required. NOT_RELEVANT: no defensible scoped connection. INSUFFICIENT_CONTEXT: source or dossier insufficient. A company mention or generic AI theme alone is not enough; do not invent suppliers/orders or financial effects.",
    "priority": "PRIORITY: relevant, concrete new decision, transaction, operating change, constraint, results or scoped policy/product development worth highlighting. A specific plan may qualify as a plan, not completed delivery. CONTEXT: relevant background, routine notices, speculative/unclear developments or sponsored educational prose. NONE only with NOT_RELEVANT. INSUFFICIENT_CONTEXT mandatory for unresolved relevance, or when attention cannot be judged.",
    "groups": "One to three actual event groups, consistent across companies for an article. UNKNOWN/other alone. Do not infer a family merely from a keyword.",
    "instructions": "Use supplied packet only; no web, predictions, implementation or peer labels. Give a concise rationale. Two separate AI contexts are not human gold or statistically independent humans.",
}


def validate_rows(rows):
    if not rows or len(rows) > 1000 or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Bounded unique company units required")
    seen = set()
    for r in rows:
        if not r["ticker"] or not r["event_cluster"] or not r["input"]["profile_id"]:
            raise ValueError("Company identity and source cluster required")
        value = r["input"]
        if "narrative" in value:
            raise ValueError("Company benchmark cannot require a narrative target")
        key = digest([value["article"], value.get("source_observation"), r["ticker"]])
        if key in seen:
            raise ValueError("Duplicate company source representation")
        seen.add(key)


def predict(row, bundle, at, article_root=None):
    value = row["input"]
    evidence = source_decisions(value, bundle, at, article_root=article_root)
    article = value["article"]
    assessment = assess({"headline": article["title"], "excerpt": article.get("summary", "")}, evidence)
    return {"id": row["id"], "selected": bool(evidence), "priority": assessment["priority"],
            "assessment": assessment, "evidence": evidence}


def frozen(directory, expected):
    directory = Path(directory)
    if pin(directory / "freeze.json")["sha256"] != expected:
        raise ValueError("Company freeze changed")
    receipt = read(directory / "freeze.json")
    if receipt["policy"] != POLICY:
        raise ValueError("Company score policy changed; create a new version")
    for p in [*receipt["files"], *receipt["provenance"]]:
        verify_pin(p)
    if receipt["article_root"] and tree(receipt["article_root"]) != receipt["article_files"]:
        raise ValueError("Frozen complete-article evidence changed")
    validate_rows(read(directory / "inputs.json"))
    return receipt


def freeze(rows, profiles, output, *, provenance, as_of=None, article_root=None):
    output = Path(output)
    if output.exists() or not provenance:
        raise ValueError("New company freeze and source provenance required")
    validate_rows(rows)
    at = datetime.fromisoformat(as_of) if as_of else datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Aware nonfuture freeze required")
    with local_environment(article_root):
        snapshot, bundles = state(profiles, at)
        predictions, dossiers = [], {}
        for row in rows:
            bundle = bundles[row["input"]["profile_id"]]
            if row["ticker"] != bundle.ticker:
                raise ValueError("Company target mismatch")
            predictions.append(predict(row, bundle, at, article_root))
            # Reviewer receives business evidence, not matcher rules or narratives.
            dossiers[bundle.id] = {k: v for k, v in bundle.model_dump(mode="json").items()
                                  if k in {"id", "ticker", "legal_name", "nodes", "relationships",
                                           "components", "sources", "observations"}}
        if state(profiles, at)[0] != snapshot:
            raise ValueError("Runtime or profiles changed during freeze")
    review_rows = []
    for row in rows:
        review_row = {"id": row["id"], "ticker": row["ticker"], "profile_id": row["input"]["profile_id"],
                      "event_cluster": row["event_cluster"], "article": row["input"]["article"]}
        if "source_observation" in row["input"]:
            from engine.article_cards import substantive_blocks

            blocks, _ = substantive_blocks(row["input"]["source_observation"], at, article_root=article_root)
            review_row["reviewed_body"] = "\n\n".join(b["text"] for b in blocks)
        review_rows.append(review_row)
    packet = {"reference_kind": "TWO_AI_REVIEWS_NOT_HUMAN_GOLD", "rubric": RUBRIC,
              "groups": sorted(GROUPS), "profiles": dossiers,
              "rows": review_rows}
    output.mkdir(parents=True)
    write(output / "inputs.json", rows)
    write(output / "predictions.json", predictions)
    write(output / "review-packet.json", packet)
    write(output / "freeze.json", {"schema": "COMPANY_BENCHMARK_FREEZE_V1", "as_of": at.isoformat(),
        "policy": POLICY, "state": snapshot, "article_root": article_root,
        "article_files": tree(article_root) if article_root else {},
        "files": [pin(output / n) for n in ["inputs.json", "predictions.json", "review-packet.json"]],
        "provenance": [pin(p) for p in provenance], "review_packet_sha256": digest(packet),
        "delivery": "disabled"})
    return pin(output / "freeze.json")


def reference(directory, expected, reviews, output):
    receipt = frozen(directory, expected)
    packet = read(Path(directory) / "review-packet.json")
    rows = read(Path(directory) / "inputs.json")
    identifiers = {r["id"] for r in rows}
    if len(reviews) != 2 or Path(output).exists():
        raise ValueError("Two reviews and a new reference path required")
    parsed = [read(p) for p in reviews]
    if len({p["reviewer_id"] for p in parsed}) != 2 or any(not p["reviewer_id"].strip() for p in parsed):
        raise ValueError("Distinct reviewer identities required")
    maps = []
    for p in parsed:
        if p["packet_sha256"] != digest(packet) or p.get("reviewer_kind") != "AI":
            raise ValueError("Review packet/AI provenance mismatch")
        items = p["labels"]
        if len(items) != len(identifiers) or {x["id"] for x in items} != identifiers:
            raise ValueError("Complete unique review labels required")
        groups_by_source: dict = {}
        source_by_id = {r["id"]: digest(r["input"]["article"]) for r in rows}
        for item in items:
            rel, pri = item["relevance"], item["priority"]
            if (rel not in LABELS or pri not in PRIORITIES or not item.get("rationale", "").strip()
                    or rel == "NOT_RELEVANT" and pri != "NONE"
                    or rel == "INSUFFICIENT_CONTEXT" and pri != "INSUFFICIENT_CONTEXT"
                    or rel == "RELEVANT" and pri == "NONE"):
                raise ValueError("Invalid relevance/priority relationship")
            groups = item["groups"]
            if (not 1 <= len(groups) <= 3 or len(set(groups)) != len(groups) or not set(groups) <= GROUPS
                    or set(groups) & {"other", "UNKNOWN"} and len(groups) != 1):
                raise ValueError("Invalid event groups")
            source = source_by_id[item["id"]]
            if source in groups_by_source and groups_by_source[source] != sorted(groups):
                raise ValueError("Article group cannot differ by company")
            groups_by_source[source] = sorted(groups)
        maps.append({x["id"]: x for x in items})
    labels = []
    for row in rows:
        a, b = (m[row["id"]] for m in maps)
        labels.append({"id": row["id"], "relevance": a["relevance"] if a["relevance"] == b["relevance"] else "INSUFFICIENT_CONTEXT",
                       "priority": a["priority"] if a["priority"] == b["priority"] else "INSUFFICIENT_CONTEXT",
                       "groups": sorted(a["groups"]) if set(a["groups"]) == set(b["groups"]) else ["UNKNOWN"]})
    write(output, {"schema": "DIRECT_COMPANY_REFERENCE_V1", "freeze_sha256": expected,
                   "packet_sha256": receipt["review_packet_sha256"], "reviews": [pin(p) for p in reviews],
                   "reference_kind": "AI_AGREEMENT_NOT_HUMAN_GOLD", "labels": labels,
                   "disagreements": {d: sum(a[d] != b[d] for a, b in zip(
                       [maps[0][r["id"]] for r in rows], [maps[1][r["id"]] for r in rows], strict=True))
                       for d in ("relevance", "priority")}})
    return pin(output)


def load_reference(path, expected, freeze_sha):
    verify_pin({"path": str(path), "sha256": expected})
    value = read(path)
    if value["freeze_sha256"] != freeze_sha or value["schema"] != "DIRECT_COMPANY_REFERENCE_V1":
        raise ValueError("Reference belongs to a different company freeze")
    for p in value["reviews"]:
        verify_pin(p)
    return value


def score(rows, predictions, labels):
    predictions = {p["id"]: p for p in predictions}
    labels = {r["id"]: r for r in labels}
    dimensions = {}
    points = 0.0
    missing = []
    ceiling = 0.0
    for dim, field in (("relevance", "selected"), ("priority", "priority")):
        units = [{**r, "groups": labels[r["id"]]["groups"], "selected": predictions[r["id"]][field],
                  "label": ("RELEVANT" if labels[r["id"]][dim] == "PRIORITY" else
                            "NOT_RELEVANT" if labels[r["id"]][dim] in {"CONTEXT", "NONE"} else labels[r["id"]][dim])}
                 for r in rows]
        m = metrics(units, lambda u: u["selected"])
        denominator = 2*m["tp"] + m["fp"] + m["fn"]
        f1 = 2*m["tp"]/denominator if denominator else None
        resolved = 1-m["unresolved"]/len(units)
        if m["tp"]+m["fn"] == 0:
            missing.append(dim)
        points += POLICY["weights"][dim] * (f1 or 0) * resolved * 100
        ceiling += POLICY["weights"][dim] * resolved * 100
        dimensions[dim] = {"overall": {**m, "f1": f1, "resolved_fraction": resolved},
            "by_company": {t: metrics([u for u in units if u["ticker"] == t], lambda u: u["selected"])
                           for t in sorted({u["ticker"] for u in units})},
            "by_group": {g: metrics([u for u in units if g in u["groups"]], lambda u: u["selected"])
                         for g in sorted({g for u in units for g in u["groups"]})}}
    return {"score": round(points, 2) if not missing else None, "policy": POLICY,
            "missing_positive_support": missing, "reference_ceiling": round(ceiling, 2),
            "dimensions": dimensions, "unmeasured": ["human_usefulness", "causal_truth", "financial_magnitude",
                "impact_horizon", "explanation_quality", "internet_coverage_latency"], "delivery": "disabled"}


def run(directory, expected, reference_path, reference_sha, profiles, output, *, baseline=None, as_of=None):
    output = Path(output)
    if output.exists():
        raise ValueError("Immutable company run requires a new directory")
    receipt = frozen(directory, expected)
    ref = load_reference(reference_path, reference_sha, expected)
    rows = read(Path(directory) / "inputs.json")
    at = datetime.fromisoformat(as_of or receipt["as_of"])
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Aware nonfuture company replay required")
    with local_environment(receipt["article_root"]):
        snapshot, bundles = state(profiles, at)
        predictions = [predict(r, bundles[r["input"]["profile_id"]], at, receipt["article_root"]) for r in rows]
        if state(profiles, at)[0] != snapshot:
            raise ValueError("Company runtime/database changed during replay")
    report = score(rows, predictions, ref["labels"])
    report.update(as_of=at.isoformat(), reference_kind=ref["reference_kind"], disagreements=ref["disagreements"])
    previous = read(Path(baseline) / "predictions.json") if baseline else read(Path(directory) / "predictions.json")
    if baseline:
        previous_receipt = read(Path(baseline) / "receipt.json")
        if (previous_receipt["freeze_sha256"] != expected or previous_receipt["reference_sha256"] != reference_sha):
            raise ValueError("Cannot compare different company targets/references")
        for p in previous_receipt["outputs"]:
            verify_pin(p)
    prior = {p["id"]: p for p in previous}
    labels = {r["id"]: r for r in ref["labels"]}
    changes = []
    for pred in predictions:
        for dim, field in (("relevance", "selected"), ("priority", "priority")):
            if pred[field] != prior[pred["id"]][field]:
                label = labels[pred["id"]][dim]
                changes.append({"id": pred["id"], "dimension": dim, "before": prior[pred["id"]][field],
                    "after": pred[field], "outcome": "UNRESOLVED" if label == "INSUFFICIENT_CONTEXT" else
                    "IMPROVED" if pred[field] == (label in {"RELEVANT", "PRIORITY"}) else "REGRESSION"})
    report["comparison"] = {"changes": changes, **{k.lower(): sum(c["outcome"] == k for c in changes)
                                                     for k in ("IMPROVED", "REGRESSION", "UNRESOLVED")}}
    frozen(directory, expected)
    load_reference(reference_path, reference_sha, expected)
    output.mkdir(parents=True)
    write(output / "predictions.json", predictions)
    write(output / "report.json", report)
    write(output / "receipt.json", {"freeze_sha256": expected, "reference_sha256": reference_sha,
        "as_of": at.isoformat(), "state": snapshot,
        "outputs": [pin(output / n) for n in ("predictions.json", "report.json")]})
    return report


def check(pointer):
    frozen(pointer["freeze"], pointer["freeze_sha256"])
    load_reference(pointer["reference"], pointer["reference_sha256"], pointer["freeze_sha256"])
    receipt = read(Path(pointer["run"]) / "receipt.json")
    if any(receipt[k] != pointer[k] for k in ("freeze_sha256", "reference_sha256")):
        raise ValueError("Company run/reference mismatch")
    for p in receipt["outputs"]:
        verify_pin(p)
    with local_environment():
        if state(pointer["profiles"], datetime.fromisoformat(receipt["as_of"]))[0] != receipt["state"]:
            raise ValueError("Company benchmark stale")
    return {"current": True, "kind": "COMPANY_EFFECTIVENESS_V1", "delivery": "disabled"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "check"])
    parser.add_argument("--pointer", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--as-of")
    args = parser.parse_args()
    value = read(args.pointer)
    if args.action == "run":
        if not args.output:
            parser.error("New output required")
        result = run(value["freeze"], value["freeze_sha256"], value["reference"], value["reference_sha256"],
                     value["profiles"], args.output, baseline=value["run"], as_of=args.as_of)
    else:
        result = check(value)
    print(result)


if __name__ == "__main__":
    main()
