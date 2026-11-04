"""Kernel-backed provider lifetime for the existing isolated local stack.

Each managed provider gets a private PID namespace. Its namespace-init identity
is captured from /proc before admitting requests. Linux kills its descendants
when init ends, including detached workers; pidfds avoid signaling a reused PID.
The AFO watchdog owns authority/intent; the existing ledgers still own capacity.
See https://man7.org/linux/man-pages/man7/pid_namespaces.7.html.
"""

from __future__ import annotations

import hashlib
import os
import re
import signal
import time
from pathlib import Path

from ..afo.durable import Refused, digest
from ..common import utc_now
from . import pidfd


def boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def identity(pid: int) -> dict | None:
    """None means absent. Unreadable observations are errors, never absence."""
    base = Path(f"/proc/{pid}")
    try:
        raw = (base / "stat").read_text()
        fields = raw[raw.rfind(")") + 2 :].split()
        record = {"boot_id": boot_id(), "start_ticks": fields[19], "state": fields[0], "uid": base.stat().st_uid}
    except FileNotFoundError:
        return None
    except (OSError, IndexError) as exc:
        raise Refused("PROVIDER_PROCESS_OBSERVATION_UNAVAILABLE", type(exc).__name__) from exc
    if record["state"] == "Z":
        return record
    try:
        record["pid_namespace"] = os.readlink(base / "ns/pid")
        status = (base / "status").read_text().splitlines()
        line = next(line for line in status if line.startswith("NSpid:"))
        record["namespace_pid"] = int(line.split()[-1])
    except FileNotFoundError:
        # The process exited between the stat and status reads: that is absence, exactly as for the first read.
        return None
    except (OSError, ValueError, StopIteration) as exc:
        raise Refused("PROVIDER_PROCESS_OBSERVATION_UNAVAILABLE", type(exc).__name__) from exc
    return record


def owner_view(pid: int) -> dict:
    """Capture the kernel UID mapping and user namespaces in this observer's view."""
    return {"user_namespace": os.readlink(f"/proc/{pid}/ns/user"),
            "uid_map": [list(map(int, line.split())) for line in Path(f"/proc/{pid}/uid_map").read_text().splitlines()],
            "observer_user_namespace": os.readlink("/proc/self/ns/user"), "observer_uid": os.getuid()}


def require_owner_view(pid: int, expected_uid: int, captured: dict) -> None:
    """Require the original observer, or the exact captured one-level mapped owner view."""
    actual = identity(pid)
    if not actual or actual.get("uid") != os.getuid() or not isinstance(captured, dict):
        raise Refused("PROVIDER_OWNER_VIEW_UNPROVEN")
    current = os.readlink("/proc/self/ns/user")
    if current == captured.get("observer_user_namespace"):
        if actual["uid"] != expected_uid or os.getuid() != captured.get("observer_uid"):
            raise Refused("PROVIDER_OWNER_VIEW_UNPROVEN")
        return
    mapping = captured.get("uid_map")
    if (current != captured.get("user_namespace") or not isinstance(mapping, list) or len(mapping) != 1
            or len(mapping[0]) != 3 or mapping[0][2] != 1
            or owner_view(pid)["uid_map"] != mapping
            or os.readlink(f"/proc/{pid}/ns/user") != current
            or actual["uid"] != mapping[0][0] or expected_uid != mapping[0][1]):
        raise Refused("PROVIDER_OWNER_VIEW_UNPROVEN")


def capture(root: Path, *, profile: str, profile_sha256: str, parent_pid: int) -> dict:
    """Discover the private namespace init directly below our pinned unshare process."""
    parent = identity(parent_pid)
    if not parent or parent.get("state") == "Z" or parent["uid"] != os.getuid():
        raise Refused("PROVIDER_PARENT_IDENTITY_UNPROVEN")
    try:
        children = [int(p) for p in Path(f"/proc/{parent_pid}/task/{parent_pid}/children").read_text().split()]
    except (OSError, ValueError) as exc:
        raise Refused("PROVIDER_CHILD_IDENTITY_UNPROVEN") from exc
    candidates = []
    for pid in children:
        rec = identity(pid)
        if (
            rec
            and rec.get("namespace_pid") == 1
            and rec.get("pid_namespace") != parent["pid_namespace"]
            and rec["uid"] == parent["uid"]
        ):
            candidates.append((pid, rec))
    if len(candidates) != 1:
        raise Refused("PROVIDER_PRIVATE_PID_NAMESPACE_REQUIRED")
    fresh_parent = identity(parent_pid)
    if (
        not fresh_parent
        or fresh_parent.get("state") == "Z"
        or any(fresh_parent.get(k) != v for k, v in parent.items() if k != "state")
    ):
        raise Refused("PROVIDER_PARENT_CHANGED_DURING_CAPTURE")
    pid, init = candidates[0]
    return {
        "schema": "forge-c/managed-provider-instance/1",
        "root": str(root.resolve()),
        "profile": profile,
        "profile_sha256": profile_sha256,
        "observer_user_namespace": os.readlink("/proc/self/ns/user"),
        "init_owner_view": owner_view(pid),
        "parent_pid": parent_pid,
        "parent": {k: v for k, v in parent.items() if k != "state"},
        "init_pid": pid,
        "init": {k: v for k, v in init.items() if k != "state"},
        "captured_at": utc_now(),
    }


