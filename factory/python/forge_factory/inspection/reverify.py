"""Gate-side defect verification with the cited tests restored from the tool snapshots (ADR-0008, r75).

A FIXED defect is verified by the detecting phase with the SAME tests that failed. r75: the SWE.4 author added new
unit tests (UT-059..) to the cited test_rcc.c before its first post-fix run, so no run ever used the cited version
and DEFECT_TEST_CHANGED rejected the phase although the fix was right. The gate now runs the cited version itself:
a scratch copy of the workspace with the cited files restored byte-identical from `.forge-run/test-snapshots`, the
fixed product code, and the test tool of each cited file. PASS = VERIFIED; FAIL = the fix does not make the cited
test pass, whatever the author did to its copy afterwards.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ..common import sha256_file

# cited test location -> (server module, operation)
TOOLS = (("software/tests/unit/", "tests", "run_unit"), ("software/tests/integration/", "tests", "run_integration"),
         ("software/tests/target/", "sim", "run_renode"), ("software/tests/software/", "tests", "run_robot"))
SKIP = (".git", "evidence", ".forge-run")  # no integrity history or defect register in the scratch copy


def _tools_for(files: list[str]) -> list[tuple[str, str]]:
    out = []
    for f in files:
        t = next(((m, op) for prefix, m, op in TOOLS if f.startswith(prefix)), None)
        if t is None:
            return []  # a cited file no test tool runs: cannot re-verify deterministically
        if t not in out:
            out.append(t)
    return out


def reverify(ws: Path, defect: dict, snapshots: Path) -> tuple[str, list[str]]:
    """('PASS' | 'FAIL' | 'UNAVAILABLE', issues) of the cited tests, restored, against the current product code."""
    from ..mcp import sdk
    from ..mcp.servers import sim, tests

    cited = defect["test_files"]
    tools = _tools_for(sorted(cited))
    if not tools or not all((snapshots / h).is_file() for h in cited.values()):
        return "UNAVAILABLE", ["REVERIFY_UNAVAILABLE:cited test snapshot or test tool missing"]
    mods = {"tests": tests, "sim": sim}
    with tempfile.TemporaryDirectory(prefix="forge-reverify-") as tmp:
        copy = Path(tmp) / "ws"
        shutil.copytree(ws, copy, ignore=lambda d, names: [n for n in names if Path(d) == ws and n in SKIP],
                        symlinks=True)
        for f, h in cited.items():
            (copy / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snapshots / h, copy / f)
            assert sha256_file(copy / f) == h
        issues: list[str] = []
        status = "PASS"
        for mod, op in tools:
            o = next(x for x in mods[mod].OPERATIONS if x.name == op)
            ctx = sdk.ToolContext(f"forge-{mod}-mcp", op, "route-gate", defect["detected_phase"], copy,
                                  "reverify")
            res = o.handler(ctx, o.model())
            if res["status"] != "PASS":
                status = "FAIL"
                issues += [f"{op}:{i}" for i in res.get("issues", [])[:6]]
        return status, issues
