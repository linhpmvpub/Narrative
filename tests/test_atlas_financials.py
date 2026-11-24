import hashlib
import sqlite3
from datetime import UTC, datetime

import pytest
from test_company_profiles import QUOTE, seal
from test_company_profiles import dossier as dossier

from engine.atlas_financials import FinancialSelection, extract_selection
from engine.impact_atlas import install, snapshot


def document():
    contexts = []
    for id, member in [('total',None),('a','co:AMember'),('b','co:BMember')]:
        dim = f'<xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">{member}</xbrldi:explicitMember>' if member else ''
        contexts.append(f'<xbrli:context id="{id}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier><xbrli:segment>{dim}</xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2023-10-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate></xbrli:period></xbrli:context>')
    facts = ''.join(f'<ix:nonFraction id="{id}" name="us-gaap:Revenues" contextRef="{ctx}" unitRef="usd" scale="6" decimals="-6">{v}</ix:nonFraction>' for id,ctx,v in [('f1','total',100),('f2','a',60),('f3','b',40)])
    return (f'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:us-gaap="http://fasb.org/us-gaap/2026" xmlns:iso4217="http://www.xbrl.org/2003/iso4217"><body><p>{QUOTE}</p>{"".join(contexts)}<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>{facts}</body></html>').encode()


def selection():
    return {'id':'synthetic-mix','version':1,'profile_id':'example','source_id':'example/s','cik':'1',
        'kind':'REPORTABLE_SEGMENTS','total':{'fact_id':'f1','context_id':'total','label':'Total','dimensions':{}},
        'parts':[{'fact_id':'f2','context_id':'a','label':'A','dimensions':{'us-gaap:StatementBusinessSegmentsAxis':'co:AMember'}},
                 {'fact_id':'f3','context_id':'b','label':'B','dimensions':{'us-gaap:StatementBusinessSegmentsAxis':'co:BMember'}}],
        'reviewed_at':datetime.now(UTC).isoformat(),'reviewer_id':'test','reviewer_kind':'AI_OPERATOR','scope':'Synthetic only'}


def test_scaled_source_cells_and_mix_persist_without_becoming_weights(dossier,tmp_path):
    root,d = dossier
    blob = document()
    (root/'source.html').write_bytes(blob)
    d['sources'][0]['sha256'] = hashlib.sha256(blob).hexdigest()
    d['identifiers'] = {'CIK':'1'}
    seal(root,d)
    data = snapshot(root.parent,financials=[selection()])
    row = data['financial_context'][0]
    assert row['total']['value_usd']=='100000000'
    assert row['parts'][0]['share_of_total']=='0.6'
    assert row['impact_weight'] is None and row['inventory_buffer_days'] is None
    install(data,tmp_path/'export')
    with sqlite3.connect(tmp_path/'export/atlas.db') as db:
        assert db.execute('select count(*) from financial_context').fetchone()[0]==1
        assert db.execute('pragma foreign_key_check').fetchall()==[]


@pytest.mark.parametrize('fault',['period','axis','issuer','unit','scale','sum','duplicate_id','hidden',
                                  'wrong_context','duplicate_member','namespace','empty_reviewer'])
def test_financial_context_rejects_misaligned_or_ambiguous_cells(fault):
    blob = document().decode()
    s = selection()
    if fault=='period':
        blob = blob.replace('<xbrli:startDate>2023-10-01', '<xbrli:startDate>2023-07-01',1)
    elif fault=='axis':
        s['parts'][0]['dimensions']={'srt:ProductOrServiceAxis':'co:AMember'}
    elif fault=='issuer':
        s['cik']='2'
    elif fault=='unit':
        blob=blob.replace('iso4217:USD','iso4217:EUR')
    elif fault=='scale':
        blob=blob.replace('scale="6"','scale="99"',1)
    elif fault=='sum':
        blob=blob.replace('>60</ix:nonFraction>','>61</ix:nonFraction>')
    elif fault=='duplicate_id':
        blob=blob.replace('id="f3"','id="f2"')
    elif fault=='hidden':
        blob=blob.replace('<ix:nonFraction id="f1"','<ix:hidden><ix:nonFraction id="f1"').replace('</ix:nonFraction>','</ix:nonFraction></ix:hidden>',1)
    elif fault=='wrong_context':
        s['parts'][0]['context_id']='b'
    elif fault=='duplicate_member':
        s['parts']=[s['parts'][0],s['parts'][0]]
    elif fault=='namespace':
        blob=blob.replace('http://fasb.org/us-gaap/2026','https://example.test/fake')
    else:
        s['reviewer_id']='   '
    with pytest.raises(ValueError):
        extract_selection(blob.encode(),FinancialSelection.model_validate(s),datetime(2024,1,1,tzinfo=UTC))


def test_inventory_is_instant_balance_not_revenue_or_buffer():
    blob=document().decode().replace('us-gaap:Revenues','us-gaap:InventoryNet')
    blob=blob.replace('<xbrli:startDate>2023-10-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate>','<xbrli:instant>2023-12-31</xbrli:instant>',1)
    blob=blob.replace('<xbrli:startDate>2023-10-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate>','<xbrli:instant>2022-12-31</xbrli:instant>')
    blob=blob.replace('<xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">co:AMember</xbrldi:explicitMember>','')
    s=selection()
    s.update(kind='INVENTORY_BALANCE',parts=[],prior={'fact_id':'f2','context_id':'a','label':'Prior','dimensions':{}})
    row=extract_selection(blob.encode(),FinancialSelection.model_validate(s),datetime(2024,1,1,tzinfo=UTC))
    assert row['total']['instant']=='2023-12-31' and row['prior']['instant']=='2022-12-31'
    assert row['inventory_buffer_days'] is None
    s['prior']['fact_id']='f1'
    s['prior']['context_id']='total'
    with pytest.raises(ValueError):
        extract_selection(blob.encode(),FinancialSelection.model_validate(s),datetime(2024,1,1,tzinfo=UTC))


@pytest.mark.parametrize('fault',['profile_cik','future_review','foreign_source'])
def test_selection_provenance_bound_to_profile_and_review_time(dossier,fault):
    root,d=dossier
    blob=document()
    (root/'source.html').write_bytes(blob)
    d['sources'][0]['sha256']=hashlib.sha256(blob).hexdigest()
    d['identifiers']={'CIK':'2' if fault=='profile_cik' else '1'}
    seal(root,d)
    s=selection()
    if fault=='future_review':
        s['reviewed_at']='2999-01-01T00:00:00Z'
    if fault=='foreign_source':
        s['source_id']='other/s'
    with pytest.raises(ValueError,match='binding'):
        snapshot(root.parent,financials=[s])
