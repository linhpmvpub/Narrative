"""Immutable local A/B/C company experiment; never a production feed or label writer."""

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

import httpx

from engine.evaluation import company_benchmark as cb
from engine.evaluation.benchmark import local_environment, pin, read, state, verify_pin, write
from engine.ingestion.contracts import digest
from engine.local_analyst import LocalAnalyst, parse_response
from engine.shadow_analyst import POLICY, VERSION, catalog, model_routes, retrieve, validate


def prepare(pointer, output):
    """Use all frozen source units, including those rejected by deterministic matching."""
    p, output = read(pointer)["company_benchmark"], Path(output)
    if output.exists():
        raise ValueError("New immutable experiment directory required")
    receipt = cb.frozen(p["freeze"], p["freeze_sha256"])
    at = datetime.fromisoformat(receipt["as_of"])
    rows = read(Path(p["freeze"]) / "inputs.json")
    with local_environment(receipt["article_root"]):
        snapshot, bundles = state(p["profiles"], at)
        target_ids = {r["input"]["profile_id"] for r in rows}
        bundles = {k: b for k, b in bundles.items() if k in target_ids}
        if len({b.company_id for b in bundles.values()}) != len(bundles) or len(bundles) > 20:
            raise ValueError("Unique bounded company universe required")
        routes = catalog(bundles, at)
        companies = [{"company_id": b.company_id, "ticker": b.ticker, "name": b.legal_name}
                     for b in sorted(bundles.values(), key=lambda b: b.id)]
        grouped: dict = {}
        baseline = []
        for row in rows:
            value = row["input"]
            published = value["article"].get("published_at")
            if published:
                published_at = datetime.fromisoformat(published)
                if published_at.tzinfo is None or published_at > at:
                    raise ValueError("Source publication is after the experiment cutoff or lacks timezone")
            key = digest({k: v for k, v in value.items() if k != "profile_id"})
            if key not in grouped:
                source = value["article"]["title"] + "\n\n" + value["article"].get("summary", "")
                representation = "RSS_EXCERPT"
                if "source_observation" in value:
                    from engine.article_cards import substantive_blocks

                    blocks, _ = substantive_blocks(value["source_observation"], at, article_root=receipt["article_root"])
                    source = value["article"]["title"] + "\n\n" + "\n\n".join(b["text"] for b in blocks)
                    representation = "REVIEWED_SUBSTANTIVE_BODY"
                grouped[key] = {"id": key, "source": source, "source_sha256": digest(source),
                                "representation": representation, "company_units": {},
                                "source_metadata": {k: v for k, v in value["article"].items()
                                                    if k in {"published_at", "source_name", "url", "verification"}},
                                "retrieval": retrieve(source, routes)}
            company = bundles[value["profile_id"]].company_id
            if company in grouped[key]["company_units"]:
                raise ValueError("Duplicate source-company unit")
            grouped[key]["company_units"][company] = row["id"]
            baseline.append(cb.predict(row, bundles[value["profile_id"]], at, receipt["article_root"]))
        if any(set(s["company_units"]) != {c["company_id"] for c in companies} for s in grouped.values()):
            raise ValueError("Every source needs the same complete company universe")
        if state(p["profiles"], at)[0] != snapshot:
            raise ValueError("Runtime/profile change during preparation")
    cb.frozen(p["freeze"], p["freeze_sha256"])
    output.mkdir(parents=True)
    write(output / "inputs.json", list(grouped.values()))
    write(output / "baseline.json", baseline)
    write(output / "catalog.json", routes)
    write(output / "experiment.json", {"schema": VERSION, "as_of": receipt["as_of"], "policy": POLICY,
        "companies": companies, "state": snapshot, "company_benchmark": p,
        "files": [pin(output / n) for n in ("inputs.json", "baseline.json", "catalog.json")],
        "reference_use": "EXPOSED_DEVELOPMENT_NOT_FRESH_BLIND", "delivery": "disabled"})
    return {"articles": len(grouped), "company_units": len(rows), "routes": len(routes),
            "experiment": pin(output / "experiment.json")}


def verify(directory, expected):
    directory = Path(directory)
    verify_pin({"path": directory / "experiment.json", "sha256": expected})
    exp = read(directory / "experiment.json")
    if exp["schema"] != VERSION or exp["policy"] != POLICY:
        raise ValueError("Experiment contract changed")
    for item in exp["files"]:
        verify_pin(item)
    p = exp["company_benchmark"]
    cb.frozen(p["freeze"], p["freeze_sha256"])
    with local_environment():
        if state(p["profiles"], datetime.fromisoformat(exp["as_of"]))[0] != exp["state"]:
            raise ValueError("Runtime/profile changed; prepare a new experiment")
    return exp


