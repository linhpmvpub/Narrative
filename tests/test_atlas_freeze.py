import json
from pathlib import Path

import pytest
from test_company_profiles import dossier as dossier

from engine import atlas_freeze
from engine.impact_atlas import install, snapshot


def prepared(dossier,tmp_path,monkeypatch):
    root,_=dossier
    atlas=tmp_path/'atlas'
    install(snapshot(root.parent),atlas)
    monkeypatch.setattr(atlas_freeze,'runtime_fingerprint',lambda:{'engine/test.py':'a'})
    output=tmp_path/'frozen'
    result=atlas_freeze.freeze(atlas,Path('config/impact-group-acceptance.json'),output)
    return atlas,output,result['baseline_sha256']


def test_baseline_is_immutable_and_does_not_claim_locked_predictions(dossier,tmp_path,monkeypatch):
    atlas,out,pin=prepared(dossier,tmp_path,monkeypatch)
    result=atlas_freeze.verify(out,pin)
    assert result['verified'] and result['event_clusters']==0
    assert not result['predictions_locked'] and result['delivery']=='disabled'
    with pytest.raises(FileExistsError):
        atlas_freeze.freeze(atlas,Path('config/impact-group-acceptance.json'),out)


@pytest.mark.parametrize('name',['atlas.db','atlas.json','index.html','criteria.json','runtime.json','baseline.json'])
def test_baseline_tampering_is_detected(dossier,tmp_path,monkeypatch,name):
    _,out,pin=prepared(dossier,tmp_path,monkeypatch)
    (out/name).write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):
        atlas_freeze.verify(out,pin)


def test_runtime_drift_invalidates_same_baseline(dossier,tmp_path,monkeypatch):
    _,out,pin=prepared(dossier,tmp_path,monkeypatch)
    monkeypatch.setattr(atlas_freeze,'runtime_fingerprint',lambda:{'engine/test.py':'b'})
    with pytest.raises(ValueError,match='Runtime/config'):
        atlas_freeze.verify(out,pin)


def test_calibrated_or_live_criteria_cannot_be_silently_frozen(dossier,tmp_path):
    root,_=dossier
    atlas=tmp_path/'atlas'
    install(snapshot(root.parent),atlas)
    criteria=json.loads(Path('config/impact-group-acceptance.json').read_text())
    criteria['delivery']='enabled'
    path=tmp_path/'criteria.json'
    path.write_text(json.dumps(criteria))
    with pytest.raises(ValueError,match='Disabled'):
        atlas_freeze.freeze(atlas,path,tmp_path/'frozen')
