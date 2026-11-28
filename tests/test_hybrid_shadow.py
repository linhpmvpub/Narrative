"""Synthetic contracts; fake adapter responses are never reported as model quality."""

import json
from copy import deepcopy
from datetime import timedelta

import httpx
import pytest
from test_company_benchmark import benchmark as benchmark
from test_company_discovery import discovery as discovery
from test_company_profiles import dossier as dossier

from engine.company_profiles import ProfileBundle, load_bundle
from engine.evaluation import hybrid_shadow as hs
from engine.evaluation.benchmark import pin, read, write
from engine.local_analyst import LocalAnalyst, parse_response, response_schema
from engine.shadow_analyst import Proposal, catalog, model_routes, retrieve, validate


def proposal(**changes):
    d = dict(company_id="co", relevance="RELEVANT", attention="PRIORITY", group="results",
             phase="REPORTED", negated=False, quote="Fjord reports results.", actor="Fjord",
             route_id="example:issuer", rationale="Synthetic only.")
    d.update(changes)
    return Proposal.model_validate({"decisions": [d]})


def context(discovery):
    root, _, now = discovery
    return retrieve("Fjord reports results. Server memory shortage.", catalog({"example": load_bundle(root)}, now))


def test_catalog_and_retrieval_do_not_require_regex_acceptance_or_narratives(discovery):
    root, data, now = discovery
    routes = catalog({"example": load_bundle(root)}, now)
    assert {r["kind"] for r in routes} == {"ISSUER_EVENT", "FACTOR_EXPOSURE"}
    # No existing required change term 'prices', yet reverse exposure is offered.
    got = retrieve("Server memory shortage", routes)
    assert any(r["route"]["kind"] == "FACTOR_EXPOSURE" for r in got)
    data["narratives"] = []
    assert catalog({"example": ProfileBundle.model_validate(data)}, now) == routes
    assert "narrative" not in json.dumps(model_routes(got))
    assert retrieve("Community festival", routes) == []


def test_context_budget_drops_whole_paths_without_changing_their_evidence(discovery):
    root, _, now = discovery
    routes = catalog({"example": load_bundle(root)}, now)
    before = deepcopy(routes)
    got = retrieve("Fjord server memory", routes, max_chars=1000)
    assert len(json.dumps(model_routes(got), ensure_ascii=False).encode()) <= 1000
    assert routes == before


def test_model_cannot_introduce_numeric_financial_predictions():
    with pytest.raises(ValueError, match="Extra inputs"):
        proposal(financial_magnitude=20, probability=.9)


@pytest.mark.parametrize("fault", ["revoked", "future", "expired", "disabled", "future_source"])
def test_catalog_withholds_unusable_graph(discovery, fault):
    _, data, now = discovery
    data = deepcopy(data)
    if fault == "revoked":
        data["relationships"][0]["status"] = "REVOKED"
    elif fault == "future":
        data["relationships"][0]["known_at"] = (now + timedelta(days=1)).isoformat()
    elif fault == "expired":
        data["factor_bindings"][0]["review_until"] = (now - timedelta(seconds=1)).isoformat()
    elif fault == "disabled":
        data["factor_bindings"][0]["enabled"] = False
    else:
        data["sources"][0]["retrieved_at"] = (now + timedelta(days=1)).isoformat()
    if fault in {"future", "future_source"}:
        with pytest.raises(ValueError, match="Future"):
            ProfileBundle.model_validate(data)
        return
    routes = catalog({"example": ProfileBundle.model_validate(data)}, now)
    assert not any(r["kind"] == "FACTOR_EXPOSURE" for r in routes)


@pytest.mark.parametrize("changes,expected", [
    ({"quote": "Invented results", "actor": "Invented"}, "MISSING_OR_AMBIGUOUS_SOURCE_QUOTE"),
    ({"actor": "Other company"}, "UNSUPPORTED_ACTOR_SPAN"),
    ({"route_id": "nonexistent"}, "MISSING_OR_WRONG_COMPANY_ROUTE"),
    ({"actor": "results"}, "ISSUER_NOT_IN_ACTOR"),
    ({"attention": "NONE"}, "INCONSISTENT_ATTENTION"),
])
def test_validator_withholds_without_fabricating_evidence(discovery, changes, expected):
    result = validate(proposal(**changes), "Fjord reports results.", [{"company_id": "co"}], context(discovery), graph=True)[0]
    assert expected in result["validation_faults"]
    assert not result["selected"] and not result["priority"] and result["delivery"] == "disabled"


