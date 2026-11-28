import json
from datetime import UTC, datetime

import pytest
from test_access_constraints import configured as access_profile
from test_company_profiles import dossier as dossier
from test_readiness_context import configured as resource_profile

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import ProfileBundle
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.profile_news import matches
from engine.profile_routing import binding_decisions
from engine.source_sentences import source_units


@pytest.mark.parametrize('name',['Orion','Cobalt'])
@pytest.mark.parametrize('kind',['party','asset'])
def test_typed_reference_original_spans_and_full_body_parity(dossier,name,kind):
    if kind=='party':
        _,_,b=access_profile(dossier,name)
        text=f'{name} GPU buyers face new rules. These buyers were told to rule out restricted renters to purchase GPUs.'
        key='activity_assertion'
    else:
        _,_,b=resource_profile(dossier,name=name)
        text=f'{name} announced a data center. The facility faces power constraints.'
        key='readiness_context'
    direct=matches(b.factor_bindings[0],{'summary':text})
    unit=matches(b.factor_bindings[0],list(source_units(text))[-1])
    assert direct and unit
    ref=direct[0][key]['source_reference']
    assert ref==unit[0][key]['source_reference']
    for span in [ref['antecedent'],ref['reference_span'],ref['window_span']]:
        assert text[span['start']:span['end']]==span['text']
    assert all(text[m['start']:m['end']]==m['text'] and m['context_only'] for m in direct)
    assert not ref['identity_verified'] and not ref['relationship_inferred']
    cards=list(article_decisions(b,b.narratives[0],'Update',[{'text':text,'source_spans':[]}],datetime.now(UTC)))
    assert cards and cards[0]['paragraph']==text
    assessment=assess({'headline':'Update','excerpt':text},[{'matches':direct}],json.loads(POLICY.read_text()))
    assert assessment['tier']=='BACKGROUND_THEME' and not assessment['signals']


@pytest.mark.parametrize('text',[
    'OtherVendor GPU buyers face rules. These buyers were told to rule out renters to purchase GPUs.',
    'Orion GPU sellers face rules. These buyers were told to rule out renters to purchase GPUs.',
    'Orion GPU buyers met Cobalt buyers. These buyers were told to rule out renters to purchase GPUs.',
    'Orion GPU buyers face rules. Unrelated update. These buyers were told to rule out renters to purchase GPUs.',
    'Orion GPU buyers face rules.\nThese buyers were told to rule out renters to purchase GPUs.',
    'Orion GPU buyers face rules; These buyers were told to rule out renters to purchase GPUs.',
    'Orion GPU buyers might face rules. These buyers were told to rule out renters to purchase GPUs.',
    'Orion GPU buyers face rules. These buyers speak while regulators restrict access to compute.',
    'Orion GPU buyers face rules. These buyers were not told to rule out renters to purchase GPUs.',
    'Orion GPU buyers face rules. These buyers face rules. These buyers were told to rule out renters to purchase GPUs.',
])
def test_party_reference_rejects_ambiguous_remote_or_negated_context(dossier,text):
    _,_,b=access_profile(dossier,'Orion')
    assert not matches(b.factor_bindings[0],{'summary':text})


@pytest.mark.parametrize('text',[
    'Orion announced a data center and a factory. The facility faces power constraints.',
    'Orion announced two data centers. The facility faces power constraints.',
    'Orion announced a food factory. The facility faces power constraints.',
    'Orion announced a data center software service. The facility faces power constraints.',
    'Orion announced a data center conference. The facility faces power constraints.',
    'Orion canceled a data center. The facility faces power constraints.',
    'Orion has no plans for a data center. The facility faces power constraints.',
    'Orion announced a data center.\nThe facility faces power constraints.',
    'Orion announced a data center. Another update. The facility faces power constraints.',
    'Orion announced a data center. The facility expands software capacity and power outages worsen.',
    'Orion announced a data center. The facility has no power constraints.',
])
def test_asset_reference_requires_unambiguous_physical_scope(dossier,text):
    _,_,b=resource_profile(dossier)
    assert not matches(b.factor_bindings[0],{'summary':text})


def test_no_title_donation_tampered_context_or_revoked_path(dossier):
    _,data,b=resource_profile(dossier)
    current='The facility faces power constraints.'
    assert not matches(b.factor_bindings[0],{'title':'Orion announced a data center.','summary':current})
    assert not matches(b.factor_bindings[0],{'summary':current,'source_context':'Orion announced a data center. Other text.','source_offset':30})
    text='Orion announced a data center. '+current
    data['relationships'][-1]['status']='REVOKED'
    b=ProfileBundle.model_validate(data)
    assert not list(binding_decisions(b,b.narratives[0],{'summary':text},datetime.now(UTC)))
