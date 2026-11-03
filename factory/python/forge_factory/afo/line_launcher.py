"""Autonomous line M2 (owner 2026-11-03) - the line launcher: one safe launch of one phase order on one host.

It replaces the Omniverse2 bash launcher (swe1-fabro-20261031/launch-generic-model.sh, with its M0 lock and RUN_LIVE
check) and the loop10 waiter (run_one_model.sh) with the same behaviour, made safe:

  1 host launch lock     flock -n on the M0 file (/mnt/data/forge-c/line/gpu.lock): the bash launcher and this one
                         exclude each other; a second launch is refused GPU_LOCK_HELD (exit 75, as `flock -E 75`).
  2 RUN_LIVE             no live Forge-C run on this stack root (local Fabro API; a Fabro of this root that is alive
                         but does not answer is FABRO_API_UNREACHABLE), checked before any worktree or stack action.
  3 one worktree per run `git worktree add --detach <runs>/<WO> <rev>` from the line repo; the shared checkout is
                         never checked out. A worktree is reused only by a re-attempt of the same order at the same
                         revision that never launched; it must be clean. The git-ignored example inputs the order
                         names are copied in, each verified against the sha256 the revision's tracked manifests
                         record, from a content-addressed inputs cache or a reference checkout (read only).
  4 stack lifecycle      the stack lock (lrtx.stack.stack_lock, <root>/run/stack.lock) is held from stop to launch and
                         handed to the stack's own start/stop, so a raced start is refused; stop, then the orphan
                         sweep (only processes of our UID, of a stack-daemon kind, with evidence of THIS root, outside
                         the live stack's network namespace), then start, healthy wait, expose-api.
  5 model swap smoke     serve each profile model in turn (alternates first, ending on the stack's primary) and
                         require /v1/models to list exactly that model: SMOKE_FAIL, no launch.
  6 launch               the work-order CLI inside the stack namespace (`stack exec`), as the bash launcher calls it;
                         returns the Fabro run id. Every attempt writes a transcript of every step and its typed
                         outcome: <worktree>/.forge-run/launch/attempt-N.json (before the worktree exists:
                         <runs>/.launch/<WO>/attempt-N.json).
  7 wait and verdict     poll the local Fabro API for the run's end; read the phase verdict from the gate log
                         (PASS / NO / INFRA_UNAVAILABLE - CAPA-122's outcome).

The library places no orders by itself; the M3 supervisor calls `launch`, `wait_for_end` and `order_verdict`. The CLI
prints the bash launcher's marker lines, so the loop10 waiter and the M1 Line Conductor read its record unchanged:

    python -m forge_factory.afo.line_launcher launch REV WO EXAMPLE PROFILE ["EXTRA"] [MODEL] [--dry-run]
    python -m forge_factory.afo.line_launcher status [--wo WO --phase SWE.n] [--run-id ID]
    python -m forge_factory.afo.line_launcher sweep [--kill]
    python -m forge_factory.afo.line_launcher wait --run-id ID [--wo WO --phase SWE.n]

Deterministic and model-free; no secret (the Fabro token) is printed or recorded.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..common import sha256_file, utc_now
from ..lrtx import stack as ST

SCHEMA = "forge-c/line-launch-attempt/1"
PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")
LIVE_KINDS = ("running", "submitted", "queued", "pending", "paused")  # the M0 bash list
ENDED_KINDS = ("succeeded", "failed", "cancelled", "canceled", "aborted", "dead", "timeout", "error")
GPU_LOCK_EXIT = 75  # `flock -n -E 75` of the M0 bash launcher

# typed outcome -> class. REFUSED: the line is busy or guarded (nothing was wrong); ORDER: the order/revision/inputs
# cannot be launched as given; INFRA: the stack or model service failed (retryable infrastructure); WORKORDER: the
# work-order CLI itself refused or failed.
CODES = {
    "GPU_LOCK_HELD": "REFUSED", "RUN_LIVE": "REFUSED", "STACK_LOCK_HELD": "REFUSED", "GUARD_FAIL": "REFUSED",
    "ORDER_ARGS_INVALID": "ORDER", "REV_UNKNOWN": "ORDER", "EXAMPLE_UNKNOWN": "ORDER", "PROFILE_UNKNOWN": "ORDER",
    "WO_ALREADY_RUN": "ORDER", "WORKTREE_PATH_OCCUPIED": "ORDER", "WORKTREE_REV_MISMATCH": "ORDER",
    "WORKTREE_ALREADY_LAUNCHED": "ORDER", "WORKTREE_NOT_CLEAN": "ORDER", "INPUT_OUTSIDE_REPO": "ORDER",
    "INPUT_MISSING": "ORDER", "INPUT_HASH_UNKNOWN": "ORDER", "INPUT_UNAVAILABLE": "ORDER",
    "WORKTREE_ADD_FAILED": "INFRA", "FABRO_API_UNREACHABLE": "INFRA", "STACK_STOP_INCOMPLETE": "INFRA",
    "STACK_START_FAILED": "INFRA", "STACK_NOT_HEALTHY": "INFRA", "EXPOSE_FAILED": "INFRA", "SMOKE_FAIL": "INFRA",
    "WORKORDER_LAUNCH_FAILED": "WORKORDER", "LAUNCH_NO_RUN_ID": "WORKORDER", "UNEXPECTED_ERROR": "INFRA",
    "QUALITY_FLAG_UNSUPPORTED": "ORDER",
}
_WO_RX = re.compile(r"^WO-[A-Za-z0-9][A-Za-z0-9-]{2,120}$")
_EX_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
_PROFILE_RX = re.compile(r"^[a-z0-9][a-z0-9.-]{0,120}$")
_REV_RX = re.compile(r"^[0-9a-f]{7,40}$")
_MODEL_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,200}$")
# the work-order flags the loop10 ladders pass in their EXTRA string (all others are refused, never forwarded)
EXTRA_FLAGS = {"--stop-after": "stop_after", "--resume-from": "resume_from", "--provided-from": "provided_from",
               "--resume-upto": "resume_upto", "--timeout-scale": "timeout_scale",
               "--quality": "quality_file"}  # M3: the campaign's order quality block (owner rule 2026-11-03), a JSON file


class LaunchError(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code, self.detail = code, str(detail)[:600]


# ------------------------------------------------------------------------------------------------------ configuration
OMNIVERSE2 = Path("/mnt/data/forge-c")
OMNIVERSE2_LINE = OMNIVERSE2 / "swe1-fabro-20261031"


@dataclass
class LineConfig:
    """The host layout of one line. Defaults are the Omniverse2 local line of the bash launcher; each value has a
    FORGE_LINE_* environment override and a CLI option."""
    launch_dir: Path = OMNIVERSE2_LINE                                   # bash $F: launch records, launch.log
    repo: Path = OMNIVERSE2_LINE / "repo"                                # line repo: worktrees are added from it
    stack_root: Path = OMNIVERSE2_LINE / "lrtx"                          # bash $L
    runs_root: Path = OMNIVERSE2_LINE / "runs"                           # one worktree per work order
    gpu_lock: Path = OMNIVERSE2 / "line/gpu.lock"                        # the M0 host launch lock
    python: Path = OMNIVERSE2_LINE / "lrtx/venv/bin/python"              # the stack venv (runs the run's own code)
    fabro_bin: str = str(OMNIVERSE2 / "fabro-0.362.0/fabro-x86_64-unknown-linux-musl/fabro")
    fabro_host_port: int = 32397                                         # expose-api --host-port (monitor, API)
    inputs_cache: Path | None = OMNIVERSE2 / "line/inputs-cache"         # content-addressed: sha256/<hex>
    references: tuple[Path, ...] = (OMNIVERSE2_LINE / "repo",)           # read-only sources of ignored inputs
    guard: tuple[str, ...] = ()                                          # optional host guard (prints OK)
    log: Path | None = OMNIVERSE2_LINE / "launch.log"
    health_timeout_s: float = 600.0
    health_poll_s: float = 5.0
    sweep_grace_s: float = 10.0
    uid: int = field(default_factory=os.getuid)

    @classmethod
    def from_env(cls, launch_dir=None, repo=None, stack_root=None, runs_root=None, gpu_lock=None, python=None,
                 fabro_bin=None, fabro_host_port=None, inputs_cache=None, references=None, guard=None,
                 log=True) -> LineConfig:
        """Explicit argument > FORGE_LINE_* environment > derived from the launch dir > the Omniverse2 default.
        `inputs_cache`/`guard` "" disable them; `log` False writes no launch.log."""
        e = os.environ.get
        F = Path(launch_dir or e("FORGE_LINE_LAUNCH_DIR") or OMNIVERSE2_LINE)
        L = Path(stack_root or e("FORGE_LINE_STACK_ROOT") or F / "lrtx")
        repo = Path(repo or e("FORGE_LINE_REPO") or F / "repo")
        guard_default = OMNIVERSE2 / "operations/swe1-obligations-20261031/work/guard.sh"
        g = guard if guard is not None else e("FORGE_LINE_GUARD", str(guard_default) if guard_default.is_file() else "")
        refs = references if references is not None else (
            [Path(x) for x in e("FORGE_LINE_REFERENCES").split(":") if x] if e("FORGE_LINE_REFERENCES") is not None
            else [repo])
        cache = inputs_cache if inputs_cache is not None else e("FORGE_LINE_INPUTS_CACHE", str(OMNIVERSE2 / "line/inputs-cache"))
        return cls(launch_dir=F, repo=repo, stack_root=L, runs_root=Path(runs_root or e("FORGE_LINE_RUNS_ROOT") or F / "runs"),
                   gpu_lock=Path(gpu_lock or e("FORGE_LINE_GPU_LOCK") or OMNIVERSE2 / "line/gpu.lock"),
                   python=Path(python or e("FORGE_LINE_PYTHON") or L / "venv/bin/python"),
                   fabro_bin=str(fabro_bin or e("FORGE_LINE_FABRO_BIN") or cls.fabro_bin),
                   fabro_host_port=int(fabro_host_port or e("FORGE_LINE_FABRO_PORT") or 32397),
                   inputs_cache=Path(cache) if cache else None, references=tuple(Path(x) for x in refs),
                   guard=("bash", str(g)) if g else (), log=F / "launch.log" if log else None)

    def describe(self) -> dict:
        d = {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(self).items()}
        d["references"] = [str(x) for x in self.references]
        d["guard"] = list(self.guard)
        return d


@dataclass
class Order:
    wo: str
    rev: str
    example: str
    profile: str
    model: str
    stop_after: str | None = None
    resume_from: str | None = None
    provided_from: str | None = None
    resume_upto: str | None = None
    timeout_scale: float | None = None
    purpose: str = "ASPICE_ONLY"
    quality_file: str | None = None  # absolute path of the order's quality block (JSON), outside the run worktree

    def validate(self) -> None:
        bad = [n for n, v, rx in (("wo", self.wo, _WO_RX), ("rev", self.rev, _REV_RX), ("example", self.example, _EX_RX),
                                   ("profile", self.profile, _PROFILE_RX), ("model", self.model, _MODEL_RX))
               if not isinstance(v, str) or not rx.match(v)]
        bad += [n for n in ("resume_from", "provided_from") if getattr(self, n) and not _WO_RX.match(getattr(self, n))]
        bad += [n for n in ("stop_after", "resume_upto") if getattr(self, n) and getattr(self, n) not in PHASES]
        if self.timeout_scale is not None and not 1.0 <= float(self.timeout_scale) <= 10.0:
            bad.append("timeout_scale")
        if self.purpose not in ("DEVELOPMENT", "FORMAL_REVIEW", "ASPICE_ONLY", "QM"):
            bad.append("purpose")
        if ".." in self.example:
            bad.append("example")
        if self.quality_file is not None and (not os.path.isabs(self.quality_file) or not os.path.isfile(self.quality_file)):
            bad.append("quality_file")
        if bad:
            raise LaunchError("ORDER_ARGS_INVALID", ",".join(sorted(set(bad))))

    def workorder_args(self) -> list[str]:
        """The work-order CLI arguments, exactly as launch-generic-model.sh passes them (run from factory/python)."""
        a = ["--example", f"../../examples/{self.example}", "--wo", self.wo, "--profile", self.profile,
             "--model", self.model, "--purpose", self.purpose]
        for flag, name in EXTRA_FLAGS.items():
            v = getattr(self, name)
            if v is not None:
                a += [flag, str(v)]
        return a + ["--detach"]


def parse_extra(extra: str) -> dict:
    """The ladders' EXTRA string (e.g. "--provided-from WO-.. --resume-from WO-.. --stop-after SWE.2") as Order
    fields. Only the work-order flags the ladders use are accepted; anything else is ORDER_ARGS_INVALID."""
    try:
        toks = shlex.split(extra or "")
    except ValueError as exc:
        raise LaunchError("ORDER_ARGS_INVALID", f"extra:{exc}") from None
    out: dict = {}
    i = 0
    while i < len(toks):
        flag, val = (toks[i].split("=", 1) + [None])[:2] if toks[i].startswith("--") and "=" in toks[i] else (toks[i], None)
        if flag not in EXTRA_FLAGS:
            raise LaunchError("ORDER_ARGS_INVALID", f"extra flag not allowed: {flag[:40]}")
        if val is None:
            if i + 1 >= len(toks):
                raise LaunchError("ORDER_ARGS_INVALID", f"extra flag without value: {flag}")
            val, i = toks[i + 1], i + 1
        name = EXTRA_FLAGS[flag]
        out[name] = float(val) if name == "timeout_scale" else val
        i += 1
    return out


# ---------------------------------------------------------------------------------------------------------- locks
@contextmanager
def gpu_lock(path: Path):
    """The M0 host launch lock (flock -n). Held for the whole launch; the stack daemons never inherit it (O_CLOEXEC,
    and subprocess closes every other descriptor), so it ends with the launcher like `flock -o`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDONLY | os.O_CREAT | os.O_CLOEXEC, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LaunchError("GPU_LOCK_HELD", f"another Forge-C launch holds {path}") from None
        yield fd
    finally:
        os.close(fd)


