"""Private read-only guard controls. Authority/systemd/NVIDIA leaves are explicit fixtures."""

import copy
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from forge_factory.afo import owner_launch_guard as G
from forge_factory.afo.durable import Refused, digest
from forge_factory.lrtx import provider_process as P
from test_da014_provider_process import provider


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path


@pytest.fixture
def environment(tmp_path, monkeypatch):
    root = tmp_path / "stack"
    (root / "state/supervisor").mkdir(parents=True)
    queue = tmp_path / "gpuq"
    for name in ["pending", "running"]:
        (queue / name).mkdir(parents=True)
    intents = {str(tmp_path / "first.json"): "", str(tmp_path / "second.json"): ""}
    for i, p in enumerate(intents):
        Path(p).write_text(str(i))
        intents[p] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    monkeypatch.setattr(G, "LEGACY_QUEUE", str(queue))
    monkeypatch.setattr(G, "LEGACY_INTENTS", intents)
    context = dict(user_namespace=os.readlink("/proc/self/ns/user"), uid_map=[[0, 0, 4294967295]])
    intent = put(tmp_path / "operations-intent.json", dict(mode="RUNNING", epoch=1, control_context=context))
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent))
    record = {
        "guardian": {k: v for k, v in P.identity(os.getpid()).items() if k != "state"},
        "control_context": context,
        "intent_epoch": 1,
        "expiry_ticket": dict(remote_boot_id=P.boot_id(), deadline_monotonic=time.monotonic() + 300),
        "expiry_boottime_deadline": time.clock_gettime(time.CLOCK_BOOTTIME) + 300,
        "guardian_pid": os.getpid(),
        "profile": "fixture",
        "profile_sha256": "a" * 64,
        "source_revisions": ["b" * 40],
        "store_path": str(root / "state/supervisor/line-queue.sqlite3"),
    }
    ref = tmp_path / (digest(record) + ".json")
    put(ref, record)
    monkeypatch.setenv(G.D.FILE, str(ref))
    put(root / "state/supervisor/line-conductor.heartbeat", dict(pid=111, mode="OBSERVE", ok=True, epoch=time.time()))
    put(
        ref.with_suffix(".heartbeat.json"), dict(pid=os.getpid(), mode=G.D.MODE, acceptance="UNACCEPTED", at=time.time(), cycle=3)
    )
    cfg = dict(
        schema=G.SCHEMA,
        source_revision="b" * 40,
        root=str(root),
        profile="fixture",
        profile_sha256="a" * 64,
        production_unit=G.PRODUCTION_UNIT,
        production_invocation="1" * 32,
        owner_unit="forge-c-owner-development-fixture.service",
        gpu_queue=str(queue),
        intent_hashes=intents,
        heartbeat_max_age_seconds=180,
        guard_sha256=hashlib.sha256(Path(G.__file__).read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(G.D, "current", lambda: record)
    monkeypatch.setattr(G.C, "revision", lambda: dict(commit="b" * 40, dirty=False))
    monkeypatch.setattr(G, "_host_context", lambda: None)
    monkeypatch.setattr(
        G,
        "observe_worker",
        lambda settings, own_pid: 222 if own_pid == 221 else (_ for _ in ()).throw(Refused("WORKER_ARGUMENT_REBOUND")),
    )
    monkeypatch.setattr(G.ST, "settings", lambda profile: dict(root=root, profile=dict(id="fixture", _sha256="a" * 64)))

    class Probe:
        def __init__(self):
            self.gpu = {222}
            self.calls = 0

        def unit(self, name):
            self.calls += 1
            return dict(
                MainPID=str(111 if name == G.PRODUCTION_UNIT else os.getpid()),
                ActiveState="active",
                InvocationID="1" * 32 if name == G.PRODUCTION_UNIT else "2" * 32,
            )

        def gpu_pids(self):
            return self.gpu

    return cfg, record, Probe(), ref


def test_healthy_observe_and_current_development_accept_exact_actual_worker(environment):
    cfg, _, probe, _ = environment
    assert G.evaluate(cfg, 221, probe=probe)["worker_pid"] == 222


@pytest.mark.parametrize("which", ["pending", "running"])
def test_original_queue_predicates_retained(environment, which):
    cfg, _, probe, _ = environment
    Path(cfg["gpu_queue"], which, "job").touch()
    with pytest.raises(Refused, match="GPUQ_"):
        G.evaluate(cfg, 221, probe=probe)


@pytest.mark.parametrize("which", [0, 1])
def test_both_original_intent_hashes_retained(environment, which):
    cfg, _, probe, _ = environment
    Path(list(cfg["intent_hashes"])[which]).write_text("changed")
    with pytest.raises(Refused, match="LEGACY_INTENT_CHANGED"):
        G.evaluate(cfg, 221, probe=probe)


@pytest.mark.parametrize(
    "mutation",
    [{"mode": "PILOT"}, {"mode": "ACT"}, {"ok": False}, {"pid": 999}, {"epoch": 0}, {"epoch": float("nan")}, {"epoch": True}],
)
def test_wrong_stale_production_heartbeat_refuses(environment, mutation):
    cfg, _, probe, _ = environment
    p = Path(cfg["root"]) / "state/supervisor/line-conductor.heartbeat"
    d = json.loads(p.read_text())
    d.update(mutation)
    put(p, d)
    with pytest.raises(Refused, match="PRODUCTION_HEARTBEAT|NONFINITE_JSON"):
        G.evaluate(cfg, 221, probe=probe)


@pytest.mark.parametrize(
    "mutation", [{"mode": "PILOT"}, {"acceptance": "ACCEPTED"}, {"pid": 999}, {"at": 0}, {"at": float("inf")}, {"at": True}]
)
def test_wrong_stale_development_heartbeat_refuses(environment, mutation):
    cfg, _, probe, ref = environment
    p = ref.with_suffix(".heartbeat.json")
    d = json.loads(p.read_text())
    d.update(mutation)
    put(p, d)
    with pytest.raises(Refused, match="OWNER_HEARTBEAT|NONFINITE_JSON"):
        G.evaluate(cfg, 221, probe=probe)


@pytest.mark.parametrize("gpu", [{223}, {222, 223}, {0}, {"unknown"}])
def test_foreign_or_unknown_gpu_never_accepted(environment, gpu):
    cfg, _, probe, _ = environment
    probe.gpu = gpu
    with pytest.raises(Refused, match="GPU"):
        G.evaluate(cfg, 221, probe=probe)


def test_probe_errors_are_not_empty_gpu(environment):
    cfg, _, probe, _ = environment

    def fail():
        raise OSError("fixture probe unavailable")

    probe.gpu_pids = fail
    with pytest.raises(OSError):
        G.evaluate(cfg, 221, probe=probe)


def test_guardian_exit_STOP_or_expiry_remains_normal_authority_failure(environment, monkeypatch):
    cfg, _, probe, _ = environment
    monkeypatch.setattr(G.D, "current", lambda: (_ for _ in ()).throw(Refused("OWNER_DEVELOPMENT_INTENT_FENCED")))
    with pytest.raises(Refused, match="INTENT_FENCED"):
        G.evaluate(cfg, 221, probe=probe)


def test_authority_loss_after_blocking_probe_refuses(environment, monkeypatch):
    cfg, record, probe, _ = environment
    calls = []

    def current():
        calls.append(1)
        if len(calls) > 1:
            raise Refused("OWNER_DEVELOPMENT_GUARDIAN_ATTESTATION_UNAVAILABLE")
        return record

    monkeypatch.setattr(G.D, "current", current)
    with pytest.raises(Refused, match="ATTESTATION_UNAVAILABLE"):
        G.evaluate(cfg, 221, probe=probe)


def test_unit_replacement_during_probe_refuses(environment):
    cfg, _, probe, _ = environment
    original = probe.unit

    def unit(name):
        out = original(name)
        if probe.calls > 2:
            out["InvocationID"] = "3" * 32
        return out

    probe.unit = unit
    with pytest.raises(Refused, match="UNIT_CHANGED"):
        G.evaluate(cfg, 221, probe=probe)


@pytest.mark.parametrize(
    "field,value", [("source_revision", "c" * 40), ("profile", "other"), ("profile_sha256", "c" * 64), ("root", "/tmp/foreign")]
)
def test_source_profile_and_canonical_store_scope_refuses(environment, field, value):
    cfg, _, probe, _ = environment
    cfg[field] = value
    with pytest.raises(Refused):
        G.evaluate(cfg, 221, probe=probe)


def test_arbitrary_waiter_argument_is_not_an_owner_token(environment):
    cfg, _, probe, _ = environment
    with pytest.raises(Refused, match="WORKER_ARGUMENT"):
        G.evaluate(cfg, 999, probe=probe)


def test_configuration_hash_and_protected_predicates(environment, tmp_path, monkeypatch):
    cfg, _, _, _ = environment
    parent = tmp_path / "owner-launch-guards"
    parent.mkdir(mode=0o700)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(tmp_path / "operations-intent.json"))
    p = put(parent / "config.json", cfg)
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert G.load_config(p, h) == cfg
    with pytest.raises(Refused, match="CONFIG"):
        G.load_config(p, "0" * 64)
    cfg["intent_hashes"] = {}
    put(p, cfg)
    with pytest.raises(Refused, match="CONFIG"):
        G.load_config(p, hashlib.sha256(p.read_bytes()).hexdigest())


def test_gpu_command_unknown_output_refuses(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "not-a-pid\n", ""))
    with pytest.raises(Refused, match="GPU_PROBE"):
        G.Probe().gpu_pids()


