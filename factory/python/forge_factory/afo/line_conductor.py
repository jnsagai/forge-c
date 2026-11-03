"""Autonomous line M1 (owner 2026-11-03, decisions 1/5/6/7/10/11) - the Line Conductor in OBSERVE mode.

The AFO conductor extended to a whole production line (decision 1: no second scheduler). M1 only observes: each cycle
it reads the line's deterministic records and writes the issues feed `forge-c/supervisor-issues/1`
(specs/014-durable-local-autonomy/contracts/supervisor-issues.schema.json). It places, changes or cancels nothing.

Sources per cycle, all read-only (the only writes are under $FORGE_STATE_DIR/supervisor/):
  * work orders: state/workorders/*/workspace/.forge-run (manifest, gate log, package, fabro_run_id, defects);
  * launch records of the line launcher (FORGE_LINE_LAUNCH_DIR/launch-<WO>.out, written by launch-generic-model.sh);
  * the AFO queue tables (state/conductor/conductor.sqlite3) when present, opened read-only;
  * CRE incidents and CAPAs (state/supervisor/incidents.sqlite3, or FORGE_LINE_CRE_DB), opened read-only;
  * the Fabro run status through the line's local Fabro API (FORGE_LINE_FABRO_URL, token from the stack storage).

Classification reuses the existing taxonomy: the 004 CRE classifier (`reliability.taxonomy`, via
`reliability.observe.from_workspace`) and the AFO failure bundle (`afo.bundle.build`, `afo_class`). The line class is
  INFRA            <- CRE INFRASTRUCTURE / TRANSIENT_DEPENDENCY, launch-log markers of the stack;
  FACTORY_DEFECT   <- AFO FACTORY_CODE_DEFECT (fingerprint linked to an open CAPA);
  PRODUCT          <- AFO PRODUCT_QUALITY with an open upstream defect, or SPECIFICATION_GAP;
  MODEL_CONVERGENCE<- AFO PRODUCT_QUALITY whose route stopped STUCK or on an exhausted rework budget with no open
                      upstream defect (the model did not converge on deterministic findings);
  UNKNOWN          <- everything else (SECURITY, unclassified, a cancelled run) - never a guessed class.
Proposals are RULE proposals derived from the records (status PROPOSED) and are never executed in M1.

Owner rule 2026-11-03 (supersedes decision 7's fixed retry budgets): the supervisor may retry as often as it needs,
as long as every new run makes progress, and a retry always resumes from the last good, quality-checked part. An
issue is the chain of one fingerprint on one part (lineage) and phase: consecutive recurrences across new runs are
its strikes (`attempts.used`); a different fingerprint or a passed phase is progress and resolves it. More than 3
strikes stops the line: ESCALATED, needs you, reason SAME_ISSUE_EXCEEDED_3. `budgets` keeps only pacing and cost
guards (never a stop reason) and `progress` names the last good part per lineage, which every retry resumes from.
Summaries are built from codes by fixed templates; no model, agent or inspector prose enters the feed.

Healthy cycles make zero model calls: the 002 model-port guard plus an allow-list socket guard (only the line's Fabro
API port) are installed and the blocked attempts are reported as `supervisor.model_calls_healthy`.

    python -m forge_factory.afo.line_conductor [--interval 30] [--once] [--launch-dir D] [--fabro-snapshot F]
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import socket
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from ..common import REPO_ROOT, state_dir

SCHEMA_ID = "forge-c/supervisor-issues/1"
SCHEMA_PATH = REPO_ROOT / "specs/014-durable-local-autonomy/contracts/supervisor-issues.schema.json"
PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")
MODE = "OBSERVE"
RESOLVED_KEEP_S = 7 * 86400  # decision 11: resolved issues stay 7 days in the feed; issues.jsonl keeps them all
LOOKBACK_S = 48 * 3600
# owner rule 2026-11-03: unlimited retries while each new run progresses; the same issue more than 3 times stops the line
STRIKE_LIMIT = 3
STRIKE_RULE = "same issue > 3 times stops the line"
STRIKE_REASON = "SAME_ISSUE_EXCEEDED_3"
# pacing and cost guards (decision 7's remaining values); they pace the supervisor, they never stop the line
BUDGETS = {
    "guard_infra_recoveries_per_hour_host": 6,
    "guard_infra_cooldown_s": 600,
    "guard_planner_calls_per_order": 4,
    "guard_planner_tokens_per_order": 200_000,
    "guard_phase_order_wall_s": 6 * 3600,
}
ENDED = ("succeeded", "failed", "cancelled", "canceled", "aborted", "dead")
WO_RX = re.compile(r"^WO-(?:F\d+-)?(?:CMP-)?SWE(\d)-([A-Z0-9]+)-(\d{8})-([A-Za-z0-9]+)$")
CONVERGENCE_RX = re.compile(r"^\s*(STUCK\b|rework budget exhausted)", re.I)
# deterministic markers of the line launcher (Omniverse2 launch-generic-model.sh, M0); first marker in file order wins
LAUNCH_RULES = [(re.compile(p), code) for p, code in [
    (r"OWN llama-server still running after stop", "STACK_STOP_INCOMPLETE"),
    (r"STACK NOT HEALTHY", "READINESS_FAILURE"),
    (r"STACK START \([^)]*\) rc [1-9]", "STACK_START_FAILED"),
    (r"SMOKE FAIL", "MODEL_SMOKE_FAILED"),
    (r"CODE NOT AT", "CODE_REVISION_MISMATCH"),
    (r"GUARD FAIL", "LAUNCH_GUARD_FAILED"),
    (r"GPU_LOCK_HELD", "GPU_LOCK_HELD"),
    (r"RUN_LIVE", "RUN_LIVE"),
    (r"\bLAUNCH WO-\S+ rc [1-9]", "WORKORDER_LAUNCH_FAILED"),  # the code itself: workorder-launch-<WO>.log
]]
STACK_CODES = {"STACK_STOP_INCOMPLETE", "READINESS_FAILURE", "STACK_START_FAILED", "MODEL_SMOKE_FAILED"}
# the work-order CLI's own refusal, last exception line of workorder-launch-<WO>.log, e.g.
# "FileNotFoundError: PROVIDED_LL_MISSING:WO-F014-SWE6-CRCL-20261103-L24::no work order workspace"
EXC_RX = re.compile(r"^\w+(?:Error|Exception): ([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)(?::(\S*))?")
REF_WO_RX = re.compile(r"(WO-[A-Za-z0-9-]+[:;,.]*)")
_CODE_BAD = re.compile(r"[^A-Za-z0-9_.:/=-]+")
_REF_OK = re.compile(r"^[A-Za-z0-9_.:/#@+=-]{1,300}$")
_TOKEN_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/+-]{0,127}$")


# ---------------------------------------------------------------------------------------------------------- helpers
def _utc(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _ts(s) -> float | None:
    import datetime as dt

    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _code(s: str) -> str:
    return (_CODE_BAD.sub("_", str(s)).strip("_") or "UNCLASSIFIED")[:160]


def _ref(s: str) -> str | None:
    s = str(s).replace(" ", "_")
    return s if _REF_OK.match(s) else None


def _token(s) -> str | None:
    return str(s) if s and _TOKEN_OK.match(str(s)) else None


def _h(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def supervisor_dir() -> Path:
    return state_dir() / "supervisor"


def feed_path() -> Path:
    return supervisor_dir() / "issues.json"


def journal_path() -> Path:
    return supervisor_dir() / "issues.jsonl"


def acks_path() -> Path:
    return supervisor_dir() / "acks.jsonl"


def heartbeat_path() -> Path:
    return supervisor_dir() / "line-conductor.heartbeat"


@contextmanager
def feed_lock():
    """Serializes the conductor's cycle write and the owner's ack CLI (the only two writers of the feed)."""
    d = supervisor_dir()
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "feed.lock", "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def atomic_write(p: Path, data: bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(tmp, p)  # a reader sees the old or the new feed, never a half-written one
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def append_jsonl(p: Path, rec: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "ab") as f:
        f.write(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode() + b"\n")
        f.flush()
        os.fsync(f.fileno())


_VALIDATOR = None


def validator():
    """The contract validator (None when the schema file is not in this checkout)."""
    global _VALIDATOR
    if _VALIDATOR is None and SCHEMA_PATH.is_file():
        import jsonschema

        _VALIDATOR = jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
    return _VALIDATOR


def contract_keys() -> tuple[set, set, set] | None:
    """The fields the installed contract declares (top level, attempts, escalation); None without a contract."""
    v = validator()
    if v is None:
        return None
    issue = v.schema["$defs"]["issue"]["properties"]
    return set(v.schema["properties"]), set(issue["attempts"]["properties"]), set(issue["escalation"]["properties"])


def fit_issue(i: dict, keys: tuple[set, set, set] | None) -> dict:
    """Drop the fields an older installed contract does not declare yet (attempts.rule, escalation.reason): the feed
    always validates against the contract that is deployed with it."""
    if keys is None:
        return i
    return {**i, "attempts": {k: v for k, v in i["attempts"].items() if k in keys[1]},
            "escalation": {k: v for k, v in i["escalation"].items() if k in keys[2]}}


def feed_errors(feed: dict) -> list[str]:
    v = validator()
    if v is None:
        return ["SCHEMA_UNAVAILABLE"]
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:200] for e in v.iter_errors(feed)]


# ------------------------------------------------------------------------------------------------------- the guard
GUARD = {"blocked": 0}
_saved_connect = None


def install_guard(allowed_ports: set[int]) -> None:
    """The 002 supervisor's model-port guard, then an allow-list on top: in OBSERVE the conductor talks to the line's
    Fabro API only (plus AF_UNIX for sd_notify). Any other TCP connect is blocked and counted."""
    global _saved_connect
    from ..supervisor.service import install_model_guard

    if _saved_connect is None:
        _saved_connect = socket.socket.connect
    install_model_guard()
    inner = socket.socket.connect

    def connect(self, address):  # type: ignore[no-untyped-def]
        if self.family in (socket.AF_INET, socket.AF_INET6):
            port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
            if port not in allowed_ports:
                GUARD["blocked"] += 1
                raise PermissionError(f"line conductor guard: port {port} is not the line's Fabro API")
        return inner(self, address)

    socket.socket.connect = connect  # type: ignore[method-assign]


def uninstall_guard() -> None:
    global _saved_connect
    if _saved_connect is not None:
        socket.socket.connect = _saved_connect  # type: ignore[method-assign]
        _saved_connect = None


def model_calls() -> int:
    from ..supervisor.service import MODEL_CALLS

    return GUARD["blocked"] + MODEL_CALLS["blocked_attempts"]


# ------------------------------------------------------------------------------------------------------ Fabro view
class FabroView:
    """Read-only Fabro run status ('running', 'succeeded:completed', 'failed:cancelled', ...); None when unknown.
    Live through the line's Fabro API, or from a recorded snapshot {run_id: status} for an offline replay."""

    def __init__(self, url: str | None = None, token: str | None = None, snapshot: dict | None = None):
        self.url, self.token, self.snapshot, self._ended = url, token, snapshot, {}

    @classmethod
    def from_env(cls, snapshot_file: str | None = None) -> FabroView:
        if snapshot_file:
            return cls(snapshot=json.loads(Path(snapshot_file).read_text()))
        from ..fabro.client import load_token

        url = os.environ.get("FORGE_LINE_FABRO_URL") or os.environ.get("FORGE_FABRO_URL")
        return cls(url=url, token=load_token(os.environ.get("FORGE_LINE_FABRO_STORAGE")))

    def port(self) -> int | None:
        if not self.url:
            return None
        u = urlparse(self.url)
        return u.port or (443 if u.scheme == "https" else 80)

    def status(self, run_id: str | None) -> str | None:
        if not run_id:
            return None
        if self.snapshot is not None:
            return self.snapshot.get(run_id)
        if run_id in self._ended:
            return self._ended[run_id]
        if not self.url:
            return None
        from ..fabro.client import FabroClient

        try:
            with FabroClient(base_url=self.url, token=self.token, timeout=4) as c:
                st = (c.get_run(run_id).get("lifecycle") or {}).get("status") or {}
        except Exception:  # noqa: BLE001 - an unreachable Fabro leaves the status unknown, never a verdict
            return None
        kind = st.get("kind") if isinstance(st, dict) else st
        out = f"{kind}:{st['reason']}" if isinstance(st, dict) and st.get("reason") else str(kind)
        if str(kind) in ENDED:
            self._ended[run_id] = out
        return out


