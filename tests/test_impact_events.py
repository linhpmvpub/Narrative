import os
from datetime import UTC, datetime, timedelta

import pytest
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_profile_news import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.impact_atlas import snapshot
from engine.impact_events import EventFrame, assess
from engine.ingestion.contracts import digest


def frame(selection):
    now = datetime.now(UTC)
    return EventFrame(id='synthetic-event', version=1, mechanism_id='input_price',
        factor_id='example/f', direction='DOWN', phase='OPERATING', scope='Synthetic server memory',
        source_quote='Server memory prices fall.', selection_sha256=digest(selection),
        available_at=now, reviewed_at=now, reviewer_id='synthetic-review', reviewer_kind='AI_OPERATOR')


def test_event_frame_routes_without_keywords_or_financial_promotion(linked, dossier, selection):
    data = snapshot(os.environ["COMPANY_PROFILE_ROOT"])
    result = assess(data, frame(selection), selection)
    assert result['paths']
    assert result['conditional_channel_direction'] == 'DOWN'
    assert result['financial_magnitude'] == 'UNKNOWN' and result['delivery'] == 'disabled'
    assert result['event']['reviewer_kind'] == 'AI_OPERATOR'
    unknown = frame(selection).model_copy(update={'direction':'UNKNOWN'})
    assert assess(data, unknown, selection)['conditional_channel_direction'] == 'UNKNOWN'


@pytest.mark.parametrize('fault', ['quote','selection','future','factor','mechanism','source_time'])
def test_event_rejects_unsupported_or_unavailable_inputs(linked, dossier, selection, fault):
    data = snapshot(os.environ["COMPANY_PROFILE_ROOT"])
    f = frame(selection)
    changes = {'quote':{'source_quote':'invented'}, 'selection':{'selection_sha256':'0'*64},
        'future':{'reviewed_at':datetime.now(UTC)+timedelta(days=1)},
        'factor':{'factor_id':'unknown'}, 'mechanism':{'mechanism_id':'unknown'},
        'source_time':{'available_at':datetime.now(UTC)-timedelta(days=1)}}
    with pytest.raises(ValueError):
        assess(data, f.model_copy(update=changes[fault]), selection)