def test_real_private_worker_waiter_identity_and_pid_reuse(tmp_path, monkeypatch):
    # Actual harmless USER/MNT/PID graph; no model, GPU, systemd, or host services.
    with provider(tmp_path, "guard-provider") as instance:
        argv = ["sleep", "60"]
        parent = instance["parent_pid"]
        worker = P.capture_worker(instance, parent, argv)
        root = Path(instance["root"])
        put(
            root / "run/services.json",
            dict(serving_instance=instance, processes={"llama_server": dict(pid=parent, argv=argv, worker=worker)}),
        )
        proof = root / "run/provider-instances" / (digest(instance) + ".json")
        put(proof, instance)
        settings = dict(root=root, profile=dict(id="fixture", _sha256="a" * 64))
        monkeypatch.setattr(G.D, "require_compatible_provider", lambda instance: None)
        before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert G.observe_worker(settings, parent) == worker["pid"] and worker["pid"] != parent
        assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        with pytest.raises(Refused, match="WORKER_ARGUMENT"):
            G.observe_worker(settings, parent + 100000)
        real = P.identity

        def reused(pid):
            d = real(pid)
            return {**d, "start_ticks": str(int(d["start_ticks"]) + 1)} if pid == worker["pid"] else d

        monkeypatch.setattr(P, "identity", reused)
        with pytest.raises(Refused, match="WORKER_KERNEL"):
            G.observe_worker(settings, parent)