# ------------------------------------------------------------------------------------------------- the records
def _gate_log(ws: Path) -> list[dict]:
    out = []
    p = ws / ".forge-run/gates/gate-log.jsonl"
    for n, line in enumerate(p.read_text(errors="replace").splitlines() if p.is_file() else [], 1):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            e["_line"] = n
            out.append(e)
    return out


def _result(e: dict) -> str | None:
    return e.get("result") or (e.get("gate") or {}).get("decision")


def parse_wo(wo: str) -> tuple[str | None, str | None]:
    """(phase, part tag) from a work-order name, e.g. WO-F014-SWE6-IWDGHAL-20261103-L22 -> (SWE.6, IWDGHAL)."""
    m = WO_RX.match(wo or "")
    return (f"SWE.{m.group(1)}", m.group(2)) if m else (None, None)


def scan_orders(root: Path, now: float, lookback_s: float) -> list[dict]:
    out = []
    for ws in sorted((root / "workorders").glob("*/workspace")):
        run = ws / ".forge-run"
        man = _load(run / "manifest.json")
        if not isinstance(man, dict):
            continue
        marks = [run / "gates/gate-log.jsonl", run / "fabro_run_id", run / "package.json", run / "manifest.json"]
        mt = [p.stat().st_mtime for p in marks if p.is_file()]
        if not mt or now - max(mt) > lookback_s:
            continue
        wo = man.get("work_order") or ws.parent.name
        ph, tag = parse_wo(wo)
        target = (man.get("phase_scope") or {}).get("stop_after") or ph or "SWE.6"
        log = _gate_log(ws)
        passed = {e.get("phase") for e in log if e.get("step") == "inspect" and _result(e) == "PASS"}
        rid = (run / "fabro_run_id").read_text().strip() if (run / "fabro_run_id").is_file() else None
        out.append({"wo": wo, "ws": ws, "rel": f"workorders/{ws.parent.name}/workspace", "tag": tag or "UNKNOWN",
                    "phase": target if target in PHASES else "SWE.6", "created": _ts(man.get("created_at")) or min(mt),
                    "rid": rid, "package": _load(run / "package.json"), "log": log, "passed": passed,
                    "source": (man.get("resumed_from") or {}).get("source_work_order"),
                    "sig": (tuple(round(x, 3) for x in mt), len(log))})
    return out


