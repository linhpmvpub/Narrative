"""Account isolation, conflict handling and relevance-only personalized ordering."""
import pytest
from test_article_feed import configured as configured
from test_article_feed import recheck
from test_article_relevance import selection as selection
from test_company_profiles import dossier as dossier
from test_product import client as client
from test_product import headers
from test_product import identities as identities
from test_profile_news import linked as linked
from test_profile_relevance import separate_profile_store as separate_profile_store

from engine.article_preferences import personalize

URL = '/api/v0/news/article-preferences'


def body(**changes):
    return {'expected_version': 0, 'tickers': ['TEST'], 'narratives': [],
            'following_only': True, 'include_archive': True, **changes}


def test_save_persists_per_user_not_tenant_and_handles_retries(client, identities, configured):
    first, same_tenant, other_tenant, _ = identities
    h = headers(first)
    assert client.get(URL, headers=h).json()['version'] == 0
    response = client.put(URL, headers=h, json=body())
    assert response.status_code == 200 and response.json()['version'] == 1
    assert client.put(URL, headers=h, json=body()).json() == response.json()
    assert client.put(URL, headers=h, json=body(tickers=[])).status_code == 409
    assert client.put(URL, headers=headers(first), json=body()).status_code == 409
    assert client.get(URL, headers=headers(first)).json()['tickers'] == ['TEST']
    for person in [same_tenant, other_tenant]:
        data = client.get(URL, headers=headers(person)).json()
        assert data['version'] == 0 and data['tickers'] == []
    assert client.put(URL, headers=headers(first), json=body(expected_version=1,tickers=[])).status_code == 200


@pytest.mark.parametrize('changes', [{'user_id':'other'}, {'tenant_id':'other'},
    {'tickers':['UNKNOWN']}, {'narratives':['other:private']}, {'following_only':'true'},
    {'tickers':['TEST']*11}])
def test_reject_identity_injection_unknown_targets_and_unbounded_data(client, identities, configured, changes):
    assert client.put(URL, headers=headers(identities[0]), json=body(**changes)).status_code == 422
    assert client.get(URL, headers=headers(identities[0])).json()['version'] == 0


def test_auth_required(client, configured):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json=body()).status_code == 401


def test_preferences_do_not_bypass_source_hold(db, client, identities, configured):
    recheck(db, configured[1])
    h = headers(identities[0])
    assert client.put(URL, headers=h, json=body()).status_code == 200
    assert len(client.get('/api/v0/news/profile-articles', headers=h).json()['items']) == 1
    recheck(db, configured[1]+b'<p>This article has been withdrawn.</p>')
    assert not client.get('/api/v0/news/profile-articles', headers=h).json()['items']


def test_priority_is_explainable_deterministic_and_not_impact():
    base={'profile_id':'p','narrative_id':'n','ticker':'A','coverage':'INDUSTRY_CONTEXT',
          'freshness':'WITHIN_RULE_WINDOW','published_at':'2026-11-24T00:00:00Z',
          'impact':'UNKNOWN','delivery':'disabled'}
    result={'items':[dict(base,id='discovery'),dict(base,id='company',ticker='B'),
                     dict(base,id='narrative',narrative_id='chosen',freshness='ARCHIVE_CONTEXT')]}
    prefs={'version':1,'tickers':['B'],'narratives':['p:chosen'],'following_only':False,'include_archive':True}
    ranked=personalize(result,prefs)
    assert [c['id'] for c in ranked['items']]==['narrative','company','discovery']
    assert ranked['items'][0]['priority_reason']=='NARRATIVE_FOLLOWED'
    assert all(c['impact']=='UNKNOWN' and c['delivery']=='disabled' for c in ranked['items'])
    assert 'personal_priority' not in result['items'][0]
    assert [c['id'] for c in personalize(result,{**prefs,'following_only':True,'include_archive':False})['items']]==['company']
    assert not personalize(result,{**prefs,'following_only':True,'tickers':[],'narratives':[]})['items']
