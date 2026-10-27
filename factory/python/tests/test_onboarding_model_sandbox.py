"""Authored-model execution cannot see the hand model, owner home, or host network."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from forge_factory.onboarding import model_sandbox as S


def test_pure_register_model_subset_accepts_arithmetic_and_state():
    assert S.source_issues('''
MODEL_LIMITS = []
if request.IsInit:
    regs = {0: 0xffffffff}
elif request.IsRead:
    request.Value = regs.get(request.Offset, 0)
elif request.IsWrite:
    regs[request.Offset] = int(request.Value) & 0xffffffff
''') == []


@pytest.mark.parametrize("source", ["import os", "open('/etc/passwd')", "request.peripheral.Machine",
                                    "request.__class__", "globals()['x']", "print('0x00000000')",
                                    "request.Offset = 0", "f = lambda: 0", "class X: pass", 'x = f"{1}"'])
def test_import_reflection_output_and_host_access_are_refused(source):
    assert S.source_issues(source)


@pytest.mark.skipif(not shutil.which('bwrap'), reason='rootless bubblewrap not installed')
def test_filesystem_view_excludes_host_hand_model_and_home(tmp_path):
    secret = tmp_path / 'hand_model.py'
    secret.write_text('not visible in the isolated scratch')
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    # The trusted test broker selects Python to probe the same mount builder used for Renode.
    command = S.argv(Path('/usr/bin/python3'), scratch, ['-c',
        f"from pathlib import Path; assert not Path({str(secret)!r}).exists(); "
        "assert not Path('/home/jefferson').exists(); assert not Path('/media').exists(); "
        "assert not Path('/proc/net/route').read_text().splitlines()[1:]"])
    result = subprocess.run(command, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr.decode()


def test_scratch_symlinks_cannot_add_a_host_read_mount(tmp_path):
    (tmp_path / 'leak').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='SYMLINK'):
        S.argv(Path(sys.executable), tmp_path, [])


def test_pure_model_runs_in_real_renode_namespace(tmp_path):
    from forge_factory.mcp.servers.sim import renode_bin
    from forge_factory.onboarding.model_gate import registers_check

    renode = renode_bin()
    if not renode or not shutil.which('bwrap'):
        pytest.skip('Renode or bubblewrap unavailable')
    model = tmp_path / 'probe_model.py'
    model.write_text('MODEL_LIMITS = []\nif request.IsRead:\n    request.Value = request.Length\n')
    platform = tmp_path / 'platform.repl'
    platform.write_text('probe: Python.PythonPeripheral @ sysbus 0x56000000\n'
                        '    size: 0x4\n    initable: true\n    filename: "X_MODEL_PATH"\n')
    package = {'facts': [{'name': 'register_prefix', 'value': 'X'}, {'name': 'base_address', 'value': '0x56000000'},
                         {'name': 'register_index', 'value': {'X_REG': {'offset': 0, 'reset': 4, 'fields': {
                             'VALUE': {'msb': 31, 'lsb': 0, 'access': ['r']}}}}}]}
    for fact in package['facts']:
        fact['status'] = 'DERIVED'
    findings, limits, stats = registers_check(package, model, platform, renode, isolated=True)
    assert not findings and not limits, findings
    assert stats['reads'] == 3  # reset plus two read-only write attempts; real request.Length is four bytes