def run(directory, expected, output, analyst=None):
    directory, output = Path(directory), Path(output)
    exp = verify(directory, expected)
    if output.exists():
        raise ValueError("New immutable run required")
    output.mkdir(parents=True)
    inputs = read(directory / "inputs.json")
    arms: dict = {"B_generic": [], "C_graph": []}
    records = []
    # No labels or A predictions are sent to the model. Independent stateless B/C calls.
    for index, item in enumerate(inputs):
        for arm in (list(arms) if index % 2 == 0 else list(reversed(arms))):
            packet = {"source": item["source"], "representation": item["representation"],
                      "source_metadata": item["source_metadata"], "as_of": exp["as_of"],
                      "companies": exp["companies"], "graph_mode": arm == "C_graph"}
            if arm == "C_graph":
                packet["routes"] = model_routes(item["retrieval"])
            record = {"source_id": item["id"], "arm": arm, "packet_sha256": digest(packet)}
            if analyst is None:
                record.update(status="UNAVAILABLE", reason="No local model configured")
            else:
                try:
                    raw = analyst.analyze(packet)
                    record["model_receipt"] = raw
                    proposal = parse_response(raw)
                    predictions = validate(proposal, item["source"], exp["companies"], item["retrieval"], graph=arm == "C_graph")
                    record.update(status="COMPLETED", proposals=proposal.model_dump(mode="json"))
                    arms[arm].extend({**d, "id": item["company_units"][d["company_id"]]} for d in predictions)
                except (ValueError, httpx.HTTPError, KeyError) as exc:
                    record.update(status="FAILED", reason=str(exc)[:1000])
            records.append(record)
            write(output / f"call-{index:03d}-{arm}.json", record)
    verify(directory, expected)
    # Prediction artifacts precede reading labels. A failed arm has no fabricated benchmark score.
    predictions = {"A_engine": read(directory / "baseline.json"), **arms}
    write(output / "predictions.json", predictions)
    p = exp["company_benchmark"]
    ref = cb.load_reference(p["reference"], p["reference_sha256"], p["freeze_sha256"])
    rows = read(Path(p["freeze"]) / "inputs.json")
    reports = {}
    for arm, preds in predictions.items():
        calls = [r for r in records if r["arm"] == arm]
        successful = len(preds) == len(rows)
        latencies = sorted(r["model_receipt"]["seconds"] for r in calls if "model_receipt" in r)
        usage = [r["model_receipt"]["response"] for r in calls if "model_receipt" in r]
        reports[arm] = {"status": "COMPLETED" if successful else "UNAVAILABLE" if analyst is None else "INCOMPLETE",
            "benchmark": cb.score(rows, preds, ref["labels"]) if successful else None,
            "raw_model_benchmark": cb.score(rows, [{"id": d["id"], "selected": d["raw_relevance"] == "RELEVANT",
                "priority": d["raw_attention"] == "PRIORITY"} for d in preds], ref["labels"])
                if successful and arm != "A_engine" else None,
            "predicted_units": len(preds), "expected_units": len(rows),
            "withheld_units": sum(bool(d.get("validation_faults")) for d in preds),
            "abstained_units": sum(d.get("status") == "ABSTAINED" for d in preds),
            "latency_seconds_p50": latencies[math.ceil(len(latencies)*.5)-1] if latencies else None,
            "latency_seconds_p95": latencies[math.ceil(len(latencies)*.95)-1] if latencies else None,
            "prompt_tokens": sum(u.get("prompt_eval_count", 0) for u in usage),
            "output_tokens": sum(u.get("eval_count", 0) for u in usage),
            "api_charge": 0 if analyst is not None and calls else None,
            "hardware_energy_cost": "UNMEASURED"}
    report = {"schema": VERSION, "arms": reports, "articles": len(inputs), "company_units": len(rows),
              "retrieved_routes": [len(i["retrieval"]) for i in inputs],
              "reference_kind": "EXPOSED_AI_DEVELOPMENT_NOT_HUMAN_GOLD", "model": analyst.identity if analyst else None,
              "policy": POLICY, "limitations": ["lexical retrieval may miss paraphrases", "semantic truth not proven by validators",
                  "single primary event per company/article", "no explanation-fidelity or human utility labels",
                  "no causal or financial impact calibration", "no production promotion"], "delivery": "disabled"}
    write(output / "report.json", report)
    write(output / "receipt.json", {"experiment_sha256": expected,
        "files": [pin(path) for path in sorted(output.glob("*.json"))], "delivery": "disabled"})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run"])
    parser.add_argument("--pointer", type=Path, default=Path("source-cache/quality-benchmark-current.json"))
    parser.add_argument("--experiment", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11435")
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.pointer, args.output)
    else:
        if not args.experiment or not args.sha256:
            parser.error("Pinned experiment required")
        analyst = LocalAnalyst(args.model, endpoint=args.endpoint) if args.model else None
        try:
            result = run(args.experiment, args.sha256, args.output, analyst)
        finally:
            if analyst:
                analyst.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
