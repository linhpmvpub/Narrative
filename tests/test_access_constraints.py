import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal

from engine.company_profiles import ProfileBundle, load_bundle
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


def configured(dossier, name):
    root, data = dossier
    quote = f"{name} supplies GPUs for compute and customer infrastructure."
    raw = (root/'source.html').read_bytes() + ('<p>'+quote+'</p>').encode()
    (root/'source.html').write_bytes(raw)
    data['sources'][0]['sha256'] = hashlib.sha256(raw).hexdigest()
    data['legal_name'] = name
    data['nodes'][0]['label'] = name
    data['relationships'][-1]['type'] = 'AFFECTS_DEMAND'
    data['relationships'][-1]['from_id'] = 'f'
    data['routing_policies'] = [{'narrative_id':'n', 'intents':['DEMAND'], 'scope_note':'Synthetic demand scope'}]
    data['factor_bindings'] = [dict(id='access',factor_id='f',topic_terms=['compute'],context_terms=['access'],
        change_terms=['restrictions'],kind='SCOPED_ACTIVITY',access_constraint={'company_terms':[name]},
        narrative_ids=['n'],scope='Synthetic sourced access scope',reviewed_at=data['available_at'],
        review_until=(datetime.now(UTC)+timedelta(days=20)).isoformat(),evidence=[{'source_id':'s','quote':quote}])]
    seal(root,data)
    return root, data, load_bundle(root)


@pytest.mark.parametrize('name',['Orion','Cobalt'])
@pytest.mark.parametrize('template,expected',[
    ('{n} GPU sellers face rules that restrict remote access to AI chips.',True),
    ('{n} chip buyers told to rule out restricted renters to purchase GPUs.',True),
    ('{n} GPU sellers seek buyers as regulators curb AI chip access.',True),
    ('{n} GPU buyers face rules that will restrict access to compute.',True),
    ('{n} GPU buyers might restrict access to compute.',False),
    ('{n} did not restrict access to compute.',False),
    ('An analyst at {n} discusses rules that restrict access to compute.',False),
    ('{n} chip launch continues while regulators restrict access to compute.',False),
    ('{n} chip buyers discuss restrictions on building access.',False),
    ('{n} GPU buyers face rules that restrict access to buildings.',False),
    ('{n} GPU buyers speak and regulators restrict access to compute.',False),
])
def test_access_scope_through_sourced_graph(dossier,name,template,expected):
    _, _, b = configured(dossier,name)
    text = template.format(n=name)
    at=datetime.now(UTC)
    links=list(binding_decisions(b,b.narratives[0],{'title':text},at))
    assert bool(links)==expected
    if expected:
        result=assess({'headline':text,'excerpt':''},[{'matches':links[0]['matches']}],json.loads(POLICY.read_text()))
        assert result['signals'][0]['event_type']=='ACCESS_RESTRICTION'
        assert result['direction']==result['horizon']=='UNKNOWN'
        event=links[0]['matches'][0]['activity_assertion']
        assert not event['legal_status_verified'] and not event['identity_verified']
        for key in ['action_span','object_span','company_span']:
            span=event[key]
            assert text[span['start']:span['end']]==span['text']


def test_access_does_not_invent_supply_paths_or_cross_fields(dossier):
    _,data,b=configured(dossier,'Orion')
    at=datetime.now(UTC)
    assert not matches(b.factor_bindings[0],{'title':'Orion GPU buyers','summary':'Regulators restrict access to compute.'})
    data['routing_policies'][0]['intents']=['SUPPLY']
    b=ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b,b.narratives[0],{'title':'Orion GPU buyers face rules that restrict access to compute.'},at))
    data['routing_policies'][0]['intents']=['DEMAND']
    data['relationships'][-1]['status']='REVOKED'
    b=ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b,b.narratives[0],{'title':'Orion GPU buyers face rules that restrict access to compute.'},at))


def test_access_requires_sourced_company_scope(dossier):
    _,data,_=configured(dossier,'Orion')
    data['factor_bindings'][0]['access_constraint']['company_terms']=['Invented']
    with pytest.raises(ValueError):
        ProfileBundle.model_validate(data)


def test_access_cannot_override_other_matcher_guards(dossier):
    _,data,_=configured(dossier,'Orion')
    data['factor_bindings'][0]['market_scope']='APPLICATION_SOFTWARE'
    with pytest.raises(ValueError, match='Access constraint'):
        ProfileBundle.model_validate(data)


def test_access_alias_cannot_include_another_sourced_company(dossier):
    _,data,_=configured(dossier,'Orion')
    b=data['factor_bindings'][0]
    b['evidence'][0]['quote']+=' Competitor Cobalt also sells compute.'
    b['access_constraint']['company_terms'].append('Cobalt')
    with pytest.raises(ValueError, match='profile company'):
        ProfileBundle.model_validate(data)
