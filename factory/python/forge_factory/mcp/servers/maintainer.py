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

from pydantic import Field, field_validator

from ...common import state_dir
from ..sdk import Operation, ToolContext, ToolDenied, ToolInput, build_server, result
from .afo_payload import payload


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
    offset: int = Field(default=0, ge=0, le=4 * 1024 * 1024,
                        description="Page offset; continue at metrics.next_offset if present.")


class PathIn(NoIn):
    path: str = Field(min_length=3, max_length=200)


class InventoryIn(NoIn):
    prefix: str = Field(default="factory/python/forge_factory", min_length=1, max_length=200,
                        description="Exact source prefix, or . for declared roots. Discover paths before reading files.")


class WriteIn(ToolInput):
    path: str = Field(min_length=3, max_length=200)
    content: str = Field(max_length=65536)


class TestsIn(ToolInput):
    tests: list[str] = Field(min_length=1, max_length=5)


class EditIn(ToolInput):
    path: str = Field(min_length=3, max_length=200)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="SHA256 of the exact current file bytes.")
    old_text: str = Field(min_length=1, max_length=8192, description="Exact UTF8 text occurring once; at most 8192 bytes.")
    new_text: str = Field(max_length=8192, description="Replacement UTF8 text, at most 8192 bytes; empty deletes.")


class SubmitIn(ToolInput):
    summary: str = Field(min_length=10, max_length=300, description="Compact repair summary, at most 300 characters.")
    reproducer: str = Field(min_length=10, max_length=200,
                            description="Plain candidate-owned relative .py path only; no prose or annotations.")
    symptom_signature: str = Field(min_length=8, max_length=160,
                                   description="Exact entire line suffix after SYMPTOM_PRESENT: on baseline; "
                                               "no extra diagnostic text on that line.")


    @field_validator("symptom_signature")
    @classmethod
    def bare_signature(cls, value: str) -> str:
        if value.startswith("SYMPTOM_PRESENT:"):
            raise ValueError("Use the bare signature suffix, without SYMPTOM_PRESENT: prefix")
        return value


def list_sources(ctx: ToolContext, a: InventoryIn) -> dict:
    from ...afo import maintainer as M

    c = _case()
    inventory = _call(M.source_inventory, c, a.prefix)
    return payload(ctx, inventory, a.offset, refs=[f"afo-maint:{c['proposal_id']}"], summary="Source paths and current hashes")


def read_case(ctx: ToolContext, a: NoIn) -> dict:
    from ...afo.maintainer import ALLOW, CANDIDATE_TESTS, DENY, SOURCE_ROOTS

    c = _case()
    body = {"proposal_id": c["proposal_id"], "base": c["base"], "incident": c["incident"],
            "allow": ALLOW, "deny": DENY, "candidate_tests": CANDIDATE_TESTS, "source_inventory_roots": list(SOURCE_ROOTS)}
    if c.get("retained_rework"):
        from ...afo.durable import digest

        rework = c["retained_rework"]
        if digest(rework["feedback"]) != rework["feedback_sha256"]:
            raise ToolDenied("REWORK_FEEDBACK_CHANGED", "frozen independent feedback hash mismatch")
        body["retained_rework"] = rework
    body["reproducer_protocol"] = {
        "registered_signature": "BARE_SUFFIX_WITHOUT_SYMPTOM_PRESENT_PREFIX",
        "baseline_exit_code": 1, "baseline_last_nonempty_stdout_line": "SYMPTOM_PRESENT:<registered_signature>",
        "candidate_exit_code": 0, "candidate_last_nonempty_stdout_line": "SYMPTOM_ABSENT",
        "diagnostics": "BEFORE_FINAL_CONTRACT_LINE; never append to marker",
        "legacy_validation": "UNCHANGED",
    }
    selected = os.environ.get("FORGE_LRTX_PROFILE")
    if selected:
        from ...common import REPO_ROOT
        from ...lrtx.profile import load

        p = load(selected)
        body["runtime_profile"] = {"id": p["id"], "path": str(Path(p["_path"]).relative_to(REPO_ROOT)
                                                       if Path(p["_path"]).is_absolute() else p["_path"]),
                                   "sha256": p["_sha256"], "source": "CONTROLLER_BOUND_ENVIRONMENT"}
    return payload(ctx, body, a.offset, refs=[f"afo-maint:{c['proposal_id']}"], summary="Maintainer case; untrusted data")


def read_source(ctx: ToolContext, a: PathIn) -> dict:
    from ...afo import maintainer as M

    text = _call(M.read_source, _case(), a.path, M.MAX_SOURCE_READ_BYTES + 1)
    if len(text.encode()) > M.MAX_SOURCE_READ_BYTES:
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


def edit_source(ctx: ToolContext, a: EditIn) -> dict:
    from ...afo import maintainer as M

    sha = _call(M.edit_source, _case(), a.path, a.expected_sha256, a.old_text, a.new_text)
    return result(ctx, "PASS", f"edited {a.path}", [f"src:{a.path}@{sha[:16]}"], [],
                  {"sha256": sha}, "forge-afo", input_obj={"path": a.path, "sha256": sha})


def submit_candidate(ctx: ToolContext, a: SubmitIn) -> dict:
    from ...afo import maintainer as M

    s = _call(M.submit, _case(), a.summary, a.reproducer, a.symptom_signature)
    return result(ctx, "BLOCKED" if s["veto"] else "PASS",
                  "candidate vetoed (quarantine)" if s["veto"] else "candidate submitted for independent evaluation",
                  [f"afo-candidate:{s['candidate'][:12]}"], s["veto"][:5], {}, "forge-afo",
                  input_obj={"candidate": s["candidate"]})


OPERATIONS = [
    Operation("read_case", NoIn, read_case, "The frozen maintainer case: incident, baseline, allowlist."),
    Operation("list_sources", InventoryIn, list_sources,
              "Discover exact source/profile paths and hashes in a bounded paginated inventory."),
    Operation("read_source", PathIn, read_source, "Bounded read of a non-protected file of the candidate worktree."),
    Operation("write_source", WriteIn, write_source, "Write one allowlisted file of the candidate worktree."),
    Operation("edit_source", EditIn, edit_source,
              "Replace one exact unique UTF8 fragment in a hash-bound allowlisted file; preserve all other bytes."),
    Operation("run_candidate_tests", TestsIn, run_candidate_tests, "Run candidate-owned tests in the sandbox UID."),
    Operation("submit_candidate", SubmitIn, submit_candidate, "Hand the patch to the broker (commit, veto, seal)."),
]

if __name__ == "__main__":
    build_server("forge-maintainer-mcp", OPERATIONS).run("stdio")
