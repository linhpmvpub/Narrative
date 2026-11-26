"""Scope roles preserve contextual relevance without inventing customer demand."""

import json
from datetime import UTC, datetime

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_profile_news import get
from test_profile_news import linked as linked

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import FactorBinding, ProfileBundle, audit_binding_routes, withdraw
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


def scoped(data, role="SHARED_MARKET"):
    d = dict(data["factor_bindings"][0])
    d.update(kind="SCOPED_ACTIVITY", narrative_ids=["n"],
             relevance_scope={"role": role, "excluded_subject_terms": ["processors"]})
    return d


def test_shared_scope_does_not_earn_concrete_change_priority(linked):
    _, data, _, _, _ = linked
    b = FactorBinding.model_validate(scoped(data))
    text = "Server memory prices increased."
    hits = matches(b, {"summary": text})
    assert hits and all(h["relevance_role"] == "SHARED_MARKET" for h in hits)
    a = assess({"headline": "Update", "excerpt": text}, [{"matches": hits}],
               json.loads(POLICY.read_text(encoding="utf-8")))
    assert a["tier"] == "BACKGROUND_THEME" and not a["signals"]
    assert a["direction"] == a["horizon"] == "UNKNOWN"


def test_excluded_article_subject_is_not_donated_as_positive_evidence(linked):
    _, data, _, _, _ = linked
    b = FactorBinding.model_validate(scoped(data))
    assert not matches(b, {"summary": "Server memory prices increased.", "context_title": "Processors update"})
    assert not matches(b, {"summary": "Memory prices increased.", "context_title": "Server industry"})
    assert not matches(b, {"summary": "Server memory overview. Prices increased elsewhere."})


def test_scope_terms_and_kind_are_source_bound(linked):
    _, data, _, _, _ = linked
    d = scoped(data)
    d["relevance_scope"]["excluded_subject_terms"] = ["Invented Vendor"]
    with pytest.raises(ValueError, match="literal source evidence"):
        FactorBinding.model_validate(d)
    d = scoped(data)
    d["kind"] = "ECONOMIC_CHANGE"
    with pytest.raises(ValueError, match="same-sentence"):
        FactorBinding.model_validate(d)
    assert "relevance_scope" not in FactorBinding.model_validate(data["factor_bindings"][0]).model_dump(mode="json")


def test_competitor_requires_actual_directed_relation_and_read_time_validity(linked):
    _, data, _, _, _ = linked
    d = scoped(data, "COMPETITOR_PLATFORM")
    d.update(topic_terms=["processors"],factor_id="rival")
    d["relevance_scope"] = {"role": "COMPETITOR_PLATFORM", "subject_terms": ["processors"], "relationship_id": "competition"}
    data["nodes"].append({"id": "rival", "kind": "product", "label": "Rival processors"})
    edge = dict(data["relationships"][0])
    edge.update(id="competition",type="COMPETES_WITH",from_id="rival",to_id="p")
    data["relationships"].append(edge)
    data["factor_bindings"] = [d]
    b = ProfileBundle.model_validate(data)
    audit_binding_routes(b)
    at = datetime.now(UTC)
    result = next(binding_decisions(b, b.narratives[0], {"summary": "Processors for server supply increased."}, at))
    assert result["path"][0].type == "COMPETES_WITH"
    assert result["matches"][0]["context_only"]
    edge["valid_until"] = data["available_at"]
    expired = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(expired, expired.narratives[0], {"summary": "Processors for server supply increased."}, at))
    with pytest.raises(ValueError, match="no sourced route"):
        audit_binding_routes(expired)
    edge["status"] = "REVOKED"
    with pytest.raises(ValueError, match="sourced outgoing competition"):
        ProfileBundle.model_validate(data)


def test_scope_survives_rss_card_and_withdrawal(db, linked):
    root, data, insert, _, _ = linked
    data["factor_bindings"] = [scoped(data)]
    seal(root, data)
    insert(title="Server memory prices increased",summary="Industry context")
    card = get(db)["items"][0]
    assert card["links"][0]["relevance_role"] == "SHARED_MARKET"
    assert not card["links"][0]["matches"][0]["news_party_verified"]
    assert card["delivery"] == "disabled" and card["impact"] == "UNKNOWN"
    withdraw(root)
    assert not get(db)["items"]


def test_full_article_uses_title_as_exclusion_only(linked):
    _, data, _, _, _ = linked
    data["factor_bindings"] = [scoped(data)]
    b = ProfileBundle.model_validate(data)
    blocks = [{"text": "Server memory prices increased.", "source_spans": []}]
    assert not list(article_decisions(b, b.narratives[0], "Processors update", blocks, datetime.now(UTC)))
    rows = list(article_decisions(b, b.narratives[0], "Industry update", blocks, datetime.now(UTC)))
    assert rows[0]["matches"][0]["relevance_role"] == "SHARED_MARKET"
    for span in rows[0]["matches"]:
        assert blocks[0]["text"][span["start"]:span["end"]] == span["text"]


def test_own_scope_cannot_claim_another_subject_as_company(linked):
    _, data, _, _, _ = linked
    d = scoped(data)
    d.update(topic_terms=["processors"], relevance_scope={"role": "OWN_PRODUCT", "subject_terms": ["processors"]})
    data["factor_bindings"] = [d]
    with pytest.raises(ValueError, match="profile company"):
        ProfileBundle.model_validate(data)
