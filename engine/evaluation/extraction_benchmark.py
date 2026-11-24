"""Source-first passage benchmark. Separate blind text from locked syntax predictions.

This measures extraction on explicitly selected passages, never company impact quality.
Two AI label sets remain separate references; disagreements are not automatic gold.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def check_span(text, value, *, nullable=False):
    if value is None and nullable:
        return
    if (
        not isinstance(value, dict)
        or set(value) != {"start", "end", "text"}
        or type(value["start"]) is not int
        or type(value["end"]) is not int
        or not 0 <= value["start"] < value["end"] <= len(text)
        or text[value["start"] : value["end"]] != value["text"]
    ):
        raise ValueError("Invalid source-bound label span")


def freeze(cases, predictions, output, *, protocol, excluded_text_hashes=()):
    """Caller supplies reviewed source passages; no truth/completeness inferred here."""
    if not 1 <= len(cases) <= 100 or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Bounded unique cases required")
    if set(predictions) != {c["id"] for c in cases}:
        raise ValueError("Exactly one prediction list per case required")
    seen = set(excluded_text_hashes)
    public = []
    for c in cases:
        if not 180 <= len(c["text"]) <= 10000 or not c.get("source_sha256"):
            raise ValueError("Bounded source-linked passage required")
        key = hashlib.sha256(c["text"].encode()).hexdigest()
        if key in seen:
            raise ValueError("Duplicate or previously exposed passage")
        seen.add(key)
        # Whitelist prevents private expected labels/predictions from leaking to reviewers.
        public.append({k: c[k] for k in ["id", "text", "title", "source_url", "published_at"]})
        for prediction in predictions[c["id"]]:
            for field in ["actor", "predicate", "object"]:
                check_span(c["text"], prediction[field])
            if prediction.get("delivery") != "disabled":
                raise ValueError("Disabled predictions required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    files = {
        "sources.json": cases,
        "blind.json": public,
        "predictions.json": predictions,
        "protocol.json": protocol,
    }
    for name, value in files.items():
        write(output / name, value)
    receipt = {
        "schema": "source-first-extraction-v1",
        "frozen_at": datetime.now(UTC).isoformat(),
        "files": {name: digest(value) for name, value in files.items()},
        "cases": len(cases),
        "human_gold": False,
        "delivery": "disabled",
        "scope": "SELECTED_PASSAGES_NOT_FULL_ARTICLE_OR_COMPANY_IMPACT",
    }
    write(output / "receipt.json", receipt)
    return digest(receipt)


def verify(root, pin):
    root = Path(root)
    receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
    if digest(receipt) != pin or set(receipt["files"]) != {
        "sources.json",
        "blind.json",
        "predictions.json",
        "protocol.json",
    }:
        raise ValueError("Freeze receipt changed")
    files = {}
    for name, expected in receipt["files"].items():
        value = json.loads((root / name).read_text(encoding="utf-8"))
        if digest(value) != expected:
            raise ValueError("Frozen artifact changed")
        files[name] = value
    return files, receipt


def validate_labels(labels, cases):
    if (
        set(labels) != {"reviewer_id", "reviewer_kind", "cases"}
        or labels["reviewer_kind"] != "AI_INDEPENDENT"
    ):
        raise ValueError("Explicit independent AI provenance required")
    if not isinstance(labels["reviewer_id"], str) or not labels["reviewer_id"].strip():
        raise ValueError("Reviewer identity required")
    rows = labels["cases"]
    if len(rows) != len(cases) or {r["id"] for r in rows} != {c["id"] for c in cases}:
        raise ValueError("Complete unique case labels required")
    sources = {c["id"]: c["text"] for c in cases}
    for row in rows:
        if set(row) != {"id", "status", "assertions", "comment"} or row["status"] not in {
            "REVIEWED",
            "UNSURE",
        }:
            raise ValueError("Explicit review/uncertainty required")
        if not isinstance(row["comment"], str) or len(row["assertions"]) > 100:
            raise ValueError("Bounded label list required")
        anchors = set()
        for a in row["assertions"]:
            if set(a) != {"actor", "predicate", "object", "polarity", "phase", "attributed"}:
                raise ValueError("Unexpected assertion fields")
            for field in ["actor", "predicate", "object"]:
                check_span(sources[row["id"]], a[field], nullable=field != "predicate")
            if len(a["predicate"]["text"].split()) != 1:
                raise ValueError("One lexical predicate token required")
            anchor = (a["predicate"]["start"], a["predicate"]["end"])
            if anchor in anchors:
                raise ValueError("Duplicate assertion predicate")
            anchors.add(anchor)
            if (
                a["polarity"] not in {"AFFIRMED", "NEGATED", "CONDITIONAL", "UNKNOWN"}
                or a["phase"] not in {"REPORTED_ACTION", "PROPOSED", "UNKNOWN"}
                or a["attributed"] not in {"YES", "NO", "UNKNOWN"}
            ):
                raise ValueError("Unsupported semantic label")
    return {r["id"]: r for r in rows}


def score(cases, predictions, labels):
    """Exact lexical predicate alignment; source-first misses stay in denominator.

    UNSURE cases excluded explicitly. Partial span matches are not silently counted as TP.
    Syntax proposals are never affirmative impact claims; no financial metric is computed.
    """
    rows = validate_labels(labels, cases)
    tp = fp = fn = excluded = actor_exact = object_exact = matched = phase_correct = 0
    all_gold = all_pred = 0
    null_object_gold = null_object_matched = 0
    flags = {
        name: {"matched_gold": 0, "flagged": 0} for name in ["NEGATED", "CONDITIONAL", "ATTRIBUTED"]
    }
    for c in cases:
        row = rows[c["id"]]
        if row["status"] == "UNSURE":
            excluded += 1
            continue
        pred = predictions[c["id"]]
        gold = row["assertions"]
        all_gold += len(gold)
        null_object_gold += sum(a["object"] is None for a in gold)
        all_pred += len(pred)
        anchors = {(a["predicate"]["start"], a["predicate"]["end"]): a for a in gold}
        used = set()
        for p in pred:
            key = (p["predicate"]["start"], p["predicate"]["end"])
            if key not in anchors or key in used:
                fp += 1
                continue
            used.add(key)
            g = anchors[key]
            tp += 1
            matched += 1
            null_object_matched += g["object"] is None
            actor_exact += p["actor"] == g["actor"]
            object_exact += p["object"] == g["object"]
            phase_correct += p["phase"] == g["phase"]
            for category, applicable, flag in [
                ("NEGATED", g["polarity"] == "NEGATED", "NEGATION_IN_SENTENCE"),
                ("CONDITIONAL", g["polarity"] == "CONDITIONAL", "CONDITIONAL_OR_MODAL"),
                ("ATTRIBUTED", g["attributed"] == "YES", "EMBEDDED_OR_ATTRIBUTED_CLAIM"),
            ]:
                if applicable:
                    flags[category]["matched_gold"] += 1
                    flags[category]["flagged"] += flag in p["review_flags"]
        fn += len(anchors) - len(used)
    return {
        "reviewer_id": labels["reviewer_id"],
        "cases": len(cases),
        "unsure_cases_excluded": excluded,
        "source_assertions": all_gold,
        "syntax_proposals": all_pred,
        "predicate_tp": tp,
        "predicate_fp": fp,
        "predicate_fn": fn,
        "predicate_precision": tp / (tp + fp) if tp + fp else None,
        "predicate_recall": tp / (tp + fn) if tp + fn else None,
        "matched_predicates": matched,
        "actor_exact": actor_exact,
        "object_exact": object_exact,
        "phase_exact": phase_correct,
        "null_object_gold": null_object_gold,
        "null_object_matched": null_object_matched,
        "uncertainty_flags_on_matched_only": flags,
        "human_gold": False,
        "delivery": "disabled",
        "metric": "EXACT_PREDICATE_ANCHOR_DIAGNOSTIC",
    }


def evaluate(root, pin, label_a, label_b):
    files, receipt = verify(root, pin)
    cases, predictions = files["sources.json"], files["predictions.json"]
    a, b = validate_labels(label_a, cases), validate_labels(label_b, cases)
    if label_a["reviewer_id"] == label_b["reviewer_id"]:
        raise ValueError("Distinct reviewers required")
    same, disagreements = 0, []

    def canonical(row):
        return sorted(row["assertions"], key=lambda v: v["predicate"]["start"])

    for c in cases:
        x, y = a[c["id"]], b[c["id"]]
        if x["status"] == "REVIEWED" and y["status"] == "REVIEWED" and canonical(x) == canonical(y):
            same += 1
        else:
            disagreements.append(c["id"])
    return {
        "freeze_sha256": pin,
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": receipt["scope"],
        "label_sha256": [digest(label_a), digest(label_b)],
        "reviewers": [score(cases, predictions, label_a), score(cases, predictions, label_b)],
        "exact_case_agreements": same,
        "cases_requiring_adjudication": disagreements,
        "consensus_gold_created": False,
        "human_gold": False,
        "delivery": "disabled",
    }


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 20_000_000:
        raise ValueError("Bounded local artifact required")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    f = sub.add_parser("freeze")
    for name in ["cases", "predictions", "protocol", "output"]:
        f.add_argument("--" + name, type=Path, required=True)
    f.add_argument("--excluded-text-hashes", type=Path, required=True)
    e = sub.add_parser("evaluate")
    for name in ["root", "label-a", "label-b", "output"]:
        e.add_argument("--" + name, type=Path, required=True)
    e.add_argument("--pin", required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        pin = freeze(
            read_json(args.cases),
            read_json(args.predictions),
            args.output,
            protocol=read_json(args.protocol),
            excluded_text_hashes=read_json(args.excluded_text_hashes),
        )
        print(json.dumps({"freeze_sha256": pin, "delivery": "disabled"}))
    else:
        result = evaluate(args.root, args.pin, read_json(args.label_a), read_json(args.label_b))
        write(args.output, result)
        print(
            json.dumps(
                {
                    "exact_case_agreements": result["exact_case_agreements"],
                    "needs_adjudication": len(result["cases_requiring_adjudication"]),
                    "human_gold": False,
                    "delivery": "disabled",
                }
            )
        )


if __name__ == "__main__":
    main()
