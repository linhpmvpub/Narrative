"""Post-hoc AI disagreement audit and a frozen gate for prospective evaluation."""

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from engine.evaluation.agent_pilot import disputes, evaluate
from engine.evaluation.language_candidate import VERSION, classify
from engine.ingestion.contracts import digest


def verify_baseline(sealed, receipt):
    value = digest({k: sealed[k] for k in ("predictions", "extractor", "as_of")})
    if (
        value != receipt["prediction_sha256"]
        or digest(sorted(sealed["cases"], key=lambda c: c["id"])) != receipt["packet_id"]
    ):
        raise ValueError("Sealed baseline differs from original freeze receipt")
    return value


def signature(text):
    words = re.findall(r"\w+", text.casefold())
    return {
        "text_hash": digest(words),
        "shingles": sorted({digest(words[i : i + 3]) for i in range(max(0, len(words) - 2))}),
    }


def protocol(cases, frozen_at):
    return {
        "kind": "PROSPECTIVE_LANGUAGE_EVALUATION",
        "candidate_version": VERSION,
        "candidate_sha256": hashlib.sha256(
            Path(__file__).with_name("language_candidate.py").read_bytes()
        ).hexdigest(),
        "frozen_at": frozen_at.isoformat(),
        "near_duplicate_jaccard": 0.8,
        "excluded_accessions": sorted({c["accession"] for c in cases}),
        "excluded_source_hashes": sorted({c["source_sha256"] for c in cases}),
        "seen_text": [signature(c["text"]) for c in cases if c["kind"] == "causal_language"],
        "reference_track": "AI_SIMULATED_UNLESS_GENUINE_HUMAN_LABELS_COLLECTED",
        "prediction_freeze_before_labels": True,
        "promotion_allowed": False,
    }


def screen_future(case, plan, now=None):
    now = now or datetime.now(UTC)
    cutoff = datetime.fromisoformat(plan["frozen_at"])
    reasons = []
    current_sha = hashlib.sha256(
        Path(__file__).with_name("language_candidate.py").read_bytes()
    ).hexdigest()
    if plan["candidate_version"] != VERSION or plan["candidate_sha256"] != current_sha:
        reasons.append("CANDIDATE_CHANGED_AFTER_FREEZE")
    if (
        case.get("accession") in plan["excluded_accessions"]
        or case.get("source_sha256") in plan["excluded_source_hashes"]
    ):
        reasons.append("SOURCE_ALREADY_EXPOSED")
    try:
        available = datetime.fromisoformat(case["available_at"])
        if available.tzinfo is None or available <= cutoff:
            reasons.append("CAPTURE_NOT_AFTER_FREEZE")
        elif available > now:
            reasons.append("CAPTURE_IN_FUTURE")
        if date.fromisoformat(case["filing_date"]) <= cutoff.date():
            reasons.append("FILING_NOT_AFTER_FREEZE")
        elif date.fromisoformat(case["filing_date"]) > now.date():
            reasons.append("FILING_IN_FUTURE")
    except (KeyError, ValueError, TypeError):
        reasons.append("MISSING_VALID_SOURCE_TIMES")
    candidate = signature(case.get("text", ""))
    if not candidate["shingles"]:
        reasons.append("INSUFFICIENT_TEXT")
    for seen in plan["seen_text"]:
        if candidate["text_hash"] == seen["text_hash"]:
            reasons.append("EXACT_TEXT_REUSE")
            break
        a, b = set(candidate["shingles"]), set(seen["shingles"])
        if a and b and len(a & b) / len(a | b) >= plan["near_duplicate_jaccard"]:
            reasons.append("NEAR_TEXT_REUSE")
            break
    return {
        "eligible_for_new_review": not reasons,
        "reasons": reasons,
        "candidate_version": plan["candidate_version"],
        "source_verification_still_required": True,
    }


