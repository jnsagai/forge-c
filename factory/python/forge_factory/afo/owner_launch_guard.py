"""Explicit read-only OS-owner development launch guard; legacy/default guards stay unchanged.

This host artifact imports normal authority/provider APIs from the explicitly
selected runtime source. It never issues authority, captures workers, signals a
process, opens a writable Store or makes model calls.
"""

import argparse
import hashlib
import math
import os
import re
import subprocess
import time
from pathlib import Path

from forge_factory.afo import line_recovery_control as C
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, digest, strict_json
from forge_factory.lrtx import provider_process as P
from forge_factory.lrtx import stack as ST

SCHEMA = "forge-c/owner-development-launch-guard/1"
PRODUCTION_UNIT = "forge-line-conductor-local.service"
LEGACY_QUEUE = "/mnt/data/forge-c/inspector-014-b309039/gpuq"
LEGACY_INTENTS = dict(
    zip(
        (
            "/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/operations.json",
            "/home/omniverse2/.local/state/forge-c-production-014/operations.json",
        ),
        (
            "9eff2df365375ae5eeae327dcd2bfefb440f14d100196a6dc1caee5b28f4d545",
            "1387fbb25538882a981b90ec6169f563dd88b4e0943ce49c402f59f90947e63c",
        ),
        strict=True,
    )
)
FIELDS = {
    "schema",
    "source_revision",
    "root",
    "profile",
    "profile_sha256",
    "production_unit",
    "production_invocation",
    "owner_unit",
    "gpu_queue",
    "intent_hashes",
    "heartbeat_max_age_seconds",
    "guard_sha256",
}


def need(ok, code):
    if not ok:
        raise Refused(code)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_json(path, maximum=65536):
    need(not path.is_symlink() and path.is_file(), "GUARD_FILE_UNAVAILABLE")
    s = path.stat()
    need(s.st_uid == os.getuid() and not s.st_mode & 0o022, "GUARD_FILE_OWNER_OR_MODE")
    return strict_json(path.read_bytes(), maximum)


def load_config(path, expected):
    from forge_factory.afo.operations import Intent

    parent = Intent().path.parent / "owner-launch-guards"
    need(
        path.parent == parent
        and not parent.is_symlink()
        and parent.is_dir()
        and parent.stat().st_uid == os.getuid()
        and not parent.stat().st_mode & 0o077,
        "GUARD_CONFIG_PRIVATE_LOCATION_REQUIRED",
    )
    need(isinstance(expected, str) and re.fullmatch("[0-9a-f]{64}", expected), "GUARD_CONFIG_HASH")
    cfg = checked_json(path)
    need(sha(path) == expected and isinstance(cfg, dict) and set(cfg) == FIELDS, "GUARD_CONFIG_CHANGED")
    need(
        cfg["schema"] == SCHEMA
        and cfg["intent_hashes"] == LEGACY_INTENTS
        and cfg["gpu_queue"] == LEGACY_QUEUE
        and cfg["production_unit"] == PRODUCTION_UNIT
        and cfg["heartbeat_max_age_seconds"] == 180
        and cfg["guard_sha256"] == sha(Path(__file__))
        and re.fullmatch("[0-9a-f]{40}", str(cfg["source_revision"]))
        and re.fullmatch("[0-9a-f]{64}", str(cfg["profile_sha256"]))
        and re.fullmatch("[0-9a-f]{32}", str(cfg["production_invocation"]))
        and re.fullmatch(r"forge-c-owner-development-[a-zA-Z0-9_.-]+\.service", str(cfg["owner_unit"]))
        and Path(cfg["root"]).is_absolute(),
        "GUARD_CONFIG_SCOPE",
    )
    return cfg


def _host_context():
    need(
        os.getuid() == 1000 and Path("/proc/self/uid_map").read_text().split() == ["0", "0", "4294967295"],
        "GUARD_INITIAL_OS_OWNER_REQUIRED",
    )
    need(
        not any(os.environ.get(k) for k in ("FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING")),
        "GUARD_AGENT_CONTEXT_REFUSED",
    )


