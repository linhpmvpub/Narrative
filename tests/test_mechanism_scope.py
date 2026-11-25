"""Synthetic context cards, never independent labels or market accuracy evidence."""

import copy
import json
from datetime import UTC, datetime

import pytest
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_scope_review import make_scoped, record_and_check
from test_structured_news import grounded as grounded
from test_structured_scope import identified as identified

from engine.impact_events import assess as event_assess
from engine.ingestion.contracts import digest
from engine.mechanism_playbook import evaluate
from engine.mechanism_scope import ContextScope, assess, load
from engine.scope_review import Proposal

QUOTE = "Alpha Foundry raised market-wide prices for wafers in Texas during 2026."


@pytest.fixture
def contextual(identified, tmp_path):
    return make_context(identified, tmp_path)


def make_context(identified, tmp_path, quote=QUOTE, phase="OPERATING"):
    values = list(make_scoped(identified, tmp_path, quote))
    values[3] = values[3].model_copy(update={"phase": phase})
    proposal = values[-1]["proposal"]
    proposal["event_sha256"] = digest(values[3].model_dump(mode="json"))
    del proposal["facets"]["facility"]
    proposal["context_scope"] = {
        "policy_sha256": digest(load()),
        "mechanism_id": "input_price",
        "not_applicable": {
            "facility": {
                "event_quote": quote,
                "exposure_quote": quote,
                "rationale": "Synthetic reviewers interpret market-wide prices as context, not an individual factory shock.",
            }
        },
    }
    return values


def decision(values, news_conn=None):
    store, policy, data, frame, selection, path, book, review = values
    return evaluate(
        data,
        frame,
        selection,
        "input_price.spot",
        scope_store=store,
        reviewer_policy=policy,
        scope_reviews={digest([path["narrative_id"], path["relations"]]): "synthetic"},
        news_conn=news_conn,
    )


def test_market_context_without_inventing_a_facility(contextual):
    result = record_and_check(contextual)
    assert result["status"] == "CONTEXT"
    result = decision(contextual)
    assert result["first_unmet_rule"] == "R05"
    assert result["decision_trace"][6]["result"] == "UNKNOWN"
    assert len(result["related_context_cards"]) == 1
    card = result["related_context_cards"][0]
    assert card["scope_review"]["context_scope"]["facets"]["facility"] == "REVIEWED_NOT_APPLICABLE"
    assert card["financial_magnitude"] == "UNKNOWN" and card["delivery"] == "disabled"
    assert card["source_packet_sha256"] == contextual[4]["packet_sha256"]
    assert len(card["relations"]) == 2 and card["phase"] == "OPERATING"
    assert card["relationship_path"][0]["from"] == "Alpha Foundry"
    assert card["relationship_path"][0]["evidence"]
    assert "Fab A" not in card["event_quote"]


def test_proposed_news_keeps_phase_without_claiming_realized_impact(identified, tmp_path):
    values = make_context(
        identified,
        tmp_path,
        "Alpha Foundry plans to raise market-wide prices for wafers in Texas during 2026.",
        "PROPOSED",
    )
    record_and_check(values)
    result = decision(values)
    assert result["first_unmet_rule"] == "R04"
    assert result["related_context_cards"][0]["phase"] == "PROPOSED"
    assert result["related_context_cards"][0]["financial_magnitude"] == "UNKNOWN"


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "required_na",
        "wrong_quote",
        "wrong_product",
        "policy",
        "mechanism",
        "votes",
        "rejected",
        "revoked",
    ],
)
def test_unknown_mismatch_or_invalid_review_cannot_create_context(contextual, fault):
    p = contextual[-1]["proposal"]
    scope = p["context_scope"]
    if fault == "missing":
        scope["not_applicable"] = {}
    elif fault == "required_na":
        scope["not_applicable"]["product"] = copy.deepcopy(scope["not_applicable"]["facility"])
        del p["facets"]["product"]
    elif fault == "wrong_quote":
        scope["not_applicable"]["facility"]["event_quote"] = "Unrelated factory announcement"
    elif fault == "wrong_product":
        p["facets"]["product"]["exposure_term"] = "Texas"
    elif fault == "policy":
        scope["policy_sha256"] = "0" * 64
    elif fault == "mechanism":
        scope["mechanism_id"] = "supply_disruption"
    elif fault == "votes":
        contextual[-1]["votes"].pop()
    elif fault == "rejected":
        contextual[-1]["votes"][0]["decision"] = "REJECT"
    elif fault == "revoked":
        contextual[-1]["status"] = "REVOKED"
    with pytest.raises(ValueError):
        record_and_check(contextual)
    assert decision(contextual)["related_context_cards"] == []


