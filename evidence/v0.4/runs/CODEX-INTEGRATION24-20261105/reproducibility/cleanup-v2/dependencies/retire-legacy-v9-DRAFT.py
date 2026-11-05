"""One-time external OS-owner adoption/retirement; default read-only. No AI/MCP entrypoint.

The original mixed-view services record is retained without correction. Only its
exact recorded llama UID0 / actual host UID1000 discrepancy may be adopted with
fresh original PID/start/boot/argv plus actual mapped owner namespace proof.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import signal
import sqlite3
import stat
import subprocess
import struct
import sys
import time
from pathlib import Path

SOURCE_REVISION = "dc27abba601e5f6713f30e6027cb0bbd64241528"
SOURCE = Path("/mnt/data/forge-c/swe1-fabro-20261031/qualification/owner-development-dc27abba-review-20261105/source")
ROOT = Path("/mnt/data/forge-c/swe1-fabro-20261031/lrtx")
EXPECTED_SHA = "771b4c25e67d62edbbdd41c87a931ad3c0c98977d8d554b0d737efe551458d98"
NAMESPACE_SHA = "3f258f632ffb138af27de431419dfb5e221eb30b9b2a29b57adecea3661a7bbd"
SERVICES_SHA = "61f5126b052970858695441c7a0343bb3889291a34c0abb33e3d390a8691aa3e"
ORDER = ("fabro", "gateway", "llama_server", "ollama")
OWNER_UID = 1000


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def kernel_argv_vector(raw):
    """Decode the actual NUL vector; preserve every empty arg except its final terminator."""
    require(isinstance(raw, bytes) and bool(raw) and raw.endswith(b"\0"), "KERNEL_ARGV_TERMINATOR_INVALID")
    try:
        return [part.decode("utf-8", errors="strict") for part in raw[:-1].split(b"\0")]
    except UnicodeDecodeError as exc:
        raise RuntimeError("KERNEL_ARGV_UTF8_INVALID") from exc


def adopt(name, saved, current, namespace, holder, uid, argv_sha):
    """Fresh owner adoption, never a claim the old UID0 value was correct."""
    require(current is not None, "ADOPTION_PROCESS_ABSENT_OR_UNKNOWN")
    require(current["pid"] == saved["pid"], "ADOPTION_PID_REBOUND")
    require(uid == OWNER_UID and current["uid"] == uid, "ADOPTION_FOREIGN_UID")
    require(current["state"] != "Z", "ADOPTION_PROCESS_NOT_LIVE")
    require(all(saved["identity"][k] == current[k] for k in ("boot_id", "start_ticks", "netns")), "ADOPTION_LIFETIME_REBOUND")
    require(argv_sha == saved["argv_sha256"], "ADOPTION_ARGV_REBOUND")
    mismatch = saved["identity"]["uid"] != current["uid"]
    require(
        not mismatch or name == "llama_server" and saved["identity"]["uid"] == 0 and current["uid"] == 1000,
        "ADOPTION_UNREVIEWED_IDENTITY_DISCREPANCY",
    )
    require(namespace["uid_map"] == [[0, uid, 1]], "ADOPTION_OWNER_UID_MAP_UNPROVEN")
    require(
        namespace["user_namespace"] == holder["user_namespace"]
        and namespace["network_namespace"] == holder["network_namespace"]
        and namespace["pid_namespace"] == holder["pid_namespace"],
        "ADOPTION_NAMESPACE_REBOUND",
    )
    return dict(
        name=name,
        pid=saved["pid"],
        identity={k: current[k] for k in ("boot_id", "start_ticks", "uid", "netns")},
        argv_sha256=argv_sha,
        namespace=namespace,
        original_saved_identity=saved["identity"],
        explicit_discrepancy="SAVED_UID0_CURRENT_OWNER_UID1000" if mismatch else None,
    )



def adopt_support_waiter(expected, current, namespace, holder, exe, argv, root, owner_uid):
    """This one source-created current lifetime only; no authority to signal it."""
    require(current is not None and current["state"] != "Z", "SUPPORT_WAITER_NOT_LIVE")
    require(current["pid"] == expected["pid"], "SUPPORT_WAITER_PID_REBOUND")
    require(all(current[k] == v for k, v in expected["identity"].items()), "SUPPORT_WAITER_LIFETIME_REBOUND")
    require(owner_uid == OWNER_UID and current["uid"] == owner_uid, "SUPPORT_WAITER_FOREIGN_UID")
    require(current["ppid"] == expected["ppid"], "SUPPORT_WAITER_PARENT_REBOUND")
    require(namespace == expected["namespace"] and namespace["uid_map"] == [[0, owner_uid, 1]],
            "SUPPORT_WAITER_NAMESPACE_REBOUND")
    require(exe == expected["exe"] == "/usr/bin/unshare", "SUPPORT_WAITER_EXE_REBOUND")
    require(str(root) == expected["root"], "SUPPORT_WAITER_ROOT_REBOUND")
    source_argv = ["unshare", "--user", "--map-root-user", "--net", "--fork", "bash", "-c",
                   f"ip link set lo up && echo $$ > {root}/run/holder.pid && exec sleep infinity"]
    require(argv == source_argv and digest(argv) == expected["argv_sha256"], "SUPPORT_WAITER_ARGV_REBOUND")
    require(holder is not None and holder["pid"] == expected["holder_pid"]
            and holder["ppid"] == current["pid"] and holder["state"] != "Z",
            "SUPPORT_WAITER_HOLDER_CHAIN_REBOUND")
    require(expected["direct_signal_authorized"] is False, "SUPPORT_WAITER_SIGNAL_SCOPE_INVALID")
    return dict(pid=current["pid"], identity=dict(expected["identity"]), name="support_waiter",
                argv_sha256=expected["argv_sha256"], direct_signal_authorized=False)

def verify_occupants(occupants, allowed):
    require(all(x["pid"] in allowed for x in occupants), "UNKNOWN_NAMESPACE_OCCUPANT_OR_DESCENDANT")


def retire_sequence(runtime, binding):
    """Each signal is pidfd-owned; every prior process must be kernel quiet first."""
    retired = []
    for name in ORDER:
        runtime.guard(name, retired)
        runtime.audit("SIGNAL_REQUEST", name)
        runtime.signal(binding[name])
        runtime.wait_quiet(binding[name])
        retired.append(name)
        runtime.audit("KERNEL_QUIET", name)
    runtime.guard("cleanup", retired)
    runtime.cleanup()
    runtime.final_check()
    return retired


HASH_CHUNK_BYTES = 65536
TEXT_CHUNK_CHARS = HASH_CHUNK_BYTES // 4


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _field(value):
    """Typed length + repeatable <=64KiB chunks; no JSON/BLOB type collision."""
    if value is None:
        return b"N", 0, lambda: iter(())
    if type(value) is int:
        raw = str(value).encode("ascii")
        return b"I", len(raw), lambda: iter((raw,))
    if type(value) is float:
        # SQLite numeric equality/order treats signed zero identically.
        raw = struct.pack(">d", 0.0 if value == 0 else value)
        return b"R", len(raw), lambda: iter((raw,))
    if isinstance(value, str):

        def chunks():
            for i in range(0, len(value), TEXT_CHUNK_CHARS):
                yield value[i : i + TEXT_CHUNK_CHARS].encode("utf-8", errors="strict")

        return b"T", sum(len(part) for part in chunks()), chunks
    if isinstance(value, bytes):

        def chunks():
            view = memoryview(value)
            for i in range(0, len(value), HASH_CHUNK_BYTES):
                yield view[i : i + HASH_CHUNK_BYTES]

        return b"B", len(value), chunks
    raise RuntimeError("SQLITE_STORAGE_TYPE_UNSUPPORTED")


def _hash_row(hasher, row):
    fields = [_field(value) for value in row]
    size = 4 + sum(9 + length for _, length, _ in fields)
    hasher.update(size.to_bytes(8, "big"))
    hasher.update(len(fields).to_bytes(4, "big"))
    for tag, length, chunks in fields:
        hasher.update(tag)
        hasher.update(length.to_bytes(8, "big"))
        for part in chunks():
            require(len(part) <= HASH_CHUNK_BYTES, "HASH_CHUNK_BOUND")
            hasher.update(part)
    return size + 8


def pinned_inactive_history(orders, attempts, commands, expected, current_order_ids):
    """Exact inactive legacy rows only; no queue state or retry semantics are changed."""
    actual_orders = {row["order_id"]: row for row in orders}
    require(set(actual_orders) == set(expected["orders"]), "HISTORICAL_ORDER_SET_CHANGED")
    for oid, pin in expected["orders"].items():
        row = actual_orders[oid]
        require(
            digest(row) == pin["row_sha256"]
            and row["state"] == pin["state"]
            and row["version"] == pin["version"]
            and row["request_id"] == pin["request_id"]
            and row["request_id"] not in current_order_ids,
            "HISTORICAL_ORDER_CHANGED_OR_IN_SCOPE",
        )
    actual_attempts = {row["attempt_id"]: row for row in attempts}
    require(set(actual_attempts) == set(expected["attempts"]), "HISTORICAL_ATTEMPT_SET_CHANGED")
    for aid, pin in expected["attempts"].items():
        row = actual_attempts[aid]
        rec = json.loads(row["record"])
        require(
            digest(row) == pin["row_sha256"]
            and row["order_id"] == pin["order_id"]
            and row["state"] == "FAILED"
            and row["finished_utc"] is not None
            and rec.get("state") == "FAILED"
            and rec.get("exit_status") == "SMOKE_FAIL"
            and rec.get("fabro_run_id") is None
            and rec.get("fabro_server") is None
            and not rec.get("evidence_refs"),
            "HISTORICAL_ATTEMPT_NOT_EXACT_QUIET_FAILURE",
        )
    actual_commands = {row["command_id"]: row for row in commands}
    require(set(actual_commands) == set(expected["failed_commands"]), "HISTORICAL_FAILED_COMMAND_SET_CHANGED")
    for cid, pin in expected["failed_commands"].items():
        row = actual_commands[cid]
        payload = json.loads(row["payload"])
        require(
            digest(row) == pin["row_sha256"]
            and row["state"] == "FAILED"
            and row["kind"] == "FABRO_LAUNCH"
            and row["order_id"] == pin["order_id"]
            and row["attempt_id"] == pin["attempt_id"]
            and row["attempts"] == 1
            and row["retry_not_before_epoch"] is None
            and row["ack_ref"] is None
            and payload == {"attempt_id": pin["attempt_id"]}
            and digest(payload) == pin["payload_sha256"],
            "HISTORICAL_COMMAND_CHANGED_OR_REPLAYABLE",
        )


def table_hashes(path, names=None):
    """Complete snapshot, typed framed rows, schema/count, no total-row cutoff.

    Python's SQLite cursor retains one row (not the DB) at a time; UTF8/hash
    scratch is <=64KiB. Non-null unique primary keys use their index order.
    NULL/no-PK tables use all-column typeof/BINARY total logical-value order.
    """
    require(path.is_file() and not path.is_symlink(), "HISTORY_DB_MISSING_OR_REBOUND")
    identity = (path.stat().st_dev, path.stat().st_ino)
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3) as c:
        c.execute("PRAGMA query_only=ON")
        c.execute("BEGIN")
        schema = hashlib.sha256(b"forge-c/sqlite-schema-stream/1\0")
        encoding = c.execute("PRAGMA encoding").fetchone()[0]
        _hash_row(schema, (encoding,))
        for row in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type COLLATE BINARY,name COLLATE BINARY"):
            _hash_row(schema, row)
        schema_sha = schema.hexdigest()
        if names is None:
            names = [
                row[0]
                for row in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name COLLATE BINARY"
                )
            ]
        out = {}
        for name in names:
            info = list(c.execute("PRAGMA table_info(" + _quote(name) + ")"))
            require(bool(info), "HISTORY_TABLE_SCHEMA_MISSING")
            columns = [row[1] for row in info]
            primary = [row[1] for row in sorted(info, key=lambda row: row[5]) if row[5]]
            no_null_keys = (
                primary
                and c.execute(
                    "SELECT 1 FROM "
                    + _quote(name)
                    + " WHERE "
                    + " OR ".join(_quote(col) + " IS NULL" for col in primary)
                    + " LIMIT 1"
                ).fetchone()
                is None
            )
            if no_null_keys:
                # A non-null PRIMARY KEY is unique; BINARY overrides declared
                # case-folding collations without adding payload sorting.
                ordering = ",".join(_quote(col) + " COLLATE BINARY" for col in primary)
                order_kind = "NONNULL_PRIMARY_KEY_BINARY"
            else:
                ordering = ",".join(
                    "typeof(" + _quote(col) + ") COLLATE BINARY," + _quote(col) + " COLLATE BINARY" for col in columns
                )
                order_kind = "TYPE_AWARE_ALL_COLUMNS_BINARY"
            counted = c.execute("SELECT COUNT(*) FROM " + _quote(name)).fetchone()[0]
            hasher = hashlib.sha256(b"forge-c/sqlite-logical-stream/1\0" + bytes.fromhex(schema_sha))
            seen = 0
            encoded_bytes = 0
            max_row_bytes = 0
            cursor = c.execute("SELECT * FROM " + _quote(name) + " ORDER BY " + ordering)
            for row in cursor:
                size = _hash_row(hasher, row)
                seen += 1
                encoded_bytes += size
                max_row_bytes = max(max_row_bytes, size)
            require(seen == counted, "HISTORY_STREAM_COUNT_MISMATCH")
            hasher.update(b"END" + seen.to_bytes(8, "big"))
            out[name] = dict(
                algorithm="forge-c/sqlite-logical-stream/1",
                schema_sha256=schema_sha,
                rows=seen,
                sha256=hasher.hexdigest(),
                ordering=order_kind,
                encoded_bytes=encoded_bytes,
                max_row_bytes=max_row_bytes,
                hash_chunk_bytes=HASH_CHUNK_BYTES,
            )
    require(identity == (path.stat().st_dev, path.stat().st_ino), "HISTORY_DB_IDENTITY_REBOUND")
    return out



def proc_entry_identity(fd):
    """Actual native procfs regular entry, never namespace-directory/content identity."""
    buf = ctypes.create_string_buffer(256)
    libc = ctypes.CDLL(None, use_errno=True)
    require(libc.fstatfs(ctypes.c_int(fd), ctypes.byref(buf)) == 0, "PROC_ENTRY_FS_UNKNOWN")
    require(ctypes.c_long.from_buffer(buf).value == 0x9FA0, "PROC_ENTRY_NOT_NATIVE_PROCFS")
    st = os.fstat(fd)
    require(stat.S_ISREG(st.st_mode), "PROC_ENTRY_NOT_REGULAR")
    return (st.st_dev, st.st_ino)


def open_proc_net_entry(pid):
    """Hold the per-net registered dev entry; no symlinks or file contents used."""
    dirs = []
    fd = None
    try:
        dirs.append(os.open("/proc", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW))
        dirs.append(os.open(str(pid), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=dirs[-1]))
        dirs.append(os.open("net", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=dirs[-1]))
        fd = os.open("dev", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=dirs[-1])
        identity = proc_entry_identity(fd)
        require(identity[0] == os.fstat(dirs[0]).st_dev, "PROC_ENTRY_MOUNT_REBOUND")
        return fd
    except BaseException:
        if fd is not None:
            os.close(fd)
        raise
    finally:
        for item in reversed(dirs):
            os.close(item)


def proc_lifetime(pid):
    raw = (Path("/proc") / str(pid) / "stat").read_text()
    fields = raw[raw.rfind(")") + 2 :].split()
    return (int(fields[1]), fields[19])

class Runtime:
    def __init__(self, args):
        require(__debug__, "OPTIMIZED_PYTHON_REFUSED")
        require(os.getuid() == OWNER_UID, "OS_OWNER_REQUIRED")
        require(
            not any(os.environ.get(k) for k in ("FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING")),
            "EXTERNAL_OPERATOR_REQUIRED",
        )
        require(sha(args.expected) == EXPECTED_SHA and sha(args.namespace) == NAMESPACE_SHA, "EXACT_EXPECTATIONS_REQUIRED")
        self.expected = json.loads(args.expected.read_text())
        self.nsproof = json.loads(args.namespace.read_text())
        require(self.expected["services_sha256"] == self.nsproof["services_sha256"] == SERVICES_SHA, "EXPECTATION_REBOUND")
        require(
            subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip() == SOURCE_REVISION,
            "SOURCE_REBOUND",
        )
        require(not subprocess.check_output(["git", "-C", str(SOURCE), "status", "--porcelain"]), "SOURCE_DIRTY")
        os.environ["FORGE_REPO_ROOT"] = str(SOURCE)
        sys.path.insert(0, str(SOURCE / "factory/python"))
        from forge_factory.afo import owner_supervised_development as D, operations, policy
        from forge_factory.afo import line_launcher as LL
        from forge_factory.lrtx import stack, pidfd

        self.D, self.operations, self.policy, self.LL, self.stack, self.pidfd = D, operations, policy, LL, stack, pidfd
        from forge_factory.lrtx.provider_process import owner_view

        require(owner_view(os.getpid())["uid_map"] == [[0, 0, 4294967295]], "INITIAL_OWNER_USERNS_REQUIRED")
        self.record = D.current()
        self.record_sha = digest(self.record)
        self.intent = operations.Intent(self.record["intent_path"])
        self.intent_record = self.intent.read()
        require(self.intent_record["mode"] == "RUNNING", "INTENT_NOT_RUNNING")
        require(self.record["store_path"] == str(ROOT / "state/supervisor/line-queue.sqlite3"), "CANONICAL_STORE_REBOUND")
        require(self.record["profile"] == D.PROFILE and self.record["profile_sha256"] == D.PROFILE_SHA, "AUTHORITY_SCOPE_REBOUND")
        require(args.order in D.ORDERS, "ORIGINAL_BCD_SCOPE_REQUIRED")
        self.request = dict(order_id=args.order, driver_class=D.DRIVER, model=D.PROFILE, service_action="line_stack_restart")
        require(D.permit(policy.load(), "launch_workorder", self.request), "LIVE_SERVICE_ACTION_AUTHORITY_REQUIRED")
        self.cfg = LL.LineConfig.from_env()
        require(self.cfg.stack_root.resolve() == ROOT, "STACK_ROOT_REBOUND")
        self.services = json.loads((ROOT / "run/services.json").read_text())
        require(sha(ROOT / "run/services.json") == SERVICES_SHA and "serving_instance" not in self.services, "SERVICES_REBOUND")
        require(list(self.services["processes"]) == list(ORDER), "SEND_FENCE_ORDER_REBOUND")
        self.settings = dict(root=ROOT, profile=stack.lp.load(self.services["profile"]), ports=self.services["ports"])
        self.binding = {}
        self.audit_dir = args.audit_dir
        self.steps = []
        self.retired = set()
        for name in ORDER:
            row = self.expected["processes"][name]
            current = self.kernel(row["pid"])
            namespace = self.namespace(row["pid"])
            holder = self.nsproof["processes"]["holder"]
            require(
                namespace == {k: v for k, v in self.nsproof["processes"][name].items() if k not in ("pid", "uid")},
                "CAPTURED_NAMESPACE_CHANGED",
            )
            self.binding[name] = adopt(name, row, current, namespace, holder, os.getuid(), self.argv_sha(row["pid"]))
        support = Path(__file__).parent / "support-waiter-current-adoption.json"
        require(not support.is_symlink() and sha(support) == "8998ac002faa15b04622c77339c6b5df13c6d6434555c2532fed6531f2ebd709",
                "EXACT_SUPPORT_WAITER_ADOPTION_REQUIRED")
        self.support_waiter_spec = json.loads(support.read_text())
        require(self.support_waiter_spec["services_sha256"] == SERVICES_SHA, "SUPPORT_WAITER_SERVICES_REBOUND")
        self.support_waiter_binding = self.validate_support_waiter()
        self.support_validate()
        expected_history = Path(__file__).parent / "inactive-history-expectation.json"
        require(
            not expected_history.is_symlink()
            and sha(expected_history) == "cced4280b02cb2cf739b8ac0a6366fb0ae9e5c3c6009f9f82318fc235c1921a3",
            "EXACT_INACTIVE_HISTORY_EXPECTATION_REQUIRED",
        )
        self.inactive_history = json.loads(expected_history.read_text())
        self.act_fd = None
        self.before_history = self.history()
        self.initial_census = None
        self.deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 90

    def validate_support_waiter(self):
        spec = self.support_waiter_spec
        current = self.kernel(spec["pid"])
        holder = self.kernel(spec["holder_pid"])
        if holder is None or holder["state"] == "Z":
            # Strict child cleanup may already have ended this original waiter.
            if current is None or current["state"] == "Z":
                return None
        value = adopt_support_waiter(spec, current, self.namespace(spec["pid"]), holder,
                                     os.readlink(Path("/proc") / str(spec["pid"]) / "exe"),
                                     kernel_argv_vector((Path("/proc") / str(spec["pid"]) / "cmdline").read_bytes()),
                                     ROOT, os.getuid())
        self.root_owned(spec["pid"])
        return value

    def wait_support_waiter_quiet(self):
        """Never signal the waiter. Original child termination must retire it."""
        if not hasattr(self, "support_waiter_binding"):
            return  # Existing isolated method CONTROL fixtures bypass __init__.
        item = self.support_waiter_binding
        require(item is not None, "SUPPORT_WAITER_BINDING_UNKNOWN")
        until = min(time.clock_gettime(time.CLOCK_BOOTTIME) + 3, self.deadline)
        while not self.quiet(item):
            require(time.clock_gettime(time.CLOCK_BOOTTIME) < until,
                    "SUPPORT_WAITER_QUIESCENCE_UNKNOWN_NO_RETRY")
            time.sleep(0.05)

    def root_owned(self, pid):
        base = Path("/proc") / str(pid)
        argv = (base / "cmdline").read_bytes().split(b"\0")
        cwd = os.readlink(base / "cwd")
        if cwd == str(ROOT) or cwd.startswith(str(ROOT) + "/") or any(str(ROOT).encode() in a for a in argv):
            return
        root_value = next(
            (x.split(b"=", 1)[1] for x in (base / "environ").read_bytes().split(b"\0") if x.startswith(b"FORGE_LRTX_ROOT=")), None
        )
        require(root_value == str(ROOT).encode(), "ACTUAL_ROOT_OWNERSHIP_UNPROVEN")

    def support_validate(self, allow_ended=False):
        holder = self.expected["holder"]
        current = self.stack.process_identity(holder["pid"])
        require(current == holder["identity"], "HOLDER_IDENTITY_CHANGED")
        require(self.stack._holder(self.settings) == holder["pid"], "HOLDER_COMMAND_CHANGED")
        require(
            self.namespace(holder["pid"])
            == {k: v for k, v in self.nsproof["processes"]["holder"].items() if k not in ("pid", "uid")},
            "HOLDER_NAMESPACE_CHANGED",
        )
        for row in self.expected["api_bridge"].values():
            actual = self.stack.process_identity(row["pid"])
            if actual is None and allow_ended:
                continue
            require(actual == row["identity"] and self.argv_sha(row["pid"]) == row["argv_sha256"], "BRIDGE_IDENTITY_CHANGED")
        for item in self.binding.values():
            self.root_owned(item["pid"])

    def kernel(self, pid):
        p = Path("/proc") / str(pid)
        try:
            raw = (p / "stat").read_text()
            f = raw[raw.rfind(")") + 2 :].split()
            return dict(
                pid=pid,
                boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                start_ticks=f[19],
                state=f[0],
                uid=p.stat().st_uid,
                netns=os.readlink(p / "ns/net") if f[0] != "Z" else None,
                ppid=int(f[1]),
            )
        except FileNotFoundError:
            return None

    def namespace(self, pid):
        p = Path("/proc") / str(pid)
        return dict(
            uid_map=[list(map(int, x.split())) for x in (p / "uid_map").read_text().splitlines()],
            user_namespace=os.readlink(p / "ns/user"),
            network_namespace=os.readlink(p / "ns/net"),
            pid_namespace=os.readlink(p / "ns/pid"),
        )

    def argv_sha(self, pid):
        vector = kernel_argv_vector((Path("/proc") / str(pid) / "cmdline").read_bytes())
        # Exact root snapshot recipe: default ensure_ascii=True, no spaces/newline.
        return digest(vector)

    def quiet(self, item):
        current = self.kernel(item["pid"])
        if current is None:
            return True
        # A replaced PID proves the original ended; never signal the replacement.
        if current["boot_id"] != item["identity"]["boot_id"] or current["start_ticks"] != item["identity"]["start_ticks"]:
            return True
        return current["state"] == "Z"

    def history(self):
        return dict(
            queue=table_hashes(ROOT / "state/supervisor/line-queue.sqlite3"),
            native=table_hashes(
                ROOT / "fabro/storage/db/fabro.sqlite3",
                ("runs", "run_events", "run_session_records", "legacy_run_history_activation", "legacy_run_history_deletions"),
            ),
        )

    @contextlib.contextmanager
    def act_lock(self):
        path = ROOT / "state/supervisor/act.lock"
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            require(os.fstat(descriptor).st_uid == os.getuid(), "ACT_LOCK_OWNER_UNKNOWN")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.act_fd = descriptor
            self.owned_act()
            yield
        finally:
            self.act_fd = None
            os.close(descriptor)

    def owned_act(self):
        require(self.act_fd is not None, "OWNED_ACT_LOCK_REQUIRED")
        path = ROOT / "state/supervisor/act.lock"
        have, want = os.fstat(self.act_fd), path.stat()
        require(
            (have.st_dev, have.st_ino) == (want.st_dev, want.st_ino) and self.LL.flock_holders(path) == {os.getpid()},
            "ACT_LOCK_REBOUND_OR_FOREIGN_HOLDER",
        )

    def producer_fence(self):
        self.owned_act()
        require(os.environ.get(self.D.SHA) == self.inactive_history["guardian_record_sha256"], "NONPLACING_GUARDIAN_REBOUND")
        for expected in self.inactive_history["producers"]:
            response = subprocess.check_output(
                ["systemctl", "--user", "show", expected["unit"], "--property=MainPID,InvocationID,ActiveState,SubState"],
                text=True,
                timeout=3,
            )
            unit = dict(line.split("=", 1) for line in response.splitlines())
            require(
                all(unit.get(k) == expected[k] for k in ("MainPID", "InvocationID", "ActiveState", "SubState")),
                "HISTORICAL_REPLAY_PRODUCER_CHANGED",
            )
            pid = int(unit["MainPID"])
            current = self.kernel(pid)
            require(
                current is not None
                and current["uid"] == OWNER_UID
                and current["state"] != "Z"
                and current["start_ticks"] == expected["start_ticks"],
                "PRODUCER_KERNEL_IDENTITY_CHANGED",
            )
            raw = (Path("/proc") / str(pid) / "cmdline").read_bytes()
            require(hashlib.sha256(raw).hexdigest() == expected["argv_sha256"], "PRODUCER_ARGV_CHANGED")
            argv = kernel_argv_vector(raw)
            if expected["mode"] == "OBSERVE":
                require(
                    [argv[i + 1] for i, value in enumerate(argv[:-1]) if value == "--mode"] == ["OBSERVE"],
                    "PRODUCTION_OBSERVER_IS_NOT_OBSERVE",
                )
            else:
                require(pid == self.record["guardian_pid"], "GUARDIAN_PRODUCER_PID_REBOUND")
                files = [Path(arg) for arg in argv if arg.endswith("guardian-only-bootstrap-DRAFT.py")]
                require(
                    len(files) == 1 and sha(files[0]) == expected["guardian_only_bootstrap_sha256"],
                    "GUARDIAN_ONLY_PRODUCER_CHANGED",
                )
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid != OWNER_UID:
                    continue
                argv = (entry / "cmdline").read_bytes().split(b"\0")
                require(
                    not any(
                        name in argv for name in (b"forge_factory.afo.line_recovery_worker", b"forge_factory.afo.line_launcher")
                    ),
                    "LEGACY_WORKER_OR_LAUNCHER_ACTIVE",
                )
            except FileNotFoundError:
                continue

    def resources(self):
        self.producer_fence()
        path = ROOT / "state/supervisor/line-queue.sqlite3"
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3) as c:
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA query_only=ON")
            c.execute("BEGIN")
            require(
                c.execute(
                    "SELECT 1 FROM afo_execution_liveness WHERE json_extract(record,'$.resource_lease')='HELD' LIMIT 1"
                ).fetchone()
                is None,
                "HELD_INFERENCE_EXECUTION",
            )
            require(
                c.execute(
                    "SELECT 1 FROM afo_resource_ownership WHERE resource='inference' AND holder IS NOT NULL AND holder!='' LIMIT 1"
                ).fetchone()
                is None,
                "INFERENCE_OWNER_BUSY",
            )
            require(
                c.execute("SELECT 1 FROM afo_request_ledger WHERE state!='QUIESCENT' LIMIT 1").fetchone() is None,
                "REQUEST_NOT_QUIESCENT",
            )
            require(
                c.execute(
                    "SELECT 1 FROM afo_work_orders WHERE state IN ('QUEUED','ADMITTED','RUNNING','WAITING_RECOVERY','VALIDATING') LIMIT 1"
                ).fetchone()
                is None,
                "PENDING_OR_ACTIVE_ORDER",
            )
            require(
                c.execute(
                    "SELECT 1 FROM afo_commands_outbox WHERE state NOT IN ('ACKED','QUARANTINED','FAILED') LIMIT 1"
                ).fetchone()
                is None,
                "PENDING_OR_UNKNOWN_COMMAND",
            )
            paused = [dict(row) for row in c.execute("SELECT * FROM afo_work_orders WHERE state='PAUSED'")]
            require(
                {row["order_id"] for row in paused}
                == {oid for oid, pin in self.inactive_history["orders"].items() if pin["state"] == "PAUSED"},
                "UNKNOWN_PAUSED_ORDER",
            )
            orders = []
            for oid in self.inactive_history["orders"]:
                row = c.execute("SELECT * FROM afo_work_orders WHERE order_id=?", (oid,)).fetchone()
                require(row is not None, "HISTORICAL_ORDER_MISSING")
                orders.append(dict(row))
            attempts = []
            for aid in self.inactive_history["attempts"]:
                row = c.execute("SELECT * FROM afo_attempts WHERE attempt_id=?", (aid,)).fetchone()
                require(row is not None, "HISTORICAL_ATTEMPT_MISSING")
                attempts.append(dict(row))
            commands = [dict(row) for row in c.execute("SELECT * FROM afo_commands_outbox WHERE state='FAILED'")]
            pinned_inactive_history(orders, attempts, commands, self.inactive_history, self.record["order_ids"])

    def occupants(self):
        known = (
            {r["pid"] for r in self.expected["processes"].values()}
            | {r["pid"] for r in self.expected["api_bridge"].values()}
            | {self.expected["holder"]["pid"]}
        )
        if hasattr(self, "support_waiter_spec"):
            support = self.validate_support_waiter()
            if support is not None:
                known.add(support["pid"])
        # Opening dev holds the original network namespace via seq_open_net.
        # Retain this one FD until this one-shot OPS process exits, including
        # final census after original holder retirement. No cached process facts.
        if not hasattr(self, "_held_net_entry_fd"):
            holder = self.expected["holder"]
            actual = self.kernel(holder["pid"])
            require(actual is not None and {k: actual[k] for k in holder["identity"]} == holder["identity"],
                    "NET_ENTRY_HOLDER_REBOUND")
            anchor = open_proc_net_entry(holder["pid"])
            try:
                require(self.kernel(holder["pid"]) == actual, "NET_ENTRY_HOLDER_REBOUND")
                self._held_net_entry_identity = proc_entry_identity(anchor)
                self._held_net_entry_fd = anchor
            except BaseException:
                os.close(anchor)
                raise
        holder_now = self.kernel(self.expected["holder"]["pid"])
        if holder_now is not None:
            identity = self.expected["holder"]["identity"]
            require(all(holder_now[k] == v for k, v in identity.items() if k != "netns")
                    and (holder_now["state"] == "Z" or holder_now["netns"] == identity["netns"]),
                    "NET_ENTRY_HOLDER_REBOUND")
        require(proc_entry_identity(self._held_net_entry_fd) == self._held_net_entry_identity,
                "NET_ENTRY_ANCHOR_REBOUND")
        facts = {}
        parents = {}
        observed = {}
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        captured = getattr(self, "_captured_unknown_lifetimes", {})
        self._captured_unknown_lifetimes = captured
        for p in Path("/proc").iterdir():
            if not p.name.isdigit():
                continue
            try:
                raw = (p / "stat").read_text()
                fields = raw[raw.rfind(")") + 2 :].split()
                parents[int(p.name)] = int(fields[1])
                observed[int(p.name)] = dict(pid=int(p.name), start_ticks=fields[19], state=fields[0])
                if p.stat().st_uid != OWNER_UID:
                    continue
                try:
                    same_net = os.readlink(p / "ns/net") == self.expected["holder"]["identity"]["netns"]
                except PermissionError as exc:
                    if exc.errno != errno.EACCES:
                        raise
                    # Linux per-net dev PDE inode identity supplies an independent
                    # native kernel proof when ptrace-gated namespace links deny.
                    # Missing/unreadable/procfs/mount/lifetime changes still refuse.
                    fd = open_proc_net_entry(int(p.name))
                    try:
                        identity = proc_entry_identity(fd)
                        require(identity[0] == self._held_net_entry_identity[0], "PROC_ENTRY_MOUNT_REBOUND")
                        require(proc_lifetime(int(p.name)) == (int(fields[1]), fields[19]), "PROC_ENTRY_PID_REBOUND")
                        second = open_proc_net_entry(int(p.name))
                        try:
                            require(proc_entry_identity(second) == identity, "PROC_ENTRY_TARGET_REBOUND")
                        finally:
                            os.close(second)
                        require(proc_lifetime(int(p.name)) == (int(fields[1]), fields[19]), "PROC_ENTRY_PID_REBOUND")
                        require(proc_entry_identity(self._held_net_entry_fd) == self._held_net_entry_identity,
                                "NET_ENTRY_ANCHOR_REBOUND")
                        same_net = identity == self._held_net_entry_identity
                    finally:
                        os.close(fd)
                if same_net:
                    facts[int(p.name)] = dict(pid=int(p.name), start_ticks=fields[19])
            except FileNotFoundError:
                continue
        # Captured unknowns/descendants remain roots across retries, including
        # reparenting or moves to another NET namespace. Only actual quiet or
        # the end of that original PID/start/boot lifetime removes the root.
        retained = set()
        for pid, original in list(captured.items()):
            try:
                raw = (Path("/proc") / str(pid) / "stat").read_text()
            except FileNotFoundError:
                del captured[pid]
                continue
            values = raw[raw.rfind(")") + 2 :].split()
            if (boot != original["boot_id"] or values[19] != original["start_ticks"] or values[0] == "Z"):
                del captured[pid]
                continue
            parents[pid] = int(values[1])
            observed[pid] = dict(pid=pid, start_ticks=values[19], state=values[0])
            retained.add(pid)
            facts[pid] = dict(pid=pid, start_ticks=values[19], relation="CAPTURED_ORIGINAL_LIFETIME_STILL_LIVE")
        descendants = set(known) | retained
        for _ in range(len(parents) + 1):
            new = {pid for pid, parent in parents.items() if parent in descendants}
            if new <= descendants:
                break
            descendants |= new
        for pid in descendants - known:
            if pid in observed and observed[pid]["state"] != "Z":
                facts[pid] = dict(pid=pid, start_ticks=observed[pid]["start_ticks"], relation="DESCENDANT_OF_CAPTURED_LIFETIME")
        for pid in set(facts) - known:
            require(pid in observed, "CAPTURED_PROCESS_IDENTITY_UNKNOWN")
            if observed[pid]["state"] != "Z":
                captured[pid] = dict(boot_id=boot, start_ticks=observed[pid]["start_ticks"])
        verify_occupants(list(facts.values()), known)
        return sorted(facts.values(), key=lambda x: x["pid"])

    def native_census(self):
        from forge_factory.fabro.client import FabroClient, load_token

        fingerprints = []
        with FabroClient(base_url="http://127.0.0.1:32397", token=load_token(str(ROOT / "fabro/storage")), timeout=2) as client:
            for _ in range(2):
                rows = []
                total = None
                offset = 0
                for _ in range(10):
                    reply = client._get(
                        "/api/v1/runs",
                        **{
                            "page[limit]": 100,
                            "page[offset]": offset,
                            "sort": "created_at",
                            "direction": "asc",
                            "include_archived": "true",
                        },
                    )
                    batch, meta = reply["data"], reply["meta"]
                    require(
                        type(meta["total"]) is int and 0 <= meta["total"] <= 1000 and type(meta["has_more"]) is bool,
                        "NATIVE_PAGE_UNKNOWN",
                    )
                    require(total is None or total == meta["total"], "NATIVE_TOTAL_CHANGED")
                    total = meta["total"]
                    for row in batch:
                        require(isinstance(row.get("id"), str) and row["id"], "NATIVE_ID_UNKNOWN")
                        status = ((row.get("lifecycle") or {}).get("status") or {}).get("kind", "").lower()
                        require(status in ("succeeded", "failed", "cancelled", "canceled"), "LIVE_OR_UNKNOWN_NATIVE")
                    rows += batch
                    require(len({r["id"] for r in rows}) == len(rows), "NATIVE_DUPLICATE")
                    if not meta["has_more"]:
                        break
                    require(bool(batch), "EMPTY_NONTERMINAL_PAGE")
                    offset += len(batch)
                else:
                    require(False, "NATIVE_PAGE_BOUND")
                require(len(rows) == total, "NATIVE_CENSUS_INCOMPLETE")
                fingerprints.append(
                    digest(
                        sorted(
                            ({k: r.get(k) for k in ("id", "source_directory", "lifecycle")} for r in rows), key=lambda r: r["id"]
                        )
                    )
                )
            removing = client._get("/api/v1/runs", **{"page[limit]": 100, "status": "removing", "include_archived": "true"})
            require(
                removing["data"] == [] and removing["meta"]["total"] == 0 and removing["meta"]["has_more"] is False,
                "REMOVING_NATIVE_UNKNOWN",
            )
        require(fingerprints[0] == fingerprints[1], "NATIVE_CENSUS_DRIFT")
        return fingerprints[0]

    def gateway_quiet(self):
        holder = self.expected["holder"]["pid"]
        port = self.services["ports"]["gateway"]
        code = (
            "import json,urllib.request;print(json.dumps(json.load(urllib.request.urlopen("
            + repr("http://127.0.0.1:" + str(port) + "/health")
            + ",timeout=2))))"
        )
        out = subprocess.check_output(
            self.stack._nsenter(holder) + [str(self.cfg.python), "-c", code],
            env={"PATH": self.stack.SYSTEM_PATH},
            timeout=5,
            text=True,
        )
        value = json.loads(out)
        adm = value.get("admission") or {}
        require(
            value.get("status") == "ok"
            and type(adm.get("waiting")) is int
            and adm["waiting"] == 0
            and type(adm.get("inflight")) is int
            and adm["inflight"] == 0,
            "GATEWAY_NOT_PROVEN_QUIESCENT",
        )

    def authority(self):
        require(time.clock_gettime(time.CLOCK_BOOTTIME) < self.deadline, "RETIREMENT_BOUND_EXPIRED")
        require(digest(self.D.current()) == self.record_sha, "GUARDIAN_REBOUND_OR_LOST")
        require(self.intent.read() == self.intent_record, "INTENT_EPOCH_OR_CONTENT_CHANGED")
        require(self.D.permit(self.policy.load(), "launch_workorder", self.request), "SERVICE_ACTION_AUTHORITY_LOST")
        require(sha(ROOT / "run/services.json") == SERVICES_SHA, "ORIGINAL_SERVICES_REBOUND")
        self.resources()
        require(self.history() == self.before_history, "CANONICAL_HISTORY_CHANGED")

    def guard(self, name, retired):
        self.authority()
        # Bridges/holder remain the original strict cleanup subjects.
        holder = self.expected["holder"]
        require(self.stack.process_identity(holder["pid"]) == holder["identity"], "HOLDER_IDENTITY_CHANGED")
        for row in self.expected["api_bridge"].values():
            require(
                self.stack.process_identity(row["pid"]) == row["identity"] and self.argv_sha(row["pid"]) == row["argv_sha256"],
                "BRIDGE_IDENTITY_CHANGED",
            )
        for prior in retired:
            require(self.quiet(self.binding[prior]), "PRIOR_LIFETIME_NOT_QUIET")
        for target in ORDER:
            if target in retired:
                continue
            item = self.binding[target]
            actual = self.kernel(item["pid"])
            require(actual is not None and actual["state"] != "Z", "UNEXPECTED_LIFETIME_EXIT_REVIEW")
            require(
                {k: actual[k] for k in item["identity"]} == item["identity"]
                and self.argv_sha(item["pid"]) == item["argv_sha256"],
                "ADOPTED_LIFETIME_CHANGED",
            )
            require(self.namespace(item["pid"]) == item["namespace"], "ADOPTED_NAMESPACE_CHANGED")
            self.root_owned(item["pid"])
        if "fabro" not in retired:
            value = self.native_census()
            require(self.initial_census is None or value == self.initial_census, "NATIVE_HISTORY_CENSUS_REBOUND")
            self.initial_census = value
        if "gateway" not in retired:
            self.gateway_quiet()
        # Read-only API relays can briefly leave their own socat fork alive.
        # Never ignore it: wait boundedly for a complete quiet census AFTER all
        # reads have closed, or refuse before the next signal.
        self.wait_occupants()
        self.authority()
        if name in ("llama_server", "ollama", "cleanup"):
            require(all(self.quiet(self.binding[x]) for x in ("fabro", "gateway")), "SENDERS_MUST_END_BEFORE_MODEL")

    def wait_occupants(self):
        until = min(time.clock_gettime(time.CLOCK_BOOTTIME) + 3, self.deadline)
        while True:
            try:
                return self.occupants()
            except RuntimeError as exc:
                if str(exc) != "UNKNOWN_NAMESPACE_OCCUPANT_OR_DESCENDANT":
                    raise
                self.authority()
                require(time.clock_gettime(time.CLOCK_BOOTTIME) < until, "UNKNOWN_NAMESPACE_OCCUPANT_OR_DESCENDANT")
                time.sleep(0.05)

    def final_fence(self):
        """No DB/history/process census follows this small effect-tail fence.

        Full protected Store/source/policy/mission validation was performed by
        authority(). Rechallenge that exact original issuer, then check original
        Intent/scope/boot and BOTH fixed clocks after the blocking socket call.
        """
        record = self.record
        require(self.D.guardian_alive(record), "FINAL_GUARDIAN_NOT_LIVE")
        socket_path = Path(record["guardian_socket"])
        socket_stat = socket_path.stat()
        require(
            dict(device=socket_stat.st_dev, inode=socket_stat.st_ino) == record["guardian_socket_identity"],
            "FINAL_GUARDIAN_SOCKET_REBOUND",
        )
        self.D._attest(record, str(socket_path))
        require(self.D.guardian_alive(record), "FINAL_GUARDIAN_LOST_AFTER_CHALLENGE")
        require(
            self.intent.read() == self.intent_record
            and self.intent_record["mode"] == "RUNNING"
            and self.intent_record["epoch"] == record["intent_epoch"],
            "FINAL_INTENT_FENCED",
        )
        require(
            self.request
            == dict(
                order_id=self.request.get("order_id"),
                driver_class=self.D.DRIVER,
                model=self.D.PROFILE,
                service_action="line_stack_restart",
            )
            and self.request["order_id"] in record["order_ids"]
            and record["profile"] == self.D.PROFILE
            and record["profile_sha256"] == self.D.PROFILE_SHA,
            "FINAL_SERVICE_SCOPE_REBOUND",
        )
        require(
            Path("/proc/sys/kernel/random/boot_id").read_text().strip() == record["expiry_ticket"]["remote_boot_id"],
            "FINAL_BOOT_CHANGED",
        )
        # These are deliberately the final observations, after every potentially
        # blocking challenge/file read. No fresh 60-second issuance limit here.
        require(
            time.monotonic() < record["expiry_ticket"]["deadline_monotonic"]
            and time.clock_gettime(time.CLOCK_BOOTTIME) < min(self.deadline, record["expiry_boottime_deadline"]),
            "FINAL_EFFECT_WINDOW_EXPIRED",
        )

    def signal(self, item):
        require(item.get("direct_signal_authorized") is not False
                and (not hasattr(self, "support_waiter_spec") or item["pid"] != self.support_waiter_spec["pid"]),
                "SUPPORT_WAITER_MUST_NEVER_BE_SIGNALED")
        descriptor = self.pidfd.open_pid(item["pid"])
        try:
            actual = self.kernel(item["pid"])
            require(actual is not None, "SIGNAL_TARGET_UNKNOWN")
            require(
                {k: actual[k] for k in item["identity"]} == item["identity"]
                and self.argv_sha(item["pid"]) == item["argv_sha256"],
                "SIGNAL_TARGET_REBOUND",
            )
            self.guard(item["name"], list(self.retired))  # All fresh native/request/kernel authority at effect.
            self.final_fence()
            self.pidfd.send_signal(descriptor, signal.SIGTERM)
        finally:
            os.close(descriptor)

    def wait_quiet(self, item):
        until = min(time.clock_gettime(time.CLOCK_BOOTTIME) + 10, self.deadline)
        while not self.quiet(item):
            self.authority()
            require(time.clock_gettime(time.CLOCK_BOOTTIME) < until, "PROCESS_QUIESCENCE_UNKNOWN_NO_RETRY")
            time.sleep(0.05)

    def audit(self, state, name):
        if state == "KERNEL_QUIET":
            self.retired.add(name)
        self.steps.append(
            dict(step=len(self.steps), state=state, name=name, boot_monotonic=time.clock_gettime(time.CLOCK_BOOTTIME))
        )
        p = self.audit_dir / (str(len(self.steps)).zfill(3) + "-" + state + "-" + name + ".json")
        with p.open("x") as f:
            json.dump(self.steps[-1], f, indent=2)
            f.flush()
            os.fsync(f.fileno())

    def cleanup(self):
        require(all(self.quiet(x) for x in self.binding.values()), "SERVICES_NOT_QUIET_BEFORE_STRICT_CLEANUP")

        def guard():
            self.authority()
            require(all(self.quiet(x) for x in self.binding.values()), "SERVICES_NOT_QUIET_AT_CLEANUP_EFFECT")
            self.wait_occupants()
            for row in self.expected["api_bridge"].values():
                actual = self.stack.process_identity(row["pid"])
                if actual is not None:
                    require(
                        actual == row["identity"] and self.argv_sha(row["pid"]) == row["argv_sha256"],
                        "CLEANUP_BRIDGE_IDENTITY_CHANGED",
                    )
            holder = self.expected["holder"]
            require(self.stack.process_identity(holder["pid"]) == holder["identity"], "CLEANUP_HOLDER_CHANGED")
            self.final_fence()  # Last guard before original strict cleanup's pidfd effect.

        # Unmodified validator now skips ended service PIDs; only original strict
        # bridge/holder identities may receive cleanup signals.
        with self.stack.line_effect_guard(guard):
            self.stack._stop(self.settings, managed=True)

    def final_check(self):
        require(all(self.quiet(x) for x in self.binding.values()), "RETIRED_SERVICE_LIFETIME_NOT_QUIET")
        require(self.history() == self.before_history and self.intent.read() == self.intent_record, "HISTORY_OR_INTENT_CHANGED")
        for group in ("api_bridge",):
            for row in self.expected[group].values():
                require(self.quiet(dict(pid=row["pid"], identity=row["identity"])), "BRIDGE_CLEANUP_UNKNOWN")
        row = self.expected["holder"]
        require(self.quiet(dict(pid=row["pid"], identity=row["identity"])), "HOLDER_CLEANUP_UNKNOWN")
        self.wait_support_waiter_quiet()
        require(not self.occupants(), "NAMESPACE_OR_DESCENDANT_CLEANUP_UNKNOWN")
        after = json.loads((ROOT / "run/services.json").read_text())
        before = dict(self.services)
        require(
            after.get("processes") == {} and "api_bridge" not in after and not (ROOT / "run/holder.pid").exists(),
            "NORMAL_STOP_PROJECTION_UNKNOWN",
        )
        for k in set(before) | set(after):
            if k not in ("processes", "api_bridge", "stopped_at"):
                require(before.get(k) == after.get(k), "UNEXPECTED_SERVICES_REWRITE")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected", type=Path, required=True)
    p.add_argument("--namespace", type=Path, required=True)
    p.add_argument("--order", required=True)
    p.add_argument("--audit-dir", type=Path, required=True)
    p.add_argument("--apply-reviewed", action="store_true")
    a = p.parse_args()
    runtime = Runtime(a)
    if not a.apply_reviewed:
        with runtime.act_lock():
            runtime.guard("readonly", [])
            print(
                json.dumps(
                    dict(
                        status="READONLY_READY_NOT_EXECUTED",
                        effects=False,
                        adoption=runtime.binding,
                        advisory_act_lock_held_during_read=True,
                    ),
                    indent=2,
                )
            )
        return
    require(not a.audit_dir.exists() and not a.audit_dir.is_symlink(), "IMMUTABLE_FRESH_AUDIT_REQUIRED")
    with runtime.intent.lock(), runtime.LL.gpu_lock(runtime.cfg.gpu_lock), runtime.LL.held_stack_lock(ROOT):
        with runtime.act_lock():
            runtime.guard("preeffect", [])
            # One owner-side marker for this actual stack lifetime; no replay.
            marker = runtime.intent.path.parent / "owner-development-retirement-dc27-attempt.json"
            a.audit_dir.mkdir(mode=0o700, parents=True)
            binding = dict(
                schema="forge-c/os-owner-legacy-adoption/1",
                source=SOURCE_REVISION,
                guardian_sha256=runtime.record_sha,
                original_services_sha256=SERVICES_SHA,
                adopted_current_lifetimes=runtime.binding,
                history=runtime.before_history,
                notice="Current owner adoption only; original UID0 historical correctness is not asserted",
            )
            with marker.open("x") as m:
                json.dump(binding, m, indent=2)
                m.flush()
                os.fsync(m.fileno())
            with (a.audit_dir / "owner-adoption-binding.json").open("x") as b:
                json.dump(binding, b, indent=2)
            raw = (ROOT / "run/services.json").read_bytes()
            require(hashlib.sha256(raw).hexdigest() == SERVICES_SHA, "PREEFFECT_SERVICES_BACKUP_REBOUND")
            with (a.audit_dir / "services.before.PRIVATE.json").open("xb") as backup:
                os.fchmod(backup.fileno(), 0o600)
                backup.write(raw)
                backup.flush()
                os.fsync(backup.fileno())
            try:
                retired = retire_sequence(runtime, runtime.binding)
                result = dict(
                    status="EXACT_LEGACY_LIFETIMES_RETIRED_NOT_RESTARTED",
                    retired=retired,
                    actual_model_calls=0,
                    mission_or_queue_or_native_history_changed=False,
                    original_services_sha256=SERVICES_SHA,
                    guardian_left_live=True,
                    no_model_start_or_dispatch=True,
                )
            except BaseException as exc:
                result = dict(
                    status="PARTIAL_OR_UNKNOWN_NO_AUTOMATIC_RETRY",
                    error_type=type(exc).__name__,
                    steps=runtime.steps,
                    no_lease_release_or_rollback=True,
                )
                raise
            finally:
                with (a.audit_dir / "outcome.json").open("x") as o:
                    json.dump(result, o, indent=2)
                print(json.dumps(result))


if __name__ == "__main__":
    main()