def validate(instance: dict) -> None:
    if not isinstance(instance, dict):
        raise Refused("MANAGED_PROVIDER_IDENTITY_INVALID")
    init = instance.get("init") or {}
    parent = instance.get("parent") or {}
    if not isinstance(init, dict) or not isinstance(parent, dict):
        raise Refused("MANAGED_PROVIDER_IDENTITY_INVALID")
    for value in (init, parent):
        if (
            not isinstance(value.get("start_ticks"), str)
            or not value["start_ticks"].isdigit()
            or not isinstance(value.get("boot_id"), str)
            or re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value["boot_id"]) is None
            or not isinstance(value.get("pid_namespace"), str)
            or re.fullmatch(r"pid:\[\d+\]", value["pid_namespace"]) is None
            or type(value.get("uid")) is not int
            or value["uid"] < 0
            or type(value.get("namespace_pid")) is not int
            or value["namespace_pid"] < 1
        ):
            raise Refused("MANAGED_PROVIDER_IDENTITY_INVALID")
    if (
        instance.get("schema") != "forge-c/managed-provider-instance/1"
        or type(instance.get("init_pid")) is not int
        or instance["init_pid"] <= 1
        or type(instance.get("parent_pid")) is not int
        or instance["parent_pid"] <= 1
        or not isinstance(instance.get("profile"), str)
        or not instance["profile"]
        or not isinstance(instance.get("profile_sha256"), str)
        or len(instance["profile_sha256"]) != 64
        or not isinstance(instance.get("root"), str)
        or not Path(instance["root"]).is_absolute()
        or not isinstance(instance.get("observer_user_namespace"), str)
        or init.get("namespace_pid") != 1
        or type(init.get("uid")) is not int
        or init.get("uid") != parent.get("uid")
        or not init.get("boot_id")
        or not init.get("start_ticks")
        or not init.get("pid_namespace")
        or not parent.get("pid_namespace")
        or not parent.get("start_ticks")
        or init.get("pid_namespace") == parent.get("pid_namespace")
        or init.get("boot_id") != parent.get("boot_id")
    ):
        raise Refused("MANAGED_PROVIDER_IDENTITY_INVALID")


def quiet(instance: dict) -> dict | None:
    """Observe old namespace-init termination; never infer it from task/HTTP/GPU state."""
    validate(instance)
    expected = instance["init"]
    current_boot = boot_id()
    kind = None
    if current_boot != expected["boot_id"]:
        kind = "PROVIDER_PREVIOUS_BOOT_QUIESCENT"
    else:
        if os.readlink("/proc/self/ns/user") != instance["observer_user_namespace"]:
            raise Refused("PROVIDER_OBSERVER_NAMESPACE_CHANGED")
        actual = identity(instance["init_pid"])
        if actual is None or actual["start_ticks"] != expected["start_ticks"] or actual["state"] == "Z":
            # A reused PID names a different process. This never authorizes a
            # signal to that newer process; the old namespace init has ended.
            kind = "PROVIDER_PRIVATE_PID_NAMESPACE_ENDED"
        elif any(actual.get(k) != expected.get(k) for k in expected):
            raise Refused("PROVIDER_IDENTITY_OBSERVATION_CHANGED")
    if not kind:
        return None
    return {"kind": kind, "instance_sha256": digest(instance), "observed_boot_id": current_boot, "observed_at": utc_now()}


def stop(instance: dict, *, fenced_effect) -> dict | None:
    """Retire only the exact captured namespace init through the existing intent fence.

    No process-name kill or stop-by-reused-unit-name is used. A stop acknowledgement
    is not the proof: the old init must independently be observed ended. The caller
    retains inference capacity until that proof and native execution reconciliation.
    """
    validate(instance)
    proof = quiet(instance)
    if proof:
        return proof
    try:
        descriptor = pidfd.open_pid(instance["init_pid"])
    except ProcessLookupError:
        return quiet(instance)
    try:

        def effect():
            current = identity(instance["init_pid"])
            expected = instance["init"]
            if current is None or current.get("start_ticks") != expected["start_ticks"] or current.get("state") == "Z":
                return
            if any(current.get(k) != expected.get(k) for k in expected):
                raise Refused("PROVIDER_IDENTITY_OBSERVATION_CHANGED")
            pidfd.send_signal(descriptor, signal.SIGKILL)

        fenced_effect(effect)
    finally:
        os.close(descriptor)
    deadline = time.monotonic() + 2
    while True:
        proof = quiet(instance)
        if proof or time.monotonic() >= deadline:
            return proof
        time.sleep(0.05)