@contextmanager
def held_stack_lock(root: Path):
    """This launcher's hold of the stack lock (the same lock the stack's start/stop take); yields the descriptor the
    start/stop subprocesses inherit through FORGE_STACK_LOCK_FD."""
    path = ST.lock_path(root)
    if not path.parent.is_dir():  # never create a stack root (or its run/ folder) the stack itself would refuse
        raise LaunchError("STACK_START_FAILED", f"stack root not initialised: {path.parent} missing")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LaunchError("STACK_LOCK_HELD", str(path)) from None
        yield fd
    finally:
        os.close(fd)


def flock_holders(path: Path, proc_locks: Path = Path("/proc/locks")) -> set[int]:
    """PIDs /proc/locks names as FLOCK holders of `path` (read only; nothing is locked to find out)."""
    try:
        st = os.stat(path)
        lines = proc_locks.read_text().splitlines()
    except OSError:
        return set()
    key = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    out = set()
    for line in lines:
        parts = line.split()
        if "->" in parts or len(parts) < 6 or parts[1] != "FLOCK" or parts[5] != key:
            continue
        if parts[4].isdigit():
            out.add(int(parts[4]))
    return out


# ------------------------------------------------------------------------------------------------- processes / sweep
@dataclass
class Proc:
    pid: int
    uid: int | None
    cmdline: list[str]
    cwd: str | None = None
    environ: dict | None = None
    netns: str | None = None
    start: str | None = None
    ppid: int | None = None


class ProcFS:
    """The host's /proc, read only, plus identity-checked signals (pidfd; a reused PID is never signalled)."""

    def __init__(self, root: Path = Path("/proc")):
        self.root = root

    def pids(self) -> list[int]:
        return sorted(int(p.name) for p in self.root.iterdir() if p.name.isdigit())

    def get(self, pid: int) -> Proc | None:
        d = self.root / str(pid)
        try:
            raw = (d / "stat").read_text()
            fields = raw[raw.rfind(")") + 2:].split()
            uid = next(int(x.split()[1]) for x in (d / "status").read_text().splitlines() if x.startswith("Uid:"))
            cmd = [x.decode(errors="replace") for x in (d / "cmdline").read_bytes().split(b"\0") if x]
        except (OSError, StopIteration, IndexError, ValueError):
            return None

        def opt(fn):
            try:
                return fn()
            except OSError:
                return None

        env = opt(lambda: dict(x.decode(errors="replace").split("=", 1) for x in (d / "environ").read_bytes().split(b"\0")
                               if b"=" in x))
        return Proc(pid=pid, uid=uid, cmdline=cmd, cwd=opt(lambda: os.readlink(d / "cwd")), environ=env,
                    netns=opt(lambda: os.readlink(d / "ns/net")), start=fields[19], ppid=int(fields[1]))

    def lock_holders(self, path: Path) -> set[int]:
        """Holders of a lock file: the /proc/locks FLOCK owner and every process of ours with a descriptor on it (a
        child that inherited the open file description keeps the lock alive after the owner died)."""
        out = {p for p in flock_holders(path, self.root / "locks") if (self.root / str(p)).exists()}
        try:
            target = os.path.realpath(path)
        except OSError:
            return out
        me = os.getuid()
        for pid in self.pids():
            d = self.root / str(pid)
            try:
                if d.stat().st_uid != me:
                    continue
                for fd in (d / "fd").iterdir():
                    if os.readlink(fd) == target:
                        out.add(pid)
                        break
            except OSError:
                continue
        return out

    def alive(self, pid: int, start: str | None) -> bool:
        p = self.get(pid)
        return p is not None and (start is None or p.start == start) and not self._zombie(pid)

    def _zombie(self, pid: int) -> bool:
        try:
            raw = (self.root / str(pid) / "stat").read_text()
            return raw[raw.rfind(")") + 2:].split()[0] in ("Z", "X")
        except (OSError, IndexError):
            return True

    def signal(self, pid: int, start: str | None, sig: int, uid: int) -> bool:
        from ..lrtx import pidfd

        try:
            fd = pidfd.open_pid(pid)
        except (ProcessLookupError, OSError):
            return False
        try:
            p = self.get(pid)  # identity re-checked after the pidfd pins the process
            if p is None or p.uid != uid or (start is not None and p.start != start):
                return False
            pidfd.send_signal(fd, sig)
            return True
        except (ProcessLookupError, OSError):
            return False
        finally:
            os.close(fd)

    def self_chain(self) -> set[int]:
        out, pid = set(), os.getpid()
        while pid and pid not in out and pid > 1:
            out.add(pid)
            p = self.get(pid)
            pid = p.ppid if p else 0
        return out


