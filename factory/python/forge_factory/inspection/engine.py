"""T009 — SWE.1–SWE.6 author/inspector process integrity (deterministic, model-free).

* Checklists: v0.4 overlays extend the hash-pinned v0.3 lists (factory/checklists/v0.4).
* Baselines: phase outputs are frozen to a content hash that also records the upstream baselines it was
  built on; any upstream change makes downstream baselines STALE (change-impact reinspection, AT-08).
* Inspections: append-only records (`open(..., "x")`), immutable initial verdicts; inspector role must be
  the phase inspector and differ from the author; a stale baseline hash cannot PASS.
* Deterministic checklist items (e.g. SWE1-07 EARS) are computed here and override inspector verdicts.
* Gate: PASS only if the latest inspection covers the *current* baseline and every required item passes;
  otherwise REWORK until `maximum_rework_cycles`, then BLOCKED (-> Release Manager BLOCKED package).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..common import REPO_ROOT, canonical_json, pretty_json, sha256_bytes, sha256_file, utc_now
from ..events.emit import emit
from .ears import check_file

PHASES = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
UPSTREAM = {"SWE.1": [], "SWE.2": ["SWE.1"], "SWE.3": ["SWE.1", "SWE.2"], "SWE.4": ["SWE.1", "SWE.3"],
            "SWE.5": ["SWE.2", "SWE.3", "SWE.4"], "SWE.6": ["SWE.1", "SWE.3", "SWE.4", "SWE.5"]}
PHASE_PATHS = {
    "SWE.1": ["workproducts/SWE.1", "safety/software_safety_requirements.md", "traceability"],
    "SWE.2": ["workproducts/SWE.2"],
    "SWE.3": ["workproducts/SWE.3", "software/src", "software/include", "software/hal", "software/ll"],
    "SWE.4": ["workproducts/SWE.4", "software/tests/unit", "verification/unit"],
    "SWE.5": ["workproducts/SWE.5", "software/tests/integration", "software/tests/target", "verification/integration"],
    "SWE.6": ["workproducts/SWE.6", "software/tests/software", "verification/software"],
}
SYSTEM_NAMES_FILE = "configuration/system_names.json"
# Deterministic presence gate before any freeze (r15/r43: lenient inspectors passed phases with missing outputs)
REQUIRED_OUTPUTS = {
    "SWE.1": ["workproducts/SWE.1/software_requirements.md", "traceability/requirements_to_tests.csv",
              "workproducts/SWE.1/software_requirements.reqif"],
    "SWE.2": ["workproducts/SWE.2/software_architecture.md", "workproducts/SWE.2/architecture_static.puml",
              "workproducts/SWE.2/architecture_dynamic.puml"],
    "SWE.3": ["workproducts/SWE.3/detailed_design.md", "software/hal/*.c", "software/hal/*.h", "software/ll/*.h"],
    "SWE.4": ["workproducts/SWE.4/unit_verification_report.md", "software/tests/unit/test_*.c"],
    "SWE.5": ["workproducts/SWE.5/integration_verification_report.md", "software/tests/integration/test_*.c"],
    "SWE.6": ["workproducts/SWE.6/software_verification_report.md", "software/tests/software/*.robot"],
}
TRACE_OUTPUTS = {"SWE.3": ["workproducts/SWE.3/unit_specifications.md", "workproducts/SWE.3/detailed_design/SWU-*.puml"]}
TRACE_CHECKS = ("swc_allocation", "unit_spec_and_code_trace", "unit_test_trace", "integration_test_trace",
                "validation_test_trace")
REQUIRED_TOOL_PASS = {"SWE.4": [("forge-tests-mcp", "run_unit")],
                      "SWE.5": [("forge-tests-mcp", "run_integration"),
                                ("forge-sim-mcp", "run_renode")],  # CAPA-009 (r81): failing target tests froze SWE.5
                      "SWE.6": [("forge-tests-mcp", "run_robot")]}


class InspectionError(ValueError):
    pass


def load_checklist(phase: str, root: Path = REPO_ROOT) -> dict:
    overlay = yaml.safe_load((root / f"factory/checklists/v0.4/{phase}.yaml").read_text())
    base_path = root / overlay["extends"]["path"]
    if sha256_file(base_path) != overlay["extends"]["sha256"]:
        raise InspectionError(f"CHECKLIST_BASE_TAMPERED:{phase}")
    base = yaml.safe_load(base_path.read_text())
    if overlay.get("policy_overrides"):
        raise InspectionError("CHECKLIST_POLICY_OVERRIDE_FORBIDDEN")
    checks = list(base["checks"]) + list(overlay.get("additional_checks") or [])
    ids = [c["id"] for c in checks]
    if len(ids) != len(set(ids)):
        raise InspectionError("CHECKLIST_DUPLICATE_ID")
    return {"phase": phase, "version": overlay["version"], "policy": base["policy"], "checks": checks,
            "sha256": sha256_bytes(canonical_json({"base": base, "overlay": overlay}))}


@dataclass
class Store:
    workspace: Path

    @property
    def base(self) -> Path:
        return self.workspace / "configuration" / "baselines"

    @property
    def insp(self) -> Path:
        return self.workspace / "inspection"

    def files_of(self, phase: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for rel in PHASE_PATHS[phase]:
            p = self.workspace / rel
            if p.is_file():
                out[rel] = sha256_file(p)
            elif p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file() and not f.is_symlink():
                        out[f.relative_to(self.workspace).as_posix()] = sha256_file(f)
        return out

    def current_hash(self, phase: str) -> str | None:
        files = self.files_of(phase)
        return sha256_bytes(canonical_json(files)) if files else None

    def baselines(self, phase: str) -> list[dict]:
        d = self.base / phase
        return [json.loads(p.read_text()) for p in sorted(d.glob("BL-*.json"))] if d.is_dir() else []

    def latest_baseline(self, phase: str) -> dict | None:
        b = self.baselines(phase)
        return b[-1] if b else None

    # -- operations ---------------------------------------------------------------------
    def freeze(self, phase: str, author_role: str) -> dict:
        if author_role != f"swe{phase[-1]}-author":
            raise InspectionError(f"AUTHOR_ROLE_MISMATCH:{author_role}")
        files = self.files_of(phase)
        if not files:
            raise InspectionError(f"NO_WORKPRODUCTS:{phase}")

        from .architecture import is_agent_reply

        for rel in files:  # an agent's status reply written over a workproduct is never frozen
            if rel.endswith((".md", ".c", ".h", ".csv")) and \
                    is_agent_reply((self.workspace / rel).read_text(errors="replace").strip()):
                raise InspectionError(f"WORKPRODUCT_IS_AGENT_REPLY:{rel}")
        upstream = {}
        for up in UPSTREAM[phase]:
            lb = self.latest_baseline(up)
            if lb is None or lb["baseline_hash"] != self.current_hash(up):
                raise InspectionError(f"UPSTREAM_NOT_FROZEN:{up}")
            upstream[up] = lb["baseline_hash"]
        bhash = sha256_bytes(canonical_json(files))
        latest = self.latest_baseline(phase)
        if latest and latest["baseline_hash"] == bhash and latest["upstream"] == upstream:
            return latest  # idempotent
        n = len(self.baselines(phase)) + 1
        rec = {"schema": "forge-c/baseline/0.4", "baseline_id": f"BL-{phase}-{n:03d}", "phase": phase,
               "author_role": author_role, "baseline_hash": bhash, "files": files, "upstream": upstream,
               "frozen_at": utc_now()}
        (self.base / phase).mkdir(parents=True, exist_ok=True)
        with open(self.base / phase / f"{rec['baseline_id']}.json", "x", encoding="utf-8") as f:
            f.write(pretty_json(rec))
        emit("workflow", "INFO", f"{phase} baseline {rec['baseline_id']} frozen", phase=phase, agent_id=author_role)
        return rec

    def missing_outputs(self, phase: str) -> list[str]:
        """Presence gate used by the production author gate before a phase may be frozen (r15/r43)."""
        from ..layer import layer_of, swtrace_enabled

        pats = REQUIRED_OUTPUTS.get(phase, []) + (TRACE_OUTPUTS.get(phase, []) if swtrace_enabled(self.workspace) else [])
        if phase == "SWE.3" and layer_of(self.workspace) == "LL":  # ADR-0009: an LL work order has no HAL files
            pats = [x for x in pats if not x.startswith("software/hal/")]
        out = [f"MISSING_REQUIRED_OUTPUT:{pat}" for pat in pats
               if not any(f.is_file() and f.stat().st_size > 0 for f in self.workspace.glob(pat))]
        if REQUIRED_TOOL_PASS.get(phase):
            from ..release.finalize import latest, tool_results

            res = tool_results(self.workspace)
            code_bl = self.latest_baseline("SWE.3") if PHASES.index(phase) > PHASES.index("SWE.3") else None
            for server, op in REQUIRED_TOOL_PASS[phase]:
                r = latest(res, server, op)
                if r is None or r["result"]["status"] != "PASS":
                    out.append(f"REQUIRED_TOOL_NOT_PASS:{op}:{r['result']['status'] if r else 'NOT_RUN'}")
                elif code_bl and r.get("ts_utc", "") < code_bl["frozen_at"]:
                    # ADR-0008: a PASS recorded before the current code baseline (e.g. before an upstream fix) is stale
                    out.append(f"REQUIRED_TOOL_STALE:{op}:before {code_bl['baseline_id']}")
        return out

    def stale_reason(self, phase: str, baseline: dict) -> str | None:
        if baseline["baseline_hash"] != self.current_hash(phase):
            return "BASELINE_CHANGED_AFTER_FREEZE"
        for up, h in baseline["upstream"].items():
            lb = self.latest_baseline(up)
            if lb is None or lb["baseline_hash"] != h or self.current_hash(up) != h:
                return f"UPSTREAM_CHANGED:{up}"
        return None

    def deterministic_items(self, phase: str, checklist: dict) -> dict[str, dict]:
        out = {}
        for c in checklist["checks"]:
            if c.get("deterministic_check") == "ears_conformance":
                req = self.workspace / "workproducts/SWE.1/software_requirements.md"
                names = None
                sn = self.workspace / SYSTEM_NAMES_FILE
                if sn.is_file():
                    names = set(json.loads(sn.read_text()))
                rep = check_file(req, names) if req.is_file() else {"verdict": "FAIL",
                                                                     "major_findings": ["SWE1:NO_REQUIREMENTS_FILE"]}
                rdir = self.insp / phase / "deterministic"
                rdir.mkdir(parents=True, exist_ok=True)
                rpath = rdir / f"{c['id']}-{utc_now().replace(':', '')}.json"
                rpath.write_text(pretty_json(rep))
                out[c["id"]] = {"verdict": rep["verdict"], "evidence_refs": [rpath.relative_to(self.workspace)
                                                                             .as_posix()],
                                "findings": rep["major_findings"][:20], "source": "deterministic"}
            elif c.get("deterministic_check") in ("architecture_structure", "register_map_conformance",
                                                  "implementation_completeness", "architecture_views", "reqif_export"):
                from .architecture import check_architecture
                from .implementation import check_implementation
                from .regmap import check_regmap
                from .reqif_export import OUT as REQIF_OUT
                from .reqif_export import validate as reqif_validate
                from .views import check_views

                def _reqif(ws: Path) -> dict:
                    p = ws / REQIF_OUT
                    if not p.is_file():
                        return {"verdict": "FAIL", "major_findings": ["REQIF:MISSING"]}
                    v = reqif_validate(p)
                    return {"verdict": v["verdict"], "major_findings": v["issues"], "spec_objects": v["spec_objects"]}

                rep = {"architecture_structure": check_architecture, "register_map_conformance": check_regmap,
                       "implementation_completeness": check_implementation, "architecture_views": check_views,
                       "reqif_export": _reqif}[c["deterministic_check"]](self.workspace)
                rdir = self.insp / phase / "deterministic"
                rdir.mkdir(parents=True, exist_ok=True)
                rpath = rdir / f"{c['id']}-{utc_now().replace(':', '')}.json"
                rpath.write_text(pretty_json(rep))
                out[c["id"]] = {"verdict": rep["verdict"], "evidence_refs": [rpath.relative_to(self.workspace)
                                                                             .as_posix()],
                                "findings": rep["major_findings"][:20], "source": "deterministic"}
            elif c.get("deterministic_check") in TRACE_CHECKS:
                from .swtrace import check_phase

                rep = check_phase(self.workspace, phase)
                rdir = self.insp / phase / "deterministic"
                rdir.mkdir(parents=True, exist_ok=True)
                rpath = rdir / f"{c['id']}-{utc_now().replace(':', '')}.json"
                rpath.write_text(pretty_json(rep))
                out[c["id"]] = {"verdict": rep["verdict"], "evidence_refs": [rpath.relative_to(self.workspace).as_posix()]
                                + [m["file"] for m in rep["matrices"]], "findings": rep["major_findings"][:20],
                                "source": "deterministic"}
            elif c.get("deterministic_check") == "hal_guideline_conformance":
                from .guideline import check_workspace

                rep = check_workspace(self.workspace)
                rdir = self.insp / phase / "deterministic"
                rdir.mkdir(parents=True, exist_ok=True)
                rpath = rdir / f"{c['id']}-{utc_now().replace(':', '')}.json"
                rpath.write_text(pretty_json(rep))
                out[c["id"]] = {"verdict": rep["verdict"],
                                "evidence_refs": [rpath.relative_to(self.workspace).as_posix()],
                                "findings": [f"{v['rule']}:{v['file']}:{v['line']}" for v in rep["violations"]][:20],
                                "source": "deterministic"}
        return out

    def record_inspection(self, phase: str, inspector_role: str, baseline_id: str, verdicts: dict[str, dict],
                          findings: list[dict] | None = None) -> dict:
        if inspector_role != f"swe{phase[-1]}-inspector":
            raise InspectionError(f"INSPECTOR_ROLE_MISMATCH:{inspector_role}")
        bl = next((b for b in self.baselines(phase) if b["baseline_id"] == baseline_id), None)
        if bl is None:
            raise InspectionError(f"UNKNOWN_BASELINE:{baseline_id}")
        if bl["author_role"] == inspector_role:
            raise InspectionError("AUTHOR_EQUALS_INSPECTOR")
        checklist = self.applicable(load_checklist(phase))
        stale = self.stale_reason(phase, bl)
        det = self.deterministic_items(phase, checklist)
        items, open_findings = {}, list(findings or [])
        for c in checklist["checks"]:
            v = det.get(c["id"]) or verdicts.get(c["id"])
            if not v or v.get("verdict") not in ("PASS", "FAIL", "NOT_APPLICABLE"):
                v = {"verdict": "FAIL", "evidence_refs": [], "findings": ["MISSING_VERDICT"]}
            if v["verdict"] == "PASS" and not v.get("evidence_refs"):
                v = {**v, "verdict": "FAIL", "findings": list(v.get("findings", [])) + ["NO_EVIDENCE_REF"]}
            if v["verdict"] == "NOT_APPLICABLE" and c.get("required"):
                v = {**v, "verdict": "FAIL", "findings": list(v.get("findings", [])) + ["REQUIRED_ITEM_NA"]}
            items[c["id"]] = v
            if v["verdict"] == "FAIL" and c.get("required"):
                open_findings.append({"id": f"{c['id']}", "severity": c["severity_if_failed"],
                                      "detail": "; ".join(map(str, v.get("findings", [])))[:200]})
        major = [f for f in open_findings if f.get("severity") in ("major", "critical")]
        verdict = "PASS" if not stale and not major else "FAIL"
        n = len(list((self.insp / phase).glob("INS-*.json"))) + 1 if (self.insp / phase).is_dir() else 1
        rec = {"schema": "forge-c/inspection/0.4", "inspection_id": f"INS-{phase}-{n:03d}", "phase": phase,
               "author_role": bl["author_role"], "inspector_role": inspector_role, "baseline_id": baseline_id,
               "baseline_hash": bl["baseline_hash"], "checklist_version": checklist["version"],
               "checklist_sha256": checklist["sha256"], "stale_reason": stale, "items": items,
               "findings": open_findings, "verdict": verdict, "recorded_at": utc_now()}
        (self.insp / phase).mkdir(parents=True, exist_ok=True)
        with open(self.insp / phase / f"{rec['inspection_id']}.json", "x", encoding="utf-8") as f:
            f.write(pretty_json(rec))
        emit("workflow", "INFO" if verdict == "PASS" else "WARN",
             f"{phase} {rec['inspection_id']} {verdict} findings={len(open_findings)}", phase=phase,
             agent_id=inspector_role)
        return rec

    def inspections(self, phase: str) -> list[dict]:
        d = self.insp / phase
        return [json.loads(p.read_text()) for p in sorted(d.glob("INS-*.json"))] if d.is_dir() else []

    def run_started(self) -> str:
        m = self.workspace / ".forge-run" / "manifest.json"
        try:
            return str(json.loads(m.read_text()).get("created_at") or "")
        except (OSError, ValueError):
            return ""

    def budget_start(self) -> str:
        """Start of the current rework-budget epoch (ADR-0008, owner decision 2026-10-15): the run start, then each
        upstream loop. Failed cycles before an upstream fix were spent on the code as it was; after the fix every
        phase gets its authored maximum again. Bounded: 1 + upstream-loop budget epochs (workflow max_visits)."""
        start = self.run_started()
        loops = self.workspace / ".forge-run" / "gates" / "upstream-loops.jsonl"
        if loops.is_file():
            for x in loops.read_text().splitlines():
                if x.strip():
                    start = max(start, str(json.loads(x).get("ts") or ""))
        return start

    def applicable(self, checklist: dict) -> dict:
        """Owner addendum checks (`applies_when: owner_trace_profile`) apply only to work orders that opted in."""
        from ..layer import swtrace_enabled

        on = swtrace_enabled(self.workspace)
        return {**checklist, "checks": [c for c in checklist["checks"]
                                        if c.get("applies_when") != "owner_trace_profile" or on]}

    def gate(self, phase: str) -> dict:
        checklist = load_checklist(phase)
        max_cycles = int(checklist["policy"]["maximum_rework_cycles"])
        ins = self.inspections(phase)
        bl = self.latest_baseline(phase)
        # r66: inspections carried over by --resume-from belong to another run's budget; only this run's count, and
        # only those of the current epoch (after the latest upstream loop)
        started = self.budget_start()
        failed = sum(1 for i in ins if i["verdict"] != "PASS" and i.get("recorded_at", "") >= started)
        if bl is None:
            decision, reason = ("REWORK" if failed < max_cycles else "BLOCKED"), "NO_BASELINE"
        else:
            stale = self.stale_reason(phase, bl)
            last = ins[-1] if ins else None
            if stale:
                decision, reason = ("REWORK" if failed < max_cycles else "BLOCKED"), stale
            elif last is None or last["baseline_hash"] != bl["baseline_hash"]:
                decision, reason = "REINSPECT", "NO_INSPECTION_FOR_CURRENT_BASELINE"
            elif last["verdict"] == "PASS":
                decision, reason = "PASS", last["inspection_id"]
            else:
                decision, reason = ("REWORK" if failed < max_cycles else "BLOCKED"), last["inspection_id"]
        return {"phase": phase, "decision": decision, "reason": reason, "failed_inspections": failed,
                "max_rework_cycles": max_cycles}

    def impacted_by(self, phase: str) -> list[str]:
        """Downstream phases whose latest baseline is now stale (AT-08)."""
        out = []
        for p in PHASES[PHASES.index(phase) + 1:]:
            bl = self.latest_baseline(p)
            if bl and self.stale_reason(p, bl):
                out.append(p)
        return out