@pytest.mark.parametrize("phase,negated,priority", [("PLAN", False, True), ("SPECULATION", False, False),
                                                   ("REPORTED", True, False)])
def test_priority_preserves_phase_and_unknown_financial_effect(discovery, phase, negated, priority):
    result = validate(proposal(phase=phase, negated=negated), "Fjord reports results.",
                      [{"company_id": "co"}], context(discovery), graph=True)[0]
    assert result["priority"] == priority and result["selected"]
    assert result["financial_magnitude"] == result["horizon"] == result["direction"] == "UNKNOWN"
    assert result["semantic_correctness"] == "UNMEASURED"


def test_wrong_company_route_and_generic_graph_leak_rejected(discovery):
    ctx = context(discovery)
    next(item["route"] for item in ctx if item["route"]["kind"] == "ISSUER_EVENT")["company_id"] = "other"
    result = validate(proposal(), "Fjord reports results.", [{"company_id": "co"}], ctx, graph=True)
    assert "MISSING_OR_WRONG_COMPANY_ROUTE" in result[0]["validation_faults"]
    assert validate(proposal(), "Fjord reports results.", [{"company_id": "co"}], [], graph=False)[0]["validation_faults"]


def test_duplicate_target_and_ambiguous_quote_rejected(discovery):
    p = proposal()
    with pytest.raises(ValueError, match="Complete unique"):
        validate(Proposal(decisions=p.decisions * 2), "Fjord reports results.", [{"company_id": "co"}], [], graph=True)
    result = validate(p, "Fjord reports results. Fjord reports results.", [{"company_id": "co"}], context(discovery), graph=True)
    assert "MISSING_OR_AMBIGUOUS_SOURCE_QUOTE" in result[0]["validation_faults"]


@pytest.mark.parametrize("endpoint", ["https://example.test", "http://localhost:11434", "http://127.0.0.1.evil:80",
                                    "http://127.0.0.1:11434/path", "http://user@127.0.0.1:11434"])
def test_private_packets_cannot_target_external_hosts(endpoint):
    with pytest.raises(ValueError, match="loopback"):
        LocalAnalyst("test", endpoint=endpoint)


def test_remote_models_and_context_truncation_rejected(monkeypatch):
    def response(self, method, path, **kwargs):
        if path == "/api/tags":
            return {"models": [{"name": "test", "digest": "abc"}]}
        if path == "/api/show":
            return {"model_info": {"family": "synthetic"}}
        return {"version": "synthetic"}
    monkeypatch.setattr(LocalAnalyst, "request", response)
    a = LocalAnalyst("test", context=4096, output_tokens=256)
    try:
        with pytest.raises(ValueError, match="BUDGET"):
            a.analyze({"source": "x" * 5000, "companies": [{"company_id": "co"}]})
    finally:
        a.close()
    with pytest.raises(ValueError, match="local"):
        LocalAnalyst("test-cloud")


@pytest.mark.parametrize("fault", ["truncated", "changed", "wrong_model", "malformed"])
def test_bad_response_is_not_a_successful_model_prediction(fault):
    record = {"model_stable": True, "identity": {"model": "test"},
              "response": {"done": True, "done_reason": "stop", "model": "test", "message": {"content": proposal().model_dump_json()}}}
    if fault == "truncated":
        record["response"]["done_reason"] = "length"
    elif fault == "changed":
        record["model_stable"] = False
    elif fault == "wrong_model":
        record["response"]["model"] = "other"
    else:
        record["response"]["message"]["content"] = "{}"
    with pytest.raises(ValueError):
        parse_response(record)