def scan_launches(launch_dir: Path | None, now: float, lookback_s: float) -> list[dict]:
    """Failed launches: a launch record with a failure marker and no 'LAUNCH <wo> rc 0' line with a Fabro run id."""
    out = []
    if launch_dir is None or not launch_dir.is_dir():
        return out
    for p in sorted(launch_dir.glob("launch-WO-*.out")):
        try:
            st = p.stat()
            if now - st.st_mtime > lookback_s:
                continue
            lines = p.read_text(errors="replace").splitlines()
        except OSError:
            continue
        wo = p.name.removeprefix("launch-").removesuffix(".out")
        if any(re.search(rf"\bLAUNCH {re.escape(wo)} rc 0\b.*\"fabro_run_id\": \"[A-Z0-9]+\"", x) for x in lines):
            continue
        hit = None
        for n, line in enumerate(lines, 1):
            hit = next(((code, n) for rx, code in LAUNCH_RULES if rx.search(line)), None)
            if hit:
                break
        if hit is None:
            continue  # still launching, or no recognised marker
        ts = next((t for t in (_ts(x.split(" ", 1)[0]) for x in lines[hit[1] - 1:hit[1]]) if t), None)
        ph, tag = parse_wo(wo)
        rec = {"wo": wo, "tag": tag or "UNKNOWN", "phase": ph or "-", "code": hit[0], "line": hit[1],
               "created": ts or st.st_mtime, "refs": [f"launch:{p.name}#{hit[1]}"], "ref_wo": None}
        if hit[0] == "WORKORDER_LAUNCH_FAILED":
            wl = launch_dir / f"workorder-launch-{wo}.log"
            try:
                wlines = wl.read_text(errors="replace").splitlines()
            except OSError:
                wlines = []
            for n in range(len(wlines), 0, -1):
                m = EXC_RX.match(wlines[n - 1].strip())
                if m:
                    rec["code"] = m.group(1)
                    rec["refs"].append(f"launch:{wl.name}#{n}")
                    r = REF_WO_RX.search(m.group(2) or "")
                    rec["ref_wo"] = r.group(1) if r else None
                    break
        out.append(rec)
    return out


def _ro(path: Path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)


def read_cre(db: Path) -> dict:
    """Open CAPAs (fingerprint -> CAPA id) and active 002 incidents, read-only; an absent or unreadable db is empty."""
    from .bundle import CAPA_OPEN

    out = {"capa_of": {}, "incidents": []}
    if not db.is_file():
        return out
    try:
        c = _ro(db)
    except sqlite3.Error:
        return out
    try:
        try:
            open_ids = {r[0] for r in c.execute("SELECT capa_id, state FROM cre_capa") if r[1] in CAPA_OPEN}
            for cid, ref in c.execute("SELECT capa_id, ref FROM cre_capa_links WHERE kind='FINGERPRINT' ORDER BY seq"):
                if cid in open_ids:
                    out["capa_of"].setdefault(ref, cid)
        except sqlite3.Error:
            pass
        try:
            for r in c.execute("SELECT incident_id, fingerprint, component, fault_type, state, created_at, updated_at, "
                               "attempts, run_id FROM incidents WHERE active=1"):
                out["incidents"].append(dict(zip(("incident_id", "fingerprint", "component", "fault_type", "state",
                                                  "created_at", "updated_at", "attempts", "run_id"), r, strict=True)))
        except sqlite3.Error:
            pass
    finally:
        c.close()
    return out


def read_afo_queue(db: Path, now: float, lookback_s: float) -> list[dict]:
    """AFO queue orders that need attention (read-only): WAITING_EXTERNAL_CHANGE, WAITING_RECOVERY, BLOCKED."""
    if not db.is_file():
        return []
    try:
        c = _ro(db)
    except sqlite3.Error:
        return []
    try:
        rows = c.execute("SELECT order_id, state, created_epoch, terminal_reason FROM afo_work_orders WHERE state IN "
                         "('WAITING_EXTERNAL_CHANGE','WAITING_RECOVERY','BLOCKED')").fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        c.close()
    return [{"order_id": r[0], "state": r[1], "created": r[2], "reason": r[3] or ""} for r in rows
            if now - float(r[2] or 0) <= lookback_s]


# ---------------------------------------------------------------------------------------------- classification
def _codes(rec: dict, phase: str) -> tuple[list[str], int | None, str]:
    """The deterministic issue codes of the last author rejection before the phase's BLOCKED route, the BLOCKED
    line, and the route code (STUCK / REWORK_BUDGET_EXHAUSTED / BLOCKED)."""
    from ..reliability.taxonomy import classify

    blocked = [e for e in rec["log"] if e.get("phase") == phase and e.get("step") == "route" and _result(e) == "BLOCKED"]
    if not blocked:
        return [], None, ""
    b = blocked[-1]
    reason = str((b.get("gate") or {}).get("reason") or "")
    route = "STUCK" if reason.upper().startswith("STUCK") else \
        "REWORK_BUDGET_EXHAUSTED" if "budget exhausted" in reason.lower() else "BLOCKED"
    rej = [e for e in rec["log"] if e.get("phase") == phase and e.get("step") == "author" and e["_line"] < b["_line"]
           and _result(e) in ("REJECTED", "FREEZE_FAILED")]
    codes: list[str] = []
    for i in ((rej[-1].get("issues") or []) if rej and rej[-1].get("status") == "INCOMPLETE" else []):
        c = _code(classify(str(i)).error_code)
        if c not in codes:
            codes.append(c)
    return codes[:5], b["_line"], route


