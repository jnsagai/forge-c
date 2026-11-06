"""Execute real cold control startup; private CPU transport leaves, no live models."""

import json
import socket
import subprocess
import sys

import pytest
from forge_factory.afo import owner_profile_bootstrap as B
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused
from forge_factory.lrtx import provider_process as provider
from forge_factory.lrtx import stack
from test_owner_profile_bootstrap import boot  # noqa: F401 - real private Store/Intent/guardian fixture
from test_owner_supervised_development import supervised  # noqa: F401 - transitive real guardian fixture

REAL_START = stack._start
REAL_IN_NS = stack._in_ns
REAL_PROBE = stack._probe
REAL_POPEN = subprocess.Popen


@pytest.fixture
def cold(boot, monkeypatch):  # noqa: F811 - imported pytest fixture requested by name
    root = boot["root"]
    (root / "logs").mkdir()
    (root / "venv/bin").mkdir(parents=True)
    (root / "venv/bin/python").symlink_to(sys.executable)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    settings = stack.settings(D.PROFILE)
    settings["root"].joinpath("fabro").mkdir(exist_ok=True)
    settings["root"].joinpath("fabro/settings.toml").write_text(stack.fabro_config(settings))
    settings["ports"] = {**settings["ports"], "fabro": port}
    monkeypatch.setattr(stack, "settings", lambda _: settings)
    # Only the transport/namespace leaves are simulated: real _start, _in_ns,
    # Popen, _probe, process_identity, provider.owner_view and disk projection run.
    server = root / "private_cpu_control.py"
    server.write_text("""import os
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlsplit
class Health(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'PRIVATE_CPU_HEALTH_ONLY')
 def log_message(self,*a): pass
HTTPServer(('127.0.0.1',urlsplit(os.environ['FORGE_FABRO_URL']).port),Health).serve_forever()
""")
    holders = []

    def namespace_process(argv, *args, **kwargs):
        if argv[:2] == ["setsid", "unshare"]:
            # Simulated namespace entry only: real _start cold-holder branch,
            # guard, Popen lifetime and holder.pid projection still execute.
            p = REAL_POPEN(["sleep", "infinity"], *args, **kwargs)
            boot["children"].append(p)
            holders.append(p)
            (root / "run/holder.pid").write_text(str(p.pid))
            return p
        return REAL_POPEN(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", namespace_process)
    monkeypatch.setattr(stack, "_nsenter", lambda _: [])
    monkeypatch.setattr(stack, "llama_server_spec", lambda *_: None)
    monkeypatch.setattr(stack, "cloud_bridge", lambda _: None)
    called = []

    def private_transport(holder_pid, argv, env, log, cwd, **kwargs):
        assert holder_pid == holders[0].pid and argv[1:3] == ["server", "start"]
        p = REAL_IN_NS(holder_pid, [sys.executable, str(server)], env, log, cwd, **kwargs)
        boot["children"].append(p)
        called.append(p)
        return p

    monkeypatch.setattr(stack, "_in_ns", private_transport)
    fake_provider_start = stack._start

    def composed_start(s, *, recovery=False, control_only=False):
        if control_only:
            return REAL_START(s, recovery=recovery, control_only=True)
        # No provider/model load is part of this CPU regression.
        return fake_provider_start(s, recovery=recovery, control_only=False)

    monkeypatch.setattr(stack, "_start", composed_start)
    observed = []

    def observe_partial(holder_pid, env, url):
        partial = json.loads((root / "run/services.json").read_text())
        fabro = partial["processes"]["fabro"]
        assert fabro["identity"] == stack.process_identity(fabro["pid"])
        assert fabro["owner_view"] == provider.owner_view(fabro["pid"])
        assert partial["owner_bootstrap_binding"]["record_sha256"]
        assert partial["holder_identity"] == stack.process_identity(holders[0].pid)
        observed.append(partial)
        return REAL_PROBE(holder_pid, env, url)

    monkeypatch.setattr(stack, "_probe", observe_partial)
    return dict(boot=boot, settings=settings, called=called, observed=observed, probe=observe_partial)


def test_real_control_start_persists_owned_partial_projection_before_health(cold):
    b = cold["boot"]
    result = B.bootstrap(b["store"], b["placer"])
    assert result["status"] == "READY"
    assert len(cold["called"]) == 1 and cold["called"][0].poll() is None
    assert cold["observed"]
    saved = json.loads((b["root"] / "run/services.json").read_text())
    assert set(saved["processes"]) == {"fabro"}
    assert saved["health"]["fabro"] is True
    assert saved["owner_bootstrap_binding"] == cold["observed"][0]["owner_bootstrap_binding"]
    assert not (b["root"] / "state/conductor/conductor.sqlite3").exists()


def test_real_control_start_health_exception_retains_owned_process_and_unknown(cold, monkeypatch):
    b = cold["boot"]

    def failed_after_projection(holder, env, url):
        cold["probe"](holder, env, url)
        raise RuntimeError("PRIVATE_HEALTH_FAILURE_AFTER_REAL_SPAWN")

    monkeypatch.setattr(stack, "_probe", failed_after_projection)
    with pytest.raises(RuntimeError, match="PRIVATE_HEALTH_FAILURE"):
        B.bootstrap(b["store"], b["placer"])
    assert len(cold["called"]) == 1 and cold["called"][0].poll() is None
    saved = json.loads((b["root"] / "run/services.json").read_text())
    assert saved["processes"]["fabro"]["pid"] == cold["called"][0].pid
    with b["store"].tx() as c:
        rows = [
            json.loads(r[0]) for r in c.execute("SELECT record FROM afo_independent_decisions WHERE kind=?", (B.RESULT_KIND,))
        ]
    assert len(rows) == 1 and rows[0]["status"] == "UNKNOWN_REQUIRES_RECONCILIATION" and rows[0]["no_retry"]
    with pytest.raises(Refused):
        D.current()
    assert not (b["root"] / "state/conductor/conductor.sqlite3").exists()
