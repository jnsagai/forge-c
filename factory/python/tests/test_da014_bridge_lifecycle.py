"""A health refresh must not orphan the host-side API relay ownership record."""
import json
import os
from pathlib import Path

import pytest
from forge_factory.lrtx import stack


@pytest.mark.parametrize('recovery,control_only', [(False, False), (True, False), (True, True)])
def test_refresh_preserves_relay_identities_for_later_managed_stop(tmp_path, monkeypatch, recovery, control_only):
    (tmp_path / 'venv/bin').mkdir(parents=True)
    (tmp_path / 'venv/bin/python').touch()
    (tmp_path / 'run').mkdir()
    prof = {'id': 'fixture', '_sha256': 'a' * 64, 'runtime': {'ollama': {}},
            'admission': {'max_inflight': 1, 'max_queue': 1, 'max_wait_s': 1},
            'deployment': {'shared_readonly': {}}}
    ports = {'ollama': 11455, 'gateway': 11456, 'fabro': 32391}
    env = {'FORGE_VENV': str(tmp_path / 'venv'), 'FORGE_FABRO_BIN': '/bin/fabro',
           'FORGE_FABRO_CONFIG': 'config', 'FORGE_FABRO_STORAGE': 'storage', 'FORGE_FABRO_HOME': 'home'}
    identity = {'boot_id': 'fixture', 'start_ticks': '42', 'uid': os.getuid()}
    holder = os.getpid()
    procs = {name: {'pid': 100 + i, 'identity': identity, 'argv': ['bin', name], 'health': name}
             for i, name in enumerate(('ollama', 'gateway', 'fabro'))}
    bridge = {name: {'pid': 200 + i, 'argv': ['socat', name], 'identity': identity}
              for i, name in enumerate(('inner', 'outer'))}
    stack._save_services(tmp_path, {'holder_identity': identity, 'processes': procs, 'api_bridge': bridge})
    monkeypatch.setattr(stack, 'envmap', lambda _: env)
    monkeypatch.setattr(stack, '_holder', lambda _: holder)
    monkeypatch.setattr(stack, 'process_identity', lambda _: identity)
    monkeypatch.setattr(stack, 'managed_serving', lambda: False)
    monkeypatch.setattr(stack, '_alive', lambda *_: True)
    monkeypatch.setattr(stack, '_probe', lambda *_: True)
    monkeypatch.setattr(stack.subprocess, 'Popen', lambda *a, **kw: pytest.fail('healthy services were relaunched'))
    s = {'root': tmp_path, 'ports': ports, 'profile': prof}
    stack._start(s, recovery=recovery, control_only=control_only)
    assert json.loads((tmp_path / 'run/services.json').read_text())['api_bridge'] == bridge
    signals = []
    monkeypatch.setattr(stack.pidfd, 'open_pid', lambda pid: pid)
    monkeypatch.setattr(stack.pidfd, 'send_signal', lambda fd, sig: signals.append((fd, sig)))
    monkeypatch.setattr(stack.os, 'close', lambda _: None)
    monkeypatch.setattr(stack.time, 'sleep', lambda _: None)
    # The fake signal cannot retire the actual test process; avoid the stop wait.
    exists = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda p: False if str(p) == f'/proc/{holder}' else exists(p))
    result = stack._stop(s, managed=True)
    assert {'api-bridge-inner', 'api-bridge-outer'} <= set(result['stopped'])
    assert {200, 201} <= {fd for fd, _ in signals}
    assert 'api_bridge' not in json.loads((tmp_path / 'run/services.json').read_text())
