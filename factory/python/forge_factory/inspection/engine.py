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
    "SWE.5": ["workproducts/SWE.5", "software/tests/integration", "verification/integration"],
    "SWE.6": ["workproducts/SWE.6", "software/tests/software", "verification/software"],
}
SYSTEM_NAMES_FILE = "configuration/system_names.json"


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
            elif c.get("deterministic_check") == "architecture_structure":
                from .architecture import check_architecture

                rep = check_architecture(self.workspace)
                rdir = self.insp / phase / "deterministic"
                rdir.mkdir(parents=True, exist_ok=True)
                rpath = rdir / f"{c['id']}-{utc_now().replace(':', '')}.json"
                rpath.write_text(pretty_json(rep))
                out[c["id"]] = {"verdict": rep["verdict"], "evidence_refs": [rpath.relative_to(self.workspace)
                                                                             .as_posix()],
                                "findings": rep["major_findings"][:20], "source": "deterministic"}
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
        checklist = load_checklist(phase)
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

    def gate(self, phase: str) -> dict:
        checklist = load_checklist(phase)
        max_cycles = int(checklist["policy"]["maximum_rework_cycles"])
        ins = self.inspections(phase)
        bl = self.latest_baseline(phase)
        failed = sum(1 for i in ins if i["verdict"] != "PASS")
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
