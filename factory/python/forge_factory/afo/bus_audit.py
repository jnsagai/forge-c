"""Bounded, read-only D-Bus visibility/source capture for host qualification.

Use dbus-monitor's header-only profile format. Its classic text format prints
unescaped bodies, so message arguments could impersonate headers in that format.
No body, environment, credentials or arbitrary command is retained or executed.
This is a source/visibility probe, not continuous coverage or an actor verdict.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import selectors
import shutil
import socket
import subprocess
import time
from pathlib import Path

from . import fault_observer as observer
from . import soak
from .durable import Refused

BUS = "org.freedesktop.DBus"
SYSTEMD = "org.freedesktop.systemd1"
ROOT = "/org/freedesktop/systemd1"
# D-Bus names are not limited to the numeric convention of dbus-daemon.
UNIQUE = re.compile(r"(?=.{1,255}\Z):[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+")
NAME = re.compile(r"(?=.{1,255}\Z)[A-Za-z_-][A-Za-z0-9_-]*(?:\.[A-Za-z_-][A-Za-z0-9_-]*)+")
INTERFACE = re.compile(r"(?=.{1,255}\Z)[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
MEMBER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,254}")
OBJECT = re.compile(r"/(?:[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*)?")
MAX_LINE = 4096
MAX_MESSAGES = 20000
PATH = "/usr/sbin:/usr/bin:/sbin:/bin"


def profile_line(raw):
    """Strict native dbus-monitor --profile line; no classic/body text accepted."""
    if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
        raise Refused("BUS_AUDIT_LINE_BOUND_OR_TRUNCATION")
    if raw in (b"#type\ttimestamp\tserial\tsender\tdestination\tpath\tinterface\tmember\n", b"#\t\t\t\t\tin_reply_to\n"):
        return None
    try:
        parts = raw[:-1].decode("ascii").split("\t")
    except UnicodeError as exc:
        raise Refused("BUS_AUDIT_PROFILE_ENCODING") from exc
    if len(parts) not in (6, 8) or parts[0] not in ("mc", "mr", "err", "sig"):
        raise Refused("BUS_AUDIT_PROFILE_INVALID")
    kind, stamp, serial, sender, destination = parts[:5]
    if (
        not re.fullmatch(r"[0-9]{1,16}\.[0-9]{6}", stamp)
        or not re.fullmatch(r"[0-9]{1,10}", serial)
        or not 1 <= int(serial) <= 2**32 - 1
        or not (UNIQUE.fullmatch(sender) or sender == BUS or sender == "<none>")
        or not (UNIQUE.fullmatch(destination) or NAME.fullmatch(destination) or destination == "<none>")
    ):
        raise Refused("BUS_AUDIT_PROFILE_HEADER_INVALID")
    result = {"kind": kind, "at": float(stamp), "serial": int(serial), "sender": sender, "destination": destination}
    if kind in ("mc", "sig"):
        if len(parts) != 8 or not OBJECT.fullmatch(parts[5]) or not (
            INTERFACE.fullmatch(parts[6]) or parts[6] == "<none>"
        ) or not MEMBER.fullmatch(parts[7]):
            raise Refused("BUS_AUDIT_PROFILE_HEADER_INVALID")
        result.update(path=parts[5], interface=parts[6], member=parts[7])
    else:
        if len(parts) != 6 or not re.fullmatch(r"[0-9]{1,10}", parts[5]) or not 1 <= int(parts[5]) <= 2**32 - 1:
            raise Refused("BUS_AUDIT_PROFILE_REPLY_INVALID")
        result["reply_serial"] = int(parts[5])
    result["source_line_sha256"] = hashlib.sha256(raw).hexdigest()
    return result


class Profile:
    """Incremental byte/message bounds; arbitrary chunk boundaries are harmless."""

    def __init__(self):
        self.pending = b""
        self.rows = []
        self.size = 0
        self.sha = hashlib.sha256()
        self.raw = bytearray()
        self.invalid = False

    def feed(self, data):
        try:
            self._feed(data)
        except Refused:
            self.invalid = True
            raise

    def _feed(self, data):
        self.size += len(data)
        if self.size > observer.MAX_BYTES:
            raise Refused("BUS_AUDIT_OUTPUT_BOUND_EXCEEDED")
        self.sha.update(data)
        self.raw.extend(data)
        self.pending += data
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            row = profile_line(line + b"\n")
            if row is not None:
                if len(self.rows) >= MAX_MESSAGES:
                    raise Refused("BUS_AUDIT_MESSAGE_BOUND_EXCEEDED")
                self.rows.append(row)
        if len(self.pending) > MAX_LINE:
            raise Refused("BUS_AUDIT_LINE_BOUND_OR_TRUNCATION")

    def finish(self):
        if self.pending:
            self.invalid = True
            raise Refused("BUS_AUDIT_LINE_BOUND_OR_TRUNCATION")

    def monitor_identity(self):
        acquired = {
            r["destination"] for r in self.rows
            if r["kind"] == "sig" and r["sender"] == BUS and r.get("path") == "/org/freedesktop/DBus"
            and r.get("interface") == BUS and r.get("member") == "NameAcquired" and UNIQUE.fullmatch(r["destination"])
        }
        lost = {
            r["destination"] for r in self.rows
            if r["kind"] == "sig" and r["sender"] == BUS and r.get("path") == "/org/freedesktop/DBus"
            and r.get("interface") == BUS and r.get("member") == "NameLost"
        }
        matches = acquired & lost
        return next(iter(matches)) if len(matches) == 1 else None

    def proves(self, probe):
        if not probe or probe.get("returncode") != 0:
            return False
        calls = [
            r for r in self.rows if r["kind"] == "mc" and r["sender"] == probe["destination"]
            and r["serial"] == probe["reply_serial"] and r["destination"] == BUS
            and r.get("path") == "/org/freedesktop/DBus" and r.get("interface") == BUS and r.get("member") == "GetId"
        ]
        replies = [
            r for r in self.rows if r["kind"] == "mr" and r["sender"] == BUS
            and r["destination"] == probe["destination"] and r["serial"] == probe["serial"]
            and r["reply_serial"] == probe["reply_serial"]
        ]
        return len(calls) == len(replies) == 1 and calls[0]["at"] <= replies[0]["at"]


def environment(scope):
    if scope not in ("user", "system"):
        raise Refused("BUS_AUDIT_SCOPE_INVALID")
    env = {"PATH": PATH, "LC_ALL": "C"}
    if scope == "user":
        address = os.environ.get("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
        if len(address) > 4096 or not address.startswith("unix:") or ";" in address or "\n" in address:
            raise Refused("BUS_AUDIT_LOCAL_ADDRESS_REQUIRED")
        env["DBUS_SESSION_BUS_ADDRESS"] = address
    return env


def _limits():
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))


def _query(tool, scope, env, member):
    # Only these two harmless bus-daemon queries are permitted. No service activation.
    if member not in ("GetId", "GetNameOwner"):
        raise Refused("BUS_AUDIT_QUERY_NOT_READ_ONLY")
    argv = [tool, "--session" if scope == "user" else "--system", "--print-reply", "--reply-timeout=1000",
            "--dest=" + BUS, "/org/freedesktop/DBus", BUS + "." + member]
    if member == "GetNameOwner":
        argv.append("string:" + SYSTEMD)
    # These fixed replies are small; RLIMIT_FSIZE bounds the anonymous temporary spool.
    import resource
    import tempfile

    def limits():
        _limits()
        resource.setrlimit(resource.RLIMIT_FSIZE, (8192, 8192))

    try:
        with tempfile.TemporaryFile() as out:
            r = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.DEVNULL,
                               timeout=2, check=False, start_new_session=True, preexec_fn=limits)
            out.seek(0)
            raw = out.read(8193)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"returncode": None, "error": type(exc).__name__}
    if r.returncode or len(raw) >= 8192:
        return {"returncode": r.returncode, "error": "BUS_QUERY_FAILED_OR_OVERSIZED"}
    # Reserved bus sender + unique recipient/reply identity, and one constrained value.
    pattern = (rb'method return time=[0-9]+\.[0-9]+ sender=org\.freedesktop\.DBus -> destination=([:A-Za-z0-9_.-]{1,255}) '
               rb'serial=([0-9]{1,10}) reply_serial=([0-9]{1,10})\n   string "([:A-Za-z0-9_.-]{1,255})"\n')
    match = re.fullmatch(pattern, raw)
    if match is None:
        return {"returncode": r.returncode, "error": "BUS_QUERY_FORMAT_UNKNOWN"}
    destination, serial, reply_serial, value = (v.decode("ascii") for v in match.groups())
    if (
        not UNIQUE.fullmatch(destination) or not 1 <= int(serial) <= 2**32 - 1 or not 1 <= int(reply_serial) <= 2**32 - 1
        or not (UNIQUE.fullmatch(value) if member == "GetNameOwner" else re.fullmatch(r"[0-9a-f]{32}", value))
    ):
        return {"returncode": r.returncode, "error": "BUS_QUERY_VALUE_UNKNOWN"}
    return {"returncode": 0, "destination": destination, "serial": int(serial), "reply_serial": int(reply_serial),
            "value": value, "reply_sha256": hashlib.sha256(raw).hexdigest()}


def source(scope="user", seconds=1.0):
    """Finite native monitor/probe; absence/denial/truncation is explicit UNKNOWN.

    NameLost for the monitor's acquired unique name demonstrates BecomeMonitor;
    old eavesdrop fallback cannot satisfy this proof. Two third-party GetId call/
    reply pairs demonstrate visibility at both boundaries, not continuous loss
    accounting or visibility on another bus, PID1 private socket or other host.
    """
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0.1 <= seconds <= 30:
        raise Refused("BUS_AUDIT_DURATION_INVALID")
    env = environment(scope)
    result = {"schema": "forge-c/systemd-bus-source/1", "host": socket.gethostname(), "boot_id": soak._boot_id(),
              "uid": os.getuid(), "bus": scope, "requested_seconds": seconds, "started_at": time.time(),
              "started_mono": time.monotonic(), "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "FINITE_BUS_VISIBILITY_AND_HEADERS_ONLY", "unexpected_interventions": None}
    blockers = []
    monitor = shutil.which("dbus-monitor", path=PATH)
    sender = shutil.which("dbus-send", path=PATH)
    stream = Profile()
    stderr_size = 0
    probes = []
    owner_before = owner_after = None
    process = None
    if not monitor or not sender:
        blockers.append("BUS_AUDIT_TOOLS_UNAVAILABLE")
    else:
        owner_before = _query(sender, scope, env, "GetNameOwner")
        matches = ["type='method_call',path_namespace='" + ROOT + "'",
                   "type='method_call',destination='" + SYSTEMD + "'",
                   "type='method_call',destination='" + BUS + "',interface='" + BUS + "',member='GetId'",
                   "type='method_return'", "type='error'",
                   "type='signal',sender='" + BUS + "',member='NameOwnerChanged',arg0='" + SYSTEMD + "'"]
        if owner_before.get("value"):
            matches.append("type='method_call',destination='" + owner_before["value"] + "'")
        result["match_rules"] = matches
        try:
            process = subprocess.Popen([monitor, "--session" if scope == "user" else "--system", "--profile", *matches],
                                       env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True, preexec_fn=_limits)
            with selectors.DefaultSelector() as poller:
                poller.register(process.stdout, selectors.EVENT_READ, "stdout")
                poller.register(process.stderr, selectors.EVENT_READ, "stderr")

                def drain(duration, predicate=None):
                    nonlocal stderr_size
                    end = time.monotonic() + duration
                    while time.monotonic() < end:
                        if predicate is not None and predicate():
                            return
                        for key, _ in poller.select(min(0.05, max(0, end - time.monotonic()))):
                            data = os.read(key.fileobj.fileno(), 8192)
                            if not data:
                                poller.unregister(key.fileobj)
                            elif key.data == "stdout":
                                stream.feed(data)
                            else:
                                stderr_size += len(data)
                                if stderr_size > 8192:
                                    raise Refused("BUS_AUDIT_DIAGNOSTIC_BOUND_EXCEEDED")
                        if process.poll() is not None:
                            raise Refused("BUS_AUDIT_MONITOR_EXITED")

                drain(1, stream.monitor_identity)
                if stream.monitor_identity() is None:
                    blockers.append("BUS_AUDIT_BECOME_MONITOR_NOT_PROVEN")
                probes.append(_query(sender, scope, env, "GetId"))
                drain(seconds)
                probes.append(_query(sender, scope, env, "GetId"))
                drain(1, lambda: stream.proves(probes[-1]))
                owner_after = _query(sender, scope, env, "GetNameOwner")
                drain(0.05)
                stream.finish()
        except (OSError, subprocess.SubprocessError, Refused) as exc:
            blockers.append(getattr(exc, "code", type(exc).__name__))
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
                process.stdout.close()
                process.stderr.close()
    if stderr_size:
        blockers.append("BUS_AUDIT_MONITOR_DIAGNOSTIC_OR_FALLBACK")
    if stream.monitor_identity() is None:
        blockers.append("BUS_AUDIT_BECOME_MONITOR_NOT_PROVEN")
    proofs = [stream.proves(p) for p in probes]
    if len(proofs) != 2 or not all(proofs) or probes[0].get("value") != probes[-1].get("value"):
        blockers.append("BUS_AUDIT_BOUNDARY_VISIBILITY_NOT_PROVEN")
    owners = [p.get("value") if p and p.get("returncode") == 0 else None for p in (owner_before, owner_after)]
    if not owners[0] or owners[0] != owners[1]:
        blockers.append("BUS_AUDIT_SYSTEMD_OWNER_UNKNOWN_OR_CHANGED")
    if any(r.get("member") == "NameOwnerChanged" and r["sender"] == BUS for r in stream.rows):
        blockers.append("BUS_AUDIT_SYSTEMD_OWNER_CHANGED_DURING_CAPTURE")
    if any(r.get("interface") == "org.freedesktop.DBus.Local" and r.get("member") == "Disconnected" for r in stream.rows):
        blockers.append("BUS_AUDIT_DISCONNECTED")
    requests = [r for r in stream.rows if r["kind"] == "mc" and (
        r["destination"] in (SYSTEMD, *[o for o in owners if o])
        or r.get("path") == ROOT or r.get("path", "").startswith(ROOT + "/")
    )]
    ended_at, ended_mono = time.time(), time.monotonic()
    if (
        abs((ended_at - result["started_at"]) - (ended_mono - result["started_mono"])) > soak.CLOCK_SKEW_S
        or ended_at < result["started_at"]
        or any(a["at"] > b["at"] for a, b in zip(stream.rows, stream.rows[1:], strict=False))
        or any(not result["started_at"] - soak.CLOCK_SKEW_S <= r["at"] <= ended_at + soak.CLOCK_SKEW_S for r in stream.rows)
    ):
        blockers.append("BUS_AUDIT_CLOCK_DISCONTINUITY")
    if soak._boot_id() != result["boot_id"] or result["boot_id"] == "unknown":
        blockers.append("BUS_AUDIT_BOOT_UNKNOWN_OR_CHANGED")
    result.update(ended_at=ended_at, ended_mono=ended_mono,
                  monitor_identity=stream.monitor_identity(), boundary_visibility=proofs, systemd_owners=owners,
                  bus_id_sha256=hashlib.sha256(probes[0]["value"].encode()).hexdigest()
                  if probes and probes[0].get("value") else None,
                  source_bytes=stream.size, stream_sha256=stream.sha.hexdigest(),
                  header_profile=bytes(stream.raw).decode("ascii") if not stream.invalid and not stream.pending else None,
                  messages=stream.rows, service_requests=[{**r, "actor": None, "effect": "UNKNOWN",
                                                        "unit_argument": None} for r in requests],
                  stderr_bytes=stderr_size, blockers=sorted(set(blockers)),
                  status="BLOCKED" if blockers else "BUS_VISIBILITY_AND_HEADERS_CAPTURED",
                  coverage="NOT_CONTINUOUS_OR_ACTOR_VERIFIED")
    return result
