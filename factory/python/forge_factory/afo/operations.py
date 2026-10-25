"""Durable operator intent and serialized service-manager effects (DA-045/046/050).

The minimal record is outside the application mount when deployed. Its directory
must be explicitly provisioned by the operator; absent/corrupt intent is UNKNOWN.
No policy, job budget or source deployment authority is granted here.
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from ..common import utc_now
from .durable import Refused, canonical

MODES = {"RUNNING", "PAUSED", "DRAINING", "STOPPED"}
# Fixed approved operational recipe: Conductor only; no recursive supervisor restarts.
UNIT = "forge-conductor.service"
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
            rec = json.loads(self.path.read_text())
            if rec["mode"] not in MODES or type(rec["epoch"]) is not int or rec["epoch"] < 1:
                raise ValueError
            return rec
        except (OSError, ValueError, KeyError):
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

    def set(self, mode, *, actor, reason, initialize=False, settle=None):
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
            }
            # Commit STOPPED before bounded cancellation/stop; all start actors share this lock.
            self._write(rec)
            if mode == "STOPPED" and settle is not None:
                result = settle()
                rec["stop_settlement"] = result
                rec["effective_stop"] = result.get("settled") is True
                self._write(rec)
            return rec

    def start(self, epoch, *, probe, runner=None, now=None):
        now = time.time() if now is None else now
        with self.lock():
            rec = self.read()
            if rec["epoch"] != epoch or rec["mode"] not in ("RUNNING", "PAUSED", "DRAINING"):
                raise Refused("OPERATIONS_START_FENCED")
            due = rec.get("next_recovery_epoch", 0)
            if now < due:
                return {"action": "COOLDOWN", "next_probe": due}
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
            self._write(rec)  # persist cooldown before uncertain external start
            run = runner or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=20))
            result = run(["systemctl", "--user", "start", UNIT])
            # Do not reset-failed: retain systemd's burst limit. A future bounded probe can try after its interval.
            return {
                "action": "START_REQUESTED",
                "returncode": result.returncode,
                "epoch": epoch,
                "next_probe": rec["next_recovery_epoch"],
            }


def observed_unit():
    r = subprocess.run(
        ["systemctl", "--user", "show", UNIT, "--property=ActiveState,SubState,Result,UnitFileState"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode:
        return {}
    return dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)


def synchronize(store, action, actor, reason):
    """Shared CLI/dashboard control path; the caller authenticates before entering."""
    mode = {"pause": "PAUSED", "drain": "DRAINING", "resume": "RUNNING", "shutdown": "STOPPED"}[action]
    rec = Intent().set(mode, actor=actor, reason=reason)
    store.set_control("paused", "0" if action == "resume" else "1", actor, reason)
    store.set_control("draining", "1" if action in ("drain", "shutdown") else "0", actor, reason)
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
    if rec["mode"] not in ("RUNNING", "PAUSED", "DRAINING") or not preflight()["ok"]:
        return {"action": "WAITING", "intent": rec["mode"]}
    return intent.start(rec["epoch"], probe=observed_unit)


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
