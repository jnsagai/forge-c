"""Explicit, unaccepted OS-owner startup before the development producer places work.

Uses the existing canonical line Store and managed stack. No synthetic job,
production grant, global Conductor DB, CRE policy edit or model inference.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path

from .durable import Refused, canonical, digest

INTENT_KIND = "OWNER_PROFILE_BOOTSTRAP_INTENT"
RESULT_KIND = "OWNER_PROFILE_BOOTSTRAP_RESULT"
GPU_LOCK = Path("/mnt/data/forge-c/line/gpu.lock")
LEGACY_PROFILE_SHA = "830da0ee607c66e462f9eabc3c5037fe64c88b5ebf35c05b99d978b7d505536f"


def require(ok, code):
    if not ok:
        raise Refused("OWNER_BOOTSTRAP_" + code)


def census(client):
    """Bounded complete native inventory, including archives/removal; unknown is busy."""
    rows, offset, total = [], 0, None
    for _ in range(100):
        page = client._get("/api/v1/runs", **{"page[limit]": 100, "page[offset]": offset,
                          "sort": "created_at", "direction": "asc", "include_archived": "true"})
        meta, part = page["meta"], page["data"]
        require(type(meta.get("total")) is int and type(meta.get("has_more")) is bool and isinstance(part, list),
                "NATIVE_INVENTORY_UNKNOWN")
        if total is None:
            total = meta["total"]
        require(total == meta["total"] and 0 <= total <= 10000, "NATIVE_INVENTORY_CHANGED")
        for row in part:
            kind = ((row.get("lifecycle") or {}).get("status") or {}).get("kind")
            require(kind in ("succeeded", "failed", "cancelled", "canceled"),
                    "NATIVE_NOT_TERMINAL")
            rows.append({"id": row["id"], "status": kind})
        if not meta["has_more"]:
            break
        require(bool(part), "NATIVE_INVENTORY_INCOMPLETE")
        offset += len(part)
    else:
        require(False, "NATIVE_INVENTORY_BOUND")
    require(len(rows) == total and len({r["id"] for r in rows}) == total, "NATIVE_INVENTORY_INCOMPLETE")
    removing = client._get("/api/v1/runs", **{"page[limit]": 100, "status": "removing", "include_archived": "true"})
    require(removing["data"] == [] and removing["meta"]["total"] == 0
            and removing["meta"]["has_more"] is False, "NATIVE_REMOVAL_UNKNOWN")
    return {"count": total, "identity_status_sha256": digest(sorted(rows, key=lambda r: r["id"]))}


def quiet_ledger(c):
    """Historical PAUSED/FAILED rows alone are not running inference."""
    held = c.execute("SELECT holder FROM afo_resource_ownership WHERE resource='inference'").fetchone()
    require(not held or not held[0], "INFERENCE_OWNER_PRESENT")
    for row in c.execute("SELECT record FROM afo_execution_liveness"):
        rec = json.loads(row[0])
        require(rec.get("resource_lease") == "RELEASED", "EXECUTION_LEASE_NOT_RELEASED")
    require(not c.execute("SELECT 1 FROM afo_request_ledger WHERE state!='QUIESCENT' LIMIT 1").fetchone(),
            "REQUEST_NOT_QUIESCENT")
    require(not c.execute("SELECT 1 FROM afo_commands_outbox WHERE state NOT IN ('ACKED','FAILED','QUARANTINED') LIMIT 1").fetchone(),
            "COMMAND_OUTCOME_UNRESOLVED")


@contextmanager
def gpu_lock(path):
    """Use the real existing line lock, never a substitute file or inherited fd."""
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), "GPU_LOCK_UNKNOWN")
    fd = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        have, want = os.fstat(fd), path.stat()
        require((have.st_dev, have.st_ino) == (want.st_dev, want.st_ino) and have.st_uid == os.getuid()
                and not stat.S_IMODE(have.st_mode) & 0o002, "GPU_LOCK_REBOUND")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("OWNER_BOOTSTRAP_GPU_BUSY") from None
        yield
    finally:
        os.close(fd)


def _services_quiet(settings):
    from ..lrtx import provider_process as provider
    from ..lrtx import stack

    path = settings["root"] / "run/services.json"
    require(not path.is_symlink(), "SERVICES_UNKNOWN")
    holder = settings["root"] / "run/holder.pid"
    require(not holder.exists() and not holder.is_symlink(), "HOLDER_PROJECTION_REMAINS")
    from .line_launcher import ProcFS, survey

    candidates, live_holder = survey(settings["root"], ProcFS(), os.getuid())
    require(not candidates and live_holder is None, "UNRECORDED_STACK_PROCESS_PRESENT")
    if not path.exists():
        return
    require(path.stat().st_uid == os.getuid() and not path.stat().st_mode & 0o022, "SERVICES_UNKNOWN")
    rec = json.loads(path.read_text())
    require(rec.get("root") == str(settings["root"]), "SERVICES_ROOT_CHANGED")
    require(rec.get("profile_sha256") in (settings["profile"]["_sha256"], LEGACY_PROFILE_SHA),
            "SERVICES_PROFILE_CHANGED")
    if rec.get("serving_instance"):
        require(provider.quiet(stack.serving_instance(settings)), "PROVIDER_NOT_QUIET")
    pids = [rec.get("holder_pid")]
    for group in (rec.get("processes") or {}, rec.get("api_bridge") or {}):
        pids += [x.get("pid") for x in group.values() if isinstance(x, dict)]
    if rec.get("serving_holder"):
        pids.append(rec["serving_holder"].get("pid"))
    # No signal or opportunistic retirement. A live/unknown recorded lifetime refuses.
    for pid in pids:
        if type(pid) is int and pid > 1:
            require(stack.process_identity(pid) is None, "RECORDED_PROCESS_STILL_PRESENT")


def bootstrap(store, placer, *, order_wo=None, timeout_s=600, cancelled=lambda: False):
    """Supported optional D.main stage, in the issuing initial-host owner process.

    Intent -> nonblocking GPU -> nonblocking stack -> nonblocking ACT -> canonical
    writer transaction. ACT remains held by this SAME Placer on success. Failed
    startup revokes this issuer and leaves an append-only unresolved result; no
    new issuer can silently retry an unresolved bootstrap.
    """
    from ..common import state_dir, sha256_file
    from ..lrtx import stack
    from . import line_recovery_control as C
    from . import owner_supervised_development as D
    from .authority import decide
    from .line_launcher import LineConfig, ShellHost
    from .operations import Intent
    from .policy import load
    from .owner_bootstrap_history import native_checkpoint, native_status

    require(type(timeout_s) in (int, float) and math.isfinite(timeout_s) and 1 <= timeout_s <= 600,
            "BOUNDED_DEADLINE_REQUIRED")
    require(not any(os.environ.get(k) for k in ("FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING",
                "FORGE_LINE_STACK_PAYLOAD", "FORGE_LINE_STACK_PAYLOAD_SHA256", "FORGE_STACK_LOCK_FD")),
            "EXTERNAL_ISSUER_REQUIRED")
    require([list(map(int, x.split())) for x in Path("/proc/self/uid_map").read_text().splitlines()]
            == [[0, 0, 4294967295]], "INITIAL_USER_NAMESPACE_REQUIRED")
    record = D.current()
    require(record["guardian_pid"] == os.getpid(), "ISSUING_PROCESS_REQUIRED")
    root = Path(record["store_path"]).parents[2]
    require(store.path.resolve() == Path(record["store_path"]) == state_dir() / "supervisor/line-queue.sqlite3",
            "CANONICAL_STORE_REQUIRED")
    require(placer.queue_path.resolve() == store.path.resolve() and placer._act_lock is None,
            "FRESH_CANONICAL_PLACER_REQUIRED")
    cfg = LineConfig.from_env()
    require(cfg.stack_root.resolve() == root and cfg.gpu_lock.resolve() == GPU_LOCK,
            "LINE_ROOT_OR_GPU_LOCK_CHANGED")
    settings = stack.settings(record["profile"])
    require(settings["root"].resolve() == root and settings["profile"]["_sha256"] == record["profile_sha256"]
            and stack.managed_serving(), "MANAGED_PROFILE_REQUIRED")
    request = dict(order_id=order_wo or D.ORDERS[0], driver_class=D.DRIVER, model=record["profile"],
                   service_action="line_stack_restart")
    intent, stop_at = Intent(), time.monotonic() + timeout_s
    boot_stop = time.clock_gettime(time.CLOCK_BOOTTIME) + timeout_s
    native_path = root / "fabro/storage/db/fabro.sqlite3"
    anchor = {k: record[k] for k in ("control_ref", "control_sha256", "mission", "intent_epoch", "store_identity")}
    key = "owner-profile-bootstrap-" + digest(record)
    acquired, attempted, result = False, False, None
    host = ShellHost(cfg)

    def guard():
        require(not cancelled(), "CANCELLED")
        current = D.current()  # ReadSnapshot, never re-enter this writer transaction.
        require(current == record and all(current[k] == v for k, v in anchor.items())
                and time.monotonic() < stop_at, "AUTHORITY_OR_DEADLINE_CHANGED")
        state = intent.read()
        require(state["mode"] == "RUNNING" and state["epoch"] == record["intent_epoch"], "INTENT_CHANGED")
        eff = load()
        require(decide("launch_workorder", request, afo=eff, log=False).allow, "BCD_SERVICE_ACTION_REFUSED")
        require(C.configuration(record["control_ref"], eff, request=request)["mission"] == record["mission"],
                "CONTROL_CHANGED")
        require(placer._act_lock is not None, "ACT_FENCE_LOST")
        native_status(native_path)
        # Heavy authorization/SQL/file work cannot spend a historical time check.
        # Same issuer challenge and pinned inputs precede a final small effect tail.
        D._attest(record, record["guardian_socket"])
        for ref in (record["control_ref"], record["runtime_policy_ref"], record["line_policy_ref"]):
            require(sha256_file(Path(ref["path"])) == ref["sha256"], "INPUT_CHANGED_AT_EFFECT")
        state = intent.read()
        require(state["mode"] == "RUNNING" and state["epoch"] == record["intent_epoch"]
                and os.getpid() == record["guardian_pid"] and not cancelled(), "FINAL_EFFECT_FENCE_CHANGED")
        require(time.monotonic() < min(stop_at, record["expiry_ticket"]["deadline_monotonic"])
                and time.clock_gettime(time.CLOCK_BOOTTIME) < min(boot_stop, record["expiry_boottime_deadline"]),
                "FINAL_EFFECT_DEADLINE_EXHAUSTED")

    guard.bootstrap_binding = {"intent_id": key, "record_sha256": digest(record),
                               "control_ref": record["control_ref"]}

    try:
        # Do not retain Intent while issuing a guardian; issuance happened already.
        with intent.lock(blocking=False), gpu_lock(cfg.gpu_lock), stack.stack_lock(root):
            act = store.path.parent / "act.lock"
            require(not act.is_symlink(), "ACT_LOCK_UNKNOWN")
            require(placer._take_act_lock(), "ACT_BUSY")
            acquired = True
            with store.tx() as c:
                quiet_ledger(c)
                guard()
                _services_quiet(settings)
                native_before = native_checkpoint(root)
                guard()
                for row in c.execute("SELECT decision_id FROM afo_independent_decisions WHERE kind=?", (INTENT_KIND,)):
                    old = c.execute("SELECT record FROM afo_independent_decisions WHERE decision_id=? AND kind=?",
                                    (row[0] + "-result", RESULT_KIND)).fetchone()
                    require(old is not None and json.loads(old[0]).get("status") == "READY", "PRIOR_ATTEMPT_UNRESOLVED")
                require(not c.execute("SELECT 1 FROM afo_independent_decisions WHERE decision_id=?", (key,)).fetchone(),
                        "ALREADY_ATTEMPTED")
                value = dict(schema="forge-c/owner-profile-bootstrap-intent/1", record_sha256=digest(record),
                             control_ref=record["control_ref"], root=str(root), request=request,
                             qualification_only=True, acceptance="UNACCEPTED", model_calls=0)
                c.execute("INSERT INTO afo_independent_decisions VALUES (?,?,?,?)",
                          (key, INTENT_KIND, canonical(value).decode(), digest(value)))
            attempted = True  # Committed intent before any process effect; never replay unknown.
            with store.tx() as c, stack.line_effect_guard(guard):
                quiet_ledger(c)
                guard()
                # Restore only Fabro first. No gateway/model can run until complete
                # authoritative native census has excluded unknown/active/removing.
                stack._start(settings, recovery=True, control_only=True)
                guard()
                exposed = stack.expose_api(settings, cfg.fabro_host_port)
                require(exposed["api_bridge"] in ("UP", "already running"), "API_NOT_READY")
                with host._client() as client:
                    before = census(client)
                require(before == native_before["inventory"], "API_STORAGE_IDENTITY_CHANGED")
                guard()
                quiet_ledger(c)
                require(native_checkpoint(root) == native_before, "NATIVE_HISTORY_CHANGED")
                guard()
                stack._start(settings, recovery=True)
                while True:
                    guard()
                    state = stack.status(settings)
                    health = state.get("health") or {}
                    if all(health.get(k) is True for k in ("fabro", "ollama", "gateway", "llama_server")):
                        break
                    time.sleep(min(0.25, max(0, stop_at - time.monotonic())))
                guard()
                D.require_compatible_provider(stack.serving_instance(settings))
                with host._client() as client:
                    after = census(client)
                require(before == after and native_checkpoint(root) == native_before, "NATIVE_HISTORY_CHANGED")
                quiet_ledger(c)
                result = dict(schema="forge-c/owner-profile-bootstrap-result/1", status="READY",
                              record_sha256=digest(record), native=after, native_history=native_before, model_calls=0,
                              qualification_only=True, acceptance="UNACCEPTED", placed_jobs=0)
                guard()
                c.execute("INSERT INTO afo_independent_decisions VALUES (?,?,?,?)",
                          (key + "-result", RESULT_KIND, canonical(result).decode(), digest(result)))
        return result
    except BaseException as exc:
        if attempted:
            result = dict(schema="forge-c/owner-profile-bootstrap-result/1", status="UNKNOWN_REQUIRES_RECONCILIATION",
                          record_sha256=digest(record), error_type=type(exc).__name__, model_calls=0,
                          qualification_only=True, acceptance="UNACCEPTED", no_retry=True)
            try:
                with store.tx() as c:
                    c.execute("INSERT INTO afo_independent_decisions VALUES (?,?,?,?)",
                              (key + "-result", RESULT_KIND, canonical(result).decode(), digest(result)))
            finally:
                D.close_guardian({"path": os.environ[D.FILE]})
        if acquired:
            placer._act_lock.close()
            placer._act_lock = None
        raise