def test_worker_proof_tamper_is_not_live_ownership(tmp_path, monkeypatch):
    with provider(tmp_path, "tamper") as instance:
        argv = ["sleep", "60"]
        parent = instance["parent_pid"]
        worker = P.capture_worker(instance, parent, argv)
        root = Path(instance["root"])
        put(
            root / "run/services.json",
            dict(serving_instance=instance, processes={"llama_server": dict(pid=parent, argv=argv, worker=worker)}),
        )
        put(root / "run/provider-instances" / (digest(instance) + ".json"), instance)
        proof = root / "run/provider-workers" / (digest(worker) + ".json")
        proof.chmod(0o600)
        proof.write_text("{}")
        monkeypatch.setattr(G.D, "require_compatible_provider", lambda instance: None)
        with pytest.raises(Refused):
            G.observe_worker(dict(root=root, profile=dict(id="fixture", _sha256="a" * 64)), parent)


def test_queue_mutation_during_gpu_probe_is_not_accepted(environment):
    cfg, _, probe, _ = environment

    def gpu():
        Path(cfg["gpu_queue"], "pending", "arrived").touch()
        return {222}

    probe.gpu_pids = gpu
    with pytest.raises(Refused, match="GPUQ_PENDING"):
        G.evaluate(cfg, 221, probe=probe)


def test_intent_mutation_during_gpu_probe_is_not_accepted(environment):
    cfg, _, probe, _ = environment

    def gpu():
        Path(next(iter(cfg["intent_hashes"]))).write_text("changed during probe")
        return {222}

    probe.gpu_pids = gpu
    with pytest.raises(Refused, match="LEGACY_INTENT"):
        G.evaluate(cfg, 221, probe=probe)


