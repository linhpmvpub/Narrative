"""Synthetic source-bound group context must never turn into legal identity."""

import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import QUOTE, seal
from test_company_profiles import dossier as dossier
from test_profile_news import get
from test_profile_news import linked as linked

from engine.company_profiles import ProfileBundle

NAME_QUOTE = "An unnamed affiliate of Example Group purchases the example company's processors."


@pytest.fixture
def named(linked):
    root, data, insert, _, _ = linked
    raw = ("<p>" + QUOTE + "</p><p>" + NAME_QUOTE + "</p>").encode()
    (root / "source.html").write_bytes(raw)
    data["sources"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    data["nodes"].append({"id": "affiliate", "kind": "customer", "label": "Unnamed affiliate"})
    relation = deepcopy(data["relationships"][0])
    relation.update(id="customer", type="BUYS", from_id="affiliate", to_id="p",
                    evidence=[{"source_id": "s", "quote": NAME_QUOTE}])
    data["relationships"].append(relation)
    ref = {"id": "group", "label": "Example Group context", "identity_level": "GROUP",
           "resolution": "CONTEXT_ONLY", "node_id": "affiliate", "names": ["Example Group"],
           "relationship_ids": ["customer"], "scope": "Group context, affiliate not identified",
           "unknowns": ["Legal party in news unknown"], "reviewed_at": data["available_at"],
           "review_until": (datetime.now(UTC) + timedelta(days=20)).isoformat(),
           "evidence": [{"source_id": "s", "quote": NAME_QUOTE}]}
    data["entity_references"] = [ref]
    rule = data["factor_bindings"][0]
    rule.update(topic_terms=["Example Group"], context_terms=["funding"], change_terms=["buildout"],
                entity_reference_id="group", evidence=ref["evidence"])
    seal(root, data)
    insert(title="Example Group receives funding for buildout", summary="Research context only")
    return root, data, insert


def test_group_context_is_not_identity_or_verified_news(db, named):
    card = get(db)["items"][0]
    link = card["links"][0]
    ref = link["entity_context"]
    assert ref["resolution"] == "CONTEXT_ONLY" and ref["identity_level"] == "GROUP"
    assert not ref["identity_merged"] and not ref["news_party_verified"]
    assert ref["node_id"] == "affiliate" and ref["unknowns"]
    assert link["entity_context_path"][0]["id"] == "customer"
    assert card["impact"] == "UNKNOWN" and card["delivery"] == "disabled"
    for hit in ref["matches"]:
        assert card["headline"][hit["start"]:hit["end"]] == hit["text"]


@pytest.mark.parametrize("fault", ["revoked", "expired", "disputed", "edge_revoked",
                                   "edge_expired", "ambiguous", "corrupt_source"])
def test_current_entity_guards_withhold_card(db, named, fault):
    root, data, _ = named
    ref = data["entity_references"][0]
    if fault == "revoked":
        ref["status"] = "REVOKED"
    elif fault == "disputed":
        ref["status"] = "DISPUTED"
    elif fault == "expired":
        ref["review_until"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    elif fault == "edge_revoked":
        data["relationships"][-1]["status"] = "REVOKED"
    elif fault == "edge_expired":
        data["relationships"][-1]["valid_until"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    elif fault == "ambiguous":
        data["entity_references"].append({**deepcopy(ref), "id": "other-group"})
    else:
        (root / "source.html").write_text("corrupted")
    seal(root, data)
    assert get(db)["items"] == []


@pytest.mark.parametrize("title", ["Example Group stock rises", "Other Group funding buildout",
                                   "Example Grouper funding buildout", "Example Group funding earnings"])
def test_name_alone_or_wrong_context_is_insufficient(db, named, title):
    named[2](title=title, summary="Unrelated")
    assert get(db)["items"] == []


@pytest.mark.parametrize("fault", ["group_exact", "affiliate_borrows_name", "unsupported_name",
                                   "wrong_node", "wrong_edge", "future_review", "unsourced_alias",
                                   "missing_reference", "exact_parent_is_not_affiliate"])
def test_contract_prevents_identity_laundering(named, fault):
    _, data, _ = named
    ref = data["entity_references"][0]
    if fault == "group_exact":
        ref["resolution"] = "EXACT_ENTITY"
    elif fault == "affiliate_borrows_name":
        ref["identity_level"] = "UNRESOLVED_AFFILIATE"
    elif fault == "unsupported_name":
        ref["names"] = ["Invented Corporation"]
    elif fault == "wrong_node":
        ref["node_id"] = "f"
    elif fault == "wrong_edge":
        ref["relationship_ids"] = ["effect"]
    elif fault == "future_review":
        ref["reviewed_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    elif fault == "unsourced_alias":
        data["factor_bindings"][0]["term_aliases"] = {"Example Group": ["Invented Alias"]}
    elif fault == "missing_reference":
        data["factor_bindings"][0]["entity_reference_id"] = "missing"
    else:
        ref.update(identity_level="LEGAL_ENTITY", resolution="EXACT_ENTITY")
    with pytest.raises(ValueError):
        ProfileBundle.model_validate(data)


def test_exact_entity_requires_its_own_name(db, named):
    root, data, _ = named
    # Separate synthetic legal-entity example; no claim that a group is an affiliate.
    data["nodes"][-1]["label"] = "Example Group"
    data["entity_references"][0].update(identity_level="LEGAL_ENTITY", resolution="EXACT_ENTITY")
    seal(root, data)
    assert get(db)["items"][0]["links"][0]["entity_context"]["resolution"] == "EXACT_ENTITY"