HOLDER_KINDS = ("netns_holder", "serving_holder")
_NSENTER_VALUE_OPTS = {"-t", "--target", "-S", "--setuid", "-G", "--setgid", "-w", "--wd", "-r", "--root"}


def _inner(argv: list[str]) -> list[str]:
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in _NSENTER_VALUE_OPTS else 1
    return argv[i:]


def kind_of(argv: list[str]) -> str | None:
    """The stack-daemon kind of a command line (lrtx/stack.py's processes), else None: a process of any other kind
    (a supervisor, a monitor, a gate node, a shell) is never swept, whatever its environment says."""
    if not argv:
        return None
    b = os.path.basename(argv[0])
    if b in ("nsenter", "unshare", "setsid"):
        inner = _inner(argv)
        k = kind_of(inner)
        return "serving_holder" if b == "unshare" and k == "netns_holder" else k
    if b == "fabro":
        return "fabro"
    if b == "ollama":
        return "ollama"
    if b == "llama-server":
        return "llama_server"
    if b == "socat":
        return "api_bridge"
    if b.startswith("python") and "forge_factory.llm_gateway" in argv:
        return "gateway"
    if b == "sleep" and argv[1:] == ["infinity"]:
        return "netns_holder"
    return None


def _under(path: str | None, root: str) -> bool:
    return bool(path) and (path == root or path.startswith(root + "/"))


def root_evidence(p: Proc, root: Path, lock_holders: set[int] = frozenset()) -> list[str]:
    r = str(root).rstrip("/")
    rx = re.compile(r"(?:^|[=:,@\s])" + re.escape(r) + r"(?:/|$|[\s,])")
    ev = []
    if any(rx.search(a) for a in p.cmdline):
        ev.append("cmdline")
    if _under(p.cwd, r):
        ev.append("cwd")
    if p.environ and (p.environ.get("FORGE_LRTX_ROOT") or "").rstrip("/") == r:
        ev.append("environ")
    if p.pid in lock_holders:
        ev.append("storage_lock")
    return ev


def storage_lock(root: Path) -> Path:
    return Path(root) / "fabro/storage/server.lock"


def _live_holder(root: Path, procs, uid: int) -> Proc | None:
    f = Path(root) / "run/holder.pid"
    try:
        pid = int(f.read_text().strip())
    except (OSError, ValueError):
        return None
    p = procs.get(pid)
    return p if p is not None and p.uid == uid and kind_of(p.cmdline) == "netns_holder" else None


def _recorded(root: Path) -> set[tuple[int, str | None]]:
    try:
        rec = json.loads((Path(root) / "run/services.json").read_text())
    except (OSError, ValueError):
        return set()
    out = set()
    for group in (rec.get("processes") or {}, rec.get("api_bridge") or {}):
        for v in group.values():
            if isinstance(v, dict) and isinstance(v.get("pid"), int):
                out.add((v["pid"], str((v.get("identity") or {}).get("start_ticks"))))
    return out


def survey(root: Path, procs, uid: int) -> tuple[list[dict], Proc | None]:
    """Every stack-daemon process of our UID with evidence of this root; `current` when it belongs to the live stack
    (inside the live holder's network namespace, or recorded with its start identity in run/services.json)."""
    holder = _live_holder(root, procs, uid)
    live_ns = holder.netns if holder else None
    recorded = _recorded(root) if holder else set()
    locks = procs.lock_holders(storage_lock(root))
    mine = procs.self_chain()
    out = []
    for pid in procs.pids():
        if pid in mine:
            continue
        p = procs.get(pid)
        if p is None or p.uid != uid:
            continue
        k = kind_of(p.cmdline)
        if k is None:
            continue
        ev = root_evidence(p, root, locks)
        if not ev:
            continue
        current = bool(live_ns) and (p.netns == live_ns or (pid, str(p.start)) in recorded)
        out.append({"pid": pid, "kind": k, "netns": p.netns, "start": p.start, "evidence": ev, "current": current,
                    "storage_lock": pid in locks, "cmd": " ".join(p.cmdline)[:160]})
    return out, holder


def sweep(root: Path, procs=None, *, uid: int | None = None, kill: bool = False, grace_s: float = 10.0,
          sleep=time.sleep) -> dict:
    """The orphan sweep: processes of our UID, of a stack-daemon kind, with evidence of THIS root, that are not part of
    the live stack (e.g. the 2026-11-03 00:49Z race: a Fabro server holding <root>/fabro/storage/server.lock in a
    network namespace whose holder was gone, with its Ollama and gateway). Without `kill` it only reports. With
    `kill`: SIGTERM through a pidfd after re-checking the start identity (holders SIGKILL), SIGKILL after the grace."""
    procs = procs or ProcFS()
    uid = os.getuid() if uid is None else uid
    cands, holder = survey(root, procs, uid)
    orphans = [c for c in cands if not c["current"]]
    rep = {"root": str(root), "live_holder": holder.pid if holder else None,
           "live_netns": holder.netns if holder else None, "candidates": cands,
           "orphans": [c["pid"] for c in orphans], "killed": [], "survivors": [], "signalled": []}
    if kill and orphans:
        for c in sorted(orphans, key=lambda c: c["kind"] in HOLDER_KINDS):
            sig = signal.SIGKILL if c["kind"] in HOLDER_KINDS else signal.SIGTERM
            if procs.signal(c["pid"], c["start"], sig, uid):
                rep["signalled"].append({"pid": c["pid"], "signal": signal.Signals(sig).name})
        for budget, final in ((grace_s, True), (5.0, False)):
            waited = 0.0
            while any(procs.alive(c["pid"], c["start"]) for c in orphans) and waited < budget:
                sleep(0.25)
                waited += 0.25
            left = [c for c in orphans if procs.alive(c["pid"], c["start"])]
            if not left or not final:
                break
            for c in left:
                if procs.signal(c["pid"], c["start"], signal.SIGKILL, uid):
                    rep["signalled"].append({"pid": c["pid"], "signal": "SIGKILL"})
        rep["survivors"] = [c["pid"] for c in orphans if procs.alive(c["pid"], c["start"])]
        rep["killed"] = [c["pid"] for c in orphans if c["pid"] not in rep["survivors"]]
    rep["storage_lock_holders"] = sorted(procs.lock_holders(storage_lock(root)))
    return rep


def safe_sweep(cfg: LineConfig, host=None, procs=None) -> dict:
    """The orphan sweep with kill, only under the launch lock and the stack lock and with no live run (never under a
    running launch). Raises LaunchError GPU_LOCK_HELD / STACK_LOCK_HELD / RUN_LIVE / FABRO_API_UNREACHABLE."""
    host = host or ShellHost(cfg)
    procs = procs or ProcFS()
    with gpu_lock(cfg.gpu_lock), held_stack_lock(cfg.stack_root):
        live_runs(cfg, host, procs)
        return sweep(cfg.stack_root, procs, uid=cfg.uid, kill=True, grace_s=cfg.sweep_grace_s)


# ---------------------------------------------------------------------------------------------------------- git
def _git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(k, None)
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args], capture_output=True,
                          env=env, check=check, stdin=subprocess.DEVNULL)


def resolve_rev(repo: Path, rev: str) -> str:
    p = _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    if p.returncode != 0:
        raise LaunchError("REV_UNKNOWN", f"{rev} not in {repo}")
    return p.stdout.decode().strip()


class RevReader:
    """Files of one revision read from git objects (no checkout needed; also serves the dry run)."""

    def __init__(self, repo: Path, sha: str):
        self.repo, self.sha = repo, sha

    def read(self, path: str) -> bytes | None:
        p = _git(self.repo, "cat-file", "blob", f"{self.sha}:{path}")
        return p.stdout if p.returncode == 0 else None

    def tracked(self, path: str) -> bool:
        return _git(self.repo, "cat-file", "-e", f"{self.sha}:{path}").returncode == 0

    def names(self, prefix: str) -> list[str]:
        p = _git(self.repo, "ls-tree", "-r", "--name-only", self.sha, "--", prefix)
        return p.stdout.decode().splitlines() if p.returncode == 0 else []


def profile_facts(reader: RevReader, profile: str) -> dict:
    """Ports and served models of the order's profile at the order's revision (lrtx.profile.load validates it)."""
    from ..lrtx import profile as lp

    raw = reader.read(f"config/factory/profiles/{profile}.yaml")
    if raw is None:
        raise LaunchError("PROFILE_UNKNOWN", f"{profile} at {reader.sha[:12]}")
    with tempfile.TemporaryDirectory(prefix="line-profile-") as d:
        (Path(d) / f"{profile}.yaml").write_bytes(raw)
        try:
            prof = lp.load(profile, directory=Path(d))
        except lp.ProfileRefused as exc:
            raise LaunchError("PROFILE_UNKNOWN", ";".join(exc.issues)) from None
    served = ST.served_models(prof)
    # alternates first, then the primary the stack starts with: the bash launcher's Ornith -> Qwen order, which
    # leaves the stack serving its own primary model at launch
    return {"ports": dict(prof["deployment"]["ports"]), "served": served, "smoke": served[1:] + served[:1]}


