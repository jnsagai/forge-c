"""Explicit OS-owner supervised development, never a production grant/capability.

The private Intent-directory owner creates a content-bound record while acting as
its live guardian. Runtime agents have no minting MCP operation; their arbitrary executable
artifacts run only in scoped mounts without this control directory. Every consumer
rechecks the guardian, Intent, source and cumulative mission;
no request is admitted merely because a file contains an owner instruction.
"""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import socket
import struct
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from .durable import Refused, canonical, digest, strict_json

MODE = "OWNER_SUPERVISED_DEVELOPMENT"
FILE = "FORGE_OWNER_DEVELOPMENT_RECORD"
SHA = "FORGE_OWNER_DEVELOPMENT_SHA256"
SCHEMA = "forge-c/owner-supervised-development/1"
DIRECTIVE = "for now go on without needing signatures"
MISSION = "line-local-role-trial-20261104"
LINEAGE = "owner-review:local-role-trial-20261104"
INITIAL_AUTHORITY = "AUTH-AFO-REVIEW-20261104-LINE-FINITE"
ORDERS = tuple("WO-F014-SWE6-AFOQUAL-20261104-L90" + c for c in "BCD")
DRIVER = "STM32N6_CRC_HAL"
DEADLINE = 1795057626.0
CAPS = dict(max_attempts=4, max_jobs=4, max_requests=32, max_tokens=8388608, max_tools=256, max_corrections=4)
PROFILE = "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"
PROFILE_SHA = "32ef6621ebc44b3532e0d0c870493eb36c7d7a35e7b0f570224b5a32393f883c"
RUNTIME_POLICY_SHA = "dcd4fc785e373058c7ec4979319540623bcd06537c37baa1d68607850d21b17e"
LINE_POLICY_SHA = "c44a5ddf14b54740ee986fe1cf9a767957353b70e19fd66ab8ef5a12588c7740"
RUN_MODEL = "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"

ROLE_ENVELOPES = {
    "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0": "979be0ef65f688365747ec27ee06ccecf572779d53ff3424124e3f1c852b9af8",
    "qwen3.8:27b-q8_0": "0106c39092d46d07a2f15688dcde404e3212134ba629a858af48474b8353ae5f",
}
QUALITY_SHA = "4fcd28818fd411e3aaddf347e372487c694a6bf3ea88b07f1cc00d9ee1594b6b"

ACTIONS = {"submit_workorder", "launch_workorder", "recover_workorder", "reconcile_run", "finalize_blocked"}


def selected():
    return bool(os.environ.get(FILE) or os.environ.get(SHA))


def _fail(code):
    raise Refused("OWNER_DEVELOPMENT_" + code)


def _private(path, *, directory=False):
    try:
        st = path.stat()
        if path.is_symlink() or st.st_uid != os.getuid() or st.st_mode & 0o077:
            _fail("PRIVATE_OS_OWNER_REQUIRED")
        if directory != path.is_dir():
            _fail("PRIVATE_OS_OWNER_REQUIRED")
    except OSError as exc:
        raise Refused("OWNER_DEVELOPMENT_PRIVATE_OS_OWNER_REQUIRED") from exc


def guardian_alive(record):
    """Kernel identity of the external issuer, including mapped-reader UID views."""
    from ..lrtx.provider_process import identity

    try:
        pid = record["guardian_pid"]
        actual = identity(pid)
        owner = record["guardian"]["uid"]
        current_ns = os.readlink("/proc/self/ns/user")
        host_ns = record["control_context"]["user_namespace"]
        mapping = [list(map(int, line.split())) for line in Path("/proc/self/uid_map").read_text().splitlines()]
        if current_ns == host_ns:
            mapped_owner = owner
        elif mapping == [[0, owner, 1]] and os.getuid() == 0:
            mapped_owner = 0
        else:
            return False
        guardian_map = [list(map(int, line.split())) for line in Path(f"/proc/{pid}/uid_map").read_text().splitlines()]
        return bool(
            guardian_map == [[0, 0, 4294967295]]
            and actual
            and actual.get("state") != "Z"
            and os.readlink(f"/proc/{pid}/ns/user") == host_ns
            and actual["uid"] == mapped_owner
            and all(actual.get(k) == v for k, v in record["guardian"].items() if k != "uid")
        )
    except (OSError, ValueError, KeyError, Refused):
        return False


def mapped_host_guardian_alive(record):
    """Outer mapped Fabro/MCP consumers retain the original host PID namespace.

    They cannot read an ancestor nsfs link; the actual initial-map extent,
    original visible PID/start/boot and exact peer PID provide kernel proof.
    This does not change the stricter initial-host guardian_alive predicate.
    """
    try:
        pid = record["guardian_pid"]
        current_map = [list(map(int, line.split())) for line in Path("/proc/self/uid_map").read_text().splitlines()]
        if (
            current_map != [[0, record["guardian"]["uid"], 1]]
            or os.getuid() != 0
            or os.readlink("/proc/self/ns/pid") != record["guardian"]["pid_namespace"]
        ):
            return False
        raw = Path(f"/proc/{pid}/stat").read_text()
        fields = raw[raw.rfind(")") + 2 :].split()
        observed = [list(map(int, line.split())) for line in Path(f"/proc/{pid}/uid_map").read_text().splitlines()]
        lower = 0 if record["guardian"]["uid"] == 0 else 4294967295
        return (
            int(raw.split("(", 1)[0]) == pid
            and fields[0] != "Z"
            and fields[19] == record["guardian"]["start_ticks"]
            and Path("/proc/sys/kernel/random/boot_id").read_text().strip() == record["guardian"]["boot_id"]
            and observed == [[0, lower, 4294967295]]
        )
    except (OSError, ValueError, KeyError):
        return False


