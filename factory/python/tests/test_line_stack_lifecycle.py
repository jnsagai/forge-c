"""Real line order/mission/lease/intent and owned process effects; no GPU or model calls."""
# ruff: noqa: F811
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_launcher as LL
from forge_factory.afo import line_recovery_control as C
from forge_factory.afo import line_recovery_product as P
from forge_factory.afo import line_stack_lifecycle as A
from forge_factory.afo import local_agent, operations
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.lrtx import stack as ST
from test_line_recovery_product_bridge import product  # noqa: F401

pytestmark = pytest.mark.parametrize("product", [True], indirect=True)


@pytest.fixture
def claimed(product, monkeypatch, tmp_path):
    p = product
    monkeypatch.setattr(operations, "configured", lambda: True)
    intent_path = Path(p.control["operations_intent"])
    intent = operations.Intent(intent_path)
    monkeypatch.setattr(local_agent, "authorized", lambda *a, **kw: True)
    monkeypatch.setattr(C, "require_native_transport", lambda *a, **kw: {"measured_fixture": True})
    p.cfg.gpu_lock = tmp_path / "gpu.lock"
    (p.cfg.stack_root / "run").mkdir(parents=True)
    monkeypatch.setenv("FORGE_LINE_STACK_ROOT", str(p.cfg.stack_root))
    monkeypatch.setenv("FORGE_LINE_GPU_LOCK", str(p.cfg.gpu_lock))
    monkeypatch.setenv("FORGE_DURABLE_NATIVE_HEADER", "1")
    caught = []

    def capture(order, cfg):
        caught.append(order)
        raise TimeoutError("private fixture: no native invocation")

    P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg, launch=capture)
    assert len(caught) == 1
    order = caught[0]
    P.claim_for_launch(p.cfg, order)
    for key, value in P.execution_context(order).items():
        monkeypatch.setenv(key, value)
    from forge_factory.lrtx.profile import load

    profile = load(p.spec["profile"])
    s = {"root": p.cfg.stack_root, "profile": profile, "ports": profile["deployment"]["ports"]}
    # The real API leaf is intentionally absent; normal M2 permits this only with no current Fabro PID.
    monkeypatch.setattr(LL.ShellHost, "fabro_runs", lambda self: [])
    p.s, p.intent, p.order = s, intent, order
    return p


def test_claimed_line_stop_preserves_intent_mission_and_lease_and_ends_only_owned_process(claimed):
    p = claimed
    before = p.intent.path.read_bytes()
    mission = MissionLedger(p.store).snapshot("fixture-mission")
    own = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    foreign = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    try:
        ST._save_services(p.s["root"], {"processes": {"fixture": {"pid": own.pid,
                          "argv": [sys.executable, "import time"], "identity": ST.process_identity(own.pid)}}})
        with LL.gpu_lock(p.cfg.gpu_lock), LL.held_stack_lock(p.s["root"]):
            out = ST._locked_stop(p.s)
        own.wait(timeout=5)
        assert out["stopped"] == ["fixture"]
        assert foreign.poll() is None
        assert p.intent.path.read_bytes() == before
        assert MissionLedger(p.store).snapshot("fixture-mission") == mission
        assert Executions(p.store).get(P.job_id(p.aid))["resource_lease"] == "HELD"
        assert not (p.cfg.stack_root / "state/conductor/conductor.sqlite3").exists()
    finally:
        for process in (own, foreign):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)


def test_claimed_start_reaches_managed_backend_with_own_held_lease_and_no_shutdown(claimed, monkeypatch):
    p = claimed
    reached = []
    before = p.intent.path.read_bytes()

    def backend(settings, **kwargs):
        assert ST.managed_serving()
        assert Executions(p.store).get(P.job_id(p.aid))["resource_lease"] == "HELD"
        child = subprocess.run([sys.executable, "-c", "print('isolated-start-backend')"],
                               capture_output=True, text=True, check=True)
        reached.append(child.stdout.strip())
        return {"started": True}

    monkeypatch.setattr(ST, "_start", backend)
    with LL.gpu_lock(p.cfg.gpu_lock), LL.held_stack_lock(p.s["root"]):
        assert ST._locked_start(p.s) == {"started": True}
    assert reached == ["isolated-start-backend"]
    assert p.intent.path.read_bytes() == before
    assert not (p.cfg.stack_root / "state/conductor/conductor.sqlite3").exists()


