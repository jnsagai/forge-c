"""T045/T046 — deterministic v0.4 finalizer: READY_FOR_OFFLINE_REVIEW or BLOCKED offline review package.

* Reuses the unchanged v0.3 packager (`build_review_package.build`) with the versioned v0.4 policy
  (strict superset of v0.3, pinned by hash). v0.3 files are never modified.
* Every quality check is derived from recorded evidence (inspection gates, tool-results.jsonl written by
  MCP servers, trace validation); absence of evidence => false => gap. Nothing is synthesised to pass.
* SUP.1/8/9/10 status reports and the operational inventory are generated from real records only.
* Target verification without target evidence is NOT_PERFORMED (=> BLOCKED). No safety approval field.
* Archives are write-once (refuse overwrite, chmod 0444). Callable from the workflow `finalize` node,
  the evidence MCP, or the external supervisor finalizer for crashed/exhausted runs.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, sha256_bytes, sha256_file, state_dir, utc_now
from ..events.emit import emit, events_dir
from ..inspection.engine import PHASES, Store

POLICY_V04 = REPO_ROOT / "factory/release-manager/policies/release-package-policy-v0.4.json"
POLICY_V05 = REPO_ROOT / "factory/release-manager/policies/release-package-policy-v0.5.json"
POLICY_V03 = REPO_ROOT / "factory/release-manager/policies/release-package-policy.json"
NOT_SAFETY = "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED"


def archive_root() -> Path:
    return Path(os.environ.get("FORGE_ARCHIVE_DIR") or state_dir().parent / "archives")


def _packager():
    sys.path.insert(0, str(REPO_ROOT / "factory/release-manager/scripts"))
    import build_review_package  # noqa: E402 - v0.3 packager, used unchanged

    return build_review_package


def tool_results(ws: Path) -> list[dict]:
    p = ws / "evidence" / "tool-results.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []


def latest(results: list[dict], server: str, op: str, pred=None) -> dict | None:
    for r in reversed(results):
        if r["server"] == server and r["op"] == op and (pred is None or pred(r)):
            return r
    return None


def _w(dst: Path, rel: str, data: str | bytes) -> None:
    p = dst / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data.encode() if isinstance(data, str) else data)


def _copy_tree(src: Path, dst: Path, pattern: str = "*") -> int:
    n = 0
    if src.is_dir():
        for f in sorted(src.rglob(pattern)):
            if f.is_file() and not f.is_symlink():
                t = dst / f.relative_to(src)
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, t)
                n += 1
    return n


def trace_check(ws: Path) -> tuple[bool, list[str]]:
    import re

    req = ws / "workproducts/SWE.1/software_requirements.md"
    tr = ws / "traceability/requirements_to_tests.csv"
    if not req.is_file() or not tr.is_file():
        return False, ["TRACE_INPUT_MISSING"]
    reqs = set(re.findall(r"\*\*(SWR-[A-Z0-9_.-]+)\*\*", req.read_text()))
    rows = list(csv.DictReader(io.StringIO(tr.read_text())))
    traced = {r.get("requirement_id", "").strip() for r in rows if (r.get("test_id") or "").strip()}
    missing = sorted(reqs - traced)
    phantom = []  # a cited test id must exist in its test file (no false traceability, r41)
    for r in rows:
        tid, tf = (r.get("test_id") or "").strip(), (r.get("test_file") or "").strip()
        f = ws / tf if tf else None
        if tid and f is not None and f.is_file() and not re.search(rf"\b{re.escape(tid)}\b", f.read_text(errors="replace")):
            phantom.append(f"TEST_ID_NOT_IN_FILE:{tid}")
    return bool(reqs) and not missing and not phantom, [f"UNTRACED:{m}" for m in missing[:20]] + phantom[:20]


def derive_gates(ws: Path, budgets: dict) -> tuple[dict, list[dict], dict]:
    store = Store(ws)
    res = tool_results(ws)
    gates = {p: store.gate(p) for p in PHASES}
    checks: dict[str, bool] = {f"swe{p[-1]}_inspection": gates[p]["decision"] == "PASS" for p in PHASES}
    ok = lambda r: r is not None and r["result"]["status"] == "PASS"  # noqa: E731
    cpp = latest(res, "forge-analysis-mcp", "cppcheck")
    cla = latest(res, "forge-analysis-mcp", "clang_analyze")
    checks["static_analysis"] = ok(cpp) and ok(cla)
    checks["misra_coverage_assessed"] = cpp is not None and (ws / "verification/static/misra_coverage_matrix.md").is_file()
    checks["unit_verification"] = ok(latest(res, "forge-tests-mcp", "run_unit"))
    checks["integration_verification"] = ok(latest(res, "forge-tests-mcp", "run_integration"))
    checks["software_verification"] = (gates["SWE.6"]["decision"] == "PASS" and checks["integration_verification"]
                                       and ok(latest(res, "forge-tests-mcp", "run_robot")))  # SWE.6 Robot suite
    tr_ok, tr_issues = trace_check(ws)
    checks["traceability"] = tr_ok
    size = latest(res, "forge-build-mcp", "measure_elf", lambda r: "target" in json.dumps(r["result"]["summary"]))
    stack = latest(res, "forge-build-mcp", "stack_usage", lambda r: "target" in json.dumps(r["result"]["summary"]))
    fp = {"flash_bytes": size["result"]["metrics"].get("flash_bytes") if size else None,
          "ram_bytes": size["result"]["metrics"].get("ram_bytes") if size else None,
          "max_frame_bytes": stack["result"]["metrics"].get("max_frame_bytes") if stack else None,
          "budgets": budgets, "scope": "object-level target build (cortex-m55, GNU Arm); not a linked firmware image"}
    checks["resource_budgets"] = bool(size and stack and budgets and fp["flash_bytes"] is not None
                                      and fp["flash_bytes"] <= budgets.get("flash_bytes", -1)
                                      and fp["ram_bytes"] <= budgets.get("static_ram_bytes", -1)
                                      and fp["max_frame_bytes"] <= budgets.get("stack_bytes", -1))
    tgt = [r for r in res if r["server"] == "forge-sim-mcp" and r["op"] in ("run_renode", "run_hwsim")]
    checks["target_verification"] = any(ok(r) for r in tgt)
    checks["safety_gaps_declared"] = True  # known_limitations.md is always generated from facts below
    findings: list[dict] = []
    for p in PHASES:
        ins = store.inspections(p)
        if ins and ins[-1]["verdict"] != "PASS":
            findings += [{"id": f"{p}:{f['id']}", "severity": f["severity"], "detail": f.get("detail", "")[:160]}
                         for f in ins[-1]["findings"]]
        if gates[p]["decision"] != "PASS":
            findings.append({"id": f"{p}:GATE_{gates[p]['decision']}", "severity": "major",
                             "detail": gates[p]["reason"][:160]})
    findings += [{"id": i, "severity": "major", "detail": "traceability"} for i in tr_issues]
    gl = ws / "verification/static/hal_guideline_conformance.json"
    if gl.is_file():
        rep = json.loads(gl.read_text())
        if rep["verdict"] != "PASS":
            findings.append({"id": "SWE3-07:HAL_GUIDELINE", "severity": "major",
                             "detail": f"{len(rep['violations'])} guideline violations"})
    rid_f = ws / ".forge-run" / "fabro_run_id"
    if rid_f.is_file():  # T028: unresolved infrastructure incidents affecting this run's provenance block it
        from ..supervisor.store import IncidentStore

        rid = rid_f.read_text().strip()
        for inc in IncidentStore().all(500):
            if inc.get("run_id") == rid and inc["state"] != "RESOLVED":
                findings.append({"id": f"INCIDENT:{inc['incident_id']}", "severity": "major",
                                 "detail": f"{inc['component']}/{inc['fault_type']} {inc['state']}"})
    from ..inspection import defects  # ADR-0008: open/escalated defects are unresolved findings (never hidden)

    findings += [{"id": g, "severity": "major", "detail": "defect register"} for g in defects.gaps(ws)]
    detail = {"gates": gates, "footprint": fp, "tool_results_considered": len(res),
              "target_runs": [r["result"]["status"] for r in tgt]}
    return checks, findings, detail


def operational_inventory(ws: Path, stage: Path, run_id: str, fabro_run_id: str | None) -> None:
    from ..knowledge.store import LessonStore
    from ..mcp.preflight import op_catalog
    from ..supervisor.store import IncidentStore

    lock = json.loads((REPO_ROOT / "config/factory/skills.lock.json").read_text())
    _w(stage, "operations/agents/skills-manifest.json", pretty_json(lock))
    _w(stage, "operations/mcp/tool-registry.json", pretty_json(op_catalog()))
    hp = state_dir() / "supervisor" / "health.json"
    _w(stage, "operations/supervisor/health-summary.json",
       hp.read_text() if hp.is_file() else pretty_json({"status": "UNKNOWN", "reason": "no supervisor health sample"}))
    ist = IncidentStore()
    _w(stage, "operations/incidents/incidents.jsonl",
       "".join(json.dumps(ist.to_contract(i), sort_keys=True) + "\n" for i in ist.all(500)) or "\n")
    _w(stage, "operations/repairs/repair-results.jsonl",
       "".join(json.dumps(a, sort_keys=True) + "\n" for a in ist.attempts()) or "\n")
    lessons = LessonStore().list()
    _w(stage, "operations/knowledge/lesson-ledger.json",
       pretty_json([{k: le.get(k) for k in ("lesson_id", "state", "source_incident_id", "source_attempt_id", "hash",
                                            "created_at", "expires_at")} for le in lessons]))
    seg = []
    for f in sorted(events_dir().glob("*.jsonl")) if events_dir().is_dir() else []:
        seg.append({"segment": f.name, "sha256": sha256_file(f), "bytes": f.stat().st_size})
    pol = (REPO_ROOT / "config/factory/trace-policy.yaml").read_text()
    _w(stage, "operations/telemetry/events-index.json",
       pretty_json({"event_schema": "specs/002-self-healing-factory/contracts/event.schema.json",
                    "capture_policy_sha256": sha256_bytes(pol.encode()), "segments": seg}))
    _w(stage, "operations/telemetry/capture-policy.yaml", pol)
    usage = token_usage(fabro_run_id, ws)
    _w(stage, "operations/tokens/usage-by-agent.json", pretty_json(usage))
    _w(stage, "operations/run/run-summary.json",
       pretty_json({"run_id": run_id, "fabro_run_id": fabro_run_id, "finalized_at": utc_now(),
                    "workspace_head": _git(ws, "rev-parse", "HEAD"), "dirty": bool(_git(ws, "status", "--porcelain"))}))


def token_usage(fabro_run_id: str | None, ws: Path | None = None) -> dict:
    if not fabro_run_id:
        return {"basis": "unknown", "reason": "no Fabro run id", "by_stage": []}
    try:
        from ..fabro.client import FabroClient, client_for_workspace, load_token

        c = client_for_workspace(ws, timeout=10) if ws is not None else FabroClient(token=load_token(), timeout=10)
        u = c.usage(fabro_run_id)
        stages = [{"stage": s["stage"]["id"], "model": s["model"]["model_id"], "provider": s["model"]["provider"],
                   "tokens_input": s["usage"]["tokens"]["input"], "tokens_output": s["usage"]["tokens"]["output"],
                   "state": s.get("state")} for s in u.get("stages", [])]
        return {"basis": "reported", "source": "fabro /runs/{id}/usage", "by_stage": stages,
                "total_input": sum(s["tokens_input"] for s in stages),
                "total_output": sum(s["tokens_output"] for s in stages)}
    except Exception as exc:  # noqa: BLE001
        return {"basis": "unknown", "reason": f"usage unavailable: {type(exc).__name__}", "by_stage": []}


def _git(ws: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ws, capture_output=True, text=True, timeout=20, check=False).stdout.strip()
    except OSError:
        return ""


def sup_reports(ws: Path, stage: Path, checks: dict, findings: list[dict], detail: dict) -> None:
    rows = "\n".join(f"| {k} | {'PASS' if v else 'NOT MET'} |" for k, v in sorted(checks.items()))
    _w(stage, "support/SUP.1/quality_assurance_status.md",
       "# SUP.1 Quality assurance status (generated from recorded gate evidence)\n\n| Check | Status |\n|---|---|\n"
       f"{rows}\n\nGate decisions per phase: `{json.dumps({p: g['decision'] for p, g in detail['gates'].items()})}`\n")
    store = Store(ws)
    bl = "\n".join(f"- {p}: " + ", ".join(f"{b['baseline_id']} `{b['baseline_hash'][:16]}`" for b in store.baselines(p))
                   for p in PHASES)
    _w(stage, "support/SUP.8/configuration_status.md",
       f"# SUP.8 Configuration status (generated)\n\nWorkspace commit: `{_git(ws, 'rev-parse', 'HEAD')}`\n\n"
       f"## Frozen baselines\n{bl}\n")
    fl = "\n".join(f"- `{f['id']}` ({f['severity']}): {f['detail']}" for f in findings) or "- none open"
    from ..inspection import defects

    rv = "\n".join(f"- {x}" for x in defects.review_items(ws)) or "- none"
    _w(stage, "support/SUP.9/problem_resolution_status.md",
       f"# SUP.9 Problem resolution status (generated)\n\n## Open findings\n{fl}\n\n"
       "## Defects filed or declared by the deterministic gate (human review required)\n"
       f"{rv}\n")
    revs = {p: len(store.baselines(p)) for p in PHASES}
    _w(stage, "support/SUP.10/change_request_status.md",
       "# SUP.10 Change request status (generated)\n\nBaseline revisions per phase (each revision after the first "
       f"is a rework/change requiring re-inspection): `{json.dumps(revs)}`\n")


def known_limitations(stage: Path, checks: dict, detail: dict, disabled: list[str]) -> None:
    lines = ["# Known limitations and declared safety gaps (generated from facts)", "",
             "- This package is an offline review candidate. It is NOT an ISO 26262 / ASIL B approval, ASPICE "
             "capability determination, tool qualification or production release.",
             "- Unit/integration tests and coverage are HOST executions; they are not target (MCU) evidence.",
             "- MISRA C: Cppcheck addon subset only; MISRA compliance is NOT claimed.",
             "- Target verification: " + ("performed" if checks["target_verification"]
                                          else "NOT_PERFORMED (no target/simulator evidence)") + ".",
             f"- Footprint scope: {detail['footprint']['scope']}.",
             "- Disabled optional tools/operations: " + (", ".join(disabled) or "none")]
    lines += [f"- Unmet check: `{k}`" for k, v in sorted(checks.items()) if not v]
    _w(stage, "safety/known_limitations.md", "\n".join(lines) + "\n")


def build_staging(ws: Path, stage: Path, run_id: str, fabro_run_id: str | None) -> dict:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    wo = json.loads((ws / ".forge-run/manifest.json").read_text()) if (ws / ".forge-run/manifest.json").is_file() else {}
    budgets = wo.get("budgets", {})
    for d in ("workproducts", "safety", "traceability", "verification", "inspection", "configuration"):
        _copy_tree(ws / d, stage / d)
    for d in ("hal", "ll", "src", "include", "tests"):
        _copy_tree(ws / "software" / d, stage / "software" / d)
    # policy-required flat views (documented in manifest): C sources -> software/src, headers -> software/include
    for d in ("hal", "src"):
        for f in sorted((ws / "software" / d).glob("*.c")) if (ws / "software" / d).is_dir() else []:
            _w(stage, f"software/src/{f.name}", f.read_bytes())
    for d in ("hal", "ll", "include"):
        for f in sorted((ws / "software" / d).glob("*.h")) if (ws / "software" / d).is_dir() else []:
            _w(stage, f"software/include/{f.name}", f.read_bytes())
    tb = ws / "build" / "target-cm55-gcc"
    for name in ("driver.elf", "driver.map"):
        if (tb / name).is_file():
            _w(stage, f"software/build/{name}", (tb / name).read_bytes())
    _copy_tree(ws / "build" / "doxygen" / "html", stage / "documentation" / "doxygen")  # owner addendum: code docs
    for f in sorted(ws.glob("workproducts/SWE.*/traceability/matrix_*")):  # owner addendum: the six matrices together
        _w(stage, f"traceability/matrices/{f.name}", f.read_bytes())
    _copy_tree(ws / "evidence" / "raw", stage / "evidence-raw")
    if (ws / "evidence/tool-results.jsonl").is_file():
        _w(stage, "verification/tool-results.jsonl", (ws / "evidence/tool-results.jsonl").read_bytes())
    for f in sorted((ws / ".forge-run/defects").glob("DEF-*.json")) if (ws / ".forge-run/defects").is_dir() else []:
        _w(stage, f"defects/{f.name}", f.read_bytes())  # full defect log incl. REJECTED reasons and TEST declarations
    for p in PHASES:
        ins = Store(ws).inspections(p)
        if ins:
            _w(stage, f"inspection/{p}/inspection_record.json", pretty_json(ins[-1]))
    checks, findings, detail = derive_gates(ws, budgets)
    res = tool_results(ws)

    def summary(server: str, op: str, extra: dict | None = None) -> str:
        r = latest(res, server, op)
        return pretty_json({"status": r["result"]["status"] if r else "NOT_RUN", "result": r["result"] if r else None,
                            **(extra or {})})

    _w(stage, "verification/static/analysis_summary.json",
       pretty_json({"cppcheck": json.loads(summary("forge-analysis-mcp", "cppcheck")),
                    "clang_analyze": json.loads(summary("forge-analysis-mcp", "clang_analyze")),
                    "misra_compliance": "NOT_CLAIMED"}))
    _w(stage, "verification/unit/unit_verification_summary.json", summary("forge-tests-mcp", "run_unit",
                                                                         {"environment": "host"}))
    _w(stage, "verification/integration/integration_verification_summary.json",
       summary("forge-tests-mcp", "run_integration", {"environment": "host"}))
    _w(stage, "verification/software/software_verification_summary.json",
       pretty_json({"swe6_gate": detail["gates"]["SWE.6"], "integration_status": checks["integration_verification"]}))
    _w(stage, "verification/coverage/coverage_summary.json", summary("forge-tests-mcp", "llvm_coverage",
                                                                    {"environment": "host"}))
    _w(stage, "verification/footprint/memory_stack_summary.json", pretty_json(detail["footprint"]))
    _w(stage, "verification/target/target_verification_summary.json",
       pretty_json({"status": "PERFORMED" if checks["target_verification"] else "NOT_PERFORMED",
                    "runs": detail["target_runs"]}))
    from ..mcp.preflight import op_catalog

    disabled = sorted(k for k, e in op_catalog().items() if e["status"] == "DISABLED")
    known_limitations(stage, checks, detail, disabled)
    sup_reports(ws, stage, checks, findings, detail)
    if not (stage / "configuration/target_baseline.json").is_file():
        _w(stage, "configuration/target_baseline.json", pretty_json(wo.get("target", {"status": "UNSPECIFIED"})))
    inv = REPO_ROOT / "evidence/v0.4/inventory/tool-inventory.json"
    if inv.is_file():
        _w(stage, "configuration/toolchain_versions.json", inv.read_bytes())
    operational_inventory(ws, stage, run_id, fabro_run_id)
    all_phases_pass = all(detail["gates"][p]["decision"] == "PASS" for p in PHASES)
    quality = {"run_status": "COMPLETED" if all_phases_pass else "INCOMPLETE", "checks": checks,
               "open_findings": findings, "derived_from": "recorded evidence only", "generated_at": utc_now(),
               "safety_approval": "NOT_APPLICABLE_OFFLINE_HUMAN_DECISION"}
    _w(stage, "quality/final-gates.json", pretty_json(quality))
    return quality


def finalize(ws: Path, run_id: str, fabro_run_id: str | None = None) -> dict:
    ws = Path(ws).resolve()
    out_dir = archive_root() / run_id
    if out_dir.exists() and any(out_dir.glob("*.zip")):
        prev = json.loads((out_dir / "finalize-result.json").read_text())
        return {**prev, "note": "already finalized; archives are write-once"}
    stage = archive_root() / "staging" / run_id
    quality = build_staging(ws, stage, run_id, fabro_run_id)
    pk = _packager()
    import tempfile

    with tempfile.TemporaryDirectory() as dry:  # status under v0.4 rules (KPI files can only add, never remove gaps)
        dry_status = pk.build(stage, Path(dry), run_id, POLICY_V04)["package_status"]
    kpi_snapshot_into(ws, stage, dry_status)
    from ..reliability.evidence import bundle_into  # feature 004: CRE evidence (never changes the package status)

    bundle_into(ws, stage, dry_status)
    from ..assurance.package import bundle_into as easa_bundle  # feature 006: changes status only in ENFORCING mode

    try:
        easa_bundle(ws, stage, dry_status)
    except Exception as exc:  # noqa: BLE001 - observe-only evidence must never break packaging
        _w(stage, "assurance/error.json", pretty_json({"error": f"{type(exc).__name__}: {exc}"[:300]}))
    sealed: dict = {}

    def seal(_key: str) -> dict:
        res = pk.build(stage, out_dir, run_id, POLICY_V05)
        with pk.zipfile.ZipFile(res["archive"]) as z:
            gaps = json.loads(z.read("missing_artifacts.json"))["gaps"]
        for f in out_dir.iterdir():
            os.chmod(f, 0o444)
        out = {"run_id": run_id, "package_status": res["package_status"], "archive": res["archive"],
               "archive_sha256": res["archive_sha256"], "archive_ref": f"archive:sha256:{res['archive_sha256']}",
               "gap_count": res["gap_count"], "gaps": gaps, "quality_run_status": quality["run_status"],
               "scope": NOT_SAFETY, "policy": str(POLICY_V05.relative_to(REPO_ROOT)), "finalized_at": utc_now()}
        os.chmod(out_dir, 0o755)  # noqa: S103 - archive dir must stay listable; members are 0444
        (out_dir / "finalize-result.json").write_text(pretty_json(out))
        os.chmod(out_dir / "finalize-result.json", 0o444)
        sealed["out"] = out
        return {"archive_sha256": res["archive_sha256"], "package_status": res["package_status"]}

    from ..reliability.production import JournalRefused, guarded  # CRE-T045: archive write is journaled

    j = guarded("archive_write", f"archive_write:{run_id}", seal)
    if not j["executed"]:  # enforcing modes only: journaled DONE but no archive on disk, or unknown outcome
        raise JournalRefused(j["status"], f"archive_write:{run_id}")
    out = sealed["out"]
    (ws / ".forge-run").mkdir(exist_ok=True)
    (ws / ".forge-run" / "package.json").write_text(pretty_json(out))
    emit("human", "INFO" if out["package_status"] == "READY_FOR_OFFLINE_REVIEW" else "WARN",
         f"Package {out['package_status']} gaps={out['gap_count']} run={run_id}", correlation_id=run_id, run_id=run_id,
         payload_ref=out["archive_ref"])
    return out


def kpi_snapshot_into(ws: Path, stage: Path, release_status: str) -> dict:
    """KPI-T015: order-scoped, deterministic KPI snapshot + catalog/policy/baselines/source events into the package."""
    from ..common import KPI_CONTRACTS_DIR
    from ..kpi.engine import serialize, snapshot
    from ..kpi.service import load_baselines
    from ..kpi.sources import collect_all, from_workspace, order_of

    man = json.loads((ws / ".forge-run/manifest.json").read_text()) if (ws / ".forge-run/manifest.json").is_file() else {}
    order = order_of(ws.parent.name, man) if man else ws.parent.name
    try:
        evs = [e for e in collect_all() if e["order_id"] in (order, "factory")]
    except Exception:  # noqa: BLE001 - KPI collection must not prevent packaging; snapshot records the gap
        evs = []
    if man and not any(e["attempt_id"] == ws.parent.name for e in evs):
        evs += from_workspace(ws)
    start = min([e["ts_utc"] for e in evs if e["order_id"] == order] or [utc_now()[:19] + "Z"])
    snap = snapshot(evs, start, utc_now()[:19] + "Z", release_status, load_baselines())
    _w(stage, "operations/kpi/kpi-snapshot.json", serialize(snap))
    _w(stage, "operations/kpi/kpi-catalog.json", (KPI_CONTRACTS_DIR / "kpi-catalog.json").read_bytes())
    _w(stage, "operations/kpi/kpi-policy.yaml", (REPO_ROOT / "config/factory/kpi-policy.yaml").read_bytes())
    _w(stage, "operations/kpi/kpi-baselines.json", pretty_json(load_baselines()))
    _w(stage, "operations/kpi/kpi-source-events.jsonl",
       "".join(json.dumps(e, sort_keys=True) + "\n" for e in evs) or "\n")
    return snap


def cross_check_kpis(archive: Path) -> dict:
    """KPI-T016: archive KPI snapshot vs package status, event evidence and the no-approval rule."""
    import zipfile

    from ..kpi.sources import event_set_digest

    issues = []
    with zipfile.ZipFile(archive) as z:
        man = json.loads(z.read("manifest.json"))
        snap = json.loads(z.read("evidence/operations/kpi/kpi-snapshot.json"))
        evs = [json.loads(x) for x in z.read("evidence/operations/kpi/kpi-source-events.jsonl").decode().splitlines() if x]
        cat = json.loads(z.read("evidence/operations/kpi/kpi-catalog.json"))
    if snap["release_status"] != man["status"]:
        issues.append(f"STATUS_MISMATCH:{snap['release_status']}!={man['status']}")
    win = [e for e in evs if snap["window_start"] <= e["ts_utc"] <= snap["window_end"]]
    if event_set_digest(win) != snap["event_set_digest"]:
        issues.append("EVENT_SET_DIGEST_MISMATCH")
    from ..common import canonical_json, sha256_bytes
    if sha256_bytes(canonical_json(cat)) != snap.get("source_catalog_hash"):
        issues.append("CATALOG_HASH_MISMATCH")
    k20 = [m for m in snap["metric_values"] if m["metric_id"] == "K20"]
    if not k20 or k20[0]["value"] != 0:
        issues.append(f"K20_SAFETY_PROCESS_VIOLATIONS:{k20[0]['value'] if k20 else 'missing'}")
    blob = json.dumps(snap).replace("NOT_SAFETY_APPROVED", "")
    if "ASIL_B_APPROVED" in blob or '"APPROVED"' in blob:
        issues.append("APPROVAL_ASSERTION_FOUND")
    if man["scope"] != NOT_SAFETY:
        issues.append("PACKAGE_SCOPE_NOT_OFFLINE_REVIEW")
    return {"archive": str(archive), "status": "PASS" if not issues else "FAIL", "issues": issues,
            "snapshot_id": snap["snapshot_id"], "metrics": len(snap["metric_values"])}


def verify_archive(archive: Path) -> dict:
    """AT-25: recompute every member hash against the embedded SHA256SUMS and the external .sha256."""
    import hashlib
    import zipfile

    issues = []
    side = archive.with_name(archive.name + ".sha256")
    if side.is_file() and side.read_text().split()[0] != hashlib.sha256(archive.read_bytes()).hexdigest():
        issues.append("ARCHIVE_SHA256_MISMATCH")
    try:
        with zipfile.ZipFile(archive) as z:
            sums: dict[str, str] = {}
            for line in z.read("SHA256SUMS.txt").decode().splitlines():
                digest, member = line.split("  ", 1)
                sums[member] = digest
            for name in z.namelist():
                if name == "SHA256SUMS.txt":
                    continue
                if sums.get(name) != hashlib.sha256(z.read(name)).hexdigest():
                    issues.append(f"MEMBER_HASH_MISMATCH:{name}")
    except (zipfile.BadZipFile, KeyError) as exc:
        issues.append(f"ARCHIVE_UNREADABLE:{type(exc).__name__}")
    return {"archive": str(archive), "integrity": "PASS" if not issues else "FAIL", "issues": issues}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", type=Path, default=Path("."))
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--fabro-run-id", default=os.environ.get("FABRO_RUN_ID"))
    a = ap.parse_args(argv)
    rid_file = a.workspace / ".forge-run" / "fabro_run_id"
    fabro_id = a.fabro_run_id or (rid_file.read_text().strip() if rid_file.is_file() else None)
    out = finalize(a.workspace, a.run_id, fabro_id)
    print(json.dumps({k: out[k] for k in ("package_status", "gap_count", "archive_sha256")}))
    return 0  # BLOCKED is a valid, complete handover outcome


if __name__ == "__main__":
    raise SystemExit(main())
