"""CRE-T048 — owner-authorized LIVE Fabro crash -> recovery drill on the real local server (:32290).

Sequence (every step recorded): preconditions (Fabro healthy, no active run, supervisor polling with repair dispatch
suspended so no model-based repair agent runs) -> owner authorization as a HUMAN_REVIEW event -> SIGKILL of the Fabro
server process (found by its listening port) -> independent detection by the systemd supervisor (incident, CRE
recovery scope, breaker) -> CRE operational action `restart_fabro` journaled as REPLAY_SAFE (documented restart
script) -> recovery verified by the SUPERVISOR (incident RESOLVED after stable polls, CRE scope RECOVERED) ->
invariants: supervisor model calls 0, protected inputs and released archives byte-identical, Fabro run history kept.
Bounded: every wait has a deadline; on timeout the drill stops and records the state reached (never a PASS).
"""
from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import time

from ..common import REPO_ROOT, data_root, pretty_json, state_dir, utc_now
from . import events as E

FABRO = "http://127.0.0.1:32290"


def _health() -> dict:
    try:
        return json.loads((state_dir() / "supervisor/health.json").read_text())
    except (OSError, ValueError):
        return {}


def _fabro_up() -> bool:
    r = subprocess.run(["curl", "-s", "-m", "3", f"{FABRO}/health"], capture_output=True, text=True)
    return '"ok"' in r.stdout


def _fabro_pid() -> int | None:
    out = subprocess.run(["ss", "-ltnpH", "sport = :32290"], capture_output=True, text=True).stdout
    import re
    m = re.search(r"pid=(\d+)", out)
    return int(m.group(1)) if m else None


def _runs_count() -> int | None:
    from ..fabro.client import load_token
    tok = load_token()
    r = subprocess.run(["curl", "-s", "-m", "5", "-H", f"Authorization: Bearer {tok}", f"{FABRO}/api/v1/runs?limit=500"],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        runs = d.get("data", d) if isinstance(d, dict) else d
        return len(runs)
    except (ValueError, AttributeError):
        return None


def _incidents_since(t: str) -> list[dict]:
    c = sqlite3.connect(f"file:{state_dir() / 'supervisor/incidents.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute("SELECT * FROM incidents WHERE created_at >= ? AND component='fabro' "
                                           "ORDER BY created_at", (t,))]
    finally:
        c.close()


def _wait(pred, deadline_s: float, step: float = 5.0):
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        v = pred()
        if v:
            return v
        time.sleep(step)
    return None


