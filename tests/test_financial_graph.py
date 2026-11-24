import hashlib
from datetime import UTC, datetime

import pytest
from test_atlas_financials import document, selection
from test_company_profiles import QUOTE, seal
from test_company_profiles import dossier as dossier

from engine.impact_atlas import Scenario, scenario, snapshot


def prepared(dossier):
    root,d=dossier
    blob=document()
    (root/'source.html').write_bytes(blob)
    d['sources'][0]['sha256']=hashlib.sha256(blob).hexdigest()
    d['identifiers']={'CIK':'1'}
    seal(root,d)
    financial=selection()
    binding={'id':'synthetic-scope','version':1,'node_id':'example/p',
        'financial_id':financial['id'],'fact_id':'f2','relationship':'SUBSET_OF_BUCKET',
        'scope':'Synthetic reviewed scope only','reviewed_at':datetime.now(UTC).isoformat(),
        'reviewer_id':'test','reviewer_kind':'AI_OPERATOR','evidence':[{'source_id':'example/s','quote':QUOTE}]}
    return root,financial,binding


def test_financial_layer_never_extends_routes_or_assigns_product_share(dossier):
    root,f,b=prepared(dossier)
    data=snapshot(root.parent,financials=[f],bindings=[b])
    assert len(data['financial_graph']['nodes'])==2
    assert len(data['financial_graph']['relations'])==3
    assert len(data['nodes'])==4 and len(data['relations'])==3
    assert data['financial_bindings'][0]['affected_revenue_share'] is None
    assert not data['financial_bindings'][0]['causal_routing']
    bucket=data['financial_graph']['nodes'][0]
    assert bucket['share_of_total']=='0.6' and bucket['impact_weight'] is None
    with pytest.raises(ValueError,match='Factor'):
        scenario(data,Scenario(mechanism_id='demand',factor_id=bucket['id'],direction='UP',phase='OPERATING',scope='test'))


@pytest.mark.parametrize('fault',['unknown_node','wrong_cell','future','old_review','quote','foreign_source','duplicate','blank_reviewer'])
def test_scope_binding_fails_closed(dossier,fault):
    root,f,b=prepared(dossier)
    if fault=='unknown_node':
        b['node_id']='other/p'
    elif fault=='wrong_cell':
        b['fact_id']='f1'
    elif fault=='future':
        b['reviewed_at']='2999-01-01T00:00:00Z'
    elif fault=='old_review':
        b['reviewed_at']='2024-01-01T00:00:00Z'
    elif fault=='quote':
        b['evidence'][0]['quote']='Invented claim'
    elif fault=='foreign_source':
        b['evidence'][0]['source_id']='other/s'
    elif fault=='blank_reviewer':
        b['reviewer_id']='   '
    bindings=[b,b] if fault=='duplicate' else [b]
    with pytest.raises(ValueError):
        snapshot(root.parent,financials=[f],bindings=bindings)