@pytest.mark.parametrize("fault", [None, "missing", "wrong_identity", "extra"])
def test_decoding_contract_requires_every_company_even_without_routes(fault):
    companies = [{"company_id": "co"}, {"company_id": "other"}]
    schema = response_schema(companies)
    assert schema["properties"]["decisions"]["required"] == ["co", "other"]
    values = {c["company_id"]: proposal(company_id=c["company_id"]).decisions[0].model_dump()
              for c in companies}
    if fault == "missing":
        del values["other"]
    elif fault == "wrong_identity":
        values["other"]["company_id"] = "co"
    elif fault == "extra":
        values["surprise"] = values["co"]
    receipt = {"model_stable": True, "identity": {"model": "test"}, "expected_companies": ["co", "other"],
               "response": {"done": True, "done_reason": "stop", "model": "test",
                            "message": {"content": json.dumps({"decisions": values})}}}
    if fault:
        with pytest.raises(ValueError, match="target-company"):
            parse_response(receipt)
    else:
        assert len(parse_response(receipt).decisions) == 2


def setup(benchmark, tmp_path):
    pointer = tmp_path / "pointer.json"
    write(pointer, {"company_benchmark": benchmark})
    directory = tmp_path / "experiment"
    result = hs.prepare(pointer, directory)
    return directory, result["experiment"]["sha256"]


def test_unavailable_arms_have_no_invented_scores(benchmark, tmp_path):
    directory, sha = setup(benchmark, tmp_path)
    result = hs.run(directory, sha, tmp_path / "shadow")
    assert result["arms"]["A_engine"]["benchmark"]["score"] == 100
    for arm in ("B_generic", "C_graph"):
        assert result["arms"][arm]["status"] == "UNAVAILABLE"
        assert result["arms"][arm]["benchmark"] is None
    assert len(read(directory / "inputs.json")) == 2  # includes rejected article
    assert pin(tmp_path / "shadow/receipt.json")
    with pytest.raises(ValueError, match="immutable"):
        hs.run(directory, sha, tmp_path / "shadow")


def test_packets_exclude_labels_predictions_and_private_graph_from_b(benchmark, tmp_path):
    directory, sha = setup(benchmark, tmp_path)
    class SyntheticAdapter:
        identity = {"model": "SYNTHETIC_TEST_NOT_LLM"}
        def analyze(self, packet):
            assert set(packet) <= {"source", "representation", "source_metadata", "as_of", "companies", "graph_mode", "routes"}
            assert ("routes" in packet) == packet["graph_mode"]
            p = proposal(relevance="INSUFFICIENT_CONTEXT", attention="INSUFFICIENT_CONTEXT", route_id="", quote="", actor="")
            return {"model_stable": True, "identity": self.identity, "seconds": .1,
                    "response": {"done": True, "done_reason": "stop", "model": self.identity["model"],
                                 "message": {"content": p.model_dump_json()}}}
    result = hs.run(directory, sha, tmp_path / "shadow", SyntheticAdapter())
    assert result["arms"]["B_generic"]["abstained_units"] == 2
    assert result["arms"]["C_graph"]["benchmark"]["score"] == 0
    assert result["delivery"] == "disabled"


def test_failed_call_keeps_receipt_without_partial_arm_score(benchmark, tmp_path):
    directory, sha = setup(benchmark, tmp_path)
    class Failed:
        identity = {"model": "SYNTHETIC_TEST_NOT_LLM"}
        def analyze(self, packet):
            raise httpx.ReadTimeout("Synthetic timeout")
    result = hs.run(directory, sha, tmp_path / "shadow", Failed())
    assert result["arms"]["C_graph"]["status"] == "INCOMPLETE"
    assert result["arms"]["C_graph"]["benchmark"] is None
    assert len(list((tmp_path / "shadow").glob("call-*.json"))) == 4


@pytest.mark.parametrize("file", ["inputs.json", "catalog.json", "baseline.json", "experiment.json"])
def test_changed_experiment_is_rejected(benchmark, tmp_path, file):
    directory, sha = setup(benchmark, tmp_path)
    target = directory / file
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError):
        hs.run(directory, sha, tmp_path / "shadow")