def classify_order(rec: dict, life: str | None, capa_of: dict) -> dict | None:
    """The issue core of one ended order that did not reach its target phase; None when it passed or still runs."""
    from ..inspection import defects
    from .bundle import blocked_phase, build

    if rec["phase"] in rec["passed"]:
        return None
    kind = (life or "").split(":")[0]
    if rec["package"] is None and kind not in ENDED:
        return None  # running (the wall budget is checked by the caller)
    ws, phase = rec["ws"], rec["phase"]
    ev = [{"kind": "manifest", "ref": f"{rec['rel']}/.forge-run/manifest.json"}]
    if rec["package"] is not None:
        ev.append({"kind": "package", "ref": f"{rec['rel']}/.forge-run/package.json"})
    if rec["rid"]:
        ev.append({"kind": "fabro_run", "ref": f"fabro:runs/{rec['rid']}"})
    bphase, reason = blocked_phase(ws)
    if bphase is None and life and life.split(":")[-1] in ("cancelled", "canceled"):
        return {"class": "UNKNOWN", "phase": phase, "error_code": "FABRO_RUN_CANCELLED", "route": "CANCELLED",
                "codes": [], "fingerprint": "sup1-" + _h("FABRO_RUN_CANCELLED", rec["tag"], phase)[:40],
                "evidence": ev, "status": "PARKED", "capa": None}
    err = "ENDED_BEFORE_TARGET_PHASE"
    try:
        b = build(ws, rec["wo"], rec["wo"], open_capa=set(capa_of), run_failed=True)
    except Exception as exc:  # noqa: BLE001 - an unreadable record is UNKNOWN, never a guessed class
        b, err = None, f"CLASSIFIER_ERROR:{type(exc).__name__}"
    if b is None:
        return {"class": "UNKNOWN", "phase": phase, "error_code": err,
                "route": "ENDED", "codes": [], "fingerprint": "sup1-" + _h("ENDED", rec["tag"], phase)[:40],
                "evidence": ev, "status": "ESCALATED", "capa": None}
    ph = b["phase"] if b["phase"] in PHASES else phase
    codes, line, route = _codes(rec, ph)
    if line:
        ev.insert(0, {"kind": "gate_log", "ref": f"{rec['rel']}/.forge-run/gates/gate-log.jsonl#{line}"})
    for r in b.get("evidence_refs", [])[-3:]:
        if r.startswith("cre-observation:"):
            ev.append({"kind": "cre_observation", "ref": r})
    for r in b.get("artifact_refs", [])[:1]:
        ev.append({"kind": "inspection_record", "ref": f"{rec['rel']}/{r.removeprefix('workspace:')}"})
    c = b["failure_class"]
    up = []
    if c == "PRODUCT_QUALITY":
        try:
            up = defects.open_from(ws, ph)
        except Exception:  # noqa: BLE001
            up = []
        if up:
            ev.append({"kind": "defect_register", "ref": f"{rec['rel']}/.forge-run/defects"})
    cls = ("INFRA" if c in ("INFRASTRUCTURE", "TRANSIENT_DEPENDENCY") else "FACTORY_DEFECT" if c == "FACTORY_CODE_DEFECT"
           else "PRODUCT" if c == "SPECIFICATION_GAP" or (c == "PRODUCT_QUALITY" and (up or not CONVERGENCE_RX.match(reason)))
           else "MODEL_CONVERGENCE" if c == "PRODUCT_QUALITY" else "UNKNOWN")
    capa = capa_of.get(b["fingerprint"])
    if capa:
        ev.append({"kind": "capa", "ref": f"capa:{capa}"})
    # the issue's identity across runs: the deterministic code set of the blocking rejection (the CRE bundle's dominant
    # observation is tie-broken by an attempt-specific id, so its cfp1 can differ between runs of the same rejection)
    fp = "sup1-" + _h("CODES", ph, route, *sorted(codes))[:40] if codes else b["fingerprint"]
    return {"class": cls, "phase": ph, "error_code": _code(b["error_code"]), "route": route or "ENDED", "codes": codes,
            "fingerprint": fp, "cre_fingerprint": b["fingerprint"], "evidence": ev, "upstream": sorted({d["target_phase"] for d in up}),
            "status": {"FACTORY_DEFECT": "WAITING_EXTERNAL_CHANGE", "UNKNOWN": "ESCALATED"}.get(cls, "OPEN"),
            "capa": capa}


SUMMARY = {
    "MODEL_CONVERGENCE": "{phase} {route}: no convergence on deterministic findings; codes {codes}",
    "PRODUCT": "{phase} {route}: product finding; codes {codes}",
    "INFRA": "{phase} {route}: infrastructure; code {error_code}",
    "FACTORY_DEFECT": "{phase} {route}: factory defect under CAPA {capa}; code {error_code}",
    "UNKNOWN": "{phase} {route}: unclassified; code {error_code}",
    "CANCELLED": "{phase} Fabro run cancelled (failed:cancelled); parked until released",
    "LAUNCH": "{phase} launch failed before a Fabro run: {error_code}",
    "INCIDENT": "002 incident {error_code} on {component}",
    "AFO": "AFO order {state}: {error_code}",
    "WALL": "{phase} order over the 6 h phase wall budget",
}


def summary(kind: str, **kw) -> str:
    from .bundle import redact

    kw.setdefault("codes", "-")
    if isinstance(kw.get("codes"), list):
        kw["codes"] = ", ".join(kw["codes"]) or kw.get("error_code", "-")
    s = redact(SUMMARY[kind].format_map({k: v if v is not None else "-" for k, v in kw.items()}))
    return re.sub(r"[^A-Za-z0-9 _.:;,/()+=#@<>-]+", "_", s)[:240]


# ---------------------------------------------------------------------------------------------- RULE proposals
def _proposal(issue_id: str, rank: int, strategy: str, reasons: list[str], text: str, **args) -> dict:
    args = {k: v for k, v in args.items() if v is not None}
    return {"proposal_id": "SUPP-" + _h(issue_id, strategy, json.dumps(args, sort_keys=True))[:12], "source": "RULE",
            "strategy": strategy, "status": "PROPOSED", "rank": rank, "args": args,
            "summary": re.sub(r"[^A-Za-z0-9 _.:;,/()+=#@<>-]+", "_", text)[:200], "reason_codes": reasons[:8],
            "cre_decision_ref": None}


def last_passed_order(orders: list[dict], tag: str, phase: str, before: float) -> str | None:
    """The newest order of this part that passed the phase before `phase`, created before `before`."""
    i = PHASES.index(phase) if phase in PHASES else 0
    if i == 0:
        return None
    prev = PHASES[i - 1]
    cand = [o for o in orders if o["tag"] == tag and prev in o["passed"] and o["created"] <= before]
    return max(cand, key=lambda o: o["created"])["wo"] if cand else None


