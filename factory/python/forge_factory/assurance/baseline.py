"""EASA-T001/T004/T007 — independent baseline of Features 001-006 before any gate change.

* capability matrix: per feature, the task status comes ONLY from evidence records (a checked box without a passing
  evidence record is reported, not counted); the class is IMPLEMENTED / PARTIAL / SPEC_ONLY / MISSING;
* tool inventory: path, first version line and binary sha256 of what is actually installed (never assumed);
* approval modes: read from the live policies (CRE mode, EASA mode, AFO presence);
* locked references: sha256 of the baselined hardware inputs, the 006 contracts and the sealed review archives.
The audit writes only its own output file; `evidence_digest()` lets a test prove historical evidence is unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, data_root, load_yaml, pretty_json, sha256_bytes, sha256_file, utc_now
from . import contracts

FEATURES = {  # id: (spec dir, task-id regex, source packages that implement it)
    "001": ("specs/001-factory", r"`(T-\d{3})`", ("tools", "profiles")),
    "002": ("specs/002-self-healing-factory", r"\*\*(T\d{3})\b", (
        "factory/python/forge_factory/supervisor", "factory/python/forge_factory/repair",
        "factory/python/forge_factory/knowledge", "factory/python/forge_factory/inspection",
        "factory/python/forge_factory/release")),
    "003": ("specs/003-manufacturing-kpis", r"\*\*(KPI-T\d{3})\b", ("factory/python/forge_factory/kpi",)),
    "004": ("specs/004-continuous-reliability-engineering", r"\*\*(CRE-T\d{3})\b",
            ("factory/python/forge_factory/reliability",)),
    "005": ("specs/005-autonomous-factory-operations", r"\*\*(AFO-T\d{3})\b",
            ("factory/python/forge_factory/operations", "factory/python/forge_factory/conductor")),
    "006": ("specs/006-enhanced-ai-software-assurance", r"\*\*(EASA-T\d{3})\b",
            ("factory/python/forge_factory/assurance",)),
}
TOOLS = ("gcc", "clang", "llvm-cov", "llvm-profdata", "clang-tidy", "cppcheck", "gcovr", "arm-none-eabi-gcc", "robot",
         "plantuml", "renode", "cbmc", "frama-c", "git", "python3")


def _tasks(feature: str) -> list[dict]:
    spec, rx, _ = FEATURES[feature]
    p = REPO_ROOT / spec / "tasks.md"
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \[([ xX])\] .*?" + rx, line)
        if not m:
            continue
        refs = re.findall(r"`(evidence/v0\.4/runs/[^`]+)`", line)
        status = "NOT_RUN"
        if refs:
            ok = []
            for ref in refs:
                f = REPO_ROOT / ref
                rec = json.loads(f.read_text()) if f.is_file() else {}
                ok.append(rec.get("status") == "PASS" and rec.get("exit_code") == 0)
            status = "PASS" if all(ok) else "FAIL"
        checked = m.group(1) in "xX"
        if checked and status != "PASS":
            status = "CHECKED_WITHOUT_EVIDENCE"
        if status == "PASS" and not checked:
            status = "EVIDENCE_NOT_MARKED"
        out.append({"task": m.group(2), "checked": checked, "status": status, "evidence": refs})
    return out


def classify(spec_present: bool, tasks: list[dict], sources: list[str]) -> str:
    if not spec_present:
        return "MISSING"
    passed = sum(t["status"] == "PASS" for t in tasks)
    if tasks and passed == len(tasks):
        return "IMPLEMENTED"
    if passed or sources:
        return "PARTIAL"
    return "SPEC_ONLY"


def capability_matrix() -> list[dict]:
    rows = []
    for fid, (spec, _, pkgs) in FEATURES.items():
        tasks = _tasks(fid)
        present = (REPO_ROOT / spec / "spec.md").is_file() or (REPO_ROOT / spec / "tasks.md").is_file()
        sources = [p for p in pkgs if (REPO_ROOT / p).exists()]
        counts: dict[str, int] = {}
        for t in tasks:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        rows.append({"feature": fid, "spec_dir": spec, "spec_present": present, "tasks_total": len(tasks),
                     "task_status_counts": counts, "source_packages_present": sources,
                     "source_packages_missing": [p for p in pkgs if p not in sources],
                     "class": classify(present, tasks, sources)})
    return rows


def _which(tool: str) -> str | None:
    if tool == "renode":
        cand = sorted((data_root() / "toolchains/renode").glob("**/renode"))
        return str(cand[0]) if cand else shutil.which(tool)
    if tool == "plantuml":
        cand = sorted((data_root() / "toolchains/plantuml").glob("*.jar"))
        return str(cand[0]) if cand else shutil.which(tool)
    return shutil.which(tool)


def tool_inventory() -> list[dict]:
    out = []
    for t in TOOLS:
        p = _which(t)
        if not p:
            out.append({"tool": t, "status": "MISSING", "path": None, "version": None, "sha256": None})
            continue
        argv = ["java", "-jar", p, "-version"] if p.endswith(".jar") else [p, "--version"]
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            ver = next((ln.strip() for ln in (r.stdout + r.stderr).splitlines() if ln.strip()), "")[:120]
        except (OSError, subprocess.SubprocessError) as exc:
            ver = f"UNKNOWN ({type(exc).__name__})"
        real = Path(p).resolve()
        out.append({"tool": t, "status": "PRESENT", "path": p, "version": ver,
                    "sha256": sha256_file(real) if real.is_file() else None})
    return out


def approval_modes() -> dict:
    cre = load_yaml(REPO_ROOT / "config/factory/reliability-policy.yaml")
    easa_p = REPO_ROOT / "config/factory/assurance-policy.yaml"
    easa = load_yaml(easa_p) if easa_p.is_file() else None
    return {"cre_mode": cre.get("mode"), "cre_authorization": bool(cre.get("authorization")),
            "easa_policy_file": easa_p.is_file(),
            "easa_mode": (easa or {}).get("mode", "OBSERVE_ONLY (no policy file: default)"),
            "afo_runtime_present": any((REPO_ROOT / p).exists() for p in FEATURES["005"][2])}


def locked_references() -> list[dict]:
    refs = []
    man = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/inputs-manifest.json"
    if man.is_file():
        for d in json.loads(man.read_text())["documents"]:
            p = man.parent / d["markdown"]
            actual = sha256_file(p) if p.is_file() else None
            refs.append({"ref": f"hardware-input:{d['doc']}:{d['markdown']}", "expected": d["markdown_sha256"],
                         "actual": actual, "status": "OK" if actual == d["markdown_sha256"] else
                         ("MISSING" if actual is None else "MISMATCH")})
    refs.append({"ref": "easa-contracts", "expected": None,
                 "actual": sha256_bytes(canonical_json(contracts.contract_digests())), "status": "RECORDED"})
    for wo in ("WO-0002A-STM32N6-RCC-LL-r101", "WO-0002B-STM32N6-RCC-HAL-r102"):
        d = data_root() / "archives" / wo
        side = next(iter(sorted(d.glob("*.zip.sha256"))), None) if d.is_dir() else None
        if side is None:
            refs.append({"ref": f"archive:{wo}", "expected": None, "actual": None, "status": "NOT_VERIFIABLE"})
            continue
        expected = side.read_text().split()[0]
        z = side.with_suffix("")
        actual = sha256_file(z) if z.is_file() else None
        refs.append({"ref": f"archive:{wo}", "expected": expected, "actual": actual,
                     "status": "OK" if actual == expected else "MISMATCH"})
    return refs


def evidence_digest(root: Path = REPO_ROOT) -> str:
    """Digest of tracked historical evidence (blob ids from git) plus any uncommitted change under evidence/."""
    ls = subprocess.run(["git", "ls-files", "-s", "evidence"], cwd=root, capture_output=True, text=True,
                        check=True).stdout
    st = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "evidence"], cwd=root,
                        capture_output=True, text=True, check=True).stdout
    return sha256_bytes((ls + "\n--\n" + st).encode())


def audit() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                            text=True).stdout.strip()
    return {"schema": "forge-c/easa-baseline/0.1", "generated_at": utc_now(), "git_head": head, "branch": branch,
            "capabilities": capability_matrix(), "tools": tool_inventory(), "approval_modes": approval_modes(),
            "locked_references": locked_references(),
            "statement": "Engineering baseline only; no ISO 26262 / Automotive SPICE conformance claim."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.assurance.baseline")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    before = evidence_digest()
    rep = audit()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(rep), encoding="utf-8")
    bad = [r for r in rep["locked_references"] if r["status"] in ("MISMATCH", "MISSING")]
    changed = evidence_digest() != before and not str(a.out.resolve()).startswith(str((REPO_ROOT / "evidence").resolve()))
    for c in rep["capabilities"]:
        print(f"{c['feature']} {c['class']} tasks={c['tasks_total']} {c['task_status_counts']}")
    print(f"locked_refs_bad={len(bad)} evidence_changed={changed}")
    return 1 if bad or changed else 0


if __name__ == "__main__":
    sys.exit(main())
