"""T026/T027/T028/T029 — isolated repair worktree, deterministic promotion controller, ledger updates.

Promotion rule (no agent self-approval):
  1. candidate commit exists on repair/<attempt> in an isolated worktree of the infra repo;
  2. protected-path diff is EMPTY and every changed path is in the repairable allowlist;
  3. deterministic regression checks pass (runtime contract validation + caller-supplied checks);
  4. atomic switch: `git update-ref refs/heads/main <candidate> <expected-old>` (compare-and-swap);
  5. health verified for N consecutive probes; otherwise rollback (CAS back to old SHA).
Product workspaces and released evidence are never inside this repo, and their hashes are checked
unchanged around every repair (T029).
"""
from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
import stat
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..common import sha256_bytes, sha256_file, state_dir, utc_now
from ..events.emit import emit
from ..supervisor.store import IncidentStore
from .infra import PROTECTED, REPAIRABLE, ensure_infra, git, validate_runtime


def _match(rel: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel, g) for g in globs)


def tree_hash(root: Path, exclude: tuple[str, ...] = (".git",)) -> str:
    h = hashlib.sha256()
    if not root.exists():
        return "absent"
    for f in sorted(p for p in root.rglob("*") if p.is_file() and not any(x in p.parts for x in exclude)):
        h.update(f.relative_to(root).as_posix().encode() + b"\0" + sha256_file(f).encode())
    return h.hexdigest()