def require_live_instance(instance: dict) -> None:
    """Observe a still-identical provider from host or its own mapped user namespace.

    Numeric UIDs are relative to the observer: require the current observer's own
    UID and its namespace to be either the captured observer or this exact init's
    user namespace. Boot/start/private PID identity must match in both cases.
    This proves liveness only; it never supplies a quiescence/release receipt.
    """
    validate(instance)
    actual = identity(instance["init_pid"])
    require_owner_view(instance["init_pid"], instance["init"]["uid"], instance.get("init_owner_view"))
    if (not actual or actual.get("state") == "Z"
            or any(actual.get(k) != instance["init"].get(k)
                   for k in ("boot_id", "start_ticks", "pid_namespace", "namespace_pid"))):
        raise Refused("PROVIDER_LIVE_INSTANCE_UNCONFIRMED")


def capture_worker(instance: dict, parent_pid: int, argv: list[str], *, timeout=3) -> dict:
    """Find the exact executable under an nsenter waiter, never treat that waiter as its private-PID child."""
    from ..afo.durable import immutable_json

    require_live_instance(instance)
    expected = b"\0".join(os.fsencode(arg) for arg in argv) + b"\0"
    deadline = time.monotonic() + timeout
    while True:
        parent = identity(parent_pid)
        if not parent or parent.get("state") == "Z" or parent["uid"] != os.getuid():
            raise Refused("PROVIDER_WORKER_PARENT_UNPROVEN")
        pending, seen, matches = [parent_pid], set(), []
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            if len(seen) > 128:
                raise Refused("PROVIDER_WORKER_OBSERVATION_BOUND")
            actual = identity(pid)
            if actual and actual.get("state") != "Z":
                try:
                    command = Path(f"/proc/{pid}/cmdline").read_bytes()
                    if (actual["uid"] == os.getuid() and actual["pid_namespace"] == instance["init"]["pid_namespace"]
                            and command == expected):
                        matches.append((pid, actual))
                    pending.extend(int(p) for p in Path(f"/proc/{pid}/task/{pid}/children").read_text().split())
                except FileNotFoundError:
                    continue
                except (OSError, ValueError) as exc:
                    raise Refused("PROVIDER_WORKER_OBSERVATION_UNAVAILABLE") from exc
        if len(matches) > 1:
            raise Refused("PROVIDER_WORKER_IDENTITY_AMBIGUOUS")
        if matches:
            pid, actual = matches[0]
            record = {"schema": "forge-c/managed-provider-worker/1", "instance_sha256": digest(instance),
                      "pid": pid, "identity": {k: v for k, v in actual.items() if k != "state"},
                      "parent_pid": parent_pid, "parent": {k: v for k, v in parent.items() if k != "state"},
                      "argv_sha256": hashlib.sha256(expected).hexdigest(),
                      "observer_user_namespace": os.readlink("/proc/self/ns/user")}
            immutable_json(Path(instance["root"]) / "run/provider-workers" / (digest(record) + ".json"), record)
            return record
        if time.monotonic() >= deadline:
            raise Refused("PROVIDER_WORKER_IDENTITY_UNPROVEN")
        time.sleep(0.02)


def signal_worker(instance: dict, worker: dict, argv: list[str], sig: int, *, fenced_effect) -> None:
    """Signal only the still-identical captured private namespace worker through a pidfd."""
    import hashlib

    from ..afo.durable import strict_json

    validate(instance)
    if (not isinstance(worker, dict) or worker.get("instance_sha256") != digest(instance)
            or worker.get("observer_user_namespace") != os.readlink("/proc/self/ns/user")
            or worker.get("argv_sha256") != hashlib.sha256(b"\0".join(os.fsencode(a) for a in argv) + b"\0").hexdigest()):
        raise Refused("PROVIDER_WORKER_BINDING_CHANGED")
    proof = Path(instance["root"]) / "run/provider-workers" / (digest(worker) + ".json")
    if proof.is_symlink() or strict_json(proof.read_bytes(), 16384) != worker:
        raise Refused("PROVIDER_WORKER_EVIDENCE_CHANGED")
    pid = worker["pid"]
    descriptor = pidfd.open_pid(pid)
    try:
        def effect():
            actual = identity(pid)
            if (not actual or actual.get("state") == "Z"
                    or {k: v for k, v in actual.items() if k != "state"} != worker["identity"]
                    or actual["pid_namespace"] != instance["init"]["pid_namespace"]
                    or Path(f"/proc/{pid}/cmdline").read_bytes() != b"\0".join(os.fsencode(a) for a in argv) + b"\0"):
                raise Refused("PROVIDER_WORKER_IDENTITY_CHANGED")
            pidfd.send_signal(descriptor, sig)
        fenced_effect(effect)
    finally:
        os.close(descriptor)
