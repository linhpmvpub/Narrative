"""Immutable local baseline for grouped evaluation; no labels or accuracy claims."""
import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from engine.impact_atlas import MECHANISMS, read_snapshot

FILES = {'atlas.db','atlas.json','index.html','manifest.json','criteria.json','runtime.json'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_fingerprint():
    root = Path(__file__).resolve().parent.parent
    paths = sorted(p for p in (root/'engine').rglob('*') if p.is_file()
                   and p.suffix in {'.py','.js','.html','.css','.json'})
    paths += sorted((root/'config').glob('*.json'))
    paths += [root/name for name in ['pyproject.toml','requirements-validated.txt','requirements-container.txt','requirements-extraction.txt'] if (root/name).is_file()]
    return {p.relative_to(root).as_posix():sha(p) for p in paths}


def freeze(atlas, criteria, output):
    atlas, output = Path(atlas), Path(output)
    data = read_snapshot(atlas)
    criteria_bytes = Path(criteria).read_bytes()
    targets = json.loads(criteria_bytes)
    if (set(targets.get('groups',[])) != set(MECHANISMS)
            or targets.get('status') != 'PREDECLARED_TARGETS_NOT_VALIDATED'
            or targets.get('delivery') != 'disabled' or targets.get('weights') is not None
            or data.get('delivery') != 'disabled' or data['policy'].get('weights') is not None):
        raise ValueError('Disabled delivery and predeclared uncalibrated group criteria required')
    output.mkdir(parents=True,exist_ok=False)
    before = runtime_fingerprint()
    for name in ['atlas.db','atlas.json','index.html','manifest.json']:
        shutil.copyfile(atlas/name,output/name)
    read_snapshot(output)
    (output/'criteria.json').write_bytes(criteria_bytes)
    (output/'runtime.json').write_text(json.dumps(before,sort_keys=True,indent=2),encoding='utf-8')
    if runtime_fingerprint() != before:
        raise ValueError('Runtime changed during baseline freeze')
    receipt = {'schema':'ATLAS_EVALUATION_BASELINE_V1','created_at':datetime.now(UTC).isoformat(),
        'atlas_as_of':data['as_of'],'status':'BASELINE_ONLY_NO_EVENT_LABELS',
        'event_clusters':0,'predictions_locked':False,'human_gold':False,'delivery':'disabled',
        'policy':data['policy'],'files':{name:sha(output/name) for name in sorted(FILES)}}
    (output/'baseline.json').write_text(json.dumps(receipt,sort_keys=True,indent=2),encoding='utf-8')
    return {'baseline_sha256':sha(output/'baseline.json'),'status':receipt['status'],
            'event_clusters':0,'predictions_locked':False,'delivery':'disabled'}


def verify(root, expected_sha256):
    root = Path(root)
    if sha(root/'baseline.json') != expected_sha256:
        raise ValueError('Baseline receipt changed')
    receipt = json.loads((root/'baseline.json').read_text(encoding='utf-8'))
    if receipt['schema'] != 'ATLAS_EVALUATION_BASELINE_V1' or set(receipt['files']) != FILES:
        raise ValueError('Invalid baseline schema/files')
    for name in FILES:
        if sha(root/name) != receipt['files'][name]:
            raise ValueError('Frozen baseline artifact changed')
    data = read_snapshot(root)
    if data['as_of'] != receipt['atlas_as_of']:
        raise ValueError('Baseline time mismatch')
    if runtime_fingerprint() != json.loads((root/'runtime.json').read_text(encoding='utf-8')):
        raise ValueError('Runtime/config differs from frozen baseline')
    return {'verified':True,'baseline_sha256':expected_sha256,'event_clusters':0,
            'predictions_locked':False,'delivery':'disabled'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','verify'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--atlas',type=Path)
    parser.add_argument('--criteria',type=Path)
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    if args.action == 'create':
        if args.atlas is None or args.criteria is None:
            parser.error('--atlas and --criteria required')
        result = freeze(args.atlas,args.criteria,args.output)
    else:
        if not args.expected_sha256:
            parser.error('--expected-sha256 required; use the separately recorded receipt hash')
        result = verify(args.output,args.expected_sha256)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