def rule_proposals(issue_id: str, cls: str, phase: str, *, resume_from: str | None, upstream: list[str],
                   capa: str | None, kind: str, code: str = "", provided: tuple[str | None, str] | None = None,
                   strikes: int = 1) -> list[dict]:
    """RULE proposals (never executed in M1). Every retry names the last good, quality-checked order it resumes from
    (`resume_from`; None only for SWE.1, which has no earlier part)."""
    ph = phase if phase in PHASES else None
    src = resume_from or "a fresh order (no earlier quality-checked part)"

    def retry(rank: int, reasons: list[str]) -> dict:
        return _proposal(issue_id, rank, "RETRY_PHASE_FROM_LAST_PASSED_ORDER", reasons + ["RESUME_FROM_LAST_GOOD_PART"],
                         f"retry {phase} from {src}", phase=ph, resume_from=resume_from)

    if strikes > STRIKE_LIMIT:
        return [_proposal(issue_id, 1, "STOP_LINE_REQUEST_OWNER", [STRIKE_REASON], f"stop the line: the same issue "
                          f"{strikes} times; resume {phase} from {src} after the owner decision", phase=ph,
                          resume_from=resume_from)]
    if kind == "CANCELLED":
        return [_proposal(issue_id, 1, "RESUME_PHASE_FROM_LAST_PASSED_ORDER", ["FABRO_RUN_CANCELLED",
                          "OWNER_RELEASE_REQUIRED", "RESUME_FROM_LAST_GOOD_PART"],
                          f"resume {phase} from {src} when released", phase=ph, resume_from=resume_from)]
    if kind == "WALL":
        return [_proposal(issue_id, 1, "CHECK_ORDER_LIVENESS", ["PHASE_WALL_GUARD"], f"check the {phase} run is alive "
                          "(pacing guard, not a stop reason)", phase=ph)]
    if kind == "LAUNCH" and provided:
        good, _raw = provided
        if good:
            return [_proposal(issue_id, 1, "RELAUNCH_WITH_CORRECTED_PROVIDED_FROM", ["PROVIDED_FROM_NAME_INVALID",
                              "CORRECTED_NAME_EXISTS"], f"relaunch {phase} with --provided-from {good}", phase=ph,
                              provided_from=good)]
        return [_proposal(issue_id, 1, "ESCALATE_TO_OWNER", ["PROVIDED_SOURCE_NOT_FOUND"],
                          "provided-from source not in the line state; owner decision needed")]
    if kind == "LAUNCH":
        relaunch = _proposal(issue_id, 2 if code in STACK_CODES else 1, "RELAUNCH_PHASE_FROM_LAST_PASSED_ORDER",
                             ["LAUNCH_FAILED_BEFORE_RUN" if code in STACK_CODES else "LAUNCH_REFUSED",
                              "RESUME_FROM_LAST_GOOD_PART"], f"relaunch {phase} from {src}", phase=ph,
                             resume_from=resume_from)
        if code not in STACK_CODES:
            return [relaunch]
        return [_proposal(issue_id, 1, "STACK_REPAIR_RECIPE", ["LAUNCH_FAILED_BEFORE_RUN"],
                          "stack stop, stop own orphaned stack processes, stack start, health check",
                          recipe="stack-repair-v1"), relaunch]
    if cls == "FACTORY_DEFECT":
        p = _proposal(issue_id, 1, "FOLLOW_CAPA", ["FACTORY_DEFECT_NEEDS_EXTERNAL_CHANGE", "RESUME_FROM_LAST_GOOD_PART"],
                      f"wait for the CRE fix of {capa}, then retry {phase} from {src}", capa_id=capa, phase=ph,
                      resume_from=resume_from)
        p["cre_decision_ref"] = _ref(f"capa:{capa}") if capa else None
        return [p]
    if cls == "INFRA":
        return [_proposal(issue_id, 1, "STACK_REPAIR_RECIPE", ["INFRASTRUCTURE"], "stack health check and repair",
                          recipe="stack-repair-v1"), retry(2, ["INFRASTRUCTURE"])]
    if cls == "PRODUCT" and upstream:
        return [_proposal(issue_id, 1, "RETURN_TO_OWNING_UPSTREAM_PHASE", ["OPEN_UPSTREAM_DEFECT"],
                          f"return to {upstream[0]} (open upstream defect)", phase=upstream[0])]
    if cls in ("MODEL_CONVERGENCE", "PRODUCT"):
        return [retry(1, ["STUCK_OR_REWORK_BUDGET" if cls == "MODEL_CONVERGENCE" else "PRODUCT_REWORK",
                          f"SAME_ISSUE_STRIKE:{strikes}"]),
                _proposal(issue_id, 2, "PROPOSE_VALIDATED_LESSON", ["LESSON_NEEDS_DETERMINISTIC_VALIDATION"],
                          f"lesson for {phase} authors from these codes, validated before it is shared", phase=ph)]
    return [retry(1, ["UNCLASSIFIED", f"SAME_ISSUE_STRIKE:{strikes}"])]


# ------------------------------------------------------------------------------------------------- the cycle
def _issue(line: str, *, wo, tag, phase, rid, cls, fingerprint, error_code, text, evidence, proposals, status, used,
           opened, lineage, now, key: str | None = None) -> dict:
    """`key` names the issue's chain (part|phase): the same fingerprint there is the same issue across runs."""
    iid = "SUP-" + _h(line, key or wo or "-", fingerprint)[:10]
    for p in proposals:  # the proposal ids are bound to the issue
        p["proposal_id"] = "SUPP-" + _h(iid, p["strategy"], json.dumps(p["args"], sort_keys=True))[:12]
    level = "NEEDS_OWNER" if status == "ESCALATED" else "FLOOR"
    return {"issue_id": iid, "line": line, "lineage": _token(lineage) or _token(tag) or "UNKNOWN", "wo": _token(wo),
            "phase": phase if phase in PHASES else "-", "fabro_run_id": _token(rid), "class": cls,
            "fingerprint": fingerprint, "error_code": _code(error_code), "summary": text,
            "evidence": [e for e in ({"kind": x["kind"], "ref": _ref(x["ref"])} for x in evidence) if e["ref"]][:24],
            "proposals": proposals[:8], "status": status,
            "attempts": {"used": int(used), "limit": STRIKE_LIMIT, "rule": STRIKE_RULE},
            "escalation": {"level": level, "at": _utc(opened), "acknowledged": False, "acknowledged_at": None,
                           "acknowledged_by": None, "ack_ref": None, "reason": None},
            "opened_at": _utc(opened), "updated_at": _utc(now), "resolved_at": None}


def _lineage(orders_by_wo: dict, rec: dict) -> str:
    """'<part tag>/<root work order>': the resume chain followed back as far as the line state records it."""
    cur, seen = rec, {rec["wo"]}
    while cur.get("source"):
        nxt = orders_by_wo.get(cur["source"])
        if nxt is None or nxt["wo"] in seen:
            return f"{rec['tag']}/{cur['source']}"
        seen.add(nxt["wo"])
        cur = nxt
    return f"{rec['tag']}/{cur['wo']}"


def _later(orders: list[dict], tag: str, phase: str, after: float, *, launched: bool) -> tuple[str | None, str | None]:
    """('RESOLVED'|'RECOVERING', the order) when a later order of the part passed this phase (or a later one), or -
    for a launch failure - simply launched; a later order still running on the phase is a recovery under way."""
    i = PHASES.index(phase) if phase in PHASES else 0
    later = sorted((o for o in orders if o["tag"] == tag and o["created"] > after), key=lambda o: o["created"])
    for o in later:
        if any(p in o["passed"] for p in PHASES[i:]):
            return "RESOLVED", o["wo"]
    if launched:
        for o in later:
            if o["phase"] == phase and o["rid"]:
                return "RESOLVED", o["wo"]
    for o in later:
        if o["phase"] == phase and o["package"] is None:
            return "RECOVERING", o["wo"]
    return None, None


def line_progress(orders: list[dict]) -> list[dict]:
    """The last good part per lineage (part): the furthest phase whose inspection gate PASSED, in the newest order that
    passed it - what every retry resumes from (owner rule 2026-11-03)."""
    best: dict[str, tuple] = {}
    for o in orders:
        for e in o["log"]:
            if e.get("step") != "inspect" or _result(e) != "PASS" or e.get("phase") not in PHASES:
                continue
            k = (PHASES.index(e["phase"]), o["created"])
            if o["tag"] not in best or k > best[o["tag"]][0]:
                t = _ts(e.get("ts"))
                best[o["tag"]] = (k, {"lineage": o["tag"], "phase": e["phase"], "wo": o["wo"],
                                      "at": _utc(t) if t else None,
                                      "ref": f"{o['rel']}/.forge-run/gates/gate-log.jsonl#{e['_line']}"})
    return [best[t][1] for t in sorted(best)]


def _resolve(iss: dict, ref: str, reason: str, now: float) -> None:
    iss["evidence"].append({"kind": "superseded_by", "ref": _ref(ref) or "-"})
    iss["evidence"] = [e for e in iss["evidence"] if e["ref"] != "-"][:24]
    iss["status"], iss["resolved_at"] = "RESOLVED", _utc(now)
    iss["escalation"].update(level="FLOOR", reason=None)
    for p in iss["proposals"]:
        p["status"] = "SUPERSEDED"
        p["reason_codes"] = (p["reason_codes"] + [reason])[:8]


