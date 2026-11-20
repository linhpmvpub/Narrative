import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from engine.adapters.fixture import FixtureSourceAdapter
from engine.evaluation.baselines import compare_baselines
from engine.graph.demo import install_context, load_context
from engine.graph.matcher import Edge, match_paths
from engine.ingestion.contracts import digest
from engine.ingestion.service import initialize_demo
from engine.models.schema_v3 import metadata, policy_traces
from engine.replay import event_input, replay
from engine.scoring.policy import EventInput, Materiality, NarrativeInput, Observation, evaluate

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 1, tzinfo=UTC)
BEFORE = NOW - timedelta(days=40)
URL = "https://example.invalid/unit-test-only"


def edge(id="E1", start="A", end="B", **changes):
    args = dict(
        id=id,
        from_entity=start,
        to_entity=end,
        family="PRODUCT_MARKET",
        mechanism="Unit-test mechanism",
        status="verified",
        sign="positive",
        strength=0.6,
        confidence=0.9,
        recorded_at=BEFORE,
        valid_from=BEFORE,
        reviewed_at=BEFORE,
        reviewer="unit-tester",
        evidence_urls=(URL,),
        evidence_available_at=BEFORE,
    )
    return Edge.model_validate({**args, **changes})


def event(**changes):
    # Entirely fabricated unit-test contract, never ingested as live source data.
    args = dict(
        event_id="test-event",
        event_version_id="test-version",
        canonical_key="test-key",
        issuer="CO_MU",
        event_type="FILING",
        headline="Unit test observation",
        published_at=NOW,
        first_seen_at=NOW,
        available_at=NOW,
        is_synthetic=False,
        rights="approved",
        evidence_urls=(URL,),
        source_span_valid=True,
        identity_valid=True,
        observations=(
            Observation(metric_id="MU_REVENUE", direction=1, evidence_url=URL, available_at=NOW),
        ),
        evidence_quality=1.0,
        materiality=Materiality(
            value=1,
            metric_id="MU_REVENUE",
            rubric_version="unit-test-only",
            scale="test scale",
            horizon="test period",
            evidence_url=URL,
        ),
    )
    return EventInput.model_validate({**args, **changes})


def narrative(**changes):
    return NarrativeInput.model_validate(
        {
            "id": "N01",
            "version_id": "unit-narrative-v1",
            "ticker": "MU",
            "available_at": BEFORE,
            "outcomes": {"MU_REVENUE": 1},
            "hypothesis_polarity": "favorable",
            "watch_next": "Test next reporting period",
            "is_synthetic": False,
            **changes,
        }
    )


def decide(item=None, nav=None, edges=None, **kwargs):
    return evaluate(
        item or event(),
        nav or narrative(),
        edges or [],
        {"CO_MU", "MU_REVENUE", "A", "B", "C", "D"},
        NOW,
        **kwargs,
    )


def test_max_two_hops_no_loops_and_best_path_not_sum():
    edges = [
        edge("one", "A", "B"),
        edge("two", "B", "C", sign="negative"),
        edge("three", "C", "D"),
        edge("loop", "B", "A"),
        edge("alternate", "A", "C", strength=0.2),
    ]
    args = dict(
        nodes={"A", "B", "C", "D"}, start="A", as_of=NOW, source_confidence=0.8, synthetic=False
    )
    paths = match_paths(edges, targets={"C"}, **args)
    assert [e.id for e in paths[0].edges] == ["one", "two"]
    assert paths[0].relevance == pytest.approx(0.306)
    assert paths[0].confidence == 0.8 and paths[0].sign == "negative"
    assert len(paths) == 2
    assert match_paths(edges[:3], targets={"D"}, **args) == []
    with pytest.raises(ValueError):
        match_paths(edges, targets={"D"}, max_hops=3, **args)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "candidate"},
        {"status": "rejected"},
        {"status": "stale"},
        {"recorded_at": NOW + timedelta(seconds=1)},
        {"reviewed_at": NOW + timedelta(seconds=1)},
        {"evidence_available_at": NOW + timedelta(seconds=1)},
        {"valid_from": NOW + timedelta(seconds=1)},
        {"valid_until": NOW},
        {"evidence_urls": ()},
        {"reviewer": None},
        {"strength": None},
        {"is_synthetic": True},
    ],
)
def test_edge_gates(changes):
    assert (
        match_paths(
            [edge(**changes)],
            nodes={"A", "B"},
            start="A",
            targets={"B"},
            as_of=NOW,
            source_confidence=1,
            synthetic=False,
        )
        == []
    )


def test_unknown_nodes_rejected():
    with pytest.raises(ValueError, match="Unknown"):
        match_paths(
            [edge()],
            nodes={"A"},
            start="A",
            targets={"A"},
            as_of=NOW,
            source_confidence=1,
            synthetic=False,
        )


