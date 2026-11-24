import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import QUOTE, seal
from test_company_profiles import dossier as dossier

from engine.impact_atlas import (
    MECHANISMS,
    ExposureFact,
    Scenario,
    install,
    read_snapshot,
    scenario,
    snapshot,
)


def test_snapshot_relational_integrity_and_no_invented_exposure(dossier, tmp_path):
    root, _ = dossier
    data = snapshot(root.parent)
    assert len(data['components']) == 42
    assert len(data['relations']) == 3
    assert data['policy']['weights'] is None
    assert all(d['status'] == 'UNKNOWN' and d['value'] is None
               for e in data['exposures'] for d in e['dimensions'].values())
    output = tmp_path / 'export'
    install(data, output)
    assert read_snapshot(output) == data
    with sqlite3.connect(output / 'atlas.db') as db:
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('SELECT count(*) FROM relations').fetchone()[0] == 3
        assert db.execute('SELECT count(*) FROM mechanisms').fetchone()[0] == 7
    with pytest.raises(FileExistsError):
        install(data, output)
    (output / 'atlas.db').write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        read_snapshot(output)


def test_candidate_expired_and_future_edges_not_eligible(dossier):
    root, data = dossier
    data['relationships'][0]['status'] = 'CANDIDATE'
    data['relationships'][1]['valid_until'] = '2025-01-01T00:00:00+00:00'
    data['relationships'][2]['valid_from'] = (datetime.now(UTC)+timedelta(days=1)).isoformat()
    seal(root, data)
    result = snapshot(root.parent)
    assert not any(r['eligible_at_snapshot'] for r in result['relations'])
    event = Scenario(mechanism_id='policy',factor_id='example/f',direction='UP',phase='OPERATING',scope='synthetic')
    assert not scenario(result, event)['paths']


def test_source_corruption_blocks_snapshot(dossier):
    root, _ = dossier
    (root / 'source.html').write_text('corrupt')
    with pytest.raises(ValueError, match='registry'):
        snapshot(root.parent)


def test_seven_event_groups_and_both_directions_remain_conditional(dossier):
    root, _ = dossier
    data = snapshot(root.parent)
    # 42 grouped synthetic scenarios; not empirical relevance/strength validation.
    for name, rule in MECHANISMS.items():
        for direction in ['UP', 'DOWN']:
            for phase in ['PROPOSED', 'COMMITTED', 'OPERATING']:
                event = Scenario(mechanism_id=name,factor_id='example/f',direction=direction,phase=phase,scope='synthetic')
                result = scenario(data, event)
                expected = rule['sign']*(1 if direction == 'UP' else -1)
                assert result['conditional_channel_direction'] == ('UP' if expected > 0 else 'DOWN')
                assert result['financial_magnitude'] == 'UNKNOWN'
                assert result['realized_effect'] == 'NOT_ESTABLISHED'
                assert result['horizon']['lag_min_days'] is None
                assert result['delivery'] == 'disabled' and result['price_prediction'] is None
                assert result['paths'][0]['relations'] == ['example/applies','example/effect']
                assert result['paths'][0]['strength'] == 'UNKNOWN'


def fact(dossier):
    _, d = dossier
    return {'id':'synthetic-fact','version':1,'relation_id':'example/owns',
        'dimension':'substitutability','value':'Synthetic reviewed category','unit':'category',
        'scope':'Synthetic product only','valid_from':d['available_at'],'known_at':d['available_at'],
        'reviewed_at':datetime.now(UTC).isoformat(),'reviewer_id':'test','reviewer_kind':'AI_OPERATOR',
        'evidence':[{'source_id':'example/s','quote':QUOTE}]}


def test_reviewed_facts_persist_with_evidence_and_overlap_rejected(dossier, tmp_path):
    root, _ = dossier
    f = fact(dossier)
    data = snapshot(root.parent, facts=[f])
    value = data['exposures'][0]['dimensions']['substitutability']
    assert value['status'] == 'SOURCED' and value['reviewer_kind'] == 'AI_OPERATOR'
    with pytest.raises(ValueError, match='Overlapping'):
        snapshot(root.parent, facts=[f,{**f,'id':'another'}])
    output = tmp_path / 'facts-export'
    install(data, output)
    with sqlite3.connect(output/'atlas.db') as db:
        assert db.execute('select count(*) from fact_evidence').fetchone()[0] == 1


@pytest.mark.parametrize('fault', ['quote','source','future','unit','value','reviewer'])
def test_invalid_exposure_facts_fail_closed(dossier, fault):
    root, _ = dossier
    f = fact(dossier)
    if fault == 'quote':
        f['evidence'][0]['quote'] = 'invented'
    elif fault == 'source':
        f['evidence'][0]['source_id'] = 'other/s'
    elif fault == 'future':
        f['reviewed_at'] = (datetime.now(UTC)+timedelta(days=1)).isoformat()
    elif fault == 'reviewer':
        f['reviewer_id'] = '   '
    elif fault == 'unit':
        f['unit'] = 'days'
    else:
        f.update(dimension='exposure_share',unit='fraction',value='1.2')
    with pytest.raises(ValueError):
        snapshot(root.parent, facts=[f])


def test_horizon_and_dimensions_validate_without_defaults(dossier):
    with pytest.raises(ValueError):
        Scenario(mechanism_id='policy',factor_id='example/f',direction='UP',phase='OPERATING',
                 scope='synthetic',lag_min_days=90,lag_max_days=10)
    f = fact(dossier)
    f.update(dimension='exposure_share',unit='fraction',value='NaN')
    with pytest.raises(ValueError):
        ExposureFact.model_validate(f)


@pytest.mark.parametrize("missing", ["period_label", "measurement_basis", "precision"])
def test_numeric_exposure_requires_period_denominator_and_precision(dossier, missing):
    f = fact(dossier)
    f.update(dimension='customer_concentration',unit='fraction',value='0.12')
    with pytest.raises(ValueError, match='Numeric exposure'):
        ExposureFact.model_validate(f)
    f.update(period_label='Synthetic fiscal quarter',period_end='2024-01-01',
             measurement_basis='One anonymous customer revenue / total company revenue',
             precision='EXACT_REPORTED')
    parsed = ExposureFact.model_validate(f)
    assert parsed.value == '0.12'
    incomplete = {k: v for k, v in f.items() if k != missing}
    with pytest.raises(ValueError, match='Numeric exposure'):
        ExposureFact.model_validate(incomplete)
    root, _ = dossier
    result = snapshot(root.parent, facts=[f])
    stored = result['exposures'][0]['dimensions']['customer_concentration']
    assert stored['measurement_basis'] == f['measurement_basis']
    assert stored['period_end'] == '2024-01-01'
    assert stored['precision'] == 'EXACT_REPORTED'
    f['period_end'] = '2999-01-01'
    with pytest.raises(ValueError, match='chronology'):
        ExposureFact.model_validate(f)


def test_html_embedded_source_text_cannot_execute(dossier, tmp_path):
    root, _ = dossier
    data = snapshot(root.parent)
    data['nodes'][0]['label'] = '</script><script>alert(1)</script> __SCRIPT__'
    install(data, tmp_path/'escape')
    html = (tmp_path/'escape/index.html').read_text(encoding='utf-8')
    assert '</script><script>alert(1)' not in html
    assert '__SCRIPT__' in html
    assert "connect-src 'none'" in html
    assert json.loads((tmp_path/'escape/atlas.json').read_text(encoding='utf-8'))['nodes'][0]['label'].startswith('</script>')