def audit(pack, a, b, sealed, expert):
    validated = evaluate(pack, a, b, sealed, expert)
    conflicts = {r["case"]["id"] for r in disputes(pack, a, b)["disagreements"]}
    refs = {r["case_id"]: r for r in a["labels"] if r["case_id"] not in conflicts}
    refs.update({r["case_id"]: r for r in expert["decisions"] if r["outcome"] == "RESOLVED"})
    rows = []
    for case in pack["cases"]:
        if case["kind"] != "causal_language" or case["id"] not in refs:
            continue
        cid = case["id"]
        baseline = sealed["predictions"][cid]
        gold = refs[cid]["language"]
        result = classify(case["text"])
        category = None
        if baseline != gold:
            category = (
                "OUTLOOK_RUBRIC_VS_CAUSAL_GATE"
                if baseline == "NO_CAUSAL_CLAIM" and gold == "UNCERTAIN_OR_FORWARD_LOOKING"
                else "MISSED_REALIZED_EXPLANATION"
                if baseline == "NO_CAUSAL_CLAIM" and gold == "ISSUER_ATTRIBUTION"
                else "AUDIT_OR_NONFINANCIAL_CAUSE"
                if gold == "NO_CAUSAL_CLAIM"
                else "PARAGRAPH_TEMPORAL_SCOPE"
            )
        rows.append(
            {
                "case": case,
                "baseline": baseline,
                "ai_reference": gold,
                "ai_reason": refs[cid]["reason"],
                "candidate": result,
                "category": category,
            }
        )
    metrics = {}
    for split in ("development", "holdout"):
        selected = [r for r in rows if r["case"]["split"] == split]
        unique = {signature(r["case"]["text"])["text_hash"]: r for r in selected}
        confusion: dict[str, int] = {}
        for row in selected:
            pair = row["ai_reference"] + " -> " + row["candidate"]["label"]
            confusion[pair] = confusion.get(pair, 0) + 1
        metrics[split] = {
            "cases": len(selected),
            "unique_texts": len(unique),
            "baseline_matches_ai": sum(r["baseline"] == r["ai_reference"] for r in selected),
            "candidate_matches_ai": sum(
                r["candidate"]["label"] == r["ai_reference"] for r in selected
            ),
            "candidate_matches_unique_text": sum(
                r["candidate"]["label"] == r["ai_reference"] for r in unique.values()
            ),
            "baseline_mismatch_categories": dict(
                Counter(r["category"] for r in selected if r["category"])
            ),
            "fixed_against_ai": sum(
                r["baseline"] != r["ai_reference"] and r["candidate"]["label"] == r["ai_reference"]
                for r in selected
            ),
            "regressed_against_ai": sum(
                r["baseline"] == r["ai_reference"] and r["candidate"]["label"] != r["ai_reference"]
                for r in selected
            ),
            "candidate_confusion_ai_to_prediction": confusion,
        }
    return {
        "packet_id": pack["packet_id"],
        "evaluation_track": "AI_SIMULATED_POST_HOC",
        "candidate_version": VERSION,
        "deployment": "SHADOW_ONLY",
        "splits": metrics,
        "review_artifact_sha256": validated["review_output_sha256"],
        "human_accuracy": None,
        "fresh_evaluation": "PENDING_POST_FREEZE_FILINGS_AND_BLIND_LABELS",
        "delivery": "disabled",
        "graph_modified": False,
        "limitations": [
            "Exposed holdout used for diagnosis; results are not independent validation",
            "AI references can be wrong; mismatch categories describe rubric disagreement, not proven errors",
            "Repeated text across filings inflates case counts; unique-text denominators also reported",
            "Candidate is heuristic and shadow-only; original frozen predictions/snapshots remain unchanged",
        ],
    }, rows


def public_audit(pid):
    path = Path(__file__).resolve().parents[2] / "reports/language-error-audit.json"
    if not path.exists():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    return result if result.get("packet_id") == pid else None


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screen-cases", type=Path, help="JSON array of prospective source cases; never labels"
    )
    args = parser.parse_args()
    output = Path("source-cache/language-audit-" + VERSION.rsplit("-", 1)[-1])
    if args.screen_cases:
        plan = json.loads((output / "prospective-protocol.json").read_text(encoding="utf-8"))
        cases = json.loads(args.screen_cases.read_text(encoding="utf-8"))
        checked = [{"case_id": c["id"], **screen_future(c, plan)} for c in cases]
        result = {
            "candidate_version": VERSION,
            "cases": len(checked),
            "eligible": sum(c["eligible_for_new_review"] for c in checked),
            "items": checked,
            "new_labels_created": 0,
            "promotion_allowed": False,
        }
        (output / "prospective-screen.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "candidate_version",
                        "cases",
                        "eligible",
                        "new_labels_created",
                        "promotion_allowed",
                    )
                }
            )
        )
        return
    directory = Path("source-cache/ai-campaign-204")

    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    pack = read("blind-input.json")
    sealed = json.loads(
        Path("source-cache/evaluation-segments-v1/sealed-predictions.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        Path("reports/adjudication-pending-quality.json").read_text(encoding="utf-8")
    )
    baseline_sha = verify_baseline(sealed, receipt)
    report, rows = audit(
        pack, read("reviewer-a.json"), read("reviewer-b.json"), sealed, read("expert.json")
    )
    report["baseline_frozen_payload_sha256"] = baseline_sha
    output.mkdir(exist_ok=True)
    (output / "case-audit.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    planpath = output / "prospective-protocol.json"
    plan = protocol(pack["cases"], datetime.now(UTC))
    if planpath.exists():
        old = json.loads(planpath.read_text(encoding="utf-8"))
        if old["candidate_sha256"] != plan["candidate_sha256"]:
            raise ValueError("Candidate changed after protocol freeze; use a new version/run")
        plan = old
    else:
        planpath.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    report["prospective_protocol"] = {
        k: plan[k]
        for k in ("candidate_sha256", "frozen_at", "near_duplicate_jaccard", "promotion_allowed")
    }
    report["prospective_protocol_sha256"] = digest(plan)
    Path("reports/language-error-audit.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["splits"], indent=2))


if __name__ == "__main__":
    main()
