"""CRE-T001 — evidence-based capability audit of features 001–003 (IMPLEMENTED / PARTIAL / SPEC_ONLY / MISSING).

* The matrix is DATA (CAPABILITIES) rendered to docs/cre-capability-matrix.md; a test re-renders it and fails on
  drift, and fails when an IMPLEMENTED/PARTIAL row cites a module that does not exist or task evidence that is not a
  recorded PASS (evidence/v0.4/runs/<task>/latest.json). Status words are never inferred from documents alone.
* Live facts are read from the running installation (supervisor checkpoint/health, incident/lesson/event stores,
  work-order packages) - read-only; absent state => UNKNOWN, never a number.
* Source inventory: the repository's current tracked files are hashed and compared with the historical v0.5 handoff
  inventory (SHA256SUMS.txt / PROJECT_MANIFEST.json). Those files are immutable history: they are reported as stale,
  never rewritten.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

from ..common import REPO_ROOT, data_root, pretty_json, sha256_file, state_dir, utc_now

PKG = "factory/python/forge_factory"
# (id, component, status, modules, evidence task ids, finding / gap for CRE)
CAPABILITIES: list[dict] = [
    {"id": "C01", "component": "Fabro workflow orchestration (SWE.1–SWE.6 graph, gates, loopbacks)", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/workflow/builder.py", f"{PKG}/inspection/gate.py", f"{PKG}/fabro/client.py"],
     "evidence": ["T004", "T009", "T018", "T047", "T048"],
     "finding": "Real Fabro 0.362 runs (77 work orders, r1–r77). Cross-phase loopbacks L0–L15 (ADR-0008)."},
    {"id": "C02", "component": "Fabro checkpoints / resume", "status": "PARTIAL",
     "modules": [f"{PKG}/workorder.py"], "evidence": ["T044"],
     "finding": "Work-order level resume (--resume-from, byte-identical carry-over) is implemented and used. Fabro-native "
                "resume of a crashed run is not exercised: a killed run is finalized BLOCKED and restarted as a new attempt."},
    {"id": "C03", "component": "Independent model-free supervisor", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/supervisor/service.py", f"{PKG}/supervisor/probes.py", f"{PKG}/supervisor/store.py"],
     "evidence": ["T019", "T020", "T021", "T024"],
     "finding": "systemd forge-supervisor, socket guard counts model calls (live: 0). GAP: probes only the local Fabro "
                "(:32290), not the cloud benchmark server (:32291); product/agent failures never become incidents."},
    {"id": "C04", "component": "Incident routing, leases, backoff, attempt caps", "status": "PARTIAL",
     "modules": [f"{PKG}/supervisor/router.py"], "evidence": ["T022"],
     "finding": "Dedup, per-incident cap, hourly quota, cooldown doubling exist. GAPS: fingerprint includes run_id "
                "(no cross-run recurrence); no jitter; no per-dependency OPEN/HALF_OPEN breaker; no replay class."},
    {"id": "C05", "component": "Repair Agent and repair dispatch (Fabro-independent path)", "status": "PARTIAL",
     "modules": [f"{PKG}/repair/worker.py", f"{PKG}/supervisor/dispatch.py", f"{PKG}/repair/promotion.py"],
     "evidence": ["T023", "T025", "T026", "T027", "T028", "T029"],
     "finding": "Live: 1 incident, 2 attempts (1 ROLLED_BACK, 1 PROMOTED) on 2026-10-14. Scope is the infra runtime-"
                "config repo only; factory source changes are promoted by human commits without an independent gate."},
    {"id": "C06", "component": "Lessons-learned database", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/knowledge/store.py", f"{PKG}/mcp/servers/knowledge.py"],
     "evidence": ["T030", "T031", "T032", "T033"],
     "finding": "VALIDATED only after a PROMOTED repair; retraction + impact list. Low volume (2 lessons). No link to "
                "a reproducer or prevention test (CRE additive fields needed)."},
    {"id": "C07", "component": "MCP gateway, tool permissions, policy hook", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/policy/authz.py", f"{PKG}/policy/fabro_hook.py", f"{PKG}/mcp/sdk.py"],
     "evidence": ["T007", "T010", "T011", "T018", "T049"], "finding": "Role/phase scoped MCP ops, one-time tickets."},
    {"id": "C08", "component": "SKILL definitions and enforcement", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/registry/agents.py", f"{PKG}/registry/skillgen.py"], "evidence": ["T005", "T006"],
     "finding": "20 roles, skills.lock.json; regenerated from agents.yaml."},
    {"id": "C09", "component": "Token/turn budget governor", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/policy/governor.py", f"{PKG}/llm_gateway.py"], "evidence": ["T041", "T042"],
     "finding": "Per-visit turn budget; reported token caps; cloud gateway lifetime cost cap ($3.00)."},
    {"id": "C10", "component": "Event ledger, capture policy, redaction (10 trace channels)", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/events/store.py", f"{PKG}/events/emit.py", f"{PKG}/events/policy.py", f"{PKG}/events/redact.py"],
     "evidence": ["T034", "T035", "T036"], "finding": "Idempotent event_id store; capture separate from display."},
    {"id": "C11", "component": "KPI event collection and aggregation (K01–K20)", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/kpi/engine.py", f"{PKG}/kpi/sources.py", f"{PKG}/kpi/service.py"],
     "evidence": ["KPI-T001", "KPI-T005", "KPI-T006", "KPI-T008", "KPI-T010", "KPI-T017"],
     "finding": "Deterministic snapshots. No confidence intervals / SPC; cloud benchmark runs excluded by design."},
    {"id": "C12", "component": "Dashboard and tracing", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/dashboard/app.py"], "evidence": ["T037", "T038", "T039", "T040", "KPI-T011"],
     "finding": "Read-only FastAPI on loopback; no reliability view."},
    {"id": "C13", "component": "Release Manager and verification gates", "status": "IMPLEMENTED",
     "modules": [f"{PKG}/release/finalize.py"], "evidence": ["T045", "T046", "KPI-T015", "KPI-T016"],
     "finding": "Every terminal run is packaged READY/BLOCKED (live: all BLOCKED; 2 owner-deferred documents). No "
                "reliability evidence bundle."},
    {"id": "C14", "component": "Cross-run failure registry (fingerprints, recurrence)", "status": "MISSING",
     "modules": [], "evidence": [],
     "finding": "Gate rejections, defects and BLOCKED reasons of every run stay in per-workspace logs; recurrence across "
                "runs is only analysed manually in ADR-0005/0008."},
    {"id": "C15", "component": "CAPA with reproducer-verified root cause", "status": "MISSING", "modules": [], "evidence": [],
     "finding": "Fixes are committed with a regression test, but no record proves the test failed before the fix."},
    {"id": "C16", "component": "Versioned benchmark + holdout and independent promotion of factory changes",
     "status": "MISSING", "modules": [], "evidence": [],
     "finding": "Benchmarking is ad hoc (one resumed or full run per change); no frozen fixtures, holdout or "
                "baseline-vs-candidate decision record."},
    {"id": "C17", "component": "Reliability statistics (Wilson CI, SPC, growth)", "status": "MISSING", "modules": [],
     "evidence": [], "finding": "KPI values carry no interval or sample-size qualification."},
    {"id": "C18", "component": "Side-effect replay classification (idempotency matrix)", "status": "MISSING",
     "modules": [], "evidence": [], "finding": "No REPLAY_SAFE / NON_REPLAYABLE tagging of actions."},
    {"id": "C19", "component": "Historical source inventory (SHA256SUMS.txt / PROJECT_MANIFEST.json)", "status": "PARTIAL",
     "modules": ["scripts/verify_bundle.py"], "evidence": [],
     "finding": "Frozen v0.5 handoff snapshot (184 files, 2026-10-14) - stale against the evolving tree; kept as "
                "immutable history. Current inventory: evidence/cre/baseline/source-inventory.json."},
]
STATUSES = ("IMPLEMENTED", "PARTIAL", "SPEC_ONLY", "MISSING")


def evidence_record(task: str) -> dict | None:
    p = REPO_ROOT / "evidence/v0.4/runs" / task / "latest.json"
    return json.loads(p.read_text()) if p.is_file() else None


def consistency_issues() -> list[str]:
    """An IMPLEMENTED/PARTIAL claim must cite existing modules and recorded PASS evidence."""
    out = []
    for c in CAPABILITIES:
        if c["status"] not in STATUSES:
            out.append(f"{c['id']}:UNKNOWN_STATUS")
        for m in c["modules"]:
            if not (REPO_ROOT / m).is_file():
                out.append(f"{c['id']}:MODULE_MISSING:{m}")
        if c["status"] == "IMPLEMENTED" and not c["evidence"]:
            out.append(f"{c['id']}:IMPLEMENTED_WITHOUT_EVIDENCE")
        for t in c["evidence"]:
            r = evidence_record(t)
            if r is None or r.get("status") != "PASS" or r.get("exit_code") != 0:
                out.append(f"{c['id']}:EVIDENCE_NOT_PASS:{t}")
        if c["status"] == "MISSING" and c["modules"]:
            out.append(f"{c['id']}:MISSING_WITH_MODULES")
    return out


def _sqlite(path: Path, sql: str):
    if not path.is_file():
        return "UNKNOWN"
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            return c.execute(sql).fetchall()
        finally:
            c.close()
    except sqlite3.Error as exc:
        return f"UNKNOWN:{exc}"[:80]


def live_facts(sd: Path | None = None) -> dict:
    sd = sd or state_dir()
    facts: dict = {"state_dir": str(sd), "collected_at": utc_now()}
    try:
        ck = json.loads((sd / "supervisor/checkpoint.json").read_text())
        h = json.loads((sd / "supervisor/health.json").read_text())
        facts["supervisor"] = {"polls": ck.get("polls"), "since": ck.get("started"), "last_poll": ck.get("last_poll"),
                               "model_calls": h.get("model_calls"), "model_tokens": h.get("model_tokens"),
                               "status": h.get("status")}
    except (OSError, ValueError):
        facts["supervisor"] = "UNKNOWN"
    inc = sd / "supervisor/incidents.sqlite3"
    r = _sqlite(inc, "select state,count(*) from incidents group by 1")
    facts["incidents_by_state"] = dict(r) if isinstance(r, list) else r
    att = _sqlite(inc, "select json_extract(record,'$.status'),count(*) from repair_attempts group by 1")
    facts["repair_attempts_by_status"] = dict(att) if isinstance(att, list) else att
    les = _sqlite(sd / "knowledge/lessons.sqlite3", "select state,count(*) from lessons group by 1")
    facts["lessons_by_state"] = dict(les) if isinstance(les, list) else les
    ev = _sqlite(sd / "events/events.sqlite3", "select channel,count(*) from events group by 1")
    facts["events_by_channel"] = dict(ev) if isinstance(ev, list) else ev
    pk: Counter = Counter()
    wos = sorted((sd / "workorders").glob("*/workspace")) if (sd / "workorders").is_dir() else []
    for w in wos:
        p = w / ".forge-run/package.json"
        try:
            pk[json.loads(p.read_text()).get("package_status") or "UNKNOWN"] += 1
        except (OSError, ValueError):
            pk["NO_PACKAGE"] += 1
    facts["work_orders"] = len(wos)
    facts["packages_by_status"] = dict(pk)
    arch = data_root() / "archives"
    facts["archives"] = len(list(arch.iterdir())) if arch.is_dir() else "UNKNOWN"
    return facts


def _tracked_files(root: Path) -> list[str]:
    r = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    return sorted(x for x in r.stdout.decode().split("\0") if x and (root / x).is_file())


def source_inventory(root: Path | None = None, sums: Path | None = None) -> dict:
    """Current tracked files vs the historical SHA256SUMS inventory (never modifies the historical files)."""
    root = root or REPO_ROOT
    sums = sums or root / "SHA256SUMS.txt"
    hist: dict[str, str] = {}
    if sums.is_file():
        for line in sums.read_text().splitlines():
            if "  " in line:
                h, p = line.split("  ", 1)
                hist[p] = h
    cur = {p: sha256_file(root / p) for p in _tracked_files(root)}
    cls = {"UNCHANGED": [], "CHANGED": [], "ADDED_SINCE_HISTORICAL": [], "MISSING_FROM_TREE": []}
    for p, h in cur.items():
        cls["UNCHANGED" if hist.get(p) == h else "CHANGED" if p in hist else "ADDED_SINCE_HISTORICAL"].append(p)
    cls["MISSING_FROM_TREE"] = sorted(set(hist) - set(cur))
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    return {"schema": "forge-c/cre-source-inventory/1.0", "git_head": git_head,
            "historical_inventory": {"file": sums.name, "entries": len(hist),
                                     "status": "STALE" if any(cls[k] for k in ("CHANGED", "MISSING_FROM_TREE",
                                                                               "ADDED_SINCE_HISTORICAL")) else "CURRENT"},
            "counts": {k: len(v) for k, v in cls.items()}, "tracked_files": len(cur),
            "changed": cls["CHANGED"], "missing_from_tree": cls["MISSING_FROM_TREE"],
            "files": [{"path": p, "sha256": h} for p, h in cur.items()]}


def render_markdown(facts: dict | None = None, inv: dict | None = None) -> str:
    lines = ["# CRE-T001 — capability matrix of features 001–003 (evidence-based)", "",
             "Generated by `python -m forge_factory.reliability.audit`. Status words come from code + recorded task "
             "evidence (`evidence/v0.4/runs/<task>/latest.json`); `tests/test_cre_d0_audit.py` fails when a row cites a "
             "missing module or non-PASS evidence, or when this file drifts from the data.", "",
             "| ID | Component | Status | Evidence (tasks) | Finding / gap for CRE |", "|---|---|---|---|---|"]
    for c in CAPABILITIES:
        lines.append(f"| {c['id']} | {c['component']} | **{c['status']}** | {', '.join(c['evidence']) or '-'} | "
                     f"{c['finding']} |")
    n = Counter(c["status"] for c in CAPABILITIES)
    lines += ["", f"Totals: {', '.join(f'{k} {n.get(k, 0)}' for k in STATUSES)}.", "",
              "Live facts and the current source inventory are machine records: `evidence/cre/baseline/capability-"
              "facts.json`, `evidence/cre/baseline/source-inventory.json` (regenerated by the audit; not embedded here "
              "so this document stays deterministic).", "",
              "## Dependencies for feature 004", "",
              "* C14–C18 are MISSING and are built by CRE-T005..T034 as extensions of C03/C04/C05/C06/C10/C11 "
              "(no second supervisor, ledger, KPI store or packager).",
              "* C02 (Fabro-native crash resume) and C05 (repair scope) limit what D2/D7 can demonstrate on real "
              "infrastructure; affected tasks report BLOCKED/NOT_RUN where a real dependency is missing.",
              "* C19: `scripts/verify_bundle.py` fails against the evolving tree by design of the historical snapshot; "
              "it is recorded as an observed constraint in the CRE-T002 baseline, not repaired by rewriting history.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    out = REPO_ROOT / "evidence/cre/baseline"
    out.mkdir(parents=True, exist_ok=True)
    (out / "capability-facts.json").write_text(pretty_json(live_facts()))
    inv = source_inventory()
    (out / "source-inventory.json").write_text(pretty_json(inv))
    (REPO_ROOT / "docs/cre-capability-matrix.md").write_text(render_markdown())
    issues = consistency_issues()
    print(f"CRE-T001 capability matrix: {Counter(c['status'] for c in CAPABILITIES)}; consistency issues: "
          f"{len(issues)}; historical inventory {inv['historical_inventory']['status']} {inv['counts']}")
    for i in issues:
        print("  ", i)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