def test_private_guard_config_cannot_live_in_agent_worktree(environment, tmp_path, monkeypatch):
    cfg, _, _, _ = environment
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(tmp_path / "operations-intent.json"))
    p = put(tmp_path / "untrusted" / "config.json", cfg)
    with pytest.raises(Refused, match="CONFIG_PRIVATE_LOCATION"):
        G.load_config(p, hashlib.sha256(p.read_bytes()).hexdigest())


def test_guard_missing_gpu_queue_is_unknown(environment):
    cfg, _, probe, _ = environment
    Path(cfg["gpu_queue"], "pending").rmdir()
    with pytest.raises(Refused, match="GPU_QUEUE_UNKNOWN"):
        G.evaluate(cfg, 221, probe=probe)


def test_real_outer_observer_worker_proof_is_readonly_on_host(tmp_path, monkeypatch):
    # Actual host->outerUSER/NET->nestedUSER/MNT/PID composition. Authority is
    # the sole explicit fixture leaf; all provider/worker/proc evidence is real.
    import signal
    import sys

    from forge_factory.lrtx import stack as ST

    root = tmp_path / "outer"
    root.mkdir()
    processes = []
    instance = None
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        outer = subprocess.Popen(
            ["unshare", "--user", "--map-root-user", "--net", "--fork", "sleep", "60"], start_new_session=True
        )
        processes.append(outer)
        until = time.monotonic() + 4
        holder = None
        while time.monotonic() < until:
            assert outer.poll() is None
            children = Path(f"/proc/{outer.pid}/task/{outer.pid}/children").read_text().split()
            if children:
                holder = int(children[0])
                break
            time.sleep(0.01)
        assert holder
        command = [
            "bwrap",
            "--bind",
            "/",
            "/",
            "--dev-bind",
            "/dev",
            "/dev",
            "--unshare-user",
            "--unshare-pid",
            "--as-pid-1",
            "--new-session",
            "--die-with-parent",
            "--proc",
            "/proc",
            "--",
            "sleep",
            "60",
        ]
        parent = ST._in_ns(holder, command, env, root / "provider.log", root)
        processes.append(parent)
        until = time.monotonic() + 4
        while True:
            assert parent.poll() is None
            try:
                instance = P.capture(root, profile="fixture", profile_sha256="a" * 64, parent_pid=parent.pid, outer_pid=holder)
                break
            except Refused:
                if time.monotonic() > until:
                    raise
                time.sleep(0.01)
        put(root / "instance.json", instance)
        script = root / "capture-outer.py"
        script.write_text("""import json,time,sys,os
from pathlib import Path
from forge_factory.lrtx import stack as ST,provider_process as P
root=Path(sys.argv[1]);instance=json.loads((root/'instance.json').read_text());holder=int(sys.argv[2]);env=dict(os.environ)
p=ST._in_ns(holder,['sleep','60'],env,root/'worker.log',root,serving=instance)
w=P.capture_worker(instance,p.pid,['sleep','60'])
(root/'worker.json').write_text(json.dumps(w))
p.wait(timeout=60)
""")
        app = subprocess.Popen(
            [
                "nsenter",
                "-t",
                str(holder),
                "-U",
                "-n",
                "--preserve-credentials",
                sys.executable,
                str(script),
                str(root),
                str(holder),
            ],
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=(root / "app.log").open("wb"),
        )
        processes.append(app)
        until = time.monotonic() + 5
        while not (root / "worker.json").is_file():
            assert app.poll() is None, (root / "app.log").read_text()
            assert time.monotonic() < until
            time.sleep(0.01)
        worker = json.loads((root / "worker.json").read_text())
        assert worker["identity"]["uid"] == 0
        assert worker["observer_user_namespace"] == instance["outer_holder"]["owner_view"]["user_namespace"]
        put(root / "run/provider-instances" / (digest(instance) + ".json"), instance)
        put(
            root / "run/services.json",
            dict(
                serving_instance=instance,
                processes={"llama_server": dict(pid=worker["parent_pid"], argv=["sleep", "60"], worker=worker)},
            ),
        )
        settings = dict(root=root, profile=dict(id="fixture", _sha256="a" * 64))
        monkeypatch.setattr(G.D, "require_compatible_provider", lambda instance: None)
        before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert G.observe_worker(settings, worker["parent_pid"]) == worker["pid"]
        assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        # A UID0 proof from an unrelated observer cannot use this translation.
        bad = copy.deepcopy(worker)
        bad["observer_user_namespace"] = "user:[999999999]"
        put(root / "run/provider-workers" / (digest(bad) + ".json"), bad)
        put(
            root / "run/services.json",
            dict(
                serving_instance=instance,
                processes={"llama_server": dict(pid=bad["parent_pid"], argv=["sleep", "60"], worker=bad)},
            ),
        )
        with pytest.raises(Refused, match="WORKER_OBSERVER_UNPROVEN"):
            G.observe_worker(settings, bad["parent_pid"])
    finally:
        if instance:
            P.stop(instance, fenced_effect=lambda effect: effect())
        for p in reversed(processes):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=5)