_GUARDIANS = {}  # External guardian memory, never reconstructed from an agent-writable record.
_HEARTBEAT_LOCK = threading.Lock()


def _publish_heartbeat(record, *, cycle=None, completed=False):
    """Private guardian liveness; completed-cycle progress is a separate fact.

    The existing nonce server can attest while a synchronous launcher waits for
    a model/stack. That proves guardian liveness, never product or cycle progress.
    Atomic replacement prevents the host guard observing a half-written JSON.
    """
    import stat
    import tempfile

    sha = digest(record)
    parent = Path(record["intent_path"]).parent / "owner-supervised-development"
    path = parent / (sha + ".heartbeat.json")
    if (cycle is not None and (type(cycle) is not int or cycle < 0)
            or type(completed) is not bool or completed and cycle is None):
        _fail("HEARTBEAT_PROGRESS_INVALID")
    with _HEARTBEAT_LOCK:
        _private(parent, directory=True)
        previous = {}
        if path.exists() or path.is_symlink():
            _private(path)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            try:
                observed = os.fstat(fd)
                if (not stat.S_ISREG(observed.st_mode) or observed.st_uid != os.getuid()
                        or observed.st_mode & 0o077 or observed.st_size > 16384):
                    _fail("HEARTBEAT_METADATA_INVALID")
                previous = strict_json(os.read(fd, 16385), 16384)
            finally:
                os.close(fd)
            if not isinstance(previous, dict):
                _fail("HEARTBEAT_METADATA_INVALID")
            if (
                previous.get("record_sha256") != sha
                or previous.get("pid") != record["guardian_pid"]
                or previous.get("mode") != MODE
                or previous.get("acceptance") != "UNACCEPTED"
            ):
                _fail("HEARTBEAT_IDENTITY_CHANGED")
            prior_cycle, last = previous.get("cycle"), previous.get("last_completed_cycle")
            completed_at = previous.get("last_cycle_completed_at")
            state = previous.get("cycle_state")
            if (
                set(previous) != {"schema", "mode", "acceptance", "record_sha256", "pid", "at", "liveness",
                                  "cycle", "cycle_state", "last_completed_cycle", "last_cycle_completed_at"}
                or previous["schema"] != "forge-c/owner-guardian-heartbeat/1"
                or previous["liveness"] != "GUARDIAN_RESPONSIVE_NOT_ENGINEERING_PROGRESS"
                or type(previous["at"]) not in (int, float) or not math.isfinite(previous["at"])
                or type(prior_cycle) is not int or type(last) is not int or not -1 <= last <= prior_cycle
                or not ((state == "NOT_STARTED" and prior_cycle == last == -1)
                        or (state == "IN_PROGRESS" and prior_cycle >= 0 and last < prior_cycle)
                        or (state == "COMPLETE" and prior_cycle >= 0 and last == prior_cycle))
                or not ((last == -1 and completed_at is None)
                        or (last >= 0 and type(completed_at) in (int, float) and math.isfinite(completed_at)))
            ):
                _fail("HEARTBEAT_METADATA_INVALID")
            if cycle is not None and (cycle < prior_cycle or not completed and cycle <= last):
                _fail("HEARTBEAT_PROGRESS_REBOUND")
        now = time.time()
        value = dict(
            schema="forge-c/owner-guardian-heartbeat/1", mode=MODE, acceptance="UNACCEPTED",
            record_sha256=sha, pid=record["guardian_pid"], at=now,
            liveness="GUARDIAN_RESPONSIVE_NOT_ENGINEERING_PROGRESS",
            cycle=previous.get("cycle", -1), cycle_state=previous.get("cycle_state", "NOT_STARTED"),
            last_completed_cycle=previous.get("last_completed_cycle", -1),
            last_cycle_completed_at=previous.get("last_cycle_completed_at"),
        )
        if cycle is not None:
            value.update(cycle=cycle, cycle_state="COMPLETE" if completed else "IN_PROGRESS")
            if completed:
                value.update(last_completed_cycle=cycle,
                             last_cycle_completed_at=(previous["last_cycle_completed_at"]
                                                      if previous.get("last_completed_cycle") == cycle else now))
        fd, temp = tempfile.mkstemp(prefix=".heartbeat-", dir=parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(canonical(value))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
            directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError as exc:
            raise Refused("OWNER_DEVELOPMENT_HEARTBEAT_STORAGE_UNAVAILABLE") from exc
        finally:
            try:
                os.unlink(temp)
            except FileNotFoundError:
                pass


@contextmanager
def _unix_path(path):
    # Linux AF_UNIX has a short pathname limit. Resolve an owned directory via
    # this process's fd rather than truncating/relocating its security boundary.
    p = Path(path)
    fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield f"/proc/self/fd/{fd}/" + p.name
    finally:
        os.close(fd)


def _serve_guardian(record, server):
    server.listen(8)
    server.settimeout(0.2)
    stop = threading.Event()
    sha = digest(record)

    def serve():
        last_heartbeat = None
        while not stop.is_set():
            try:
                client, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with client:
                client.settimeout(1)
                try:
                    data = client.recv(4097)
                    value = strict_json(data, 4096)
                    if not isinstance(value, dict):
                        continue
                    nonce = value.get("nonce")
                    if (
                        set(value) != {"record_sha256", "nonce"}
                        or value["record_sha256"] != sha
                        or not isinstance(nonce, str)
                        or not re.fullmatch("[0-9a-f]{64}", nonce)
                    ):
                        continue
                    # Publish before acknowledging the first challenge. The host
                    # launch guard calls current() before reading this heartbeat.
                    # Do not renew completed-cycle progress from an attestation.
                    now = time.monotonic()
                    if last_heartbeat is None or now - last_heartbeat >= 15:
                        _publish_heartbeat(record)
                        last_heartbeat = now
                    client.sendall(canonical(dict(record_sha256=sha, nonce=nonce, scope=MODE)))
                except (OSError, ValueError, Refused):
                    continue

    thread = threading.Thread(target=serve, name="owner-development-guardian", daemon=True)
    _GUARDIANS[sha] = (server, stop, thread)
    thread.start()


def close_guardian(ref):
    """Issuer teardown; revocation never settles/releases an uncertain native lease."""
    for sha, (server, stop, thread) in list(_GUARDIANS.items()):
        if sha + ".json" == Path(ref["path"]).name:
            stop.set()
            server.close()
            thread.join(timeout=2)
            del _GUARDIANS[sha]


def _attest(record, socket_path, *, private_view=False, mapped_host=False):
    """Authenticate a live issuer's retained digest, rather than trusting JSON provenance."""
    live = mapped_host_guardian_alive if mapped_host else guardian_alive
    if not private_view and not live(record):
        _fail("GUARDIAN_NOT_LIVE")
    nonce = secrets.token_hex(32)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            with _unix_path(socket_path) as address:
                client.connect(address)
            pid, uid, _ = struct.unpack("3i", client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            if uid != os.getuid() or (pid != record["guardian_pid"] and not (private_view and pid == 0)):
                _fail("GUARDIAN_SOCKET_PEER_CHANGED")
            client.sendall(canonical(dict(record_sha256=digest(record), nonce=nonce)))
            reply = strict_json(client.recv(4097), 4096)
        if reply != dict(record_sha256=digest(record), nonce=nonce, scope=MODE) or (not private_view and not live(record)):
            _fail("GUARDIAN_ATTESTATION_CHANGED")
    except (OSError, ValueError) as exc:
        raise Refused("OWNER_DEVELOPMENT_GUARDIAN_ATTESTATION_UNAVAILABLE") from exc


def _mission(store, control, *, anchor=None):
    from .mission_ledger import MissionLedger

    mission = MissionLedger(store).snapshot(MISSION)
    limits = mission["limits"]
    if (
        control["mission"] != {k: mission[k] for k in ("mission_id", "lineage", "limits")}
        or mission["lineage"] != LINEAGE
        or any(limits.get(k) != v for k, v in CAPS.items())
        or not time.time() < limits["deadline"] <= DEADLINE
        or mission.get("initial_authorization_ref", mission["authorization_ref"]) != INITIAL_AUTHORITY
        or mission["unbounded_historical_usage"]
    ):
        _fail("ORIGINAL_MISSION_REQUIRED")
    with store.tx() as c:
        base = json.loads(c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (MISSION,)).fetchone()[0])
    if base["authorization_ref"] != INITIAL_AUTHORITY:
        _fail("ORIGINAL_MISSION_REQUIRED")
    if anchor:
        if digest(base) != anchor["base_sha256"] or any(mission[k] < anchor["counters"][k] for k in anchor["counters"]):
            _fail("ACCOUNTING_REBOUND")
        if anchor["usage_unknown"] and not mission["usage_unknown"]:
            _fail("HISTORICAL_UNKNOWN_USAGE_CHANGED")
    if mission["attempts"] < 1 or mission["charged_tokens"] < 1048576:
        _fail("ORIGINAL_SPEND_REQUIRED")
    return mission, base


def _snapshot_store():
    from ..common import state_dir
    from .queue import ReadSnapshot

    return ReadSnapshot(state_dir() / "supervisor/line-queue.sqlite3", max_rows=10000, timeout_s=3)


def _read_file(ref):
    from .fault_observer import bound_json

    if (
        not isinstance(ref, dict)
        or set(ref) != {"path", "sha256"}
        or not Path(ref["path"]).is_absolute()
        or not re.fullmatch("[0-9a-f]{64}", str(ref["sha256"]))
    ):
        _fail("REFERENCE_INVALID")
    return bound_json(ref)


def _trial_envelopes(control):
    from .product_role_trial import resolve

    refs = control.get("product_role_trials") or {}
    if (
        set(refs) != set(ROLE_ENVELOPES)
        or control.get("role_capabilities")
        or control.get("qualified_local_alternatives")
        or control.get("product_role_trial") != refs.get(RUN_MODEL)
    ):
        _fail("ORIGINAL_ROLE_ENVELOPES_REQUIRED")
    for model, ref in refs.items():
        trial = resolve(ref)
        normalized = {
            role: [{k: v for k, v in identity.items() if k != "adapter_revision"} for identity in identities]
            for role, identities in trial["roles"].items()
        }
        if (
            digest(normalized) != ROLE_ENVELOPES[model]
            or trial.get("model") != model
            or trial.get("profile") != PROFILE
            or trial.get("source_revision") != control["source_revision"]
            or trial.get("deadline_epoch") != control["mission"]["limits"]["deadline"]
            or any(
                identity.get("adapter_revision") != control["source_revision"]
                for identities in trial["roles"].values()
                for identity in identities
            )
        ):
            _fail("ORIGINAL_ROLE_ENVELOPES_REQUIRED")


def validate_order(order):
    record = current()
    control = _read_file(record["control_ref"])
    if (
        order.get("wo") not in ORDERS
        or order.get("revision") != control["source_revision"]
        or order.get("profile") != PROFILE
        or order.get("driver_class") != DRIVER
        or order.get("purpose") != "ASPICE_ONLY"
        or order.get("example") != "0014m-crc-hal"
        or order.get("phase") != "SWE.6"
        or order.get("stop_after") != "SWE.6"
        or order.get("run_model") != RUN_MODEL
        or order.get("resume_from") != "WO-F014-SWE5-CRCHAL-20261104-L34G"
        or order.get("provided_from") != "WO-F014-SWE6-CRCL-20261103-L24"
        or order.get("durable_control") != record["control_ref"]
        or digest(order.get("quality")) != QUALITY_SHA
    ):
        _fail("ORIGINAL_ORDER_ENVELOPE_REQUIRED")


def validate_expiry_ticket(ticket, deadline):
    from ..lrtx.provider_process import boot_id

    required = {
        "remote_boot_id",
        "remote_monotonic",
        "remote_boottime",
        "fresh_until_monotonic",
        "deadline_monotonic",
        "external_utc_upper_at_remote_sample",
        "RTT_seconds",
        "clock_sync_waived_by_owner",
        "host_UTC_or_NTP_not_used",
        "anchor_sha256",
    }
    now = time.monotonic()
    if (
        not isinstance(ticket, dict)
        or set(ticket) != required
        or ticket["remote_boot_id"] != boot_id()
        or any(
            type(ticket[k]) not in (int, float) or not math.isfinite(ticket[k])
            for k in (
                "remote_monotonic",
                "remote_boottime",
                "fresh_until_monotonic",
                "deadline_monotonic",
                "external_utc_upper_at_remote_sample",
                "RTT_seconds",
            )
        )
        or not 0 < ticket["remote_monotonic"] <= now < ticket["fresh_until_monotonic"] <= ticket["remote_monotonic"] + 60
        or not 0 < ticket["remote_boottime"] <= time.clock_gettime(time.CLOCK_BOOTTIME) <= ticket["remote_boottime"] + 60
        or time.clock_gettime(time.CLOCK_BOOTTIME)
        >= (ticket["remote_boottime"] + ticket["deadline_monotonic"] - ticket["remote_monotonic"])
        or not now
        < ticket["deadline_monotonic"]
        <= ticket["remote_monotonic"] + deadline - ticket["external_utc_upper_at_remote_sample"]
        or not 0 <= ticket["RTT_seconds"] <= 2
        or ticket["external_utc_upper_at_remote_sample"] >= deadline
        or ticket["clock_sync_waived_by_owner"] is not True
        or ticket["host_UTC_or_NTP_not_used"] is not True
        or not re.fullmatch("[0-9a-f]{64}", str(ticket["anchor_sha256"]))
    ):
        _fail("ACTUAL_UTC_EXPIRY_TICKET_INVALID")


def create(store, *, control_ref, runtime_policy, line_policy, directive, expiry_ticket, controller_revision=None):
    """External operator only. Does not amend, admit, reserve or reset a mission.

    It must stay alive as the guardian. Production MCP does not expose creation,
    and its sandbox never receives this private writable Intent-directory mount.
    """
    from ..common import load_yaml, sha256_file
    from ..lrtx.provider_process import identity, owner_view
    from . import line_recovery_control as C
    from .operations import Intent, control_context
    from .policy import floor_violations, schema_errors

    if directive != DIRECTIVE or any(os.environ.get(k) for k in ("FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING")):
        _fail("EXTERNAL_OPERATOR_REQUIRED")
    if owner_view(os.getpid())["uid_map"] != [[0, 0, 4294967295]]:
        _fail("INITIAL_HOST_USER_NAMESPACE_REQUIRED")
    intent = Intent()
    _private(intent.path.parent, directory=True)
    with intent.lock():
        current_intent = intent.read()
        if current_intent["mode"] != "RUNNING":
            _fail("INTENT_NOT_RUNNING")
        old_context = current_intent.get("control_context") or {}
        context = control_context(intent.path, current_intent)
        if (
            not old_context
            or old_context.get("user_namespace") != context["user_namespace"]
            or old_context.get("uid_map") != context["uid_map"]
        ):
            _fail("EXTERNAL_OPERATOR_NAMESPACE_REQUIRED")
        control = C.read(control_ref)
        actual = C.revision()
        revisions = {control["source_revision"], controller_revision or control["source_revision"]}
        if (
            actual.get("dirty") is not False
            or actual.get("commit") not in revisions
            or any(not re.fullmatch("[0-9a-f]{40}", x) for x in revisions)
        ):
            _fail("SOURCE_CHANGED")
        if (
            str(intent.path) != control["operations_intent"]
            or C.profile_identity(control["profile"]) != control["profile_sha256"]
        ):
            _fail("CONTROL_CHANGED")
        runtime_policy = Path(runtime_policy).resolve()
        line_policy = Path(line_policy).resolve()
        raw = load_yaml(runtime_policy)
        from .line_orders import load_policy

        line = load_policy(line_policy)
        if (
            schema_errors(raw)
            or floor_violations(raw)
            or raw.get("mode") != "PILOT"
            or line.issues
            or line.get("mode") != "PILOT"
            or digest(raw) != RUNTIME_POLICY_SHA
            or line.sha256 != LINE_POLICY_SHA
            or control["profile"] != PROFILE
            or control["profile_sha256"] != PROFILE_SHA
            or digest(raw) != control["policy_sha256"]
            or raw.get("authorization_ref") != INITIAL_AUTHORITY
        ):
            _fail("POLICY_INVALID")
        _trial_envelopes(control)
        mission, base = _mission(store, control)
        validate_expiry_ticket(expiry_ticket, mission["limits"]["deadline"])
        parent = intent.path.parent / "owner-supervised-development"
        parent.mkdir(mode=0o700, exist_ok=True)
        _private(parent, directory=True)
        socket_path = parent / ("guardian-" + secrets.token_hex(12) + ".sock")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with _unix_path(socket_path) as address:
            server.bind(address)
        os.chmod(socket_path, 0o600)
        socket_stat = socket_path.stat()
        record = dict(
            schema=SCHEMA,
            mode=MODE,
            qualification_only=True,
            acceptance="UNACCEPTED",
            directive_sha256=digest(dict(external_directive=DIRECTIVE)),
            expiry_ticket=expiry_ticket,
            # BOOTTIME includes suspend; MONOTONIC alone would extend UTC authority.
            expiry_boottime_deadline=(
                expiry_ticket["remote_boottime"] + expiry_ticket["deadline_monotonic"] - expiry_ticket["remote_monotonic"]
            ),
            guardian_socket=str(socket_path),
            guardian_socket_identity=dict(device=socket_stat.st_dev, inode=socket_stat.st_ino),
            guardian_userns_inode=os.stat("/proc/self/ns/user").st_ino,
            store_path=str(store.path.resolve()),
            store_identity=dict(device=store.path.stat().st_dev, inode=store.path.stat().st_ino),
            guardian_pid=os.getpid(),
            guardian={k: v for k, v in identity(os.getpid()).items() if k != "state"},
            guardian_view=owner_view(os.getpid()),
            control_context=context,
            intent_path=str(intent.path),
            intent_epoch=current_intent["epoch"],
            control_ref=control_ref,
            control_sha256=digest(control),
            source_revisions=sorted(revisions),
            runtime_policy_ref=dict(path=str(runtime_policy), sha256=sha256_file(runtime_policy)),
            runtime_policy_sha256=digest(raw),
            line_policy_ref=dict(path=str(line_policy), sha256=sha256_file(line_policy)),
            line_policy_sha256=line.sha256,
            mission=control["mission"],
            mission_anchor=dict(
                base_sha256=digest(base),
                counters={k: mission[k] for k in ("attempts", "jobs", "requests", "tools", "corrections", "charged_tokens")},
                usage_unknown=mission["usage_unknown"],
            ),
            order_ids=list(ORDERS),
            driver_class=DRIVER,
            profile=control["profile"],
            profile_sha256=control["profile_sha256"],
            trial_refs=control.get("product_role_trials") or {},
            issued_at=time.time(),
        )
        parent = intent.path.parent / "owner-supervised-development"
        parent.mkdir(mode=0o700, exist_ok=True)
        _private(parent, directory=True)
        path = parent / (digest(record) + ".json")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(record))
            stream.flush()
            os.fsync(stream.fileno())
        # A runtime JSON/env reference is never its own origin authority. This
        # append-only row is issued only after the host-kernel owner check.
        with store.tx() as c:
            c.execute(
                "INSERT INTO afo_independent_decisions VALUES (?,?,?,?)",
                ("owner-development-" + digest(record), MODE, canonical(record).decode(), digest(record)),
            )
        _serve_guardian(record, server)
        return dict(path=str(path), sha256=sha256_file(path))


