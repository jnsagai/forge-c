"""EASA-T004 — run the existing regression/design checks and record tool, version, exit code and hashes, together
with NEGATIVE CONTROLS: the same checkers on deliberately invalid input must fail. A checker that passes invalid
input makes the whole record FAIL (a check that cannot fail is not evidence)."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

from ..common import REPO_ROOT, canonical_json, pretty_json, sha256_bytes, sha256_file, utc_now

SPEC = REPO_ROOT / "specs/006-enhanced-ai-software-assurance"


def _version(argv0: str) -> str:
    try:
        r = subprocess.run([argv0, "--version"], capture_output=True, text=True, timeout=30)
        return ((r.stdout or r.stderr).strip().splitlines() or ["UNKNOWN"])[0][:100]
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def run_check(cid: str, argv: list[str], expect: str, inputs: list[Path], cwd: Path = REPO_ROOT,
              timeout: int = 3600) -> dict:
    t0 = time.monotonic()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout)
        out, code = p.stdout + b"\n--- stderr ---\n" + p.stderr, p.returncode
    except subprocess.TimeoutExpired as exc:
        out, code = (exc.stdout or b"") + b"\nTIMEOUT", 124
    ok = (code == 0) if expect == "pass" else (code != 0)
    return {"case_id": cid, "tool_id": Path(argv[0]).name, "tool_version": _version(argv[0]),
            "command_digest": sha256_bytes(canonical_json(argv)), "argv": argv,
            "input_sha256": sha256_bytes(canonical_json({str(p): sha256_file(p) for p in inputs if p.is_file()})),
            "expected_observation": f"exit {'0' if expect == 'pass' else '!=0'}", "exit_code": code,
            "actual_observation": f"exit {code}", "output_sha256": sha256_bytes(out),
            "output_tail": out.decode(errors="replace")[-400:], "status": "PASS" if ok else "FAIL",
            "duration_ms": int((time.monotonic() - t0) * 1000), "started_at_utc": utc_now()}


def negative_spec_copy(tmp: Path, mutate: str) -> Path:
    d = tmp / f"spec-{mutate}"
    shutil.copytree(SPEC, d)
    cat = d / "contracts/iso26262-6-2018-methods.working.yaml"
    doc = yaml.safe_load(cat.read_text())
    if mutate == "46-methods":
        doc["methods"].pop()
    elif mutate == "checked-entry":
        doc["methods"][0]["normative_checked"] = True
    cat.write_text(yaml.safe_dump(doc, sort_keys=False))
    return d


def run(full: bool) -> dict:
    py = sys.executable
    cases = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cases.append(run_check("design-006", [py, str(SPEC / "validate_spec.py")], "pass", list(SPEC.rglob("*.*"))))
        for m in ("46-methods", "checked-entry"):
            d = negative_spec_copy(tmp, m)
            cases.append(run_check(f"design-006-negative-{m}", [py, str(d / "validate_spec.py")], "fail",
                                   [d / "contracts/iso26262-6-2018-methods.working.yaml"]))
        cases.append(run_check("design-check-002", [py, "tests/spec/validate_design.py"], "pass",
                               [REPO_ROOT / "tests/spec/validate_design.py"]))
        cases.append(run_check("legacy-v0.1", [py, "-m", "unittest", "discover", "-s", "tests"], "pass",
                               sorted((REPO_ROOT / "tests").glob("test_*.py"))))
        if full:
            cases.append(run_check("factory-test", [py, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                                    "factory/python/tests"], "pass",
                                   sorted((REPO_ROOT / "factory/python/tests").glob("test_*.py"))))
    neg_bad = [c["case_id"] for c in cases if "negative" in c["case_id"] and c["status"] != "PASS"]
    return {"schema": "forge-c/easa-regression/0.1", "generated_at": utc_now(), "cases": cases,
            "negative_controls_effective": not neg_bad, "status": "PASS" if all(c["status"] == "PASS" for c in cases)
            else "FAIL"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.assurance.regress")
    ap.add_argument("--full", action="store_true", help="also run the full factory pytest suite")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rep = run(a.full)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(rep), encoding="utf-8")
    for c in rep["cases"]:
        print(f"{c['case_id']}: {c['status']} exit={c['exit_code']} out={c['output_sha256'][:12]}")
    return 0 if rep["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