def quality_supported(reader: RevReader) -> bool:
    """M3: the revision's work-order CLI takes the order quality block (`--quality FILE`)."""
    src = reader.read("factory/python/forge_factory/workorder.py") or b""
    return b'"--quality"' in src


def worktree_clean(wt: Path) -> list[str]:
    p = _git(wt, "status", "--porcelain")
    if p.returncode != 0:
        return [f"git status rc {p.returncode}"]
    return [x for x in p.stdout.decode().splitlines() if x and not x[3:].startswith(".forge-run/")]


def _common_dir(path: Path) -> str | None:
    p = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return os.path.realpath(p.stdout.decode().strip()) if p.returncode == 0 else None


def prior_attempts(cfg: LineConfig, wo: str) -> list[dict]:
    out = []
    for d in (cfg.runs_root / wo / ".forge-run/launch", cfg.runs_root / ".launch" / wo):
        for f in sorted(d.glob("attempt-*.json")) if d.is_dir() else []:
            try:
                out.append(json.loads(f.read_text()))
            except (OSError, ValueError):
                out.append({"attempt": f.stem, "outcome": "UNREADABLE"})
    return out


def ensure_worktree(cfg: LineConfig, order: Order, sha: str) -> tuple[Path, bool]:
    """The order's own worktree at `sha`: added from the line repo when missing (the shared checkout's HEAD, index and
    files are never touched), reused only by a re-attempt of the same order at the same revision that never
    launched."""
    wt = cfg.runs_root / order.wo
    if wt.exists() and (not wt.is_dir() or any(wt.iterdir())):
        top = _git(wt, "rev-parse", "--show-toplevel")
        if top.returncode != 0 or os.path.realpath(top.stdout.decode().strip()) != os.path.realpath(wt) \
                or _common_dir(wt) != _common_dir(cfg.repo):
            raise LaunchError("WORKTREE_PATH_OCCUPIED", str(wt))
        head = _git(wt, "rev-parse", "HEAD").stdout.decode().strip()
        if head != sha:
            raise LaunchError("WORKTREE_REV_MISMATCH", f"{wt} is at {head[:12]}, order wants {sha[:12]}")
        launched = [a.get("fabro_run_id") for a in prior_attempts(cfg, order.wo) if a.get("outcome") == "LAUNCHED"]
        if launched:
            raise LaunchError("WORKTREE_ALREADY_LAUNCHED", f"{order.wo} launched as {launched[-1]}; a new run needs a new WO")
        created = False
    else:
        cfg.runs_root.mkdir(parents=True, exist_ok=True)
        p = _git(cfg.repo, "worktree", "add", "--detach", str(wt), sha)
        if p.returncode != 0:
            raise LaunchError("WORKTREE_ADD_FAILED", p.stderr.decode(errors="replace").strip()[-300:])
        created = True
    dirty = worktree_clean(wt)
    if dirty:
        raise LaunchError("WORKTREE_NOT_CLEAN", "; ".join(dirty[:5]))
    return wt, created


# ---------------------------------------------------------------------------------------------------------- inputs
def needed_inputs(reader: RevReader, example: str) -> list[str]:
    raw = reader.read(f"examples/{example}/workorder.json")
    if raw is None:
        raise LaunchError("EXAMPLE_UNKNOWN", f"examples/{example}/workorder.json at {reader.sha[:12]}")
    spec = json.loads(raw)
    rels = [i["path"] for i in spec.get("inputs") or [] if isinstance(i, dict) and i.get("path")]
    if spec.get("provided_requirements"):
        rels.append(spec["provided_requirements"])
    out = []
    for rel in rels:
        n = os.path.normpath(os.path.join("examples", example, rel))
        if os.path.isabs(rel) or n.startswith(".."):
            raise LaunchError("INPUT_OUTSIDE_REPO", rel)
        if n not in out:
            out.append(n)
    return out


def input_hashes(reader: RevReader) -> dict[str, str]:
    """repo path -> sha256 from every tracked inputs manifest of the revision (examples/*/inputs/*manifest*.json:
    documents[].markdown / markdown_sha256, the pdf2md conversion record)."""
    out = {}
    for name in reader.names("examples"):
        parts = name.split("/")
        if len(parts) != 4 or parts[2] != "inputs" or not re.match(r".*manifest.*\.json$", parts[3]):
            continue
        try:
            docs = json.loads(reader.read(name) or b"{}").get("documents") or []
        except ValueError:
            continue
        for d in docs:
            if isinstance(d, dict) and d.get("markdown") and re.fullmatch(r"[0-9a-f]{64}", str(d.get("markdown_sha256"))):
                out[os.path.normpath(os.path.join(os.path.dirname(name), d["markdown"]))] = d["markdown_sha256"]
    return out


def _cache_file(cache: Path, sha: str) -> Path:
    return cache / "sha256" / sha


def plan_inputs(reader: RevReader, example: str, cfg: LineConfig, wt: Path | None = None) -> list[dict]:
    """For each input the order names: TRACKED (in the revision), PRESENT (already in the worktree with the
    manifest hash) or a verified source (cache / reference checkout). Raises the first input that cannot be had."""
    idx = None
    out = []
    for rel in needed_inputs(reader, example):
        if reader.tracked(rel):
            out.append({"path": rel, "status": "TRACKED"})
            continue
        idx = input_hashes(reader) if idx is None else idx
        sha = idx.get(rel)
        if sha is None:
            raise LaunchError("INPUT_HASH_UNKNOWN", f"{rel}: git-ignored and no tracked manifest records its sha256")
        if wt is not None and (wt / rel).is_file() and sha256_file(wt / rel) == sha:
            out.append({"path": rel, "status": "PRESENT", "sha256": sha})
            continue
        src = None
        if cfg.inputs_cache is not None:
            c = _cache_file(cfg.inputs_cache, sha)
            if c.is_file() and sha256_file(c) == sha:
                src = ("cache", c)
        for ref in cfg.references if src is None else ():
            f = Path(ref) / rel
            if f.is_file() and sha256_file(f) == sha:
                src = ("reference", f)
                break
        if src is None:
            raise LaunchError("INPUT_UNAVAILABLE", f"{rel} sha256 {sha[:16]}: not in the inputs cache or any reference")
        out.append({"path": rel, "status": "COPY", "sha256": sha, "source": src[0], "from": str(src[1])})
    return out


