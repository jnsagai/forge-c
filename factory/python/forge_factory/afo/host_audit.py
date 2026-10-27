"""Bounded read-only Linux audit source capture for operational qualification.

This exports kernel facts, not an intervention verdict or host authority. Kernel
records alone cannot cover service-manager bus requests and authenticated controls.
No command here enables auditing, installs rules or changes a service or grant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from . import fault_observer as observer
from . import soak
from .durable import Refused, digest, immutable_json

CHANNELS = ("KERNEL_AUDIT", "SYSTEMD_BUS", "AUTHENTICATED_CONTROLS")
HEADER = re.compile(
    r"^(?:node=(?P<node>\S+) )?type=(?P<kind>[A-Z0-9_]{1,64}) "
    r"msg=audit\((?P<epoch>\d{1,16}\.\d{1,9}):(?P<serial>\d{1,20})\): ?(?P<body>.*)$"
)
STATUS_FIELDS = {"enabled", "pid", "rate_limit", "backlog_limit", "lost", "backlog"}
MAX_EVENTS = 10000
MAX_LINE = 65536
MAX_RECORDS = 50000


def kernel_status(text):
    """Parse native auditctl status variants; never default an absent counter to 0."""
    result = {}
    for line in text.splitlines():
        line = line.removeprefix("AUDIT_STATUS:").strip()
        if "=" not in line and line.split() and line.split()[0] in STATUS_FIELDS and len(line.split()) != 2:
            raise Refused("HOST_AUDIT_STATUS_AMBIGUOUS")
        entries = line.split() if "=" in line else ["=".join(line.split()[:2])]
        for entry in entries:
            if "=" not in entry:
                continue
            key, value = entry.split("=", 1)
            if key not in STATUS_FIELDS:
                continue
            if key in result or not re.fullmatch(r"\d{1,20}", value):
                raise Refused("HOST_AUDIT_STATUS_AMBIGUOUS")
            result[key] = int(value)
    if set(result) != STATUS_FIELDS or result["enabled"] not in (0, 1, 2):
        raise Refused("HOST_AUDIT_STATUS_INCOMPLETE")
    return result


def _fields(body):
    result = {}
    try:
        for word in shlex.split(body.split("\x1d", 1)[0]):
            if "=" not in word:
                raise Refused("HOST_AUDIT_RECORD_INVALID")
            key, value = word.split("=", 1)
            if key in result:
                raise Refused("HOST_AUDIT_RECORD_AMBIGUOUS")
            result[key] = value
    except ValueError as exc:
        raise Refused("HOST_AUDIT_RECORD_INVALID") from exc
    return result


def events(raw, *, host, keys):
    """Group compound events by node/time/serial; export whitelisted facts only.

    EXECVE argv, PROCTITLE, account names, command strings and raw path names are
    deliberately absent. Original private source bytes remain separately hashed.
    """
    if len(raw) > observer.MAX_BYTES or (raw and not raw.endswith(b"\n")):
        raise Refused("HOST_AUDIT_LOG_BOUND_OR_TRUNCATION")
    groups = {}
    records = duplicates = 0
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise Refused("HOST_AUDIT_LOG_ENCODING") from exc
    for line in lines:
        if not line or len(line.encode()) > MAX_LINE:
            raise Refused("HOST_AUDIT_RECORD_BOUND_EXCEEDED")
        m = HEADER.fullmatch(line)
        if m is None:
            raise Refused("HOST_AUDIT_RECORD_HEADER_INVALID")
        node = m["node"] or host
        if node != host:
            raise Refused("HOST_AUDIT_LOG_HOST_MISMATCH")
        epoch = float(m["epoch"])
        if not math.isfinite(epoch):
            raise Refused("HOST_AUDIT_EVENT_CLOCK_INVALID")
        identity = (node, m["epoch"], int(m["serial"]))
        if identity not in groups:
            if len(groups) >= MAX_EVENTS:
                raise Refused("HOST_AUDIT_EVENT_COUNT_BOUND_EXCEEDED")
            groups[identity] = {"types": set(), "hashes": set(), "syscall": None, "paths": set()}
        group = groups[identity]
        sha = hashlib.sha256(line.encode()).hexdigest()
        if sha in group["hashes"]:
            duplicates += 1
            continue
        group["hashes"].add(sha)
        group["types"].add(m["kind"])
        records += 1
        if records > MAX_RECORDS:
            raise Refused("HOST_AUDIT_RECORD_COUNT_BOUND_EXCEEDED")
        if m["kind"] == "SYSCALL":
            if group["syscall"] is not None:
                raise Refused("HOST_AUDIT_SYSCALL_AMBIGUOUS")
            fields = _fields(m["body"])
            if not all(re.fullmatch(r"\d{1,20}", fields.get(k, "")) for k in ("pid", "ppid", "uid", "auid", "syscall", "items")):
                raise Refused("HOST_AUDIT_SYSCALL_INCOMPLETE")
            if fields.get("success") not in ("yes", "no") or not re.fullmatch(r"[0-9a-fA-F]{8}", fields.get("arch", "")):
                raise Refused("HOST_AUDIT_SYSCALL_INCOMPLETE")
            group["syscall"] = fields
        elif m["kind"] == "PATH":
            fields = _fields(m["body"])
            if not re.fullmatch(r"\d{1,8}", fields.get("item", "")) or int(fields["item"]) in group["paths"]:
                raise Refused("HOST_AUDIT_PATH_RECORD_AMBIGUOUS")
            group["paths"].add(int(fields["item"]))
    selected = []
    integrity = []
    for (node, epoch, serial), group in sorted(groups.items(), key=lambda i: (float(i[0][1]), i[0][2])):
        syscall = group["syscall"]
        changes = [t for t in group["types"] if t.startswith("DAEMON_") or t == "CONFIG_CHANGE"]
        if changes:
            integrity.append({"host": node, "at": float(epoch), "serial": serial, "types": sorted(changes)})
        if syscall is None or syscall.get("key") not in keys:
            continue
        if int(syscall["items"]) > MAX_RECORDS or group["paths"] != set(range(int(syscall["items"]))):
            raise Refused("HOST_AUDIT_COMPOUND_EVENT_INCOMPLETE")
        selected.append(
            {
                "host": node,
                "at": float(epoch),
                "serial": serial,
                "record_types": sorted(group["types"]),
                "path_records": len(group["paths"]),
                "key": syscall["key"],
                "arch": syscall["arch"].lower(),
                "syscall": int(syscall["syscall"]),
                "success": syscall["success"] == "yes",
                **{k: int(syscall[k]) for k in ("pid", "ppid", "uid", "auid")},
                "source_record_hashes": sorted(group["hashes"]),
            }
        )
    return {
        "events": selected,
        "integrity_events": integrity,
        "source_events": len(groups),
        "source_records": records,
        "duplicate_records": duplicates,
    }


def _command(argv):
    """Fixed read-only utility; timeout and output bounds, no stderr content retained."""
    import resource

    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE, (observer.MAX_BYTES, observer.MAX_BYTES))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (3, 4))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))

    try:
        with tempfile.TemporaryFile() as output:
            p = subprocess.run(
                argv,
                stdout=output,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
                stdin=subprocess.DEVNULL,
                preexec_fn=limits,
                start_new_session=True,
                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
            )
            if output.tell() >= observer.MAX_BYTES:
                return {"returncode": p.returncode, "error": "OUTPUT_BOUND_EXCEEDED"}
            output.seek(0)
            raw = output.read(observer.MAX_BYTES + 1)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"returncode": None, "error": type(exc).__name__}
    if len(raw) > observer.MAX_BYTES:
        return {"returncode": p.returncode, "error": "OUTPUT_BOUND_EXCEEDED"}
    try:
        return {"returncode": p.returncode, "stdout": raw.decode("utf-8", errors="strict")}
    except UnicodeError:
        return {"returncode": p.returncode, "error": "OUTPUT_ENCODING"}


def preflight():
    """Factual current prerequisites; a healthy user bus is not audit visibility."""
    tool = shutil.which("auditctl", path="/usr/sbin:/usr/bin:/sbin:/bin")
    status = _command([tool, "-s"]) if tool else {"returncode": None, "error": "AUDITCTL_UNAVAILABLE"}
    blockers = []
    parsed = None
    if status["returncode"] != 0 or "stdout" not in status:
        blockers.append("KERNEL_AUDIT_STATUS_UNAVAILABLE")
    else:
        try:
            parsed = kernel_status(status["stdout"])
        except Refused as exc:
            blockers.append(exc.code)
    if parsed is not None:
        if parsed["enabled"] != 2 or parsed["pid"] <= 0:
            blockers.append("KERNEL_AUDIT_NOT_RUNNING_WITH_FROZEN_RULES")
        if parsed["backlog"]:
            blockers.append("KERNEL_AUDIT_UNDRAINED_BACKLOG")
    # Native collection/coverage for these independent channels is still required.
    blockers += ["SYSTEMD_BUS_AUDIT_COVERAGE_REQUIRED", "AUTHENTICATED_CONTROL_CORRELATION_REQUIRED"]
    return {
        "schema": "forge-c/host-audit-preflight/1",
        "host": socket.gethostname(),
        "uid": os.getuid(),
        "at": time.time(),
        "mono": time.monotonic(),
        "boot_id": soak._boot_id(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "auditctl_available": tool is not None,
        "kernel_status": parsed,
        "status_probe": {"returncode": status["returncode"], "error": status.get("error")},
        "required_channels": list(CHANNELS),
        "blockers": blockers,
        "status": "BLOCKED" if blockers else "READY_FOR_CAPTURE",
        "unexpected_interventions": None,
        "scope": "HOST_AUDIT_PREREQUISITES_ONLY",
    }


def read_protected_log(path):
    """Read a root-protected regular source and bind its exact prefix on one fd."""
    import stat

    path = Path(path).absolute()
    for parent in path.parents:
        s = parent.stat()
        if parent.is_symlink() or s.st_uid != 0 or s.st_mode & 0o022:
            raise Refused("KERNEL_AUDIT_LOG_ANCESTRY_NOT_PROTECTED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
            raise Refused("KERNEL_AUDIT_LOG_NOT_PROTECTED")
        if s.st_size > observer.MAX_BYTES:
            raise Refused("KERNEL_AUDIT_LOG_BOUND_EXCEEDED")
        raw = f.read(s.st_size)
        if len(raw) != s.st_size:
            raise Refused("KERNEL_AUDIT_LOG_TRUNCATED_DURING_READ")
    return raw, {
        "path": str(path),
        "device": s.st_dev,
        "inode": s.st_ino,
        "offset": 0,
        "length": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def kernel_window(before, after):
    """Loss/counter facts for one kernel channel, never a global intervention count."""
    reasons = []
    if any(before.get(k) != after.get(k) for k in ("host", "boot_id", "source_sha256", "host_plan_ref", "rules_sha256")):
        reasons.append("KERNEL_AUDIT_SOURCE_OR_BOOT_CHANGED")
    if not before.get("rules_sha256") or not after.get("rules_sha256"):
        reasons.append("KERNEL_AUDIT_RULES_UNKNOWN")
    if any(type(s.get(k)) not in (int, float) or not math.isfinite(s[k]) for s in (before, after) for k in ("at", "mono")):
        raise Refused("HOST_AUDIT_WINDOW_CLOCK_INVALID")
    if (
        after["at"] <= before["at"]
        or after["mono"] <= before["mono"]
        or abs((after["at"] - before["at"]) - (after["mono"] - before["mono"])) > soak.CLOCK_SKEW_S
    ):
        reasons.append("KERNEL_AUDIT_WINDOW_CLOCK_GAP")
    a, b = before.get("kernel_status"), after.get("kernel_status")
    delta = None
    if not isinstance(a, dict) or not isinstance(b, dict) or any(set(s) != STATUS_FIELDS for s in (a, b)):
        reasons.append("KERNEL_AUDIT_STATUS_UNKNOWN")
    elif any(type(v) is not int or v < 0 for s in (a, b) for v in s.values()):
        reasons.append("KERNEL_AUDIT_STATUS_UNKNOWN")
    else:
        if b["lost"] < a["lost"]:
            reasons.append("KERNEL_AUDIT_LOSS_COUNTER_RESET")
        else:
            delta = b["lost"] - a["lost"]
            if delta:
                reasons.append("KERNEL_AUDIT_RECORDS_LOST")
        if a["enabled"] != 2 or b["enabled"] != 2 or not a["pid"] or a["pid"] != b["pid"] or a["backlog"] or b["backlog"]:
            reasons.append("KERNEL_AUDIT_CAPTURE_NOT_STABLE")
    if any(before.get("kernel_log_ref", {}).get(k) != after.get("kernel_log_ref", {}).get(k) for k in ("device", "inode")):
        reasons.append("KERNEL_AUDIT_ROTATION_REQUIRES_SEGMENT_EVIDENCE")
    if not before.get("kernel_log_ref") or not after.get("kernel_log_ref"):
        reasons.append("KERNEL_AUDIT_LOG_UNKNOWN")
    if any(before["at"] <= e["at"] <= after["at"] for e in after.get("kernel_facts", {}).get("integrity_events", [])):
        reasons.append("KERNEL_AUDIT_DAEMON_OR_CONFIG_EVENT")
    return {
        "kernel_loss_delta": delta,
        "status": "INCOMPLETE" if reasons else "KERNEL_CHANNEL_FACTS_ONLY",
        "blockers": sorted(set(reasons)),
        "unexpected_interventions": None,
        "missing_channels": ["SYSTEMD_BUS", "AUTHENTICATED_CONTROLS"],
        "scope": "KERNEL_COUNTER_COMPARISON_NOT_HOST_INTERVENTION_VERIFICATION",
    }


def capture(manifest, observer_plan_ref, host_plan_ref, destination):
    frozen = observer.plan(manifest, observer_plan_ref)
    if host_plan_ref not in manifest["inputs"]:
        raise Refused("HOST_AUDIT_PLAN_NOT_FROZEN")
    plan = observer.bound_json(host_plan_ref)
    if (
        plan.get("schema") != "forge-c/host-audit-plan/1"
        or plan.get("observer_plan_ref") != observer_plan_ref
        or plan.get("source_sha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or plan.get("host") != socket.gethostname()
        or not isinstance(plan.get("keys"), list)
        or len(plan["keys"]) != 2
        or any(not isinstance(k, str) or not re.fullmatch(r"forgec014-[a-z-]{1,20}", k) for k in plan["keys"])
        or len(set(plan["keys"])) != 2
        or not isinstance(plan.get("kernel_log"), str)
        or not Path(plan["kernel_log"]).is_absolute()
    ):
        raise Refused("HOST_AUDIT_PLAN_INVALID")
    result = preflight()
    result.update(
        schema="forge-c/host-audit-source-capture/1",
        manifest_sha256=digest(manifest),
        observer_plan_ref=observer_plan_ref,
        host_plan_ref=host_plan_ref,
    )
    log = Path(plan["kernel_log"])
    if log.is_symlink() or not log.is_file():
        result["blockers"].append("KERNEL_AUDIT_LOG_UNAVAILABLE")
    else:
        try:
            raw, ref = read_protected_log(log)
            result["kernel_log_ref"] = ref
            result["kernel_facts"] = events(raw, host=plan["host"], keys=plan["keys"])
        except (OSError, ValueError) as exc:
            result["blockers"].append(getattr(exc, "code", type(exc).__name__))
    rules_ref = plan.get("rules_ref")
    if not isinstance(rules_ref, dict) or rules_ref not in manifest["inputs"]:
        result["blockers"].append("KERNEL_AUDIT_APPROVED_RULES_REQUIRED")
    else:
        expected = observer.read_bytes(rules_ref["path"])
        if hashlib.sha256(expected).hexdigest() != rules_ref["sha256"]:
            raise Refused("HOST_AUDIT_RULES_REFERENCE_CHANGED")
        tool = shutil.which("auditctl", path="/usr/sbin:/usr/bin:/sbin:/bin")
        actual = _command([tool, "-l"]) if tool else {}
        if actual.get("returncode") != 0 or "stdout" not in actual:
            result["blockers"].append("KERNEL_AUDIT_RULES_UNAVAILABLE")
        elif hashlib.sha256(actual["stdout"].encode()).hexdigest() != rules_ref["sha256"]:
            result["blockers"].append("KERNEL_AUDIT_RULES_CHANGED")
        elif not all(k in actual["stdout"] for k in plan["keys"]) or "never" in actual["stdout"]:
            result["blockers"].append("KERNEL_AUDIT_RULE_SCOPE_UNQUALIFIED")
        else:
            result["rules_sha256"] = rules_ref["sha256"]
    result["status"] = "INCOMPLETE_SOURCE_COVERAGE"
    immutable_json(observer.artifact(frozen, destination), result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("preflight", "capture"))
    p.add_argument("--manifest", type=Path)
    p.add_argument("--observer-plan-ref", type=Path)
    p.add_argument("--host-plan-ref", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    if args.command == "preflight":
        result = preflight()
        immutable_json(args.out, result)
    else:
        if not all((args.manifest, args.observer_plan_ref, args.host_plan_ref)):
            p.error("capture requires manifest, observer-plan-ref and host-plan-ref")
        result = capture(
            observer.read_json(args.manifest),
            observer.read_json(args.observer_plan_ref),
            observer.read_json(args.host_plan_ref),
            args.out,
        )
    print(json.dumps({k: result[k] for k in ("schema", "status", "blockers")}, sort_keys=True))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