def current(*, store=None):
    from ..common import sha256_file
    from . import line_recovery_control as C
    from .operations import Intent

    if store is None:
        with _snapshot_store() as reader:
            return current(store=reader)
    ref = dict(path=os.environ.get(FILE, ""), sha256=os.environ.get(SHA, ""))
    p = Path(ref["path"])
    intent = Intent()
    expected = intent.path.parent / "owner-supervised-development"
    if not p.is_absolute() or p.parent != expected or p.name != p.stem + ".json":
        _fail("REFERENCE_INVALID")
    _private(intent.path.parent, directory=True)
    _private(expected, directory=True)
    _private(p)
    if sha256_file(p) != ref["sha256"]:
        _fail("RECORD_CHANGED")
    record = strict_json(p.read_bytes(), 1024 * 1024)
    if (
        record.get("schema") != SCHEMA
        or record.get("mode") != MODE
        or record.get("acceptance") != "UNACCEPTED"
        or record.get("qualification_only") is not True
        or p.stem != digest(record)
        or record.get("directive_sha256") != digest(dict(external_directive=DIRECTIVE))
    ):
        _fail("RECORD_INVALID")
    state = intent.read()
    if (
        record["expiry_ticket"]["remote_boot_id"] != Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        or time.monotonic() >= record["expiry_ticket"]["deadline_monotonic"]
        or time.clock_gettime(time.CLOCK_BOOTTIME) >= record["expiry_boottime_deadline"]
    ):
        _fail("ACTUAL_UTC_WINDOW_EXPIRED")
    current_context = state.get("control_context") or {}
    if (
        any(record["control_context"].get(k) != current_context.get(k) for k in ("user_namespace", "uid_map"))
        or record["intent_path"] != str(intent.path)
        or state["mode"] != "RUNNING"
        or state["epoch"] != record["intent_epoch"]
    ):
        _fail("INTENT_FENCED")
    if (
        Path(store.path).is_symlink()
        or str(store.path.resolve()) != record["store_path"]
        or dict(device=store.path.stat().st_dev, inode=store.path.stat().st_ino) != record["store_identity"]
    ):
        _fail("CANONICAL_STORE_REBOUND")
    with store.tx() as c:
        authority = c.execute(
            "SELECT record,sha256 FROM afo_independent_decisions WHERE decision_id=? AND kind=?",
            ("owner-development-" + digest(record), MODE),
        ).fetchone()
    if not authority or authority[1] != digest(record) or strict_json(authority[0].encode(), 1024 * 1024) != record:
        _fail("ISSUER_STORE_BINDING_REQUIRED")
    mapped_host = False
    if guardian_alive(record) or (mapped_host := mapped_host_guardian_alive(record)):
        socket_path = record["guardian_socket"]
        st = Path(socket_path).stat()
        if dict(device=st.st_dev, inode=st.st_ino) != record["guardian_socket_identity"]:
            _fail("GUARDIAN_SOCKET_NODE_REBOUND")
        private_view = False
    else:
        from .owner_development_view import current as provider_view

        socket_path = provider_view(record, store)
        private_view = True
    _attest(record, socket_path, private_view=private_view, mapped_host=mapped_host)
    if private_view:
        provider_view(record, store)  # Fresh kernel identity after the challenge.
    actual = C.revision()
    if actual.get("dirty") is not False or actual.get("commit") not in record["source_revisions"]:
        _fail("SOURCE_CHANGED")
    control = C.read(record["control_ref"])
    if digest(control) != record["control_sha256"] or C.profile_identity(record["profile"]) != record["profile_sha256"]:
        _fail("CONTROL_CHANGED")
    for key in ("runtime_policy_ref", "line_policy_ref"):
        ref = record[key]
        if sha256_file(Path(ref["path"])) != ref["sha256"]:
            _fail("POLICY_CHANGED")
    _mission(store, control, anchor=record["mission_anchor"])
    return record


