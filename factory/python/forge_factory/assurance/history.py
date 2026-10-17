"""EASA-T061 — Features 001-005 preserved: every protected-path change on this branch since the Feature 005 base must
come from an owner-decision commit, a CRE oracle commit (frozen reproducers / decisions) or be a pure ADDITION of a new
evidence record. Editing or deleting existing evidence, or changing a protected policy in an ordinary commit, is a
violation. The git history decides, not a claim."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..common import REPO_ROOT
from ..reliability.protect import _match
from .protect import globs

ALLOWED_SUBJECTS = ("Owner decision", "CRE oracle:")


def _git(*a: str, repo: Path = REPO_ROOT) -> str:
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True).stdout


def check(base: str, head: str = "HEAD", repo: Path = REPO_ROOT) -> dict:
    g = globs(repo)
    rows, violations = [], []
    for sha in _git("rev-list", "--reverse", f"{base}..{head}", repo=repo).split():
        subject = _git("log", "-1", "--format=%s", sha, repo=repo).strip()
        body = _git("log", "-1", "--format=%B", sha, repo=repo)
        human = "Co-Authored-By: Claude" not in body  # owner-authored commit (not produced by the coding agent)
        for line in _git("diff-tree", "--no-commit-id", "--name-status", "--no-renames", "-r", sha, repo=repo).splitlines():
            status, path = line.split("\t", 1)
            if not _match(path, g):
                continue
            if human:
                kind = "OWNER_AUTHORED"
            elif subject.startswith(ALLOWED_SUBJECTS):
                kind = "OWNER_DECISION_OR_ORACLE_COMMIT"
            elif path.startswith("evidence/") and (status == "A" or (status == "M" and path.endswith("/latest.json"))):
                kind = "EVIDENCE_ADDITION"
            else:
                kind = "VIOLATION"
                violations.append(f"{sha[:8]}:{status}:{path}")
            rows.append({"commit": sha[:12], "subject": subject[:80], "status": status, "path": path, "kind": kind})
    return {"base": base, "head": _git("rev-parse", head, repo=repo).strip()[:12], "protected_changes": rows,
            "violations": violations, "status": "PASS" if not violations else "FAIL"}
