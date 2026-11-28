"""Versioned local regression benchmark. No uploads, live delivery or promotion.

The suite pins inputs and reference labels; runs re-execute the current engine.
Changing a target or reference requires a new suite, not an edited baseline.
"""

import argparse
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from engine.atlas_freeze import runtime_fingerprint, sha
from engine.company_discovery import source_decisions as company_decisions
from engine.company_profiles import available_bundles
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.evaluation.company_quality import (
    SCORE_POLICY,
    company_report,
    company_rows,
    headline,
    identity,
)
from engine.evaluation.grouped_relevance import metrics
from engine.evaluation.priority_review import decisions, read
from engine.ingestion.contracts import digest
from engine.profile_news import entity_context
from engine.profile_routing import binding_decisions

SCHEMA = "LOCAL_QUALITY_BENCHMARK_V1"
REFERENCE = "EXPOSED_AI_REFERENCE_NOT_FRESH_BLIND_OR_HUMAN_GOLD"
LABELS = {"RELEVANT", "NOT_RELEVANT", "INSUFFICIENT_CONTEXT"}
PRIORITIES = {"PRIORITY", "CONTEXT", "NONE", "INSUFFICIENT_CONTEXT"}


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def tree(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"Missing data directory: {root}")
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def pin(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def verify_pin(item):
    if sha(item["path"]) != item["sha256"]:
        raise ValueError(f"Pinned benchmark input changed: {item['path']}")


def validate_rows(rows):
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Nonempty, uniquely identified benchmark pairs required")
    for row in rows:
        if row["label"] not in LABELS or row.get("priority") not in PRIORITIES | {None}:
            raise ValueError("Invalid benchmark reference label")
        if not row["event_cluster"] or not row["groups"] or not row["ticker"]:
            raise ValueError("Reference grouping and company required")
        if row.get("priority") == "PRIORITY" and row["label"] != "RELEVANT":
            raise ValueError("Priority requires a relevant reference")
        if row["track"] not in {"rss", "full_article", "archive"}:
            raise ValueError("Unknown source track")
        if row["track"] == "full_article" and "source_observation" not in row["input"]:
            raise ValueError("Full article source observation required")
    company_rows([{**r, **identity(r["input"]), "selected": False} for r in rows])


def create(spec, output):
    """Pin normalized cohorts plus original packets/labels/source receipts."""
    spec = read(spec)
    if not spec["version"] or not spec["cohorts"]:
        raise ValueError("Version and cohorts required")
    at = datetime.fromisoformat(spec["as_of"])
    if at.tzinfo is None:
        raise ValueError("Timezone required")
    names, cohorts = set(), []
    for c in spec["cohorts"]:
        if c["id"] in names or not c["provenance"]:
            raise ValueError("Unique cohorts and source provenance required")
        names.add(c["id"])
        rows = read(c["rows"])
        validate_rows(rows)
        cohorts.append({"id": c["id"], "rows": pin(c["rows"]), "pairs": len(rows),
                        "provenance": [pin(p) for p in c["provenance"]],
                        "article_dir": str(Path(c["article_dir"]).resolve()) if c.get("article_dir") else None,
                        "article_files": tree(c["article_dir"]) if c.get("article_dir") else None})
    suite = {"schema": SCHEMA, "version": spec["version"], "as_of": at.isoformat(),
             "reference_kind": REFERENCE, "cohorts": cohorts, "delivery": "disabled",
             "limitations": spec["limitations"], "no_pooled_accuracy": True}
    if spec.get("headline_score") is not None:
        config = spec["headline_score"]
        if config.get("policy") != SCORE_POLICY or config.get("anchor") not in names:
            raise ValueError("Unknown headline score policy or anchor")
        suite["headline_score"] = config
    write(output, suite)
    return {"suite_sha256": sha(output), "pairs": sum(c["pairs"] for c in cohorts)}


def load_suite(path, expected):
    if sha(path) != expected:
        raise ValueError("Suite hash differs; explicitly version a changed benchmark")
    suite = read(path)
    if suite["schema"] != SCHEMA or suite["reference_kind"] != REFERENCE or suite["delivery"] != "disabled":
        raise ValueError("Unsupported benchmark contract")
    for c in suite["cohorts"]:
        for p in [c["rows"], *c["provenance"]]:
            verify_pin(p)
        rows = read(c["rows"]["path"])
        validate_rows(rows)
        if len(rows) != c["pairs"]:
            raise ValueError("Benchmark pair count changed")
        if c["article_dir"] and tree(c["article_dir"]) != c["article_files"]:
            raise ValueError("Full article source cache changed")
    return suite


@contextmanager
def local_environment(article_dir=None):
    values = {"DEV_INFORMATIONAL_FEED": "true", "SEND_NOTIFICATIONS": "false",
              "ALLOW_SYNTHETIC_LIVE": "false", "LLM_MODE": "none",
              "NEWS_ARTICLE_DIR": article_dir or "source-cache/benchmark-no-article-cache"}
    before = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, value in before.items():
            if value is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = value


def state(profile_root, at):
    registry = available_bundles(at, root=Path(profile_root))
    if not registry["enabled"] or not registry["items"] or registry["withheld"] or registry["truncated"]:
        raise ValueError("Complete validated local profile registry required")
    bundles = {b.id: b for b in registry["items"]}
    return {"runtime": runtime_fingerprint(), "profile_root": str(Path(profile_root).resolve()),
            "profile_files": tree(profile_root),
            "profiles": {key: digest(b.model_dump(mode="json")) for key, b in bundles.items()}}, bundles


def predict(row, bundle, narrative, at, policy):
    value = row["input"]
    if row["track"] != "archive":
        return decisions(value, bundle, narrative, at, policy)
    article, links = value["article"], []
    for d in binding_decisions(bundle, narrative, article, at, issuer_cik=value["archive_source"]["cik"]):
        if d["paths_truncated"] or len(d["path"]) > policy["max_hops"]:
            continue
        ref = d["binding"].entity_reference_id
        links.append({"matches": d["matches"], "entity_context": entity_context(
            bundle, ref, article, at) if ref else None})
    return bool(links), assess({"headline": article.get("title", ""),
                               "excerpt": article.get("summary", "")}, links, policy)


def dimension(rows, name):
    total = len(rows)
    if name == "priority":
        labelled = [r for r in rows if r.get("priority") is not None]
        rows = [{**r, "label": "RELEVANT" if r["priority"] == "PRIORITY" else
                 "INSUFFICIENT_CONTEXT" if r["priority"] == "INSUFFICIENT_CONTEXT" else
                 "NOT_RELEVANT"} for r in labelled]
        if not rows:
            return {"status": "NOT_MEASURED_NO_PRIORITY_LABELS"}
    field = "selected" if name == "relevance" else "main"
    def score(items):
        return metrics(items, lambda r: r[field])
    return {"status": "EXPOSED_REGRESSION", "overall": score(rows),
            "reference_total_pairs": total, "unlabelled_pairs": total - len(rows),
            "by_group": {g: score([r for r in rows if g in r["groups"]])
                         for g in sorted({g for r in rows for g in r["groups"]})},
            "by_company": {t: score([r for r in rows if r["ticker"] == t])
                           for t in sorted({r["ticker"] for r in rows})},
            "by_narrative": {t: score([r for r in rows if r.get("target_id") == t])
                             for t in sorted({r["target_id"] for r in rows if "target_id" in r})}}


def comparison(previous, current):
    if set(previous) != set(current):
        raise ValueError("Cannot compare different cohort membership")
    changes = []
    for cohort, rows in current.items():
        old = {r["id"]: r for r in previous[cohort]}
        if set(old) != {r["id"] for r in rows}:
            raise ValueError("Cannot compare different pair membership")
        for row in rows:
            prior = old[row["id"]]
            for key in ("label", "priority", "groups", "event_cluster", "ticker", "track", "company_label"):
                if prior.get(key) != row.get(key):
                    raise ValueError("Reference changed between runs")
            for key in ("source_unit_id", "target_id"):
                if key in prior and prior[key] != row.get(key):
                    raise ValueError("Source or narrative identity changed between runs")
            for dim, field, label in (("relevance", "selected", row["label"]),
                                      ("priority", "main", row.get("priority"))):
                if row[field] == prior[field]:
                    continue
                unresolved = label in {None, "INSUFFICIENT_CONTEXT"}
                truth = label in {"RELEVANT", "PRIORITY"}
                changes.append({"cohort": cohort, "id": row["id"], "dimension": dim,
                                "before": prior[field], "after": row[field],
                                "outcome": "UNRESOLVED" if unresolved else
                                "IMPROVED" if row[field] == truth else "REGRESSION"})
        # Direct company truth was frozen separately; never score new company
        # discovery against the narrower legacy narrative-union proxy.
        if rows and all("company_label" in r for r in rows):
            before = {r["id"]: r for r in company_rows(previous[cohort])}
            for unit in company_rows(rows):
                prior = before[unit["id"]]
                if unit["selected"] == prior["selected"]:
                    continue
                changes.append({"cohort": cohort, "id": unit["id"], "dimension": "company",
                                "before": prior["selected"], "after": unit["selected"],
                                "outcome": "UNRESOLVED" if unit["label"] == "INSUFFICIENT_CONTEXT" else
                                "IMPROVED" if unit["selected"] == (unit["label"] == "RELEVANT") else "REGRESSION"})
    return {"changes": changes, "regressions": sum(c["outcome"] == "REGRESSION" for c in changes),
            "improvements": sum(c["outcome"] == "IMPROVED" for c in changes),
            "unresolved_changes": sum(c["outcome"] == "UNRESOLVED" for c in changes)}


def load_run(path, suite_sha):
    path = Path(path)
    receipt = read(path / "receipt.json")
    if receipt["suite_sha256"] != suite_sha:
        raise ValueError("Baseline belongs to a different suite")
    for name, expected in receipt["outputs"].items():
        if sha(path / name) != expected:
            raise ValueError("Benchmark run output changed")
    return receipt, read(path / "predictions.json"), read(path / "report.json")


def run(suite_path, expected, profile_root, output, baseline=None, as_of=None):
    suite = load_suite(suite_path, expected)
    output = Path(output)
    if output.exists():
        raise ValueError("New immutable run directory required")
    at = datetime.fromisoformat(as_of) if as_of else datetime.now(UTC)
    if at.tzinfo is None or at < datetime.fromisoformat(suite["as_of"]):
        raise ValueError("Replay time must be timezone aware and follow suite creation")
    prior_run = load_run(baseline, expected) if baseline else None
    previous = prior_run[1] if prior_run else None
    with local_environment():
        before, bundles = state(profile_root, at)
        policy, results = read(POLICY), {}
        for cohort in suite["cohorts"]:
            rows = []
            discovery_cache = {}
            with local_environment(cohort["article_dir"]):
                for row in read(cohort["rows"]["path"]):
                    value = row["input"]
                    b = bundles[value["profile_id"]]
                    n = next(n for n in b.narratives if n.id == value["narrative"]["id"])
                    if n.model_dump(mode="json") != value["narrative"]:
                        raise ValueError("Narrative target changed; new suite required")
                    matched, activity = predict(row, b, n, at, policy)
                    key = (identity(value)["source_unit_id"], b.id)
                    if key not in discovery_cache:
                        discovery_cache[key] = company_decisions(value, b, at) if "company_label" in row else []
                    rows.append({k: v for k, v in row.items() if k != "input"} | {
                        **identity(value),
                        "company_selected": bool(discovery_cache[key]),
                        "company_discovery": discovery_cache[key],
                        "selected": matched, "main": matched and activity["tier"] not in
                        {"BACKGROUND_THEME", "SPONSORED_RESEARCH"}, "assessment": activity})
            results[cohort["id"]] = rows
        if state(profile_root, at)[0] != before:
            raise ValueError("Runtime or database changed during benchmark")
    load_suite(suite_path, expected)
    report = {"schema": SCHEMA, "version": suite["version"], "reference_kind": REFERENCE,
              "suite_as_of": suite["as_of"], "as_of": at.isoformat(),
              "baseline_as_of": prior_run[0]["as_of"] if prior_run else None,
              "pairs": sum(len(r) for r in results.values()),
              "cohorts": {c: {**{d: dimension(rows, d) for d in ("relevance", "priority")},
                              "company": company_report(rows)}
                          for c, rows in results.items()},
              "comparison": comparison(previous, results) if previous is not None else None,
              "limitations": suite["limitations"], "delivery": "disabled", "promotion": "NOT_AUTHORIZED",
              "unmeasured": ["financial_magnitude", "impact_horizon", "causal_truth", "personalized_utility",
                             "live_source_coverage_latency", "fresh_blind_generalization"],
              "no_pooled_accuracy": True}
    report["headline"] = headline(report["cohorts"], suite.get("headline_score"))
    if prior_run and suite.get("headline_score"):
        old_score = prior_run[2].get("headline", {}).get("score")
        new_score = report["headline"]["score"]
        report["headline"]["delta"] = (round(new_score - old_score, 2)
                                       if new_score is not None and old_score is not None else None)
    output.mkdir(parents=True)
    write(output / "predictions.json", results)
    write(output / "report.json", report)
    write(output / "receipt.json", {"schema": SCHEMA, "created_at": datetime.now(UTC).isoformat(),
          "suite_sha256": expected, "state": before, "as_of": at.isoformat(),
          "baseline_receipt_sha256": sha(Path(baseline) / "receipt.json") if baseline else None,
          "outputs": {name: sha(output / name) for name in ("predictions.json", "report.json")},
          "delivery": "disabled"})
    return report


def check(suite_path, expected, profile_root, output):
    suite = load_suite(suite_path, expected)
    receipt, _, report = load_run(output, expected)
    with local_environment():
        current, _ = state(profile_root, datetime.fromisoformat(receipt["as_of"]))
    if current != receipt["state"] or report["suite_as_of"] != suite["as_of"]:
        raise ValueError("Benchmark is stale: rerun after runtime/database update")
    comparison = report["comparison"]
    return {"current": True, "quality_status": "REGRESSION_REVIEW_REQUIRED" if comparison and
            comparison["regressions"] else "CURRENT_EXPOSED_REGRESSION_ONLY", "delivery": "disabled"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "run", "check"])
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--suite-sha256")
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--as-of", help="Optional fixed replay time; default is current UTC")
    args = parser.parse_args()
    if args.action == "create":
        if not args.spec:
            parser.error("--spec required")
        result = create(args.spec, args.suite)
    else:
        if not args.suite_sha256 or not args.profiles or not args.output:
            parser.error("--suite-sha256, --profiles and --output required")
        result = (run(args.suite, args.suite_sha256, args.profiles, args.output, args.baseline, args.as_of)
                  if args.action == "run" else check(args.suite, args.suite_sha256, args.profiles, args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
