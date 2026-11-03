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
# decision 7 (owner 2026-11-03)
BUDGETS = {
    "convergence_retries_per_phase": 2,
    "infra_recoveries_per_order": 3,
    "infra_recoveries_per_hour_host": 6,
    "infra_cooldown_s": 600,
    "planner_calls_per_order": 4,
    "planner_tokens_per_order": 200_000,
    "phase_order_wall_s": 6 * 3600,
}
CLASS_LIMIT = {"MODEL_CONVERGENCE": 2, "INFRA": 3, "PRODUCT": 2, "FACTORY_DEFECT": 0, "UNKNOWN": 0}
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
    return {"class": cls, "phase": ph, "error_code": _code(b["error_code"]), "route": route or "ENDED", "codes": codes,
            "fingerprint": b["fingerprint"], "evidence": ev, "upstream": sorted({d["target_phase"] for d in up}),
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


def rule_proposals(issue_id: str, cls: str, phase: str, *, resume_from: str | None, used: int, limit: int,
                   upstream: list[str], capa: str | None, kind: str, code: str = "",
                   provided: tuple[str | None, str] | None = None) -> list[dict]:
    retry_txt = f"retry {phase} from {resume_from}" if resume_from else f"retry {phase} from a fresh order"
    if kind == "CANCELLED":
        return [_proposal(issue_id, 1, "RESUME_PHASE_FROM_LAST_PASSED_ORDER", ["FABRO_RUN_CANCELLED",
                          "OWNER_RELEASE_REQUIRED"], f"resume {phase} from {resume_from or 'a fresh order'} when released",
                          phase=phase if phase in PHASES else None, resume_from=resume_from)]
    if kind == "LAUNCH" and provided:
        good, raw = provided
        if good:
            return [_proposal(issue_id, 1, "RELAUNCH_WITH_CORRECTED_PROVIDED_FROM", ["PROVIDED_FROM_NAME_INVALID",
                              "CORRECTED_NAME_EXISTS"], f"relaunch {phase} with --provided-from {good}",
                              phase=phase if phase in PHASES else None, provided_from=good)]
        return [_proposal(issue_id, 1, "ESCALATE_TO_OWNER", ["PROVIDED_SOURCE_NOT_FOUND"],
                          "provided-from source not in the line state; owner decision needed")]
    if kind == "LAUNCH" and code not in STACK_CODES:
        return [_proposal(issue_id, 1, "RELAUNCH_PHASE_FROM_LAST_PASSED_ORDER", ["LAUNCH_REFUSED"],
                          f"relaunch {phase} from {resume_from}" if resume_from else f"relaunch {phase}",
                          phase=phase if phase in PHASES else None, resume_from=resume_from)]
    if kind == "LAUNCH":
        return [_proposal(issue_id, 1, "STACK_REPAIR_RECIPE", ["LAUNCH_FAILED_BEFORE_RUN"],
                          "stack stop, stop own orphaned stack processes, stack start, health check", recipe="stack-repair-v1"),
                _proposal(issue_id, 2, "RELAUNCH_PHASE_FROM_LAST_PASSED_ORDER", ["LAUNCH_FAILED_BEFORE_RUN"],
                          f"relaunch {phase} from {resume_from}" if resume_from else f"relaunch {phase}",
                          phase=phase if phase in PHASES else None, resume_from=resume_from)]
    if cls == "FACTORY_DEFECT":
        p = _proposal(issue_id, 1, "FOLLOW_CAPA", ["FACTORY_DEFECT_NEEDS_EXTERNAL_CHANGE"],
                      f"wait for the CRE fix of {capa}, then {retry_txt}", capa_id=capa, phase=phase, resume_from=resume_from)
        p["cre_decision_ref"] = _ref(f"capa:{capa}") if capa else None
        return [p]
    if cls == "INFRA":
        return [_proposal(issue_id, 1, "STACK_REPAIR_RECIPE", ["INFRASTRUCTURE"], "stack health check and repair",
                          recipe="stack-repair-v1"),
                _proposal(issue_id, 2, "RETRY_PHASE_FROM_LAST_PASSED_ORDER", ["INFRASTRUCTURE"], retry_txt,
                          phase=phase if phase in PHASES else None, resume_from=resume_from)]
    if cls == "PRODUCT" and upstream:
        return [_proposal(issue_id, 1, "RETURN_TO_OWNING_UPSTREAM_PHASE", ["OPEN_UPSTREAM_DEFECT"],
                          f"return to {upstream[0]} (open upstream defect)", phase=upstream[0])]
    if cls in ("MODEL_CONVERGENCE", "PRODUCT"):
        if used < limit:
            return [_proposal(issue_id, 1, "RETRY_PHASE_FROM_LAST_PASSED_ORDER",
                              ["STUCK_OR_REWORK_BUDGET" if cls == "MODEL_CONVERGENCE" else "PRODUCT_REWORK",
                               f"RETRY_BUDGET_LEFT:{limit - used}"], retry_txt, phase=phase, resume_from=resume_from),
                    _proposal(issue_id, 2, "PROPOSE_VALIDATED_LESSON", ["LESSON_NEEDS_DETERMINISTIC_VALIDATION"],
                              f"lesson for {phase} authors from these codes, validated before it is shared", phase=phase)]
        return [_proposal(issue_id, 1, "RETURN_UPSTREAM_OR_LESSON", ["RETRY_BUDGET_EXHAUSTED"],
                          f"{phase}: upstream return or validated lesson, else BLOCKED", phase=phase)]
    return [_proposal(issue_id, 1, "ESCALATE_TO_OWNER", ["UNCLASSIFIED"], "owner decision needed")]


# ------------------------------------------------------------------------------------------------- the cycle
def _issue(line: str, *, wo, tag, phase, rid, cls, fingerprint, error_code, text, evidence, proposals, status, used,
           limit, opened, lineage, now) -> dict:
    iid = "SUP-" + _h(line, wo or "-", fingerprint)[:10]
    for p in proposals:  # the proposal ids are bound to the issue
        p["proposal_id"] = "SUPP-" + _h(iid, p["strategy"], json.dumps(p["args"], sort_keys=True))[:12]
    level = "NEEDS_OWNER" if status == "ESCALATED" else "FLOOR"
    return {"issue_id": iid, "line": line, "lineage": _token(lineage) or _token(tag) or "UNKNOWN", "wo": _token(wo),
            "phase": phase if phase in PHASES else "-", "fabro_run_id": _token(rid), "class": cls,
            "fingerprint": fingerprint, "error_code": _code(error_code), "summary": text,
            "evidence": [e for e in ({"kind": x["kind"], "ref": _ref(x["ref"])} for x in evidence) if e["ref"]][:24],
            "proposals": proposals[:8], "status": status, "attempts": {"used": int(used), "limit": int(limit)},
            "escalation": {"level": level, "at": _utc(opened), "acknowledged": False, "acknowledged_at": None,
                           "acknowledged_by": None, "ack_ref": None},
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


class Observer:
    """One OBSERVE pass over a line's records -> the feed's issues and budgets (pure: writes nothing)."""

    def __init__(self, line: str = "local", launch_dir: Path | None = None, fabro: FabroView | None = None,
                 cre_db: Path | None = None, lookback_s: float = LOOKBACK_S):
        self.line, self.launch_dir, self.fabro = line, launch_dir, fabro or FabroView()
        self.cre_db, self.lookback_s = cre_db, lookback_s
        self._cache: dict = {}

    def issues(self, now: float) -> tuple[list[dict], dict]:
        root = state_dir()
        orders = scan_orders(root, now, self.lookback_s)
        by_wo = {o["wo"]: o for o in orders}
        cre = read_cre(self.cre_db or root / "supervisor/incidents.sqlite3")
        out: list[dict] = []
        wall_used = 0.0
        for rec in orders:
            life = self.fabro.status(rec["rid"]) if rec["package"] is None else None
            key = (rec["wo"], rec["sig"], life, tuple(sorted(cre["capa_of"])))
            if key not in self._cache:
                self._cache = {k: v for k, v in self._cache.items() if k[0] != rec["wo"]}
                self._cache[key] = classify_order(rec, life, cre["capa_of"])
            core = self._cache[key]
            if core is None:
                kind = (life or "").split(":")[0]
                if rec["package"] is None and rec["phase"] not in rec["passed"] and kind not in ENDED:
                    wall = now - rec["created"]
                    wall_used = max(wall_used, wall)
                    if wall > BUDGETS["phase_order_wall_s"]:
                        out.append(_issue(self.line, wo=rec["wo"], tag=rec["tag"], phase=rec["phase"], rid=rec["rid"],
                                          cls="UNKNOWN", fingerprint="sup1-" + _h("WALL", rec["wo"])[:40],
                                          error_code="PHASE_WALL_BUDGET_EXCEEDED",
                                          text=summary("WALL", phase=rec["phase"]),
                                          evidence=[{"kind": "manifest", "ref": f"{rec['rel']}/.forge-run/manifest.json"}],
                                          proposals=rule_proposals("x", "UNKNOWN", rec["phase"], resume_from=None, used=0,
                                                                   limit=0, upstream=[], capa=None, kind="WALL"),
                                          status="ESCALATED", used=0, limit=0, opened=rec["created"],
                                          lineage=_lineage(by_wo, rec), now=now))
                continue
            cls, phase = core["class"], core["phase"]
            same = [o for o in orders if o["tag"] == rec["tag"] and o["phase"] == phase and o["source"] == rec["source"]
                    and o["created"] < rec["created"] and phase not in o["passed"]]
            used, limit = len(same), CLASS_LIMIT[cls]
            status = core["status"]
            if status == "OPEN" and used >= limit and cls != "INFRA":
                status = "ESCALATED"
            kind = "CANCELLED" if core["route"] == "CANCELLED" else cls
            # the order this one resumed from (it passed the phase before), else the newest such order of the part
            resume = rec["source"] or last_passed_order(orders, rec["tag"], phase, rec["created"])
            text = summary("CANCELLED" if kind == "CANCELLED" else cls, phase=phase, route=core["route"],
                           codes=core["codes"], error_code=core["error_code"], capa=core["capa"])
            props = rule_proposals("x", cls, phase, resume_from=resume, used=used, limit=limit,
                                   upstream=core.get("upstream", []), capa=core["capa"], kind=kind)
            iss = _issue(self.line, wo=rec["wo"], tag=rec["tag"], phase=phase, rid=rec["rid"], cls=cls,
                         fingerprint=core["fingerprint"], error_code=core["error_code"], text=text,
                         evidence=core["evidence"], proposals=props, status=status, used=used, limit=limit,
                         opened=rec["created"], lineage=_lineage(by_wo, rec), now=now)
            self._settle(iss, orders, rec["tag"], phase, rec["created"], launched=False, now=now)
            out.append(iss)
        from ..reliability.taxonomy import fingerprint

        launches = scan_launches(self.launch_dir, now, self.lookback_s)
        for la in launches:
            earlier = [x for x in launches
                       if x["tag"] == la["tag"] and x["phase"] == la["phase"] and x["created"] < la["created"]]
            resume = last_passed_order(orders, la["tag"], la["phase"], la["created"]) if la["phase"] in PHASES else None
            provided = None
            if la["ref_wo"]:  # a source order named in the refusal; strip trailing punctuation, check it exists
                good = la["ref_wo"].rstrip(":;,.")
                ok = good != la["ref_wo"] and (root / "workorders" / good / "workspace").is_dir()
                provided = (good if ok else None, la["ref_wo"])
            iss = _issue(self.line, wo=la["wo"], tag=la["tag"], phase=la["phase"], rid=None, cls="INFRA",
                         fingerprint=fingerprint("INFRASTRUCTURE", "line-launcher", la["code"], f"{la['phase']}/launch"),
                         error_code=la["code"], text=summary("LAUNCH", phase=la["phase"], error_code=la["code"]),
                         evidence=[{"kind": "launch_log", "ref": r} for r in la["refs"]],
                         proposals=rule_proposals("x", "INFRA", la["phase"], resume_from=resume, used=len(earlier),
                                                  limit=CLASS_LIMIT["INFRA"], upstream=[], capa=None, kind="LAUNCH",
                                                  code=la["code"], provided=provided),
                         status="OPEN", used=len(earlier), limit=CLASS_LIMIT["INFRA"], opened=la["created"],
                         lineage=la["tag"], now=now)
            self._settle(iss, orders, la["tag"], la["phase"], la["created"], launched=True, now=now)
            out.append(iss)
        for inc in cre["incidents"]:
            iss = _issue(self.line, wo=None, tag="LINE", phase="-", rid=inc.get("run_id"), cls="INFRA",
                         fingerprint="sup1-" + _h("INCIDENT", inc["fingerprint"])[:40], error_code=inc["fault_type"],
                         text=summary("INCIDENT", error_code=_code(inc["fault_type"]), component=_code(inc["component"])),
                         evidence=[{"kind": "incident", "ref": f"incident:{inc['incident_id']}"}],
                         proposals=rule_proposals("x", "INFRA", "-", resume_from=None, used=int(inc["attempts"] or 0),
                                                  limit=3, upstream=[], capa=None, kind="INFRA")[:1],
                         status="OPEN", used=int(inc["attempts"] or 0), limit=CLASS_LIMIT["INFRA"],
                         opened=_ts(inc["created_at"]) or now, lineage="LINE", now=now)
            out.append(iss)
        for q in read_afo_queue(root / "conductor/conductor.sqlite3", now, self.lookback_s):
            from ..reliability.taxonomy import classify

            c = classify(q["reason"])
            cls = "FACTORY_DEFECT" if q["state"] == "WAITING_EXTERNAL_CHANGE" else \
                "INFRA" if c.failure_class in ("INFRASTRUCTURE", "TRANSIENT_DEPENDENCY") else "UNKNOWN"
            st = {"WAITING_EXTERNAL_CHANGE": "WAITING_EXTERNAL_CHANGE", "WAITING_RECOVERY": "RECOVERING"}.get(q["state"],
                                                                                                          "ESCALATED")
            code = _code(f"AFO_{q['state']}:{c.error_code}")
            out.append(_issue(self.line, wo=q["order_id"], tag="AFO", phase="-", rid=None, cls=cls,
                              fingerprint="sup1-" + _h("AFO", q["order_id"], q["state"])[:40], error_code=code,
                              text=summary("AFO", state=q["state"], error_code=_code(c.error_code)),
                              evidence=[{"kind": "afo_order", "ref": f"afo:{q['order_id']}"}], proposals=[],
                              status=st, used=0, limit=CLASS_LIMIT[cls], opened=float(q["created"] or now),
                              lineage="AFO", now=now))
        budgets = self.budgets(out, now, wall_used)
        return out, budgets

    @staticmethod
    def _settle(iss: dict, orders: list[dict], tag: str, phase: str, after: float, *, launched: bool, now: float) -> None:
        st, by = _later(orders, tag, phase, after, launched=launched)
        if st is None:
            return
        iss["evidence"].append({"kind": "superseded_by", "ref": f"workorders/{by}"})
        if st == "RECOVERING":
            iss["status"] = "RECOVERING"
            return
        iss["status"], iss["resolved_at"] = "RESOLVED", _utc(now)
        iss["escalation"]["level"] = "FLOOR"
        for p in iss["proposals"]:
            p["status"] = "SUPERSEDED"
            p["reason_codes"] = (p["reason_codes"] + ["RESOLVED_BY_LATER_ORDER"])[:8]

    @staticmethod
    def budgets(issues: list[dict], now: float, wall_used: float) -> dict:
        live = [i for i in issues if i["status"] != "RESOLVED"]
        conv = [i["attempts"]["used"] for i in live if i["class"] == "MODEL_CONVERGENCE"]
        infra = [i["attempts"]["used"] for i in live if i["class"] == "INFRA"]
        hour = sum(1 for i in issues if i["class"] == "INFRA" and now - (_ts(i["opened_at"]) or 0) <= 3600)
        return {"convergence_retries_per_phase": {"used": max(conv, default=0),
                                                  "limit": BUDGETS["convergence_retries_per_phase"]},
                "infra_recoveries_per_order": {"used": max(infra, default=0), "limit": BUDGETS["infra_recoveries_per_order"]},
                "infra_recoveries_per_hour_host": {"used": hour, "limit": BUDGETS["infra_recoveries_per_hour_host"]},
                "infra_cooldown_s": {"used": 0, "limit": BUDGETS["infra_cooldown_s"]},
                "planner_calls_per_order": {"used": 0, "limit": BUDGETS["planner_calls_per_order"]},
                "planner_tokens_per_order": {"used": 0, "limit": BUDGETS["planner_tokens_per_order"]},
                "phase_order_wall_s": {"used": round(wall_used), "limit": BUDGETS["phase_order_wall_s"]}}


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
        with feed_lock():
            prev = _load(feed_path())
            merged, events = merge(prev if isinstance(prev, dict) else None, issues, latest_acks(), now)
            feed = {"schema": SCHEMA_ID, "generated_at": _utc(now),
                    "supervisor": {"unit": self.unit, "pid": os.getpid(), "mode": MODE, "cycle": self.cycle_n,
                                   "heartbeat_age_s": round(now - self.last_epoch, 1) if self.last_epoch else None,
                                   "model_calls_healthy": model_calls()},
                    "budgets": budgets, "issues": merged}
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
