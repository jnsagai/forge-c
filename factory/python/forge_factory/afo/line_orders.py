"""Autonomous line M3 (owner 2026-11-03, decisions 3/4/5/12/14/15) - the Line Conductor places and continues orders.

ACT mode of the Line Conductor. Each cycle it plans every lineage of the owner-approved campaign files
(`afo.line_campaign`) from the line's own records, then - only with a valid owner-signed PILOT grant - executes at most
one step: it places the next phase order through the M2 line launcher (one GPU run at a time), follows the run with
`wait_for_end` and `order_verdict`, and chains the next phase (`--resume-from` the passed order, same revision,
`--provided-from` where needed). Without a valid grant ACT refuses and the conductor stays OBSERVE.

Records (restart-safe; a restart never double-launches):
  * the line queue: the AFO queue store (`afo.queue.Store`) at $FORGE_STATE_DIR/supervisor/line-queue.sqlite3, one
    order per phase order (request_id = the work-order name, manifest = the campaign file and its sha256,
    payload_digest = the order spec's sha256), its attempts (one per launch) and outbox commands;
  * the order spec $FORGE_STATE_DIR/supervisor/line-orders/<WO>.json (written before the queue submit);
  * the launcher's own transcripts (<runs>/<WO>/.forge-run/launch/attempt-N.json) and launch-<WO>.out records, the
    work-order workspaces (state/workorders/<WO>) and the Fabro run status.
A live run whose name belongs to a lineage (e.g. launched by the loop10 ladders) is adopted, never relaunched.

Owner retry rule (decision 14): retries are unlimited while the lineage progresses (a PASS or a new fingerprint); the
SAME fingerprint more than 3 times in a row on one lineage phase stops that lineage (ESCALATED, NEEDS_OWNER, a GitHub
issue) and the other lineages go on. Every retry resumes from the last good, quality-checked part. Per class:
  INFRA / INFRA_UNAVAILABLE  orphan sweep, then relaunch with backoff inside the pacing guards;
  MODEL_CONVERGENCE / PRODUCT without an upstream defect / UNKNOWN   retry the phase from the last passed order;
  FACTORY_DEFECT             WAITING_EXTERNAL_CHANGE, no loop; resumes when the campaign names a newer factory_revision;
  PRODUCT with an upstream defect   resume the owning upstream phase from the failed order (the defect route);
  a cancelled run            PARKED until the owner changes the lineage.
Never: a weakened gate, a changed requirement/checklist/budget, a merge or a promotion (decision 4: only the run-branch
revisions the campaign names). Quality (decision 15): the campaign's quality block goes into the order; a phase that
passes below the target but at or above the minimum is accepted and its gap is recorded in the feed.
Disk (decision 12): no placement below 30 GB free (escalated); only the conductor's own run worktrees and pytest temps
older than 3 days, after the order finished and was archived, are cleaned. M3 makes no model call.

    python -m forge_factory.afo.line_orders plan [--dry-run] [--campaigns DIR] [--fabro-snapshot F] [--json]
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, load_yaml, sha256_bytes, state_dir
from . import line_campaign as LCMP

POLICY_PATH = REPO_ROOT / "config/factory/line-policy.yaml"
POLICY_SCHEMA = "forge-c/line-policy/1"
ORDER_SCHEMA = "forge-c/line-order/1"
PHASES = LCMP.PHASES
STRIKE_LIMIT = 3  # owner rule 2026-11-03 (binding): the same issue more than 3 times stops the lineage
FLOOR = {"same_issue_limit": 3, "min_free_gb": 30, "cleanup_min_age_days": 3, "max_concurrent_gpu_runs": 1}
STATES = ("QUEUED", "CHAINED", "LAUNCHING", "RUNNING", "WAITING", "ESCALATED", "PARKED", "ON_HOLD", "DONE")
LAUNCH_ACTIONS = ("PLACE", "RELAUNCH", "LAUNCH")
RETRY_KINDS = ("RETRY", "RETRY_INFRA", "UPSTREAM", "RELAUNCH", "RELAUNCH_INFRA")
GB = 1024 ** 3


def _utc(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _ts(s) -> float | None:
    from .line_conductor import _ts as ts

    return ts(s)


def _load(p: Path):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def _atomic(p: Path, obj) -> None:
    from .line_conductor import atomic_write

    atomic_write(p, json.dumps(obj, indent=1, sort_keys=True, default=str).encode() + b"\n")


def _fp(*parts) -> str:
    return "sup1-" + sha256_bytes("|".join(map(str, parts)).encode())[:40]


def supervisor_dir() -> Path:
    return state_dir() / "supervisor"


# ------------------------------------------------------------------------------------------------------ the policy
@dataclass
class LinePolicy:
    raw: dict | None
    sha256: str | None
    issues: list[str]
    path: Path

    def get(self, dotted: str, default=None):
        node = self.raw or {}
        for k in dotted.split("."):
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node


def load_policy(path: Path | None = None) -> LinePolicy:
    """The line policy (owner-controlled; the PILOT grant is bound to its sha256). Values below the code floor are
    refused, never applied: the owner rules are not weakened by a policy edit."""
    p = Path(path or os.environ.get("FORGE_LINE_POLICY") or POLICY_PATH)
    try:
        raw = load_yaml(p)
    except Exception as exc:  # noqa: BLE001 - an unreadable policy disables ACT, never raises
        return LinePolicy(None, None, [f"POLICY_UNREADABLE:{type(exc).__name__}"], p)
    if not isinstance(raw, dict):
        return LinePolicy(None, None, ["POLICY_ABSENT"], p)
    sha = sha256_bytes(canonical_json(raw))
    issues = [] if raw.get("schema") == POLICY_SCHEMA else ["POLICY_SCHEMA_ID"]
    pol = LinePolicy(raw, sha, issues, p)
    if pol.get("mode") not in ("OBSERVE", "PILOT"):
        issues.append("POLICY_MODE")
    if pol.get("owner_rules.same_issue_limit") != FLOOR["same_issue_limit"]:
        issues.append("FLOOR:same_issue_limit")
    if not isinstance(pol.get("disk.min_free_gb"), (int, float)) or pol.get("disk.min_free_gb") < FLOOR["min_free_gb"]:
        issues.append("FLOOR:min_free_gb")
    if not isinstance(pol.get("disk.cleanup_min_age_days"), (int, float)) or \
            pol.get("disk.cleanup_min_age_days") < FLOOR["cleanup_min_age_days"]:
        issues.append("FLOOR:cleanup_min_age_days")
    if pol.get("pacing.max_concurrent_gpu_runs") != FLOOR["max_concurrent_gpu_runs"]:
        issues.append("FLOOR:max_concurrent_gpu_runs")
    for k in ("never.merge", "never.promote", "never.weaken_gate", "never.edit_requirements"):
        if pol.get(k) is not True:
            issues.append(f"FLOOR:{k}")
    if pol.get("escalation.mentions") is not False:
        issues.append("FLOOR:escalation.mentions")
    return pol


# ------------------------------------------------------------------------------------------------- authorization
@dataclass
class Grant:
    """The PILOT grant as verified this cycle (afo.authz: signature, mode, expiry, policy hash, revocation)."""
    allow: bool
    code: str
    reason: str
    authorization_id: str | None
    expires_utc: str | None
    policy: LinePolicy
    base: Path | None = None
    now: float | None = None
    allowed_signers: Path | None = None

    def permit(self, action: str, request: dict | None = None):
        """The grant's decision for one action and request (driver_class, model, service_action)."""
        from datetime import UTC, datetime

        from . import authz

        if not self.allow:
            return authz.AuthDecision(False, self.code, self.reason, self.authorization_id)
        kw = {"allowed_signers": self.allowed_signers} if self.allowed_signers else {}
        return authz.find("PILOT", self.policy.sha256 or "", base=self.base, ref=self.policy.get("authorization_ref"),
                          action=action, request=request or {},
                          now=datetime.fromtimestamp(self.now or time.time(), UTC), **kw)

    def view(self) -> dict:
        return {"authorization_id": self.authorization_id, "code": self.code, "expires_at": self.expires_utc,
                "policy_sha256": self.policy.sha256}


def verify_grant(policy: LinePolicy, *, now: float, base: Path | None = None,
                 allowed_signers: Path | None = None) -> Grant:
    from datetime import UTC, datetime

    from . import authz

    base = base or authz.AUTH_DIR
    if policy.issues:
        return Grant(False, "LINE_POLICY_INVALID", ";".join(policy.issues)[:200], None, None, policy, base, now,
                     allowed_signers)
    if policy.get("mode") != "PILOT":
        return Grant(False, "LINE_POLICY_MODE_OBSERVE", "the line policy requests OBSERVE", None, None, policy, base,
                     now, allowed_signers)
    kw = {"allowed_signers": allowed_signers} if allowed_signers else {}
    d = authz.find("PILOT", policy.sha256 or "", base=base, ref=policy.get("authorization_ref"),
                   now=datetime.fromtimestamp(now, UTC), **kw)
    rec = _load(base / f"{policy.get('authorization_ref')}.json") if policy.get("authorization_ref") else None
    return Grant(d.allow, d.code, d.reason, d.authorization_id, (rec or {}).get("expires_utc") if isinstance(rec, dict)
                 else None, policy, base, now, allowed_signers)


