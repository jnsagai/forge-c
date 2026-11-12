"""An owner-lane retry starts from the best test run of its earlier attempts.

Every robot run records its exact test files by SHA-256 (evidence/test-integrity.jsonl) and keeps
their bytes in .forge-run/test-snapshots. The retry restores the files of the run that passed most,
verified byte for byte, so a later edit that broke the build cannot hide an earlier good state.
The files are a draft, never a verdict: every gate, test run and inspection repeats on them.
They stay uncommitted, the same state as tests the author just wrote.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from .common import sha256_file, state_dir

PHASE = "SWE.6"
TESTS = "software/tests/software"
RESULTS = "evidence/tool-results.jsonl"
INTEGRITY = "evidence/test-integrity.jsonl"
SNAPSHOTS = ".forge-run/test-snapshots"
SCORE = re.compile(r"robot: (\d+)/(\d+) tests passed; (\d+)/\d+ requirements verified")
NAME = re.compile(r"(scn_[A-Za-z0-9_]+\.c|test_[a-z0-9_]+_requirements\.robot)\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILES = 64
MAX_FILE_BYTES = 1024 * 1024
MAX_LOG_BYTES = 256 * 1024 * 1024
MAX_SKEW_SECONDS = 5.0


def _regular(path: Path, root: Path) -> bool:
    return (path.is_file() and path.resolve().is_relative_to(root.resolve())
            and not any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)))


def _rows(workspace: Path, rel: str, op: str) -> list[dict]:
    path = workspace / rel
    if not _regular(path, workspace) or path.stat().st_size > MAX_LOG_BYTES:
        return []
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("op") == op and row.get("phase") == PHASE:
            rows.append(row)
    return rows


def _time(value) -> float | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def runs(workspace: Path) -> list[dict]:
    """Every robot run whose result and exact files are both on record, oldest first."""
    results = _rows(workspace, RESULTS, "run_robot")
    integrity = _rows(workspace, INTEGRITY, "run_robot")
    if len(results) != len(integrity):
        return []  # the two logs no longer line up: no run can be attributed to its files
    out = []
    for index, (result, record) in enumerate(zip(results, integrity)):
        found = SCORE.search(str((result.get("result") or {}).get("summary")))
        at, recorded = _time(result.get("ts_utc")), _time(record.get("ts_utc"))
        files = record.get("files")
        if (not found or at is None or recorded is None or abs(at - recorded) > MAX_SKEW_SECONDS
                or not isinstance(files, dict)):
            continue
        tests = {p: s for p, s in files.items() if isinstance(p, str) and p.startswith(TESTS + "/")}
        if (not tests or len(tests) > MAX_FILES
                or not all(p.count("/") == TESTS.count("/") + 1 and NAME.fullmatch(p.rsplit("/", 1)[1])
                           and isinstance(s, str) and SHA.fullmatch(s) for p, s in tests.items())
                or not any(p.endswith(".robot") for p in tests)):
            continue
        out.append({"index": index, "passed": int(found[1]), "total": int(found[2]), "verified": int(found[3]),
                    "at": result["ts_utc"], "files": tests})
    return out


def _snapshot(workspace: Path, sha: str) -> bytes | None:
    path = workspace / SNAPSHOTS / sha
    if not _regular(path, workspace) or path.stat().st_size > MAX_FILE_BYTES:
        return None
    data = path.read_bytes()
    return data if hashlib.sha256(data).hexdigest() == sha else None


def select(order: str, orders, root: Path | None = None) -> dict | None:
    """Most tests passed, then most requirements verified, among earlier attempts; later wins a tie."""
    root = root or state_dir() / "workorders"
    earlier = list(orders)[:list(orders).index(order)]
    best = None
    for name in earlier:
        workspace = root / name / "workspace"
        if not workspace.is_dir():
            continue
        for run in runs(workspace):
            if run["passed"] < 1 or not all(_snapshot(workspace, s) is not None for s in run["files"].values()):
                continue
            if best is None or (run["passed"], run["verified"]) >= (best["passed"], best["verified"]):
                best = {"source_work_order": name, "source_run_at": run["at"], "passed": run["passed"],
                        "verified": run["verified"], "total": run["total"], "workspace": workspace,
                        "snapshot": run["files"]}
    return best


def install(workspace: Path, order: str, orders, root: Path | None = None) -> dict | None:
    chosen = select(order, orders, root)
    if chosen is None:
        return None
    source, snapshot = chosen.pop("workspace"), chosen.pop("snapshot")
    for rel in snapshot:
        if (workspace / rel).exists():
            raise ValueError("ATTEMPT_CARRY_TARGET_EXISTS:" + rel)
    files = []
    for rel, sha in sorted(snapshot.items()):
        data = _snapshot(source, sha)
        if data is None:
            raise ValueError("ATTEMPT_CARRY_SNAPSHOT_CHANGED:" + rel)
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({"path": rel, "sha256": sha256_file(target)})
    return {"phase": PHASE, **chosen, "files": files}


def prompt_note(manifest: dict | None, phase: str) -> list[str]:
    carried = (manifest or {}).get("attempt_carry")
    if not carried or carried.get("phase") != phase:
        return []
    total = int(carried["total"])
    return [f"{TESTS} already holds the best tests of an earlier attempt: {int(carried['passed'])} of {total} tests "
            f"passed and {int(carried.get('verified', 0))} of {total} requirements were verified. They are a draft, "
            "not a verdict. Do not rewrite them and do not search the tree: call mcp__forge_tests_mcp__run_robot "
            "first, then change only what its issues name. Use only register and macro names that already appear "
            "in these scenarios or in the driver headers; after each edit run run_robot again, and undo an edit "
            "that breaks the build."]
