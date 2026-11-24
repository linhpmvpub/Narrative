"""Synthetic source refresh, correction and withdrawal lifecycle integration."""
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, update
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_product import client as client
from test_product import headers
from test_product import identities as identities
from test_profile_news import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.adapters.news import NewsClient, canonical_url
from engine.article_feed import approve_replacement, feed, install, refresh
from engine.ingestion.contracts import digest
from engine.models.schema_v13 import news_items
from engine.news_articles import capture, read_packet, root_dir
from engine.news_capture import read_capture


@pytest.fixture
def configured(db, selection, tmp_path, monkeypatch):
    root = tmp_path / 'feed'
    monkeypatch.setenv('ARTICLE_FEED_ROOT', str(root))
    with db.begin() as conn:
        item = conn.execute(select(news_items)).mappings().one()
        payload = {**item['payload'], 'url': selection['revision']['payload']['url']}
        conn.execute(update(news_items).values(payload=payload, content_sha256=digest(payload),
            article_key=digest(canonical_url(payload['url']))))
        install(conn, [selection], Path(os.environ['COMPANY_PROFILE_ROOT']), root_dir())
    rev = {**selection['revision'], 'received_at': datetime.fromisoformat(selection['revision']['received_at'])}
    packet, _ = read_packet(rev, selection['packet_sha256'])
    body = read_capture(root_dir() / 'bodies', packet['body_sha256'], '.html')
    return root, body


def recheck(db, body, status=200):
    c = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        status, content=body, headers={'content-type': 'text/html'})))
    try:
        with db.connect() as conn:
            return refresh(conn, c)
    finally:
        c.close()


def project(db, **kw):
    with db.connect() as conn:
        return feed(conn, **kw)


def test_feed_requires_recheck_and_auth_then_filters(db, configured, client, identities):
    assert project(db)['items'] == []
    assert recheck(db, configured[1])['states'] == {'ACTIVE': 1}
    result = project(db)
    assert len(result['items']) == 1 and result['delivery'] == 'disabled'
    card = result['items'][0]
    assert not project(db, ticker='OTHER')['items']
    assert len(project(db, narrative=card['profile_id']+':'+card['narrative_id'])['items']) == 1
    assert not project(db, narrative='unknown')['items']
    assert client.get('/api/v0/news/profile-articles').status_code == 401
    response = client.get('/api/v0/news/profile-articles', headers=headers(identities[0]))
    assert response.status_code == 200 and len(response.json()['items']) == 1
    assert 'selection' not in response.json() and 'profiles' not in response.json()


@pytest.mark.parametrize('change', ['html', 'withdrawal', 'rss', 'rss_withdrawal', 'missing', 'expiry', 'corrupt'])
def test_correction_withdrawal_expiry_fail_closed(db, configured, change):
    root, body = configured
    recheck(db, body)
    if change == 'html':
        recheck(db, body.replace(b'prices fall', b'prices rise'))
    elif change == 'withdrawal':
        recheck(db, body + b'<p>This article has been withdrawn.</p>')
    elif change in {'rss', 'rss_withdrawal'}:
        with db.begin() as conn:
            row = conn.execute(select(news_items)).mappings().one()
            payload = {**row['payload'], 'withdrawn': change == 'rss_withdrawal'}
            conn.execute(update(news_items).values(version=row['version']+1,
                payload=payload, content_sha256=digest(payload)))
        assert not project(db)['items']  # Immediate local revision gate, before network refresh.
        recheck(db, body)
    elif change == 'missing':
        recheck(db, b'', 404)
    else:
        p = root / 'current.json'
        state = json.loads(p.read_text())
        state['entries'][0]['checked_at'] = (datetime.now(UTC)-timedelta(hours=2)).isoformat()
        if change == 'corrupt':
            state['entries'][0]['proof'] = '0'*64
        p.write_text(json.dumps(state))
    assert not project(db)['items']
    if change in {'html', 'withdrawal', 'rss', 'rss_withdrawal'}:
        recheck(db, body)
        assert not project(db)['items']  # Reversion cannot silently restore approval.


def test_network_failure_recovers_without_mutating_review(db, configured):
    recheck(db, b'', 503)
    assert not project(db)['items']
    recheck(db, configured[1])
    assert len(project(db)['items']) == 1
    assert len(list(configured[0].glob('state-v*.json'))) == 5


def test_explicit_reviewed_replacement_requires_recheck(db, configured, selection):
    recheck(db, configured[1] + b'<p>This article was withdrawn.</p>')
    with db.connect() as conn:
        with pytest.raises(ValueError, match='New capture'):
            approve_replacement(conn, selection)
    rev = {**selection['revision'], 'received_at': datetime.fromisoformat(selection['revision']['received_at'])}
    c = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, content=configured[1], headers={'content-type': 'text/html'})))
    try:
        new = capture(rev, c)
    finally:
        c.close()
    selection['packet_sha256'] = new['packet_sha256']
    selection['body_review']['reviewed_at'] = datetime.now(UTC).isoformat()
    with db.connect() as conn:
        approve_replacement(conn, selection)
    assert not project(db)['items']
    recheck(db, configured[1])
    assert len(project(db)['items']) == 1
