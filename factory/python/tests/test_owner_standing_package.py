"""Exercise administrative recovery/start helpers with isolated SQLite and a harmless child process."""
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[3] / 'tools/owner_standing_package.py'
spec = importlib.util.spec_from_file_location('owner_standing_package', TOOL)
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def test_standing_start_uses_observed_epoch_across_owner_resume(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from forge_factory.afo import operations
    from forge_factory.afo.durable import Refused

    path = tmp_path / "private" / "intent.json"
    path.parent.mkdir(mode=0o700)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(path))
    intent = operations.Intent()
    intent.set("RUNNING", actor="FIXTURE", reason="initialize", initialize=True)
    intent.set("STOPPED", actor="FIXTURE", reason="pause work")
    resumed = intent.set("RUNNING", actor="FIXTURE", reason="resume work")
    issued = []

    def need(ok, code):
        if not ok:
            raise ValueError(code)

    source = """def start(b, x):
    prerequisites.require_poststop(b,x.stop_result_sha256,allowance=True)
    return operations.fenced_call(1,request_start)
"""
    ns = dict(operations=operations, need=need, request_start=lambda: issued.append(1),
              prerequisites=SimpleNamespace(require_poststop=lambda *_, **__: {"expectation": {"Intent": resumed}}))
    exec(compile(P.bind_verified_intent_epoch(source), "<bound-start>", "exec"), ns)
    ns["start"]({}, SimpleNamespace(stop_result_sha256="fixture"))
    assert issued == [1] and resumed["epoch"] > 1
    intent.set("STOPPED", actor="FIXTURE", reason="stop before stale starter acts")
    with pytest.raises(Refused, match="OPERATIONS_ADMISSION_FENCED"):
        ns["start"]({}, SimpleNamespace(stop_result_sha256="fixture"))
    assert issued == [1]


@pytest.mark.parametrize('actor,paused,extra,passes', [
    ('model-service-qualification-window','0',False,True),
    ('owner-development-source-fix-hold','0',False,True),
    ('model-service-qualification-window','1',False,False),
    ('unknown-writer','0',False,False),
    ('model-service-qualification-window','0',True,False),
])
def test_real_retirement_observer_accepts_only_known_unpaused_controls(actor, paused, extra, passes):
    source = (Path(__file__).parent / 'fixtures/owner-supervised-development/retirement-cursor.py').read_text()
    namespace = {}
    exec(compile(P.retirement_cursor(source), '<isolated-retirement-observer>', 'exec'), namespace)
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE afo_control(key TEXT,value TEXT,updated_utc TEXT,actor TEXT)')
    db.execute('INSERT INTO afo_control VALUES (?,?,?,?)', ('paused',paused,'2026-11-21T00:00:00Z',actor))
    if extra:
        db.execute('INSERT INTO afo_control VALUES (?,?,?,?)', ('unknown','1','2026-11-21T00:00:00Z','unknown'))
    before = db.total_changes
    if passes:
        assert namespace['observe_connection'](db)['writes'] == 0
    else:
        with pytest.raises(RuntimeError):
            namespace['observe_connection'](db)
    assert db.total_changes == before


@pytest.fixture
def launcher(tmp_path):
    root = tmp_path / 'isolated-host'
    ops = root / 'owner-main-ops'
    ops.mkdir(parents=True)
    helper = ops / 'start-main-reviewed.py'
    helper.write_text("import json,os,sys\nfrom pathlib import Path\n"
                      "Path(__file__).with_name('received.json').write_text(json.dumps(dict(argv=sys.argv[1:],env=dict(os.environ))))\n")
    binding = ops / 'binding.json'
    binding.write_text('{}')
    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    original = (f'T={str(root)!r}\nPY={sys.executable!r}\nRET={"a"*64!r}\nHARD={"b"*64!r}\n'
                f"if False:\n assert hashlib.sha256(p.read_bytes()).hexdigest()=='{sha(helper)}'\n"
                f" assert hashlib.sha256(b.read_bytes()).hexdigest()=='{sha(binding)}'\n")
    script = tmp_path / 'start-once.py'
    script.write_text(P.standing_launcher(original))
    env = {k: v for k,v in os.environ.items() if not k.startswith('FORGE_')}
    env.update(XDG_RUNTIME_DIR=str(tmp_path), DBUS_SESSION_BUS_ADDRESS='fixture-no-real-bus',
               UNRELATED_FIXTURE_VALUE='must-not-reach-the-child')
    return root, helper, script, env


def test_standing_launcher_uses_bound_child_without_network_dates_and_never_replays(launcher):
    root, _, script, env = launcher
    result = subprocess.run([sys.executable,str(script),'c'*64,'d'*64],env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['authorization_lifetime'] == 'UNTIL_OWNER_STOP'
    received = root / 'owner-main-ops/received.json'
    until = time.monotonic()+5
    while not received.exists() and time.monotonic()<until:
        time.sleep(.02)
    child = json.loads(received.read_text())
    assert '--until-owner-stop' in child['argv'] and '--ticket' not in child['argv']
    assert '--stop-result-sha256' in child['argv'] and '--metadata-receipt-sha256' in child['argv']
    assert 'UNRELATED_FIXTURE_VALUE' not in child['env']
    again = subprocess.run([sys.executable,str(script),'c'*64,'d'*64],env=env,capture_output=True,text=True,timeout=10)
    assert again.returncode != 0


def test_changed_helper_refuses_before_start_intent_or_child(launcher):
    root, helper, script, env = launcher
    helper.write_text("raise SystemExit('changed')")
    result = subprocess.run([sys.executable,str(script),'c'*64,'d'*64],env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode != 0
    assert not script.with_name('start-request-intent-r1.json').exists()
    assert not (root/'owner-main-preflight-r1').exists()


def test_unknown_package_shape_is_rejected_before_mutation(tmp_path):
    (tmp_path/'ops').mkdir()
    for name in ('ops/start-main-reviewed.py','start-with-fresh-ticket-once-r1.py','bind-main.py'):
        (tmp_path/name).write_text('unrecognized = True\n')
    with pytest.raises(ValueError,match='SHAPE_CHANGED'):
        P.adapt(tmp_path)
    assert (tmp_path/'ops/start-main-reviewed.py').read_text() == 'unrecognized = True\n'
