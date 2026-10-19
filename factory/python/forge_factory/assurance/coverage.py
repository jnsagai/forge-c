"""EASA-T042/T044/T045 and AT-042/AT-043/AT-045 — measured structural coverage and API execution proof.

Coverage is MEASURED with LLVM source-based coverage (clang + llvm-profdata + llvm-cov export). Statement coverage is
reported from llvm-cov LINE counts (stated as the proxy it is); branch and MC/DC come from llvm-cov's own branch and
MC/DC records (`-fcoverage-mcdc`, LLVM >= 18). Anything the toolchain cannot produce is NOT_SUPPORTED / NOT_COMPUTABLE
with no number. No universal 100% threshold is implied (EASA-FR-043; MC/DC is `+`, not `++`, for ASIL B).
API execution proof: the functions of the unit under test must have non-zero execution counts in the test run, and a
test may not define (stub) the API it claims to test (AT-042).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import contracts


def _tool(name: str) -> str | None:
    return shutil.which(name)


def measure(sources: list[Path], test: Path, includes: list[Path], *, mcdc: bool = True,
            defines: list[str] | None = None) -> dict:
    """Build `sources` + `test` with coverage instrumentation, run, export. Returns per-function counts and records."""
    clang, prof, cov = _tool("clang"), _tool("llvm-profdata"), _tool("llvm-cov")
    if not (clang and prof and cov):
        return {"status": "NOT_SUPPORTED", "reason": "clang/llvm-profdata/llvm-cov not installed", "records": []}
    code_hash = hashlib.sha256(b"".join(p.read_bytes() for p in sources)).hexdigest()
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        flags = ["-fprofile-instr-generate", "-fcoverage-mapping"] + (["-fcoverage-mcdc"] if mcdc else [])
        inc = sum((["-I", str(i)] for i in includes), [])
        b = subprocess.run([clang, "-std=c99", "-O0", *flags, *(defines or []), *inc, *map(str, sources), str(test),
                            "-o", str(t / "ut")], capture_output=True, text=True)
        if b.returncode:
            if mcdc and "mcdc" in b.stderr.lower():
                return measure(sources, test, includes, mcdc=False, defines=defines) | {"mcdc_build_error": b.stderr[-200:]}
            return {"status": "BUILD_FAILED", "reason": b.stderr[-300:], "records": []}
        r = subprocess.run([str(t / "ut")], capture_output=True, text=True, timeout=120,
                           env={"LLVM_PROFILE_FILE": str(t / "ut.profraw")})
        subprocess.run([prof, "merge", "-sparse", str(t / "ut.profraw"), "-o", str(t / "ut.profdata")], check=True,
                       capture_output=True)
        ex = subprocess.run([cov, "export", str(t / "ut"), f"-instr-profile={t / 'ut.profdata'}", *map(str, sources)],
                            capture_output=True, text=True, check=True)
        ver = subprocess.run([cov, "--version"], capture_output=True, text=True).stdout
    data = json.loads(ex.stdout)["data"][0]
    tot = data["totals"]
    funcs = {f["name"]: f["count"] for f in data.get("functions", [])}
    run_ref = "sha256:" + hashlib.sha256(r.stdout.encode()).hexdigest()
    tool = "llvm-cov " + (re.search(r"version\s+([\d.]+)", ver).group(1) if re.search(r"version\s+([\d.]+)", ver) else "?")

    def rec(kind: str, key: str, measured: bool, note: str) -> dict:
        d = tot.get(key) or {}
        ok = measured and d.get("count") is not None
        return {"code_hash": code_hash, "kind": kind, "measured": ok, "covered": d.get("covered") if ok else None,
                "total": d.get("count") if ok else None, "scope": note, "test_run_refs": [run_ref] if ok else [],
                "uncovered_rationale_refs": [], "tool_id": tool,
                "status": "MEASURED" if ok else ("NOT_SUPPORTED" if kind == "MCDC" else "NOT_COMPUTABLE")}
    mcdc_ok = mcdc and "mcdc" in tot and (tot["mcdc"].get("count") or 0) >= 0 and "mcdc" in json.dumps(data)[:10**7]
    records = [rec("STATEMENT", "lines", True, "driver sources; llvm-cov line coverage used as statement proxy"),
               rec("BRANCH", "branches", True, "driver sources; llvm-cov branch records"),
               rec("MCDC", "mcdc", bool(mcdc_ok), "driver sources; llvm-cov MC/DC (selected, risk-based; '+' for ASIL B)")]
    for x in records:
        x["schema_issues"] = contracts.errors("coverage-evidence", {k: v for k, v in x.items() if k != "schema_issues"})
    return {"status": "MEASURED", "records": records, "function_counts": funcs, "test_exit": r.returncode,
            "test_output_sha256": run_ref}


def api_execution(function_counts: dict[str, int], unit_functions: list[str], test_text: str) -> list[str]:
    """AT-042: unit functions must execute in the test run; a test defining the API itself only tests a stub."""
    f = []
    for fn in unit_functions:
        if re.search(rf"^[\w\s\*]*\b{re.escape(fn)}\s*\([^;{{)]*\)\s*\{{", test_text, re.M):
            f.append(f"STUB_SHADOWS_API:{fn}")
        elif not function_counts.get(fn):
            f.append(f"API_NOT_EXECUTED:{fn}")
    return f


def missing_branch_evidence(records: list[dict]) -> list[str]:
    """AT-043: statement coverage alone is not branch evidence; never synthesize a branch number."""
    kinds = {r["kind"]: r for r in records}
    out = []
    if "BRANCH" not in kinds or kinds["BRANCH"]["status"] != "MEASURED":
        out.append("BRANCH_EVIDENCE_MISSING")
        if "BRANCH" in kinds and kinds["BRANCH"].get("covered") is not None:
            out.append("FABRICATED_BRANCH_NUMBER")
    return out
