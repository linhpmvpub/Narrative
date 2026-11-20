"""Offline P3 replay: persists every pair, including suppressed candidates."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine

from engine.adapters.fixture import FixtureEvent, FixtureSourceAdapter
from engine.db import database
from engine.evaluation.baselines import compare_baselines
from engine.graph.demo import install_context, load_context
from engine.graph.matcher import Edge
from engine.ingestion.contracts import digest
from engine.ingestion.service import ingest_fixtures
from engine.models.schema_v3 import policy_traces
from engine.scoring.policy import EventInput, NarrativeInput, Observation, evaluate, render_card


def event_input(item: FixtureEvent, receipt: dict, context: dict) -> EventInput:
    signal = context["policy"]["signals"].get(item.event_id)
    observations: tuple[Observation, ...] = ()
    conditions = ()
    if signal:
        if (
            signal["source_headline_sha256"] != digest(item.headline_factual)
            or signal["metric_id"] != item.driver_entity_id
            or signal["evidence_url"] != item.source_url
            or datetime.fromisoformat(signal["available_at"].replace("Z", "+00:00"))
            != item.available_at
        ):
            raise ValueError("Synthetic observation no longer matches source fixture")
        observations = (
            Observation(
                metric_id=signal["metric_id"],
                direction=signal["direction"],
                evidence_url=item.source_url,
                available_at=item.available_at,
            ),
        )
        conditions = tuple(signal["confirmed_conditions"])
    return EventInput(
        event_id=item.event_id,
        event_version_id=receipt["event_version_id"],
        canonical_key=item.canonical_event_key,
        issuer=item.primary_entity_id,
        event_type=item.event_type,
        headline=item.headline_factual,
        published_at=item.published_at,
        first_seen_at=item.first_seen_at,
        available_at=item.available_at,
        is_synthetic=True,
        rights="approved_fixture_only",
        evidence_urls=(item.source_url,),
        source_span_valid=True,
        identity_valid=receipt["reason"] not in ("issuer_identity_mismatch", "unknown_entity"),
        observations=observations,
        evidence_quality=item.fixture_metadata.q_test_input,
        is_correction=item.fixture_metadata.is_correction,
        duplicate=bool(item.fixture_metadata.reprint_of),
        period_valid=item.event_type != "MISALIGNED_PERIOD",
        confirmed_conditions=conditions,
    )


def replay(engine: Engine, records: list[FixtureEvent], as_of: datetime, context_id: str) -> dict:
    with engine.connect() as conn:
        context = load_context(conn, context_id, as_of)
    receipts = {r["input_id"]: r for r in ingest_fixtures(engine, records, as_of)}
    edges = [Edge.model_validate(e) for e in context["edges"]]
    narratives = [
        NarrativeInput.model_validate({**n, "version_id": context_id + ":" + n["version_id"]})
        for n in context["narratives"]
    ]
    outputs: list[dict] = []
    for item in records:
        event = event_input(item, receipts[item.event_id], context)
        for narrative in narratives:
            trace = evaluate(event, narrative, edges, set(context["nodes"]), as_of, demo=True)
            trace["context_id"] = context_id
            trace["ingestion_status"] = receipts[item.event_id]["status"]
            key = digest(
                [
                    item.event_id,
                    narrative.id,
                    as_of.isoformat(),
                    context_id,
                    trace["policy_version"],
                    trace["input_sha256"],
                ]
            )
            trace["decision_id"] = key
            card = render_card(event, narrative, trace)
            outputs.append({"is_synthetic": True, "decision_trace": trace, "card": card})
    with engine.begin() as conn:
        for output in outputs:
            trace = output["decision_trace"]
            existing = conn.execute(
                select(policy_traces.c.trace).where(policy_traces.c.id == trace["decision_id"])
            ).scalar_one_or_none()
            if existing is not None:
                if existing != trace:
                    raise ValueError("Replay changed an immutable decision trace")
                continue
            conn.execute(
                policy_traces.insert().values(
                    id=trace["decision_id"],
                    input_id=trace["event_id"],
                    narrative_id=trace["narrative_id"],
                    as_of=as_of,
                    policy_version=trace["policy_version"],
                    trace=trace,
                )
            )
    return {
        "is_synthetic": True,
        "context_id": context_id,
        "as_of": as_of.isoformat(),
        "delivery": "disabled",
        "counts": dict(Counter(x["decision_trace"]["decision"] for x in outputs)),
        "results": outputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="P3 synthetic replay, delivery always disabled")
    parser.add_argument("--fixture", type=Path, default=Path("fixtures/events.jsonl"))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument(
        "--graph", type=Path, default=Path("fixtures/demo_verified_relationships.json")
    )
    parser.add_argument("--policy", type=Path, default=Path("fixtures/p3_demo_policy.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-output", type=Path)
    parser.add_argument("--baseline-output", type=Path)
    args = parser.parse_args()
    engine = database()
    try:
        context_id = install_context(engine, args.config, args.graph, args.policy)
        records = FixtureSourceAdapter().read(args.fixture)
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        result = replay(engine, records, as_of, context_id)
        if args.output:
            args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if args.sample_output:
            sample = next(
                x
                for x in result["results"]
                if x["decision_trace"]["event_id"] == "F021"
                and x["decision_trace"]["narrative_id"] == "N08"
            )
            args.sample_output.write_text(json.dumps(sample, indent=2), encoding="utf-8")
        if args.baseline_output:
            args.baseline_output.write_text(
                json.dumps(compare_baselines(records, result, as_of), indent=2), encoding="utf-8"
            )
        print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