@pytest.mark.parametrize("change,code", [("intent", "AUTHORITY_OR_EXECUTION_FENCED"),
    ("nonce", "REGISTERED_BINDING_CHANGED"), ("profile", "AUTHORITY_OR_EXECUTION_FENCED"),
    ("foreign-owner", "RESOURCE_OR_REQUEST_NOT_QUIESCENT"), ("missing-lock", "CLAIM_OR_LOCKS_UNPROVEN"),
    ("unknown-native", "NATIVE_NOT_QUIESCENT")])
def test_line_preparation_refuses_changed_authority_before_any_process_effect(claimed, monkeypatch, change, code):
    p = claimed
    if change == "intent":
        p.intent.set("STOPPED", actor="private-owner", reason="superseded")
    elif change == "nonce":
        job = P.registered(p.store, P.job_id(p.aid))
        job["nonce"] = "different-nonce"
        with p.store.tx() as c:
            c.execute("UPDATE afo_product_jobs SET record=? WHERE job_id=?", (json.dumps(job), job["job_id"]))
    elif change == "profile":
        monkeypatch.setenv("FORGE_OPERATIONS_PROFILE", "foreign-profile")
    elif change == "foreign-owner":
        with p.store.tx() as c:
            c.execute("UPDATE afo_resource_ownership SET holder='foreign' WHERE resource='inference'")
    elif change == "unknown-native":
        monkeypatch.setattr(LL.ShellHost, "fabro_runs", lambda self: [{"id": "unknown", "lifecycle": {}}])
    monkeypatch.setattr(ST, "_stop", lambda *a, **kw: pytest.fail("refusal reached a service effect"))
    before = p.intent.path.read_bytes()
    with LL.gpu_lock(p.cfg.gpu_lock), LL.held_stack_lock(p.s["root"]):
        if change == "missing-lock":
            monkeypatch.setattr(LL, "flock_holders", lambda path: set())
        with pytest.raises(Refused, match=code):
            ST._locked_stop(p.s)
    assert p.intent.path.read_bytes() == before


