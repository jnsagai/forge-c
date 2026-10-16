"""CRE-T020 — protected-path enforcement at the runner boundary (before and after any candidate code runs).

* before: `harden_worktree` removes write permission (OS level) from every protected file/dir in a candidate
  worktree, so a candidate's build/test step cannot alter policies, oracles or evidence while it runs;
* after: `protected_changes` inspects the candidate commit range with git (not agent claims): any change to a
  protected path is a denial. Exception (documented): new files under evidence/** (append-only records) and the
  mutable `latest.json` pointers of evidence runs; modifying or deleting an existing evidence record is denied.
Every denial is a durable `cre.security_denial` event with the path, never file contents.
"""
from __future__ import annotations

import fnmatch
import os
import stat
import subprocess
from pathlib import Path

from ..common import REPO_ROOT
from . import events as E
from .policy import Policy
from .store import CREStore


def _match(rel: str, globs: list[str]) -> bool:
    for g in globs:
        if fnmatch.fnmatch(rel, g) or (g.endswith("/**") and (rel == g[:-3] or rel.startswith(g[:-2]))):
            return True
    return False


def protected_changes(base: str, candidate: str, globs: list[str], repo: Path = REPO_ROOT,
                      strict: bool = False) -> list[str]:
    """strict (promotion candidates): no evidence change at all - evidence is produced by runs, never by patches."""
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", base, candidate], cwd=repo,
                         capture_output=True, text=True, check=True, timeout=120).stdout
    denied = []
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        if not _match(path, globs):
            continue
        if not strict and path.startswith("evidence/") and (status == "A" or (status == "M" and path.endswith("/latest.json"))):
            continue  # append-only evidence records and run pointers are not edits of frozen evidence
        denied.append(f"{status}:{path}")
    return denied


def harden_worktree(wt: Path, globs: list[str]) -> list[str]:
    hardened = []
    for root, dirs, files in os.walk(wt):
        if ".git" in Path(root).parts:
            continue
        for name in files + dirs:
            p = Path(root) / name
            rel = p.relative_to(wt).as_posix()
            if _match(rel, globs):
                mode = p.stat().st_mode
                p.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
                hardened.append(rel)
    return sorted(hardened)


def deny(store: CREStore, policy: Policy, subject: str, paths: list[str], actor: str) -> dict:
    ev = E.build("cre.security_denial", f"{subject}|{actor}|{'|'.join(sorted(paths))}",
                 {"subject": subject[:120], "actor": actor[:80], "paths": sorted(paths)[:30],
                  "reason": "PROTECTED_PATH_CHANGE"}, policy_sha256=policy.sha256, correlation_id=subject[:120])
    E.record(store, ev)
    return ev