# ------------------------------------------------------------------------------------------------------ the line
class RealLine:
    """The real line: the M2 launcher (as a subprocess, so a launch outlives a conductor cycle and its restart), the
    line's Fabro API (M2 `wait_for_end`, one poll), the phase verdict (M2 `order_verdict`), the orphan sweep (M2
    `safe_sweep`), git objects of the line repo, the host's disk and `gh` for owner escalations."""

    def __init__(self, cfg=None, *, fabro_snapshot: dict | None = None, launch_python: str | None = None,
                 launch_cwd: Path | None = None, gh: str = "gh", pytest_roots: list[Path] | None = None):
        from . import line_launcher as LL

        self.LL = LL
        self.cfg = cfg or LL.LineConfig.from_env()
        self.snapshot = fabro_snapshot
        self.host = _SnapshotHost(fabro_snapshot) if fabro_snapshot is not None else LL.ShellHost(self.cfg)
        self.python = launch_python or sys.executable
        self.cwd = launch_cwd or (REPO_ROOT / "factory/python")
        self.gh_bin = gh
        self.pytest_roots = pytest_roots if pytest_roots is not None else _default_pytest_roots()
        self._rev: dict = {}
        if (self.cfg.stack_root / "state").resolve() != state_dir().resolve():
            raise ValueError(f"LINE_STATE_MISMATCH: FORGE_STATE_DIR {state_dir()} is not the launcher's stack state "
                             f"{self.cfg.stack_root / 'state'}")

    # records ----------------------------------------------------------------------------------------------------
    @property
    def state_root(self) -> Path:
        return state_dir()

    def workspace(self, wo: str) -> Path:
        return self.state_root / "workorders" / wo / "workspace"

    def transcripts(self, wo: str) -> list[dict]:
        return self.LL.prior_attempts(self.cfg, wo)

    def launch_dir(self) -> Path:
        return self.cfg.launch_dir

    # Fabro ------------------------------------------------------------------------------------------------------
    def run_status(self, run_id: str) -> str | None:
        """'kind' or 'kind:reason' from one non-blocking `wait_for_end` poll; None when Fabro does not answer."""
        w = self.LL.wait_for_end(run_id, self.host, poll_s=0, timeout_s=0, sleep=lambda _s: None,
                                 monotonic=time.monotonic)
        if w["status"] is None:
            return None
        return f"{w['status']}:{w['reason']}" if w.get("reason") else str(w["status"])

    def ended_run(self, wo: str, run_id: str) -> bool:
        """Authoritative terminal evidence bound to this exact own workspace and Fabro run."""
        try:
            run = self.host.fabro_run(run_id)
        except self.LL.FabroUnavailable:
            return False
        return (run.get("id") == run_id and run.get("source_directory") == str(self.workspace(wo))
                and self.LL._kind(run) in self.LL.ENDED_KINDS)

    def completed_run(self, run_id: str, workspace: Path) -> bool:
        """Identity-bound native completion for the narrow independent upstream-review classifier."""
        if not workspace.is_relative_to(self.state_root / "workorders"):
            return False
        try:
            run = self.host.fabro_run(run_id)
        except self.LL.FabroUnavailable:
            return False
        if not isinstance(run, dict) or not isinstance(run.get("lifecycle"), dict):
            return False
        status = run["lifecycle"].get("status") or {}
        return (run.get("id") == run_id and run.get("source_directory") == str(workspace)
                and isinstance(status, dict) and status.get("kind") == "succeeded" and status.get("reason") == "completed")

    def live_runs(self) -> list[str] | None:
        """Live Forge-C runs of this stack root; None when the API does not answer (fail closed: busy)."""
        try:
            runs = self.host.fabro_runs()
        except self.LL.FabroUnavailable:
            return None
        # Admission occupies this canonical server, including foreign/unknown
        # source directories. Exact own-native identity is checked at handoff.
        return [r["id"] for r in runs if self.LL._kind(r) in self.LL.LIVE_KINDS]

    def verdict(self, wo: str, phase: str) -> dict:
        return self.LL.order_verdict(self.cfg, wo, phase)

    def gpu_holders(self) -> list[int]:
        return sorted(self.LL.flock_holders(self.cfg.gpu_lock))

    # git --------------------------------------------------------------------------------------------------------
    def resolve(self, rev: str | None) -> str | None:
        if not rev:
            return None
        if rev not in self._rev:
            try:
                self._rev[rev] = self.LL.resolve_rev(self.cfg.repo, rev)
            except self.LL.LaunchError:
                self._rev[rev] = None
        return self._rev[rev]

    def spec_quality(self, sha: str, example: str) -> tuple[bool, dict | None]:
        """(spec readable, the example's quality block at the revision)."""
        raw = self.LL.RevReader(self.cfg.repo, sha).read(f"examples/{example}/workorder.json")
        if raw is None:
            return False, None
        try:
            return True, json.loads(raw).get("quality")
        except ValueError:
            return False, None

    def quality_supported(self, sha: str) -> bool:
        return self.LL.quality_supported(self.LL.RevReader(self.cfg.repo, sha))

    # actions ----------------------------------------------------------------------------------------------------
    def spawn_launch(self, argv: list[str], wo: str) -> dict:
        """Start `python -m forge_factory.afo.line_launcher launch ...` detached; its marker lines go to the launch
        record launch-<WO>.out that the M1 conductor reads."""
        out = self.cfg.launch_dir / f"launch-{wo}.out"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "ab") as fh:
            p = subprocess.Popen([self.python, "-m", "forge_factory.afo.line_launcher", *argv], cwd=self.cwd,
                                 stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
        return {"pid": p.pid, "start": _proc_start(p.pid)}

    def spawn_recovery_worker(self, command_id: str, wo: str, *, quiesce=False) -> dict:
        """Only spawn the external bounded worker. Source preparation/serving never runs in the cycle."""
        out = self.cfg.launch_dir / f"recovery-{wo}.out"
        out.parent.mkdir(parents=True, exist_ok=True)
        from .line_recovery_worker import config_environment

        env = {**os.environ, **config_environment(self.cfg), "FORGE_STATE_DIR": str(self.cfg.stack_root / "state")}
        with out.open("ab") as fh:
            p = subprocess.Popen([self.python, "-m", "forge_factory.afo.line_recovery_worker", "bootstrap",
                                  "--command", command_id, *(["--quiesce"] if quiesce else [])], cwd=self.cwd,
                                 stdin=subprocess.DEVNULL,
                                 stdout=fh, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        return {"pid": p.pid, "start": _proc_start(p.pid)}

    def alive(self, pid: int, start: str | None) -> bool:
        return pid > 0 and _proc_start(pid) == start and start is not None

    def sweep(self) -> dict:
        try:
            from .line_liveness import clear

            clear(self.cfg)
            return {"ok": True, **self.LL.safe_sweep(self.cfg, self.host if self.snapshot is None else None)}
        except self.LL.LaunchError as exc:
            return {"ok": False, "refused": exc.code, "detail": exc.detail[:200]}
        except ValueError as exc:
            return {"ok": False, "refused": getattr(exc, "code", "DURABLE_LIVENESS_UNKNOWN")}

    def free_bytes(self) -> int:
        st = os.statvfs(self.state_root if self.state_root.exists() else self.cfg.launch_dir)
        return st.f_bavail * st.f_frsize

    def run_worktree(self, wo: str) -> Path:
        return self.cfg.runs_root / wo

    def remove_worktree(self, wo: str) -> bool:
        from .durable import Refused
        from .line_liveness import clear

        try:
            clear(self.cfg)
        except Refused:
            return False
        wt = self.run_worktree(wo)
        if not wt.is_dir():
            return False
        keep = self.cfg.runs_root / ".launch" / wo / "kept"
        src = wt / ".forge-run/launch"
        if src.is_dir():  # the launch transcripts outlive the worktree
            keep.mkdir(parents=True, exist_ok=True)
            for f in src.glob("attempt-*.json"):
                shutil.copy2(f, keep / f.name)
        p = subprocess.run(["git", "-C", str(self.cfg.repo), "worktree", "remove", "--force", str(wt)],
                           capture_output=True, timeout=120)
        return p.returncode == 0

    def gh(self, argv: list[str]) -> tuple[int, str]:
        p = subprocess.run([self.gh_bin, *argv], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout or p.stderr).strip()[-300:]


class _SnapshotHost:
    """Offline replay: Fabro answers from a recorded {run_id: 'kind[:reason]'} snapshot."""

    def __init__(self, snapshot: dict):
        self.snapshot = snapshot

    def fabro_run(self, run_id: str) -> dict:
        s = self.snapshot.get(run_id)
        if s is None:
            from .line_launcher import FabroUnavailable

            raise FabroUnavailable("NOT_IN_SNAPSHOT")
        kind, _, reason = str(s).partition(":")
        return {"lifecycle": {"status": {"kind": kind, **({"reason": reason} if reason else {})}}}

    def fabro_runs(self) -> list[dict]:
        return []  # a replay has no live run besides those of its snapshot (read per order)

    sleep = staticmethod(lambda _s: None)
    monotonic = staticmethod(time.monotonic)


def _proc_start(pid: int) -> str | None:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def _default_pytest_roots() -> list[Path]:
    import getpass
    import tempfile

    return [Path(tempfile.gettempdir()) / f"pytest-of-{getpass.getuser()}"]


# ---------------------------------------------------------------------------------------------------- the records
@dataclass
class Att:
    """One phase order (one work-order name) of a lineage, as its records show it."""
    wo: str
    phase: str
    n: int
    created: float | None = None
    spec: dict | None = None        # line-orders/<WO>.json (placed or adopted by M3)
    queue: dict | None = None       # the line queue's order row
    rid: str | None = None
    pkg: dict | None = None
    rec: dict | None = None         # M1 order record of the workspace
    launching: bool = False
    launches: list[dict] = field(default_factory=list)  # failed launch attempts [{at, code, class}]
    life: str | None = None
    status: str = "NONE"            # NONE QUEUED LAUNCHING LAUNCH_FAILED RUNNING ENDED
    verdict: str | None = None      # PASS NO INFRA_UNAVAILABLE
    core: dict | None = None        # M1 classification of an ended order that did not pass
    ended_at: float | None = None

    @property
    def lineage_sha(self) -> str | None:
        return (self.spec or {}).get("lineage_sha")

    @property
    def revision(self) -> str | None:
        return (self.rec or {}).get("revision") or (self.spec or {}).get("revision")


def launch_fp(phase: str, code: str) -> str:
    from ..reliability.taxonomy import fingerprint

    return fingerprint("INFRASTRUCTURE", "line-launcher", code, f"{phase}/launch")


class Records:
    """Everything the planner reads in one cycle (read-only)."""

    def __init__(self, line, queue_path: Path, now: float, capa_of: dict | None = None):
        from .line_conductor import scan_launches

        self.line, self.now = line, now
        self.queue_rows = _queue_rows(queue_path)
        self.legacy = {la["wo"]: la for la in scan_launches(line.launch_dir(), now, float("inf"))}
        self.capa_of = capa_of or {}
        self.cre_db: Path | None = None
        self.orders_dir = supervisor_dir() / "line-orders"
        self.launching_dir = supervisor_dir() / "launching"
        self._cache: dict = {}

    def exists(self, wo: str) -> bool:
        return (wo in self.queue_rows or (self.orders_dir / f"{wo}.json").is_file()
                or self.line.workspace(wo).joinpath(".forge-run/manifest.json").is_file()
                or bool(self.line.transcripts(wo)) or wo in self.legacy)

    def attempt(self, wo: str, phase: str, n: int) -> Att:
        if wo in self._cache:
            return self._cache[wo]
        from .line_conductor import classify_order, order_rec

        a = Att(wo, phase, n)
        a.spec = _load(self.orders_dir / f"{wo}.json")
        a.queue = self.queue_rows.get(wo)
        ws = self.line.workspace(wo)
        a.rec = order_rec(ws) if ws.is_dir() else None
        if a.rec:
            a.rid, a.pkg, a.created = a.rec["rid"], a.rec["package"], a.rec["created"]
        if a.created is None and a.spec:
            a.created = _ts(a.spec.get("placed_at"))
        la = _load(self.launching_dir / f"{wo}.json")
        a.launching = bool(la) and self.line.alive(int(la.get("pid") or 0), la.get("start"))
        from .line_launcher import CODES

        for t in self.line.transcripts(wo):
            out = t.get("outcome")
            if out in ("LAUNCHED", "PLANNED"):
                continue
            a.launches.append({"at": _ts(t.get("ended_at")) or _ts(t.get("started_at")) or 0.0, "code": str(out),
                               "class": t.get("class") or CODES.get(str(out), "INFRA"), "attempt": t.get("attempt")})
        if not a.launches and a.rid is None and wo in self.legacy:  # a bash-launcher failure (before M2/M3)
            lg = self.legacy[wo]
            cls = "REFUSED" if lg["code"] in ("GPU_LOCK_HELD", "RUN_LIVE") else \
                "INFRA" if lg["code"] in ("STACK_STOP_INCOMPLETE", "READINESS_FAILURE", "STACK_START_FAILED",
                                          "MODEL_SMOKE_FAILED") else "WORKORDER"
            a.launches.append({"at": lg["created"], "code": lg["code"], "class": cls, "attempt": None})
        if la and not la.get("durable_worker") and not a.launching and not a.rid and not any(
                x["at"] >= (_ts(la.get("at")) or 0) for x in a.launches):
            # the launcher ended without a transcript (killed): a launch that never reached Fabro
            a.launches.append({"at": _ts(la.get("at")) or self.now, "code": "LAUNCHER_INTERRUPTED", "class": "INFRA",
                               "attempt": None})
        a.launches.sort(key=lambda x: x["at"])
        if a.created is None and a.launches:
            a.created = a.launches[0]["at"]
        if a.rid:
            a.life = None if a.pkg is not None else self.line.run_status(a.rid)
            kind = (a.life or "").split(":")[0]
            from .line_launcher import ENDED_KINDS

            if a.pkg is not None or kind in ENDED_KINDS:
                a.status = "ENDED"
                a.verdict = self.line.verdict(wo, phase)["verdict"]
                ts = [t for t in (_ts(e.get("ts")) for e in (a.rec or {}).get("log") or []) if t]
                a.ended_at = max(ts) if ts else (max(a.rec["sig"][0]) if a.rec and a.rec["sig"][0] else a.created)
                if a.verdict == "NO":
                    try:
                        a.core = classify_order(a.rec, a.life, self.capa_of,
                                              completed_run=getattr(self.line, "completed_run", None)) if a.rec else None
                    except Exception as exc:  # noqa: BLE001 - an unreadable record is UNKNOWN, never a guessed class
                        a.core = {"class": "UNKNOWN", "error_code": f"CLASSIFIER_ERROR:{type(exc).__name__}",
                                  "fingerprint": _fp("CLASSIFIER_ERROR", wo), "route": "ENDED", "upstream": []}
                    if a.core is None:
                        a.core = {"class": "UNKNOWN", "error_code": "ENDED_BEFORE_TARGET_PHASE", "route": "ENDED",
                                  "fingerprint": _fp("ENDED_BEFORE_TARGET_PHASE", phase), "upstream": []}
            else:
                a.status = "RUNNING"  # live, or Fabro does not answer: never relaunched (fail closed)
        elif a.launching:
            a.status = "LAUNCHING"
        elif a.launches and (not a.queue or a.queue["state"] in ("ADMITTED", "PAUSED") or
                             a.launches[-1]["at"] >= (_ts((a.spec or {}).get("placed_at")) or 0)):
            a.status = "LAUNCH_FAILED"
        elif a.queue and a.queue["state"] in ("BLOCKED", "READY_FOR_OFFLINE_REVIEW", "REJECTED_INTAKE"):
            a.status = "CLOSED"  # closed without a run (superseded by a campaign change): history, never launched
        elif a.spec and a.spec.get("kind") != "ADOPTED":
            a.status = "QUEUED"  # placed (spec written, maybe queued and admitted) and never launched
        elif a.rec is not None:  # a prepared workspace without a run and without a launch record
            a.launches.append({"at": a.created or self.now, "code": "PREPARED_WITHOUT_RUN", "class": "WORKORDER",
                               "attempt": None})
            a.status = "LAUNCH_FAILED"
        self._cache[wo] = a
        return a

    def phase_attempts(self, L: LCMP.Lineage, phase: str) -> list[Att]:
        out, n, misses = [], 1, 0
        while misses < 3 and n < 200:  # names are dense; tolerate gaps of 2
            wo = L.wo(phase, n)
            if self.exists(wo):
                out.append(self.attempt(wo, phase, n))
                misses = 0
            else:
                misses += 1
            n += 1
        return out


def _queue_rows(path: Path) -> dict:
    import sqlite3

    if not path.is_file():
        return {}
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return {}
    try:
        rows = c.execute("SELECT order_id, request_id, state, envelope, terminal_reason, authorization_id, policy_sha256 "
                         "FROM afo_work_orders").fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        c.close()
    return {r[1]: {"order_id": r[0], "state": r[2], "envelope": json.loads(r[3]), "terminal_reason": r[4],
                   "authorization_id": r[5], "policy_sha256": r[6]} for r in rows}


# ------------------------------------------------------------------------------------------------------ the planner
def _events(atts: list[Att], sha: str) -> list[tuple]:
    """(t, fingerprint, class, code) of one lineage phase in time order; refused launches (the line was busy) are
    not issues; attempts placed under another version of the lineage block are history only (the owner changed it)."""
    ev = []
    for a in atts:
        if a.lineage_sha not in (None, sha):
            continue
        for x in a.launches:
            if x["class"] != "REFUSED":
                ev.append((x["at"], launch_fp(a.phase, x["code"]), "INFRA" if x["class"] == "INFRA" else "LAUNCH",
                           x["code"]))
        if a.status == "ENDED":
            t = a.ended_at or a.created or 0
            if a.verdict == "PASS":
                ev.append((t, "PASS", "PASS", "PASS"))
            elif a.verdict == "INFRA_UNAVAILABLE":
                ev.append((t, _fp("INFRA_UNAVAILABLE", a.phase), "INFRA", "INFRA_UNAVAILABLE"))
            else:
                ev.append((t, a.core["fingerprint"], a.core["class"], a.core["error_code"]))
    return sorted(ev, key=lambda e: e[0])


def strikes(ev: list[tuple]) -> tuple[int, tuple | None]:
    """Consecutive recurrences of the last fingerprint (a PASS or another fingerprint is progress)."""
    if not ev or ev[-1][1] == "PASS":
        return 0, None
    n = 0
    for e in reversed(ev):
        if e[1] != ev[-1][1]:
            break
        n += 1
    return n, ev[-1]


@dataclass
class Plan:
    lineage: LCMP.Lineage
    state: str = "WAITING"
    reason: str = ""
    phase: str | None = None
    current: Att | None = None
    chain: dict = field(default_factory=dict)   # phase -> wo that passed it (the lineage's quality-checked parts)
    last_good: dict | None = None
    strikes: int = 0
    strike_event: tuple | None = None
    action: str | None = None                   # PLACE RELAUNCH LAUNCH ESCALATE None
    kind: str | None = None                     # START CHAIN RETRY RETRY_INFRA UPSTREAM RELAUNCH RELAUNCH_INFRA
    order: dict | None = None                   # the phase order spec to place / launch
    not_before: float = 0.0
    sweep: bool = False
    provided_from: str | None = None
    gaps: list[dict] = field(default_factory=list)
    prev: Att | None = None                     # the last passed order (the last good part)
    atts: dict = field(default_factory=dict)     # phase -> the attempts read this cycle
    superseded: str | None = None               # a never-launched queued order replaced after a campaign change

    def view(self) -> dict:
        L = self.lineage
        nxt = None
        if self.order is not None:
            nxt = {k: self.order.get(k) for k in ("wo", "phase", "kind", "revision", "resume_from", "provided_from",
                                                  "resume_upto", "stop_after")}
            nxt.update(action=self.action, not_before=_utc(self.not_before) if self.not_before else None,
                       sweep=self.sweep, quality=bool(self.order.get("quality")))  # carried by flag or revision
        cur = self.current
        return {"lineage": f"{L.campaign_id}/{L.id}", "tag": L.tag, "example": L.example, "state": self.state,
                "reason": self.reason or None, "phase": self.phase, "priority": L.priority,
                "revision": (L.factory_revision or None), "wo": cur.wo if cur else None,
                "fabro_run_id": cur.rid if cur else None, "last_good": self.last_good,
                "strikes": {"count": self.strikes, "limit": STRIKE_LIMIT,
                            "fingerprint": self.strike_event[1] if self.strike_event else None,
                            "class": self.strike_event[2] if self.strike_event else None,
                            "code": self.strike_event[3] if self.strike_event else None},
                "provided_from": self.provided_from, "next": nxt}


def infra_backoff(k: int, policy: LinePolicy) -> float:
    base = float(policy.get("pacing.infra_backoff_base_s", 60))
    cap = float(policy.get("pacing.infra_cooldown_s", 600))
    return min(cap, base * 2 ** max(0, k - 1))


class Planner:
    """Pure planning over one cycle's records: every lineage's state, last good part and next step."""

    def __init__(self, campaigns: list[LCMP.Campaign], recs: Records, line, policy: LinePolicy, now: float,
                 *, durable_control=None):
        from .line_verified_causes import Guard

        self.campaigns, self.recs, self.line, self.policy, self.now = campaigns, recs, line, policy, now
        self.durable_control = durable_control
        self.verified_causes = Guard(getattr(recs, "cre_db", None))
        self.plans: dict[str, Plan] = {}

    def run(self) -> list[Plan]:
        for c in self.campaigns:
            for L in c.lineages:
                self.plans[L.key] = self.walk(L)
        for c in self.campaigns:  # dependencies resolve against the walked chains
            for L in c.lineages:
                self.decide(self.plans[L.key], c)
        return [self.plans[L.key] for c in self.campaigns for L in c.lineages]

    def walk(self, L: LCMP.Lineage) -> Plan:
        P = Plan(L)
        P.atts = {ph: self.recs.phase_attempts(L, ph) for ph in L.phases}
        if L.status == "DONE":
            P.state, P.reason, P.phase = "DONE", "CAMPAIGN_DONE", L.phases[-1]
            P.chain = {L.phases[-1]: L.completed_by}
            P.last_good = {"phase": L.phases[-1], "wo": L.completed_by}
            return P
        phases = list(L.phases)
        prev: Att | None = None
        if L.start:
            at = L.start["at"]
            before = PHASES[PHASES.index(at) - 1]
            src = self.recs.attempt(L.start["resume_from"], before, 0)
            if not (src.rec and before in src.rec["passed"]):
                P.state, P.reason, P.phase = "ESCALATED", "START_ORDER_NOT_PASSED", at
                return P
            prev = src
            P.chain[before] = src.wo
            phases = phases[phases.index(at):]
        for ph in phases:
            atts = self.recs.phase_attempts(L, ph)
            cands = [a for a in atts if a.status != "CLOSED" and (prev is None or (a.created or 0) >= (prev.created or 0))]
            P.phase = ph
            if not cands:
                P.current = None
                break
            a = max(cands, key=lambda x: ((x.created or 0), x.n))
            P.current = a
            if a.status == "ENDED" and a.verdict == "PASS":
                P.chain[ph] = a.wo
                prev = a
                P.gaps += quality_gaps(a, L)
                continue
            break
        else:
            P.current, P.state, P.reason = None, "DONE", "ALL_PHASES_PASSED"
        if prev is not None:
            last = [p for p in PHASES if P.chain.get(p) == prev.wo]
            P.last_good = {"phase": last[-1] if last else None, "wo": prev.wo}
        P.prev = prev
        if P.phase:
            n, e = strikes(_events(self.recs.phase_attempts(L, P.phase), L.sha256)) if P.state != "DONE" else (0, None)
            P.strikes, P.strike_event = n, e
        return P

    # ---------------------------------------------------------------------------------------------- decisions
    def _order(self, P: Plan, phase: str, kind: str, *, resume_from, resume_upto=None, wo=None) -> dict | None:
        L = self.plans[P.lineage.key].lineage
        n = max([a.n for a in self.recs.phase_attempts(L, phase)] + [0]) + 1
        ok, via = self._quality_ok(L)
        order = phase_order(L, phase, kind, wo=wo or L.wo(phase, n), resume_from=resume_from,
                            provided_from=P.provided_from, resume_upto=resume_upto,
                            quality_via=(via or None) if ok else None, durable_control=self.durable_control)
        if self.durable_control is not None and P.prev and (P.prev.spec or {}).get("durable_recovery"):
            order["durable_recovery"] = P.prev.spec["durable_recovery"]
        return order

    def decide(self, P: Plan, campaign: LCMP.Campaign) -> None:
        L = P.lineage
        if P.state in ("DONE", "ESCALATED"):
            return
        if L.status == "ON_HOLD":
            P.state, P.reason = "ON_HOLD", "CAMPAIGN_ON_HOLD"
            return
        # the provided LL of a HAL lineage
        if L.depends_on:
            dep = self.plans.get(f"{L.campaign_id}/{L.depends_on['lineage']}")
            got = (dep.chain.get(L.depends_on["phase"]) if dep else None)
            if not got:
                P.state, P.reason = "WAITING", f"DEPENDS_ON:{L.depends_on['lineage']}:{L.depends_on['phase']}:PASS"
                return
            P.provided_from = got
        elif L.provided_from:
            P.provided_from = L.provided_from
        a, prev = P.current, P.prev
        if a is not None and a.status in ("LAUNCHING", "RUNNING"):
            P.state, P.reason = a.status, "ADOPTED" if not a.spec else ""
            return
        if L.factory_revision is None:
            P.state, P.reason = "WAITING", "FACTORY_REVISION_PENDING"
            return
        full = self.line.resolve(L.factory_revision)
        if full is None:
            P.state, P.reason = "WAITING", "FACTORY_REVISION_NOT_ON_HOST"
            return
        ph = P.phase
        if a is None:
            kind = "START" if prev is None else "CHAIN"
            self._place(P, self._order(P, ph, kind, resume_from=prev.wo if prev else None), "PLACE")
            return
        if a.status == "QUEUED":
            prior = [x for x in P.atts.get(ph, []) if x.status == "ENDED" and x.verdict == "NO"]
            failed = max(prior, key=lambda x: ((x.created or 0), x.n)) if prior else None
            reason = self.verified_causes.blocked(failed, full, self.recs)
            if reason:
                P.state, P.reason = (("ESCALATED", "SAME_ISSUE_EXCEEDED_3") if P.strikes > STRIKE_LIMIT
                                     else ("WAITING", reason))
                return
            o = dict(a.spec or {})
            fresh = self._order(P, ph, o.get("kind") or "CHAIN", resume_from=o.get("resume_from"),
                                resume_upto=o.get("resume_upto"), wo=a.wo)
            if self.durable_control is not None and o.get("durable_control") == self.durable_control:
                if o.get("durable_recovery"):
                    fresh["durable_recovery"] = o["durable_recovery"]
            if "rework_context" in o:
                fresh["rework_context"] = o["rework_context"]
            if a.spec and _digest(fresh) == _digest(a.spec):
                self._place(P, a.spec, "LAUNCH")
            else:  # the campaign changed under a never-launched order: a new name, the old one is superseded
                P.superseded = a.wo
                self._place(P, self._order(P, ph, o.get("kind") or "CHAIN", resume_from=o.get("resume_from"),
                                           resume_upto=o.get("resume_upto")), "PLACE")
            return
        if P.strikes > STRIKE_LIMIT:
            P.state, P.reason = "ESCALATED", "SAME_ISSUE_EXCEEDED_3"
            return
        base = a.spec or {"resume_from": (a.rec or {}).get("source") or (prev.wo if prev else None),
                          "resume_upto": None}
        if a.status == "LAUNCH_FAILED":
            last = a.launches[-1]
            if a.spec and a.lineage_sha != L.sha256:  # the owner changed the lineage (e.g. a newer revision): new name
                P.superseded = a.wo  # the never-launched order is closed in the queue
                self._place(P, self._order(P, ph, "RETRY", resume_from=base.get("resume_from"),
                                           resume_upto=base.get("resume_upto")), "PLACE")
                return
            o = self._order(P, ph, "RELAUNCH_INFRA" if last["class"] == "INFRA" else "RELAUNCH",
                            resume_from=base.get("resume_from"), resume_upto=base.get("resume_upto"), wo=a.wo)
            if last["class"] == "REFUSED":
                P.not_before = last["at"] + 60
            elif last["class"] == "INFRA":
                P.not_before, P.sweep = last["at"] + infra_backoff(P.strikes, self.policy), True
            else:
                P.not_before = last["at"] + infra_backoff(P.strikes, self.policy)
            self._place(P, o, "RELAUNCH")
            return
        # an ended order that did not pass
        cls = "INFRA" if a.verdict == "INFRA_UNAVAILABLE" else a.core["class"]
        if a.core and a.core.get("route") == "CANCELLED" and a.verdict != "INFRA_UNAVAILABLE":
            if a.lineage_sha in (None, L.sha256):
                P.state, P.reason = "PARKED", "FABRO_RUN_CANCELLED"
                return
            cls = "RELEASED"
        reason = self.verified_causes.blocked(a, full, self.recs)
        if reason:
            P.state, P.reason = "WAITING", reason
            return
        if cls == "FACTORY_DEFECT":
            if self._same_rev(a.revision, full):
                P.state = "WAITING"
                P.reason = f"WAITING_EXTERNAL_CHANGE:{a.core.get('capa') or a.core.get('error_code')}"
                return
            self._place(P, self._order(P, ph, "RETRY", resume_from=base.get("resume_from"),
                                       resume_upto=base.get("resume_upto")), "PLACE")
            return
        up = [u for u in (a.core or {}).get("upstream") or [] if u in PHASES and PHASES.index(u) < PHASES.index(ph)]
        if cls == "PRODUCT" and up:
            u = sorted(up, key=PHASES.index)[0]  # the earliest owning phase (the factory's defect route)
            self._place(P, self._order(P, u, "UPSTREAM", resume_from=a.wo, resume_upto=u), "PLACE")
            return
        o = self._order(P, ph, "RETRY_INFRA" if cls == "INFRA" else "RETRY", resume_from=base.get("resume_from"),
                        resume_upto=base.get("resume_upto"))
        if cls == "INFRA":
            P.not_before, P.sweep = (a.ended_at or self.now) + infra_backoff(P.strikes, self.policy), True
        self._place(P, o, "PLACE")

    def _same_rev(self, rev: str | None, full: str) -> bool:
        """True when the failed order ran on the revision the campaign names now (an unknown revision counts as the
        same: a factory defect is never retried without a recorded change)."""
        if not rev:
            return True
        r = self.line.resolve(rev) or rev
        return full.startswith(r) or r.startswith(full)

    def _place(self, P: Plan, order: dict, action: str) -> None:
        L = P.lineage
        ok, why = self._quality_ok(L)
        if not ok:
            P.state, P.reason = "WAITING", why
            return
        # order["quality_via"]: FLAG = --quality FILE; REVISION = the revision gives exactly that quality
        P.order, P.action, P.kind = order, action, order["kind"]
        if order.get("resume_from") is None and order["phase"] != L.phases[0] and not L.start:
            P.state, P.reason, P.action, P.order = "ESCALATED", "NO_LAST_GOOD_PART", None, None
            return
        P.state = "CHAINED" if order["kind"] == "CHAIN" or (order["kind"] == "START" and L.depends_on) else "QUEUED"
        P.reason = order["kind"]

    def _quality_ok(self, L: LCMP.Lineage) -> tuple[bool, str]:
        return quality_delivery(L, self.line)


def quality_delivery(L, line):
    """The existing quality-source rule shared with read-only intake previews."""
    if L.quality is None:
        return True, ""
    from ..quality import defaults

    full = line.resolve(L.factory_revision)
    readable, spec_q = line.spec_quality(full, L.example)
    if not readable:
        return False, "EXAMPLE_NOT_AT_REVISION"
    effective = spec_q if spec_q is not None else defaults(L.purpose)
    if effective == L.quality:
        return True, "REVISION"
    if line.quality_supported(full):
        return True, "FLAG"
    return False, "QUALITY_NOT_DELIVERABLE_AT_REVISION"


def phase_order(L, phase, kind, *, wo, resume_from, provided_from, resume_upto=None,
                quality_via=None, durable_control=None):
    """Canonical launch identity; producing this dictionary does not place an order."""
    order = {"schema": ORDER_SCHEMA, "wo": wo, "phase": phase, "kind": kind,
             "lineage": L.key, "lineage_sha": L.sha256, "campaign_id": L.campaign_id, "example": L.example,
             "driver_class": L.driver_class, "revision": L.factory_revision, "profile": L.profile,
             "run_model": L.run_model, "purpose": L.purpose, "resume_from": resume_from,
             "provided_from": provided_from, "resume_upto": resume_upto, "stop_after": phase,
             "quality": L.quality, "quality_via": quality_via}
    if durable_control is not None:
        order["durable_control"] = durable_control
    return order


def placed_spec(order, campaign, grant, *, placed_at=None):
    """Stable campaign/grant binding; an omitted timestamp is explicitly only a proposal."""
    return {**order, **({"placed_at": placed_at} if placed_at is not None else {}),
            "campaign_sha256": campaign.sha256, "campaign_commit": campaign.commit,
            "campaign_file": campaign.rel, "authorization_id": grant.authorization_id}


def envelope_for(order, lineage, campaign, grant, now, payload_digest, *, line_id):
    """Existing normal intake envelope. submitted_utc here is proposed until Store.submit persists it."""
    return {"schema_version": "1.0", "request_id": order["wo"], "tenant_scope": f"line-{line_id}",
            "manifest_sha256": campaign.sha256, "input_manifest_ref": campaign.rel,
            "approved_by": f"campaign-commit:{(campaign.commit or 'none')[:40]}",
            "authorization_ref": grant.authorization_id or "-", "driver_class": lineage.driver_class,
            "target": lineage.example, "safety_scope": lineage.purpose, "model_profile": lineage.profile,
            "submitted_utc": _utc(now).replace("Z", "+00:00"), "priority": "NORMAL",
            "git_revision": order.get("revision") or "unknown", "payload_digest": payload_digest}


ORDER_KEYS = ("schema", "wo", "phase", "kind", "lineage", "lineage_sha", "campaign_id", "example", "driver_class",
              "revision", "profile", "run_model", "purpose", "resume_from", "provided_from", "resume_upto", "stop_after",
              "quality", "quality_via")


def _digest(spec: dict) -> str:
    """The order spec's identity (the queue's payload_digest): only the fields that define the launch."""
    identity = {k: spec.get(k) for k in ORDER_KEYS}
    for key in ("durable_control", "durable_recovery", "rework_context"):
        if key in spec:
            identity[key] = spec[key]
    return sha256_bytes(canonical_json(identity))


def quality_gaps(a: Att, L: LCMP.Lineage) -> list[dict]:
    """Decision 15: a phase that passed below the order's target (at or above its minimum) - the gap, from the gate
    log's BELOW_TARGET_ACCEPTED records and the package's quality-achieved rows."""
    out = []
    rx = re.compile(r"^([A-Z_]+BELOW_TARGET):([A-Za-z_]+):([0-9.]+)%\s*\(target ([0-9.]+)%, minimum ([0-9.]+)%")
    for e in (a.rec or {}).get("log") or []:
        if e.get("step") == "quality" and e.get("result") == "BELOW_TARGET_ACCEPTED" and e.get("phase") == a.phase:
            for s in e.get("shortfall") or []:
                m = rx.match(str(s))
                if m:
                    out.append({"lineage": L.key, "wo": a.wo, "phase": a.phase, "metric": m.group(2).lower(),
                                "achieved": float(m.group(3)), "target": float(m.group(4)),
                                "minimum": float(m.group(5)), "code": m.group(1)})
    ws = a.rec["ws"] if a.rec else None
    for q in (list(ws.glob("*/quality/quality-achieved.json")) + list(ws.glob("*/*/quality/quality-achieved.json"))
              if ws else []):
        for r in (_load(q) or {}).get("rows") or []:
            if r.get("status") == "BELOW_TARGET" and r.get("achieved") is not None:
                out.append({"lineage": L.key, "wo": a.wo, "phase": a.phase, "metric": str(r.get("metric")),
                            "achieved": float(r["achieved"]), "target": float(r["target"]),
                            "minimum": float(r["minimum"]), "code": "QUALITY_BELOW_TARGET"})
    seen, uniq = set(), []
    for g in out:
        k = (g["wo"], g["metric"])
        if k not in seen:
            seen.add(k)
            uniq.append(g)
    return uniq


# ----------------------------------------------------------------------------------------------------- escalation
class Escalator:
    """Decision 5: everything goes to the floor and the local log; a GitHub issue only for 'needs you' (a stopped
    lineage, disk below the guard), once per cause, with no @mention. Dry run: the gh command is recorded, not run."""

    def __init__(self, line, repo: str, *, dry_run: bool, now: float, persist: bool | None = None):
        self.line, self.repo, self.dry_run, self.now = line, repo, dry_run, now
        self.persist = (not dry_run) if persist is None else persist
        self.path = supervisor_dir() / "escalations.jsonl"

    def _done(self) -> dict:
        out = {}
        for ln in self.path.read_text().splitlines() if self.path.is_file() else []:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("status") in ("CREATED", "DRY_RUN"):
                out[r["key"]] = r
        return out

    @staticmethod
    def _clean(s: str, n: int) -> str:
        s = s.replace("@", "(at)")  # never an @mention (decision 5)
        return re.sub(r"[^A-Za-z0-9 _.:;,/()+=#<>|\n-]+", "_", s)[:n]

    def raise_once(self, key: str, title: str, body: str) -> dict:
        from .line_conductor import append_jsonl

        done = self._done()
        if key in done:
            return {**done[key], "deduplicated": True}
        title, body = self._clean(title, 200), self._clean(body, 4000)
        argv = ["issue", "create", "--repo", self.repo, "--title", title, "--body", body]
        rec = {"at": _utc(self.now), "key": key, "title": title, "argv": ["gh", *argv[:4], "--title", "<title>",
                                                                          "--body", "<body>"]}
        if self.dry_run:
            rec.update(status="DRY_RUN", body_sha256=sha256_bytes(body.encode()))
        else:
            rc, out = self.line.gh(argv)
            rec.update(status="CREATED" if rc == 0 else "FAILED", url=out if rc == 0 else None, rc=rc,
                       body_sha256=sha256_bytes(body.encode()))
        if self.persist:
            append_jsonl(self.path, rec)
        return rec


# ------------------------------------------------------------------------------------------------------ the placer
class Placer:
    """ACT mode: one cycle = plan, then (with a valid grant, outside dry run) at most one launch step, the queue
    bookkeeping, owner escalations and the disk guard's cleanup."""

    def __init__(self, line, *, line_id: str = "local", dry_run: bool = False, campaigns_dir: Path | None = None,
                 policy_path: Path | None = None, auth_base: Path | None = None, allowed_signers: Path | None = None,
                 unit: str = "manual", clock=time.time, require_approval: bool = True, capa_of: dict | None = None,
                 cre_db: Path | None = None, recovery_config: Path | None = None,
                 owner_supervised_development: bool = False):
        self.owner_supervised_development = owner_supervised_development
        self.line, self.line_id, self.dry_run = line, line_id, dry_run
        self.cre_db = cre_db
        self.recovery_config = recovery_config
        self.durable_control = None
        self.campaigns_dir = campaigns_dir
        self.policy_path, self.auth_base, self.allowed_signers = policy_path, auth_base, allowed_signers
        self.unit, self.clock, self.require_approval, self.capa_of = unit, clock, require_approval, capa_of
        self.queue_path = supervisor_dir() / "line-queue.sqlite3"
        # This is an observation of the existing authority, never a request to
        # restore it. Once seen, its inode cannot be replaced by a new empty
        # database through a later explicit-path Store constructor.
        self._queue_identity = None
        self._queue_unknown = False
        try:
            info = self.queue_path.lstat()
            self._queue_identity = info.st_dev, info.st_ino
        except FileNotFoundError:
            pass  # explicit legacy first bootstrap remains supported below
        except OSError:
            self._queue_unknown = True
        self._store_handle = None
        self._act_lock = None
        self._logged: set = set()

    def _storage_ready(self):
        """No initialization: fence known/durable authority before cycle writes."""
        from .operations import configured
        from .queue import QueueError

        required = (self._queue_identity is not None or self._queue_unknown
                    or self.owner_supervised_development or self.recovery_config is not None
                    or os.environ.get("FORGE_DURABLE_AUTONOMY") == "1"
                    or os.environ.get("FORGE_AFO_QUEUE_SCOPE") == "line-local" or configured())
        if not required:
            return
        if os.environ.get("FORGE_DURABLE_AUTONOMY") == "1":
            from .host import preflight

            if not preflight()["ok"]:
                raise QueueError("DURABLE_DATA_VOLUME_NOT_READY")
        if self._queue_unknown:
            raise QueueError("AUTHORITATIVE_DATABASE_UNAVAILABLE")
        # Existing-only mode checks the actual SQLite header, schema and path
        # identity without mkdir/migration/empty fallback. Its connect() keeps
        # enforcing that same identity at every subsequent transaction.
        if self._store_handle is None:
            from .queue import Store

            handle = Store(self.queue_path, producer=f"line-conductor:{self.line_id}", must_exist=True)
            if self._queue_identity is not None and handle._existing_identity != self._queue_identity:
                raise QueueError("AUTHORITATIVE_DATABASE_IDENTITY_CHANGED")
            self._queue_identity = handle._existing_identity
            self._store_handle = handle
        self._store_handle._check_existing()

    def _store(self, *, producer=None):
        """The existing controller Store, with one explicit legacy bootstrap."""
        from .queue import Store

        self._storage_ready()
        if self._store_handle is None:
            # Reached only before any authority has been observed, with no
            # durable/Intent/development runtime configured. This is the old
            # explicit M3 bootstrap, not restoration after storage loss.
            initial = Store(self.queue_path, producer=f"line-conductor:{self.line_id}")
            self._store_handle = Store(initial.path, producer=initial.producer, must_exist=True)
            self._queue_identity = self._store_handle._existing_identity
        self._store_handle._check_existing()
        if producer is not None and producer != self._store_handle.producer:
            consumer = Store(self.queue_path, producer=producer, must_exist=True)
            if consumer._existing_identity != self._queue_identity:
                from .queue import QueueError

                raise QueueError("AUTHORITATIVE_DATABASE_IDENTITY_CHANGED")
            return consumer
        return self._store_handle

    # ------------------------------------------------------------------------------------------------ the cycle
    def cycle(self, now: float | None = None) -> dict:
        now = now or self.clock()
        policy = load_policy(self.policy_path)
        if self.owner_supervised_development:
            from .owner_supervised_development import DevelopmentGrant

            grant = DevelopmentGrant(policy)
        else:
            grant = verify_grant(policy, now=now, base=self.auth_base, allowed_signers=self.allowed_signers)
        try:
            self._storage_ready()
        except (OSError, ValueError) as exc:
            from .queue import QueueError

            # This check precedes ACT locks, recovery, learning and local
            # status/spec/log publication. Unknown storage cannot gain an
            # apparently fresh allowance from a newly initialized queue.
            if not isinstance(exc, (OSError, QueueError)):
                raise
            return {"mode": "OBSERVING", "authorization": grant.view(), "policy_issues": policy.issues[:6],
                    "error": getattr(exc, "code", "AUTHORITATIVE_STORAGE_UNKNOWN"),
                    "storage": {"status": "BLOCKED", "initialized": False}, "lineages": [],
                    "gpu": {"busy": True, "reason": "AUTHORITATIVE_STORAGE_UNKNOWN", "wo": None},
                    "campaigns": [], "rejected": [], "actions": [], "quality_gaps": []}
        cdir = self.campaigns_dir or (Path(policy.get("campaigns_dir")) if policy.get("campaigns_dir") and
                                      Path(policy.get("campaigns_dir")).is_absolute() else
                                      REPO_ROOT / (policy.get("campaigns_dir") or "config/factory/campaigns"))
        campaigns, rejected = LCMP.load_all(cdir, line=self.line_id, require_approval=self.require_approval)
        capa_of = self.capa_of
        if capa_of is None:  # open CAPAs by fingerprint (read-only), for the FACTORY_DEFECT class
            from .line_conductor import read_cre

            capa_of = read_cre(self.cre_db or supervisor_dir() / "incidents.sqlite3")["capa_of"]
        recs = self._records(now, capa_of)
        recs.cre_db = self.cre_db or supervisor_dir() / "incidents.sqlite3"
        if self.recovery_config is not None:
            from .line_recovery_coordination import reference

            self.durable_control = reference(self.recovery_config)
        plans = Planner(campaigns, recs, self.line, policy, now, durable_control=self.durable_control).run()
        locked = (grant.allow or self.durable_control is not None) and not self.dry_run and not self._take_act_lock()
        acting = grant.allow and not self.dry_run and not locked
        mode = (("OWNER_SUPERVISED_DEVELOPMENT" if self.owner_supervised_development else "ACTING")
                if acting else ("DRY_RUN" if self.dry_run else "OBSERVING"))
        actions: list[dict] = []
        free = self.line.free_bytes()
        min_gb = float(policy.get("disk.min_free_gb", FLOOR["min_free_gb"]))
        placing_ok = free >= min_gb * GB
        gpu = self._gpu(plans)
        esc = Escalator(self.line, str(policy.get("escalation.github_repo") or "jnsagai/forge-c"),
                        dry_run=not acting or self.owner_supervised_development, now=now)
        if acting:
            actions += self._reconcile(plans, policy, grant, campaigns, now)
        if self.durable_control is not None:
            from .line_recovery_coordination import coordinate

            actions += coordinate(self, plans, policy, grant, campaigns, now, execute=not self.dry_run and not locked)
        # owner escalations (decision 5): lineages stopped by the owner retry rule, and the disk guard
        for P in plans:
            if P.state == "ESCALATED":
                ev = P.strike_event
                key = _fp("ESCALATED", P.lineage.key, P.lineage.sha256, P.reason, ev[1] if ev else "-")
                body = (f"Line {self.line_id}: lineage {P.lineage.key} ({P.lineage.example}) stopped at {P.phase}.\n"
                        f"Reason: {P.reason}. Strikes: {P.strikes} of {STRIKE_LIMIT} allowed (same issue more than 3 "
                        f"times stops the lineage).\nLast issue: class {ev[2] if ev else '-'}, code {ev[3] if ev else '-'}, "
                        f"fingerprint {ev[1] if ev else '-'}.\nLast order: {P.current.wo if P.current else '-'}. "
                        f"Last good part: {(P.last_good or {}).get('wo') or '-'}.\nOther lineages keep going. "
                        "The lineage resumes when the owner changes its campaign entry (a new commit).")
                actions.append({"action": "ESCALATE", "lineage": P.lineage.key, "reason": P.reason,
                                **{k: v for k, v in esc.raise_once(
                                    key, f"Forge-C line {self.line_id}: {P.lineage.id} stopped ({P.reason})", body).items()
                                   if k in ("status", "deduplicated")}})
        if not placing_ok:
            key = _fp("DISK_LOW", self.line_id, int(now // 86400))
            actions.append({"action": "ESCALATE", "reason": "DISK_BELOW_GUARD", **{k: v for k, v in esc.raise_once(
                key, f"Forge-C line {self.line_id}: placement stopped, disk below {min_gb:g} GB",
                f"Free space {free / GB:.1f} GB is below the {min_gb:g} GB guard (decision 12). No new order is "
                "placed; running orders continue. Only the conductor's own run worktrees and pytest temps older than "
                "3 days are cleaned.").items() if k in ("status", "deduplicated")}})
        if acting or self.dry_run:
            actions += self._cleanup(policy, grant, now, execute=acting)
        recovery_busy = any(a.get("outcome") in ("DURABLE_WORKER_STARTED", "DURABLE_WORKER_ACTIVE") for a in actions)
        for chosen in self._ready(plans, now) if placing_ok and not gpu["busy"] and not recovery_busy else []:
            res = self._execute(chosen, policy, grant, campaigns, now, execute=acting)
            actions.append(res)
            if res["outcome"] not in ("REFUSED", "WOULD_REFUSE", "PACED"):
                break  # one launch step per cycle; a lineage the grant refuses never blocks the next one
        from .line_conductor import append_jsonl

        for a in actions:  # the local log (decision 5); a repeated identical non-executing outcome is logged once
            key = json.dumps({k: a.get(k) for k in ("action", "wo", "outcome", "detail", "status")}, sort_keys=True)
            if acting and key not in self._logged:
                append_jsonl(supervisor_dir() / "placement.jsonl", {"at": _utc(now), "mode": mode, **a})
            self._logged.add(key) if a.get("outcome") not in ("LAUNCHING", "REMOVED", "RUNNING") else None
        if acting:
            import sqlite3

            from .line_lessons import capture

            try:
                learning = capture(self._store(producer=f"line-learning:{self.line_id}"), limit=8)
            except (OSError, ValueError, sqlite3.Error) as exc:
                learning = {"schema": "forge-c/line-learning-capture/1", "status": "CAPTURE_FAILED",
                            "code": getattr(exc, "code", type(exc).__name__), "model_calls": 0, "new_lessons": 0}
            _atomic(supervisor_dir() / "line-learning.json", learning)
        return {"mode": mode, **({"error": "ACT_LOCK_HELD"} if locked else {}), "authorization": grant.view(),
                "policy_issues": policy.issues[:6],
                "campaigns": [{"campaign_id": c.campaign_id, "file": c.rel, "sha256": c.sha256, "commit": c.commit}
                              for c in campaigns],
                "rejected": rejected[:20], "gpu": gpu,
                "disk": {"free_gb": round(free / GB, 1), "min_gb": min_gb, "placing": placing_ok},
                "lineages": [P.view() for P in plans], "actions": actions,
                "quality_gaps": [g for P in plans for g in P.gaps][:50]}

    def _take_act_lock(self) -> bool:
        """One acting conductor per line state (a second instance stays OBSERVE)."""
        if self._act_lock is not None:
            return True
        d = supervisor_dir()
        d.mkdir(parents=True, exist_ok=True)
        f = open(d / "act.lock", "a")  # noqa: SIM115 - held for the process lifetime
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.close()
            return False
        self._act_lock = f
        return True

    def _records(self, now, capa_of):
        return Records(self.line, self.queue_path, now, capa_of)

    def _gpu(self, plans: list[Plan]) -> dict:
        busy = [P for P in plans if P.state in ("LAUNCHING", "RUNNING")]
        if busy:
            return {"busy": True, "reason": busy[0].state, "wo": busy[0].current.wo if busy[0].current else None}
        holders = self.line.gpu_holders()
        if holders:
            return {"busy": True, "reason": "GPU_LOCK_HELD", "wo": None}
        live = self.line.live_runs()
        if live is None:
            return {"busy": True, "reason": "FABRO_API_UNREACHABLE", "wo": None}
        if live:
            return {"busy": True, "reason": "RUN_LIVE_NOT_IN_CAMPAIGN", "wo": None}
        return {"busy": False, "reason": None, "wo": None}

    def _ready(self, plans: list[Plan], now: float) -> list[Plan]:
        """Plans with a launch step due now, highest priority first (campaign order breaks ties)."""
        ready = [P for P in plans if P.action in LAUNCH_ACTIONS and P.not_before <= now]
        return sorted(ready, key=lambda P: (-P.lineage.priority, P.lineage.position))

    def _pacing_ok(self, P: Plan, policy: LinePolicy, now: float) -> bool:
        if P.kind not in ("RETRY_INFRA", "RELAUNCH_INFRA"):
            return True
        n = 0
        for f in (supervisor_dir() / "line-orders").glob("*.json"):
            s = _load(f) or {}
            for t in s.get("infra_recoveries") or []:
                if now - t <= 3600:
                    n += 1
        return n < int(policy.get("pacing.infra_recoveries_per_hour_host", 6))

    # ------------------------------------------------------------------------------------------------ execution
    def _requests(self, P: Plan) -> list[tuple[str, dict]]:
        o, L = P.order, P.lineage
        req = {"order_id": o["wo"], "driver_class": L.driver_class, "model": L.profile}
        out = [("launch_workorder", req), ("launch_workorder", {**req, "service_action": "line_stack_restart"})]
        if P.action == "PLACE":
            out.insert(0, ("submit_workorder", req))
        if o["kind"] in RETRY_KINDS:
            out.append(("recover_workorder", req))
        if P.sweep:
            out.append(("recover_workorder", {**req, "service_action": "line_orphan_sweep"}))
        return out

    def _execute(self, P: Plan, policy: LinePolicy, grant: Grant, campaigns, now: float, *, execute: bool) -> dict:
        o = P.order
        if self.owner_supervised_development:
            from .durable import Refused
            from .owner_supervised_development import ENVELOPE_REFUSED, validate_order

            try:
                validate_order(o)
            except Refused as exc:
                if exc.code != ENVELOPE_REFUSED:
                    raise
                # An order outside the lane is not placed. It must not end the guardian either.
                return {"action": P.action, "kind": o["kind"], "wo": o["wo"], "outcome": "REFUSED", "detail": exc.code}
        act = {"action": P.action, "kind": o["kind"], "lineage": P.lineage.key, "wo": o["wo"], "phase": o["phase"],
               "revision": o["revision"], "resume_from": o["resume_from"], "provided_from": o["provided_from"],
               "resume_upto": o["resume_upto"]}
        argv = self._argv(o)
        act["argv"] = argv  # the exact launcher command, also shown when the grant refuses it
        if not self._pacing_ok(P, policy, now):
            return {**act, "outcome": "PACED", "detail": "infra recoveries per hour at the guard (pacing only)"}
        denied = [(a, r, d) for a, r in self._requests(P) if not (d := grant.permit(a, r)).allow]
        if denied:
            a, r, d = denied[0]
            return {**act, "outcome": "WOULD_REFUSE" if not execute else "REFUSED", "detail": f"{d.code}:{a}:{r}"[:200]}
        if not execute:
            return {**act, "outcome": "PLANNED", "sweep": P.sweep}
        if P.sweep:
            rep = self.line.sweep()
            act["sweep"] = {k: rep.get(k) for k in ("ok", "refused", "killed", "survivors")}
            if not rep.get("ok"):
                return {**act, "outcome": "SWEEP_REFUSED"}
        camp = next(c for c in campaigns if c.campaign_id == P.lineage.campaign_id)
        superseded = P.superseded
        from .queue import QueueError

        store = self._store()
        if superseded and superseded in _queue_rows(self.queue_path):
            oid = _queue_rows(self.queue_path)[superseded]["order_id"]
            try:
                store.transition(oid, "BLOCKED", "superseded by a campaign change",
                                 terminal_reason="SUPERSEDED_BY_CAMPAIGN_CHANGE")
            except QueueError:
                pass
        spec_path = supervisor_dir() / "line-orders" / f"{o['wo']}.json"
        spec = _load(spec_path) if P.action != "PLACE" else None
        if spec is None:
            spec = placed_spec(o, camp, grant, placed_at=_utc(now))
        if o["kind"] in ("RETRY_INFRA", "RELAUNCH_INFRA"):
            spec["infra_recoveries"] = (spec.get("infra_recoveries") or []) + [now]
        if o.get("quality") and o.get("quality_via") == "FLAG":
            qf = supervisor_dir() / "line-orders" / f"{o['wo']}.quality.json"
            _atomic(qf, o["quality"])
            spec["quality_file"] = str(qf)
        spec["digest"] = _digest(spec)
        _atomic(spec_path, spec)
        env = self._env(o, P.lineage, camp, grant, now, spec["digest"])
        try:
            if o.get("durable_control"):
                from .line_recovery_coordination import prepare_continuation

                prepare_continuation(self, store, spec, grant)
            aid, oid = self._admit(store, env, camp, policy, grant, P.kind,
                                   recovery_plan_id=(o.get("durable_recovery") or {}).get("plan_id"))
        except QueueError as exc:
            return {**act, "outcome": "QUEUE_REFUSED", "detail": str(exc)[:200]}
        if o.get("durable_control"):
            from .line_recovery_coordination import bind_continuation, launch_product

            bind_continuation(store, spec, oid, aid)
            return {**act, **launch_product(self, store, o, aid, oid, camp, now)}
        started = self.line.spawn_launch(argv, o["wo"])
        _atomic(supervisor_dir() / "launching" / f"{o['wo']}.json", {**started, "at": _utc(now), "attempt_id": aid,
                                                                       "order_id": oid})
        return {**act, "outcome": "LAUNCHING", "attempt_id": aid, "pid": started.get("pid")}

    def _env(self, o: dict, P_lineage: LCMP.Lineage, camp: LCMP.Campaign, grant: Grant, now: float, digest: str) -> dict:
        return envelope_for(o, P_lineage, camp, grant, now, digest, line_id=self.line_id)

    def _admit(self, store, env: dict, camp: LCMP.Campaign, policy: LinePolicy, grant: Grant, why: str | None,
               *, recovery_plan_id=None) -> tuple[str, str]:
        """(attempt_id, order_id): the queue order of this work order (submitted once, idempotent), a new attempt in
        DISPATCH_PENDING. A paused order (its launch failed) is queued again; an order a crash left ADMITTED reuses
        its pending attempt."""
        from .queue import QueueError

        row = _queue_rows(self.queue_path).get(env["request_id"])
        self._check_admission_scope(env, grant, submit=row is None)
        if row is None:
            oid, _created = store.submit(env, repo=camp.root or camp.path.parent, max_queued=100,
                                         approve=lambda e: (True, "CAMPAIGN_APPROVED"))
            state = store.order(oid)["state"]
        else:
            oid, state = row["order_id"], row["state"]
        if state == "ADMITTED":
            pend = [x for x in store.attempts(oid) if x["state"] in ("PREPARED", "DISPATCH_PENDING")]
            if pend:
                if pend[-1]["state"] == "PREPARED":
                    store.attempt_transition(pend[-1]["attempt_id"], "DISPATCH_PENDING")
                return pend[-1]["attempt_id"], oid
            raise QueueError("QUEUE_STATE", "ADMITTED without a pending attempt")
        if state == "PAUSED":
            store.transition(oid, "QUEUED", f"relaunch ({why})")
        elif state != "QUEUED":
            raise QueueError("QUEUE_STATE", state)
        epoch = store.acquire_lease(f"line:{self.line_id}", self.unit, 600, now=time.time())
        if epoch is None:
            raise QueueError("LEASE_HELD")
        aid = store.admit(oid, epoch=epoch, scope=f"line:{self.line_id}", policy_sha256=policy.sha256 or "",
                          authorization_id=grant.authorization_id, max_concurrent=self._admission_capacity(policy),
                          **({"recovery_plan_id": recovery_plan_id} if recovery_plan_id is not None else {}))
        store.attempt_transition(aid, "DISPATCH_PENDING")
        return aid, oid

    @staticmethod
    def _check_admission_scope(env, grant, *, submit):
        """New admission/adoption rechecks the actual immutable request identity.

        This is not a gate on observation or settlement of an already bound
        native attempt. It never revokes an existing inference lease.
        """
        from .queue import QueueError

        request = {"order_id": env["request_id"], "driver_class": env["driver_class"], "model": env["model_profile"]}
        for action in (("submit_workorder", "launch_workorder") if submit else ("launch_workorder",)):
            decision = grant.permit(action, request)
            if not decision.allow:
                raise QueueError("ORDER_ADMISSION_NOT_AUTHORIZED", f"{decision.code}:{action}")

    def _admission_capacity(self, policy: LinePolicy) -> int:
        return 1  # Local production retains the single-GPU admission floor.

    def _argv(self, o: dict) -> list[str]:
        a = ["launch", o["revision"], o["wo"], o["example"], o["profile"], "--model", o["run_model"],
             "--purpose", o["purpose"], "--stop-after", o["stop_after"]]
        for flag, k in (("--resume-from", "resume_from"), ("--provided-from", "provided_from"),
                        ("--resume-upto", "resume_upto")):
            if o.get(k):
                a += [flag, o[k]]
        if o.get("quality") and o.get("quality_via") == "FLAG":
            a += ["--quality", str(supervisor_dir() / "line-orders" / f"{o['wo']}.quality.json")]
        return a + ["--json"]

    def _reconcile(self, plans: list[Plan], policy: LinePolicy, grant: Grant, campaigns, now: float) -> list[dict]:
        """The queue follows the records: launched -> RUNNING, launch failed -> PAUSED, run ended -> terminal; a live
        run of a lineage that the queue does not hold yet is adopted (submitted and admitted as RUNNING)."""
        from .queue import QueueError

        out = []
        rows = _queue_rows(self.queue_path)
        store = None
        visited = set()
        for P in plans:
            for ph in P.lineage.phases:
                for a in self._known(P, ph):
                    visited.add(a.wo)
                    row = rows.get(a.wo)
                    try:
                        store = store or self._store()
                        ev = self._sync(store, P, a, row, policy, grant, campaigns, now)
                    except QueueError as exc:
                        ev = {"action": "QUEUE_SYNC", "wo": a.wo, "outcome": "QUEUE_REFUSED", "detail": str(exc)[:160]}
                    if ev:
                        out.append(ev)
        # Campaign series can change while an old launch is running. Its immutable queue row still owns
        # capacity; settle it from authoritative terminal evidence even after the planner stops enumerating it.
        ended_run = getattr(self.line, "ended_run", None)
        if not callable(ended_run):
            return out
        recs = Records(self.line, self.queue_path, now, {})
        for wo, row in rows.items():
            env = row["envelope"]
            if wo in visited or row["state"] not in ("RUNNING", "ADMITTED") or Path(wo).name != wo or "\\" in wo:
                continue
            if env.get("tenant_scope") != f"line-{self.line_id}" or env.get("request_id") != wo:
                continue
            spec = _load(supervisor_dir() / "line-orders" / f"{wo}.json")
            if not spec or spec.get("wo") != wo or env.get("payload_digest") != _digest(spec):
                continue
            if spec.get("driver_class") != env.get("driver_class") or spec.get("profile") != env.get("model_profile"):
                continue
            ph = spec.get("phase")
            # A current narrowed grant cannot authorize a NEW order, but it
            # must not strand a previously admitted exact native attempt.
            # This path only observes terminal state under original dispatch
            # identity; it neither submits/adopts nor starts a replacement.
            # The generic recover check authenticates the observing actor only;
            # original admitted identity bounds this monotonic settlement.
            # New admission and any new replan use full current order scope.
            if (ph not in tuple(f"SWE.{n}" for n in range(1, 7))
                    or not grant.permit("recover_workorder", {}).allow
                    or not row.get("authorization_id")
                    or row["authorization_id"] != env.get("authorization_ref")):
                continue
            store = store or self._store()
            attempts = store.attempts(row["order_id"])
            live = attempts[-1] if attempts else None
            rid = (live or {}).get("record", {}).get("fabro_run_id")
            if not rid or live["state"] != "RUNNING" or not ended_run(wo, rid):
                continue
            a = recs.attempt(wo, ph, 1)
            if a.rid != rid or a.status != "ENDED":
                continue
            try:
                ev = self._sync(store, None, a, row, policy, grant, campaigns, now)
            except QueueError as exc:
                ev = {"action": "QUEUE_SYNC", "wo": wo, "outcome": "QUEUE_REFUSED", "detail": str(exc)[:160]}
            if ev:
                out.append(ev)
        return out

    def _known(self, P: Plan, phase: str) -> list[Att]:
        return P.atts.get(phase, [])

    def _sync(self, store, P: Plan, a: Att, row: dict | None, policy: LinePolicy, grant: Grant, campaigns, now: float):
        att_rows = store.attempts(row["order_id"]) if row else []
        live = att_rows[-1] if att_rows else None
        if row is None:
            if a.status != "RUNNING" or (a.spec and a.spec.get("kind") != "ADOPTED"):
                return None
            # adopt a live run placed outside M3 (the loop10 ladders): record it in the queue, never relaunch it
            spec = a.spec or {"schema": ORDER_SCHEMA, "wo": a.wo, "phase": a.phase, "kind": "ADOPTED",
                              "lineage": P.lineage.key, "lineage_sha": P.lineage.sha256,
                              "campaign_id": P.lineage.campaign_id, "example": P.lineage.example,
                              "driver_class": P.lineage.driver_class, "revision": a.revision,
                              "profile": P.lineage.profile, "placed_at": _utc(a.created or now), "fabro_run_id": a.rid}
            spec["digest"] = _digest(spec)
            camp = next(c for c in campaigns if c.campaign_id == P.lineage.campaign_id)
            envelope = self._env(spec, P.lineage, camp, grant, now, spec["digest"])
            self._check_admission_scope(envelope, grant, submit=True)
            _atomic(supervisor_dir() / "line-orders" / f"{a.wo}.json", spec)
            aid, oid = self._admit(store, envelope, camp, policy,
                                   grant, "adopted live run")
            store.attempt_transition(aid, "RUNNING", fabro_run_id=a.rid)
            store.transition(oid, "RUNNING", "adopted: a live run of a campaign lineage placed outside the conductor")
            for c in store.commands("PENDING"):
                if c["order_id"] == oid:
                    store.mark_command(c["command_id"], "ACKED", ack_ref=f"fabro:{a.rid}")
            return {"action": "ADOPT", "wo": a.wo, "fabro_run_id": a.rid, "outcome": "ADOPTED"}
        oid, st = row["order_id"], row["state"]
        if a.status == "RUNNING" and st == "ADMITTED":
            if live and live["state"] == "DISPATCH_PENDING":
                store.attempt_transition(live["attempt_id"], "RUNNING", fabro_run_id=a.rid)
            store.transition(oid, "RUNNING", "launched")
            for c in store.commands("PENDING"):
                if c["order_id"] == oid:
                    store.mark_command(c["command_id"], "ACKED", ack_ref=f"fabro:{a.rid}")
            return {"action": "QUEUE_SYNC", "wo": a.wo, "outcome": "RUNNING", "fabro_run_id": a.rid}
        if a.status == "LAUNCH_FAILED" and st == "ADMITTED":
            if live and live["state"] in ("DISPATCH_PENDING", "PREPARED"):
                store.attempt_transition(live["attempt_id"], "FAILED", exit_status=a.launches[-1]["code"],
                                         finished_utc=_utc(now).replace("Z", "+00:00"))
            store.transition(oid, "PAUSED", f"launch failed {a.launches[-1]['code']}")
            for c in store.commands("PENDING"):
                if c["order_id"] == oid:
                    store.mark_command(c["command_id"], "FAILED")
            return {"action": "QUEUE_SYNC", "wo": a.wo, "outcome": "LAUNCH_FAILED", "code": a.launches[-1]["code"]}
        if a.status == "ENDED" and st in ("RUNNING", "ADMITTED"):
            if st == "ADMITTED":
                store.transition(oid, "RUNNING", "launched (ended before the conductor saw it run)")
            ready = (a.pkg or {}).get("package_status") == "READY_FOR_OFFLINE_REVIEW"
            if live and live["state"] in ("RUNNING", "DISPATCH_PENDING"):
                if live["state"] == "DISPATCH_PENDING":
                    store.attempt_transition(live["attempt_id"], "RUNNING", fabro_run_id=a.rid)
                store.attempt_transition(live["attempt_id"], "SUCCEEDED" if a.verdict == "PASS" else "FAILED",
                                         exit_status=f"PHASE_VERDICT:{a.verdict}",
                                         terminal_package_status="READY_FOR_OFFLINE_REVIEW" if ready else "BLOCKED",
                                         finished_utc=_utc(now).replace("Z", "+00:00"))
            reason = f"PHASE_VERDICT:{a.verdict}:{a.phase}" + (
                f":{a.core['class']}:{a.core['error_code']}" if a.core else "")
            if ready:
                store.transition(oid, "VALIDATING", reason)
                store.transition(oid, "READY_FOR_OFFLINE_REVIEW", reason, terminal_reason=reason[:200])
            else:  # a phase-scoped order's package is BLOCKED (later phases are gaps); the phase verdict is the reason
                if (a.verdict != "PASS" and self.durable_control is not None
                        and (a.spec or {}).get("durable_control") == self.durable_control
                        and grant.permit("recover_workorder", {"order_id": a.wo,
                            "driver_class": row["envelope"].get("driver_class"),
                            "model": row["envelope"].get("model_profile")}).allow):
                    from .line_recovery_coordination import request_replan

                    store.transition(oid, "WAITING_RECOVERY", reason)
                    request_replan(self, store, P, a, live, campaigns, now)
                else:
                    store.transition(oid, "BLOCKED", reason, terminal_reason=reason[:200])
            return {"action": "QUEUE_SYNC", "wo": a.wo, "outcome": f"ENDED_{a.verdict}"}
        return None

    # ------------------------------------------------------------------------------------------------ cleanup
    def _cleanup(self, policy: LinePolicy, grant: Grant, now: float, *, execute: bool) -> list[dict]:
        """Decision 12: only the conductor's own run worktrees (orders it placed, terminal in the line queue, packaged)
        and pytest temps, both older than the policy's age (>= 3 days)."""
        age = float(policy.get("disk.cleanup_min_age_days", 3)) * 86400
        if not grant.permit("recover_workorder", {"service_action": "line_run_worktree_cleanup"}).allow:
            return []
        out = []
        rows = _queue_rows(self.queue_path)
        for wo, row in rows.items():
            if row["state"] not in ("BLOCKED", "READY_FOR_OFFLINE_REVIEW"):
                continue
            if not grant.permit("recover_workorder", {"order_id": wo,
                    "driver_class": row["envelope"].get("driver_class"),
                    "model": row["envelope"].get("model_profile"),
                    "service_action": "line_run_worktree_cleanup"}).allow:
                continue
            pkg = self.line.workspace(wo) / ".forge-run/package.json"
            wt = self.line.run_worktree(wo)
            if not pkg.is_file() or not wt.is_dir() or now - pkg.stat().st_mtime < age:
                continue
            if execute:
                out.append({"action": "CLEANUP_WORKTREE", "wo": wo, "outcome": "REMOVED" if self.line.remove_worktree(wo)
                            else "FAILED"})
            else:
                out.append({"action": "CLEANUP_WORKTREE", "wo": wo, "outcome": "PLANNED"})
        uid = os.getuid()
        for root in self.line.pytest_roots:
            for d in sorted(root.glob("pytest-*")) if root.is_dir() else []:
                try:
                    st = d.stat()
                except OSError:
                    continue
                if not d.is_dir() or d.is_symlink() or st.st_uid != uid or now - st.st_mtime < age \
                        or d.name == "pytest-current":
                    continue
                if execute:
                    shutil.rmtree(d, ignore_errors=True)
                out.append({"action": "CLEANUP_PYTEST_TEMP", "path": str(d), "outcome": "REMOVED" if execute else
                            "PLANNED"})
        return out


# --------------------------------------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m forge_factory.afo.line_orders", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["plan"])
    ap.add_argument("--dry-run", action="store_true", help="ACT-dry-run: plan, verify the grant, execute nothing")
    ap.add_argument("--line", default=os.environ.get("FORGE_LINE_ID", "local"))
    ap.add_argument("--campaigns", type=Path, default=None)
    ap.add_argument("--policy", type=Path, default=None)
    ap.add_argument("--recovery-config", type=Path, default=None)
    ap.add_argument("--fabro-snapshot", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run:
        raise SystemExit("the plan CLI runs only as --dry-run; the Line Conductor service acts (--mode ACT)")
    snap = json.loads(a.fabro_snapshot.read_text()) if a.fabro_snapshot else None
    line = RealLine(fabro_snapshot=snap)
    out = Placer(line, line_id=a.line, dry_run=True, campaigns_dir=a.campaigns, policy_path=a.policy,
                 recovery_config=a.recovery_config).cycle()
    if a.json:
        print(json.dumps(out, indent=1, default=str))
        return 0
    print(f"mode {out['mode']}  authorization {out['authorization']['code']} ({out['authorization']['authorization_id']})"
          f"  disk {out['disk']['free_gb']} GB free (min {out['disk']['min_gb']:g})  gpu "
          f"{'busy ' + str(out['gpu']['reason']) if out['gpu']['busy'] else 'free'}")
    for c in out["campaigns"]:
        print(f"campaign {c['campaign_id']} {c['file']} sha256 {c['sha256'][:16]} commit {(c['commit'] or '-')[:12]}")
    for r in out["rejected"]:
        print(f"rejected {r['file']}: {r['code']}")
    for v in out["lineages"]:
        n = v["next"] or {}
        print(f"  {v['lineage']:<38} {v['state']:<10} {v['phase'] or '-':<6} {(v['reason'] or ''):<40} "
              f"last good {(v['last_good'] or {}).get('wo') or '-'}"
              + (f"\n      next {n.get('action')} {n.get('kind')} {n.get('wo')} resume_from {n.get('resume_from')}"
                 f" provided_from {n.get('provided_from')} rev {n.get('revision')}" if n else ""))
    for x in out["actions"]:
        print(f"  action {x.get('action')} {x.get('wo') or x.get('reason') or ''} -> {x.get('outcome') or x.get('status')}"
              + (f"  {' '.join(x['argv'])}" if x.get("argv") else "") + (f"  ({x['detail']})" if x.get("detail") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
