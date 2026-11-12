"""Explicit fresh-namespace staging only; default prints plan without mutations."""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path('/mnt/data/forge-c/swe1-fabro-20261031/qualification/owner-development-dc27abba-review-20261105')
OLD = Path('/mnt/data/forge-c/swe1-fabro-20261031/qualification/local-gen36-74e44a1f-review-20261105/source')
SOURCE = 'dc27abba601e5f6713f30e6027cb0bbd64241528'
BASE = '74e44a1f23b01f3200350436df1691249b441292'
MANIFEST_SHA = '8513583841f05259bdd0991fa485bd3e8c0554fcbb9129235f09ffe16e4c4f2f'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(p, *args): return subprocess.check_output(['git', '-C', str(p), *args], text=True, timeout=60).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage-reviewed', action='store_true')
    a = ap.parse_args()
    if not a.stage_reviewed:
        print(json.dumps(dict(status='OFFLINE_PLAN_ONLY', effects=False, source=SOURCE, root=str(ROOT))))
        return
    assert Path(__file__).resolve().parent == ROOT
    assert sha(ROOT/'transfer-manifest.json') == MANIFEST_SHA
    manifest = json.loads((ROOT/'transfer-manifest.json').read_text())
    assert manifest['source'] == SOURCE and manifest['prerequisite'] == BASE
    for row in manifest['files']:
        p = ROOT/row['name']
        assert p.is_file() and not p.is_symlink() and sha(p) == row['sha256'] and p.stat().st_size == row['bytes']
    assert git(OLD, 'rev-parse', 'HEAD') == BASE and not git(OLD, 'status', '--porcelain')
    before = dict(head=git(OLD,'rev-parse','HEAD'), refs=git(OLD,'for-each-ref','--format=%(refname) %(objectname)'), status=git(OLD,'status','--porcelain'))
    source = ROOT/'source'
    assert not source.exists() and not source.is_symlink() and not (ROOT/'staging-receipt.json').exists()
    with (ROOT/'stage-intent.json').open('x') as f:
        json.dump(dict(status='STAGING_ATTEMPTED_NO_AUTOMATIC_REPLAY',source=SOURCE), f)
    subprocess.run(['git','clone','--shared','--no-checkout',str(OLD),str(source)],check=True,timeout=60)
    subprocess.run(['git','-C',str(source),'fetch','--no-tags',str(ROOT/'candidate-source.bundle'),'HEAD'],check=True,timeout=60)
    subprocess.run(['git','-C',str(source),'checkout','--detach',SOURCE],check=True,timeout=60)
    assert git(source,'rev-parse','HEAD') == SOURCE
    expected = {r['path']:r for r in manifest['inputs']}
    with tarfile.open(ROOT/'runtime-inputs.tar') as archive:
        members = archive.getmembers()
        assert len(members) == len(expected) == 12 and {m.name for m in members} == set(expected)
        for member in members:
            assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
            data = archive.extractfile(member).read()
            assert hashlib.sha256(data).hexdigest() == expected[member.name]['sha256']
            p = source/member.name
            assert not p.is_symlink()
            if p.exists(): assert p.read_bytes() == data
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open('xb') as f: f.write(data)
                p.chmod(0o444)
    for row in manifest['inputs']: assert sha(source/row['path']) == row['sha256']
    for row in manifest['changed_source_files']: assert sha(source/row['path']) == row['sha256']
    assert not git(source,'status','--porcelain')
    after = dict(head=git(OLD,'rev-parse','HEAD'), refs=git(OLD,'for-each-ref','--format=%(refname) %(objectname)'), status=git(OLD,'status','--porcelain'))
    assert before == after
    receipt = dict(schema='forge-c/owner-development-offline-staging/1', source=SOURCE, source_path=str(source),
        all12_inputs_before_any_tests=True, files=manifest['inputs'], manifest_sha256=MANIFEST_SHA,
        prior_repository_unchanged=before==after, actual_models=0, native_runs=0, services_or_mission_or_policy_changed=False,
        scope='NEW_IMMUTABLE_SOURCE_NAMESPACE_ONLY_NOT_ACTIVATED')
    with (ROOT/'staging-receipt.json').open('x') as f: json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))


if __name__ == '__main__': main()