def permit(eff, action, request):
    if eff.mode != MODE:
        return False
    record = current()
    control = _read_file(record["control_ref"])
    models = {record["profile"], *record["trial_refs"]}
    return (
        action in ACTIONS
        and request.get("order_id") in record["order_ids"]
        and request.get("driver_class") == record["driver_class"]
        and request.get("model") in models
        and set(request) <= {"order_id", "driver_class", "model", "service_action"}
        and request.get("service_action") in (None, "line_stack_restart", "line_orphan_sweep")
        and digest(control) == record["control_sha256"]
        and eff.sha256 == record["runtime_policy_sha256"]
    )


def effective(pol, sha, path):
    from .policy import Effective

    record = current()
    if Path(path).resolve() != Path(record["runtime_policy_ref"]["path"]) or sha != record["runtime_policy_sha256"]:
        _fail("POLICY_CHANGED")
    return Effective(MODE, "PILOT", sha, pol, ["OWNER_SUPERVISED_DEVELOPMENT_UNACCEPTED"], INITIAL_AUTHORITY)


def control_authorized(ref, value, eff, request):
    record = current()
    if (
        ref != record["control_ref"]
        or digest(value) != record["control_sha256"]
        or not permit(eff, "recover_workorder", request or {})
    ):
        _fail("CONTROL_SCOPE_CHANGED")
    return True