def create_repair_worktree(attempt_id: str, infra: Path | None = None) -> Path:
    """T026: isolated worktree; protected paths made read-only at the OS level before any agent runs."""
    infra = ensure_infra(infra)
    wt = state_dir() / "repair" / "worktrees" / attempt_id
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
        git(infra, "worktree", "prune")
    wt.parent.mkdir(parents=True, exist_ok=True)
    git(infra, "worktree", "add", "-q", "-b", f"repair/{attempt_id}", str(wt), "main")
    for f in wt.rglob("*"):
        rel = f.relative_to(wt).as_posix()
        if ".git" in f.parts:
            continue
        if _match(rel, PROTECTED) or not (_match(rel, REPAIRABLE) or f.is_dir()):
            mode = f.stat().st_mode
            f.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    for d in sorted({p.parent for p in wt.rglob("*") if _match(p.relative_to(wt).as_posix(), PROTECTED)}, reverse=True):
        if d != wt:
            d.chmod(d.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    return wt


def commit_worktree(wt: Path, message: str) -> str | None:
    git(wt, "add", "-A")
    if not git(wt, "diff", "--cached", "--name-only"):
        return None
    git(wt, "commit", "-q", "-m", message)
    return git(wt, "rev-parse", "HEAD")


def promote(attempt_id: str, incident_id: str, store: IncidentStore, health_check: Callable[[Path], bool],
            extra_checks: list[tuple[str, Callable[[Path], bool]]] | None = None, infra: Path | None = None,
            stable_polls: int = 3, poll_interval_s: float = 0.2, protected_roots: list[Path] | None = None,
            token_usage: dict | None = None) -> dict:
    infra = ensure_infra(infra)
    wt = state_dir() / "repair" / "worktrees" / attempt_id
    branch = f"repair/{attempt_id}"
    old = git(infra, "rev-parse", "main")
    cand = git(infra, "rev-parse", branch, check=False)
    roots_before = {str(r): tree_hash(r) for r in (protected_roots or [])}
    rec: dict[str, Any] = {"attempt_id": attempt_id, "incident_id": incident_id, "agent_role": "fabric-repair",
                           "status": "TESTING",
           "worktree_ref": f"worktree:{attempt_id}", "tests": [], "protected_path_changes": [],
           "token_usage": token_usage or {"total": None, "basis": "unknown"},
           "started_at": next((a["started_at"] for a in store.attempts(incident_id) if a["attempt_id"] == attempt_id),
                              utc_now())}

    def finish(status: str, incident_state: str, reason: str, **extra) -> dict:
        rec.update({"status": status, "finished_at": utc_now(), **extra})
        store.record_attempt(rec)
        inc = store.must(incident_id)
        if inc["state"] == "REPAIRING":
            store.transition(incident_id, "VERIFYING", "promotion controller")
        if incident_state == "ROLLED_BACK":
            store.transition(incident_id, "ROLLED_BACK", reason)
            budget = int(os.environ.get("FORGE_MAX_ATTEMPTS", "2"))
            if store.must(incident_id)["attempts"] >= budget:
                store.transition(incident_id, "REQUIRES_OFFLINE_ATTENTION", "attempt budget exhausted after rollback")
            else:
                store.transition(incident_id, "TRIAGED", "eligible for another bounded attempt")
        else:
            store.transition(incident_id, incident_state, reason,
                             **({"patch_hash": rec["patch_sha256"]} if rec.get("patch_sha256") else {}))
        emit("repair", "INFO" if status == "PROMOTED" else "WARN", f"repair {attempt_id} {status}: {reason}"[:160],
             incident_id=incident_id, correlation_id=incident_id)
        return rec

    if not cand or cand == old:
        return finish("FAILED", "ROLLED_BACK", "no candidate commit")
    changed = git(infra, "diff", "--name-only", old, cand).splitlines()
    patch = git(infra, "diff", old, cand)
    rec["patch_sha256"] = sha256_bytes(patch.encode())
    bad = [c for c in changed if _match(c, PROTECTED)]
    outside = [c for c in changed if not _match(c, REPAIRABLE)]
    if bad:
        rec["protected_path_changes"] = []  # schema forbids non-empty; record in tests evidence instead
        rec["tests"].append({"name": "protected-path-diff-empty", "status": "FAIL", "evidence_ref": f"commit:{cand}"})
        return finish("ROLLED_BACK", "REQUIRES_OFFLINE_ATTENTION", f"protected paths changed: {','.join(bad)[:80]}")
    rec["tests"].append({"name": "protected-path-diff-empty", "status": "PASS", "evidence_ref": f"commit:{cand}"})
    if outside:
        rec["tests"].append({"name": "repairable-allowlist", "status": "FAIL", "evidence_ref": f"commit:{cand}"})
        return finish("ROLLED_BACK", "ROLLED_BACK", f"paths outside repair allowlist: {','.join(outside)[:80]}")
    rec["tests"].append({"name": "repairable-allowlist", "status": "PASS", "evidence_ref": f"commit:{cand}"})
    issues = validate_runtime(wt)
    rec["tests"].append({"name": "runtime-config-contract", "status": "PASS" if not issues else "FAIL",
                         "evidence_ref": f"sha256:{sha256_bytes(';'.join(issues).encode())}"})
    for name, fn in extra_checks or []:
        ok = bool(fn(wt))
        rec["tests"].append({"name": name, "status": "PASS" if ok else "FAIL", "evidence_ref": f"commit:{cand}"})
    if any(t["status"] != "PASS" for t in rec["tests"]):
        return finish("ROLLED_BACK", "ROLLED_BACK", "regression checks failed")
    # atomic compare-and-swap switch of main (CRE-T045: journaled COMPENSATABLE; the reverse CAS compensates)
    from ..reliability.production import guarded

    def switch(_key: str) -> dict:
        git(infra, "update-ref", "refs/heads/main", cand, old)
        git(infra, "reset", "-q", "--hard", "main")
        return {"from": old, "to": cand}

    def rollback() -> None:
        def undo(_key: str) -> dict:
            git(infra, "update-ref", "refs/heads/main", old, cand)
            git(infra, "reset", "-q", "--hard", "main")
            return {"from": cand, "to": old}
        guarded("infra_cas_rollback", f"infra_cas_rollback:{attempt_id}", undo)

    sw = guarded("infra_cas_switch", f"infra_cas_switch:{attempt_id}", switch)
    if not sw["executed"] and sw["status"] != "ALREADY_DONE":  # enforcing: a previous switch has an unknown outcome
        return finish("ROLLED_BACK", "REQUIRES_OFFLINE_ATTENTION", f"infra switch journal: {sw['status']}")
    stable = 0
    for _ in range(stable_polls * 3):
        stable = stable + 1 if health_check(infra) else 0
        if stable >= stable_polls:
            break
        time.sleep(poll_interval_s)
    after = {str(r): tree_hash(r) for r in (protected_roots or [])}
    if after != roots_before:
        rollback()
        return finish("ROLLED_BACK", "REQUIRES_OFFLINE_ATTENTION", "product/evidence hash changed during repair")
    if stable < stable_polls:
        rollback()
        rec["tests"].append({"name": f"health-stable-{stable_polls}-polls", "status": "FAIL", "evidence_ref": f"commit:{old}"})
        return finish("ROLLED_BACK", "ROLLED_BACK", "health not restored; rolled back")
    rec["tests"].append({"name": f"health-stable-{stable_polls}-polls", "status": "PASS", "evidence_ref": f"commit:{cand}"})
    rec["promotion_evidence_ref"] = f"commit:{cand}"
    return finish("PROMOTED", "RESOLVED", f"promoted {cand[:12]} after {stable_polls} stable polls")
