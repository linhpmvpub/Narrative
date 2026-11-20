"""Offline sanity checks for the Codex handoff pack (not engine tests)."""
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
def read(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))
def test_package_integrity():
    stocks=read('config/stocks.json')
    entities=read('config/entities.json')
    narratives=read('config/narratives.json')
    edges=read('config/relationships.json')
    cases=read('tests/golden_cases.json')
    contracts=read('schemas/json_contracts.json')
    demo=read('fixtures/demo_verified_relationships.json')
    events=[json.loads(x) for x in (ROOT/'fixtures/events.jsonl').read_text(encoding='utf-8').splitlines() if x]
    assert len(stocks)==5
    assert {s['ticker'] for s in stocks}=={'MU','NVDA','AMD','DELL','SNDK'}
    assert len(narratives)==10
    assert dict(Counter(n['primary_ticker'] for n in narratives)) == {'MU':2,'NVDA':2,'AMD':2,'DELL':2,'SNDK':2}
    assert len(edges)==40 and all(e['status']=='candidate' and e['confidence']==0 and e['strength'] is None for e in edges)
    assert 'EventExtraction' in contracts['$defs'] and 'DecisionTrace' in contracts['$defs']
    graph={(e['from_entity'], e['to_entity']):e['relation_id'] for e in edges}
    assert graph[('NAND_ASP','SERVER_COMPONENT_COST')]=='R026'
    assert graph[('SERVER_COMPONENT_COST','DELL_ISG_MARGIN')]=='R027'
    ent_ids={e['entity_id'] for e in entities}
    assert len(ent_ids)==len(entities)
    assert all(e['from_entity'] in ent_ids and e['to_entity'] in ent_ids for e in edges)
    assert all(f'CO_{s["ticker"]}' in ent_ids for s in stocks)
    assert {n['narrative_id'] for n in narratives if n['hypothesis_polarity_for_company']=='adverse'}=={'N02','N04','N08'}
    for n in narratives:
        assert n['driver_ids'] and n['supporting_evidence'] and n['challenging_evidence'] and n['disconfirmation']
        assert all(d in ent_ids for d in n['driver_ids'] + n['watch_entities'])
        assert n['scope']['max_hops']==2
        assert n['hypothesis_polarity_for_company'] in {'favorable','adverse'}
    assert all(e['is_synthetic'] is True and e['source_url'].startswith('fixture://') for e in events)
    assert demo['is_synthetic'] and demo['never_use_in_live'] and len(demo['edges'])==len(edges)
    assert len(events)>=30 and len(cases)>=20
    ids={e['event_id'] for e in events}
    assert len(ids)==len(events)
    assert sum(e['canonical_event_key']=='SYN-F001' for e in events)==2
    assert sum(e['canonical_event_key']=='SYN-F017' for e in events)==2
    assert 'CO_WDC' not in ent_ids
    assert stocks[-1]['independent_from']=='2025-02-21'
    print(f'PASS: {len(stocks)} stocks, {len(entities)} entities, {len(narratives)} narratives, {len(edges)} candidate relations, {len(events)} synthetic event fixtures, {len(cases)} golden cases.')

if __name__=='__main__':
    test_package_integrity()
