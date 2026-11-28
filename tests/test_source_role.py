import json
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_profile_news import get
from test_profile_news import linked as linked
from test_readiness_context import configured

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import FactorBinding
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.market_developments import classify
from engine.profile_news import matches
from engine.profile_routing import binding_decisions
from engine.source_role import assess as source_role
from engine.source_sentences import source_units


@pytest.mark.parametrize('name',['Orion','Cobalt'])
@pytest.mark.parametrize('resource',['power','water'])
@pytest.mark.parametrize('headline,expected',[
    ('Operator completes financial audit',False),
    ('Data center adds new board member',False),
    ('Data center {r} availability review',True),
    ('Data center opens; farms report {r} shortages',False),
    ('Data center {r} shares surge',False),
])
def test_persistent_state_needs_explicit_primary_focus(dossier,name,resource,headline,expected):
    _,_,bundle=configured(dossier,name=name)
    text=f'{name} data center has also maintained {resource} availability since 2021.'
    article={'title':headline.format(r=resource),'summary':text}
    links=list(binding_decisions(bundle,bundle.narratives[0],article,datetime.now(UTC)))
    assert bool(links)==expected
    if expected:
        result=assess({'headline':article['title'],'excerpt':text},[{'matches':link['matches']} for link in links],json.loads(POLICY.read_text()))
        assert result['tier']=='BACKGROUND_THEME' and not result['signals']


@pytest.mark.parametrize('text',[
    'Power shortages could delay data center deployment.',
    'Grid strain limits data center capacity.',
    'Construction paused at the data center.',
    'The data center has lost power capacity.',
])
def test_secondary_substantive_statement_survives_unrelated_headline(dossier,text):
    _,_,bundle=configured(dossier)
    article={'title':'Operator provides business update','summary':text}
    assert list(binding_decisions(bundle,bundle.narratives[0],article,datetime.now(UTC)))


def test_body_units_and_rss_share_focus_without_borrowing_evidence(dossier):
    _,_,bundle=configured(dossier)
    narrative=bundle.narratives[0]
    headline='Operator publishes audit'
    text='The data center has maintained power availability since 2019. Grid constraints could delay data center deployment.'
    units=list(source_units(text))
    assert len(units)==2
    links=[list(binding_decisions(bundle,narrative,{**unit,'context_title':headline},datetime.now(UTC))) for unit in units]
    assert not links[0] and links[1]
    assert list(binding_decisions(bundle,narrative,{'title':headline,'summary':text},datetime.now(UTC)))
    # A focus title cannot create a resource or market missing from the source unit.
    assert not list(binding_decisions(bundle,narrative,{'context_title':'Data center power capacity',
        'summary':'The operator has maintained availability since 2019.'},datetime.now(UTC)))


def test_original_offsets_and_no_cross_clause_suppression():
    text='An operator has maintained water availability since 2019 but data center power capacity is constrained'
    start=text.index('data center')
    role=source_role(text,start,len(text))
    assert role['allowed'] and role['description_span'] is None
    span=role['clause_span']
    assert text[span['start']:span['end']]==span['text']
    text='The data center has maintained power availability since 2019'
    role=source_role(text,0,len(text))
    assert not role['allowed']
    span=role['description_span']
    assert text[span['start']:span['end']]==span['text']


@pytest.mark.parametrize('text',[
    'The data center is equipped with redundant power capacity.',
    'The data center has provided power availability for 12 years.',
])
def test_capability_and_history_are_background_without_primary_focus(dossier,text):
    _,_,bundle=configured(dossier)
    assert not list(binding_decisions(bundle,bundle.narratives[0],{'title':'Operator announces audit','summary':text},datetime.now(UTC)))


def market_binding():
    now=datetime.now(UTC)
    return FactorBinding(id='market',factor_id='f',topic_terms=['data center'],context_terms=['infrastructure'],
        kind='STRUCTURED_ACTIVITY',activity_rule={'version':'activity-assertions-v2','market':'DATA_CENTER','event_types':['INFRASTRUCTURE_DEVELOPMENT']},
        narrative_ids=['n'],scope='Synthetic sourced market scope',reviewed_at=now,review_until=now+timedelta(days=1),
        evidence=[{'source_id':'s','quote':'Customer data center construction affects demand.'}])


@pytest.mark.parametrize('name',['Orion','Cobalt'])
def test_capability_does_not_become_new_project_even_in_headline(name):
    text=f'{name} specializes in building data centers.'
    assert classify(text)['phase']=='BACKGROUND'
    assert not matches(market_binding(),{'title':'An operator publishes results','summary':text})
    spans=matches(market_binding(),{'title':text})
    assert spans and all(s['context_only'] for s in spans)
    assert spans[0]['activity_assertion']['phase']=='BACKGROUND'
    result=assess({'headline':text,'excerpt':''},[{'matches':spans}],json.loads(POLICY.read_text()))
    assert result['tier']=='BACKGROUND_THEME' and not result['signals']


@pytest.mark.parametrize('text',[
    'Orion, a provider of servers, plans a new data center.',
    'Orion is a provider of servers that plans a new data center.',
    'Orion specializes in memory packaging and builds a data center.',
    'Orion specializes in building data centers and Cobalt plans a new data center.',
])
def test_company_description_does_not_erase_separate_new_project(text):
    spans=matches(market_binding(),{'title':'Operator business update','summary':text})
    assert spans
    result=assess({'headline':'Operator business update','excerpt':text},[{'matches':spans}],json.loads(POLICY.read_text()))
    assert result['signals']


def test_later_substantive_sentence_survives_description():
    text='Orion specializes in building data centers. Cobalt plans an AI infrastructure test.'
    spans=matches(market_binding(),{'title':'Operator update','summary':text})
    assert spans and spans[0]['activity_assertion']['text'].strip().startswith('Cobalt')
    for span in spans:
        assert text[span['start']:span['end']]==span['text']


def test_reviewed_article_projection_uses_same_statement_scope(dossier):
    _,_,bundle=configured(dossier)
    blocks=[{'text':'The data center has maintained power availability since 2019.', 'source_spans':[]}]
    now=datetime.now(UTC)
    assert not list(article_decisions(bundle,bundle.narratives[0],'Operator completes audit',blocks,now))
    cards=list(article_decisions(bundle,bundle.narratives[0],'Data center power availability review',blocks,now))
    assert any(c['field']=='body' for c in cards)
    assert all(s['context_only'] for c in cards for s in c['matches'])
    body=next(c for c in cards if c['field']=='body')
    assert 'chưa phải thay đổi mới' in body['matches'][0]['routing_contract']['explanation']


def test_rss_corrections_reassess_description_and_new_development(db,linked):
    root,data,insert,_,_=linked
    configured((root,data))
    insert(title='Operator completes audit',summary='The data center has maintained power availability since 2019.')
    assert not get(db)['items']
    insert(title='Operator completes audit',summary='Power shortages could delay data center deployment.')
    card=get(db)['items'][0]
    assert card['delivery']=='disabled'
    assert card['links'][0]['matches'][0]['readiness_context']['source_role']['allowed']
    insert(title='Operator completes audit',summary='The data center has maintained power availability since 2019.')
    assert not get(db)['items']


@pytest.mark.parametrize('start,end',[(-1,4),(2,2),(0,100)])
def test_source_role_rejects_invalid_offsets(start,end):
    with pytest.raises(ValueError,match='original candidate offsets'):
        source_role('Original source text',start,end)
