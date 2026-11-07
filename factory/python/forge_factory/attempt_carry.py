"""An owner-lane retry starts from the tests of its best earlier attempt.

The files are a draft, never a verdict: every gate, test run and inspection repeats on them.
They stay uncommitted, the same state as tests the author just wrote.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .common import sha256_file, state_dir

PHASE = "SWE.6"
TESTS = "software/tests/software"
RESULTS = "evidence/tool-results.jsonl"
SCORE = re.compile(r"robot: (\d+)/(\d+) tests passed")
NAME = re.compile(r"(scn_[A-Za-z0-9_]+\.c|test_[a-z0-9_]+_requirements\.robot)\Z")
MAX_FILES = 64
MAX_FILE_BYTES = 1024 * 1024
MAX_RESULT_BYTES = 256 * 1024 * 1024


def _regular(path: Path, root: Path) -> bool:
    return (path.is_file() and path.resolve().is_relative_to(root.resolve())
            and not any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)))


def last_score(workspace: Path) -> tuple[int, int] | None:
    """The last SWE.6 robot result on record, or None. Unreadable evidence is no evidence."""
    path = workspace / RESULTS
    if not _regular(path, workspace) or path.stat().st_size > MAX_RESULT_BYTES:
        return None
    score = None
    for line in path.read_text(errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("op") != "run_robot" or row.get("phase") != PHASE:
            continue
        result = row.get("result")
        found = SCORE.search(str(result.get("summary"))) if isinstance(result, dict) else None
        if found:
            score = (int(found[1]), int(found[2]))
    return score


def _files(workspace: Path) -> list[Path] | None:
    folder = workspace / TESTS
    if folder.is_symlink() or not folder.is_dir():
        return None
    names = sorted(p for p in folder.iterdir() if NAME.fullmatch(p.name))
    if (not any(p.suffix == ".robot" for p in names) or len(names) > MAX_FILES
            or not all(_regular(p, workspace) and p.stat().st_size <= MAX_FILE_BYTES for p in names)):
        return None
    return names


def select(order: str, orders, root: Path | None = None) -> dict | None:
    """Most tests passed among earlier attempts; a later attempt wins a tie."""
    root = root or state_dir() / "workorders"
    earlier = list(orders)[:list(orders).index(order)]
    best = None
    for name in earlier:
        workspace = root / name / "workspace"
        score = last_score(workspace) if workspace.is_dir() else None
        if score and score[0] > 0 and _files(workspace) and (best is None or score[0] >= best["passed"]):
            best = {"source_work_order": name, "passed": score[0], "total": score[1], "workspace": workspace}
    return best


def install(workspace: Path, order: str, orders, root: Path | None = None) -> dict | None:
    chosen = select(order, orders, root)
    if chosen is None:
        return None
    source = chosen.pop("workspace")
    files = []
    for path in _files(source):
        target = workspace / TESTS / path.name
        if target.exists():
            raise ValueError("ATTEMPT_CARRY_TARGET_EXISTS:" + path.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        files.append({"path": f"{TESTS}/{path.name}", "sha256": sha256_file(target)})
    return {"phase": PHASE, **chosen, "files": files}


def prompt_note(manifest: dict | None, phase: str) -> list[str]:
    carried = (manifest or {}).get("attempt_carry")
    if not carried or carried.get("phase") != phase:
        return []
    return [f"{TESTS} already holds the tests of an earlier attempt, which last passed {int(carried['passed'])} of "
            f"{int(carried['total'])}. They are a draft, not a verdict. Do not rewrite them and do not search the "
            "tree: call mcp__forge_tests_mcp__run_robot first, then change only what its issues name."]
