import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_access_constraints import configured as access_profile
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_profile_news import get
from test_profile_news import linked as linked

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import ProfileBundle, load_bundle, withdraw
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.profile_routing import binding_decisions


def configured(dossier):
    root, data = dossier
    quote = "Capital and financing availability can limit customer data center deployment."
    raw = (root / "source.html").read_bytes() + ("<p>" + quote + "</p>").encode()
    (root / "source.html").write_bytes(raw)
    data["sources"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    evidence = [{"source_id": "s", "quote": quote}]
    data["relationships"][-1].update(from_id="f", type="AFFECTS_DEMAND", evidence=evidence)
    data["routing_policies"] = [
        {"narrative_id": "n", "intents": ["DEPLOYMENT"], "scope_note": "Synthetic deployment scope"}
    ]
    data["factor_bindings"] = [
        dict(
            id="finance",
            factor_id="f",
            topic_terms=["capital"],
            context_terms=["deployment"],
            change_terms=["funding"],
            kind="SCOPED_ACTIVITY",
            narrative_ids=["n"],
            project_finance={"relationship_id": "effect"},
            scope="Conditional capital availability, not a named customer or supplier",
            reviewed_at=data["available_at"],
            review_until=(datetime.now(UTC) + timedelta(days=20)).isoformat(),
            evidence=evidence,
        )
    ]
    seal(root, data)
    return root, data, load_bundle(root)


@pytest.mark.parametrize("name", ["Orion", "Cobalt"])
@pytest.mark.parametrize(
    "template,expected",
    [
        ("{n} secures funding for a data center.", True),
        ("{n} secured $5 million in financing to build a data center.", True),
        ("{n} will provide capital for AI infrastructure.", True),
        ("{n} plans to obtain a loan for a data center.", True),
        ("{n} announced a data center. {n} secures funding for the facility.", True),
        ("{n} secures funding for data center software.", False),
        ("{n} secures funding for data center cooling systems.", False),
        ("{n} secures funding for a conference about data centers.", False),
        ("{n} secures funding and another operator builds a data center.", False),
        ("{n} could secure funding for a data center.", False),
        ("Analysts say {n} secures funding for a data center.", False),
        ("{n} announced a food factory. {n} secures funding for the facility.", False),
        ("{n} backs startup developing data center cooling.", False),
    ],
)
def test_financing_binds_actor_capital_and_actual_deployment_object(
    dossier, name, template, expected
):
    _, _, b = configured(dossier)
    text = template.format(n=name)
    links = list(binding_decisions(b, b.narratives[0], {"summary": text}, datetime.now(UTC)))
    assert bool(links) == expected
    if expected:
        event = links[0]["matches"][0]["project_finance"]
        assert event["relationship_id"] == "effect" and event["capital_disbursed"] == "UNKNOWN"
        assert event["amount"] == "NOT_EXTRACTED" and not event["supplier_relationship_inferred"]
        assert all(text[m["start"] : m["end"]] == m["text"] for m in links[0]["matches"])
        assert links[0]["matches"][0]["routing_contract"]["allowed"]
        score = assess(
            {"headline": "Update", "excerpt": text},
            [{"matches": links[0]["matches"]}],
            json.loads(POLICY.read_text()),
        )
        assert score["tier"] == "BACKGROUND_THEME" and not score["signals"]
        cards = list(
            article_decisions(
                b,
                b.narratives[0],
                "Update",
                [{"text": text, "source_spans": []}],
                datetime.now(UTC),
            )
        )
        assert cards


@pytest.mark.parametrize(
    "fault", ["wrong_edge", "foreign_factor", "no_policy", "unsupported_edge", "bypass_guard"]
)
def test_exact_sourced_finance_mechanism_is_required(dossier, fault):
    _, data, _ = configured(dossier)
    if fault == "wrong_edge":
        data["factor_bindings"][0]["project_finance"]["relationship_id"] = "owns"
    if fault == "foreign_factor":
        data["relationships"][-1]["from_id"] = "p"
    if fault == "no_policy":
        data["routing_policies"] = []
    if fault == "unsupported_edge":
        data["relationships"][-1]["evidence"] = [
            {"source_id": "s", "quote": "Different operating scope."}
        ]
    if fault == "bypass_guard":
        data["factor_bindings"][0]["market_scope"] = "APPLICATION_SOFTWARE"
    with pytest.raises(ValueError):
        ProfileBundle.model_validate(data)


@pytest.mark.parametrize("kind", ["finance", "access"])
def test_another_demand_path_cannot_rescue_revoked_selected_mechanism(dossier, kind):
    if kind == "finance":
        _, data, _ = configured(dossier)
        text = "Orion secures funding for a data center."
    else:
        _, data, _ = access_profile(dossier, "Orion")
        data["factor_bindings"][0]["access_constraint"]["relationship_id"] = "effect"
        data["relationships"][-1]["evidence"] = deepcopy(data["factor_bindings"][0]["evidence"])
        text = "Orion GPU buyers face rules that restrict access to compute."
    other = deepcopy(data["relationships"][-1])
    other["id"] = "other-demand"
    data["relationships"].append(other)
    data["relationships"][-2]["status"] = "REVOKED"
    b = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b, b.narratives[0], {"title": text}, datetime.now(UTC)))
    data["relationships"][-2]["status"] = "SOURCE_BACKED"
    data["routing_policies"][0]["intents"] = ["SUPPLY"]
    b = ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b, b.narratives[0], {"title": text}, datetime.now(UTC)))


@pytest.mark.parametrize("fault", ["corrected", "withdrawn", "tampered"])
def test_finance_rss_revalidates_source_and_profile(db, linked, fault):
    root, data, insert, _, _ = linked
    configured((root, data))
    insert(title="Orion secures funding for a data center.", summary="Project financing context.")
    assert get(db)["items"][0]["delivery"] == "disabled"
    if fault == "corrected":
        insert(title="Software update", summary="No physical project.")
    elif fault == "withdrawn":
        withdraw(root)
    else:
        (root / "source.html").write_bytes(b"changed")
    assert not get(db)["items"]