def test_exact_weighted_score_and_no_delivery():
    trace = decide()
    assert trace["score"] == 100
    assert trace["score_components"] == {"R": 1, "M": 1, "N": 1, "Q": 1, "T": 1, "U": 1}
    assert trace["decision"] == "push" and trace["send_recommendation"]
    assert trace["delivery_status"] == "disabled" and trace["sent_at"] is None
    assert trace["policy_version"].endswith(digest(trace["policy_snapshot"])[:12])
    lower = decide(user_fit=0)
    assert lower["score"] == 90
    assert lower["observations"] == trace["observations"]


@pytest.mark.parametrize(
    "changes,decision,reason",
    [
        ({"rights": "pending"}, "suppressed", "source_rights_not_approved"),
        ({"is_synthetic": True}, "suppressed", "synthetic_live_forbidden"),
        ({"identity_valid": False}, "suppressed", "invalid_identity"),
        ({"duplicate": True}, "suppressed", "duplicate_or_delivered"),
        ({"delivered": True}, "suppressed", "duplicate_or_delivered"),
        ({"source_span_valid": False}, "review_required", "missing_provenance"),
        ({"period_valid": False}, "review_required", "incompatible_period"),
        ({"core_numbers_conflict": True}, "review_required", "contradictory_core_numbers"),
        ({"unverified_contract_claim": True}, "suppressed", "unsupported_contract_claim"),
        ({"evidence_quality": 0.69}, "suppressed", "low_evidence_quality"),
        ({"evidence_quality": None}, "review_required", "unknown_evidence_quality"),
    ],
)
def test_hard_gates_before_scoring(changes, decision, reason):
    trace = decide(event(**changes))
    assert trace["decision"] == decision and reason in trace["reasons"]
    assert trace["score"] is None and not trace["send_recommendation"]


def test_quality_and_unknown_materiality_push_gates():
    assert decide(event(evidence_quality=0.75))["decision"] == "digest"
    unknown = decide(event(materiality=None))
    assert unknown["decision"] == "review_required" and unknown["score"] is None
    assert unknown["score_bounds"] == [80, 100]
    assert not unknown["send_recommendation"]


def test_aware_future_and_narrative_version_gates():
    trace = decide(event(available_at=NOW + timedelta(seconds=1)))
    assert trace["reasons"] == ["future_available_at"]
    assert (
        decide(nav=narrative(available_at=NOW + timedelta(seconds=1)))["decision"] == "suppressed"
    )
    with pytest.raises(ValueError):
        evaluate(event(), narrative(), [], {"CO_MU", "MU_REVENUE"}, NOW.replace(tzinfo=None))


def test_stance_adverse_thesis_and_mixed_evidence():
    negative = Observation(metric_id="MU_REVENUE", direction=-1, evidence_url=URL, available_at=NOW)
    trace = decide(
        event(observations=(negative,)),
        narrative(outcomes={"MU_REVENUE": -1}, hypothesis_polarity="adverse"),
    )
    assert trace["stance"] == "SUPPORTS" and trace["economic_effect"] == "ADVERSE"
    assert decide(event(observations=(negative,)))["stance"] == "CHALLENGES"
    mixed = decide(event(observations=event().observations + (negative,)))
    assert mixed["stance"] == "MIXED"
    assert len(mixed["observations"]) == 2


def test_conditions_unknown_sign_and_candidate_cannot_push():
    obs = Observation(metric_id="A", direction=1, evidence_url=URL, available_at=NOW)
    mat = Materiality(
        value=1,
        metric_id="A",
        rubric_version="unit",
        scale="unit",
        horizon="unit",
        evidence_url=URL,
    )
    item = event(observations=(obs,), materiality=mat)
    route = edge(start="A", end="MU_REVENUE", conditions=("confirmed_cost",))
    trace = decide(item, edges=[route])
    assert trace["stance"] == "INSUFFICIENT_EVIDENCE" and trace["conditional_stance"] == "SUPPORTS"
    assert (
        decide(
            item.model_copy(update={"confirmed_conditions": ("confirmed_cost",)}), edges=[route]
        )["stance"]
        == "SUPPORTS"
    )
    assert (
        decide(item, edges=[edge(start="A", end="MU_REVENUE", sign="conditional")])["stance"]
        == "INSUFFICIENT_EVIDENCE"
    )
    assert (
        decide(item, edges=[edge(start="A", end="MU_REVENUE", status="candidate")])["decision"]
        == "review_required"
    )
    assert decide(
        item, edges=[edge(start="A", end="MU_REVENUE", recorded_at=NOW + timedelta(days=1))]
    )["reasons"] == ["graph_lookahead"]


def test_stale_timeliness_and_price_only():
    old = NOW - timedelta(days=90)
    trace = decide(event(available_at=old, published_at=old, first_seen_at=old))
    assert trace["score_components"]["T"] == pytest.approx(0.5)
    assert trace["score"] == 95
    assert decide(event(event_type="PRICE_ONLY"))["stance"] == "NO_CHANGE"


