"""Offline AI-simulated review: isolated artifacts, never human-label ingestion."""

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from engine.api.annotations import Numeric
from engine.evaluation.consensus import normalized, predicted
from engine.ingestion.contracts import digest

CLASSES = {"ISSUER_ATTRIBUTION", "UNCERTAIN_OR_FORWARD_LOOKING", "NO_CAUSAL_CLAIM"}


def prepare_input(blind_path, source_root, target):
    cases = json.loads(blind_path.read_text(encoding="utf-8"))
    pid = digest(sorted(cases, key=lambda c: c["id"]))
    cache = {}
    for case in cases:
        source = (source_root / (case["ticker"] + "-" + case["accession"] + ".html")).resolve()
        if not source.is_relative_to(source_root.resolve()):
            raise ValueError("Source path outside capture directory")
        if case["snapshot_id"] not in cache:
            # Original ingestion hashed decoded text; Windows captures may have CRLF on disk.
            text = source.read_text(encoding="utf-8")
            if hashlib.sha256(text.encode()).hexdigest() != case["source_sha256"]:
                raise ValueError("Original capture hash mismatch")
            root = ET.fromstring(text)
            cache[case["snapshot_id"]] = {n.get("id"): n for n in root.iter() if n.get("id")}
        if case["kind"] == "segment_comparison":
            index = cache[case["snapshot_id"]]
            operands = {}
            for side in ("current", "prior"):
                node = index[case[side + "_locator"]]
                operands[side] = {
                    "fact_xml": ET.tostring(node, encoding="unicode"),
                    "context_xml": ET.tostring(index[node.get("contextRef")], encoding="unicode"),
                    "unit_xml": ET.tostring(index[node.get("unitRef")], encoding="unicode"),
                }
            case["raw_source_operands"] = operands
        case["local_source_file"] = str(source)
    payload = {"evaluation_track": "AI_SIMULATED", "packet_id": pid, "cases": cases}
    if target.exists() and json.loads(target.read_text(encoding="utf-8")) != payload:
        raise ValueError("Existing blind agent input differs; use a separate run directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"cases": len(cases), "packet_id": pid, "predictions_included": False}


def validate_label(row, case):
    if row.get("source_sha256") != case["source_sha256"] or len(row.get("reason", "").strip()) < 10:
        raise ValueError("Source hash and case-specific rationale required")
    if case["kind"] == "causal_language":
        if row.get("language") not in CLASSES or row.get("numeric") is not None:
            raise ValueError("Language label required")
    else:
        if row.get("language") is not None or not row.get("numeric"):
            raise ValueError("Numeric label required")
        Numeric.model_validate(row["numeric"])
    return normalized(row)


def votes(pack, review, profile):
    if (
        review.get("evaluation_track") != "AI_SIMULATED"
        or review.get("profile") != profile
        or review.get("blind_to_predictions") is not True
        or review.get("packet_id") != pack["packet_id"]
    ):
        raise ValueError("Explicit AI provenance and prediction blinding required")
    cases = {c["id"]: c for c in pack["cases"]}
    rows = review["labels"]
    if len(rows) != len(cases) or {r["case_id"] for r in rows} != set(cases):
        raise ValueError("Exactly one independent label per case required")
    for row in rows:
        validate_label(row, cases[row["case_id"]])
    return {r["case_id"]: r for r in rows}


def disputes(pack, left, right):
    a, b = votes(pack, left, "retail_investor"), votes(pack, right, "fund_manager")
    rows = []
    for c in pack["cases"]:
        cid = c["id"]
        if normalized(a[cid]) != normalized(b[cid]):
            rows.append(
                {
                    "case": c,
                    "reviewer_a": a[cid],
                    "reviewer_b": b[cid],
                    "vote_hash": digest([a[cid], b[cid]]),
                }
            )
    return {
        "evaluation_track": "AI_SIMULATED",
        "packet_id": pack["packet_id"],
        "disagreements": rows,
        "instructions": "Resolve independently from original source or defer; no model predictions provided",
    }


def evaluate(pack, left, right, sealed, adjudicated=None):
    # This function never writes to annotation tables, accounts, graph or delivery.
    a, b = votes(pack, left, "retail_investor"), votes(pack, right, "fund_manager")
    cases = {c["id"]: c for c in pack["cases"]}
    original = sorted(sealed["cases"], key=lambda c: c["id"])
    if digest(original) != pack["packet_id"] or len(original) != len(cases):
        raise ValueError("Frozen comparison packet mismatch")
    for c in original:
        if any(cases[c["id"]].get(k) != v for k, v in c.items()):
            raise ValueError("Blind source packet was altered")
    conflicts = {r["case"]["id"]: r for r in disputes(pack, left, right)["disagreements"]}
    references = {cid: normalized(a[cid]) for cid in cases if cid not in conflicts}
    decisions = {}
    if adjudicated is not None:
        if (
            adjudicated.get("evaluation_track") != "AI_SIMULATED"
            or adjudicated.get("profile") != "financial_expert"
            or adjudicated.get("packet_id") != pack["packet_id"]
            or adjudicated.get("blind_to_predictions") is not True
        ):
            raise ValueError("AI expert provenance required")
        for r in adjudicated["decisions"]:
            cid = r["case_id"]
            if (
                cid not in conflicts
                or cid in decisions
                or r.get("vote_hash") != conflicts[cid]["vote_hash"]
            ):
                raise ValueError("Unknown, repeated or stale AI adjudication")
            if (
                r.get("source_sha256") != cases[cid]["source_sha256"]
                or len(r.get("reason", "").strip()) < 10
            ):
                raise ValueError("Source and rationale required for adjudication")
            if r.get("outcome") == "RESOLVED":
                references[cid] = validate_label(r, cases[cid])
            elif (
                r.get("outcome") != "DEFERRED"
                or r.get("language") is not None
                or r.get("numeric") is not None
            ):
                raise ValueError("Deferred decisions cannot supply reference labels")
            decisions[cid] = r
    metrics = {}
    for kind in ("causal_language", "segment_comparison"):
        held = [c for c in cases.values() if c["kind"] == kind and c["split"] == "holdout"]
        scored = [
            (predicted(c, sealed["predictions"][c["id"]]), references[c["id"]])
            for c in held
            if c["id"] in references
        ]
        correct = sum(x == y for x, y in scored)
        metrics[kind] = {
            "total_holdout": len(held),
            "scored": len(scored),
            "matches_ai_reference": correct,
            "agreement_with_ai_reference": correct / len(scored) if scored else None,
            "coverage": len(scored) / len(held) if held else None,
        }
    return {
        "evaluation_track": "AI_SIMULATED",
        "packet_id": pack["packet_id"],
        "status": "AI_REVIEW_COMPLETE"
        if len(decisions) == len(conflicts)
        else "AI_ADJUDICATION_PENDING",
        "generated_at": datetime.now(UTC).isoformat(),
        "total_cases": len(cases),
        "profiles": {
            "retail_investor": len(a),
            "fund_manager": len(b),
            "financial_expert": len(decisions),
        },
        "initial_agreements": len(cases) - len(conflicts),
        "initial_disagreements": len(conflicts),
        "resolved_disagreements": sum(r["outcome"] == "RESOLVED" for r in decisions.values()),
        "deferred_disagreements": sum(r["outcome"] == "DEFERRED" for r in decisions.values()),
        "pending_adjudications": len(conflicts) - len(decisions),
        "ai_reference_cases": len(references),
        "human_labels_created": 0,
        "human_accuracy": None,
        "independent_human_validation": False,
        "holdout_diagnostics": metrics,
        "input_sha256": digest(pack),
        "review_output_sha256": {
            "a": digest(left),
            "b": digest(right),
            "expert": digest(adjudicated),
        },
        "delivery": "disabled",
        "graph_modified": False,
        "limitations": [
            "Three personas are not three statistically independent human experts",
            "Shared model biases may inflate consensus and agreement",
            "Numbers measure agreement with AI reference, not validated accuracy or stock impact",
            "No AI outputs are imported as human labels; source lifecycle must be rechecked before reuse",
        ],
    }


def public_summary(pid):
    path = Path(__file__).resolve().parents[2] / "reports/ai-campaign-204-summary.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("packet_id") != pid or data.get("evaluation_track") != "AI_SIMULATED":
        return None
    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-input", action="store_true")
    parser.add_argument("--directory", type=Path, default=Path("source-cache/ai-campaign-204"))
    parser.add_argument(
        "--sealed",
        type=Path,
        default=Path("source-cache/evaluation-segments-v1/sealed-predictions.json"),
    )
    args = parser.parse_args()
    if args.prepare_input:
        print(
            json.dumps(
                prepare_input(
                    Path("source-cache/evaluation-segments-v1/blind-cases.json"),
                    Path("source-cache/sec-review-2026-11-20"),
                    args.directory / "blind-input.json",
                )
            )
        )
        return

    def read(name):
        return json.loads((args.directory / name).read_text(encoding="utf-8"))

    pack, left, right = read("blind-input.json"), read("reviewer-a.json"), read("reviewer-b.json")
    (args.directory / "disputes.json").write_text(
        json.dumps(disputes(pack, left, right), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    expert = read("expert.json") if (args.directory / "expert.json").exists() else None
    report = evaluate(
        pack, left, right, json.loads(args.sealed.read_text(encoding="utf-8")), expert
    )
    Path("reports/ai-campaign-204-summary.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "status",
                    "total_cases",
                    "initial_disagreements",
                    "pending_adjudications",
                    "human_labels_created",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