def test_prelaunch_serve_swaps_real_cpu_workers_in_managed_namespace_under_own_lease(claimed, tmp_path, monkeypatch):
    """Transport substitute is an actual HTTP server; no model or GPU is emulated as qualification."""
    import copy
    import socket

    from forge_factory.afo.durable import digest, immutable_json
    from forge_factory.lrtx import provider_process as provider
    from test_da014_provider_process import provider as private_namespace

    p = claimed
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        gateway_port = listener.getsockname()[1]
    script = tmp_path / "llama-server-control.py"
    script.write_text("""
import argparse,json
from http.server import BaseHTTPRequestHandler,HTTPServer
ap=argparse.ArgumentParser();ap.add_argument('--alias');ap.add_argument('--port',type=int);a=ap.parse_args()
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  body=json.dumps({'data':[{'id':a.alias}]} if self.path=='/v1/models' else {'admission':{'inflight':0,'waiting':0}}).encode()
  self.send_response(200);self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
HTTPServer.allow_reuse_address=True
HTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
""")
    profile = copy.deepcopy(p.s["profile"])
    first, second = "qwen3.6:35b-a3b", "gpt-oss:20b"
    # CPU backend declarations only; real model pins/capabilities are not exercised by this test.
    profile["runtime"]["llama_server"] = {"model": first, "vram_required_mib": 0}
    profile["runtime"]["llama_server_alternates"] = {second: {"vram_required_mib": 0}}
    p.s["profile"] = profile
    p.s["ports"] = p.s["ports"] | {"llama": port, "gateway": gateway_port}
    (p.s["root"] / "logs").mkdir()
    monkeypatch.setattr(ST, "envmap", lambda s: dict(os.environ) | {"FORGE_VENV": str(Path(sys.executable).parent.parent)})
    monkeypatch.setattr(ST, "_vram_free_mib", lambda: 100000)
    monkeypatch.setattr(ST, "llama_server_spec", lambda r, prof, ports, env, model=None:
                        ([sys.executable, str(script), "--alias", model or first, "--port", str(port)], dict(os.environ),
                         f"http://127.0.0.1:{port}/health", [model or first]))
    processes = []
    original_spawn = ST._in_ns

    def actual_spawn(*args, **kwargs):
        assert kwargs.get("serving"), "managed worker must enter private provider PID namespace"
        child = original_spawn(*args, **kwargs)
        processes.append(child)
        return child

    monkeypatch.setattr(ST, "_in_ns", actual_spawn)
    before = p.intent.path.read_bytes()
    try:
        with private_namespace(tmp_path, "managed-cpu-transport", network=True) as base:
            instance = provider.capture(p.s["root"], profile=profile["id"], profile_sha256=profile["_sha256"],
                                        parent_pid=base["parent_pid"])
            subprocess.run(ST._nsenter(instance["init_pid"]) + ["ip", "link", "set", "lo", "up"], check=True,
                           capture_output=True)
            immutable_json(p.s["root"] / "run/provider-instances" / (digest(instance) + ".json"), instance)
            ST._save_services(p.s["root"], {"processes": {}, "serving_instance": instance})
            inner_code = """
import copy,json,os,sys
from pathlib import Path
from forge_factory.lrtx import provider_process as P
from forge_factory.afo.durable import Refused
v=json.loads(Path(sys.argv[1]).read_text());P.require_live_instance(v)
bad=copy.deepcopy(v);bad['init_owner_view']['uid_map'][0][1]+=1
try:P.require_live_instance(bad)
except Refused:pass
else:raise AssertionError('changed UID mapping accepted')
print(json.dumps({'mapped_owner_verified':True,'current_uid':os.getuid(),'captured_uid':v['init']['uid']}))
"""
            inner = subprocess.run(ST._nsenter(instance["init_pid"]) + [sys.executable, "-c", inner_code,
                                   str(p.s["root"] / "run/provider-instances" / (digest(instance) + ".json"))],
                                   env=dict(os.environ), capture_output=True, text=True, check=True)
            mapped = json.loads(inner.stdout)
            assert mapped["mapped_owner_verified"] and mapped["current_uid"] == 0
            monkeypatch.setattr(ST, "_holder", lambda s: instance["init_pid"])
            gateway = actual_spawn(instance["init_pid"], [sys.executable, str(script), "--alias", "gateway-control",
                                   "--port", str(gateway_port)], dict(os.environ), p.s["root"] / "logs/gateway.log",
                                   p.s["root"], serving=instance)
            import time

            until = time.monotonic() + 5
            while True:
                try:
                    response = ST._get(f"http://127.0.0.1:{gateway_port}/health", instance["init_pid"], ST.envmap(p.s), False)
                    if response:
                        break
                    raise OSError("isolated gateway not ready")
                except OSError:
                    if gateway.poll() is not None or time.monotonic() >= until:
                        pytest.fail("isolated CPU gateway did not start")
                    time.sleep(0.02)
            with LL.gpu_lock(p.cfg.gpu_lock), LL.held_stack_lock(p.s["root"]):
                assert ST.serve(p.s, first)["result"] == "SWAPPED"
                record = json.loads((p.s["root"] / "run/services.json").read_text())["processes"]["llama_server"]
                assert record["worker"]["pid"] != record["pid"]  # actual worker, not nsenter waiter
                assert record["worker"]["identity"]["pid_namespace"] == instance["init"]["pid_namespace"]
                assert ST.serve(p.s, second)["result"] == "SWAPPED"
                assert provider.identity(record["worker"]["pid"]) is None
                assert ST.serve(p.s, second)["result"] == "ALREADY_SERVED"
                # Expire a real claimed job during the model-stop/VRAM wait;
                # the exact worker may already be retired, but no replacement can start.
                before_spawn_count = len(processes)
                job = P.registered(p.store, P.job_id(p.aid))
                real_clock, real_sleep = A.time.time, ST.time.sleep
                free_calls = [0]

                def free_memory():
                    free_calls[0] += 1
                    return 0 if free_calls[0] <= 2 else 100000

                def expire_during_wait(delay):
                    monkeypatch.setattr(A.time, "time", lambda: job["deadline_epoch"] + 1)
                    real_sleep(0.02)

                profile["runtime"]["llama_server"]["vram_required_mib"] = 5
                monkeypatch.setattr(ST, "_vram_free_mib", free_memory)
                monkeypatch.setattr(ST.time, "sleep", expire_during_wait)
                try:
                    with pytest.raises(Refused, match="EFFECT_AUTHORITY_EXPIRED_OR_CHANGED"):
                        ST.serve(p.s, first)
                    assert len(processes) == before_spawn_count
                finally:
                    monkeypatch.setattr(A.time, "time", real_clock)
                    monkeypatch.setattr(ST.time, "sleep", real_sleep)
                assert ST._EFFECT_GUARD.get() is None
            assert p.intent.path.read_bytes() == before
            assert Executions(p.store).get(P.job_id(p.aid))["resource_lease"] == "HELD"
    finally:
        for process in processes:
            process.wait(timeout=5)