def require_job_context(job):
    """An existing job cannot inherit a newly issued guardian lifetime."""
    native = job.get("native_context") or {}
    if (
        job.get("execution_scope") != MODE
        or job.get("qualification_only") is not True
        or job.get("acceptance") != "UNACCEPTED"
        or native.get(FILE) != os.environ.get(FILE)
        or native.get(SHA) != os.environ.get(SHA)
    ):
        _fail("JOB_AUTHORITY_REBOUND")
    current()


def trial_authorized(ref, job, eff, request):
    record = current()
    if (
        ref not in record["trial_refs"].values()
        or job.get("mission_id", MISSION) != MISSION
        or (job.get("factory_revision") or {}).get("commit") != _read_file(record["control_ref"])["source_revision"]
        or not permit(eff, "recover_workorder", request)
    ):
        _fail("TRIAL_SCOPE_CHANGED")
    return True


class DevelopmentGrant:
    """Existing Placer protocol, with truthful OS-owner development provenance."""

    def __init__(self, policy):
        record = current()
        if policy.issues or policy.sha256 != record["line_policy_sha256"]:
            _fail("LINE_POLICY_CHANGED")
        self.policy = policy
        self.allow = True
        self.code = "OWNER_SUPERVISED_DEVELOPMENT_UNACCEPTED"
        self.authorization_id = "owner-development-" + digest(record)[:24]
        self.expires_utc = (
            __import__("datetime")
            .datetime.fromtimestamp(record["mission"]["limits"]["deadline"], __import__("datetime").UTC)
            .isoformat()
        )

    def permit(self, action, request=None):
        from .authz import AuthDecision
        from .policy import load

        allowed = permit(load(), action, request or {})
        return AuthDecision(
            allowed,
            self.code if allowed else "OWNER_DEVELOPMENT_SCOPE_REFUSED",
            "Unaccepted OS-owner supervised qualification only",
            self.authorization_id,
        )

    def view(self):
        return dict(
            authorization_id=self.authorization_id, code=self.code, expires_at=self.expires_utc, policy_sha256=self.policy.sha256
        )


