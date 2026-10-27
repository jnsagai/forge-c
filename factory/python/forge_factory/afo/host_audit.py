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
from contextlib import contextmanager
from pathlib import Path

from . import fault_observer as observer
from . import soak
from .durable import Refused, canonical, digest, immutable_json

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


class EventReplay:
    """Ephemeral bounded assembly; no raw record is persisted or exposed.

    Interleaved events retain their node/time/serial identity across byte/file
    boundaries. End-of-input is never an implicit event boundary. This is a
    selected-field parser, not a replacement for the native audit/retention stack.
    """

    def __init__(self, *, host, keys, maximum=None):
        self.maximum = observer.MAX_TRACE_BYTES if maximum is None else maximum
        if type(self.maximum) is not int or not 1 <= self.maximum <= observer.MAX_TRACE_BYTES:
            raise Refused("HOST_AUDIT_EVENT_REPLAY_BOUND_INVALID")
        self.host, self.keys = host, keys
        self.groups = {}
        self.records = self.duplicates = self.input_bytes = 0
        self.partial = b""
        self.input_hash = hashlib.sha256()
        self.closed = self.failed = False

    def feed(self, raw):
        if self.closed or self.failed:
            raise Refused("HOST_AUDIT_EVENT_REPLAY_ALREADY_SETTLED")
        try:
            if not isinstance(raw, bytes) or len(raw) > observer.MAX_BYTES or self.input_bytes + len(raw) > self.maximum:
                raise Refused("HOST_AUDIT_LOG_BOUND_OR_TRUNCATION")
            self.input_bytes += len(raw)
            self.input_hash.update(raw)
            data = self.partial + raw
            start = 0
            while True:
                end = data.find(b"\n", start)
                if end < 0:
                    break
                if end - start > MAX_LINE:
                    raise Refused("HOST_AUDIT_RECORD_BOUND_EXCEEDED")
                try:
                    line = data[start:end].removesuffix(b"\r").decode("utf-8")
                except UnicodeError as exc:
                    raise Refused("HOST_AUDIT_LOG_ENCODING") from exc
                self._line(line)
                start = end + 1
            self.partial = data[start:]
            if len(self.partial) > MAX_LINE:
                raise Refused("HOST_AUDIT_RECORD_BOUND_EXCEEDED")
        except ValueError:
            self.failed = True
            raise

    def _line(self, line):
        if not line or len(line.encode()) > MAX_LINE:
            raise Refused("HOST_AUDIT_RECORD_BOUND_EXCEEDED")
        m = HEADER.fullmatch(line)
        if m is None:
            raise Refused("HOST_AUDIT_RECORD_HEADER_INVALID")
        node = m["node"] or self.host
        if node != self.host:
            raise Refused("HOST_AUDIT_LOG_HOST_MISMATCH")
        epoch = float(m["epoch"])
        if not math.isfinite(epoch):
            raise Refused("HOST_AUDIT_EVENT_CLOCK_INVALID")
        identity = (node, m["epoch"], int(m["serial"]))
        if identity not in self.groups:
            if len(self.groups) >= MAX_EVENTS:
                raise Refused("HOST_AUDIT_EVENT_COUNT_BOUND_EXCEEDED")
            self.groups[identity] = {"types": set(), "hashes": set(), "syscall": None, "paths": set()}
        group = self.groups[identity]
        sha = hashlib.sha256(line.encode()).hexdigest()
        if sha in group["hashes"]:
            self.duplicates += 1
            return
        group["hashes"].add(sha)
        group["types"].add(m["kind"])
        self.records += 1
        if self.records > MAX_RECORDS:
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

    def finish(self, *, legacy=False):
        if self.closed or self.failed:
            raise Refused("HOST_AUDIT_EVENT_REPLAY_ALREADY_SETTLED")
        self.closed = True
        if legacy and self.partial:
            raise Refused("HOST_AUDIT_LOG_BOUND_OR_TRUNCATION")
        selected, pending, integrity = [], [], []
        orphan = 0
        for (node, epoch, serial), group in sorted(self.groups.items(), key=lambda i: (float(i[0][1]), i[0][2])):
            syscall = group["syscall"]
            changes = [t for t in group["types"] if t.startswith("DAEMON_") or t == "CONFIG_CHANGE"]
            if changes:
                integrity.append({"host": node, "at": float(epoch), "serial": serial, "types": sorted(changes)})
            if syscall is None:
                if group["types"] & {"PATH", "EXECVE", "CWD", "PROCTITLE", "EOE", "SOCKADDR"}:
                    orphan += 1
                continue
            if syscall.get("key") not in self.keys:
                continue
            if int(syscall["items"]) > MAX_RECORDS:
                raise Refused("HOST_AUDIT_COMPOUND_EVENT_INCOMPLETE")
            path_coverage = group["paths"] == set(range(int(syscall["items"])))
            boundary = sorted(group["types"] & {"PROCTITLE", "EOE"})
            if legacy and not path_coverage:
                raise Refused("HOST_AUDIT_COMPOUND_EVENT_INCOMPLETE")
            if not legacy and (not path_coverage or not boundary):
                pending.append({"host": node, "at": float(epoch), "serial": serial,
                                "path_records": len(group["paths"]), "expected_path_records": int(syscall["items"]),
                                "path_item_coverage": path_coverage, "boundary_records": boundary,
                                "source_record_hashes": sorted(group["hashes"])})
                continue
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
        facts = {
            "events": selected,
            "integrity_events": integrity,
            "source_events": len(self.groups),
            "source_records": self.records,
            "duplicate_records": self.duplicates,
        }
        if legacy:
            return facts
        blockers = []
        if self.partial:
            blockers.append("KERNEL_EVENT_PARTIAL_LINE")
        if pending:
            blockers.append("KERNEL_EVENT_PENDING_COMPOUND_RECORDS")
        if orphan:
            blockers.append("KERNEL_EVENT_ORPHAN_COMPOUND_GROUPS")
        return {"schema": "forge-c/kernel-event-replay/1", "facts": facts,
                "status": "INCOMPLETE_EVENT_PREFIX" if blockers else "SELECTED_EVENT_FACTS_REPLAYED",
                "pending_events": pending, "orphan_compound_groups": orphan,
                "pending_line": {"length": len(self.partial), "sha256": hashlib.sha256(self.partial).hexdigest()},
                "input_bytes": self.input_bytes, "input_sha256": self.input_hash.hexdigest(),
                "blockers": blockers, "unexpected_interventions": None,
                "scope": "SELECTED_RECORD_FACTS_NOT_ALL_RECORD_COMPLETENESS_OR_HOST_COVERAGE"}


