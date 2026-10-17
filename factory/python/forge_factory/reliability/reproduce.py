"""CRE-T018/T019 — independent reproducer runner (ADR-CRE-004). Deterministic, model-free.

* Reproducers are frozen black-box programs in tests/reliability/reproducers, listed with their SHA-256 in
  manifest.yaml; a script whose hash differs from the manifest is never run (tamper => INCOMPLETE).
* A revision is evaluated in a detached `git worktree` (isolated tree) with PYTHONPATH pointing at that worktree and
  scratch state/event dirs; an import preflight proves the revision under test is what runs.
* Verdict from the contract line + exit code: SYMPTOM_PRESENT (1) / SYMPTOM_ABSENT (0) / ERROR (2, API drift,
  mismatched exit code or unexpected signature). Runs are append-only records with the log hash.
* Causal verification = baseline SYMPTOM_PRESENT with the expected signature AND candidate SYMPTOM_ABSENT, both by
  this runner. Agent text is never an input.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..common import REPO_ROOT, load_yaml, sha256_bytes, sha256_file, state_dir, utc_now
from . import events as E
from . import isolation
from .policy import Policy
from .store import CREStore

REPRO_DIR = REPO_ROOT / "tests" / "reliability" / "reproducers"
MANIFEST = REPRO_DIR / "manifest.yaml"
RUNNER_ID = "cre-reproducer-runner"


def load_manifest(path: Path | None = None) -> tuple[dict[str, dict], list[str]]:
    p = path or MANIFEST
    data = load_yaml(p) or {}
    out, issues = {}, []
    for r in data.get("reproducers") or []:
        script = p.parent / r["script"]
        if not script.is_file():
            issues.append(f"{r['id']}:SCRIPT_MISSING")
            continue
        if sha256_file(script) != r["sha256"]:
            issues.append(f"{r['id']}:SCRIPT_HASH_MISMATCH")  # tampered or unfrozen: never run
            continue
        out[r["id"]] = {**r, "path": str(script)}
    return out, issues


def _git(*args: str, cwd: Path = REPO_ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=120).stdout.strip()


class WorktreePool:
    """Detached worktrees per revision, removed on exit (the main checkout is never touched)."""

    def __init__(self, repo: Path = REPO_ROOT):
        self.repo, self.root, self.trees = repo, isolation.new_dir("cre-wt"), {}

    def get(self, revision: str) -> Path:
        full = _git("rev-parse", f"{revision}^{{commit}}", cwd=self.repo)
        if full not in self.trees:
            wt = self.root / full[:12]
            _git("worktree", "add", "--detach", "--force", str(wt), full, cwd=self.repo)
            self.trees[full] = wt
        return self.trees[full]

    def harden(self, revision: str, globs: list[str]) -> list[str]:
        """CRE-T043: protected paths of this worktree become read-only (OS) before candidate code runs in it."""
        from .protect import harden_worktree

        return harden_worktree(self.get(revision), globs)

    def close(self) -> None:
        for wt in self.trees.values():
            for root, dirs, files in os.walk(wt):  # undo hardening so the worktree can be removed
                for n in dirs + files:
                    p = Path(root) / n
                    if not p.is_symlink():
                        p.chmod(p.stat().st_mode | 0o200)
            subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=self.repo, capture_output=True)
        isolation.discard(self.root)

    def __enter__(self) -> WorktreePool:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _env(wt: Path, scratch: Path) -> dict:
    from ..common import data_root

    env = {k: v for k, v in os.environ.items() if not k.startswith("FORGE_") or k in ("FORGE_FABRO_BIN",)}
    # writes are isolated (state, events in scratch); the data root stays real for read-only pinned toolchains
    env.update({"PYTHONPATH": str(wt / "factory" / "python"), "FORGE_REPO_ROOT": str(wt),
                "FORGE_STATE_DIR": str(scratch / "state"), "FORGE_EVENTS_DIR": str(scratch / "events"),
                "FORGE_DATA_ROOT": str(data_root()), "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def run(store: CREStore, policy: Policy, rid: str, revision: str, role: str, pool: WorktreePool,
        manifest: dict[str, dict] | None = None, timeout: int = 600) -> dict:
    reps = manifest if manifest is not None else load_manifest()[0]
    rep = reps.get(rid)
    if rep is None:
        raise KeyError(f"REPRODUCER_NOT_IN_FROZEN_MANIFEST:{rid}")
    wt = pool.get(revision)
    rev = _git("rev-parse", "HEAD", cwd=wt)
    scratch = isolation.new_dir("cre-repro")
    isolation.hand_over("verifier", scratch)  # CRE-T049: the reproducer runs as the verifier OS identity
    try:
        env = _env(wt, scratch)
        pre = isolation.execute("verifier", [sys.executable, "-c", "import forge_factory; print(forge_factory.__file__)"],
                                cwd=scratch, env=env, writable=[scratch], readable=[Path(rep["path"]).parent],
                                timeout=120)
        imported = pre.stdout.decode(errors="replace").strip()
        if not imported.startswith(str(wt)):
            verdict, code, out = "ERROR", 2, f"IMPORT_PREFLIGHT_FAILED:{imported or pre.stderr[-200:]}".encode()
        else:
            p = isolation.execute("verifier", [sys.executable, rep["path"]], cwd=scratch, env=env,
                                  writable=[scratch], readable=[Path(rep["path"]).parent], timeout=timeout)
            code, out = p.returncode, p.stdout + b"\n--- stderr ---\n" + p.stderr
            lines = [x for x in p.stdout.decode(errors="replace").splitlines() if x.strip()]
            last = lines[-1] if lines else ""
            if last.startswith("SYMPTOM_PRESENT:") and code == 1:
                verdict = "SYMPTOM_PRESENT" if last.split(":", 1)[1] == rep["symptom_signature"] else "ERROR"
            elif last == "SYMPTOM_ABSENT" and code == 0:
                verdict = "SYMPTOM_ABSENT"
            else:
                verdict = "ERROR"
    finally:
        isolation.discard(scratch)
    lines = out.decode(errors="replace").strip().splitlines()
    signature = lines[0][:200] if verdict != "SYMPTOM_ABSENT" and lines else None
    if verdict == "SYMPTOM_PRESENT":
        signature = rep["symptom_signature"]
    at = utc_now()
    run_id = "rr-" + sha256_bytes(f"{rid}|{rev}|{role}|{at}".encode())[:20]
    logs = state_dir() / "reliability" / "reproducers"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / f"{run_id}.log").write_bytes(out)
    rec = {"run_id": run_id, "reproducer_id": rid, "revision": rev, "role": role, "exit_code": code,
           "verdict": verdict, "signature": signature, "log_sha256": sha256_bytes(out), "at": at}
    with store.conn() as c:
        c.execute("INSERT INTO cre_reproducer_runs VALUES (?,?,?,?,?,?,?,?,?)", tuple(rec.values()))
    E.record(store, E.build("cre.reproducer_run", run_id, {"reproducer_id": rid, "revision": rev[:12], "role": role,
                                                           "verdict": verdict, "exit_code": code,
                                                           "runner": RUNNER_ID},
                            policy_sha256=policy.sha256, correlation_id=rid, evidence_sha256=rec["log_sha256"],
                            evidence_refs=[f"reproducer-log:{run_id}"]))
    return rec


def reproducer_runs(store: CREStore, rid: str | None = None) -> list[dict]:
    q, a = "SELECT * FROM cre_reproducer_runs", ()
    if rid:
        q, a = q + " WHERE reproducer_id=?", (rid,)
    with store.conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY at", a)]


def causal_verdict(baseline: dict, candidate: dict) -> tuple[bool, str]:
    """CRE-T019: VERIFIED only when the same frozen reproducer shows the symptom on the baseline revision and not
    on the candidate revision, both executed by the runner."""
    if baseline["reproducer_id"] != candidate["reproducer_id"]:
        return False, "DIFFERENT_REPRODUCERS"
    if baseline["revision"] == candidate["revision"]:
        return False, "SAME_REVISION"
    if baseline["verdict"] != "SYMPTOM_PRESENT":
        return False, f"BASELINE_NOT_REPRODUCED:{baseline['verdict']}"
    if candidate["verdict"] != "SYMPTOM_ABSENT":
        return False, f"CANDIDATE_NOT_FIXED:{candidate['verdict']}"
    return True, "CAUSE_VERIFIED_BY_CONTRAST"
