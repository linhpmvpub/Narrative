import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_profile_news import get
from test_profile_news import linked as linked

from engine.company_profiles import ProfileBundle, load_bundle, withdraw
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


def configured(dossier, scope='CUSTOMER_DEPLOYMENT', name='Orion'):
    root, data = dossier
    quote = f'{name} reports that data center construction and power availability affect customer deployment; semiconductor manufacturing depends on water and power.'
    raw = (root/'source.html').read_bytes() + ('<p>'+quote+'</p>').encode()
    (root/'source.html').write_bytes(raw)
    data['sources'][0]['sha256'] = hashlib.sha256(raw).hexdigest()
    data['legal_name'] = name
    data['relationships'][-1].update(type='AFFECTS_DEMAND' if scope == 'CUSTOMER_DEPLOYMENT' else 'AFFECTS_SUPPLY',
                                   from_id='f', to_id='m' if scope == 'CUSTOMER_DEPLOYMENT' else 'p',
                                   evidence=[{'source_id':'s','quote':quote}])
    data['narratives'][0]['watched_nodes'] = ['m' if scope == 'CUSTOMER_DEPLOYMENT' else 'p']
    data['routing_policies'] = [{'narrative_id':'n','intents':['DEPLOYMENT' if scope == 'CUSTOMER_DEPLOYMENT' else 'SUPPLY'], 'scope_note':'Synthetic scope'}]
    data['factor_bindings'] = [dict(id='readiness',factor_id='f',topic_terms=['resource'],context_terms=['operations'],
        change_terms=['readiness'],kind='SCOPED_ACTIVITY',narrative_ids=['n'],
        readiness_context={'scope':scope,'resources':['POWER','WATER','CONSTRUCTION'] if scope=='CUSTOMER_DEPLOYMENT' else ['POWER','WATER'], 'relationship_id':'effect'},
        scope='Conditional resource context only',reviewed_at=data['available_at'],
        review_until=(datetime.now(UTC)+timedelta(days=20)).isoformat(),evidence=[{'source_id':'s','quote':quote}])]
    seal(root, data)
    return root, data, load_bundle(root)


@pytest.mark.parametrize('name',['Orion','Cobalt'])
@pytest.mark.parametrize('text,expected',[
    ('Grid constraints could delay data center deployment.',True),
    ('Data center construction paused following permit withdrawal.',True),
    ('Power availability limits data center capacity.',True),
    ('Water shortages could delay data center operations.',True),
    ('Data center operators recover stranded power capacity.',True),
    ('Data center software adds powerful scheduling tools.',False),
    ('Power shortages delay automobile production.',False),
    ('Data center shares rose while residential construction was delayed.',False),
    ('Data center operators expand software capacity and residential power outages worsen.',False),
    ('A vendor ships low-power memory capacity for AI data centers.',False),
    ('New data center memory provides power efficiency and higher capacity.',False),
    ('Data center chip capacity expands with lower power consumption.',False),
    ('Data center power supply constraints affect deployment.',True),
    ('Data center operators face shortages of electrical power.',True),
    ('Data centers deploy software. Water shortages delay farming.',False),
    ('No power shortage is reported at the data center.',False),
    ('Data center operators denied power constraints.',False),
])
def test_context_routes_without_claiming_company_event(dossier,name,text,expected):
    _,_,b=configured(dossier,name=name)
    links=list(binding_decisions(b,b.narratives[0],{'title':text},datetime.now(UTC)))
    assert bool(links)==expected
    if expected:
        result=assess({'headline':text,'excerpt':''},[{'matches':links[0]['matches']}],json.loads(POLICY.read_text()))
        assert result['tier']=='BACKGROUND_THEME' and not result['signals']
        assert result['direction']==result['horizon']=='UNKNOWN'
        for s in links[0]['matches']:
            assert text[s['start']:s['end']]==s['text']
            assert s['context_only'] and not s['readiness_context']['company_incident_verified']


@pytest.mark.parametrize('text,expected',[
    ('How industrial power outages disrupt manufacturing operations',True),
    ('Why industrial water shortages constrain production',True),
    ('Power shortages constrain semiconductor production.',True),
    ('Water availability limits chip manufacturing.',True),
    ('Power shortages constrain automobile manufacturing.',False),
    ('A food plant halts production because of a power shortage.',False),
    ('Data center power capacity expands.',False),
])
def test_manufacturing_market_or_general_utility_explainer(dossier,text,expected):
    _,_,b=configured(dossier,'MANUFACTURING')
    assert bool(list(binding_decisions(b,b.narratives[0],{'title':text},datetime.now(UTC))))==expected


def test_no_cross_field_or_cross_narrative_donation(dossier):
    _,data,b=configured(dossier)
    text='Data center power capacity is constrained.'
    assert not matches(b.factor_bindings[0],{'title':'Data center deployment', 'summary':'Power capacity is constrained.'})
    data['routing_policies'][0]['intents']=['SUPPLY']
    b=ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b,b.narratives[0],{'title':text},datetime.now(UTC)))


