"""Synthetic role/scope and source-lifecycle regressions, not a news holdout."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_company_profiles import seal

from engine.adapters.news import NewsClient
from engine.company_profiles import load_bundle
from engine.ingestion.contracts import digest
from engine.news_articles import capture, read_packet
from engine.structured_news import GroundingRule, build, extract


@pytest.mark.parametrize("actor", ["Alpha Foundry", "Beta Memory", "Gamma Labs"])
@pytest.mark.parametrize(
    "verb,phase",
    [("plans to build", "PROPOSED"), ("will build", "PROPOSED"), ("built", "REPORTED_ACTION")],
)
def test_roles_not_company_keywords(actor, verb, phase):
    text = f"{actor} {verb} wafer factories in Texas."
    events, _ = extract(text)
    assert len(events) == 1 and events[0]["phase"] == phase
    assert events[0]["fields"]["object"]["text"] == "wafer factories"
    assert events[0]["fields"]["location"]["text"] == "Texas"
    for field in events[0]["fields"].values():
        assert text[field["start"] : field["end"]] == field["text"]
    assert events[0]["horizon"] == "UNKNOWN" and events[0]["occurrence_time"] is None


@pytest.mark.parametrize(
    "text",
    [
        "Alpha did not build wafer factories.",
        "Alpha might build wafer factories.",
        "If Alpha built wafer factories, output would rise.",
        "Alpha built memory. Beta prices increased.",
        "They built wafer factories.",
        "Alpha built on the success of an RF chip.",
        "Alpha and Beta built wafer factories.",
        "Alpha said Beta built wafer factories.",
        "Alpha builds wafer factories.",
        "Alpha plans to built wafer factories.",
        "Alpha built wafer factories but cancelled the project.",
    ],
)
def test_no_unsupported_claim_promotion(text):
    events, _ = extract(text)
    # Literal object is retained even in metaphor; exact reviewed scope must reject it.
    assert not any(e["fields"]["object"]["text"] == "wafer factories" for e in events)


@pytest.mark.parametrize(
    "sentence,family,direction",
    [
        ("Alpha halted production of NAND.", "supply_disruption", "DOWN"),
        ("Alpha resumed production of NAND.", "supply_disruption", "UP"),
        ("Alpha cancelled orders for servers.", "demand", "DOWN"),
        ("Alpha raised prices for gas.", "input_price", "UP"),
        ("Alpha provided funding for factories.", "financing", "UP"),
        ("Agency granted licenses for processors.", "policy", "UP"),
        ("Alpha sampled HBM.", "technology", "UNKNOWN"),
    ],
)
def test_typed_action_direction_is_not_company_stance(sentence, family, direction):
    events, _ = extract(sentence)
    assert len(events) == 1
    assert (events[0]["mechanism"], events[0]["direction"]) == (family, direction)


@pytest.fixture
def grounded(dossier, selection, monkeypatch):
    root, data = dossier
    registry = root.parent / "profiles"
    registry.mkdir()
    moved = registry / root.name
    root.rename(moved)
    root = moved
    monkeypatch.setenv("COMPANY_PROFILE_ROOT", str(registry))
    quote = "Alpha Foundry operates wafer factories in Texas for the example company."
    original = (root / "source.html").read_text()
    (root / "source.html").write_text(original + "<p>" + quote + "</p>")
    import hashlib

    data["sources"][0]["sha256"] = hashlib.sha256((root / "source.html").read_bytes()).hexdigest()
    data["relationships"][1]["evidence"] = [{"source_id": "s", "quote": quote}]
    seal(root, data)
    b = load_bundle(root)
    now = datetime.now(UTC)
    rule = GroundingRule(
        id="scope",
        version=1,
        profile_id=b.id,
        profile_sha256=digest(b.model_dump(mode="json")),
        relationship_id="applies",
        actor="Alpha Foundry",
        object="wafer factories",
        location="Texas",
        action="build",
        source_id="s",
        source_quote=quote,
        reviewed_at=now,
        review_until=now + timedelta(days=1),
        reviewer_id="synthetic",
        reviewer_kind="AI_OPERATOR",
    )
    return root, data, selection, rule


def replace_article(selection, text):
    rev = {**selection["revision"], "received_at": datetime.now(UTC)}
    body = ("<p>" + text + "</p><p>" + ("Unrelated synthetic background. " * 12) + "</p>").encode()
    c = NewsClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=body, headers={"content-type": "text/html"})
        )
    )
    try:
        saved = capture(rev, c)
    finally:
        c.close()
    _, visible = read_packet(rev, saved["packet_sha256"])
    rev["received_at"] = rev["received_at"].isoformat()
    return {
        **selection,
        "revision": rev,
        "packet_sha256": saved["packet_sha256"],
        "body_review": {
            **selection["body_review"],
            "start": 0,
            "end": len(visible),
            "related_link_ranges": [],
            "reviewed_at": datetime.now(UTC).isoformat(),
        },
    }


def test_complete_source_to_typed_event_to_graph_candidate(grounded):
    _, _, s, rule = grounded
    s = replace_article(s, "Alpha Foundry plans to build wafer factories in Texas.")
    result = build([s, s], [rule])
    assert len(result["items"]) == 1
    card = result["items"][0]
    assert [e["id"] for e in card["path"]] == ["applies", "effect"]
    assert card["event"]["phase"] == "PROPOSED"
    assert card["financial_magnitude"] == "UNKNOWN" and card["delivery"] == "disabled"
    assert card["stance"] == "RELATED_INFORMATION"
    assert card["source_packet_sha256"] == s["packet_sha256"]
    assert result["active_feed_changed"] is False


@pytest.mark.parametrize(
    "text",
    [
        "Other Foundry plans to build wafer factories in Texas.",
        "Alpha Foundry plans to build RF devices in Texas.",
        "Alpha Foundry plans to build wafer factories in Taiwan.",
        "Alpha Foundry plans to build wafer factories.",
        "Alpha Foundry built on prior wafer factories in Texas.",
        "Alpha Foundry will open wafer factories in Texas.",
        "Alpha Foundry did not build wafer factories in Texas.",
    ],
)
def test_scope_mismatch_never_falls_back_to_keyword_route(grounded, text):
    _, _, s, rule = grounded
    assert not build([replace_article(s, text)], [rule])["items"]


@pytest.mark.parametrize(
    "fault", ["pin", "quote", "actor", "future", "expired", "edge", "duplicate"]
)
def test_rule_provenance_and_version_guards(grounded, fault):
    _, _, s, rule = grounded
    s = replace_article(s, "Alpha Foundry built wafer factories in Texas.")
    updates = {
        "pin": {"profile_sha256": "0" * 64},
        "quote": {"source_quote": "Unsupported source sentence"},
        "actor": {"actor": "Other Foundry"},
        "future": {"reviewed_at": datetime.now(UTC) + timedelta(days=1)},
        "expired": {"review_until": datetime.now(UTC) - timedelta(seconds=1)},
        "edge": {"relationship_id": "owns"},
        "duplicate": {},
    }
    rule = rule.model_copy(update=updates[fault])
    with pytest.raises(ValueError):
        build([s], [rule, rule] if fault == "duplicate" else [rule])


@pytest.mark.parametrize(
    "fault", ["rule_revoked", "edge_revoked", "source_changed", "body_changed"]
)
def test_revocation_and_tampering(grounded, fault):
    root, data, s, rule = grounded
    s = replace_article(s, "Alpha Foundry built wafer factories in Texas.")
    if fault == "rule_revoked":
        assert not build([s], [rule.model_copy(update={"status": "REVOKED"})])["items"]
    elif fault == "edge_revoked":
        data["relationships"][1]["status"] = "REVOKED"
        seal(root, data)
        rule = rule.model_copy(
            update={"profile_sha256": digest(load_bundle(root).model_dump(mode="json"))}
        )
        assert not build([s], [rule])["items"]
    else:
        if fault == "source_changed":
            (root / "source.html").write_text("corrupt")
        else:
            s["packet_sha256"] = "0" * 64
        with pytest.raises((ValueError, FileNotFoundError)):
            build([s], [rule])


def test_conflicting_anchors_with_same_scope_are_held(grounded):
    root, data, s, rule = grounded
    data["nodes"].append({"id": "other-factor", "kind": "factor", "label": "Other factor"})
    data["relationships"].append(
        {**data["relationships"][1], "id": "other-applies", "from_id": "other-factor"}
    )
    seal(root, data)
    rule = rule.model_copy(
        update={"profile_sha256": digest(load_bundle(root).model_dump(mode="json"))}
    )
    other = rule.model_copy(update={"id": "conflict", "relationship_id": "other-applies"})
    s = replace_article(s, "Alpha Foundry built wafer factories in Texas.")
    result = build([s], [rule, other])
    assert not result["items"]
    assert any(a["reason"] == "NO_UNAMBIGUOUS_SOURCED_SCOPE_PATH" for a in result["audit"])


def test_registry_change_during_run_rejected(grounded, monkeypatch):
    import engine.structured_news as module

    _, _, s, rule = grounded
    original = module.available_bundles
    calls = []

    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(1)
        if len(calls) > 1:
            result["items"][0] = result["items"][0].model_copy(update={"version": 99})
        return result

    monkeypatch.setattr(module, "available_bundles", changing)
    s = replace_article(s, "Alpha Foundry built wafer factories in Texas.")
    with pytest.raises(ValueError, match="changed"):
        build([s], [rule])


def test_appendix_event_does_not_route(grounded):
    _, _, s, rule = grounded
    s = replace_article(
        s,
        "Board appointment only.</p><h2>About Example</h2><p>"
        "Alpha Foundry built wafer factories in Texas.",
    )
    assert not build([s], [rule])["items"]
