"""Evidence-derived local v1 readiness; never authorizes delivery or deployment."""

import argparse
import json
import math
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from engine.evaluation.profile_relevance import consensus, evaluate
from engine.ingestion.contracts import digest
from engine.market_pipeline import save


def wilson_lower(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    return (
        p + z * z / (2 * total) - z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    ) / (1 + z * z / total)


def quality(directory, reviews, policy):
    # Recompute consensus from two original reviews; never trust supplied aggregate metrics.
    labels = consensus(directory, reviews)
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "consensus.json"
        save(path, labels)
        metrics = evaluate(directory, path)
    packet = json.loads((directory / "packet.json").read_text(encoding="utf-8"))
    frozen = json.loads((directory / "freeze.json").read_text(encoding="utf-8"))
    positive_ids = {v["id"] for v in labels["labels"] if v["relevance"] == "RELEVANT"}
    targets = {
        ticker: len(
            {r["cluster"] for r in packet if r["ticker"] == ticker and r["id"] in positive_ids}
        )
        for ticker in policy["tickers"]
    }
    clusters = len({r["cluster"] for r in packet})
    if clusters != frozen["clusters"]:
        raise ValueError("Freeze cluster count mismatch")
    t = policy["quality_targets"]
    lower = wilson_lower(metrics["tp"], metrics["tp"] + metrics["fp"])
    checks = {
        "article_clusters": clusters >= t["min_event_clusters"],
        "positive_pairs": metrics["tp"] + metrics["fn"] >= t["min_resolved_positive_pairs"],
        "negative_pairs": metrics["tn"] + metrics["fp"] >= t["min_resolved_negative_pairs"],
        "all_target_companies": all(n >= t["min_clusters_per_target"] for n in targets.values()),
        "strata": len(metrics["by_stratum"]) >= t["min_strata"],
        "unresolved": 1 - metrics["resolved_fraction"] <= t["max_unresolved_fraction"],
        "precision": metrics["precision"] is not None
        and metrics["precision"] >= t["min_precision"],
        "precision_lower_bound": lower is not None and lower >= t["min_precision_wilson_lower"],
        "recall": metrics["recall"] is not None and metrics["recall"] >= t["min_recall"],
        # URL deduplication is not independently verified economic-event clustering.
        "independent_event_cluster_audit": False,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "metrics": {k: v for k, v in metrics.items() if k != "errors"},
        "precision_wilson_lower": lower,
        "clusters_per_target": targets,
        "review_sha256": labels["review_sha256"],
        "human_gold": False,
        "policy_sha256": digest(policy),
        "limitation": "Current-profile convenience sample; no historical as-of or product impact claim",
    }


def operations(root, policy, *, now=None):
    now = now or datetime.now(UTC)
    reports = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "runs").glob("*.json"))
    ]
    reports = [r for r in reports if r.get("policy_sha256") == digest(policy)]
    clocks = sorted(datetime.fromisoformat(r["at"]) for r in reports)
    if any(t.tzinfo is None or t > now for t in clocks):
        raise ValueError("Invalid observation clocks")
    attempts = [a for r in reports for a in r["poll_attempts"]]
    successes = sum(a["status"] in {"OK", "NOT_MODIFIED"} for a in attempts)
    success = successes / len(attempts) if attempts else None
    latest = max(reports, key=lambda r: r["at"]) if reports else None
    sources = [s for s in latest["sources"] if s["enabled"]] if latest else []
    stale = sum(s["stale"] for s in sources) / len(sources) if sources else 1.0
    span = (clocks[-1] - clocks[0]).total_seconds() / 86400 if clocks else 0
    max_gap = max(
        [(b - a).total_seconds() for a, b in zip(clocks, clocks[1:], strict=False)]
        + [(now - clocks[-1]).total_seconds()]
        if clocks
        else [float("inf")]
    )
    target = policy["operations_targets"]
    checks = {
        "observation_days": span >= target["min_observation_days"],
        "continuous_observation": max_gap <= target["max_feed_poll_interval_seconds"],
        "success_fraction": success is not None and success >= target["min_success_fraction"],
        "source_freshness": bool(sources) and stale <= target["max_source_stale_fraction"],
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "observed_days": span,
        "attempts": len(attempts),
        "success_fraction": success,
        "stale_fraction": stale,
        "receipt_count": len(reports),
        "note": "Local operational diagnostics, not independently attested uptime",
    }


def assess(root, policy, directory=None, reviews=()):
    plan = json.loads((root / "profile-plan.json").read_text(encoding="utf-8"))
    q = (
        quality(directory, reviews, policy)
        if directory
        else {"passed": False, "reason": "No complete independent review cohort supplied"}
    )
    ops = operations(root, policy)
    return {
        "schema": "PRODUCT_V1_READINESS_V1",
        "policy_sha256": digest(policy),
        "profiles_complete": plan["profiles_complete"],
        "profile_gaps": [c for c in plan["companies"] if not c["ready"]],
        "quality": q,
        "operations": ops,
        "release_ready": False,
        "delivery": "disabled",
        "cloud_data": False,
        "remaining_gates": [
            "Independent economic-event grouping audit",
            "Human validation before public launch",
        ],
        "local_engineering_gates_passed": plan["profiles_complete"]
        and q["passed"]
        and ops["passed"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("source-cache/product-v1-pipeline"))
    parser.add_argument("--policy", type=Path, default=Path("config/product-v1.json"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--review", type=Path, action="append", default=[])
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    result = assess(args.root, policy, args.directory, args.review)
    save(args.root / "readiness.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