@pytest.mark.parametrize('name',['Orion','Cobalt'])
@pytest.mark.parametrize('text,expected',[
    ('Cooling constraints delay data center deployment.',True),
    ('Data center cooling capacity is constrained.',True),
    ('Cooling shortages delay food processing.',False),
    ('Data center memory capacity rises with new cooling technology.',False),
    ('Data centers expand software capacity and household cooling shortages worsen.',False),
    ('Data center operators denied cooling constraints.',False),
])
def test_cooling_requires_explicit_sourced_scope(dossier,name,text,expected):
    root,data,b=configured(dossier,name=name)
    assert not list(binding_decisions(b,b.narratives[0],{'title':text},datetime.now(UTC)))
    quote='Data center deployment depends on cooling availability.'
    raw=(root/'source.html').read_bytes()+('<p>'+quote+'</p>').encode()
    (root/'source.html').write_bytes(raw)
    data['sources'][0]['sha256']=hashlib.sha256(raw).hexdigest()
    binding=data['factor_bindings'][0]
    binding['readiness_context']['resources']=['COOLING']
    evidence=[{'source_id':'s','quote':quote}]
    binding['evidence']=evidence
    data['relationships'][-1]['evidence']=evidence
    seal(root,data)
    b=load_bundle(root)
    links=list(binding_decisions(b,b.narratives[0],{'title':text},datetime.now(UTC)))
    assert bool(links)==expected
    if expected:
        result=assess({'headline':text,'excerpt':''},[{'matches':links[0]['matches']}],json.loads(POLICY.read_text()))
        assert result['tier']=='BACKGROUND_THEME' and not result['signals']
        assert all(m['context_only'] for m in links[0]['matches'])


@pytest.mark.parametrize('fault',['revoked','expired','future','disabled'])
def test_source_route_and_binding_lifecycle(dossier,fault):
    _,data,_=configured(dossier)
    now=datetime.now(UTC)
    if fault=='revoked':
        data['relationships'][-1]['status']='REVOKED'
    if fault=='expired':
        data['relationships'][-1]['valid_until']=data['available_at']
    if fault=='future':
        data['relationships'][-1]['known_at']=(now+timedelta(days=1)).isoformat()
        with pytest.raises(ValueError,match='Future relation knowledge'):
            ProfileBundle.model_validate(data)
        return
    if fault=='disabled':
        data['factor_bindings'][0]['enabled']=False
    b=ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b,b.narratives[0],{'title':'Data center power capacity is constrained.'},now))


@pytest.mark.parametrize('fault',['resource','scope','guard','duplicate'])
def test_reject_unsupported_or_overlapping_binding(dossier,fault):
    _,data,_=configured(dossier)
    binding=data['factor_bindings'][0]
    if fault=='resource':
        binding['evidence'][0]['quote']='Data center capacity.'
    if fault=='scope':
        binding['evidence'][0]['quote']='Water, power and construction matter to agricultural production.'
    if fault=='guard':
        binding['market_scope']='APPLICATION_SOFTWARE'
    if fault=='duplicate':
        binding['readiness_context']['resources']=['POWER','POWER']
    with pytest.raises(ValueError,match='Readiness context'):
        ProfileBundle.model_validate(data)


@pytest.mark.parametrize('fault',['corrected','retracted','withdrawn','tampered'])
def test_rss_readiness_cards_recheck_original_source_and_profile(db,linked,fault):
    root,data,insert,_,_=linked
    configured((root,data))
    insert(title='Power availability limits data center capacity.',summary='Conditional operating context.')
    card=get(db)['items'][0]
    assert card['delivery']=='disabled' and card['impact']=='UNKNOWN'
    assert card['links'][0]['matches'][0]['routing_contract']['role']=='OPERATING_READINESS_CONTEXT'
    if fault=='corrected':
        insert(title='Software scheduling update',summary='New user interface.')
    elif fault=='retracted':
        insert(title='Power availability limits data center capacity.',summary='This article has been retracted.')
    elif fault=='withdrawn':
        withdraw(root)
    else:
        (root/'source.html').write_bytes(b'changed source')
    assert not get(db)['items']


@pytest.mark.parametrize('fault',['missing','foreign_factor','wrong_type','unsupported_edge'])
def test_readiness_requires_its_own_sourced_mechanism(dossier,fault):
    _,data,_=configured(dossier)
    if fault=='missing':
        data['factor_bindings'][0]['readiness_context']['relationship_id']='absent'
    elif fault=='foreign_factor':
        data['nodes'].append({'id':'other','kind':'factor','label':'Other'})
        data['relationships'][-1]['from_id']='other'
    elif fault=='wrong_type':
        data['relationships'][-1]['type']='AFFECTS_REVENUE'
    else:
        data['relationships'][-1]['evidence']=[{'source_id':'s','quote':'No resource evidence.'}]
    with pytest.raises(ValueError,match='Readiness context'):
        ProfileBundle.model_validate(data)