class Observer:
    """One OBSERVE pass over a line's records -> the feed's issues, guards and progress (pure: writes nothing)."""

    def __init__(self, line: str = "local", launch_dir: Path | None = None, fabro: FabroView | None = None,
                 cre_db: Path | None = None, lookback_s: float = LOOKBACK_S):
        self.line, self.launch_dir, self.fabro = line, launch_dir, fabro or FabroView()
        self.cre_db, self.lookback_s = cre_db, lookback_s
        self._cache: dict = {}
        self.progress: list[dict] = []

    def _core(self, rec: dict, life: str | None, capa_of: dict) -> dict | None:
        key = (rec["wo"], rec["sig"], life, tuple(sorted(capa_of)))
        if key not in self._cache:
            self._cache = {k: v for k, v in self._cache.items() if k[0] != rec["wo"]}
            self._cache[key] = classify_order(rec, life, capa_of)
        return self._cache[key]

    def issues(self, now: float) -> tuple[list[dict], dict]:
        from ..reliability.taxonomy import classify, fingerprint

        root = state_dir()
        orders = scan_orders(root, now, self.lookback_s)
        by_wo = {o["wo"]: o for o in orders}
        cre = read_cre(self.cre_db or root / "supervisor/incidents.sqlite3")
        out: list[dict] = []
        wall_used = 0.0
        # every run of a part and phase is an event of its chain: PASS (progress) or the fingerprint it stopped on
        chains: dict[tuple, list[tuple]] = {}
        drafts: list[dict] = []
        for rec in orders:
            life = self.fabro.status(rec["rid"]) if rec["package"] is None else None
            core = self._core(rec, life, cre["capa_of"])
            ref = f"workorders/{rec['wo']}"
            for ph in rec["passed"]:
                chains.setdefault((rec["tag"], ph), []).append((rec["created"], "PASS", ref))
            if core is not None:
                chains.setdefault((rec["tag"], core["phase"]), []).append((rec["created"], core["fingerprint"], ref))
                drafts.append({"rec": rec, "core": core, "tag": rec["tag"], "phase": core["phase"],
                               "fp": core["fingerprint"], "created": rec["created"], "ref": ref})
                continue
            kind = (life or "").split(":")[0]
            if rec["package"] is None and rec["phase"] not in rec["passed"] and kind not in ENDED:
                wall_used = max(wall_used, now - rec["created"])
                if now - rec["created"] > BUDGETS["guard_phase_order_wall_s"]:  # a pacing guard, not a stop reason
                    out.append(_issue(self.line, wo=rec["wo"], tag=rec["tag"], phase=rec["phase"], rid=rec["rid"],
                                      cls="UNKNOWN", fingerprint="sup1-" + _h("WALL", rec["wo"])[:40],
                                      error_code="PHASE_WALL_GUARD_EXCEEDED", text=summary("WALL", phase=rec["phase"]),
                                      evidence=[{"kind": "manifest", "ref": f"{rec['rel']}/.forge-run/manifest.json"}],
                                      proposals=rule_proposals("x", "UNKNOWN", rec["phase"], resume_from=None,
                                                               upstream=[], capa=None, kind="WALL"),
                                      status="OPEN", used=1, opened=rec["created"], lineage=_lineage(by_wo, rec),
                                      now=now))
        for la in scan_launches(self.launch_dir, now, self.lookback_s):
            fp = fingerprint("INFRASTRUCTURE", "line-launcher", la["code"], f"{la['phase']}/launch")
            ref = la["refs"][0].split("#")[0]
            chains.setdefault((la["tag"], la["phase"]), []).append((la["created"], fp, ref))
            drafts.append({"la": la, "tag": la["tag"], "phase": la["phase"], "fp": fp, "created": la["created"], "ref": ref})
        groups: dict[tuple, list[dict]] = {}
        for d in drafts:  # the same issue = the same fingerprint on the same part and phase, across runs
            groups.setdefault((d["tag"], d["phase"], d["fp"]), []).append(d)
        for (tag, phase, fp), ds in groups.items():
            ds.sort(key=lambda d: d["created"])
            last = ds[-1]
            chain = sorted(chains[(tag, phase)], key=lambda e: e[0])
            i = max(n for n, e in enumerate(chain) if e[1] == fp and e[2] == last["ref"])
            strikes, first = 0, last["created"]
            for e in reversed(chain[:i + 1]):  # consecutive recurrences; a pass or another issue is progress
                if e[1] != fp:
                    break
                strikes, first = strikes + 1, e[0]
            resume = last_passed_order(orders, tag, phase, float("inf")) if phase in PHASES else None
            iss = self._draft_issue(last, root, now, by_wo, resume=resume, strikes=strikes, opened=first)
            earlier = [d for d in ds[:-1] if d["created"] >= first][-3:]
            iss["evidence"] = (iss["evidence"] + [{"kind": "launch_log" if d["ref"].startswith("launch:") else "manifest",
                                                   "ref": _ref(d["ref"] if d["ref"].startswith("launch:") else
                                                               f"{d['ref']}/workspace/.forge-run/manifest.json")}
                                                  for d in earlier])[:24]
            nxt = chain[i + 1] if i + 1 < len(chain) else None
            if nxt is not None:
                _resolve(iss, nxt[2], "RESOLVED_BY_PROGRESS" if nxt[1] == "PASS" else "PROGRESS_NEW_ISSUE", now)
            else:
                st, by = _later(orders, tag, phase, last["created"], launched="la" in last)
                if st == "RESOLVED":
                    _resolve(iss, f"workorders/{by}", "RESOLVED_BY_LATER_ORDER", now)
                elif st == "RECOVERING":
                    iss["evidence"].append({"kind": "superseded_by", "ref": f"workorders/{by}"})
                    iss["status"] = "RECOVERING"
            if iss["status"] != "RESOLVED" and strikes > STRIKE_LIMIT:
                iss["status"] = "ESCALATED"
                iss["escalation"].update(level="NEEDS_OWNER", at=_utc(last["created"]), reason=STRIKE_REASON)
            out.append(iss)
        for inc in cre["incidents"]:
            n = int(inc["attempts"] or 0)
            iss = _issue(self.line, wo=None, tag="LINE", phase="-", rid=inc.get("run_id"), cls="INFRA",
                         fingerprint="sup1-" + _h("INCIDENT", inc["fingerprint"])[:40], error_code=inc["fault_type"],
                         text=summary("INCIDENT", error_code=_code(inc["fault_type"]), component=_code(inc["component"])),
                         evidence=[{"kind": "incident", "ref": f"incident:{inc['incident_id']}"}],
                         proposals=rule_proposals("x", "INFRA", "-", resume_from=None, upstream=[], capa=None,
                                                  kind="INFRA", strikes=n)[:1],
                         status="ESCALATED" if n > STRIKE_LIMIT else "OPEN", used=n,
                         opened=_ts(inc["created_at"]) or now, lineage="LINE", now=now)
            if n > STRIKE_LIMIT:
                iss["escalation"].update(level="NEEDS_OWNER", reason=STRIKE_REASON)
            out.append(iss)
        for q in read_afo_queue(root / "conductor/conductor.sqlite3", now, self.lookback_s):
            c = classify(q["reason"])
            cls = "FACTORY_DEFECT" if q["state"] == "WAITING_EXTERNAL_CHANGE" else \
                "INFRA" if c.failure_class in ("INFRASTRUCTURE", "TRANSIENT_DEPENDENCY") else "UNKNOWN"
            st = {"WAITING_EXTERNAL_CHANGE": "WAITING_EXTERNAL_CHANGE", "WAITING_RECOVERY": "RECOVERING"}.get(q["state"], "OPEN")
            out.append(_issue(self.line, wo=q["order_id"], tag="AFO", phase="-", rid=None, cls=cls,
                              fingerprint="sup1-" + _h("AFO", q["order_id"], q["state"])[:40],
                              error_code=_code(f"AFO_{q['state']}:{c.error_code}"),
                              text=summary("AFO", state=q["state"], error_code=_code(c.error_code)),
                              evidence=[{"kind": "afo_order", "ref": f"afo:{q['order_id']}"}], proposals=[],
                              status=st, used=1, opened=float(q["created"] or now), lineage="AFO", now=now))
        self.progress = line_progress(orders)
        return out, self.budgets(out, now, wall_used)

    def _draft_issue(self, d: dict, root: Path, now: float, by_wo: dict, *, resume, strikes: int, opened: float) -> dict:
        tag, phase = d["tag"], d["phase"]
        if "la" in d:
            la = d["la"]
            provided = None
            if la["ref_wo"]:  # a source order named in the refusal; strip trailing punctuation, check it exists
                good = la["ref_wo"].rstrip(":;,.")
                ok = good != la["ref_wo"] and (root / "workorders" / good / "workspace").is_dir()
                provided = (good if ok else None, la["ref_wo"])
            return _issue(self.line, wo=la["wo"], tag=tag, phase=phase, rid=None, cls="INFRA", fingerprint=d["fp"],
                          error_code=la["code"], text=summary("LAUNCH", phase=phase, error_code=la["code"]),
                          evidence=[{"kind": "launch_log", "ref": r} for r in la["refs"]],
                          proposals=rule_proposals("x", "INFRA", phase, resume_from=resume, upstream=[], capa=None,
                                                   kind="LAUNCH", code=la["code"], provided=provided, strikes=strikes),
                          status="OPEN", used=strikes, opened=opened, lineage=tag, now=now, key=f"{tag}|{phase}")
        rec, core = d["rec"], d["core"]
        cls = core["class"]
        kind = "CANCELLED" if core["route"] == "CANCELLED" else cls
        text = summary("CANCELLED" if kind == "CANCELLED" else cls, phase=phase, route=core["route"], codes=core["codes"],
                       error_code=core["error_code"], capa=core["capa"])
        status = "OPEN" if core["status"] == "ESCALATED" else core["status"]  # unclassified is retried too (the rule)
        return _issue(self.line, wo=rec["wo"], tag=tag, phase=phase, rid=rec["rid"], cls=cls, fingerprint=d["fp"],
                      error_code=core["error_code"], text=text, evidence=core["evidence"],
                      proposals=rule_proposals("x", cls, phase, resume_from=resume, upstream=core.get("upstream", []),
                                               capa=core["capa"], kind=kind, strikes=strikes),
                      status=status, used=strikes, opened=opened, lineage=_lineage(by_wo, rec), now=now,
                      key=f"{tag}|{phase}")

    @staticmethod
    def budgets(issues: list[dict], now: float, wall_used: float) -> dict:
        """Pacing and cost guards only (owner rule 2026-11-03): they pace the supervisor and never stop the line."""
        hour = sum(1 for i in issues if i["class"] == "INFRA" and now - (_ts(i["updated_at"]) or 0) <= 3600
                   and i["status"] != "RESOLVED")
        used = {"guard_infra_recoveries_per_hour_host": hour, "guard_phase_order_wall_s": round(wall_used)}
        return {k: {"used": used.get(k, 0), "limit": v} for k, v in BUDGETS.items()}