class Probe:
    def unit(self, name):
        result = subprocess.run(
            ["systemctl", "--user", "show", name, "-p", "MainPID", "-p", "ActiveState", "-p", "InvocationID"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        need(result.returncode == 0 and len(result.stdout) < 4096, "GUARD_UNIT_PROBE_UNKNOWN")
        out = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        need(set(out) == {"MainPID", "ActiveState", "InvocationID"}, "GUARD_UNIT_PROBE_UNKNOWN")
        return out

    def gpu_pids(self):
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        lines = result.stdout.splitlines()
        need(result.returncode == 0 and len(result.stdout) <= 8192 and len(lines) <= 256, "GUARD_GPU_PROBE_UNKNOWN")
        need(all(re.fullmatch(r"[1-9][0-9]*", s.strip()) for s in lines), "GUARD_GPU_PROBE_UNKNOWN")
        return {int(s.strip()) for s in lines}


def heartbeat(path, pid, mode, timestamp, code, now):
    d = checked_json(path)
    age = d.get(timestamp)
    need(type(d.get("pid")) is int and d["pid"] == pid and d.get("mode") == mode, code + "_IDENTITY_CHANGED")
    need((d.get("ok") is True if mode == "OBSERVE" else d.get("acceptance") == "UNACCEPTED"), code + "_UNHEALTHY")
    need(type(age) in (int, float) and math.isfinite(age) and 0 <= now - age <= 180, code + "_STALE_OR_INVALID")


def _same_identity(actual, expected, *, uid):
    return (
        actual
        and actual.get("state") != "Z"
        and actual.get("uid") == uid
        and all(actual.get(k) == expected.get(k) for k in ("boot_id", "start_ticks", "pid_namespace", "namespace_pid"))
    )


def observe_worker(settings, own_pid):
    """Verify existing immutable evidence and kernel identity; never capture/write a worker.

    Host-created proofs use the existing _bound_worker validator. An exact
    outer-observer proof may encode UID0; only captured v2 outer provenance maps
    that value back to this same OS owner's UID1000. No signal accepts this
    translation; normal provider signal/stop APIs are unchanged.
    """
    root = settings["root"]
    path = root / "run/services.json"
    raw = path.read_bytes()
    rec = checked_json(path)
    instance = ST.serving_instance(settings)
    P.require_live_instance(instance)
    D.require_compatible_provider(instance)
    pr = (rec.get("processes") or {}).get("llama_server") or {}
    worker = pr.get("worker") or {}
    argv = pr.get("argv")
    need(isinstance(argv, list) and argv and all(isinstance(a, str) and "\0" not in a for a in argv), "GUARD_WORKER_ARGV_INVALID")
    need(
        type(own_pid) is int
        and own_pid > 1
        and own_pid in (pr.get("pid"), worker.get("pid"))
        and worker.get("parent_pid") == pr.get("pid"),
        "GUARD_WORKER_ARGUMENT_REBOUND",
    )
    encoded = b"\0".join(os.fsencode(a) for a in argv) + b"\0"
    need(
        worker.get("schema") == "forge-c/managed-provider-worker/1"
        and worker.get("instance_sha256") == digest(instance)
        and worker.get("argv_sha256") == hashlib.sha256(encoded).hexdigest(),
        "GUARD_WORKER_BINDING_CHANGED",
    )
    observer = worker.get("observer_user_namespace")
    current = os.readlink("/proc/self/ns/user")
    if observer == current:
        P._bound_worker(instance, worker, argv)
        uid = os.getuid()
        need(
            worker.get("identity", {}).get("uid") == uid and worker.get("parent", {}).get("uid") == uid,
            "GUARD_WORKER_OWNER_CHANGED",
        )
    else:
        outer = instance.get("outer_holder") or {}
        view = outer.get("owner_view") or {}
        need(
            instance.get("schema") == "forge-c/managed-provider-instance/2"
            and instance.get("observer_user_namespace") == current
            and observer == view.get("user_namespace")
            and view.get("uid_map") == [[0, os.getuid(), 1]]
            and worker.get("identity", {}).get("uid") == 0
            and worker.get("parent", {}).get("uid") == 0,
            "GUARD_WORKER_OBSERVER_UNPROVEN",
        )
        actual_outer = P.identity(outer["pid"])
        need(
            _same_identity(actual_outer, outer["identity"], uid=os.getuid())
            and os.readlink(f"/proc/{outer['pid']}/ns/user") == observer
            and os.readlink(f"/proc/{outer['pid']}/ns/net") == outer["net_namespace"]
            and [list(map(int, r.split())) for r in Path(f"/proc/{outer['pid']}/uid_map").read_text().splitlines()]
            == view["uid_map"],
            "GUARD_WORKER_OUTER_OWNER_CHANGED",
        )
        proof = root / "run/provider-workers" / (digest(worker) + ".json")
        need(checked_json(proof, 16384) == worker, "GUARD_WORKER_EVIDENCE_CHANGED")
        uid = os.getuid()
    parent = P.identity(worker["parent_pid"])
    actual = P.identity(worker["pid"])
    need(
        _same_identity(parent, worker.get("parent") or {}, uid=uid)
        and _same_identity(actual, worker.get("identity") or {}, uid=uid)
        and actual["pid_namespace"] == instance["init"]["pid_namespace"]
        and Path(f"/proc/{worker['pid']}/cmdline").read_bytes() == encoded,
        "GUARD_WORKER_KERNEL_CHANGED",
    )
    # PID/start/argv observation must stay tied to the captured waiter's live descendants.
    pending, seen, found = [worker["parent_pid"]], set(), False
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        need(len(seen) <= 128, "GUARD_WORKER_DESCENDANT_BOUND")
        if pid == worker["pid"]:
            found = True
        pending.extend(int(x) for x in Path(f"/proc/{pid}/task/{pid}/children").read_text().split())
    need(
        found and path.read_bytes() == raw and P.identity(worker["pid"]) == actual and P.identity(worker["parent_pid"]) == parent,
        "GUARD_WORKER_KERNEL_OR_PROJECTION_CHANGED",
    )
    return worker["pid"]


def legacy_predicates(cfg):
    for directory in ("pending", "running"):
        path = Path(cfg["gpu_queue"]) / directory
        need(path.is_dir() and not path.is_symlink(), "GUARD_GPU_QUEUE_UNKNOWN")
        need(not any(path.iterdir()), "GUARD_GPUQ_" + directory.upper() + "_NOT_EMPTY")
    for path, expected in cfg["intent_hashes"].items():
        p = Path(path)
        need(not p.is_symlink() and p.is_file() and sha(p) == expected, "GUARD_LEGACY_INTENT_CHANGED")


def exact_runtime(cfg):
    revision = C.revision()
    need(
        revision.get("dirty") is False and revision.get("commit") == cfg["source_revision"],
        "GUARD_EXACT_RUNTIME_REVISION_CHANGED",
    )


def final_authority(record):
    """Lightweight current-host fence after normal authority's blocking reads."""
    from forge_factory.afo.operations import Intent

    state = Intent().read()
    need(D.guardian_alive(record), "GUARD_FINAL_GUARDIAN_ENDED")
    need(
        state.get("mode") == "RUNNING"
        and state.get("epoch") == record["intent_epoch"]
        and all(
            (state.get("control_context") or {}).get(k) == record["control_context"].get(k) for k in ("user_namespace", "uid_map")
        ),
        "GUARD_FINAL_INTENT_FENCED",
    )
    need(
        P.boot_id() == record["expiry_ticket"]["remote_boot_id"]
        and time.monotonic() < record["expiry_ticket"]["deadline_monotonic"]
        and time.clock_gettime(time.CLOCK_BOOTTIME) < record["expiry_boottime_deadline"],
        "GUARD_FINAL_ACTUAL_UTC_DEADLINE_EXPIRED",
    )


def evaluate(cfg, own_pid, *, probe=None):
    _host_context()
    exact_runtime(cfg)
    record = D.current()  # Normal readonly canonical Store/kernel/socket/source/policy/accounting checks.
    need(
        cfg["source_revision"] in record["source_revisions"]
        and cfg["profile"] == record["profile"]
        and cfg["profile_sha256"] == record["profile_sha256"]
        and str(Path(record["store_path"]).parents[2]) == cfg["root"],
        "GUARD_AUTHORITY_SCOPE_CHANGED",
    )
    probe = probe or Probe()
    production = probe.unit(cfg["production_unit"])
    owner = probe.unit(cfg["owner_unit"])
    need(
        production.get("ActiveState") == "active"
        and production.get("InvocationID") == cfg["production_invocation"]
        and str(production.get("MainPID", "")).isdigit()
        and int(production["MainPID"]) > 1,
        "GUARD_PRODUCTION_UNIT_UNHEALTHY",
    )
    need(
        owner.get("ActiveState") == "active"
        and owner.get("MainPID") == str(record["guardian_pid"])
        and re.fullmatch("[0-9a-f]{32}", owner.get("InvocationID", "")),
        "GUARD_OWNER_UNIT_UNHEALTHY",
    )
    prod_hb = Path(cfg["root"]) / "state/supervisor/line-conductor.heartbeat"
    owner_hb = Path(os.environ[D.FILE]).with_suffix(".heartbeat.json")
    heartbeat(prod_hb, int(production["MainPID"]), "OBSERVE", "epoch", "GUARD_PRODUCTION_HEARTBEAT", time.time())
    heartbeat(owner_hb, record["guardian_pid"], D.MODE, "at", "GUARD_OWNER_HEARTBEAT", time.time())
    legacy_predicates(cfg)
    settings = ST.settings(cfg["profile"])
    worker = observe_worker(settings, own_pid)
    gpu = probe.gpu_pids()
    need(isinstance(gpu, set) and all(type(pid) is int and pid > 1 for pid in gpu), "GUARD_GPU_PROBE_UNKNOWN")
    need(gpu <= {worker}, "GUARD_FOREIGN_GPU_PROCESS")
    need(digest(D.current()) == digest(record), "GUARD_AUTHORITY_CHANGED_DURING_PROBE")
    need(
        probe.unit(cfg["production_unit"]) == production and probe.unit(cfg["owner_unit"]) == owner,
        "GUARD_UNIT_CHANGED_DURING_PROBE",
    )
    heartbeat(prod_hb, int(production["MainPID"]), "OBSERVE", "epoch", "GUARD_PRODUCTION_HEARTBEAT", time.time())
    heartbeat(owner_hb, record["guardian_pid"], D.MODE, "at", "GUARD_OWNER_HEARTBEAT", time.time())
    legacy_predicates(cfg)
    need(observe_worker(settings, own_pid) == worker, "GUARD_WORKER_CHANGED_DURING_PROBE")
    exact_runtime(cfg)
    need(digest(D.current()) == digest(record), "GUARD_FINAL_AUTHORITY_CHANGED")
    final_authority(record)
    return dict(status="OK", acceptance="UNACCEPTED", worker_pid=worker)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--own-pid", default="")
    args = parser.parse_args(argv)
    try:
        need(args.own_pid.isdecimal(), "GUARD_WORKER_ARGUMENT_INVALID")
        selected = Path(os.environ["FORGE_REPO_ROOT"]).resolve()
        need(
            Path(D.__file__).resolve() == selected / "factory/python/forge_factory/afo/owner_supervised_development.py"
            and Path(P.__file__).resolve() == selected / "factory/python/forge_factory/lrtx/provider_process.py",
            "GUARD_RUNTIME_IMPORT_REBOUND",
        )
        cfg = load_config(
            Path(os.environ["FORGE_OWNER_LAUNCH_GUARD_CONFIG"]), os.environ["FORGE_OWNER_LAUNCH_GUARD_CONFIG_SHA256"]
        )
        evaluate(cfg, int(args.own_pid))
        print("OK")
        return 0
    except Exception as exc:  # Unknown observation is a refusal, never an empty GPU census.
        code = exc.code if isinstance(exc, Refused) else "GUARD_OBSERVATION_UNKNOWN_" + type(exc).__name__
        print("FAIL:" + code)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
