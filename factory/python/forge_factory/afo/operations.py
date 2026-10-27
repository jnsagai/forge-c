"""Durable operator intent and serialized service-manager effects (DA-045/046/050).

The minimal record is outside the application mount when deployed. Its directory
must be explicitly provisioned by the operator; absent/corrupt intent is UNKNOWN.
No policy, job budget or source deployment authority is granted here.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from ..common import utc_now
from .durable import Refused, canonical, digest, strict_json

MODES = {"RUNNING", "PAUSED", "DRAINING", "STOPPED"}
# Fixed approved operational recipe: Conductor only; no recursive supervisor restarts.
UNIT = os.environ.get("FORGE_CONDUCTOR_UNIT", "forge-conductor.service")
if UNIT not in ("forge-conductor.service", "forge-conductor-local-omniverse2.service"):
    raise ValueError("UNAPPROVED_CONDUCTOR_RECOVERY_UNIT")
COOLDOWN = 600


def configured() -> bool:
    return bool(os.environ.get("FORGE_OPERATIONS_INTENT"))


def path() -> Path:
    raw = os.environ.get("FORGE_OPERATIONS_INTENT")
    if not raw or not Path(raw).is_absolute():
        raise Refused("OPERATIONS_INTENT_NOT_CONFIGURED")
    return Path(raw)


class Intent:
    def __init__(self, location=None):
        self.path = Path(location) if location else path()

    @contextmanager
    def lock(self):
        parent = self.path.parent
        if not parent.is_dir() or parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o022:
            raise Refused("OPERATIONS_DIRECTORY_NOT_PRIVATE_OR_OWNED")
        lock = self.path.with_suffix(".lock")
        if lock.is_symlink() or self.path.is_symlink():
            raise Refused("OPERATIONS_SYMLINK_DENIED")
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def read(self):
        try:
            st = self.path.stat()
            if self.path.is_symlink() or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise Refused("OPERATIONS_RECORD_NOT_PRIVATE_OR_OWNED")
            rec = strict_json(self.path.read_bytes(), 65536)
            if rec["mode"] not in MODES or type(rec["epoch"]) is not int or rec["epoch"] < 1:
                raise ValueError
            return rec
        except (OSError, ValueError, KeyError, TypeError):
            return {"mode": "UNKNOWN", "epoch": 0, "effective_stop": False}

    def _write(self, rec):
        fd, tmp = tempfile.mkstemp(prefix=".intent-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(canonical(rec))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def set(self, mode, *, actor, reason, initialize=False, settle=None, apply=None, authentication=None):
        if mode not in MODES or not actor or not reason.strip():
            raise Refused("AUTHENTICATED_INTENT_AND_REASON_REQUIRED")
        with self.lock():
            old = self.read()
            if old["mode"] == "UNKNOWN" and not initialize:
                raise Refused("OPERATIONS_INTENT_UNKNOWN")
            rec = {
                "schema": "forge-c/operations-intent/1",
                "mode": mode,
                "epoch": old["epoch"] + 1,
                "actor": actor,
                "reason": reason[:200],
                "changed_at": utc_now(),
                "effective_stop": False,
                "next_recovery_epoch": old.get("next_recovery_epoch", 0),
                "recoveries": old.get("recoveries", 0),
                "pending_start": old.get("pending_start", False),
                "last_recovery": old.get("last_recovery"),
            }
            rec["control_context"] = control_context(self.path, rec, authentication=authentication)
            # Commit STOPPED before bounded cancellation/stop; all start actors share this lock.
            self._write(rec)
            # Keep database controls under the same intent fence. An older
            # resume must not overwrite a newer stop after dropping this lock.
            if apply is not None:
                apply(rec)
            if mode == "STOPPED" and settle is not None:
                result = settle()
                rec["stop_settlement"] = result
                rec["effective_stop"] = result.get("settled") is True
                self._write(rec)
            return rec

    def start(self, epoch, *, probe, runner=None, now=None, authorize=None):
        now = time.time() if now is None else now
        with self.lock():
            rec = self.read()
            if rec["epoch"] != epoch or rec["mode"] not in ("RUNNING", "PAUSED", "DRAINING"):
                raise Refused("OPERATIONS_START_FENCED")
            due = rec.get("next_recovery_epoch", 0)
            if due - now > COOLDOWN:
                rec["clock_regression_detected_at"] = now
                rec["next_recovery_epoch"] = now + COOLDOWN
                self._write(rec)
                due = rec["next_recovery_epoch"]
            if now < due:
                return {"action": "COOLDOWN", "next_probe": due}
            if not (authorize or operational_authorized)():
                return {"action": "WAITING_FOR_PREAUTHORIZED_OPERATIONAL_RECIPE"}
            state = probe()
            # An explicit systemctl stop produces inactive/success; never undo it. Disabled/masked is deliberate.
            if (
                state.get("UnitFileState") not in ("enabled", "enabled-runtime")
                or state.get("ActiveState") != "failed"
                or state.get("Result") not in ("start-limit-hit", "watchdog", "exit-code", "signal", "timeout", "oom-kill")
            ):
                return {"action": "NO_APPROVED_RECOVERY", "state": state}
            rec["next_recovery_epoch"] = now + COOLDOWN
            rec["recoveries"] = rec.get("recoveries", 0) + 1
            rec["last_recovery"] = {"epoch": epoch, "at": now, "recipe": "conductor-failed-start-v1", "state": state}
            rec["pending_start"] = True
            self._write(rec)  # persist cooldown before uncertain external start
            run = runner or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=20))
            result = run(["systemctl", "--user", "start", UNIT])
            rec["pending_start"] = False
            self._write(rec)
            # Do not reset-failed: retain systemd's burst limit. A future bounded probe can try after its interval.
            return {
                "action": "START_REQUESTED",
                "returncode": result.returncode,
                "epoch": epoch,
                "next_probe": rec["next_recovery_epoch"],
            }


def operational_authorized(action="restart_conductor"):
    """Reuse CRE's persistent, pre-authorized operational boundary; engineering grant expiry is separate."""
    from ..reliability.policy import load

    try:
        return load().automatic_action_allowed(action)
    except (OSError, ValueError):
        return False


