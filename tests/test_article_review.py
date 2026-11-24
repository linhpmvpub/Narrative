import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_article_feed import configured as configured
from test_article_feed import project, recheck
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_profile_news import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.adapters.news import NewsClient
from engine.article_review import approve, prepare, queue


def test_operator_commands_import_in_fresh_process():
    for module in ['engine.article_review', 'engine.article_feed']:
        result = subprocess.run([sys.executable, '-m', module, '--help'],
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr


def draft(db, configured, selection, tmp_path):
    body = configured[1].replace(b'prices fall', b'prices rise')
    recheck(db, body)
    output = tmp_path / 'review'
    client = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, content=body, headers={'content-type': 'text/html'})))
    try:
        with db.connect() as conn:
            prepare(conn, client, selection['revision']['payload']['url'], output)
    finally:
        client.close()
    return output, body


def complete(output, selection):
    p = output / 'selection.json'
    data = json.loads(p.read_text(encoding='utf-8'))
    data['body_review'] = {**selection['body_review'], 'reviewed_at': datetime.now(UTC).isoformat()}
    p.write_text(json.dumps(data), encoding='utf-8')


def test_review_queue_draft_and_explicit_replacement(db, configured, selection, tmp_path):
    with db.connect() as conn:
        assert queue(conn)['items'][0]['action'] == 'RECHECK'
    recheck(db, configured[1])
    with db.connect() as conn:
        assert not queue(conn)['items']
    output, body = draft(db, configured, selection, tmp_path)
    with db.connect() as conn:
        assert queue(conn)['items'][0]['action'] == 'EXPLICIT_BODY_REVIEW'
        with pytest.raises((ValueError, TypeError)):
            approve(conn, output)
    assert not project(db)['items']
    assert 'prices rise' in (output / 'review.html').read_text(encoding='utf-8')
    complete(output, selection)
    with db.connect() as conn:
        assert approve(conn, output)['status'] == 'AWAITING_RECHECK'
        with pytest.raises(ValueError, match='stale'):
            approve(conn, output)
    assert not project(db)['items']
    recheck(db, body)
    assert project(db)['items']


@pytest.mark.parametrize('change', ['entry', 'candidate', 'inbox'])
def test_review_rejects_changes_during_review(db, configured, selection, tmp_path, change):
    from sqlalchemy import update

    from engine.models.schema_v13 import news_items
    output, _ = draft(db, configured, selection, tmp_path)
    complete(output, selection)
    if change == 'entry':
        p = configured[0] / 'current.json'
        state = json.loads(p.read_text())
        state['entries'][0]['status'] = 'WITHDRAWN'
        p.write_text(json.dumps(state))
    elif change == 'candidate':
        p = output / 'selection.json'
        data = json.loads(p.read_text())
        data['revision']['payload']['title'] = 'changed'
        p.write_text(json.dumps(data))
    else:
        with db.begin() as conn:
            conn.execute(update(news_items).values(version=news_items.c.version+1))
    with db.connect() as conn:
        with pytest.raises(ValueError):
            approve(conn, output)
    assert not project(db)['items']


@pytest.mark.parametrize('reason', ['UNAVAILABLE', 'PROOF_EXPIRED'])
def test_temporary_holds_request_recheck_without_approval(db, configured, reason):
    recheck(db, configured[1])
    if reason == 'UNAVAILABLE':
        recheck(db, b'', 503)
    else:
        p = configured[0] / 'current.json'
        state = json.loads(p.read_text())
        state['entries'][0]['checked_at'] = (datetime.now(UTC)-timedelta(hours=2)).isoformat()
        p.write_text(json.dumps(state))
    with db.connect() as conn:
        row = queue(conn)['items'][0]
        assert row['reasons'] == [reason] and row['action'] == 'RECHECK'
    assert not project(db)['items']
    recheck(db, configured[1])
    assert project(db)['items']
