"""T016 — forge-repo-mcp: tightly scoped Git operations. No push, fetch, remote, reset or config ops exist.

* diff_scoped: bounded diff summary; full patch by artifact ref.
* create_worktree: only `repair/<name>` branches under `<workspace>/../repair-worktrees/` (repair roles).
* commit_candidate: commits in a repair worktree only; refuses protected-path changes (deterministic).
* get_commit: HEAD SHA + clean flag (release provenance).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field

from ...policy.authz import ALWAYS_PROTECTED, _match, _protected_from_supervisor_policy
from ..sdk import Operation, ToolContext, ToolDenied, ToolInput, build_server, result, run_argv, tool_version

ALLOW = {"git"}
GIT_ENV = {"GIT_AUTHOR_NAME": "forge-repair", "GIT_AUTHOR_EMAIL": "repair@forge-c.local",
           "GIT_COMMITTER_NAME": "forge-repair", "GIT_COMMITTER_EMAIL": "repair@forge-c.local",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}


class DiffIn(ToolInput):
    path: str = Field(default=".", max_length=200)


class WorktreeIn(ToolInput):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,40}$")


class CommitIn(ToolInput):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,40}$")
    message: str = Field(min_length=5, max_length=200)


class EmptyIn(ToolInput):
    pass


def git(ctx: ToolContext, cwd: Path, *args: str, timeout: int = 60):
    return run_argv(["git", "-c", "core.hooksPath=/dev/null", *args], cwd, timeout, ALLOW, env_extra=GIT_ENV)


def diff_scoped(ctx: ToolContext, a: DiffIn) -> dict:
    target = ctx.path(a.path, must_exist=True)
    rel = ctx.rel(target) if target != ctx.workspace else "."
    stat = git(ctx, ctx.workspace, "diff", "--stat", "HEAD", "--", rel)
    patch = git(ctx, ctx.workspace, "diff", "HEAD", "--", rel)
    lines = stat.stdout.decode(errors="replace").strip().splitlines()
    return result(ctx, "PASS" if stat.exit_code == 0 else "FAIL", lines[-1][:160] if lines else "no changes",
                  [ctx.store(patch.stdout, "patch")], [], {"files_changed": max(0, len(lines) - 1)}, "git",
                  tool_version("git"), stat.exit_code, stat.duration_ms, a.model_dump(), patch.stdout)


def _wt_root(ctx: ToolContext) -> Path:
    return ctx.workspace.parent / "repair-worktrees"


def create_worktree(ctx: ToolContext, a: WorktreeIn) -> dict:
    root = _wt_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    wt = root / a.name
    if wt.exists():
        raise ToolDenied("WORKTREE_EXISTS", a.name)
    r = git(ctx, ctx.workspace, "worktree", "add", "-b", f"repair/{a.name}", str(wt), "HEAD")
    return result(ctx, "PASS" if r.exit_code == 0 else "FAIL", f"worktree repair/{a.name}",
                  [f"worktree:{a.name}"], [] if r.exit_code == 0 else ["WORKTREE_FAILED"], {}, "git",
                  tool_version("git"), r.exit_code, r.duration_ms, a.model_dump())


def commit_candidate(ctx: ToolContext, a: CommitIn) -> dict:
    wt = _wt_root(ctx) / a.name
    if not (wt / ".git").exists():
        raise ToolDenied("NOT_A_REPAIR_WORKTREE", a.name)
    br = git(ctx, wt, "rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip()
    if br != f"repair/{a.name}":
        raise ToolDenied("NOT_A_REPAIR_BRANCH", br[:60])
    git(ctx, wt, "add", "-A")
    names = git(ctx, wt, "diff", "--cached", "--name-only").stdout.decode().split()
    protected = ALWAYS_PROTECTED + _protected_from_supervisor_policy()
    bad = [n for n in names if _match(n, protected)]
    if bad:
        git(ctx, wt, "reset", "-q")
        return result(ctx, "BLOCKED", "protected paths changed; commit refused",
                      issues=[f"PROTECTED_PATH:{b}"[:120] for b in bad], tool="git")
    if not names:
        return result(ctx, "BLOCKED", "nothing to commit", issues=["EMPTY_PATCH"], tool="git")
    r = git(ctx, wt, "commit", "-q", "-m", a.message)
    patch = git(ctx, wt, "show", "--format=", "HEAD")
    sha = git(ctx, wt, "rev-parse", "HEAD").stdout.decode().strip()
    return result(ctx, "PASS" if r.exit_code == 0 else "FAIL", f"candidate {sha[:12]} ({len(names)} files)",
                  [ctx.store(patch.stdout, "patch"), f"commit:{sha}"], [], {"files": len(names)}, "git",
                  tool_version("git"), r.exit_code, r.duration_ms, a.model_dump(), patch.stdout)


def get_commit(ctx: ToolContext, a: EmptyIn) -> dict:
    sha = git(ctx, ctx.workspace, "rev-parse", "HEAD")
    st = git(ctx, ctx.workspace, "status", "--porcelain")
    dirty = bool(st.stdout.strip())
    return result(ctx, "PASS" if sha.exit_code == 0 else "FAIL", f"HEAD {sha.stdout.decode().strip()[:12]}"
                  + (" (dirty)" if dirty else ""), [f"commit:{sha.stdout.decode().strip()}"], [],
                  {"dirty": dirty}, "git", tool_version("git"), sha.exit_code, sha.duration_ms, a.model_dump())


OPERATIONS = [
    Operation("diff_scoped", DiffIn, diff_scoped, "Diff of a workspace path vs HEAD (bounded; patch by ref)."),
    Operation("create_worktree", WorktreeIn, create_worktree, "Create isolated repair/<name> worktree."),
    Operation("commit_candidate", CommitIn, commit_candidate, "Commit repair candidate; protected paths refused."),
    Operation("get_commit", EmptyIn, get_commit, "HEAD commit SHA and clean state."),
]

if __name__ == "__main__":
    build_server("forge-repo-mcp", OPERATIONS).run("stdio")