def observed_unit():
    r = subprocess.run(
        ["systemctl", "--user", "show", UNIT, "--property=ActiveState,SubState,Result,UnitFileState,Job"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode:
        return {}
    return dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)


def control_context(location, record, *, authentication=None):
    """Facts from the existing caller/OS boundary, never an intervention verdict.

    Failure to observe a process must not prevent an authenticated operator stop.
    Unknown process facts remain explicit for independent audit reconciliation.
    """
    from ..lrtx.provider_process import identity

    try:
        process = identity(os.getpid())
        user_namespace = os.readlink("/proc/self/ns/user")
        uid_map = [list(map(int, row.split())) for row in Path("/proc/self/uid_map").read_text().splitlines()]
    except (OSError, ValueError):
        process, user_namespace, uid_map = None, None, None
    try:
        producer_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError:
        producer_sha = None
    # All exported authentication fields are allowlisted. Credentials/reason/
    # actor text cannot enter the factual receipt through arbitrary caller data.
    auth = {"method": "PRIVATE_INTENT_DIRECTORY_OWNER", "uid": os.getuid()}
    if isinstance(authentication, dict) and authentication.get("method") in (
        "OS_STATE_DIRECTORY_OWNER", "DASHBOARD_OPERATOR_BEARER",
    ):
        import re

        auth["method"] = authentication["method"]
        for key in ("credential_sha256", "source_sha256"):
            value = authentication.get(key)
            if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                auth[key] = value
    body = {
        "schema": "forge-c/control-source-context/1", "intent_epoch": record["epoch"], "mode": record["mode"],
        "intent_path_sha256": hashlib.sha256(str(location.absolute()).encode()).hexdigest(),
        "intent_request_sha256": digest({k: record[k] for k in ("epoch", "mode", "actor", "reason", "changed_at")}),
        "producer_source_sha256": producer_sha,
        "at": time.time(), "mono": time.monotonic(), "pid": os.getpid(), "process": process,
        "user_namespace": user_namespace, "uid_map": uid_map, "authentication": auth,
        "scope": "CALLER_AND_OS_SOURCE_FACTS_NOT_INDEPENDENT_HOST_AUDIT",
    }
    return {**body, "control_id": "control-" + digest(body)}


def synchronize(store, action, actor, reason, *, authentication=None):
    """Shared CLI/dashboard control path; the caller authenticates before entering."""
    mode = {"pause": "PAUSED", "drain": "DRAINING", "resume": "RUNNING", "shutdown": "STOPPED"}[action]
    def apply(rec):
        store.set_controls({"paused": "0" if action == "resume" else "1",
                            "draining": "1" if action in ("drain", "shutdown") else "0"},
                           actor, reason, context=rec["control_context"])

    rec = Intent().set(mode, actor=actor, reason=reason, apply=apply, authentication=authentication)
    return rec


def boot_allowed():
    if not configured():
        return True  # legacy profile, no automatic recovery lane
    return Intent().read()["mode"] in ("RUNNING", "PAUSED", "DRAINING")


def recover():
    from .host import preflight

    if not configured():
        return {"action": "NOT_ENABLED"}
    intent = Intent()
    rec = intent.read()
    ready = preflight()["ok"]
    if rec["mode"] == "STOPPED" and ready and not rec.get("effective_stop"):
        from .queue import Store

        return {"action": "STOP_SETTLEMENT", **settle_shutdown(Store(), external=True)}
    if rec["mode"] not in ("RUNNING", "PAUSED", "DRAINING") or not ready:
        return {"action": "WAITING", "intent": rec["mode"]}
    return intent.start(rec["epoch"], probe=observed_unit)


def recover_profile(store, *, external=False):
    """Restore the existing profile without treating native terminal as provider quiet."""
    profile = os.environ.get("FORGE_OPERATIONS_PROFILE")
    if not configured() or not profile:
        return {"action": "NOT_ENABLED"}
    from ..lrtx import stack
    from .dependency_wait import probe

    # Kernel identities are captured by the external observer. The Conductor
    # runs inside the profile's user namespace and cannot safely adopt them.
    if stack.managed_serving() and not external:
        return {"action": "WAIT_FOR_EXTERNAL_WATCHDOG"}

    def restore():
        rec = Intent().read()
        allowed = ("RUNNING", "PAUSED", "DRAINING") if stack.managed_serving() else ("RUNNING",)
        if rec["mode"] not in allowed or not operational_authorized("restart_local_stack"):
            return {"ok": False, "code": "OPERATIONAL_RECIPE_NOT_AUTHORIZED"}
        intent = Intent()
        with intent.lock():
            current = intent.read()
            if current["epoch"] != rec["epoch"] or current["mode"] not in allowed:
                return {"ok": False, "code": "OPERATIONS_START_FENCED"}
            # Lock order is intent -> SQLite, shared with shutdown. Hold admission
            # while restoring model-free dependencies so no owner appears mid-start.
            with store.tx() as c:
                held = c.execute("SELECT holder FROM afo_resource_ownership WHERE resource='inference'").fetchone()
                owner = held[0] if held else None
                if owner and not stack.managed_serving():
                    return {"ok": False, "code": "NATIVE_QUIESCENCE_UNPROVEN"}
                if not owner:
                    if current["mode"] == "RUNNING":
                        restored = stack._start(stack.settings(profile), recovery=True)
                    else:
                        restored = stack._start(stack.settings(profile), recovery=True, control_only=True)
                        return {
                            "ok": restored["health"].get("fabro") is True,
                            "code": "CONTROL_PLANE_ONLY",
                            "health": restored["health"],
                        }
            if owner:
                from .execution_lifecycle import Executions
                from .mission_ledger import MissionLedger
                from .provider_recovery import reconcile

                ex = Executions(store)
                live = ex.get(owner)
                if not live:
                    return {"ok": False, "code": "NATIVE_OWNER_IDENTITY_UNPROVEN"}
                expired = time.time() >= MissionLedger(store).snapshot(live["mission_id"])["limits"]["deadline"]
                table = "afo_product_jobs" if owner.startswith("afo-product-") else "afo_local_agent_jobs"
                with store.tx() as c:
                    job = c.execute(f"SELECT record FROM {table} WHERE job_id=?", (owner,)).fetchone()  # noqa: S608 - two fixed tables
                if job:
                    deadline = json.loads(job[0]).get("deadline_epoch")
                    expired = expired or (isinstance(deadline, (int, float)) and time.time() >= deadline)
                terminal = ex._evidence(owner, "NATIVE_TERMINAL")
                eligible = terminal or expired or live["authorization_state"] != "VALID" or live["task_outcome"] != "ACTIVE"
                if not eligible:
                    restored = stack._start(stack.settings(profile), recovery=True, control_only=True)
                    return {"ok": False, "code": "ACTIVE_PROVIDER_PRESERVED", "health": restored["health"]}
                instance = stack.serving_instance(stack.settings(profile))
                proof = reconcile(store, owner, instance, retire=True, fenced_effect=lambda effect: effect())
                # The retained inference owner blocks new admission. Restoring
                # Fabro permits native status/cancel reconciliation only; no
                # replacement gateway or model may start until that completes.
                restored = stack._start(stack.settings(profile), recovery=True, control_only=True)
                return {"ok": False, "code": "WAITING_FOR_NATIVE_RECONCILIATION", "provider": proof, "health": restored["health"]}
        return {
            "ok": all(restored["health"].get(k) is True for k in ("fabro", "gateway", "ollama")),
            "health": restored["health"],
        }

    return probe(store, "local-profile", profile, restore, minimum=60, maximum=600)


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["boot-check", "status", "initialize"])
    ap.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    if a.command == "boot-check":
        return 0 if boot_allowed() else 1
    if a.command == "initialize":
        # OS-owned private directory is the authenticated installation boundary. No automatic initialization.
        print(json.dumps(Intent().set("STOPPED", actor=str(os.getuid()), reason=a.reason, initialize=True)))
    else:
        print(json.dumps(Intent().read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def fenced_call(epoch, effect):
    """Serialize only the bounded external start effect with authenticated operator control."""
    if not configured():
        return effect()
    intent = Intent()
    with intent.lock():
        rec = intent.read()
        if rec["mode"] != "RUNNING" or rec["epoch"] != epoch:
            raise Refused("OPERATIONS_ADMISSION_FENCED")
        return effect()


def settle_shutdown(store, *, probe=None, stop_runner=None, client=None, external=False):
    """Requested stop remains unresolved until every native inference owner is quiescent."""
    intent = Intent()
    with intent.lock():
        rec = intent.read()
        if rec["mode"] != "STOPPED":
            raise Refused("SHUTDOWN_INTENT_SUPERSEDED")
        from ..lrtx import stack

        if stack.managed_serving() and os.environ.get("FORGE_OPERATIONS_PROFILE") and not external:
            return {"settled": rec.get("effective_stop") is True, "code": "WAIT_FOR_EXTERNAL_WATCHDOG"}
        return _settle_shutdown_locked(store, intent, rec, probe=probe, stop_runner=stop_runner, client=client)


def _settle_shutdown_locked(store, intent, intent_record, *, probe, stop_runner, client):
    from ..fabro.client import FabroClient, load_token
    from .execution_lifecycle import Executions

    ex = Executions(store)
    serving_settled = True
    serving_result = None
    from ..lrtx import stack

    if stack.managed_serving() and os.environ.get("FORGE_OPERATIONS_PROFILE"):
        # STOP is already durable. Serialize exact-instance retirement with
        # resume/recovery before issuing any signal. Legacy lifetimes remain
        # unresolved; they cannot be retroactively adopted as managed evidence.
        try:
            from ..lrtx import provider_process
            from .provider_recovery import reconcile

            instance = stack.serving_instance(stack.settings(os.environ["FORGE_OPERATIONS_PROFILE"]))
            serving_result = provider_process.stop(instance, fenced_effect=lambda effect: effect())
            serving_settled = bool(serving_result)
            if serving_settled:
                for live in ex.pending()[:8]:
                    reconcile(store, live["job_id"], instance, fenced_effect=lambda effect: effect())
        except (OSError, ValueError) as exc:
            serving_settled = False
            serving_result = {"code": getattr(exc, "code", type(exc).__name__)}
    owned_client = client is None
    client = client or FabroClient(token=load_token(), timeout=3)
    try:
        for rec in ex.pending()[:8]:
            if rec["authorization_state"] == "VALID":
                ex.revoke(rec["job_id"])
            if rec["task_outcome"] == "ACTIVE":
                ex.outcome(rec["job_id"], "BLOCKED", "OPERATOR_SHUTDOWN")
            ex.reconcile(rec["job_id"], client, cancel=True)
    finally:
        if owned_client:
            client.close()
    unresolved = [r["job_id"] for r in ex.pending()]
    result = {"settled": False, "unresolved_native_jobs": unresolved}
    if serving_result is not None:
        result["serving_settlement"] = serving_result
    # A timed-out systemctl start may still be queued. Cancel it with a
    # serialized stop and observe Job=0 before confirming the operator stop.
    rec = intent_record
    manager_settled = True
    if rec.get("pending_start"):
        run = stop_runner or (lambda args: subprocess.run(args, capture_output=True, text=True, timeout=20))
        stopped = run(["systemctl", "--user", "stop", UNIT])
        state = (probe or observed_unit)()
        manager_settled = (
            stopped.returncode == 0 and state.get("Job") in ("0", "") and state.get("ActiveState") in ("inactive", "failed")
        )
        if manager_settled:
            rec["pending_start"] = False
        result["service_manager_settled"] = manager_settled
    result["settled"] = not unresolved and manager_settled and serving_settled
    rec.update(effective_stop=result["settled"], stop_settlement=result)
    intent._write(rec)
    return result