@pytest.fixture
def demo_run(db):
    initialize_demo(db)
    context_id = install_context(
        db,
        ROOT / "config",
        ROOT / "fixtures/demo_verified_relationships.json",
        ROOT / "fixtures/p3_demo_policy.json",
    )
    records = FixtureSourceAdapter().read(ROOT / "fixtures/events.jsonl")
    return context_id, records, replay(db, records, NOW, context_id)


def test_f021_response_and_replay_immutability(db, demo_run):
    context_id, records, result = demo_run
    assert len(result["results"]) == 310
    response = next(
        x
        for x in result["results"]
        if x["card"]["event_id"] == "F021" and x["card"]["narrative_id"] == "N08"
    )
    trace = response["decision_trace"]
    assert [e["id"] for e in trace["selected_path"]["edges"]] == ["R026", "R027"]
    assert trace["selected_path"]["confidence"] == 0.9
    assert trace["stance"] == "INSUFFICIENT_EVIDENCE" and trace["conditional_stance"] == "SUPPORTS"
    assert trace["decision"] == "review_required" and trace["score"] is None
    assert trace["conditional_reasons"] == ["contracted_cost_rises", "cost_not_offset"]
    assert replay(db, records, NOW, context_id) == result
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(policy_traces)) == 310
        edges = metadata.tables["rie_relationships"]
        assert set(conn.execute(select(edges.c.status)).scalars()) == {"candidate"}
        docs = metadata.tables["rie_documents"]
        assert set(trace["evidence_urls"]) <= set(conn.execute(select(docs.c.source_url)).scalars())
        versions = metadata.tables["rie_narrative_versions"]
        assert conn.execute(select(versions).where(versions.c.available_at <= NOW)).first() is None


def test_golden_p3_graph_cases_and_baselines(db, demo_run):
    _, records, result = demo_run
    traces = {
        (r["card"]["event_id"], r["card"]["narrative_id"]): r["decision_trace"]
        for r in result["results"]
    }
    cases = {c["case_id"]: c for c in json.loads((ROOT / "tests/golden_cases.json").read_text())}
    assert [
        e["id"]
        for e in traces["F003", cases["G03"]["assertions"]["narrative"]]["selected_path"]["edges"]
    ] == ["R007", "R005"]
    assert traces["F024", "N10"]["stance"] == "INSUFFICIENT_EVIDENCE"
    assert traces["F029", "N01"]["decision"] == "suppressed"
    assert traces["F030", "N03"]["reasons"] == [cases["G07"]["assertions"]["reason"]]
    assert traces["F025", "N03"]["decision"] == "suppressed"
    assert traces["F027", "N07"]["decision"] == "review_required"
    assert traces["F028", "N09"]["reasons"] == ["invalid_identity"]
    assert traces["F026", "N01"]["stance"] == "NO_CHANGE"
    assert traces["F026", "N09"]["decision"] == "suppressed"
    comparison = compare_baselines(records, result, NOW)
    assert comparison["corpus_count"] == 30 and comparison["pair_count"] == 300
    assert "F030" not in comparison["corpus_input_ids"]
    assert comparison["B1"]["status"] == "UNAVAILABLE" and comparison["precision"] is None


def test_no_gold_stance_or_materiality_leakage(db, demo_run):
    context_id, records, _ = demo_run
    with db.connect() as conn:
        context = load_context(conn, context_id, NOW)
    original = next(r for r in records if r.event_id == "F021")
    altered = original.model_copy(
        update={
            "fixture_metadata": original.fixture_metadata.model_copy(
                update={"illustrative_stance": "CHALLENGES", "m_test_input": 1.0}
            )
        }
    )
    receipt = {"event_version_id": "unit", "reason": "new_fact"}
    assert event_input(original, receipt, context) == event_input(altered, receipt, context)


def test_demo_refused_in_production_and_before_snapshot(db):
    with pytest.raises(ValueError, match="synthetic"):
        install_context(
            db,
            ROOT / "config",
            ROOT / "fixtures/demo_verified_relationships.json",
            ROOT / "fixtures/p3_demo_policy.json",
        )
    initialize_demo(db)
    context_id = install_context(
        db,
        ROOT / "config",
        ROOT / "fixtures/demo_verified_relationships.json",
        ROOT / "fixtures/p3_demo_policy.json",
    )
    with db.connect() as conn, pytest.raises(ValueError, match="unavailable"):
        load_context(conn, context_id, datetime(2026, 8, 1, tzinfo=UTC))


def test_graph_snapshot_header_cannot_leak_future_context(db, tmp_path):
    initialize_demo(db)
    graph = json.loads((ROOT / "fixtures/demo_verified_relationships.json").read_text())
    graph["as_of_available_at"] = "2026-11-20T00:00:00Z"
    path = tmp_path / "later-graph.json"
    path.write_text(json.dumps(graph))
    context_id = install_context(db, ROOT / "config", path, ROOT / "fixtures/p3_demo_policy.json")
    with db.connect() as conn, pytest.raises(ValueError, match="unavailable"):
        load_context(conn, context_id, NOW)