TRACKED = ("status", "class", "error_code", "attempts", "escalation", "proposals", "resolved_at")


def latest_acks() -> dict[str, dict]:
    out = {}
    p = acks_path()
    for line in p.read_text(errors="replace").splitlines() if p.is_file() else []:
        try:
            a = json.loads(line)
        except ValueError:
            continue
        if isinstance(a, dict) and a.get("issue_id"):
            out[a["issue_id"]] = a
    return out


def merge(prev: dict | None, new: list[dict], acks: dict, now: float) -> tuple[list[dict], list[tuple[str, dict]]]:
    """Carry identity over cycles: opened_at and acknowledgements persist, updated_at moves only on a tracked change;
    issues no longer derived are kept as they were (their records left the look-back window); resolved issues older
    than 7 days leave the feed. Returns the issues and the journal events."""
    old = {i["issue_id"]: i for i in (prev or {}).get("issues", []) if isinstance(i, dict) and i.get("issue_id")}
    events, out, seen = [], [], set()
    for i in new:
        o = old.get(i["issue_id"])
        if o is not None:
            i["opened_at"] = o.get("opened_at", i["opened_at"])
            if i["status"] == "RESOLVED" and o.get("resolved_at"):
                i["resolved_at"] = o["resolved_at"]
            if o.get("escalation", {}).get("level") == i["escalation"]["level"]:
                i["escalation"]["at"] = o["escalation"].get("at", i["escalation"]["at"])
        a = acks.get(i["issue_id"])
        if a:
            i["escalation"].update(acknowledged=True, acknowledged_at=a["at"], acknowledged_by=a["by"],
                                   ack_ref=a.get("event_id"))
        if o is not None and all(o.get(k) == i.get(k) for k in TRACKED):
            i["updated_at"] = o.get("updated_at", i["updated_at"])
        else:
            events.append(("OPENED" if o is None else "RESOLVED" if i["status"] == "RESOLVED" else "CHANGED", i))
        seen.add(i["issue_id"])
        out.append(i)
    for iid, o in old.items():
        if iid not in seen:
            out.append(o)
    out = [i for i in out if not (i["status"] == "RESOLVED" and now - (_ts(i.get("resolved_at")) or now) > RESOLVED_KEEP_S)]
    out.sort(key=lambda i: i["opened_at"], reverse=True)
    out.sort(key=lambda i: i["status"] == "RESOLVED")  # open first, newest first
    return out[:500], events


