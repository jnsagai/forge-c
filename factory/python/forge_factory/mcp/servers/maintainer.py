"""AFO-T045/T046 (AFO-FR-007/016/049/050; AT-043/045/046) - forge-maintainer-mcp: the afo-factory-maintainer's ONLY
tools. Distinct from the infra fabric-repair role (forge-repo-mcp, runtime/** and services/**): this server reaches one
candidate worktree prepared by the Conductor for one verified FACTORY_CODE_DEFECT.

Scope: `FORGE_AFO_MAINT_CASE` = <state>/afo/maintainer/<proposal_id>/case.json. Reads are bounded and never reach
protected paths (holdouts, reproducer oracles, evidence, policies); writes are canonical, allowlisted, symlink-free and
refused where the OS made the file read-only; tests run as the sandbox UID `maintainer`. `submit_candidate` hands the
patch to the deterministic broker (commit, git-diff veto, sealed reproducer) - it evaluates and publishes nothing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import Field

from ...common import state_dir
from ..sdk import Operation, ToolContext, ToolDenied, ToolInput, build_server, result
from .afo_payload import payload

MAX_BYTES = 2048


def _case() -> dict:
    p = Path(os.environ.get("FORGE_AFO_MAINT_CASE", ""))
    root = (state_dir() / "afo/maintainer").resolve()
    if not p.is_file() or root not in p.resolve().parents:
        raise ToolDenied("AFO_CASE_OUT_OF_SCOPE", str(p)[:100])
    case = json.loads(p.read_text())
    if (p.parent / "submission.json").exists():
        raise ToolDenied("CASE_ALREADY_SUBMITTED", case["proposal_id"])
    return case


def _call(fn, *a):
    from ...afo.maintainer import MaintainerDenied

    try:
        return fn(*a)
    except MaintainerDenied as e:
        raise ToolDenied(e.code, e.detail[:120]) from e


class NoIn(ToolInput):
    offset: int = Field(default=0, ge=0, le=1000000, description="Page offset; continue at metrics.next_offset if present.")


class PathIn(NoIn):
    path: str = Field(min_length=3, max_length=200)


class WriteIn(ToolInput):
    path: str = Field(min_length=3, max_length=200)
    content: str = Field(max_length=65536)


class TestsIn(ToolInput):
    tests: list[str] = Field(min_length=1, max_length=5)


class SubmitIn(ToolInput):
    summary: str = Field(min_length=10, max_length=300)
    reproducer: str = Field(min_length=10, max_length=200)
    symptom_signature: str = Field(min_length=8, max_length=160)


def read_case(ctx: ToolContext, a: NoIn) -> dict:
    from ...afo.maintainer import ALLOW, CANDIDATE_TESTS, DENY

    c = _case()
    body = {"proposal_id": c["proposal_id"], "base": c["base"], "incident": c["incident"],
            "allow": ALLOW, "deny": DENY, "candidate_tests": CANDIDATE_TESTS}
    return payload(ctx, body, a.offset, refs=[f"afo-maint:{c['proposal_id']}"], summary="Maintainer case; untrusted data")


def read_source(ctx: ToolContext, a: PathIn) -> dict:
    from ...afo import maintainer as M

    text = _call(M.read_source, _case(), a.path, M.MAX_FILE_BYTES + 1)
    if len(text) > M.MAX_FILE_BYTES:
        raise ToolDenied("SOURCE_TOO_LARGE", "split the candidate; source was not silently truncated")
    return payload(ctx, text, a.offset, refs=[f"src:{a.path}"], summary=a.path)


def write_source(ctx: ToolContext, a: WriteIn) -> dict:
    from ...afo import maintainer as M

    sha = _call(M.write_source, _case(), a.path, a.content)
    return result(ctx, "PASS", f"wrote {a.path}", [f"src:{a.path}@{sha[:16]}"], [], {}, "forge-afo",
                  input_obj={"path": a.path, "sha256": sha})


def run_candidate_tests(ctx: ToolContext, a: TestsIn) -> dict:
    from ...afo import maintainer as M

    r = _call(M.run_tests, _case(), a.tests)
    return payload(ctx, r["excerpt"], status="PASS" if r["passed"] else "FAIL",
                   refs=[f"maint-tests:{r['output_sha256'][:16]}"], summary=f"exit {r['exit_code']} ({r['isolation']})")


def submit_candidate(ctx: ToolContext, a: SubmitIn) -> dict:
    from ...afo import maintainer as M

    s = _call(M.submit, _case(), a.summary, a.reproducer, a.symptom_signature)
    return result(ctx, "BLOCKED" if s["veto"] else "PASS",
                  "candidate vetoed (quarantine)" if s["veto"] else "candidate submitted for independent evaluation",
                  [f"afo-candidate:{s['candidate'][:12]}"], s["veto"][:5], {}, "forge-afo",
                  input_obj={"candidate": s["candidate"]})


OPERATIONS = [
    Operation("read_case", NoIn, read_case, "The frozen maintainer case: incident, baseline, allowlist."),
    Operation("read_source", PathIn, read_source, "Bounded read of a non-protected file of the candidate worktree."),
    Operation("write_source", WriteIn, write_source, "Write one allowlisted file of the candidate worktree."),
    Operation("run_candidate_tests", TestsIn, run_candidate_tests, "Run candidate-owned tests in the sandbox UID."),
    Operation("submit_candidate", SubmitIn, submit_candidate, "Hand the patch to the broker (commit, veto, seal)."),
]

if __name__ == "__main__":
    build_server("forge-maintainer-mcp", OPERATIONS).run("stdio")