def test_context_cannot_survive_withdrawn_source(contextual):
    record_and_check(contextual)
    store = contextual[0]
    sid = contextual[4]["revision"]["id"]
    old = store.history("source", sid)[-1]
    store.append(
        "source", sid, {**old["payload"], "status": "WITHDRAWN"}, expected_head=old["sha256"]
    )
    assert decision(contextual)["related_context_cards"] == []


def test_context_obeys_ingestion_binding_and_failed_poll(contextual, db):
    from sqlalchemy import update
    from test_scope_sources import bound

    from engine.models.schema_v13 import news_sources

    bound.__wrapped__(contextual, db)
    with db.connect() as conn:
        assert len(decision(contextual, news_conn=conn)["related_context_cards"]) == 1
    assert decision(contextual)["related_context_cards"] == []
    with db.begin() as conn:
        conn.execute(update(news_sources).values(failures=1))
    with db.connect() as conn:
        assert decision(contextual, news_conn=conn)["related_context_cards"] == []


def test_context_cannot_leak_to_unreviewed_path_or_truncated_graph(contextual, monkeypatch):
    record_and_check(contextual)
    base = event_assess(contextual[2], contextual[3], contextual[4])
    base["paths"].append({**base["paths"][0], "narrative_id": "unreviewed"})
    monkeypatch.setattr("engine.mechanism_playbook.assess", lambda *a, **kw: base)
    assert len(decision(contextual)["related_context_cards"]) == 1
    base["truncated"] = True
    assert decision(contextual)["related_context_cards"] == []


@pytest.mark.parametrize("mechanism", list(load()["groups"]))
def test_each_mechanism_requires_all_declared_dimensions_or_explicit_na(mechanism):
    policy = load()
    group = policy["groups"][mechanism]
    evidence = {
        "event_quote": QUOTE,
        "exposure_quote": QUOTE,
        "rationale": "Synthetic interpretation supplied to exercise schema, not a true mechanism label.",
    }
    scope = ContextScope(
        policy_sha256=digest(policy),
        mechanism_id=mechanism,
        not_applicable={name: evidence for name in group["conditional"]},
    )
    facets = {name: object() for name in group["required"]}
    result = assess(scope, facets, QUOTE, QUOTE, mechanism)
    assert result["level"] == "RELATED_CONTEXT_ONLY"
    del facets["legal_entity"]
    with pytest.raises(ValueError):
        assess(scope, facets, QUOTE, QUOTE, mechanism)


@pytest.mark.parametrize("fault", ["version", "level", "delivery", "requirements", "groups"])
def test_policy_cannot_silently_relax_contract(tmp_path, fault):
    policy = load()
    if fault == "requirements":
        policy["groups"]["supply_disruption"]["required"].remove("facility")
    elif fault == "groups":
        del policy["groups"]["policy"]
    else:
        policy[fault] = "wrong"
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(ValueError):
        load(path)


def test_legacy_proposal_serialization_is_unchanged(contextual):
    value = copy.deepcopy(contextual[-1]["proposal"])
    del value["context_scope"]
    parsed = Proposal.model_validate(value)
    dumped = parsed.model_dump(mode="json")
    assert "context_scope" not in dumped
    for name in ["effective_from", "effective_until", "created_at", "review_until"]:
        value[name] = (
            datetime.fromisoformat(value[name]).astimezone(UTC).isoformat().replace("+00:00", "Z")
        )
    assert digest(value) == digest(dumped)
