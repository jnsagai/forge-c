"""Actual namespaced Python through an exact UV-style version directory alias."""
import json
import os
from pathlib import Path
import sys
import tempfile

import pytest


def contrast(root):
    from forge_factory.common import REPO_ROOT
    from forge_factory.reliability import isolation

    if isolation.backend() != 'bubblewrap':
        raise RuntimeError('ACTUAL_BUBBLEWRAP_REQUIRED')
    original = sys.executable, sys.prefix, sys.base_prefix
    prefix = Path(sys.prefix)
    install = Path(sys.base_prefix).resolve()
    executable = Path(sys.executable).resolve()
    alias = root / 'uv-minor-version-alias'
    alias.symlink_to(install, target_is_directory=True)
    venv = root / 'private-venv'
    (venv / 'bin').mkdir(parents=True)
    (venv / 'bin/python').symlink_to(alias / 'bin' / executable.name)
    (venv / 'lib').symlink_to(prefix / 'lib', target_is_directory=True)
    (venv / 'pyvenv.cfg').write_text('home = ' + str(alias / 'bin') + '\ninclude-system-site-packages = false\n')
    marker = root / 'private-marker-not-runtime'
    marker.write_text('must stay outside verifier namespace')
    env = {'PATH': '/usr/bin:/bin', 'FORGE_REPO_ROOT': str(REPO_ROOT)}
    code = ('import json,sys,jsonschema; print(json.dumps({"prefix":sys.prefix,"dependency_import":True}))')
    control = isolation.execute('verifier', [original[0], '-c', code], cwd=REPO_ROOT, env=env,
                                writable=[], readable=[prefix], timeout=15)
    if control.returncode:
        raise RuntimeError('NORMAL_PYTHON_CONTROL_FAILED:' + control.stderr.decode(errors='replace')[-300:])
    try:
        # Explicit runtime-layout fixture; command below executes the actual
        # interpreter/venv under the real supported kernel namespace backend.
        sys.executable, sys.prefix, sys.base_prefix = str(venv / 'bin/python'), str(venv), str(install)
        code = ('import json,os,sys,jsonschema; from pathlib import Path; '
                f'alias=Path({str(alias)!r}); marker=Path({str(marker)!r}); '
                'print(json.dumps({"prefix":sys.prefix,"dependency_import":True,'
                '"alias_readonly":bool(os.statvfs(alias).f_flag & os.ST_RDONLY),'
                '"unrelated_private_visible":marker.exists()}))')
        result = isolation.execute('verifier', [sys.executable, '-c', code], cwd=REPO_ROOT, env=env,
                                   writable=[], readable=[prefix], timeout=15)
        facts = json.loads(result.stdout.decode()) if result.returncode == 0 else None
        return {'fixture_only': True, 'normal_python_control_exit': control.returncode,
                'alias_command_exit': result.returncode, 'alias_error': result.stderr.decode(errors='replace')[-400:],
                'facts': facts,
                'pass': result.returncode == 0 and facts.get('prefix') == str(venv)
                        and facts.get('dependency_import') is True and facts.get('alias_readonly') is True
                        and facts.get('unrelated_private_visible') is False}
    finally:
        sys.executable, sys.prefix, sys.base_prefix = original


def test_actual_version_alias_preserves_venv_and_readonly_scope(tmp_path, monkeypatch):
    monkeypatch.setenv('FORGE_CRE_ISOLATION', 'bubblewrap')
    facts = contrast(tmp_path)
    assert facts['pass'], facts


def test_only_alias_of_already_mounted_python_install_is_added(tmp_path, monkeypatch):
    from forge_factory.reliability import isolation

    install = tmp_path / 'python-install'
    (install / 'bin').mkdir(parents=True)
    (install / 'bin/python').write_text('fixture')
    alias = tmp_path / 'runtime-alias'
    alias.symlink_to(install, target_is_directory=True)
    venv = tmp_path / 'venv'
    (venv / 'bin').mkdir(parents=True)
    (venv / 'bin/python').symlink_to(alias / 'bin/python')
    monkeypatch.setattr(sys, 'executable', str(venv / 'bin/python'))
    monkeypatch.setattr(sys, 'base_prefix', str(install))
    assert isolation.python_runtime_aliases() == {alias, install}
    assert tmp_path not in isolation.python_runtime_aliases()
    unrelated = tmp_path / 'unrelated-install'
    unrelated.mkdir()
    monkeypatch.setattr(sys, 'base_prefix', str(unrelated))
    assert isolation.python_runtime_aliases() == set()


def main():
    os.environ["FORGE_CRE_ISOLATION"] = "bubblewrap"  # explicit nested-backend fixture, not runner default
    with tempfile.TemporaryDirectory(prefix='rpr158-python-alias-') as temporary:
        facts = contrast(Path(temporary))
        print(json.dumps(facts))
        if not facts['pass']:
            if facts['alias_command_exit'] == 0:
                print('REPRODUCER_ERROR:alias ran but runtime identity/privacy controls failed')
                return 2
            print('SYMPTOM_PRESENT:scoped verifier cannot execute venv Python through its version alias')
            return 1
    print('SYMPTOM_ABSENT')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('REPRODUCER_ERROR:' + type(exc).__name__ + ':' + str(exc)[:400])
        raise SystemExit(2)