def provision_inputs(items: list[dict], wt: Path, cache: Path | None) -> list[dict]:
    for it in items:
        if it["status"] != "COPY":
            continue
        dst = wt / it["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(f".{dst.name}.line-copy")
        shutil.copyfile(it["from"], tmp)
        if sha256_file(tmp) != it["sha256"]:  # the source changed between the plan and the copy
            tmp.unlink(missing_ok=True)
            raise LaunchError("INPUT_UNAVAILABLE", f"{it['path']}: hash changed while copying")
        os.chmod(tmp, 0o644)
        os.replace(tmp, dst)
        it["status"] = "COPIED"
        if cache is not None and it["source"] != "cache":
            c = _cache_file(cache, it["sha256"])
            if not c.is_file():
                c.parent.mkdir(parents=True, exist_ok=True)
                ctmp = c.with_name(f".{c.name}.{os.getpid()}")
                shutil.copyfile(dst, ctmp)
                os.chmod(ctmp, 0o444)
                os.replace(ctmp, c)
    return items


# ---------------------------------------------------------------------------------------------------------- host
LOCK_FD_ENV = ST.LOCK_FD_ENV
DROP_ENV = ("PYTHONPATH", "FORGE_REPO_ROOT", "FORGE_OPERATIONS_INTENT", "FORGE_DURABLE_AUTONOMY", "VIRTUAL_ENV",
            "FORGE_LRTX_ROOT", "FORGE_LRTX_PROFILE", "FORGE_FABRO_BIN", LOCK_FD_ENV, "FORGE_FABRO_TOKEN")


def run_env(cfg: LineConfig, wt: Path, profile: str) -> dict:
    """The bash launcher's exports: the stack and the work order run the RUN WORKTREE's code (lrtx.stack binds its
    REPO_ROOT, the gateway's PYTHONPATH and the work orders' factory code to FORGE_REPO_ROOT at import time). No
    operations intent is inherited (the stack stays unmanaged, as under the bash launcher)."""
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    env.update(FORGE_REPO_ROOT=str(wt), PYTHONPATH=str(wt / "factory/python"), FORGE_LRTX_ROOT=str(cfg.stack_root),
               FORGE_LRTX_PROFILE=profile, FORGE_FABRO_BIN=cfg.fabro_bin)
    return env


class FabroUnavailable(RuntimeError):
    pass


class ShellHost:
    """Real side effects: the run worktree's `python -m forge_factory.lrtx.stack ...` and the local Fabro API."""

    def __init__(self, cfg: LineConfig):
        self.cfg = cfg

    def stack(self, args: list[str], *, env: dict, cwd: Path, log: Path, lock_fd: int | None = None,
              timeout: float = 1800) -> tuple[int, str]:
        env = dict(env)
        if lock_fd is not None:
            env[LOCK_FD_ENV] = str(lock_fd)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("ab") as fh:  # a file, not a pipe: a daemon that kept a pipe open would hang the launcher
            try:
                rc = subprocess.run([str(self.cfg.python), "-m", "forge_factory.lrtx.stack", *args], env=env, cwd=cwd,
                                    stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout,
                                    pass_fds=(lock_fd,) if lock_fd is not None else ()).returncode
            except subprocess.TimeoutExpired:
                rc = 124
        return rc, log.read_text(errors="replace")[-20000:]

    def _client(self):
        from ..fabro.client import FabroClient, load_token

        return FabroClient(base_url=f"http://127.0.0.1:{self.cfg.fabro_host_port}",
                           token=load_token(str(self.cfg.stack_root / "fabro/storage")), timeout=10)

    def fabro_runs(self) -> list[dict]:
        from ..fabro.client import FabroUnavailable as FU

        try:
            with self._client() as c:
                return c.list_runs(limit=100)
        except (FU, OSError, ValueError) as exc:
            raise FabroUnavailable(type(exc).__name__) from None
        except Exception as exc:  # noqa: BLE001 - httpx status errors: the API did not answer usefully
            raise FabroUnavailable(type(exc).__name__) from None

    def fabro_run(self, run_id: str) -> dict:
        try:
            with self._client() as c:
                return c.get_run(run_id)
        except Exception as exc:  # noqa: BLE001
            raise FabroUnavailable(type(exc).__name__) from None

    def fabro_runs_in_ns(self, pid: int, port: int) -> list[dict] | None:
        """Ask a Fabro server outside the live stack (an orphan) for its runs, inside its own namespaces."""
        from ..fabro.client import load_token

        code = ("import os,sys,urllib.request;r=urllib.request.Request(sys.argv[1],headers={'Authorization':"
                "'Bearer '+os.environ.get('FORGE_T','')});sys.stdout.write(urllib.request.urlopen(r,timeout=5).read().decode())")
        env = {"PATH": ST.SYSTEM_PATH, "FORGE_T": load_token(str(self.cfg.stack_root / "fabro/storage")) or ""}
        try:
            p = subprocess.run(ST._nsenter(pid) + [str(self.cfg.python), "-c", code,
                                                    f"http://127.0.0.1:{port}/api/v1/runs?page%5Blimit%5D=100"],
                               env=env, capture_output=True, timeout=30, stdin=subprocess.DEVNULL)
            return json.loads(p.stdout).get("data", []) if p.returncode == 0 else None
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None

    def guard(self, own_pid: int | None) -> str:
        if not self.cfg.guard:
            return "OK"
        p = subprocess.run([*self.cfg.guard, str(own_pid or "")], capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
        return (p.stdout.strip().splitlines() or [f"FAIL:GUARD_RC_{p.returncode}"])[-1]

    sleep = staticmethod(time.sleep)
    monotonic = staticmethod(time.monotonic)


def _last_json(out: str) -> dict | None:
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict):
                return d
    return None


# ---------------------------------------------------------------------------------------------------------- Fabro
def _kind(run: dict) -> str | None:
    st = (run.get("lifecycle") or {}).get("status")
    return st.get("kind") if isinstance(st, dict) else st


def _reason(run: dict) -> str | None:
    st = (run.get("lifecycle") or {}).get("status")
    return st.get("reason") if isinstance(st, dict) else None


def live_runs(cfg: LineConfig, host, procs=None, ports: dict | None = None) -> dict:
    """Live Forge-C runs of this stack root (the M0 rule: lifecycle running/submitted/queued/pending/paused and a
    source_directory under <root>/state/). Fails closed: an API that does not answer while a Fabro of the live stack
    is alive is FABRO_API_UNREACHABLE. Fabro servers outside the live stack (orphans) are asked in their own
    namespace; one that does not answer cannot be asked and is left to the sweep."""
    procs = procs or ProcFS()
    prefix = str(cfg.stack_root).rstrip("/") + "/state/"

    def live(runs):
        return [r.get("id") for r in runs or [] if _kind(r) in LIVE_KINDS
                and str(r.get("source_directory", "")).startswith(prefix)]

    out = {"api": "UP", "live": [], "orphan_fabro": []}
    try:
        out["live"] = live(host.fabro_runs())
    except FabroUnavailable as exc:
        out["api"] = f"UNREACHABLE:{exc}"
    cands, _holder = survey(cfg.stack_root, procs, cfg.uid)
    fabros = [c for c in cands if c["kind"] == "fabro"]
    if out["api"] != "UP" and any(c["current"] for c in fabros):
        raise LaunchError("FABRO_API_UNREACHABLE", f"Fabro {[c['pid'] for c in fabros if c['current']]} of the live "
                                                   f"stack is alive but its API on :{cfg.fabro_host_port} does not answer")
    port = (ports or {}).get("fabro") or _recorded_port(cfg.stack_root)
    for c in fabros:
        if c["current"]:
            continue
        runs = host.fabro_runs_in_ns(c["pid"], port) if port else None
        out["orphan_fabro"].append({"pid": c["pid"], "answered": runs is not None})
        out["live"] += [f"{x}@orphan-fabro-{c['pid']}" for x in live(runs)]
    if out["live"]:
        raise LaunchError("RUN_LIVE", " ".join(map(str, out["live"])))
    return out


def _recorded_port(root: Path) -> int | None:
    try:
        return int(json.loads((Path(root) / "run/services.json").read_text())["ports"]["fabro"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def wait_for_end(run_id: str, host, *, poll_s: float = 30.0, timeout_s: float | None = None, sleep=None,
                 monotonic=None) -> dict:
    """Poll the local Fabro API until the run ends (the loop10 waiter's status set plus aborted/dead). An unreachable
    API is waited through (counted), never read as an end; `timeout_s` bounds the wait (ended False)."""
    sleep = sleep or host.sleep
    monotonic = monotonic or host.monotonic
    t0, unreachable, polls = monotonic(), 0, 0
    last = reason = None
    while True:
        polls += 1
        try:
            run = host.fabro_run(run_id)
            last, reason = _kind(run), _reason(run)
        except FabroUnavailable:
            unreachable += 1
        if last in ENDED_KINDS:
            return {"run_id": run_id, "status": last, "reason": reason, "ended": True, "polls": polls,
                    "unreachable_polls": unreachable}
        if timeout_s is not None and monotonic() - t0 >= timeout_s:
            return {"run_id": run_id, "status": last, "reason": reason, "ended": False, "polls": polls,
                    "unreachable_polls": unreachable}
        sleep(poll_s)


# ---------------------------------------------------------------------------------------------------------- verdict
VERDICTS = ("PASS", "NO", "INFRA_UNAVAILABLE")


def phase_verdict(workspace: Path, phase: str) -> dict:
    """The phase gate verdict from <workspace>/.forge-run/gates/gate-log.jsonl. PASS: the phase's last inspect
    decision is PASS (the ladders' rule). INFRA_UNAVAILABLE: its latest author/inspect/route record is CAPA-122's
    infrastructure outcome (model calls refused/unreachable after the bounded wait; retryable, not a product
    rejection). NO: everything else, including a missing log."""
    from ..inspection import outage
    from .line_conductor import _gate_log

    if phase not in PHASES:
        raise ValueError(f"PHASE_INVALID:{phase}")
    log = Path(workspace) / ".forge-run/gates/gate-log.jsonl"
    if not log.is_file():
        return {"phase": phase, "verdict": "NO", "reason": "GATE_LOG_MISSING"}
    rows = [e for e in _gate_log(Path(workspace)) if e.get("phase") == phase]
    steps = [e for e in rows if e.get("step") in ("author", "inspect", "route")]
    last = steps[-1] if steps else None
    if last is not None and (outage.is_infra_row(last) or (last.get("step") == "route"
                                                           and (last.get("gate") or {}).get("infra_outcome"))):
        return {"phase": phase, "verdict": outage.INFRA, "reason": f"{last.get('step')}:{outage.CODE}",
                "line": last.get("_line")}
    ins = [e for e in rows if e.get("step") == "inspect"]
    decision = (ins[-1].get("gate") or {}).get("decision") if ins else None
    return {"phase": phase, "verdict": "PASS" if decision == "PASS" else "NO",
            "reason": f"inspect:{decision}" if ins else "NO_INSPECTION", "line": ins[-1].get("_line") if ins else None}


def order_verdict(cfg: LineConfig, wo: str, phase: str) -> dict:
    return {"work_order": wo, **phase_verdict(cfg.stack_root / "state/workorders" / wo / "workspace", phase)}


# ---------------------------------------------------------------------------------------------------------- transcript
class Attempt:
    """One launch attempt: its number (reserved atomically), its step records and its transcript file."""

    def __init__(self, cfg: LineConfig, order: Order, dry_run: bool):
        self.cfg, self.order, self.dry_run = cfg, order, dry_run
        self.steps: list[dict] = []
        self.started, self.t0 = utc_now(), time.monotonic()
        self.worktree: Path | None = None
        self.sha: str | None = None
        self.number = self._reserve() if not dry_run else 0
        self.logdir = cfg.runs_root / ".launch" / order.wo / f"attempt-{self.number}"

    def _reserve(self) -> int:
        base = self.cfg.runs_root / ".launch" / self.order.wo
        base.mkdir(parents=True, exist_ok=True)
        seen = [int(m.group(1)) for d in (base, self.cfg.runs_root / self.order.wo / ".forge-run/launch") if d.is_dir()
                for f in d.iterdir() if (m := re.match(r"attempt-(\d+)", f.name))]
        n = max(seen, default=0) + 1
        while True:
            try:
                (base / f"attempt-{n}").mkdir()
                return n
            except FileExistsError:
                n += 1

    def step(self, name: str, outcome: str = "OK", **detail) -> dict:
        rec = {"step": name, "outcome": outcome, "at": utc_now(), "t_s": round(time.monotonic() - self.t0, 2), **detail}
        self.steps.append(rec)
        return rec

    def write(self, result: dict) -> Path | None:
        if self.dry_run:
            return None
        doc = {"schema": SCHEMA, "work_order": self.order.wo, "attempt": self.number, "started_at": self.started,
               "ended_at": utc_now(), "order": asdict(self.order), "revision": self.sha,
               "worktree": str(self.worktree) if self.worktree else None, "config": self.cfg.describe(),
               "outcome": result["outcome"], "class": result["class"], "detail": result.get("detail", ""),
               "fabro_run_id": result.get("fabro_run_id"), "steps": self.steps, "step_logs": str(self.logdir)}
        d = (self.worktree / ".forge-run/launch") if self.worktree else (self.cfg.runs_root / ".launch" / self.order.wo)
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"attempt-{self.number}.json"
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
        os.replace(tmp, f)
        return f


def legacy_line(code: str, detail: str, order: Order) -> str:
    """The bash launcher's marker line for a typed outcome (the loop10 waiter greps these; the M1 Line Conductor's
    LAUNCH_RULES classify them). A code the bash launcher never had becomes the work-order CLI's REFUSED shape on the
    LAUNCH line, from which M1 takes the code."""
    d = detail[:300]
    if code == "GPU_LOCK_HELD":
        return f"GPU_LOCK_HELD: another Forge-C launch holds the host launch lock ({order.wo})"
    if code == "RUN_LIVE":
        return f"RUN_LIVE: Forge-C run(s) {d} still live on this stack; not restarting it"
    if code == "STACK_STOP_INCOMPLETE":
        return f"OWN llama-server still running after stop (STACK_STOP_INCOMPLETE: {d})"
    if code == "STACK_NOT_HEALTHY":
        return f"STACK NOT HEALTHY: {d}"
    if code == "STACK_START_FAILED":
        m = re.match(r"rc (\d+)", d)
        return f"STACK START ({order.profile}) rc {m.group(1) if m and m.group(1) != '0' else 1}: {d}"
    if code == "SMOKE_FAIL":
        return f"SMOKE FAIL: {d}"
    if code in ("REV_UNKNOWN", "WORKTREE_REV_MISMATCH", "WORKTREE_NOT_CLEAN", "WORKTREE_PATH_OCCUPIED"):
        return f"CODE NOT AT {order.rev} OR NOT CLEAN ({code}: {d})"
    if code == "GUARD_FAIL":
        return f"GUARD FAIL {d}"
    if code == "WORKORDER_LAUNCH_FAILED":
        m = re.match(r"rc (\d+): ?(.*)", d, re.S)
        rc = m.group(1) if m and m.group(1) != "0" else "1"
        return f"LAUNCH {order.wo} rc {rc}: {(m.group(2) if m else d)}"
    return f"LAUNCH {order.wo} rc 1: " + json.dumps({"work_order": order.wo, "status": "REFUSED",
                                                      "stage": "line_launcher", "issues": [f"{code}:{d}"]})


# ---------------------------------------------------------------------------------------------------------- launch
def _result(att: Attempt, outcome: str, detail: str = "", **extra) -> dict:
    cls = "LAUNCHED" if outcome == "LAUNCHED" else ("PLANNED" if outcome == "PLANNED" else CODES.get(outcome, "INFRA"))
    return {"work_order": att.order.wo, "outcome": outcome, "class": cls, "detail": detail, "attempt": att.number,
            "revision": att.sha, "worktree": str(att.worktree) if att.worktree else None, **extra}


def launch(order: Order, cfg: LineConfig | None = None, *, host=None, procs=None, say=None,
           dry_run: bool = False) -> dict:
    """One launch attempt of one order. Returns {outcome: LAUNCHED|<typed code>, class, fabro_run_id, worktree,
    attempt, transcript}. Every refusal/failure is typed (CODES); nothing is retried here (the supervisor decides).
    `dry_run`: only read-only probes (lock holders, Fabro API GET, git objects, /proc), the plan is returned and
    nothing is locked, created, copied, started, stopped or killed."""
    cfg = cfg or LineConfig.from_env()
    host = host or ShellHost(cfg)
    procs = procs or ProcFS()
    say = say or (lambda _line: None)
    order.validate()
    att = Attempt(cfg, order, dry_run)
    result = None
    try:
        if dry_run:
            result = _plan(att, cfg, order, host, procs, say)
        else:
            with gpu_lock(cfg.gpu_lock):
                att.step("gpu_lock", lock=str(cfg.gpu_lock))
                result = _launch_locked(att, cfg, order, host, procs, say)
    except LaunchError as exc:
        att.step("outcome", exc.code, detail=exc.detail)
        say(legacy_line(exc.code, exc.detail, order))
        result = _result(att, exc.code, exc.detail)
    except Exception as exc:  # noqa: BLE001 - never an untyped end: the transcript records it as infrastructure
        detail = f"{type(exc).__name__}: {str(exc)[:300]}"
        att.step("outcome", "UNEXPECTED_ERROR", detail=detail)
        say(legacy_line("UNEXPECTED_ERROR", detail, order))
        result = _result(att, "UNEXPECTED_ERROR", detail)
    path = att.write(result)
    result["transcript"] = str(path) if path else None
    return result


def _launch_locked(att: Attempt, cfg: LineConfig, order: Order, host, procs, say) -> dict:
    # 2 RUN_LIVE: first, before any worktree or stack action
    lr = live_runs(cfg, host, procs)
    att.step("run_live", api=lr["api"], orphan_fabro=lr["orphan_fabro"])
    say(f"step run_live ok: no live run on {cfg.stack_root} (api {lr['api'].lower()})")
    sha = resolve_rev(cfg.repo, order.rev)  # read only (git objects of the line repo)
    att.sha = sha
    reader = RevReader(cfg.repo, sha)
    facts = profile_facts(reader, order.profile)
    att.step("revision", sha=sha, ports=facts["ports"], smoke=facts["smoke"])
    if order.quality_file and not quality_supported(reader):
        raise LaunchError("QUALITY_FLAG_UNSUPPORTED", f"the work-order CLI at {sha[:12]} has no --quality")
    done = cfg.stack_root / "state/workorders" / order.wo / "workspace/.forge-run/fabro_run_id"
    if done.is_file():
        raise LaunchError("WO_ALREADY_RUN", f"{order.wo} already has Fabro run {done.read_text().strip()[:40]}")
    # 3 the order's own worktree + its verified inputs
    wt, created = ensure_worktree(cfg, order, sha)
    att.worktree = wt
    att.step("worktree", path=str(wt), created=created, head=sha)
    say(f"step worktree ok: {wt} at {sha[:12]} ({'added' if created else 'reused, clean'})")
    items = provision_inputs(plan_inputs(reader, order.example, cfg, wt), wt, cfg.inputs_cache)
    att.step("inputs", items=items)
    say(f"step inputs ok: {sum(i['status'] == 'COPIED' for i in items)} copied, "
        f"{sum(i['status'] in ('PRESENT', 'TRACKED') for i in items)} present")
    if worktree_clean(wt):
        raise LaunchError("WORKTREE_NOT_CLEAN", "after the input copy")
    env = run_env(cfg, wt, order.profile)
    cwd = wt / "factory/python"
    _guard(att, host, procs, cfg, say)
    # 4 stack lifecycle under the stack lock
    with held_stack_lock(cfg.stack_root) as lock_fd:
        att.step("stack_lock", lock=str(ST.lock_path(cfg.stack_root)))
        rc, out = host.stack(["stop"], env=env, cwd=cwd, log=att.logdir / "stack-stop.log", lock_fd=lock_fd)
        att.step("stack_stop", "OK" if rc == 0 else f"RC_{rc}", rc=rc, out=out.strip()[-300:])
        say(f"step stack_stop rc {rc}: {out.strip()[-160:]}")
        rep = sweep(cfg.stack_root, procs, uid=cfg.uid, kill=True, grace_s=cfg.sweep_grace_s, sleep=host.sleep)
        att.step("sweep", killed=rep["killed"], survivors=rep["survivors"],
                 orphans=[{k: c[k] for k in ("pid", "kind", "netns", "evidence", "storage_lock")}
                          for c in rep["candidates"] if not c["current"]])
        say(f"step sweep ok: {len(rep['killed'])} orphan(s) stopped {rep['killed']}")
        left, _h = survey(cfg.stack_root, procs, cfg.uid)
        locks = rep["storage_lock_holders"]
        if left or locks:
            raise LaunchError("STACK_STOP_INCOMPLETE", "; ".join(
                [f"{c['kind']} {c['pid']} still running" for c in left]
                + ([f"FABRO_STORAGE_LOCK_HELD by {locks}"] if locks else [])))
        rc, out = host.stack(["start"], env=env, cwd=cwd, log=att.logdir / "stack-start.log", lock_fd=lock_fd)
        js = _last_json(out) or {}
        if js.get("refused") == "STACK_LOCK_HELD":
            raise LaunchError("STACK_LOCK_HELD", "stack start refused by the stack lock")
        att.step("stack_start", "OK" if rc == 0 else "STACK_START_FAILED", rc=rc, out=out.strip()[-300:])
        if rc != 0:
            raise LaunchError("STACK_START_FAILED", f"rc {rc}: {out.strip()[-200:]}")
        say(f"step stack_start ok ({order.profile})")
        health = _healthy_wait(att, cfg, host, env, cwd)
        say(f"step stack_healthy ok: {health}")
        rc, out = host.stack(["--host-port", str(cfg.fabro_host_port), "expose-api"], env=env, cwd=cwd,
                             log=att.logdir / "expose.log")
        bridge = (_last_json(out) or {}).get("api_bridge")
        att.step("expose_api", "OK" if rc == 0 and bridge in ("UP", "already running") else "EXPOSE_FAILED",
                 rc=rc, api_bridge=bridge)
        if rc != 0 or bridge not in ("UP", "already running"):
            raise LaunchError("EXPOSE_FAILED", f"rc {rc} api_bridge {bridge}: {out.strip()[-200:]}")
        say(f"step expose_api ok: 127.0.0.1:{cfg.fabro_host_port}")
        _guard(att, host, procs, cfg, say)
        # 5 model swap smoke, exactly as the serve nodes run it (inside the stack namespace)
        for m in facts["smoke"]:
            t0 = host.monotonic()
            rc, out = host.stack(["exec", "--", "bash", "-c",
                                  'cd factory/python && exec python -m forge_factory.lrtx.stack serve --model "$1"',
                                  "serve", m], env=env, cwd=cwd, log=att.logdir / "smoke-serve.log")
            if rc != 0:
                att.step("smoke_serve", "SMOKE_FAIL", model=m, rc=rc, out=out.strip()[-300:])
                raise LaunchError("SMOKE_FAIL", f"serve {m} exited {rc}")
            host.sleep(3)
            rc2, out2 = host.stack(["exec", "--", "curl", "-s", "-m", "5",
                                    f"http://127.0.0.1:{facts['ports']['llama']}/v1/models"],
                                   env=env, cwd=cwd, log=att.logdir / "smoke-models.log")
            try:
                ids = [d["id"] for d in (_last_json(out2) or {}).get("data", [])]
            except (TypeError, KeyError):
                ids = None
            if ids != [m]:
                att.step("smoke_models", "SMOKE_FAIL", model=m, listed=ids)
                raise LaunchError("SMOKE_FAIL", f"after the serve command exited the server lists {ids}, expected {m}")
            att.step("smoke", model=m, seconds=round(host.monotonic() - t0, 1), listed=ids)
            say(f"step smoke ok: {m} served after the command exited")
        if not facts["smoke"]:
            att.step("smoke", "SKIPPED", reason="profile has no llama-server models")
        _guard(att, host, procs, cfg, say)
        # 6 launch: the work-order CLI inside the stack namespace
        rc, out = host.stack(["exec", "--", "bash", "-c",
                              'cd factory/python && exec python -m forge_factory.workorder "$@"', "workorder",
                              *order.workorder_args()], env=env, cwd=cwd, log=att.logdir / "workorder-launch.log")
    try:  # the M1 Line Conductor reads the work-order CLI's own output from this file
        (cfg.launch_dir / f"workorder-launch-{order.wo}.log").write_text(out)
    except OSError:
        pass
    js = _last_json(out) or {}
    rid = js.get("fabro_run_id")
    att.step("workorder_launch", "OK" if rc == 0 and rid else "WORKORDER_LAUNCH_FAILED", rc=rc,
             fabro_run_id=rid, status=js.get("status"), issues=(js.get("issues") or [])[:5])
    if rc != 0:
        raise LaunchError("WORKORDER_LAUNCH_FAILED", f"rc {rc}: {json.dumps(js) if js else out.strip()[-300:]}")
    if not rid:
        raise LaunchError("LAUNCH_NO_RUN_ID", out.strip()[-300:])
    say(f"LAUNCH {order.wo} rc 0: " + json.dumps({k: js.get(k) for k in ("work_order", "fabro_run_id", "workspace",
                                                                           "intake", "status")}))
    return _result(att, "LAUNCHED", fabro_run_id=rid, workspace=js.get("workspace"))


def _healthy_wait(att: Attempt, cfg: LineConfig, host, env: dict, cwd: Path) -> dict:
    deadline = host.monotonic() + cfg.health_timeout_s
    polls = 0
    while True:
        polls += 1
        rc, out = host.stack(["status"], env=env, cwd=cwd, log=att.logdir / "stack-status.log")
        st = _last_json(out) or {}
        health = st.get("health") if isinstance(st.get("health"), dict) else {}
        if rc == 0 and st.get("status") == "UP" and health and all(health.values()):
            att.step("stack_healthy", polls=polls, health=health)
            return health
        if host.monotonic() >= deadline:
            att.step("stack_healthy", "STACK_NOT_HEALTHY", polls=polls, status=st)
            raise LaunchError("STACK_NOT_HEALTHY", json.dumps(st)[:300])
        host.sleep(cfg.health_poll_s)


def _guard(att: Attempt, host, procs, cfg: LineConfig, say) -> None:
    if not cfg.guard:
        return
    cands, _h = survey(cfg.stack_root, procs, cfg.uid)
    own = next((c["pid"] for c in cands if c["kind"] == "llama_server" and c["current"]), None)
    g = host.guard(own)
    att.step("guard", "OK" if g == "OK" else "GUARD_FAIL", result=g[:200], own_llama_server=own)
    if g != "OK":
        raise LaunchError("GUARD_FAIL", f"{g[:200]} (own llama-server {own})")


def _plan(att: Attempt, cfg: LineConfig, order: Order, host, procs, say) -> dict:
    """Dry run: what a launch would do on this host now, from read-only probes only."""
    holders = sorted(flock_holders(cfg.gpu_lock))
    att.step("gpu_lock", "WOULD_REFUSE:GPU_LOCK_HELD" if holders else "FREE", holders=holders, lock=str(cfg.gpu_lock))
    say(f"plan gpu_lock: {cfg.gpu_lock} {'held by ' + str(holders) + ' -> would refuse GPU_LOCK_HELD' if holders else 'free'}")
    try:
        lr = live_runs(cfg, host, procs)
        att.step("run_live", "NONE", api=lr["api"], orphan_fabro=lr["orphan_fabro"])
        say(f"plan run_live: none (api {lr['api'].lower()})")
    except LaunchError as exc:
        att.step("run_live", f"WOULD_REFUSE:{exc.code}", detail=exc.detail)
        say(f"plan run_live: would refuse {exc.code}: {exc.detail[:200]}")
    sha = resolve_rev(cfg.repo, order.rev)
    att.sha = sha
    reader = RevReader(cfg.repo, sha)
    facts = profile_facts(reader, order.profile)
    say(f"plan revision: {order.rev} -> {sha} (profile ports {facts['ports']}, smoke order {facts['smoke']})")
    wt = cfg.runs_root / order.wo
    state = "would add" if not wt.exists() else "exists (re-attempt check: same revision, never launched, clean)"
    att.step("worktree", "PLANNED", path=str(wt), action=state)
    say(f"plan worktree: git -C {cfg.repo} worktree add --detach {wt} {sha[:12]}  [{state}]")
    try:
        items = plan_inputs(reader, order.example, cfg, wt if wt.is_dir() else None)
        att.step("inputs", "PLANNED", items=items)
        for i in items:
            say(f"plan input: {i['path']} {i['status']}" + (f" from {i['source']} {i['from']} (sha256 {i['sha256'][:16]})"
                                                           if i["status"] == "COPY" else ""))
    except LaunchError as exc:
        att.step("inputs", f"WOULD_FAIL:{exc.code}", detail=exc.detail)
        say(f"plan inputs: would fail {exc.code}: {exc.detail}")
    rep = sweep(cfg.stack_root, procs, uid=cfg.uid, kill=False)
    att.step("sweep", "PLANNED", live_holder=rep["live_holder"], live_netns=rep["live_netns"],
             current=[(c["pid"], c["kind"]) for c in rep["candidates"] if c["current"]],
             orphans=[(c["pid"], c["kind"], c["netns"]) for c in rep["candidates"] if not c["current"]],
             storage_lock_holders=rep["storage_lock_holders"])
    say(f"plan stack: lock {ST.lock_path(cfg.stack_root)}; stop the live stack (holder {rep['live_holder']}, "
        f"{sum(c['current'] for c in rep['candidates'])} process(es)); sweep orphans now "
        f"{[(c['pid'], c['kind']) for c in rep['candidates'] if not c['current']]}; Fabro storage lock held by "
        f"{rep['storage_lock_holders']}")
    py = f"{cfg.python} -m forge_factory.lrtx.stack"
    for line in (f"{py} stop", f"{py} start", f"{py} status  (every {cfg.health_poll_s:g} s, up to {cfg.health_timeout_s:g} s)",
                 f"{py} --host-port {cfg.fabro_host_port} expose-api",
                 *[f"{py} exec -- ... stack serve --model {m}; curl :{facts['ports'].get('llama')}/v1/models == ['{m}']"
                   for m in facts["smoke"]],
                 f"{py} exec -- bash -c 'cd factory/python && exec python -m forge_factory.workorder' "
                 + " ".join(shlex.quote(a) for a in order.workorder_args())):
        say(f"plan run [cwd {wt}/factory/python, FORGE_REPO_ROOT={wt}]: {line}")
    att.step("launch", "PLANNED", workorder_args=order.workorder_args(), guard=list(cfg.guard))
    if cfg.guard:
        say(f"plan guard: {' '.join(cfg.guard)} <own llama-server pid> before stop, after expose, before launch")
    return _result(att, "PLANNED", plan=att.steps)


# ---------------------------------------------------------------------------------------------------------- status
def status(cfg: LineConfig, host=None, procs=None) -> dict:
    host = host or ShellHost(cfg)
    procs = procs or ProcFS()
    out = {"gpu_lock_holders": sorted(flock_holders(cfg.gpu_lock)),
           "stack_lock_holders": sorted(flock_holders(ST.lock_path(cfg.stack_root)))}
    try:
        runs = host.fabro_runs()
        prefix = str(cfg.stack_root).rstrip("/") + "/state/"
        out["live_runs"] = [r.get("id") for r in runs if _kind(r) in LIVE_KINDS
                            and str(r.get("source_directory", "")).startswith(prefix)]
        out["api"] = "UP"
    except FabroUnavailable as exc:
        out["api"] = f"UNREACHABLE:{exc}"
    rep = sweep(cfg.stack_root, procs, uid=cfg.uid, kill=False)
    out["stack"] = {"live_holder": rep["live_holder"], "live_netns": rep["live_netns"],
                    "current": [(c["pid"], c["kind"]) for c in rep["candidates"] if c["current"]],
                    "orphans": [(c["pid"], c["kind"], c["netns"]) for c in rep["candidates"] if not c["current"]],
                    "storage_lock_holders": rep["storage_lock_holders"]}
    return out


# ---------------------------------------------------------------------------------------------------------- CLI
def _printer(cfg: LineConfig, echo: bool = True):
    def say(text: str) -> None:
        line = f"{utc_now()[:19]}Z {text}"  # the bash launcher's `date -u +%FT%TZ` prefix
        if echo:
            print(line, flush=True)
        if cfg.log is not None:
            try:
                with cfg.log.open("a") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass
    return say


def _cfg_from_args(a) -> LineConfig:
    return LineConfig.from_env(launch_dir=a.launch_dir, repo=a.repo, stack_root=a.stack_root, runs_root=a.runs_root,
                               gpu_lock=a.gpu_lock, python=a.python, fabro_bin=a.fabro_bin, fabro_host_port=a.fabro_port,
                               inputs_cache=a.inputs_cache, references=a.reference, guard=a.guard, log=not a.no_log)


def main(argv: list[str] | None = None, *, host=None, procs=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m forge_factory.afo.line_launcher", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    for opt in ("--launch-dir", "--repo", "--stack-root", "--runs-root", "--gpu-lock", "--python", "--fabro-bin",
                "--inputs-cache", "--guard"):
        common.add_argument(opt, default=None)
    common.add_argument("--fabro-port", type=int, default=None)
    common.add_argument("--reference", action="append", default=None, help="read-only source of ignored inputs")
    common.add_argument("--no-log", action="store_true", help="do not append to <launch-dir>/launch.log")
    sub = ap.add_subparsers(dest="cmd", required=True)
    la = sub.add_parser("launch", parents=[common], help="one launch attempt (drop-in for launch-generic-model.sh)")
    la.add_argument("rev")
    la.add_argument("wo")
    la.add_argument("example")
    la.add_argument("profile")
    la.add_argument("extra", nargs="?", default="", help='the ladders\' EXTRA string, e.g. "--stop-after SWE.1"')
    la.add_argument("run_model", nargs="?", default=None, help="the run (native-node) model, as the bash 6th arg")
    la.add_argument("--model", default=None)
    for flag, name in EXTRA_FLAGS.items():
        la.add_argument(flag, dest=name, default=None)
    la.add_argument("--purpose", default="ASPICE_ONLY")
    la.add_argument("--dry-run", action="store_true")
    la.add_argument("--json", action="store_true", help="print the result JSON as the last line")
    st = sub.add_parser("status", parents=[common], help="read-only: locks, live runs, stack processes, verdict")
    st.add_argument("--wo")
    st.add_argument("--phase", choices=PHASES)
    st.add_argument("--run-id")
    sw = sub.add_parser("sweep", parents=[common], help="list orphans of this stack root; --kill stops them")
    sw.add_argument("--kill", action="store_true")
    wa = sub.add_parser("wait", parents=[common], help="wait for a Fabro run's end, then print the phase verdict")
    wa.add_argument("--run-id", required=True)
    wa.add_argument("--wo")
    wa.add_argument("--phase", choices=PHASES)
    wa.add_argument("--poll", type=float, default=30.0)
    wa.add_argument("--timeout", type=float, default=None)
    a = ap.parse_args(argv)
    cfg = _cfg_from_args(a)
    host = host or ShellHost(cfg)
    if a.cmd == "launch":
        say = _printer(cfg)
        try:
            kw = parse_extra(a.extra)
            for name in EXTRA_FLAGS.values():
                v = getattr(a, name)
                if v is not None:
                    kw[name] = float(v) if name == "timeout_scale" else v
            model = a.model or a.run_model
            if not model:
                raise LaunchError("ORDER_ARGS_INVALID", "run model missing (6th argument or --model)")
            order = Order(wo=a.wo, rev=a.rev, example=a.example, profile=a.profile, model=model,
                          purpose=a.purpose, **kw)
            order.validate()
        except LaunchError as exc:
            dummy = Order(wo=a.wo, rev=a.rev, example=a.example, profile=a.profile, model=a.model or a.run_model or "-")
            say(legacy_line(exc.code, exc.detail, dummy))
            return 2
        say(f"line-launcher start wo={order.wo} rev={order.rev} example={order.example} profile={order.profile} "
            f"model={order.model}{' (dry run)' if a.dry_run else ''}")
        res = launch(order, cfg, host=host, procs=procs, say=say, dry_run=a.dry_run)
        say(f"line-launcher end outcome={res['outcome'].lower()} class={res['class'].lower()} "
            f"attempt={res['attempt']} transcript={res.get('transcript')}")
        if a.json:
            print(json.dumps({k: v for k, v in res.items() if k != "plan"}, default=str))
        if res["outcome"] in ("LAUNCHED", "PLANNED"):
            return 0
        return GPU_LOCK_EXIT if res["outcome"] == "GPU_LOCK_HELD" else (3 if res["class"] == "REFUSED" else 1)
    if a.cmd == "status":
        out = status(cfg, host, procs)
        if a.run_id:
            try:
                out["run"] = {"id": a.run_id, "status": _kind(host.fabro_run(a.run_id))}
            except FabroUnavailable as exc:
                out["run"] = {"id": a.run_id, "status": None, "api": f"UNREACHABLE:{exc}"}
        if a.wo and a.phase:
            out["verdict"] = order_verdict(cfg, a.wo, a.phase)
        print(json.dumps(out, default=str))
        return 0
    if a.cmd == "sweep":
        if not a.kill:
            print(json.dumps(sweep(cfg.stack_root, procs, uid=cfg.uid, kill=False), default=str))
            return 0
        try:  # killing orphans needs the launch lock, the stack lock and no live run (never under a running launch)
            rep = safe_sweep(cfg, host, procs)
        except LaunchError as exc:
            print(json.dumps({"refused": exc.code, "detail": exc.detail}))
            return GPU_LOCK_EXIT if exc.code == "GPU_LOCK_HELD" else 3
        print(json.dumps(rep, default=str))
        return 0 if not rep["survivors"] else 1
    if a.cmd == "wait":
        w = wait_for_end(a.run_id, host, poll_s=a.poll, timeout_s=a.timeout)
        print(f"{a.wo or a.run_id} ended: {w['status']} at {utc_now()}" if w["ended"]
              else f"{a.wo or a.run_id} not ended: {w['status']} (timeout)", flush=True)
        if a.wo and a.phase:
            print(json.dumps(order_verdict(cfg, a.wo, a.phase)))
        return 0 if w["ended"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
