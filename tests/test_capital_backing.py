import json

import pytest
from test_core_activity import activity

from engine.core_activity import assess
from engine.core_decisions import POLICY


@pytest.mark.parametrize('name',['Orion','Cobalt'])
@pytest.mark.parametrize('template,eligible',[
    ('{n} backs startup developing a data center cooling system.',True),
    ('{n} invested in a company manufacturing memory chips.',True),
    ('{n} will fund a startup building AI infrastructure.',True),
    ('{n} plans to back a supplier developing server cooling.',True),
    ('{n} backs a lawsuit against a startup developing cooling systems.',False),
    ('{n} backs a conference about a company developing memory.',False),
    ('{n} could back a startup developing cooling.',False),
    ('{n} did not back a startup developing cooling.',False),
    ('{n} backs a startup discussing AI.',False),
    ('{n} backs a startup developing application software.',False),
    ('{n} backs a startup, while another company builds cooling systems.',False),
    ('{n} designed tools to back a startup developing cooling.',False),
])
def test_backing_requires_counterparty_operating_purpose_and_asserted_phase(name,template,eligible):
    text=template.format(n=name)
    result=activity(text)
    assert bool(result['signals']) is eligible
    assert result['direction']==result['horizon']=='UNKNOWN'
    if eligible:
        signal=result['signals'][0]
        assert signal['event_type']=='CAPITAL_BACKING'
        d=signal['operating_development']
        assert d['capital_disbursed']=='UNKNOWN' and d['amount']=='NOT_EXTRACTED'
        assert not d['identity_verified'] and d['financial_impact']=='UNKNOWN'
        assert signal['phase']==('FORWARD_LOOKING' if 'will' in text or 'plans to' in text else 'SOURCE_REPORTED_BACKING')
        for key in ['action_span','counterparty_span','purpose_action_span','object_span']:
            s=d[key]
            assert text[s['start']:s['end']]==s['text']


def test_backing_cannot_create_graph_paths_or_borrow_amounts():
    text='Orion backs startup developing data center cooling.'
    policy=json.loads(POLICY.read_text())
    assert not assess({'headline':text,'excerpt':'Funding totals $500k.'},[],policy)['signals']
    result=assess({'headline':text,'excerpt':'Funding totals $500k.'},[
        {'matches':[{'field':'title','start':0,'end':5}]}],policy)
    assert result['signals'][0]['operating_development']['amount']=='NOT_EXTRACTED'