def _untrusted_scope(record, writable, readable):
    """Never overmount protected host control/history as agent scratch/input."""
    root = Path(record["store_path"]).parents[2]
    protected = [
        Path(record["intent_path"]).parent,
        Path(record["store_path"]).parent,
        root / "run",
        Path(record["runtime_policy_ref"]["path"]),
        Path(record["line_policy_ref"]["path"]),
        Path(record["control_ref"]["path"]),
    ]
    for p in [*writable, *readable]:
        p = Path(p).resolve()
        if any(p.is_relative_to(q.resolve()) or q.resolve().is_relative_to(p) for q in protected):
            _fail("PRIVILEGED_EXECUTION_MOUNT_DENIED")


def contained_argv(cmd, *, cwd, env):
    """Untrusted native artifacts cannot mutate/re-enter the trusted host issuer.

    User namespaces alone preserve host DAC access. The existing scoped mount,
    PID and network isolator is mandatory for this experimental lane; no socket,
    owner HOME, control directory or writable factory checkout is exposed.
    """
    import shutil

    from ..reliability import isolation

    record = current()
    if not shutil.which("bwrap"):
        _fail("SCOPED_EXECUTION_UNAVAILABLE")
    cwd = Path(cwd).resolve()
    workspace = next((p for p in (cwd, *cwd.parents) if (p / ".forge-run/manifest.json").is_file()), cwd)
    from ..common import REPO_ROOT

    if cwd.is_relative_to(REPO_ROOT) or REPO_ROOT.is_relative_to(cwd):
        _fail("TRUSTED_SOURCE_WRITE_DENIED")
    _untrusted_scope(record, [cwd], [workspace])
    return isolation.bubblewrap_argv("repair", cmd, cwd=cwd, env=env, writable=[cwd], readable=[workspace])


