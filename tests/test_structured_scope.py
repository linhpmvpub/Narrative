"""Synthetic identity-to-edge authorization and compound scope checks."""

from datetime import UTC, datetime, timedelta

import pytest
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_structured_news import grounded as grounded
from test_structured_news import replace_article

from engine.company_profiles import load_bundle
from engine.ingestion.contracts import digest
from engine.structured_news import build, extract
from engine.structured_scope import audit


@pytest.fixture
def identified(grounded):
    root, data, s, rule = grounded
    data["nodes"].append({"id": "supplier", "kind": "supplier", "label": "Alpha Foundry"})
    edge = data["relationships"][1]
    edge.update(type="SUPPLIES", from_id="supplier")
    now = datetime.now(UTC)
    data["entity_references"] = [
        {
            "id": "actor-ref",
            "label": "Alpha Foundry",
            "identity_level": "LEGAL_ENTITY",
            "resolution": "EXACT_ENTITY",
            "node_id": "supplier",
            "names": ["Alpha Foundry"],
            "relationship_ids": [edge["id"]],
            "scope": "Synthetic factories",
            "unknowns": ["No realized financial effect"],
            "reviewed_at": data["available_at"],
            "review_until": (now + timedelta(days=1)).isoformat(),
            "evidence": edge["evidence"],
        }
    ]
    seal(root, data)
    b = load_bundle(root)
    rule = rule.model_copy(
        update={
            "profile_sha256": digest(b.model_dump(mode="json")),
            "identity_reference_id": "actor-ref",
        }
    )
    return root, data, s, rule


def test_identity_grounded_path_and_readiness(identified):
    _, _, s, rule = identified
    result = build(
        [replace_article(s, "Alpha Foundry built wafer factories in Texas.")],
        [rule],
        require_identity=True,
    )
    assert result["items"][0]["identity_basis"] == "SOURCE_REVIEWED_UPSTREAM_ENTITY"
    readiness = audit([rule])
    assert readiness["rules"][0]["status"] == "READY_FOR_SHADOW_ONLY"
    assert readiness["coverage"][0]["narratives_covered"] == ["n"]


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "actor",
        "downstream",
        "revoked",
        "expired",
        "wrong_edge",
        "same_quote_wrong_supplier",
    ],
)
def test_identity_failures_do_not_authorize_scope(identified, fault):
    root, data, s, rule = identified
    if fault == "missing":
        rule = rule.model_copy(update={"identity_reference_id": None})
    elif fault == "actor":
        rule = rule.model_copy(update={"actor": "Foundry"})
    elif fault == "wrong_edge":
        rule = rule.model_copy(update={"relationship_id": "effect"})
    else:
        ref = data["entity_references"][0]
        if fault == "downstream":
            data["relationships"][1].update(from_id="p", to_id="supplier", type="DEPENDS_ON")
        elif fault == "same_quote_wrong_supplier":
            data["nodes"].append(
                {"id": "other-supplier", "kind": "supplier", "label": "Other supplier"}
            )
            data["relationships"].append(
                {**data["relationships"][1], "id": "other-supply", "from_id": "other-supplier"}
            )
            rule = rule.model_copy(update={"relationship_id": "other-supply"})
        elif fault == "revoked":
            ref["status"] = "REVOKED"
        else:
            ref["review_until"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        seal(root, data)
        rule = rule.model_copy(
            update={"profile_sha256": digest(load_bundle(root).model_dump(mode="json"))}
        )
    result = audit([rule])
    assert result["coverage"][0]["ready_rules"] == 0
    with pytest.raises(ValueError):
        build(
            [replace_article(s, "Alpha Foundry built wafer factories in Texas.")],
            [rule],
            require_identity=True,
        )


def test_compound_object_is_literal_not_broad_keyword_match():
    text = "Alpha halted production of wafers for processors and accelerators at 7 nm or smaller nodes."
    events, _ = extract(text)
    assert len(events) == 1
    obj = events[0]["fields"]["object"]
    assert (
        text[obj["start"] : obj["end"]]
        == "wafers for processors and accelerators at 7 nm or smaller nodes"
    )
    assert not extract("Alpha and Beta halted production of wafers.")[0]
    assert not extract("Alpha halted production of wafers in Texas or Arizona.")[0]


def test_compound_clause_does_not_match_atomic_scope(identified):
    _, _, s, rule = identified
    s = replace_article(s, "Alpha Foundry built wafer factories and cancelled orders in Texas.")
    assert not build([s], [rule], require_identity=True)["items"]


def test_readiness_duplicate_and_timing(identified):
    _, _, _, rule = identified
    with pytest.raises(ValueError):
        audit([rule, rule])
    with pytest.raises(ValueError):
        audit([rule], at=datetime.now(UTC) + timedelta(days=1))
