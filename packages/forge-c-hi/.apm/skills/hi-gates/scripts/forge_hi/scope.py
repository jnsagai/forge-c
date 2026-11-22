"""Write-scope backstop (`hi scope`): the files a role changed must lie inside its write scope.

The PreToolUse guard blocks out-of-scope writes live where the harness supports hooks. This gate re-checks after the
fact, for every harness:

- snapshot mode (used by the conductor): hash every project file before the role runs, compare after it ends;
- git mode (assisted use): files changed against HEAD plus untracked files. Paths owned by the gates and the conductor
  are ignored in this mode, so commit or stash unrelated work before checking.

With neither a snapshot nor git, the gate is NOT_RUN, never PASS.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import gate_result
from .config import effective_rigor, load_project, stages
from .guard_glob import in_scope, protected
from .io import read_json, sha256_file, write_json

SKIP_DIRS = {".git"}
SKIP_PREFIXES = (".hi/runs/",)  # conductor run records (snapshots, events); roles cannot write .hi/ (guard)
TOOL_OWNED = [
    "hi/*/gates/**", "hi/*/inspection/**", "hi/trace.json", "hi/trace-matrix.md", "hi/packages/**", ".hi/**",
]


def write_scope(role: str, stage: str) -> list[str]:
    st = stages()[stage]
    if role == "author":
        return list(st["author_write_scope"])
    if role == "inspector":
        return list(st["inspector_write_scope"])
    if role == "release":
        return ["hi/packages/**"]
    if role == "intake":
        return []
    raise ValueError(f"unknown role {role}")


def snapshot(root: Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in filenames:
            full = Path(dirpath) / f
            rel = full.relative_to(root).as_posix()
            if full.is_symlink() or not full.is_file() or rel.startswith(SKIP_PREFIXES):
                continue
            out[rel] = sha256_file(full)
    return out


def diff(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))


def git_changed(root: Path) -> list[str] | None:
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if top.returncode != 0:
        return None
    res = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "-uall", "--", "."], cwd=root, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return None
    toplevel = Path(top.stdout.strip()).resolve()
    rel_root = Path(root).resolve().relative_to(toplevel)
    parts = res.stdout.split("\0")
    out, i = [], 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # the next field is the source path of the rename or copy
        p = Path(path)
        try:
            out.append(p.relative_to(rel_root).as_posix() if str(rel_root) != "." else p.as_posix())
        except ValueError:
            continue
    return sorted(set(out))


def violations(changed: list[str], scope: list[str], ignore: list[str] = ()) -> list[str]:
    return [p for p in changed if not in_scope(p, list(ignore)) and (protected(p) or not in_scope(p, scope))]


def run(
    root: Path,
    role: str,
    stage: str,
    *,
    snapshot_file: Path | None = None,
    after: dict[str, str] | None = None,
    write: bool = True,
) -> dict:
    root = Path(root)
    project = load_project(root)
    rigor = effective_rigor(project)
    common = {"profile": rigor["profile"], "integrity_level": rigor["level"], "root": root}
    scope = write_scope(role, stage)
    if snapshot_file is not None:
        before = read_json(snapshot_file)["files"]
        changed = diff(before, after if after is not None else snapshot(root))
        mode, ignore = "snapshot", []
    else:
        changed = git_changed(root)
        mode, ignore = "git", TOOL_OWNED
    if changed is None:
        doc = gate_result.result(
            "scope", [], not_run_reason="no snapshot given and the project is not a git work tree", **common)
    else:
        bad = violations(changed, scope, ignore)
        issues = [gate_result.issue("SCOPE-OUTSIDE", f"{p} changed; {role} of {stage} may write only {scope}", p)
                  for p in bad[:50]]
        if len(bad) > 50:
            issues.append(gate_result.issue("SCOPE-OUTSIDE", f"... and {len(bad) - 50} more files"))
        doc = gate_result.result("scope", issues, tool={"name": f"forge-c-hi scope ({mode})", "version": _version()},
                                 **common)
    if write:
        gate_result.write(root, stage, doc)
    return doc


def save_snapshot(root: Path, path: Path) -> Path:
    return write_json(path, {"schema": "forge-c-hi/snapshot@1", "files": snapshot(root)})


def _version() -> str:
    from . import __version__
    return __version__
