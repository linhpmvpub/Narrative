import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal

from engine.company_discovery import decisions, issuer_matches
from engine.company_profiles import ProfileBundle, load_bundle
from engine.evaluation.benchmark import comparison
from engine.evaluation.company_quality import company_report


@pytest.fixture
def discovery(dossier):
    root, data = dossier
    now = datetime.now(UTC)
    quote = "Fjord Computing, also called Fjord, sells processors. Fjord uses server memory."
    data["nodes"][0]["label"] = data["legal_name"] = "Fjord Computing"
    data["sources"][0]["sha256"] = hashlib.sha256(("<p>" + quote + "</p>").encode()).hexdigest()
    (root / "source.html").write_text("<p>" + quote + "</p>")
    evidence = [{"source_id": "s", "quote": quote}]
    for entry in [*data["components"], *data["relationships"], *data["events"]]:
        entry["evidence"] = evidence
    data["factor_bindings"] = [
        {
            "id": "input",
            "factor_id": "f",
            "topic_terms": ["memory"],
            "context_terms": ["server"],
            "change_terms": ["prices"],
            "scope": "Synthetic input",
            "reviewed_at": data["available_at"],
            "review_until": (now + timedelta(days=10)).isoformat(),
            "evidence": evidence,
        }
    ]
    base = dict(
        enabled=True,
        scope="Synthetic company context",
        reviewed_at=data["available_at"],
        review_until=(now + timedelta(days=10)).isoformat(),
        evidence=evidence,
    )
    data["company_discovery"] = [
        dict(base, id="issuer", kind="ISSUER_EVENT", names=["Fjord"]),
        dict(
            base,
            id="input",
            kind="FACTOR_EXPOSURE",
            binding_id="input",
            relation_ids=["applies"],
            membership_ids=["owns"],
            intents=["SUPPLY"],
        ),
    ]
    seal(root, data)
    return root, data, now


@pytest.mark.parametrize("name", ["Fjord", "Cedar Devices"])
@pytest.mark.parametrize(
    "tail",
    [
        " reports fiscal fourth quarter financial results",
        "'s credit rating could be cut",
        " secures a new credit facility",
        " appoints a new chief executive",
    ],
)
def test_named_issuer_actions_are_shared_and_literal(name, tail):
    text = "Source says " + name + tail + "."
    matches = list(issuer_matches([name], {"title": text}))
    assert len(matches) == 1
    m = matches[0]
    assert text[m["start"] : m["end"]] == m["text"] and m["context_only"]


@pytest.mark.parametrize(
    "text",
    [
        "Fjord shares trade higher",
        "Market roundup: Fjord and Cedar. Cedar reports financial results.",
        "Fjord will report financial results next month",
        "Fjord did not report financial results",
        "If Fjord reports financial results, we will see.",
        "How Fjord reports financial results",
        "Fjord reports financial results?",
        "Fjord secures no funding",
        "BlueFjord reports financial results",
        "Fjord appoints a fictional mascot",
    ],
)
def test_mentions_other_subjects_negations_and_calendar_do_not_make_events(text):
    assert not list(issuer_matches(["Fjord"], {"title": text}))


def test_company_discovery_survives_no_narratives_and_never_assigns_one(discovery):
    root, data, now = discovery
    data["narratives"] = []
    # Validate in memory: enabled legacy bindings intentionally require narratives
    # on installation; the discovery runtime itself does not inspect that inventory.
    b = ProfileBundle.model_validate(data)
    for article in [
        {"title": "Fjord reports financial results"},
        {"title": "Server memory prices rise"},
    ]:
        found = decisions(b, article, now)
        assert found and all(r["delivery"] == "disabled" for r in found)
        assert all("narrative_id" not in r for r in found)
        for decision in found:
            if decision["routing_contract"]:
                contract = decision["routing_contract"]
                assert "COMPANY_SCOPE_CHECKED" in contract["stages"]
                assert "NARRATIVE_SCOPE_CHECKED" not in contract["stages"]
    assert load_bundle(root).company_discovery


@pytest.mark.parametrize(
    "fault", ["disabled", "expired", "future", "revoked", "expired_edge", "membership", "binding"]
)
def test_exposure_requires_every_current_exact_edge_and_review(discovery, fault):
    _, data, now = discovery
    rule = data["company_discovery"][1]
    if fault == "disabled":
        rule["enabled"] = False
    elif fault == "expired":
        rule["review_until"] = (now - timedelta(seconds=1)).isoformat()
    elif fault == "future":
        now = datetime.fromisoformat(rule["reviewed_at"]) - timedelta(seconds=1)
    elif fault == "revoked":
        data["relationships"][1]["status"] = "REVOKED"
    elif fault == "expired_edge":
        data["relationships"][1]["valid_until"] = (now - timedelta(seconds=1)).isoformat()
    elif fault == "membership":
        data["relationships"][0]["status"] = "DISPUTED"
    elif fault == "binding":
        data["factor_bindings"][0]["enabled"] = False
    assert not decisions(
        ProfileBundle.model_validate(data), {"title": "Server memory prices rise"}, now
    )


@pytest.mark.parametrize(
    "fault", ["missing_edge", "wrong_endpoint", "wrong_owner", "invented_name", "invented_quote"]
)
def test_invalid_source_and_graph_contracts_rejected(discovery, fault):
    root, data, _ = discovery
    if fault == "missing_edge":
        data["company_discovery"][1]["relation_ids"] = ["absent"]
    elif fault == "wrong_endpoint":
        data["company_discovery"][1]["relation_ids"] = ["applies", "effect"]
    elif fault == "wrong_owner":
        data["company_discovery"][1]["membership_ids"] = ["effect"]
    elif fault == "invented_name":
        data["company_discovery"][0]["names"] = ["Other Corporation"]
    else:
        data["company_discovery"][0]["evidence"][0]["quote"] = "Fjord invented evidence"
    seal(root, data)
    with pytest.raises(ValueError):
        load_bundle(root)


def test_company_selection_improves_only_direct_company_truth():
    base = dict(
        id="a",
        ticker="ANY",
        groups=["other"],
        event_cluster="x",
        source_unit_id="x",
        target_id="n",
        label="NOT_RELEVANT",
        priority="NONE",
        selected=False,
        main=False,
        company_label="RELEVANT",
    )
    improved = {**base, "company_selected": True}
    assert company_report([improved])["overall"]["tp"] == 1
    assert comparison({"c": [base]}, {"c": [improved]})["changes"][0]["dimension"] == "company"
    legacy = deepcopy(improved)
    del legacy["company_label"]
    assert company_report([legacy])["overall"]["tn"] == 1
    with pytest.raises(ValueError, match="company discovery predictions"):
        company_report(
            [improved, {**improved, "id": "b", "target_id": "n2", "company_selected": False}]
        )


def test_company_only_binding_installs_without_narratives_but_cannot_leak_into_them(discovery):
    from engine.profile_routing import binding_decisions

    root, data, now = discovery
    data["factor_bindings"][0]["company_only"] = True
    narrative = ProfileBundle.model_validate(data).narratives[0]
    data["narratives"] = []
    seal(root, data)
    bundle = load_bundle(root)
    article = {"title": "Server memory prices rise"}
    assert decisions(bundle, article, now)
    assert not list(binding_decisions(bundle, narrative, article, now))
    data["company_discovery"] = data["company_discovery"][:1]
    seal(root, data)
    with pytest.raises(ValueError, match="Company-only"):
        load_bundle(root)
