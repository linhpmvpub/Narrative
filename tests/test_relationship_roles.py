from datetime import UTC, datetime, timedelta

from test_company_profiles import dossier as dossier

from engine.company_profiles import ProfileBundle
from engine.relationship_roles import roles


def test_roles_are_nonexclusive_directional_and_source_scoped(dossier):
    _, data = dossier
    template = data['relationships'][0]
    data['nodes'].append({'id': 'peer', 'kind': 'company', 'label': 'Peer'})
    for key, kind in [('buys', 'BUYS'), ('supplies', 'SUPPLIES'), ('competes', 'COMPETES_WITH')]:
        data['relationships'].append({**template, 'id': key, 'type': kind, 'from_id': 'peer', 'to_id': 'p'})
    b = ProfileBundle.model_validate(data)
    at = datetime.now(UTC)
    result = roles(b, 'peer', at)
    assert {r['role'] for r in result} == {'CUSTOMER', 'SUPPLIER', 'COMPETITOR'}
    assert all(r['scope'] == 'Synthetic test' and r['source_ids'] == ['s'] for r in result)
    assert 'CUSTOMER' not in {r['role'] for r in roles(b, 'p', at)}
    data['relationships'][-1]['valid_until'] = (at-timedelta(seconds=1)).isoformat()
    data['relationships'][-2]['status'] = 'REVOKED'
    b = ProfileBundle.model_validate(data)
    assert {r['role'] for r in roles(b, 'peer', at)} == {'CUSTOMER'}
    assert roles(b, 'missing', at) == []