@pytest.mark.parametrize("revision", [dict(commit="c" * 40, dirty=False), dict(commit="b" * 40, dirty=True)])
def test_other_allowed_or_dirty_runtime_cannot_rebind_config(environment, monkeypatch, revision):
    cfg, record, probe, _ = environment
    record["source_revisions"].append("c" * 40)
    monkeypatch.setattr(G.C, "revision", lambda: revision)
    with pytest.raises(Refused, match="EXACT_RUNTIME_REVISION"):
        G.evaluate(cfg, 221, probe=probe)


def test_authority_loss_during_last_worker_walk_refuses(environment, monkeypatch):
    cfg, record, probe, _ = environment
    walks = []
    calls = []

    def worker(settings, pid):
        walks.append(1)
        return 222

    def current():
        calls.append(1)
        if len(walks) >= 2:
            raise Refused("OWNER_DEVELOPMENT_GUARDIAN_ATTESTATION_UNAVAILABLE")
        return record

    monkeypatch.setattr(G, "observe_worker", worker)
    monkeypatch.setattr(G.D, "current", current)
    with pytest.raises(Refused, match="ATTESTATION_UNAVAILABLE"):
        G.evaluate(cfg, 221, probe=probe)
    assert len(walks) == 2 and len(calls) == 3


def test_STOP_during_last_worker_walk_refuses_even_if_current_leaf_returns(environment, monkeypatch):
    cfg, _, probe, _ = environment
    walks = []

    def worker(settings, pid):
        walks.append(1)
        if len(walks) == 2:
            p = Path(os.environ["FORGE_OPERATIONS_INTENT"])
            d = json.loads(p.read_text())
            d["mode"] = "STOPPED"
            put(p, d)
        return 222

    monkeypatch.setattr(G, "observe_worker", worker)
    with pytest.raises(Refused, match="FINAL_INTENT_FENCED"):
        G.evaluate(cfg, 221, probe=probe)


def test_guardian_loss_after_last_current_leaf_refuses(environment, monkeypatch):
    cfg, _, probe, _ = environment
    monkeypatch.setattr(G.D, "guardian_alive", lambda record: False)
    with pytest.raises(Refused, match="FINAL_GUARDIAN_ENDED"):
        G.evaluate(cfg, 221, probe=probe)


@pytest.mark.parametrize("clock", ["monotonic", "boottime"])
def test_deadline_crossing_during_last_worker_walk_refuses(environment, monkeypatch, clock):
    from types import SimpleNamespace

    cfg, record, probe, _ = environment
    walks = []
    real = time
    expired = [False]
    facade = SimpleNamespace(
        time=real.time,
        CLOCK_BOOTTIME=real.CLOCK_BOOTTIME,
        monotonic=lambda: (
            record["expiry_ticket"]["deadline_monotonic"] + 1 if expired[0] and clock == "monotonic" else real.monotonic()
        ),
        clock_gettime=lambda c: (
            record["expiry_boottime_deadline"] + 1 if expired[0] and clock == "boottime" else real.clock_gettime(c)
        ),
    )

    def worker(settings, pid):
        walks.append(1)
        if len(walks) == 2:
            expired[0] = True
        return 222

    monkeypatch.setattr(G, "time", facade)
    monkeypatch.setattr(G, "observe_worker", worker)
    with pytest.raises(Refused, match="FINAL_ACTUAL_UTC_DEADLINE_EXPIRED"):
        G.evaluate(cfg, 221, probe=probe)
    assert len(walks) == 2
