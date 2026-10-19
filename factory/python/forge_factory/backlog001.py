"""SPEC-001 backlog evidence: checks a sealed review package (read-only; the archive hash is compared before and
after) against the acceptance of the SPEC-001 engineering tasks. Owner/human tasks (T-001, T-002, T-009 approval,
T-010 signed review, T-016 tool confidence, T-018 sign-off) are never decided here.

  python -m forge_factory.backlog001 <review.zip> --task T-011    exit 0 = acceptance met by the package
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from .common import sha256_file

E = "evidence/"


def _json(z: zipfile.ZipFile, name: str) -> dict:
    try:
        return json.loads(z.read(name))
    except (KeyError, ValueError):
        return {}


def _tool_pass(z: zipfile.ZipFile, op: str) -> bool:
    try:
        rows = [json.loads(x) for x in z.read(E + "verification/tool-results.jsonl").decode().splitlines() if x.strip()]
    except KeyError:
        return False
    last = [r for r in rows if r.get("op") == op]
    return bool(last) and (last[-1].get("result") or {}).get("status") == "PASS"


def _inspected(z: zipfile.ZipFile, phase: str) -> bool:
    for n in z.namelist():
        if n.startswith(f"{E}inspection/{phase}/INS-") and n.endswith(".json") and _json(z, n).get("verdict") == "PASS":
            return True
    return False


def checks(z: zipfile.ZipFile) -> dict[str, list[tuple[str, bool]]]:
    names = set(z.namelist())

    def has(prefix: str, suffix: str = "") -> bool:
        return any(n.startswith(E + prefix) and n.endswith(suffix) and z.getinfo(n).file_size > 0 for n in names)

    reg = _json(z, E + "verification/static/register_map_conformance.json")
    matrices = [n for n in names if n.startswith(E + "traceability/matrices/") and n.endswith(".csv")]
    man = _json(z, "manifest.json")
    return {
        "T-003": [("register map conformance against the RM index PASS",
                   reg.get("verdict") == "PASS" and not reg.get("major_findings")),
                  ("SWE.2 register table (architecture) present", has("workproducts/SWE.2/software_architecture.md")),
                  ("RM-cited requirements baseline present", has("workproducts/SWE.1/software_requirements.md")),
                  ("toolchain/target baseline recorded", has("configuration/target_baseline.json"))],
        "T-011": [("HAL source and header", has("software/hal/", ".c") and has("software/hal/", ".h")),
                  ("LL header", has("software/ll/", ".h")),
                  ("ELF and map file", has("software/build/", ".elf") and has("software/build/", ".map")),
                  ("detailed design", has("workproducts/SWE.3/detailed_design")),
                  ("SWE.3 inspection PASS", _inspected(z, "SWE.3"))],
        "T-012": [("unit tests run PASS (raw tool result)", _tool_pass(z, "run_unit")),
                  ("unit test sources", has("software/tests/unit/", ".c")),
                  ("static analysis summary", has("verification/static/analysis_summary.json")),
                  ("MISRA coverage matrix (subset, no compliance claim)", has("verification/static/misra_coverage_matrix.md")),
                  ("raw tool logs", has("evidence-raw/", ".log")),
                  ("SWE.4 inspection PASS", _inspected(z, "SWE.4"))],
        "T-017": [("six traceability matrices", len(matrices) >= 6),
                  ("work products SWE.1-SWE.6", all(has(f"workproducts/SWE.{i}/") for i in range(1, 7))),
                  ("raw evidence", has("evidence-raw/")),
                  ("gaps reported in the package manifest", "gaps" in man and "gap_count" in man),
                  ("hash list", "SHA256SUMS.txt" in names)],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.backlog001")
    ap.add_argument("zip", type=Path)
    ap.add_argument("--task", required=True, choices=["T-003", "T-011", "T-012", "T-017"])
    a = ap.parse_args(argv)
    before = sha256_file(a.zip)
    with zipfile.ZipFile(a.zip) as z:
        res = checks(z)[a.task]
    unchanged = sha256_file(a.zip) == before
    ok = all(v for _, v in res) and unchanged
    print(json.dumps({"task": a.task, "package": a.zip.name, "archive_sha256": before, "archive_unchanged": unchanged,
                      "checks": [{"check": k, "pass": v} for k, v in res], "status": "PASS" if ok else "FAIL"}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
