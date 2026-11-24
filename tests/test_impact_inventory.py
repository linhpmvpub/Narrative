import sqlite3
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import QUOTE, seal
from test_company_profiles import dossier as dossier
from test_impact_atlas import fact

from engine.impact_atlas import install, snapshot


def linked(dossier):
    root, data = dossier
    data['nodes'][0]['label'] = 'example company'
    data['entity_references'] = [{'id':'legal','label':'example company',
        'identity_level':'LEGAL_ENTITY','resolution':'EXACT_ENTITY','node_id':'co',
        'names':['example company'],'relationship_ids':['owns'],'scope':'Synthetic legal identity',
        'unknowns':['No automatic economic propagation'], 'reviewed_at':data['available_at'],
        'review_until':(datetime.now(UTC)+timedelta(days=1)).isoformat(),
        'evidence':[{'source_id':'s','quote':QUOTE}]}]
    seal(root,data)
    other = root.parent/'second'
    other.mkdir()
    (other/'source.html').write_bytes((root/'source.html').read_bytes())
    second = deepcopy(data)
    second['id'] = 'second'
    seal(other,second)
    group = {'id':'example-identity','version':1,'legal_name':'example company',
        'references':['example/legal','second/legal'],'reviewed_at':datetime.now(UTC).isoformat(),
        'reviewer_id':'test','reviewer_kind':'AI_OPERATOR','scope':'Navigation only'}
    return root, other, data, second, group


def test_identity_links_persist_without_merging_nodes_or_edges(dossier, tmp_path):
    root, _, _, _, group = linked(dossier)
    data = snapshot(root.parent,identities=[group])
    assert len(data['nodes']) == 8 and len(data['relations']) == 6
    assert not data['identity_groups'][0]['automatic_cross_profile_propagation']
    output = tmp_path/'export'
    install(data,output)
    with sqlite3.connect(output/'atlas.db') as db:
        assert db.execute('select count(*) from identity_members').fetchone()[0] == 2
        assert db.execute('pragma foreign_key_check').fetchall() == []


@pytest.mark.parametrize('fault',['parent','expired','revoked','future','duplicate','unknown','earlier_review','inactive_edge','wrong_name','blank_reviewer'])
def test_identity_group_rejects_unsupported_connections(dossier, fault):
    root, other, data, second, group = linked(dossier)
    ref = second['entity_references'][0]
    if fault == 'parent':
        ref.update(identity_level='GROUP',resolution='CONTEXT_ONLY')
    elif fault == 'expired':
        ref['review_until'] = (datetime.now(UTC)-timedelta(minutes=1)).isoformat()
    elif fault == 'revoked':
        ref['status'] = 'REVOKED'
    elif fault == 'future':
        group['reviewed_at'] = (datetime.now(UTC)+timedelta(days=1)).isoformat()
    elif fault == 'duplicate':
        group['references'][1] = 'example/legal'
    elif fault == 'unknown':
        group['references'][1] = 'second/missing'
    elif fault == 'earlier_review':
        group['reviewed_at'] = '2024-01-01T00:00:00Z'
    elif fault == 'wrong_name':
        group['legal_name'] = 'example company holdings'
    elif fault == 'blank_reviewer':
        group['reviewer_id'] = '   '
    else:
        second['relationships'][0]['status'] = 'CANDIDATE'
    seal(other,second)
    with pytest.raises(ValueError):
        snapshot(root.parent,identities=[group])


def test_names_do_not_auto_link_and_missing_fields_never_pool(dossier):
    root, _, _, _, _ = linked(dossier)
    one = fact(dossier)
    two = {**one,'id':'other','relation_id':'example/applies','dimension':'inventory_days','unit':'days',
           'value':'10','period_label':'Synthetic point in time','measurement_basis':'Synthetic buffer',
           'precision':'EXACT_REPORTED'}
    data = snapshot(root.parent,facts=[one,two])
    assert data['identity_groups'] == []
    rows = {r['relation_id']:r for r in data['field_inventory'] if r['mechanism_id']=='supply_disruption'}
    assert 'inventory_days' in rows['example/owns']['missing']
    assert 'substitutability' in rows['example/applies']['missing']
    assert all(r['strength']=='UNKNOWN' and r['applicability']=='NOT_ASSESSED' and r['period_alignment']=='NOT_ASSESSED' for r in rows.values())


def test_inactive_relation_facts_do_not_fill_field_inventory(dossier):
    root, data = dossier
    data['relationships'][0]['status'] = 'CANDIDATE'
    seal(root,data)
    result = snapshot(root.parent,facts=[fact(dossier)])
    assert all(not r['present'] for r in result['field_inventory'])