class LineConductor:
    """The OBSERVE service: one cycle = observe, merge, validate, write the feed atomically, heartbeat."""

    def __init__(self, observer: Observer, unit: str | None = None):
        self.observer = observer
        self.unit = _token(unit or os.environ.get("FORGE_LINE_CONDUCTOR_UNIT")) or "manual"
        self.cycle_n = 0
        self.last_epoch: float | None = None

    def cycle(self, now: float | None = None) -> dict:
        now = now or time.time()
        issues, budgets = self.observer.issues(now)
        keys = contract_keys()
        issues = [fit_issue(i, keys) for i in issues]
        with feed_lock():
            prev = _load(feed_path())
            merged, events = merge(prev if isinstance(prev, dict) else None, issues, latest_acks(), now)
            feed = {"schema": SCHEMA_ID, "generated_at": _utc(now),
                    "supervisor": {"unit": self.unit, "pid": os.getpid(), "mode": MODE, "cycle": self.cycle_n,
                                   "heartbeat_age_s": round(now - self.last_epoch, 1) if self.last_epoch else None,
                                   "model_calls_healthy": model_calls()},
                    "budgets": budgets, "issues": merged, "progress": self.observer.progress}
            if keys is not None and "progress" not in keys[0]:
                feed.pop("progress")
            errs = feed_errors(feed)
            if errs and errs != ["SCHEMA_UNAVAILABLE"]:
                raise ValueError("SUPERVISOR_FEED_INVALID: " + "; ".join(errs[:3]))
            atomic_write(feed_path(), json.dumps(feed, indent=1, sort_keys=True, ensure_ascii=False).encode() + b"\n")
            for ev, i in events:
                append_jsonl(journal_path(), {"at": _utc(now), "event": ev, "issue": i})
        self.cycle_n += 1
        self.last_epoch = now
        return feed

    def write_heartbeat(self, ok: bool, detail: str) -> None:
        atomic_write(heartbeat_path(), json.dumps({"ts": _utc(time.time()), "epoch": time.time(), "pid": os.getpid(),
                                                   "cycle": self.cycle_n, "mode": MODE, "ok": ok,
                                                   "detail": detail[:200]}).encode())


def run(conductor: LineConductor, interval: float, max_cycles: int | None) -> int:
    from ..supervisor.service import sd_notify

    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    ready, n = False, 0
    while not stop["flag"] and (max_cycles is None or n < max_cycles):
        try:
            feed = conductor.cycle()
        except Exception as exc:  # noqa: BLE001 - a failed cycle sends no watchdog ping; systemd decides
            conductor.write_heartbeat(False, f"{type(exc).__name__}: {exc}")
        else:
            open_n = sum(1 for i in feed["issues"] if i["status"] != "RESOLVED")
            conductor.write_heartbeat(True, f"issues_open={open_n} model_calls={feed['supervisor']['model_calls_healthy']}"
                                      + ("" if validator() else " SCHEMA_UNAVAILABLE"))
            if not ready:
                sd_notify(f"READY=1\nSTATUS=line conductor {MODE}")
                ready = True
            sd_notify(f"WATCHDOG=1\nSTATUS=cycle {conductor.cycle_n} {MODE} open={open_n}")
        n += 1
        end = time.monotonic() + interval
        while not stop["flag"] and time.monotonic() < end and (max_cycles is None or n < max_cycles):
            time.sleep(0.2)
    sd_notify("STOPPING=1")
    return 0


# ---------------------------------------------------------------------------------------------- owner ack (CLI)
def acknowledge(issue_id: str, by: str, note: str) -> dict:
    """Decision 10: the owner acknowledges an issue on the host. Sets escalation.acknowledged (and its who/when/ref)
    and nothing else; audited in the factory event ledger; kept in acks.jsonl so later cycles carry it."""
    from ..events.emit import emit

    if not re.fullmatch(r"SUP-[0-9a-f]{10}", issue_id or ""):
        raise ValueError("ISSUE_ID_INVALID")
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", by or ""):
        raise ValueError("BY_INVALID")
    if not (note or "").strip():
        raise ValueError("NOTE_REQUIRED")
    with feed_lock():
        feed = _load(feed_path())
        if not isinstance(feed, dict):
            raise FileNotFoundError("NO_SUPERVISOR_FEED")
        issue = next((i for i in feed.get("issues", []) if i.get("issue_id") == issue_id), None)
        if issue is None:
            raise KeyError("ISSUE_NOT_FOUND")
        import getpass

        ev = emit("audit", "INFO", f"supervisor ack {issue_id} by {by}: {note.strip()}", correlation_id=issue_id,
                  incident_id=issue_id, agent_id=f"os:{getpass.getuser()}")
        at = _utc(time.time())
        issue["escalation"].update(acknowledged=True, acknowledged_at=at, acknowledged_by=by, ack_ref=ev["event_id"])
        errs = feed_errors(feed)
        if errs and errs != ["SCHEMA_UNAVAILABLE"]:
            raise ValueError("SUPERVISOR_FEED_INVALID: " + "; ".join(errs[:3]))
        append_jsonl(acks_path(), {"issue_id": issue_id, "by": by, "at": at, "event_id": ev["event_id"],
                                   "os_user": getpass.getuser(),
                                   "note_sha256": hashlib.sha256(note.strip().encode()).hexdigest()})
        atomic_write(feed_path(), json.dumps(feed, indent=1, sort_keys=True, ensure_ascii=False).encode() + b"\n")
        append_jsonl(journal_path(), {"at": at, "event": "ACKNOWLEDGED", "issue": issue})
    return {"issue_id": issue_id, "acknowledged": True, "acknowledged_by": by, "acknowledged_at": at,
            "ack_ref": ev["event_id"]}


def cli(argv: list[str]) -> int:
    """`python -m forge_factory.afo.cli supervisor ack <issue_id> --by owner --note "..."`"""
    ap = argparse.ArgumentParser(prog="forge_factory.afo.cli supervisor")
    ap.add_argument("action", choices=["ack"])
    ap.add_argument("issue_id")
    ap.add_argument("--by", required=True)
    ap.add_argument("--note", required=True)
    a = ap.parse_args(argv)
    from .cli import operator_ok

    if not operator_ok():
        print("refused: the owner ack needs the account that owns the line state directory", file=sys.stderr)
        return 3
    try:
        out = acknowledge(a.issue_id, a.by, a.note)
    except (ValueError, KeyError, FileNotFoundError) as e:
        print(json.dumps({"refused": str(e).strip("'")}))
        return 1
    print(json.dumps(out))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.afo.line_conductor", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--max-cycles", type=int)
    ap.add_argument("--once", action="store_true", help="one cycle, print the feed path and the open-issue count")
    ap.add_argument("--mode", choices=[MODE], default=MODE)
    ap.add_argument("--line", default=os.environ.get("FORGE_LINE_ID", "local"))
    ap.add_argument("--launch-dir", default=os.environ.get("FORGE_LINE_LAUNCH_DIR"))
    ap.add_argument("--fabro-snapshot", help="offline replay: a recorded {run_id: status} file instead of the live API")
    ap.add_argument("--cre-db", default=os.environ.get("FORGE_LINE_CRE_DB"))
    ap.add_argument("--lookback-h", type=float, default=LOOKBACK_S / 3600)
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9-]{1,32}", a.line):
        raise SystemExit("--line must match [a-z0-9-]{1,32}")
    fabro = FabroView.from_env(a.fabro_snapshot)
    install_guard({p for p in (fabro.port(),) if p})
    obs = Observer(a.line, Path(a.launch_dir) if a.launch_dir else None, fabro,
                   Path(a.cre_db) if a.cre_db else None, a.lookback_h * 3600)
    lc = LineConductor(obs)
    if a.once:
        feed = lc.cycle()
        lc.write_heartbeat(True, "once")
        print(json.dumps({"feed": str(feed_path()), "issues": len(feed["issues"]),
                          "open": sum(1 for i in feed["issues"] if i["status"] != "RESOLVED"),
                          "model_calls_healthy": feed["supervisor"]["model_calls_healthy"]}))
        return 0
    return run(lc, a.interval, a.max_cycles)


if __name__ == "__main__":
    sys.exit(main())
