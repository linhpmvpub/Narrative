import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_market_developments import setup
from test_profile_news import get
from test_profile_news import linked as linked

from engine.company_profiles import ProfileBundle, withdraw
from engine.infrastructure_scope import assess
from engine.market_developments import classify
from engine.profile_news import matches
from engine.profile_routing import binding_decisions


def scoped(linked, own="Orion", peer="Cobalt"):
    root, data = setup(linked)
    data['legal_name'] = own
    data['nodes'][0]['label'] = own
    quote = f"{own} sells infrastructure systems and competes with {peer}."
    evidence = {'source_id': 's', 'quote': quote}
    raw = (root/'source.html').read_bytes() + ('<p>'+quote+'</p>').encode()
    (root/'source.html').write_bytes(raw)
    data['sources'][0]['sha256'] = hashlib.sha256(raw).hexdigest()
    data['nodes'].append({'id': 'peer', 'kind': 'company', 'label': peer})
    data['relationships'].append({**data['relationships'][0], 'id': 'peer-edge',
        'type': 'COMPETES_WITH', 'from_id': 'peer', 'to_id': 'p', 'evidence': [evidence]})
    binding = data['factor_bindings'][0]
    binding['evidence'].append(evidence)
    binding['infrastructure_scope'] = {'own_names': [own], 'competitors': [
        {'names': [peer], 'relationship_id': 'peer-edge'}]}
    return root, data


@pytest.mark.parametrize('own,peer', [('Orion','Cobalt'), ('Aspen','Zephyr')])
@pytest.mark.parametrize('text,allowed', [
    ('An operator plans a new data center.', True),
    ('{own} opens a new data center.', True),
    ('{peer} opens a new data center.', True),
    ('{peer} and Atlas Systems are working with a university on its expanding AI infrastructure footprint.', False),
    ('{own} and {peer} are working with a university on its expanding AI infrastructure footprint.', True),
    ('An operator builds a data center powered by {peer} GPUs.', False),
    ('An operator builds a data center powered by {own} GPUs.', True),
    ('An operator builds a data center powered by Uncatalogued GPUs.', False),
    ('{own} builds a data center powered by {peer} GPUs.', False),
    ('{own} builds offices and {peer} opens a new data center.', True),
    ('An operator opens a data center while {peer} sells GPUs.', True),
    ('A researcher at {peer} discusses plans to build a new data center.', True),
])
def test_source_roles_with_renamed_companies(linked, own, peer, text, allowed):
    _, data = scoped(linked, own, peer)
    b = ProfileBundle.model_validate(data)
    source = text.format(own=own, peer=peer)
    d = classify(source)
    assert d
    trace = assess(b.factor_bindings[0].infrastructure_scope, d, b, datetime.now(UTC))
    assert trace['allowed'] is allowed
    assert trace['actor_identity'] == trace['financial_impact'] == 'UNKNOWN'
    for p in trace.get('own_participants',[]) + trace.get('other_participants',[]):
        s = p['span']
        assert source[s['start']:s['end']] == s['text']


def test_field_boundary_and_next_valid_sentence(db, linked):
    root, data = scoped(linked)
    b = ProfileBundle.model_validate(data)
    binding = b.factor_bindings[0]
    now = datetime.now(UTC)
    bad = 'An operator builds a new data center powered by Cobalt GPUs.'
    assert not matches(binding, {'title': 'Orion infrastructure', 'summary': bad}, bundle=b, at=now)
    text = bad + ' An operator plans a new data center.'
    spans = matches(binding, {'summary': text}, bundle=b, at=now)
    assert spans and all(s['start'] > len(bad) for s in spans)
    routed = list(binding_decisions(b, b.narratives[0], {'summary': text}, now))
    assert routed[0]['matches'][0]['routing_contract']['infrastructure_scope']['reason'] == 'GENERIC_MARKET_NOT_VENDOR_PROOF'
    seal(root, data)
    linked[2](title='Infrastructure', summary=text)
    assert get(db)['items'] and get(db)['delivery'] == 'disabled'
    linked[2](title='Infrastructure corrected', summary=bad)
    assert not get(db)['items']
    withdraw(root)
    assert not get(db)['items']


@pytest.mark.parametrize('fault', ['names','edge','own','unrelated'])
def test_sourced_profile_scope_required(linked, fault):
    _, data = scoped(linked)
    scope = data['factor_bindings'][0]['infrastructure_scope']
    if fault == 'names':
        scope['competitors'][0]['names'] = ['Invented']
    elif fault == 'edge':
        scope['competitors'][0]['relationship_id'] = 'absent'
    elif fault == 'own':
        scope['own_names'] = ['Cobalt']
        scope['competitors'] = []
    else:
        data['nodes'].append({'id': 'unrelated', 'kind': 'company', 'label': 'Unrelated'})
        data['relationships'][-1]['to_id'] = 'unrelated'
    with pytest.raises(ValueError):
        ProfileBundle.model_validate(data)


def test_expired_scope_and_missing_context_fail_closed(linked):
    _, data = scoped(linked)
    b = ProfileBundle.model_validate(data)
    binding = b.factor_bindings[0]
    text = {'summary': 'An operator opens a new data center.'}
    assert not matches(binding, text)
    data['relationships'][-1]['valid_until'] = (datetime.now(UTC)-timedelta(seconds=1)).isoformat()
    b = ProfileBundle.model_validate(data)
    assert not matches(b.factor_bindings[0], text, bundle=b, at=datetime.now(UTC))