def test_effect_guard_refuses_expired_job_and_resets_after_exception(claimed, monkeypatch):
    p = claimed
    job = P.registered(p.store, P.job_id(p.aid))
    from forge_factory.afo import line_recovery_worker as worker

    permissions = [True]
    monkeypatch.setattr(worker, "bound_order", lambda *a, **kw: {"grant": SimpleNamespace(
        permit=lambda *a, **kw: SimpleNamespace(allow=permissions[0]))})
    with LL.gpu_lock(p.cfg.gpu_lock), LL.held_stack_lock(p.s["root"]):
        with A.fenced(p.s, "start") as guard:
            with ST.line_effect_guard(guard):
                ST._guard_effect()
                permissions[0] = False
                with pytest.raises(Refused, match="ACTION_NOT_AUTHORIZED"):
                    ST._guard_effect()
                permissions[0] = True
                real_clock = A.time.time
                monkeypatch.setattr(A.time, "time", lambda: job["deadline_epoch"] + 1)
                with pytest.raises(Refused, match="EFFECT_AUTHORITY_EXPIRED_OR_CHANGED"):
                    ST._guard_effect()
                monkeypatch.setattr(A.time, "time", real_clock)
    assert ST._EFFECT_GUARD.get() is None
    ST._guard_effect()  # unchanged ordinary backend has no stale context callback


