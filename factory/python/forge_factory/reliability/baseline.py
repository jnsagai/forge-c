"""CRE-T002 — reproducible baseline run of the inherited test suites (v0.5 handoff smoke commands + factory pytest).

Records, per command: argv, exit code, duration, stdout/stderr SHA-256 (logs stored next to the record), and the
host's tool versions and git head. A command's failure is DATA, classified against KNOWN_CONSTRAINTS (documented,
pre-existing, not caused by CRE); an unexplained failure makes the baseline FAIL.

"Do not alter preexisting evidence": several suites regenerate tracked evidence (status reports, KPI pilot snapshot,
OSS demo logs). Tracked files under evidence/ and docs/ that were clean before the run and modified after it are
listed in the record and restored to HEAD; untracked new files from the run are removed only under build dirs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, sha256_bytes, utc_now

PY = sys.executable
SUITES: list[dict] = [
    {"id": "design", "argv": [PY, "tests/spec/validate_design.py"]},
    {"id": "unittest-tests", "argv": [PY, "-m", "unittest", "discover", "-s", "tests", "-v"]},
    {"id": "unittest-release-manager", "argv": [PY, "-m", "unittest", "discover", "-s", "factory/release-manager/tests",
                                                "-p", "test_*.py", "-v"]},
    {"id": "verify-bundle", "argv": [PY, "scripts/verify_bundle.py"]},
    {"id": "oss-demo", "argv": ["bash", "scripts/run_oss_demo.sh"]},
    {"id": "factory-pytest", "argv": [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "factory/python/tests",
                                      "--ignore=factory/python/tests/test_cre_d0_baseline.py"]},
]
# Pre-existing, documented constraints (not caused by CRE): a failure of these is recorded, not hidden.
KNOWN_CONSTRAINTS = {
    "verify-bundle": "SHA256SUMS.txt is the frozen v0.5 handoff inventory (184 files, 2026-10-14) and the tree has "
                     "evolved since; the script also walks .git. See CRE-T001 C19 / source-inventory.json.",
}
TOOLS = {"python": [PY, "--version"], "clang": ["clang", "--version"], "gcc": ["gcc", "--version"],
         "arm-none-eabi-gcc": ["arm-none-eabi-gcc", "--version"], "cppcheck": ["cppcheck", "--version"],
         "cmake": ["cmake", "--version"], "ninja": ["ninja", "--version"], "git": ["git", "--version"]}
WATCHED = ("evidence", "docs")


def tool_versions() -> dict:
    out = {}
    for k, argv in TOOLS.items():
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=20)
            out[k] = (r.stdout or r.stderr).strip().splitlines()[0][:120] if r.returncode == 0 else "UNAVAILABLE"
        except (OSError, subprocess.SubprocessError, IndexError):
            out[k] = "MISSING"
    for k, env in (("fabro", "FORGE_FABRO_BIN"), ("renode", None)):
        exe = os.environ.get(env) if env else shutil.which(k)
        try:
            r = subprocess.run([exe or k, "--version"], capture_output=True, text=True, timeout=20)
            out[k] = (r.stdout or r.stderr).strip().splitlines()[0][:120] if r.returncode == 0 else "UNAVAILABLE"
        except (OSError, subprocess.SubprocessError, IndexError, TypeError):
            out[k] = "MISSING"
    return out


def _tail(out: bytes) -> str:
    lines = out.decode(errors="replace").strip().splitlines()
    return lines[-1][:200] if lines else ""


def _dirty(root: Path) -> set[str]:
    r = subprocess.run(["git", "status", "--porcelain", "--", *WATCHED], cwd=root, capture_output=True, text=True)
    return {line[3:] for line in r.stdout.splitlines() if line[:2].strip() == "M"}


def run(root: Path | None = None, suites: list[dict] | None = None, out_dir: Path | None = None,
        timeout: int = 3600) -> dict:
    root = root or REPO_ROOT
    out_dir = out_dir or root / "evidence/cre/baseline"
    stamp = utc_now().replace(":", "").replace("-", "").replace(".", "")[:15]
    logs = out_dir / f"baseline-{stamp}"
    logs.mkdir(parents=True, exist_ok=True)
    before = _dirty(root)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    results = []
    for s in suites or SUITES:
        t0, started = time.monotonic(), utc_now()
        try:
            p = subprocess.run(s["argv"], cwd=root, capture_output=True, timeout=timeout,
                               env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            code, so, se = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as exc:
            code, so, se = 124, exc.stdout or b"", (exc.stderr or b"") + b"\nTIMEOUT\n"
        except OSError as exc:
            code, so, se = 127, b"", str(exc).encode()
        (logs / f"{s['id']}.stdout").write_bytes(so)
        (logs / f"{s['id']}.stderr").write_bytes(se)
        cls = "PASS" if code == 0 else ("KNOWN_CONSTRAINT" if s["id"] in KNOWN_CONSTRAINTS else "FAIL")
        results.append({"id": s["id"], "argv": [a if a != PY else "python" for a in s["argv"]], "exit_code": code,
                        "result": cls, "start_utc": started, "end_utc": utc_now(),
                        "duration_s": round(time.monotonic() - t0, 2),
                        "stdout_sha256": sha256_bytes(so), "stderr_sha256": sha256_bytes(se),
                        "tail": _tail(so + se),
                        "constraint": KNOWN_CONSTRAINTS.get(s["id"]) if cls == "KNOWN_CONSTRAINT" else None})
    modified = sorted(_dirty(root) - before)
    if modified:  # restore tracked evidence the suites regenerated (preexisting evidence is not altered)
        subprocess.run(["git", "checkout", "--", *modified], cwd=root, check=True)
    rec = {"schema": "forge-c/cre-baseline/1.0", "task": "CRE-T002", "git_head": head, "recorded_at": utc_now(),
           "tool_versions": tool_versions(), "results": results,
           "restored_regenerated_evidence": modified,
           "status": "PASS" if all(r["result"] != "FAIL" for r in results) else "FAIL",
           "logs_dir": str(logs.relative_to(root)) if logs.is_relative_to(root) else str(logs)}
    (out_dir / "baseline-latest.json").write_text(pretty_json(rec))
    (logs / "record.json").write_text(pretty_json(rec))
    return rec


def main(argv: list[str] | None = None) -> int:
    rec = run()
    for r in rec["results"]:
        print(f"  {r['id']:26s} {r['result']:16s} exit={r['exit_code']} {r['duration_s']}s  {r['tail'][:90]}")
    print(f"CRE-T002 baseline {rec['status']} @ {rec['git_head'][:12]}; restored regenerated evidence: "
          f"{len(rec['restored_regenerated_evidence'])} files")
    return 0 if rec["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
