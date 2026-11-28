"""Current full-body evidence reaches company cards without narrative routing."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from test_company_feed import company as company
from test_company_profiles import dossier as dossier
from test_profile_news import linked as linked

from engine import news_articles
from engine.adapters.news import NewsClient
from engine.article_feed import install, refresh
from engine.company_feed import feed
from engine.company_profiles import available_bundles
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_items, news_revisions


@pytest.fixture
def reviewed(db, company, tmp_path, monkeypatch):
    company[2](title="Market bulletin", summary="See full article.")
    monkeypatch.setattr(news_articles, "HOSTS", news_articles.HOSTS | {"example.test"})
    articles, root = tmp_path / "bodies", tmp_path / "feed"
    body = ("<article><p>" + "Synthetic source statement and explicit limitations. " * 5
            + "</p><p>Example company reports quarterly financial results.</p></article>").encode()
    client = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, content=body, headers={"content-type": "text/html"})))
    try:
        with db.connect() as conn:
            row = conn.execute(select(news_revisions).order_by(news_revisions.c.received_at.desc())).mappings().first()
            rev = dict(row)
            rev["received_at"] = utc(rev["received_at"])
            saved = news_articles.capture(rev, client, root=articles)
            _, text = news_articles.read_packet(rev, saved["packet_sha256"], root=articles)
            rev["received_at"] = rev["received_at"].isoformat()
            selection = {"revision": rev, "packet_sha256": saved["packet_sha256"],
                "provenance": "MANUAL_PUBLIC_DOCUMENT_OBSERVATION_NOT_RSS",
                "body_review": {"start": 0, "end": len(text), "complete_body": True,
                    "reviewer_id": "synthetic", "boundary_basis": "Entire synthetic article",
                    "reviewed_at": datetime.now(UTC).isoformat(), "related_link_ranges": []}}
            install(conn, [selection], company[0].parent, articles, root=root)
            refresh(conn, client, root=root)
    finally:
        client.close()
    return root, body


def project(db, company, root):
    profiles = {"profiles": [{"id": b.id, "sha256": digest(b.model_dump(mode="json"))}
                            for b in available_bundles(root=company[0].parent)["items"]]}
    with db.connect() as conn:
        return feed(conn, profiles, company[0].parent, article_feed_root=root)


def test_body_company_development_keeps_unit_and_source_spans(db, company, reviewed):
    result = project(db, company, reviewed[0])
    assert result["reviewed_articles"] == 1 and len(result["items"]) == 1
    card = result["items"][0]
    assert card["source_representation"] == "REVIEWED_COMPLETE_BODY"
    assert "financial results" in card["excerpt"]
    assert card["assessment"]["tier"] == "ISSUER_DEVELOPMENT"
    for decision in card["company_discovery"]:
        assert decision["source_spans"]
        for match in decision["matches"]:
            assert decision["source_unit"][match["field"]][match["start"]:match["end"]] == match["text"]
    assert card["delivery"] == "disabled" and not card["narratives"]


@pytest.mark.parametrize("fault", ["expiry", "changed", "withdrawn", "rss", "proof", "registry"])
def test_changed_or_expired_body_withholds_company_cards(db, company, reviewed, fault):
    root, body = reviewed
    path = root / "current.json"
    state = json.loads(path.read_text())
    if fault in {"changed", "withdrawn"}:
        body += b"<p>This article was withdrawn.</p>" if fault == "withdrawn" else b"<p>Correction.</p>"
        client = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(
            200, content=body, headers={"content-type": "text/html"})))
        with db.connect() as conn:
            refresh(conn, client, root=root)
        client.close()
    elif fault == "rss":
        with db.begin() as conn:
            conn.execute(update(news_items).values(version=99))
    else:
        if fault == "expiry":
            state["entries"][0]["checked_at"] = (datetime.now(UTC)-timedelta(hours=2)).isoformat()
        elif fault == "proof":
            state["entries"][0]["proof"] = "0"*64
        else:
            state["profiles"] += "-other"
        path.write_text(json.dumps(state))
    if fault == "registry":
        with pytest.raises(ValueError, match="registry differs"):
            project(db, company, root)
    else:
        result = project(db, company, root)
        assert not result["items"] and not result["background"]