@pytest.mark.parametrize("wrong_nonce", [False, True])
def test_first_graph_serve_uses_existing_authoritative_nonce_adoption_before_detach_receipt(claimed, monkeypatch, wrong_nonce):
    from forge_factory.afo.line_product_context import capture
    from forge_factory.afo.product_job import install

    p = claimed
    job = P.registered(p.store, P.job_id(p.aid))
    ws = Path(job["workspace"])
    run = ws / ".forge-run"
    run.mkdir(parents=True, exist_ok=True)
    model = job["model"]
    (run / "workflow.fabro").write_text('digraph g {\n'
        + f'  author [prompt="test", model="{model}"]\n'
        + f'  author_serve [script="python -m forge_factory.lrtx.stack serve --model {model}"]\n'
        + '  author_serve -> author [condition="outcome=succeeded"]\n}\n')
    (run / "binding.json").write_text(json.dumps({"workspace": str(ws), "nodes": {"author": {"role": "swe3-author"}}}))
    (run / "model-profile.json").write_text(json.dumps({"default": model}))
    install(ws, {k: job[k] for k in ("job_id", "nonce", "mission_id", "order_id", "attempt_id", "operations_epoch")})
    job["line_product_context"] = capture(ws, job, p.s["profile"])
    with p.store.tx() as c:
        c.execute("UPDATE afo_product_jobs SET record=? WHERE job_id=?", (json.dumps(job), job["job_id"]))
    ex = Executions(p.store)
    ex._save_evidence(job["job_id"], "PRODUCT_NATIVE_SUBMIT_INTENT", {"job_id": job["job_id"], "nonce": job["nonce"],
                     "role_context": job["line_product_context"], "source_revision": job["factory_revision"]["commit"]})
    native = {"id": "OWN-NATIVE", "labels": {"afo_agent": job["job_id"],
              "afo_nonce": "foreign-nonce" if wrong_nonce else job["nonce"]}, "source_directory": str(ws),
              "lifecycle": {"status": {"kind": "running"}}}
    monkeypatch.setattr(LL.ShellHost, "fabro_runs", lambda self: [native])
    from contextlib import contextmanager

    @contextmanager
    def client(self):
        yield SimpleNamespace(get_run=lambda rid: native)

    monkeypatch.setattr(LL.ShellHost, "_client", client)
    monkeypatch.setattr(LL.ShellHost, "fabro_run", lambda self, rid: native)
    from forge_factory.lrtx import provider_process as provider

    ST._save_services(p.s["root"], {"processes": {"fabro": {"pid": os.getpid(),
                       "identity": ST.process_identity(os.getpid()), "owner_view": provider.owner_view(os.getpid())}}})
    before = MissionLedger(p.store).snapshot("fixture-mission")
    execution = ex.get(job["job_id"])
    assert execution["native_run_ids"] == []
    if wrong_nonce:
        with pytest.raises(Refused, match="NATIVE_IDENTITY_CHANGED"):
            A._native_handoff(p.cfg, p.store, job, execution, ws, model, p.s)
        assert ex.get(job["job_id"])["native_run_ids"] == []
    else:
        current = A._native_handoff(p.cfg, p.store, job, execution, ws, model, p.s)
        assert current["native_run_ids"] == ["OWN-NATIVE"] and current["identity_state"] == "CONFIRMED"
        assert current["resource_lease"] == "HELD" and current["lease_epoch"] == execution["lease_epoch"]
        with A.fenced(p.s, "serve", model=model, workspace=ws) as guard:
            guard()  # fresh permission can be checked with the ledger write fence held
            assert Executions(p.store).store.path == p.store.path  # same durable store
    assert MissionLedger(p.store).snapshot("fixture-mission") == before


def test_inside_observer_uses_only_pinned_namespace_fabro_port(claimed, tmp_path):
    from forge_factory.lrtx import provider_process as provider
    from test_da014_provider_process import provider as private_namespace

    p = claimed
    with private_namespace(tmp_path, "observer-net", network=True) as instance:
        record = {"root": str(p.s["root"]), "profile": p.s["profile"]["id"],
                  "profile_sha256": p.s["profile"]["_sha256"], "processes": {},
                  "holder_pid": instance["init_pid"], "holder_identity": ST.process_identity(instance["init_pid"]),
                  "netns": os.readlink(f"/proc/{instance['init_pid']}/ns/net")}
        ST._save_services(p.s["root"], record)
        assert A._observation_host(p.cfg, p.s).cfg.fabro_host_port == p.cfg.fabro_host_port
        code = """
import json,sys
from pathlib import Path
from forge_factory.afo.line_launcher import LineConfig
from forge_factory.afo.line_stack_lifecycle import _observation_host
from forge_factory.lrtx.profile import load
root=Path(sys.argv[1]);profile=load(sys.argv[2]);s={'root':root,'profile':profile,'ports':profile['deployment']['ports']}
cfg=LineConfig(stack_root=root,fabro_host_port=43210)
assert _observation_host(cfg,s).cfg.fabro_host_port==s['ports']['fabro']
print(json.dumps({'inside_port':_observation_host(cfg,s).cfg.fabro_host_port,'host_port':cfg.fabro_host_port}))
"""
        report = subprocess.run(ST._nsenter(instance["init_pid"]) + [sys.executable, "-c", code,
                                str(p.s["root"]), p.s["profile"]["id"]], env=dict(os.environ), capture_output=True,
                                text=True, check=True)
        assert json.loads(report.stdout)["inside_port"] == p.s["ports"]["fabro"]
        assert provider.quiet(instance) is None