def run(authorized_by: str, authorized_on: str, detect_s: float = 600, recover_s: float = 900) -> dict:
    from ..repair.promotion import tree_hash
    from .faults import protected_digest
    from .policy import load
    from .recovery import Breaker, RecoveryController, SideEffectJournal
    from .store import CREStore

    pol, store = load(), CREStore()
    rec: dict = {"schema": "forge-c/cre-live-drill/1.0", "drill": "fabro-crash-recovery", "started_at": utc_now(),
                 "target": FABRO, "steps": []}

    def step(name: str, **kw):
        rec["steps"].append({"at": utc_now(), "step": name, **kw})

    h0 = _health()
    pre = {"fabro_up": _fabro_up(), "active_runs": next((c["metrics"].get("active_runs") for c in h0.get("components", [])
                                                         if c["id"] == "fabro:fabro_readiness"), None),
           "supervisor_polls": h0.get("polls"), "supervisor_status": h0.get("status"),
           "dispatch_suspended": os.environ.get("FORGE_SUPERVISOR_NO_DISPATCH") == "1" or _no_dispatch_in_unit(),
           "runs_count": _runs_count()}
    rec["preconditions"] = pre
    if not (pre["fabro_up"] and pre["active_runs"] == 0 and pre["dispatch_suspended"]):
        rec["result"] = "NOT_RUN"
        rec["reason"] = "preconditions not met (Fabro healthy, no active run, repair dispatch suspended)"
        return rec
    auth = E.build("cre.policy_decision", f"drill|fabro-crash|{authorized_on}|{rec['started_at']}", {
        "decision": "AUTHORIZED", "action": "live_fabro_crash_recovery_drill", "authorized_by": authorized_by,
        "authorized_on": authorized_on, "scope": "one crash + one restart of the local Fabro server :32290"},
        policy_sha256=pol.sha256, correlation_id="drill:fabro", source_type="HUMAN_REVIEW", data_status="OBSERVED")
    E.record(store, auth)
    rec["authorization_event"] = auth["event_id"]
    digest0, arch0 = protected_digest(), tree_hash(data_root() / "archives")
    pid = _fabro_pid()
    t_crash = utc_now()
    os.kill(pid, signal.SIGKILL)
    step("crash", pid=pid, signal="SIGKILL")
    t0 = time.monotonic()
    inc = _wait(lambda: (_incidents_since(t_crash) or [None])[0], detect_s)
    if not inc:
        step("detection_timeout")
        rec["result"] = "FAIL"
        rec["reason"] = "supervisor did not open a Fabro incident within the deadline"
    else:
        t_detect = time.monotonic() - t0
        step("detected", incident=inc["incident_id"], fault=inc["fault_type"], state=inc["state"],
             latency_s=round(t_detect, 1), supervisor_status=_health().get("status"))
        rec["dispatch_decision"] = {"would_dispatch_via": "external_local_worker", "executed": False,
                                    "reason": "repair dispatch suspended for the drill (owner rule: no local-model "
                                              "repair agent); the route for component 'fabro' is the Fabro-independent "
                                              "worker path"}
        j = SideEffectJournal(store, pol)
        key = f"drill:{auth['event_id']}:restart_fabro"
        log = state_dir() / "reliability" / f"drill-restart-{rec['started_at'][:19].replace(':', '')}.log"
        log.parent.mkdir(parents=True, exist_ok=True)

        def restart(_k: str) -> int:
            # the script backgrounds Fabro in a subshell that keeps inherited fds: never pipe it (first drill hung)
            with open(log, "ab") as fh:
                p = subprocess.Popen(["bash", str(REPO_ROOT / "scripts/forge_services.sh"), "restart-fabro"],
                                     stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     start_new_session=True)
            return p.pid

        res = j.perform(key, "process_restart", "REPLAY_SAFE", restart)
        step("recovery_action", action="restart_fabro", journal_status=res["status"], launcher_pid=res["receipt"],
             log=str(log))
        up = _wait(_fabro_up, 120, 2)
        step("fabro_healthy" if up else "fabro_restart_failed", elapsed_s=round(time.monotonic() - t0, 1))

        def resolved():
            c = sqlite3.connect(f"file:{state_dir() / 'supervisor/incidents.sqlite3'}?mode=ro", uri=True)
            try:
                r = c.execute("SELECT state FROM incidents WHERE incident_id=?", (inc["incident_id"],)).fetchone()
            finally:
                c.close()
            return r and r[0] == "RESOLVED"
        ok = _wait(resolved, recover_s) if up else None
        mttr = round(time.monotonic() - t0, 1)
        step("incident_resolved" if ok else "recovery_timeout", elapsed_s=mttr)
        ctl = RecoveryController(store, pol)
        scope = ctl.get(f"incident:{inc['incident_id']}")
        with store.conn() as c:
            bh = [dict(r) for r in c.execute("SELECT from_state,to_state,at,reason FROM cre_breaker_history WHERE "
                                             "dependency='fabro' AND at >= ? ORDER BY seq", (t_crash,))]
        h1 = _health()
        rec.update({
            "incident": inc["incident_id"], "detection_latency_s": round(t_detect, 1), "time_to_recover_s": mttr,
            "cre_recovery_scope": scope and {k: scope[k] for k in ("state", "failure_class", "terminal_reason")},
            "breaker_history": bh, "breaker_now": Breaker(store, pol).state("fabro")["state"],
            "supervisor_after": {"status": h1.get("status"), "model_calls": h1.get("model_calls"),
                                 "model_tokens": h1.get("model_tokens"), "polls": h1.get("polls")},
            "invariants": {"protected_inputs_unchanged": protected_digest() == digest0,
                           "archives_unchanged": tree_hash(data_root() / "archives") == arch0,
                           "fabro_runs_before": pre["runs_count"], "fabro_runs_after": _runs_count()}})
        good = (ok and up and scope and scope["state"] == "RECOVERED" and h1.get("model_calls") == 0
                and rec["invariants"]["protected_inputs_unchanged"] and rec["invariants"]["archives_unchanged"]
                and rec["invariants"]["fabro_runs_after"] == pre["runs_count"])
        rec["result"] = "PASS" if good else "FAIL"
    rec["finished_at"] = utc_now()
    return rec


def _no_dispatch_in_unit() -> bool:
    r = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True)
    return "FORGE_SUPERVISOR_NO_DISPATCH=1" in r.stdout


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--authorized-by", required=True)
    ap.add_argument("--authorized-on", required=True)
    a = ap.parse_args(argv)
    try:
        rec = run(a.authorized_by, a.authorized_on)
    except Exception as exc:  # noqa: BLE001 - the record is written for every outcome
        rec = {"schema": "forge-c/cre-live-drill/1.0", "drill": "fabro-crash-recovery", "started_at": utc_now(),
               "result": "FAIL", "reason": f"drill harness error: {type(exc).__name__}: {str(exc)[:200]}"}
    out = REPO_ROOT / "evidence/cre/live"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"fabro-crash-drill-{rec['started_at'][:10].replace('-', '')}.json").write_text(pretty_json(rec))
    print(json.dumps({k: rec.get(k) for k in ("result", "reason", "incident", "detection_latency_s",
                                              "time_to_recover_s", "cre_recovery_scope", "breaker_now",
                                              "supervisor_after", "invariants")}, indent=2))
    return 0 if rec["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
