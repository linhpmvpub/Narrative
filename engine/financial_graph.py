"""Financial reporting layer and reviewed scope links; excluded from causal routing."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from engine.company_profiles import source_text
from engine.impact_atlas import FactEvidence


class FinancialBinding(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str = Field(pattern=r'^[A-Za-z0-9_.:-]{1,100}$')
    version: int = Field(ge=1)
    node_id: str
    financial_id: str
    fact_id: str
    relationship: Literal['SUBSET_OF_BUCKET', 'CONTAINS_BUCKET']
    scope: str = Field(min_length=1, max_length=2000)
    reviewed_at: AwareDatetime
    reviewer_id: str = Field(min_length=1, max_length=200)
    reviewer_kind: Literal['AI_OPERATOR', 'HUMAN']
    evidence: list[FactEvidence] = Field(min_length=1, max_length=10)


def project_financial_graph(data, bindings, profile_root, bundles, at):
    if len(bindings) > 500:
        raise ValueError('Bounded financial bindings required')
    nodes = {n['id']: n for n in data['nodes']}
    profiles = {p['id']: p for p in data['profiles']}
    financials = {f['id']: f for f in data['financial_context']}
    projected, edges, cells = [], [], {}
    for f in financials.values():
        if not f['parts']:
            continue
        for part in f['parts']:
            id = f['profile_id']+'/reporting/'+f['id']+'/'+part['fact_id']
            cells[(f['id'],part['fact_id'])] = id
            projected.append({'id':id,'profile_id':f['profile_id'],'kind':'reporting_bucket',
                'label':part['label'],'financial_id':f['id'],'fact_id':part['fact_id'],
                'source_id':f['source_id'],'period_start':part['period_start'],'period_end':part['period_end'],
                'value_usd':part['value_usd'],'share_of_total':part['share_of_total'],
                'classification':f['kind'],'role':part['role'],'impact_weight':None})
            edges.append({'id':id+'/reported','profile_id':f['profile_id'],
                'from_id':profiles[f['profile_id']]['company_id'],'to_id':id,'type':'REPORTED_REVENUE_PART',
                'family':'FINANCIAL','scope':f['scope'],'financial_id':f['id'],
                'eligible_at_snapshot':True,'evidence':[],'causal_routing':False})
    registry = {b.id:b for b in bundles}
    dirs = {json.loads((p/'current.json').read_text(encoding='utf-8'))['id']:p
            for p in Path(profile_root).iterdir() if p.is_dir() and (p/'current.json').exists()}
    used, pairs, output = set(), set(), []
    for raw in bindings:
        binding = FinancialBinding.model_validate(raw)
        f, n = financials.get(binding.financial_id), nodes.get(binding.node_id)
        target = cells.get((binding.financial_id,binding.fact_id))
        if (f is None or n is None or target is None or n['profile_id'] != f['profile_id']
                or n['kind'] not in {'product','segment'} or binding.id in used
                or (binding.node_id,target) in pairs or binding.reviewed_at > at
                or binding.reviewed_at < datetime.fromisoformat(f['reviewed_at'])):
            raise ValueError('Invalid financial scope binding identity/time')
        part = next(p for p in f['parts'] if p['fact_id']==binding.fact_id)
        if part['role'] != 'PART':
            raise ValueError('Reconciliation is not product scope')
        bundle = registry[f['profile_id']]
        if binding.reviewed_at < bundle.available_at:
            raise ValueError('Binding predates profile')
        sources = {bundle.id+'/'+s.id:s for s in bundle.sources}
        for e in binding.evidence:
            source = sources.get(e.source_id)
            if source is None or source.retrieved_at > binding.reviewed_at:
                raise ValueError('Invalid binding evidence source/time')
            directory = dirs[bundle.id].resolve()
            path = (directory/source.file).resolve()
            if not path.is_relative_to(directory):
                raise ValueError('Invalid binding source path')
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest()!=source.sha256 or e.quote not in source_text(body):
                raise ValueError('Unsupported financial binding quote')
        used.add(binding.id)
        pairs.add((binding.node_id,target))
        row = {**binding.model_dump(mode='json'),'bucket_node_id':target,
               'affected_revenue_share':None,'impact_weight':None,'causal_routing':False,
               'scope_status':'OPERATOR_REVIEWED_NOT_INDEPENDENTLY_VERIFIED'}
        output.append(row)
        edges.append({'id':'binding/'+binding.id,'profile_id':f['profile_id'],
            'from_id':binding.node_id,'to_id':target,'type':binding.relationship,'family':'FINANCIAL',
            'scope':binding.scope,'financial_id':f['id'],'eligible_at_snapshot':True,
            'evidence':row['evidence'],'binding':row,'causal_routing':False})
    data['financial_bindings'] = output
    data['financial_graph'] = {'nodes':projected,'relations':edges,
        'purpose':'REPORTING_SCOPE_ONLY_NOT_CAUSAL_GRAPH','automatic_share_propagation':False}