def events(raw, *, host, keys):
    """Compatible single-buffer facts; raw commands/argv/paths stay private."""
    replay = EventReplay(host=host, keys=keys, maximum=observer.MAX_BYTES)
    replay.feed(raw)
    return replay.finish(legacy=True)


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


@contextmanager
def protected_log(path):
    """Open one protected source; root ownership does not imply audit coverage."""
    import stat

    path = Path(path).absolute()
    for parent in path.parents:
        s = parent.stat()
        if parent.is_symlink() or s.st_uid != 0 or s.st_mode & 0o022:
            raise Refused("KERNEL_AUDIT_LOG_ANCESTRY_NOT_PROTECTED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
            raise Refused("KERNEL_AUDIT_LOG_NOT_PROTECTED")
        yield fd
    finally:
        os.close(fd)


def read_protected_log(path):
    """Read a root-protected regular source and bind its exact prefix on one fd."""
    path = Path(path).absolute()
    with protected_log(path) as fd:
        s = os.fstat(fd)
        if s.st_size > observer.MAX_BYTES:
            raise Refused("KERNEL_AUDIT_LOG_BOUND_EXCEEDED")
        raw = os.pread(fd, s.st_size, 0)
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


def _plans(manifest, observer_plan_ref, host_plan_ref):
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
    from . import bus_audit

    scopes = plan.get("bus_scopes", [])
    if (
        not isinstance(scopes, list) or len(scopes) > 2
        or any(not isinstance(s, str) or s not in ("user", "system") for s in scopes)
        or len(scopes) != len(set(scopes))
    ):
        raise Refused("HOST_AUDIT_BUS_SCOPES_INVALID")
    if scopes and plan.get("bus_source_sha256") != hashlib.sha256(Path(bus_audit.__file__).read_bytes()).hexdigest():
        raise Refused("HOST_AUDIT_BUS_SOURCE_NOT_FROZEN")
    segments = plan.get("segments")
    if segments is not None:
        from . import audit_segments

        audit_segments.configuration(segments, plan["kernel_log"])
    return frozen, plan


def _capture_record(manifest, frozen, plan, observer_plan_ref, host_plan_ref, ref):
    if (
        not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
        or not isinstance(ref["path"], str) or not isinstance(ref["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])
    ):
        raise Refused("HOST_AUDIT_CAPTURE_REFERENCE_INVALID")
    record = observer.bound_json(ref, path=observer.artifact(frozen, ref["path"]))
    if (
        not isinstance(record, dict) or record.get("schema") != "forge-c/host-audit-source-capture/1"
        or record.get("manifest_sha256") != digest(manifest)
        or record.get("host_plan_ref") != host_plan_ref or record.get("observer_plan_ref") != observer_plan_ref
        or record.get("source_sha256") != plan["source_sha256"] or record.get("host") != plan["host"]
    ):
        raise Refused("HOST_AUDIT_PREVIOUS_CAPTURE_UNBOUND")
    return record


def capture(manifest, observer_plan_ref, host_plan_ref, destination, *, previous_ref=None):
    frozen, plan = _plans(manifest, observer_plan_ref, host_plan_ref)
    from . import audit_segments, bus_audit

    segments = plan.get("segments")
    if segments is None and previous_ref is not None:
        raise Refused("HOST_AUDIT_SEGMENT_PLAN_REQUIRED_FOR_RESUME")
    previous, resume_ref = None, None
    if previous_ref is not None:
        prior = _capture_record(manifest, frozen, plan, observer_plan_ref, host_plan_ref, previous_ref)
        if "kernel_segment" in prior:
            previous, resume_ref = prior, previous_ref
        elif prior.get("resume_ref") is not None:
            resume_ref = prior["resume_ref"]
            previous = _capture_record(manifest, frozen, plan, observer_plan_ref, host_plan_ref, resume_ref)
            if "kernel_segment" not in previous:
                raise Refused("HOST_AUDIT_RESUME_CURSOR_UNAVAILABLE")
        if previous is not None:
            audit_segments.validate(previous["kernel_segment"], segments)
            sequence = previous["kernel_segment"].get("sequence")
            if type(sequence) is not int or not 0 <= sequence < 2**63 - 1:
                raise Refused("HOST_AUDIT_SEGMENT_SEQUENCE_INVALID")
    result = preflight()
    result.update(
        schema="forge-c/host-audit-source-capture/1",
        manifest_sha256=digest(manifest),
        observer_plan_ref=observer_plan_ref,
        host_plan_ref=host_plan_ref,
    )
    # A finite visibility probe adds factual sources; it cannot clear the
    # continuous-coverage or authenticated-control prerequisites by itself.
    result["bus_sources"] = [bus_audit.source(scope) for scope in plan.get("bus_scopes", [])]
    log = Path(plan["kernel_log"])
    if segments is not None:
        result["previous_capture_ref"] = previous_ref
        result["resume_ref"] = resume_ref
        try:
            _, segment = audit_segments.read(
                segments, previous["kernel_segment"]["cursor"] if previous else None,
                daemon_pid=(result.get("kernel_status") or {}).get("pid"),
            )
            segment.update(sequence=previous["kernel_segment"]["sequence"] + 1 if previous else 0,
                           previous_segment_ref=resume_ref)
            result["kernel_segment"] = segment
            # Byte ranges may split records/events. Do not pretend each range is
            # a complete compound event, or discard trailing source bytes.
            result["blockers"].append("KERNEL_SEGMENT_COMPOUND_EVENT_REPLAY_REQUIRED")
        except (OSError, ValueError) as exc:
            result["blockers"].append(getattr(exc, "code", type(exc).__name__))
    elif log.is_symlink() or not log.is_file():
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


def verify_segments(manifest, observer_plan_ref, host_plan_ref, refs, destination):
    """Replay an explicitly bounded, hash-bound successful-capture chain.

    Failed captures remain separate immutable history. They cannot advance the
    byte cursor or be represented as a successfully observed time window.
    """
    from . import audit_segments

    frozen, plan = _plans(manifest, observer_plan_ref, host_plan_ref)
    if plan.get("segments") is None:
        raise Refused("HOST_AUDIT_SEGMENT_PLAN_REQUIRED_FOR_REPLAY")
    if not isinstance(refs, list) or not 1 <= len(refs) <= audit_segments.MAX_SEGMENTS:
        raise Refused("HOST_AUDIT_SEGMENT_REFERENCES_INVALID")
    segments, previous_ref, budget, boots = [], None, observer.MAX_BYTES, set()
    for sequence, ref in enumerate(refs):
        record = _capture_record(manifest, frozen, plan, observer_plan_ref, host_plan_ref, ref)
        budget -= len(canonical(record))
        if budget < 0:
            raise Refused("HOST_AUDIT_SEGMENT_METADATA_BOUND_EXCEEDED")
        segment = record.get("kernel_segment")
        audit_segments.validate(segment, plan["segments"])
        if (type(segment.get("sequence")) is not int or segment["sequence"] != sequence
                or segment.get("previous_segment_ref") != previous_ref):
            raise Refused("HOST_AUDIT_SEGMENT_CAPTURE_CHAIN_DISCONTINUITY")
        rotation = segment.get("rotation")
        if rotation is not None:
            if not isinstance(rotation, dict) or not isinstance(rotation.get("observation"), dict):
                raise Refused("HOST_AUDIT_SEGMENT_ROTATION_INVALID")
            status = record.get("kernel_status")
            if (not isinstance(status, dict) or type(status.get("pid")) is not int
                    or rotation["observation"].get("pid") != status["pid"]):
                raise Refused("HOST_AUDIT_SEGMENT_DAEMON_BINDING_UNKNOWN")
        segments.append(segment)
        boot = record.get("boot_id")
        boots.add(boot if isinstance(boot, str) else None)
        previous_ref = ref
    errors = []
    if len(boots) != 1 or not isinstance(next(iter(boots)), str) or not re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", next(iter(boots))
    ):
        errors.append("KERNEL_EVENT_REPLAY_BOOT_CONTINUITY_UNKNOWN")
    replay = EventReplay(host=plan["host"], keys=plan["keys"])

    def consume(raw):
        if not errors:
            try:
                replay.feed(raw)
            except Refused as exc:
                errors.append(exc.code)

    byte_chain = audit_segments.verify_chain(plan["segments"], segments, consume=consume)
    event_replay = None
    if not errors:
        try:
            event_replay = replay.finish()
        except Refused as exc:
            errors.append(exc.code)
    if event_replay is None:
        event_replay = {"schema": "forge-c/kernel-event-replay/1", "status": "BLOCKED",
                        "facts": None, "blockers": errors, "unexpected_interventions": None,
                        "scope": "EVENT_REPLAY_UNAVAILABLE_NOT_ZERO"}
    elif event_replay["input_bytes"] != byte_chain["bytes"]:
        raise Refused("HOST_AUDIT_EVENT_REPLAY_INPUT_MISMATCH")
    event_replay["parser_source_sha256"] = plan["source_sha256"]
    result = {"schema": "forge-c/host-audit-segment-replay/1",
              "manifest_sha256": digest(manifest), "observer_plan_ref": observer_plan_ref,
              "host_plan_ref": host_plan_ref, "capture_refs_sha256": digest(refs),
              "first_capture_ref": refs[0], "last_capture_ref": refs[-1], "byte_chain": byte_chain,
              "kernel_event_replay": event_replay,
              "status": "INCOMPLETE_SOURCE_COVERAGE", "unexpected_interventions": None,
              "blockers": sorted(set(event_replay["blockers"] + [
                  "KERNEL_AUDIT_FULL_RECORD_AND_WINDOW_QUALIFICATION_REQUIRED",
                  "HOST_AUDIT_ALL_CHANNEL_CONTINUOUS_COVERAGE_REQUIRED"])),
              "scope": "CAPTURED_BYTE_PREFIX_NOT_HOST_INTERVENTION_VERIFICATION"}
    if len(canonical(result)) > observer.MAX_BYTES:
        raise Refused("HOST_AUDIT_SEGMENT_REPLAY_OUTPUT_BOUND_EXCEEDED")
    immutable_json(observer.artifact(frozen, destination), result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("preflight", "capture", "verify-segments", "bus-preflight"))
    p.add_argument("--bus", choices=("user", "system"), default="user")
    p.add_argument("--seconds", type=float, default=1)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--observer-plan-ref", type=Path)
    p.add_argument("--host-plan-ref", type=Path)
    p.add_argument("--previous-ref", type=Path)
    p.add_argument("--segment-refs", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    if args.command == "preflight":
        result = preflight()
        immutable_json(args.out, result)
    elif args.command == "bus-preflight":
        from . import bus_audit

        result = bus_audit.source(args.bus, args.seconds)
        immutable_json(args.out, result)
    else:
        if not all((args.manifest, args.observer_plan_ref, args.host_plan_ref)):
            p.error("capture/verify-segments requires manifest, observer-plan-ref and host-plan-ref")
        shared = (observer.read_json(args.manifest), observer.read_json(args.observer_plan_ref),
                  observer.read_json(args.host_plan_ref))
        if args.command == "verify-segments":
            if not args.segment_refs or args.previous_ref:
                p.error("verify-segments requires segment-refs and no previous-ref")
            result = verify_segments(*shared, observer.read_json(args.segment_refs), args.out)
        else:
            if args.segment_refs:
                p.error("segment-refs is only valid for verify-segments")
            result = capture(*shared, args.out,
                             previous_ref=observer.read_json(args.previous_ref) if args.previous_ref else None)
    print(json.dumps({k: result[k] for k in ("schema", "status", "blockers")}, sort_keys=True))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