def native_process(argv, *, directory, readable=(), **kwargs):
    """Existing non-MCP compiled-artifact consumers get the same dev confinement.

    The legacy subprocess contract is unchanged outside this explicit channel.
    Caller-supplied scratch/inputs remain the sole writable/readable additions.
    """
    import subprocess

    if not selected():
        return subprocess.run(argv, **kwargs)
    import shutil

    from ..reliability import isolation

    record = current()
    if not shutil.which("bwrap"):
        _fail("SCOPED_EXECUTION_UNAVAILABLE")
    directory = Path(directory).resolve()
    from ..common import REPO_ROOT

    if directory.is_relative_to(REPO_ROOT) or REPO_ROOT.is_relative_to(directory):
        _fail("TRUSTED_SOURCE_WRITE_DENIED")
    env = kwargs.pop("env", None) or os.environ.copy()
    _untrusted_scope(record, [directory], readable)
    command = isolation.bubblewrap_argv("repair", argv, cwd=directory, env=env, writable=[directory], readable=readable)
    return subprocess.run(command, **{**kwargs, "cwd": directory, "env": env})


def require_compatible_provider(instance):
    """No silent reuse of a serving lifetime belonging to another guardian."""
    record = current()
    view = instance.get("owner_development_view") or {}
    if (
        instance.get("root") != str(Path(record["store_path"]).parents[2])
        or instance.get("profile") != record["profile"]
        or instance.get("profile_sha256") != record["profile_sha256"]
        or view.get("record_sha256") != digest(record)
        or view.get("socket_identity") != record["guardian_socket_identity"]
        or view.get("store_identity") != record["store_identity"]
        or view.get("store_path") != record["store_path"]
    ):
        _fail("KNOWN_PROVIDER_REPLACEMENT_REQUIRED")


