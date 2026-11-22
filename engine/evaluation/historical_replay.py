"""Local archive reconstruction benchmark, separate from strict production replay.

Never backdates acquisition, writes graph state, or enables delivery. Review packets
contain evidence only; frozen predictions and later labels live in separate files.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from engine.adapters.http_sources import SourceClient
from engine.collect_sec import identities
from engine.evaluation.agent_pilot import CLASSES
from engine.evaluation.language_candidate import VERSION, classify
from engine.evaluation.prospective import Paragraphs
from engine.ingestion.contracts import digest

TRACK = "HISTORICAL_ARCHIVE_RECONSTRUCTION_AI"
PROFILES = {"retail_investor", "fund_manager", "financial_expert"}
EXCLUDED = {"0001045810-25-000116"}  # Previously developed H20 worked case.
FINANCIAL = re.compile(r"\b(revenue|sales|margin|income|profit|cost|expense|loss|cash)\w*\b", re.I)
CHANGE = re.compile(r"\b(increased|decreased|grew|declined|higher|lower|charge|improved)\b", re.I)
RISK = re.compile(r"\b(may|could|risk|expect|uncertain|dependent)\w*\b", re.I)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selection(ticker, cik, recent):
    """One original periodic filing per issuer/report period; deterministic selection."""
    rows = []
    for i, form in enumerate(recent["form"]):
        filed, acc = recent["filingDate"][i], recent["accessionNumber"][i]
        doc, period = recent["primaryDocument"][i], recent["reportDate"][i]
        if form not in {"10-Q", "10-K"} or not "2022-01-01" <= filed <= "2025-12-31":
            continue
        if acc in EXCLUDED or (ticker == "SNDK" and filed < "2025-02-21"):
            continue
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", acc):
            raise ValueError("Invalid accession")
        if not re.fullmatch(r"[\w.-]+\.html?", doc) or not period:
            raise ValueError("Invalid document/report period")
        amendments = [
            recent["accessionNumber"][j] for j, f in enumerate(recent["form"])
            if f == form + "/A" and recent["reportDate"][j] == period
        ]
        rows.append({"ticker": ticker, "cik": str(cik), "accession": acc,
                     "filing_date": filed, "report_period": period, "form": form,
                     "cluster_key": ticker + ":" + period,
                     "known_amendments": amendments,
                     "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"})
    unique: dict = {}
    for row in sorted(rows, key=lambda r: (r["filing_date"], r["accession"])):
        unique.setdefault(row["cluster_key"], row)
    return list(unique.values())


def collect(root, user_agent):
    root.mkdir(parents=True, exist_ok=True)
    if (root / "collection.json").exists():
        raise ValueError("Collection already sealed; use a new run")
    client = SourceClient(user_agent=user_agent, cache_dir=root / "captures")
    result: dict = {"track": TRACK, "sources": [], "errors": [], "delivery": "disabled"}
    try:
        index = client.fetch("https://www.sec.gov/files/company_tickers.json")
        issuers = identities(json.loads(index.text))
        result["identity_source_sha256"] = index.content_sha256
        candidates = []
        for ticker, identity in issuers.items():
            cik = identity["cik"]
            doc = client.fetch(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
            body = json.loads(doc.text)
            if int(body["cik"]) != int(cik):
                raise ValueError("Issuer mismatch")
            candidates.extend(selection(ticker, cik, body["filings"]["recent"]))
        # Limit only after issuer/period grouping, before content or model inspection.
        candidates = sorted(candidates, key=lambda r: (r["filing_date"], r["ticker"]))[:100]
        result["candidate_count"] = len(candidates)
        for row in candidates:
            try:
                doc = client.fetch(row["url"])
                name = row["ticker"] + "-" + row["accession"] + ".html"
                path = root / "documents" / name
                path.parent.mkdir(exist_ok=True)
                if path.exists() and sha(path) != doc.content_sha256:
                    raise ValueError("Existing source changed")
                path.write_bytes(doc.text.encode("utf-8"))
                result["sources"].append({**row, "file": "documents/" + name,
                    "source_sha256": doc.content_sha256,
                    "retrieved_at": doc.retrieved_at.isoformat(),
                    "archive_time_basis": "SEC_ACCESSION_ORIGINAL_FILE_RETRIEVED_NOW",
                    "strict_production_replay_eligible": False})
            except Exception as exc:
                result["errors"].append({"accession": row["accession"], "error": str(exc)})
        write(root / "collection.json", result)
    finally:
        client.close()
    return {"captured": len(result["sources"]), "errors": len(result["errors"])}


def excerpts(text):
    parser = Paragraphs()
    parser.feed(text)
    parser.flush()
    rows = list(dict.fromkeys(parser.rows))
    eligible = [(i, s) for i, s in enumerate(rows)
                if 120 <= len(s) <= 1600 and FINANCIAL.search(s)]
    chosen = []
    # Sampling strata are fixed before predictions. They are NOT reference labels.
    for predicate in (lambda s: CHANGE.search(s) and not RISK.search(s),
                      lambda s: RISK.search(s),
                      lambda s: not CHANGE.search(s) and not RISK.search(s)):
        pool = [(i, s) for i, s in eligible if predicate(s) and (i, s) not in chosen]
        # Prefer narrative text over sparse financial table rows without a sentence.
        pool.sort(key=lambda x: (not bool(re.search(r"[a-z]{3} [a-z]{3}", x[1])), x[0]))
        if pool:
            chosen.append(pool[0])
    if len(chosen) != 3:
        raise ValueError("Insufficient distinct source passages")
    return [{"paragraph_index": i, "text": s, "text_sha256": digest(s)} for i, s in chosen]


def partition(filed):
    return "development" if filed < "2024-01-01" else (
        "calibration" if filed < "2025-01-01" else "holdout")


def freeze(root):
    collection = read(root / "collection.json")
    if not 50 <= len(collection["sources"]) <= 100:
        raise ValueError("Need 50–100 captured issuer-period clusters")
    cases: list[dict] = []
    seen: set[str] = set()
    failures: list[dict] = []
    for source in collection["sources"]:
        key = source["cluster_key"]
        if key in seen:
            raise ValueError("Duplicate issuer-period cluster")
        seen.add(key)
        path = (root / source["file"]).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != source["source_sha256"]:
            raise ValueError("Source path/hash invalid")
        try:
            passages = excerpts(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            failures.append({"cluster_key": key, "error": str(exc)})
            continue
        cases.append({**source, "id": "H" + str(len(cases) + 1).zfill(3),
                      "split": partition(source["filing_date"]), "passages": passages,
                      "archive_cutoff_date": source["filing_date"],
                      "prior_exposure_risk": any("H20" in p["text"] for p in passages)})
    if not 50 <= len(cases) <= 100:
        raise ValueError("Insufficient reviewable clusters")
    # Identical passages cannot leak a reference across partitions; retain but flag.
    partitions: dict[str, set[str]] = {}
    for c in cases:
        for p in c["passages"]:
            partitions.setdefault(p["text_sha256"], set()).add(c["split"])
    for c in cases:
        c["cross_split_text_reuse"] = any(len(partitions[p["text_sha256"]]) > 1
                                         for p in c["passages"])
        c["clean_holdout_eligible"] = (c["split"] == "holdout"
                                      and not c["cross_split_text_reuse"]
                                      and not c["prior_exposure_risk"])
    packet = {"track": TRACK, "cases": cases, "packet_id": digest(cases),
              "source_root": str(root.resolve()), "instructions_version": "history-label-v1"}
    now = datetime.now(UTC).isoformat()
    predictions = {c["id"]: [classify(p["text"]) for p in c["passages"]] for c in cases}
    sealed = {"packet_id": packet["packet_id"], "frozen_at": now,
              "version": VERSION, "predictions": predictions,
              "predictor_sha256": sha(Path(__file__).with_name("language_candidate.py")),
              "graph_policy": "UNAVAILABLE_NO_POINT_IN_TIME_VERIFIED_GRAPH",
              "price_prediction": "NOT_RUN", "delivery": "disabled"}
    write(root / "blind-input.json", packet)
    write(root / "sealed-predictions.json", sealed)
    receipt = {"track": TRACK, "packet_id": packet["packet_id"], "frozen_at": now,
               "packet_sha256": sha(root / "blind-input.json"),
               "prediction_sha256": sha(root / "sealed-predictions.json"),
               "collection_sha256": sha(root / "collection.json"),
               "clusters": len(cases), "passages": 3 * len(cases),
               "split_counts": dict(Counter(c["split"] for c in cases)),
               "clean_holdout_clusters": sum(c["clean_holdout_eligible"] for c in cases),
               "capture_errors": collection["errors"], "passage_failures": failures,
               "published_data": False, "delivery": "disabled"}
    write(root / "freeze-receipt.json", receipt)
    return receipt


def verify(root):
    receipt = read(root / "freeze-receipt.json")
    for name, key in (("blind-input.json", "packet_sha256"),
                      ("sealed-predictions.json", "prediction_sha256"),
                      ("collection.json", "collection_sha256")):
        if sha(root / name) != receipt[key]:
            raise ValueError("Frozen artifact changed")
    pack = read(root / "blind-input.json")
    if digest(pack["cases"]) != pack["packet_id"] or pack["packet_id"] != receipt["packet_id"]:
        raise ValueError("Packet identity invalid")
    for c in pack["cases"]:
        path = (root / c["file"]).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != c["source_sha256"]:
            raise ValueError("Source evidence changed")
        if excerpts(path.read_text(encoding="utf-8")) != c["passages"]:
            raise ValueError("Passages no longer match source")
    return pack, read(root / "sealed-predictions.json"), receipt


def validate_review(pack, review, frozen_at):
    if (review.get("track") != TRACK or review.get("profile") not in PROFILES
            or review.get("packet_id") != pack["packet_id"]
            or review.get("blind_to_predictions") is not True
            or review.get("blind_to_other_reviews") is not True):
        raise ValueError("Invalid blind AI review provenance")
    at = datetime.fromisoformat(review["reviewed_at"])
    if at.tzinfo is None or not datetime.fromisoformat(frozen_at) <= at <= datetime.now(UTC):
        raise ValueError("Review must follow freeze")
    cases = {c["id"]: c for c in pack["cases"]}
    rows = review["labels"]
    if len(rows) != len(cases) or {r["case_id"] for r in rows} != set(cases):
        raise ValueError("Exact cluster coverage required")
    for row in rows:
        case = cases[row["case_id"]]
        if row["source_sha256"] != case["source_sha256"] or len(row["passages"]) != 3:
            raise ValueError("Wrong source or passage coverage")
        for label, passage in zip(row["passages"], case["passages"], strict=True):
            if (label["language"] not in CLASSES
                    or label["impact_sign"] not in {"POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"}
                    or type(label["numeric_effect_supported"]) is not bool
                    or len(label["reason"].strip()) < 15
                    or not label["quote"] or label["quote"] not in passage["text"]):
                raise ValueError("Invalid evidence-bound label")
    return {r["case_id"]: r for r in rows}


def label_key(label):
    return (label["language"], label["impact_sign"], label["numeric_effect_supported"])


def evaluate(root):
    pack, sealed, receipt = verify(root)
    votes = {profile: validate_review(pack, read(root / (profile + ".json")),
                                     receipt["frozen_at"]) for profile in sorted(PROFILES)}
    if any(read(root / (p + ".json"))["profile"] != p for p in PROFILES):
        raise ValueError("Duplicate reviewer profile")
    details: list[dict] = []
    totals: Counter[str] = Counter()
    for c in pack["cases"]:
        for i in range(3):
            labels = [votes[p][c["id"]]["passages"][i] for p in sorted(PROFILES)]
            counts = Counter(label_key(v) for v in labels)
            key, n = counts.most_common(1)[0]
            reference = key if n >= 2 else None
            pred = sealed["predictions"][c["id"]][i]["label"]
            group = c["split"]
            totals[group + "_total"] += 1
            totals["unanimous" if n == 3 else "disputed"] += 1
            if reference:
                totals[group + "_resolved"] += 1
                totals[group + "_language_matches"] += int(pred == reference[0])
                if c["clean_holdout_eligible"]:
                    totals["clean_holdout_resolved"] += 1
                    totals["clean_holdout_language_matches"] += int(pred == reference[0])
            details.append({"case_id": c["id"], "passage": i, "split": group,
                            "vote_count": n, "reference": reference,
                            "prediction": pred, "match": pred == reference[0] if reference else None})
    write(root / "comparison-private.json", details)
    report = {"track": TRACK, "packet_id": pack["packet_id"],
              "clusters": len(pack["cases"]), "passages": len(details),
              "profiles": {p: len(v) for p, v in votes.items()}, "counts": dict(totals),
              "reference_method": "THREE_BLIND_AI_VOTES_MAJORITY_FULL_LABEL_TUPLE",
              "status": "BLIND_REVIEW_COMPLETE", "human_labels": 0,
              "push_precision": None, "two_hop_recall": None, "stock_prediction_accuracy": None,
              "graph_promotions": 0, "delivery": "disabled",
              "limitations": ["AI consensus is not human truth or independent causal identification",
                  "Historical LLM pretraining contamination cannot be excluded",
                  "Archive reconstruction is not first-seen production replay",
                  "Financial filing sample is not all market news; no two-hop graph evaluated",
                  "Three sampling strata do not guarantee positive/negative class proportions",
                  "Cross-split exact reuse/exposed H20 passages excluded only from clean subset",
                  "Near-duplicate boilerplate and implicit prior knowledge may remain"]}
    write(root / "evaluation.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["collect", "freeze", "verify", "evaluate"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--user-agent", default="Narrative research linhpm.vpub@gmail.com")
    args = parser.parse_args()
    if args.action == "collect":
        result = collect(args.root, args.user_agent)
    elif args.action == "freeze":
        result = freeze(args.root)
    elif args.action == "verify":
        result = {"verified": True, "clusters": len(verify(args.root)[0]["cases"])}
    else:
        result = evaluate(args.root)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
