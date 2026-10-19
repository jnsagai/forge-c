"""AFO-T002 (AFO-FR-001) - capability matrix of what Feature 005 needs against what 001-004 already implement.

Each row names the AFO need, the existing module(s) it reuses and a code check (file + symbol regex). The status
is derived, never asserted: IMPLEMENTED when every check holds, PARTIAL when the row says what is missing and at
least one check holds, MISSING when no code exists. `docs/afo-capability-matrix.md` is generated from this table;
`test_afo_m0_audit.py` fails when a row cites code that does not exist or when the document drifts.
"""
from __future__ import annotations

import json
import re
import sys

from ..common import REPO_ROOT

PY = "factory/python/forge_factory"
# id, AFO need, reused module(s) / owner, checks [(path, symbol regex)], gap (None = nothing missing), AFO tasks
ROWS = [
    ("A01", "Launch a work order on Fabro", "workorder.run + fabro.runconfig.fabro_run (002)",
     [(f"{PY}/workorder.py", r"^def run\("), (f"{PY}/fabro/runconfig.py", r"^def fabro_run\(")], None, "T026, T028"),
    ("A02", "Look up Fabro runs (status, list, events, cancel)", "fabro.client.FabroClient (002)",
     [(f"{PY}/fabro/client.py", r"def list_runs\("), (f"{PY}/fabro/client.py", r"def get_run\("),
      (f"{PY}/fabro/client.py", r"def cancel\(")],
     "no lookup by a unique attempt label/nonce: launch-receipt reconciliation must be built (T026)", "T026, T029"),
    ("A03", "Work-order level resume from a validated source", "workorder.resume_from (--resume-from)",
     [(f"{PY}/workorder.py", r"^def resume_from\(")],
     "work-order level only (new attempt carrying verified files); no native Fabro continuation", "T030, T031"),
    ("A04", "Accepted SWE checkpoints with upstream hashes", "inspection.engine Store baselines + stale_reason",
     [(f"{PY}/inspection/engine.py", r"def latest_baseline\("), (f"{PY}/inspection/engine.py", r"def stale_reason\(")],
     "baselines live per workspace; no cross-attempt immutable checkpoint refs", "T030"),
    ("A05", "Model-free infrastructure health and repair", "supervisor.service + supervisor.dispatch + repair.infra (002)",
     [(f"{PY}/supervisor/service.py", r"^class Supervisor"), (f"{PY}/supervisor/dispatch.py", r"def "),
      (f"{PY}/repair/infra.py", r"^def validate_runtime\(")], None, "reuse (M1, M4)"),
    ("A06", "Guarded side effects and idempotent journal", "reliability.recovery.SideEffectJournal + production.guarded (004)",
     [(f"{PY}/reliability/recovery.py", r"^class SideEffectJournal"), (f"{PY}/reliability/production.py", r"^def guarded\(")],
     None, "T027"),
    ("A07", "Retry admission, breakers, leases", "reliability.recovery RetryAdmission/Breaker/ScopeLeases (004)",
     [(f"{PY}/reliability/recovery.py", r"^class RetryAdmission"), (f"{PY}/reliability/recovery.py", r"^class Breaker"),
      (f"{PY}/reliability/recovery.py", r"^class ScopeLeases")], None, "T019, T022"),
    ("A08", "Failure taxonomy and cross-run fingerprints", "reliability.taxonomy + observe (004)",
     [(f"{PY}/reliability/taxonomy.py", r"def "), (f"{PY}/reliability/observe.py", r"^def ingest\(")], None, "T035, T036"),
    ("A09", "CAPA, frozen reproducers, independent promotion gate", "reliability.capa + reproduce + promotion (004)",
     [(f"{PY}/reliability/capa.py", r"^class CapaRegistry"), (f"{PY}/reliability/promotion.py", r"def ")], None,
     "T047, T048"),
    ("A10", "KPI engine and reliability statistics", "kpi (003) + reliability.metrics (004)",
     [(f"{PY}/reliability/metrics.py", r"^def wilson\("), (f"{PY}/kpi/__init__.py", r"")], None, "T062, T063"),
    ("A11", "Event ledger", "events (002)", [(f"{PY}/events/emit.py", r"^def emit\(")], None, "T018"),
    ("A12", "Immutable release package READY/BLOCKED", "release.finalize (002)",
     [(f"{PY}/release/finalize.py", r"^def finalize\(")], None, "T032, T059"),
    ("A13", "Read-only dashboard API", "dashboard (002/003/004)", [(f"{PY}/dashboard/__init__.py", r"")],
     "no /api/v1/autonomy routes and no authenticated operator writes", "T056-T058"),
    ("A14", "systemd services with restart and watchdog", "deploy/systemd/forge-supervisor.service.in (002)",
     [("deploy/systemd/forge-supervisor.service.in", r"Restart="),
      ("scripts/forge_services.sh", r"")],
     "only the supervisor is a systemd unit; Ollama/gateway/Fabro/dashboard run from forge_services.sh", "T007-T013"),
    ("A15", "AFO fail-closed policy and modes", "afo.policy (005 M0)",
     [(f"{PY}/afo/policy.py", r"^def load\("), (f"{PY}/afo/policy.py", r"^FLOOR = ")], None, "T004"),
    ("A16", "Signed owner authorization", "afo.authz (005 M0)",
     [(f"{PY}/afo/authz.py", r"^def verify\("), (f"{PY}/afo/authz.py", r'^NAMESPACE = ')], None, "T006"),
    ("A17", "Authority intersection with constitution and CRE", "afo.authority (005 M0)",
     [(f"{PY}/afo/authority.py", r"^def decide\("), (f"{PY}/afo/authority.py", r"^FORBIDDEN = ")], None, "T003"),
    ("A18", "Durable work-order queue, outbox and leases", "-", [(f"{PY}/afo/queue.py", r"")],
     "not built", "T016-T025"),
    ("A19", "Mount sentinel / stable data volume preflight", "-", [(f"{PY}/afo/host.py", r"")], "not built", "T010"),
    ("A20", "Recovery planner and factory maintainer roles", "-", [(f"{PY}/afo/planner.py", r"")], "not built",
     "T037-T045"),
    ("A21", "Dead-letter cases and alerts", "-", [(f"{PY}/afo/deadletter.py", r"")], "not built", "T054, T055"),
]


