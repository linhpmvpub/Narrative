"""Product-facing source excerpts and routing boundaries, entirely synthetic."""
import json
from datetime import UTC, datetime

import httpx
import pytest
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_profile_news import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.adapters.news import NewsClient
from engine.article_cards import Blocks, build, decisions, render, substantive_blocks
from engine.company_profiles import ProfileBundle
from engine.news_articles import capture, read_packet


def test_inline_fragments_preserve_source_order_and_block_boundaries():
    parser = Blocks()
    parser.feed('<p>Server <b>memory</b> prices fall.</p><p>Other story.</p><script>ignore</script>')
    assert parser.parts == ['Server', 'memory', 'prices fall.', 'Other story.']
    assert len(set(parser.groups[:3])) == 1
    assert parser.groups[3] != parser.groups[2]


def test_no_legacy_cross_sentence_or_cross_paragraph_matching(linked):
    bundle = ProfileBundle.model_validate(linked[1])
    n = bundle.narratives[0]
    at = datetime.now(UTC)
    assert not list(decisions(bundle, n, '', [{'text': 'Memory prices rise. Unrelated server opens.',
                                             'source_spans': []}], at))
    assert not list(decisions(bundle, n, 'Memory', [{'text': 'Server prices fall.', 'source_spans': []}], at))
    hits = list(decisions(bundle, n, '', [{'text': 'Server memory prices fall.', 'source_spans': []}], at))
    assert hits and hits[0]['excerpt'] == 'Server memory prices fall'
    for match in hits[0]['matches']:
        assert hits[0]['paragraph'][match['start']:match['end']] == match['text']


def test_cards_show_provenance_unknowns_archive_and_escaped_text(linked, selection):
    selection['revision']['payload']['title'] = 'Test bulletin'  # Same pinned observation.
    blocks, suppressed = substantive_blocks(selection, datetime.now(UTC))
    assert not suppressed
    assert all('Related:' not in b['text'] for b in blocks)
    result = build([selection, selection])
    assert len(result['audit']) == len(result['items']) == 1
    card = result['items'][0]
    assert card['freshness'] == 'ARCHIVE_CONTEXT'
    assert card['impact'] == 'UNKNOWN' and card['delivery'] == 'disabled'
    assert card['path'] and card['evidence']['matches'][0]['source_spans']
    card['headline'] = '<script>alert(1)</script>'
    output = render(result)
    assert '<script>alert(1)' not in output and '&lt;script&gt;' in output
    assert 'Đọc nguồn' in output and 'Vì sao liên quan' in output
    assert 'RELATED_INFORMATION' in json.dumps(result)


@pytest.mark.parametrize('heading', ['About ExampleCo', 'Forward-Looking Statements', 'CAUTIONARY STATEMENT'])
def test_boilerplate_not_promoted_to_news(linked, selection, heading):
    revision = {**selection['revision'], 'received_at': datetime.fromisoformat(selection['revision']['received_at'])}
    body = ('<article><p>' + 'Board appointment only. ' * 12
            + f'</p><h2>{heading}</h2><p>Server <b>memory</b> prices and supply risks.</p></article>').encode()
    client = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, content=body, headers={'content-type': 'text/html'})))
    try:
        saved = capture(revision, client)
    finally:
        client.close()
    _, text = read_packet(revision, saved['packet_sha256'])
    selection['packet_sha256'] = saved['packet_sha256']
    selection['body_review'].update(start=0, end=len(text), related_link_ranges=[],
                                   reviewed_at=datetime.now(UTC).isoformat())
    result = build([selection])
    assert result['items'] == []
    assert result['audit'][0]['suppressed_blocks'] == 2
