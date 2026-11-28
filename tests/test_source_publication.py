from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from test_atlas_financials import document, selection
from test_company_profiles import dossier as dossier
from test_company_profiles import seal

from engine.company_profiles import ProfileBundle, Source, load_bundle, paths, project
from engine.impact_atlas import snapshot


def undated(dossier):
    root,data=dossier
    source=deepcopy(data['sources'][0])
    source.update(id='u',published_at=None,unknown_publication={
        'source_kind':'OFFICIAL_PRODUCT_PAGE','basis':'NO_PUBLICATION_DATE',
        'review_note':'Synthetic official product page has no original publication date.'})
    data['sources'].append(source)
    relation=data['relationships'][1]
    relation.update(valid_from=source['retrieved_at'],known_at=source['retrieved_at'])
    relation['evidence']=[{**e,'source_id':'u'} for e in relation['evidence']]
    seal(root,data)
    return root,data


def test_legacy_source_serialization_stays_identical(dossier):
    source=dossier[1]['sources'][0]
    model=Source.model_validate(source)
    assert 'unknown_publication' not in model.model_dump(mode='json')
    assert model.published_at is not None


@pytest.mark.parametrize('fault',['missing_metadata','fake_date','bad_kind','future_display','display_without_basis'])
def test_unknown_publication_requires_explicit_nonfinancial_scope(dossier,fault):
    _,data=undated(dossier)
    source=data['sources'][-1]
    if fault=='missing_metadata':
        source.pop('unknown_publication')
    elif fault=='fake_date':
        source['published_at']=source['retrieved_at']
    elif fault=='bad_kind':
        source['unknown_publication']['source_kind']='SEC_FILING'
    elif fault=='future_display':
        source['unknown_publication'].update(basis='DISPLAYED_UPDATE_NOT_ORIGINAL',displayed_date='2099-01-01')
    else:
        source['unknown_publication']['displayed_date']='2020-01-01'
    with pytest.raises(ValueError):
        Source.model_validate(source)


def test_display_date_is_not_original_publication(dossier):
    _,data=undated(dossier)
    source=data['sources'][-1]
    source['unknown_publication'].update(basis='DISPLAYED_UPDATE_NOT_ORIGINAL',displayed_date='2020-01-01')
    model=Source.model_validate(source)
    assert model.published_at is None
    assert model.unknown_publication.displayed_date.isoformat()=='2020-01-01'


@pytest.mark.parametrize('field',['valid_from','known_at'])
def test_relationship_cannot_precede_undated_source_capture(dossier,field):
    _,data=undated(dossier)
    data['relationships'][1][field]='2020-01-01T00:00:00Z'
    with pytest.raises(ValueError,match='cannot backdate'):
        ProfileBundle.model_validate(data)


def test_undated_relationship_only_routes_after_capture_and_public_metadata_survives(dossier):
    root,data=undated(dossier)
    b=load_bundle(root)
    at=datetime.fromisoformat(data['available_at'])
    event=SimpleNamespace(anchors=['f'])
    assert not paths(b,event,b.narratives[0],effective_at=at-timedelta(seconds=1))[0]
    assert paths(b,event,b.narratives[0],effective_at=at)[0]
    shown=next(s for s in project(b)['sources'] if s['id']=='u')
    assert shown['published_at'] is None and shown['unknown_publication']['basis']=='NO_PUBLICATION_DATE'
    atlas=snapshot(root.parent)
    source=next(s for s in atlas['sources'] if s['id']=='example/u')
    assert source['published_at'] is None


def test_undated_source_cannot_backfill_event(dossier):
    _,data=undated(dossier)
    data['events'][0]['evidence']=deepcopy(data['events'][0]['evidence'])
    data['events'][0]['evidence'][0]['source_id']='u'
    with pytest.raises(ValueError,match='Dated events'):
        ProfileBundle.model_validate(data)


def test_undated_source_cannot_supply_financial_extraction(dossier):
    import hashlib

    root,data=undated(dossier)
    raw=document()
    (root/'source.html').write_bytes(raw)
    for source in data['sources']:
        source['sha256']=hashlib.sha256(raw).hexdigest()
    data['identifiers']={'CIK':'1'}
    seal(root,data)
    chosen=selection()
    chosen['source_id']='example/u'
    with pytest.raises(ValueError,match='dated disclosure'):
        snapshot(root.parent,financials=[chosen])


def test_metric_observation_requires_dated_evidence(dossier):
    _,data=undated(dossier)
    data['observations']=[{'id':'o','node_id':'m','value':'10','unit':'USD',
        'period_start':'2023-01-01','period_end':'2023-12-31','scope':'Synthetic',
        'basis':'GAAP','evidence':[{'source_id':'u','quote':data['sources'][0]['id']}]}]
    with pytest.raises(ValueError,match='Dated events and metric observations'):
        ProfileBundle.model_validate(data)