def check(path: str, rx: str) -> bool:
    p = REPO_ROOT / path
    return p.is_file() and (not rx or re.search(rx, p.read_text(errors="replace"), re.M) is not None)


def matrix() -> list[dict]:
    out = []
    for rid, need, reuse, checks, gap, tasks in ROWS:
        ok = [check(p, rx) for p, rx in checks]
        status = ("IMPLEMENTED" if all(ok) and gap is None else "PARTIAL" if any(ok) else "MISSING")
        out.append({"id": rid, "need": need, "reuse": reuse, "status": status, "checks_passed": f"{sum(ok)}/{len(ok)}",
                    "gap": gap or "", "afo_tasks": tasks})
    return out


def markdown(rows: list[dict]) -> str:
    lines = ["# AFO capability matrix (Feature 005, AFO-T002)", "",
             "Generated by `python -m forge_factory.afo.audit`. Status comes from code checks (file + symbol), never from "
             "this text; `factory/python/tests/test_afo_m0_audit.py` fails when the document drifts or a row cites "
             "missing code. Reuse-first: AFO adds the Conductor, queue and recovery plans; it does not rebuild the 002 "
             "supervisor, 003 KPIs or 004 CRE.", "",
             "| ID | AFO need | Reuses | Status | Checks | Gap | AFO tasks |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['need']} | {r['reuse']} | **{r['status']}** | {r['checks_passed']} | {r['gap']} | "
              f"{r['afo_tasks']} |" for r in rows]
    c = {s: sum(r["status"] == s for r in rows) for s in ("IMPLEMENTED", "PARTIAL", "MISSING")}
    lines += ["", f"Totals: IMPLEMENTED {c['IMPLEMENTED']}, PARTIAL {c['PARTIAL']}, MISSING {c['MISSING']}.", ""]
    return "\n".join(lines)


DOC = REPO_ROOT / "docs/afo-capability-matrix.md"


def main(argv: list[str] | None = None) -> int:
    rows = matrix()
    DOC.write_text(markdown(rows))
    print(json.dumps({s: sum(r["status"] == s for r in rows) for s in ("IMPLEMENTED", "PARTIAL", "MISSING")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