def provider_preflight(root):
    """Before queue admission/spend, distinguish absent/compatible/replacement/unknown.

    Known replacement is not performed by this healthy loop. The live guardian
    remains available while the external M0 owner uses the existing identity-
    checked retirement/cleanup APIs under their ordinary quiescence fences.
    """
    record = current()
    root = Path(root).resolve()
    if root != Path(record["store_path"]).parents[2]:
        _fail("CANONICAL_STORE_REBOUND")
    path = root / "run/services.json"
    if not path.exists() and not path.is_symlink():
        return dict(state="ABSENT", placing=True)
    try:
        if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o022:
            _fail("SERVICES_IDENTITY_UNKNOWN")
        services = strict_json(path.read_bytes(), 65536)
        from ..lrtx import provider_process as provider
        from ..lrtx import stack

        instance = services.get("serving_instance")
        if instance:
            actual = stack.serving_instance(dict(root=root, profile=dict(id=record["profile"], _sha256=record["profile_sha256"])))
            if provider.quiet(actual):
                return dict(state="ABSENT", placing=True, proof="EXISTING_KERNEL_PROVIDER_QUIESCENCE")
            try:
                require_compatible_provider(actual)
            except Refused as exc:
                return dict(state="NEEDS_KNOWN_RETIREMENT", placing=False, code=exc.code)
            return dict(state="COMPATIBLE", placing=True)
        live = False
        for process in (services.get("processes") or {}).values():
            actual = stack.process_identity(process["pid"])
            if actual is not None:
                expected = process.get("identity")
                if expected and any(actual.get(k) != expected.get(k) for k in ("boot_id", "start_ticks", "uid")):
                    _fail("SERVICES_IDENTITY_UNKNOWN")
                live = True
        return dict(
            state="NEEDS_KNOWN_RETIREMENT" if live else "ABSENT",
            placing=not live,
            code="LEGACY_LIFETIME_REQUIRES_NORMAL_OWNED_QUIESCENT_REPLACEMENT" if live else "NO_RECORDED_LIVE_PROCESS",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(state="UNKNOWN", placing=False, code=getattr(exc, "code", type(exc).__name__))


def main(argv=None):
    """Explicit external engineering producer, using the existing placer/worker.

    It writes no production observer heartbeat/feed and owns no second queue.
    A lost guardian closes new authority; existing durable workers keep their
    nonce/UNKNOWN leases until their ordinary native/provider settlement.
    """
    import argparse
    import signal

    from ..common import state_dir
    from .line_launcher import LineConfig
    from .line_orders import Placer, RealLine
    from .line_recovery_coordination import reference
    from .queue import Store

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control", required=True, type=Path)
    ap.add_argument("--runtime-policy", required=True, type=Path)
    ap.add_argument("--line-policy", required=True, type=Path)
    ap.add_argument("--campaigns", required=True, type=Path)
    ap.add_argument("--expiry-ticket", required=True, type=Path)
    ap.add_argument("--interval", type=float, default=30)
    ap.add_argument("--max-cycles", type=int)
    ap.add_argument("--bootstrap-managed-profile", action="store_true",
                    help="external issuer only: scoped canonical managed startup before any placement")
    ap.add_argument("--reconcile-bootstrap-intent")
    ap.add_argument("--reconcile-bootstrap-result-sha256")
    ap.add_argument("--reconcile-bootstrap-evidence", type=Path)
    ap.add_argument("--reconcile-bootstrap-evidence-sha256")
    a = ap.parse_args(argv)
    if (
        os.environ.get("FORGE_AFO_QUEUE_SCOPE") != "line-local"
        or os.environ.get("FORGE_DURABLE_AUTONOMY") != "1"
        or os.environ.get("FORGE_DURABLE_NATIVE_HEADER") != "1"
        or not 1 <= a.interval <= 300
        or a.max_cycles is not None
        and a.max_cycles < 1
    ):
        _fail("EXPLICIT_DURABLE_LOCAL_INPUTS_REQUIRED")
    reconciliation_args = (a.reconcile_bootstrap_intent, a.reconcile_bootstrap_result_sha256,
                           a.reconcile_bootstrap_evidence, a.reconcile_bootstrap_evidence_sha256)
    if any(reconciliation_args) and (not all(reconciliation_args) or not a.bootstrap_managed_profile):
        _fail("EXPLICIT_COMPLETE_BOOTSTRAP_RECONCILIATION_REQUIRED")
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    from .line_recovery_control import revision

    ref = create(
        store,
        control_ref=reference(a.control),
        runtime_policy=a.runtime_policy,
        line_policy=a.line_policy,
        directive=DIRECTIVE,
        expiry_ticket=strict_json(a.expiry_ticket.read_bytes(), 65536),
        controller_revision=revision()["commit"],
    )
    old_env = {key: os.environ.get(key) for key in (FILE, SHA, "FORGE_AFO_POLICY")}
    os.environ.update({FILE: ref["path"], SHA: ref["sha256"], "FORGE_AFO_POLICY": str(a.runtime_policy.resolve())})
    cfg = LineConfig.from_env()
    producer = "owner-supervised-development-" + str(os.getpid())
    placer = Placer(
        RealLine(cfg),
        line_id="local",
        policy_path=a.line_policy,
        campaigns_dir=a.campaigns,
        recovery_config=a.control,
        unit=producer,
        owner_supervised_development=True,
    )
    stop = threading.Event()
    old_signals = {signum: signal.getsignal(signum) for signum in (signal.SIGTERM, signal.SIGINT)}
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    audit = Path(ref["path"]).with_suffix(".audit.jsonl")
    n = 0
    try:
        if a.bootstrap_managed_profile:
            from .owner_profile_bootstrap import bootstrap

            reconciled = None
            if all(reconciliation_args):
                from .owner_profile_bootstrap import reconcile_unknown

                reconciled = reconcile_unknown(store, placer, intent_id=a.reconcile_bootstrap_intent,
                    result_sha256=a.reconcile_bootstrap_result_sha256,
                    evidence_ref=dict(path=str(a.reconcile_bootstrap_evidence), sha256=a.reconcile_bootstrap_evidence_sha256),
                    cancelled=stop.is_set)
            if reconciled is None:
                bootstrap(store, placer, cancelled=stop.is_set)
            else:
                bootstrap(store, placer, cancelled=stop.is_set, reconciliation_ref=reconciled)
        while not stop.is_set() and (a.max_cycles is None or n < a.max_cycles):
            live_record = current(store=store)
            _publish_heartbeat(live_record, cycle=n)
            readiness = provider_preflight(cfg.stack_root)
            result = placer.cycle() if readiness["placing"] else dict(mode=MODE, actions=[], readiness=readiness)
            # No submit/admission or PRODUCT reservation occurs while replacement
            # or observation is unknown. Guardian stays live for normal M0 work.
            row = dict(
                schema="forge-c/owner-development-cycle/1",
                mode=MODE,
                acceptance="UNACCEPTED",
                pid=os.getpid(),
                record_ref=ref,
                cycle=n,
                at=time.time(),
                placement=result,
                provider_readiness=readiness,
            )
            with audit.open("ab") as stream:
                stream.write(canonical(row) + b"\n")
            _publish_heartbeat(live_record, cycle=n, completed=True)
            n += 1
            if a.max_cycles is None or n < a.max_cycles:
                stop.wait(a.interval)
    finally:
        close_guardian(ref)
        for signum, handler in old_signals.items():
            signal.signal(signum, handler)
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
