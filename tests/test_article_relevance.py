"""Synthetic complete-body provenance and blind-freeze invariants."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_company_profiles import dossier as dossier
from test_profile_news import linked as linked
from test_profile_relevance import reference
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.adapters.news import NewsClient
from engine.company_profiles import ProfileBundle
from engine.evaluation.article_relevance import freeze, full_body_decisions, reviewed_body
from engine.evaluation.profile_relevance import evaluate
from engine.news_articles import capture, read_packet, root_dir


@pytest.fixture
def selection(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_ARTICLE_DIR", str(tmp_path / "articles"))
    now = datetime.now(UTC)
    revision = {"id": "synthetic-observation", "received_at": now-timedelta(hours=1),
                "payload": {"url": "https://ir.amd.com/synthetic", "title": "Test bulletin",
                            "published_at": (now-timedelta(days=100)).isoformat(), "summary": ""}}
    body = ("<nav>Server memory prices</nav><article><p>Unrelated introduction. "
            + "A synthetic complete article with explicitly reported limitations. " * 5
            + "</p><p>Server memory prices fall.</p><p>Related:</p><p>Other company</p>"
            + "<p>The outcome remains uncertain.</p></article><footer>Other news</footer>").encode()
    client = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, content=body, headers={"content-type": "text/html"})))
    try:
        saved = capture(revision, client)
    finally:
        client.close()
    _, text = read_packet(revision, saved["packet_sha256"])
    revision["received_at"] = revision["received_at"].isoformat()
    a = text.index("Related:")
    return {"revision": revision, "packet_sha256": saved["packet_sha256"],
            "provenance": "MANUAL_PUBLIC_DOCUMENT_OBSERVATION_NOT_RSS",
            "body_review": {"start": text.index("Unrelated"), "end": text.index("\nOther news"),
                "complete_body": True, "reviewer_id": "synthetic-boundary-review",
                "reviewed_at": datetime.now(UTC).isoformat(),
                "boundary_basis": "Complete article excluding navigation/footer",
                "related_link_ranges": [[a, a+len("Related:\nOther company")]]}}


def test_complete_body_freeze_traces_and_prior_exclusion(linked, tmp_path, selection):
    directory = tmp_path / "freeze"
    receipt = freeze([selection], directory)
    assert receipt["clusters"] == 1 and receipt["prediction_track"] == "full_article_relevance"
    packet = json.loads((directory / "packet.json").read_text())
    assert "Related:" not in packet[0]["article"]["summary"]
    assert "topic_terms" not in json.dumps(packet)
    result = evaluate(directory, reference(directory))
    assert result["tp"] == 1  # Old article is semantic context, never feed eligibility.
    traces = json.loads((directory / "traces.json").read_text())
    for decisions in traces.values():
        for decision in decisions:
            for match in decision["matches"]:
                text = packet[0]["article"]["summary"]
                assert text[match["start"]:match["end"]] == match["text"]
    with pytest.raises(ValueError, match="unseen"):
        freeze([selection], tmp_path / "repeat", exclude_packets=[directory / "packet.json"])
    (directory / "traces.json").write_text("{}")
    with pytest.raises(ValueError, match="artifacts"):
        evaluate(directory, directory / "labels.json")


@pytest.mark.parametrize("fault", ["boundary", "incomplete", "future", "context", "raw", "omission", "provenance"])
def test_reject_invalid_full_body_provenance(selection, fault):
    selection = deepcopy(selection)
    review = selection["body_review"]
    if fault == "boundary":
        review["end"] = 1000000
    elif fault == "incomplete":
        review["complete_body"] = False
    elif fault == "future":
        review["reviewed_at"] = (datetime.now(UTC)+timedelta(days=1)).isoformat()
    elif fault == "context":
        selection["revision"]["payload"]["url"] = "https://ir.amd.com/other"
    elif fault == "raw":
        for path in (root_dir() / "bodies").glob("*.html"):
            path.write_bytes(b"changed")
    elif fault == "provenance":
        selection["provenance"] = "RSS"
    else:
        review["related_link_ranges"] = [[review["start"], review["start"]+20]]
    with pytest.raises(ValueError):
        reviewed_body(selection, datetime.now(UTC))


def test_no_cross_paragraph_or_headline_keyword_assembly(linked):
    bundle = ProfileBundle.model_validate(linked[1])
    narrative = bundle.narratives[0]
    assert not list(full_body_decisions(bundle, narrative, "memory", "server\nprices", datetime.now(UTC)))
    assert not list(full_body_decisions(bundle, narrative, "", "memory server\nprices", datetime.now(UTC)))


def test_freeze_current_card_matcher_agrees_with_feed(linked, tmp_path, selection):
    from engine.article_cards import build
    at = datetime.now(UTC)
    directory = tmp_path / 'cards-freeze'
    receipt = freeze([selection], directory, at=at, matcher='feed_cards')
    cards = build([selection], at)['items']
    selected = {(c['profile_id'], c['narrative_id']) for c in cards}
    packet = json.loads((directory / 'packet.json').read_text())
    predictions = json.loads((directory / 'predictions.json').read_text())
    assert receipt['matcher'] == 'feed_cards'
    assert 'binding_id' not in json.dumps(packet)
    for row in packet:
        assert predictions[row['id']] == ((row['profile_id'], row['narrative']['id']) in selected)
    assert evaluate(directory, reference(directory))['tp'] == len(cards)
