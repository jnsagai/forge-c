"""CRE-T027..T029 — independent promotion gate for factory changes + reversible intervention rollback.

Gate chain (ADR-CRE-004; hard gates first, cheapest first, stop at the first hard FAIL):
  1 protected_files    git diff baseline..candidate vs policy protected globs (strict: no evidence edits at all)
  2 policy_integrity   candidate's CRE + supervisor policies judged by the RUNNER's validators (never weakened)
  3 reproducer         each cited reproducer: SYMPTOM_PRESENT on baseline, SYMPTOM_ABSENT on candidate
  4 prevention         every frozen reproducer (previously resolved failures) absent on the candidate
  5 quality_process    design check + loopback/gate/policy test subset: the baseline's tests AND the candidate's own
  6 golden_benchmark   all cases PASS on the candidate and nothing that passed on the baseline regressed
  7 holdout            same for the holdout suite
Statistics/efficiency are reported, never a vote: a fast/cheap candidate failing any hard gate is REJECTED.
Decision: REJECTED (hard FAIL) | INCONCLUSIVE (a required gate could not run) | ELIGIBLE_FOR_OFFLINE_REVIEW.
`allowed_auto_deployment` is always false: promotion to production stays with the owner's change control.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, load_yaml, sha256_bytes, state_dir, utc_now
from . import benchmark as BM
from . import events as E
from . import reproduce as RR
from .policy import CRE_CONTRACTS_DIR, Policy, issues_of
from .protect import deny, protected_changes
from .store import CREStore

EVALUATOR_ID = "cre-promotion-runner"
QUALITY_TESTS = ["tests/test_loopbacks.py", "tests/test_t009_inspection.py", "tests/test_t007_policy.py",
                 "tests/test_cre_d0_policy.py"]


def _rev(r: str, repo: Path = REPO_ROOT) -> str:
    return subprocess.run(["git", "rev-parse", f"{r}^{{commit}}"], cwd=repo, capture_output=True, text=True,
                          check=True).stdout.strip()


def tree_sha256(rev: str, repo: Path = REPO_ROOT) -> str:
    """Content identity of a revision (64-hex): SHA-256 of its full tree listing."""
    return sha256_bytes(subprocess.run(["git", "ls-tree", "-r", rev], cwd=repo, capture_output=True,
                                       check=True).stdout)


def _gate(name: str, result: str, refs: list[str], reason: str | None = None) -> dict:
    return {"name": name, "result": result, "evidence_refs": refs or [f"gate:{name}"], "reason_code": reason}


def _quality(base_wt: Path, cand_wt: Path) -> tuple[str, str | None, list[str]]:
    import os

    refs = []
    for label, tests_from in (("candidate-tests", cand_wt), ("baseline-tests", base_wt)):
        scratch = Path(tempfile.mkdtemp(prefix=f"cre-q-{label}-"))
        try:
            files = [t for t in QUALITY_TESTS if (tests_from / "factory/python" / t).is_file()]
            # the whole tests dir of that revision (tests import sibling helpers); only the gate subset is run
            shutil.copytree(tests_from / "factory/python/tests", scratch / "tests",
                            ignore=shutil.ignore_patterns("__pycache__"))
            env = RR._env(cand_wt, scratch)  # the CANDIDATE's code is under test in both runs
            env["PATH"] = os.environ.get("PATH", "")
            p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", *files],
                               cwd=scratch, env=env, capture_output=True, timeout=1800)
            refs.append(f"{label}:exit{p.returncode}:sha256:{sha256_bytes(p.stdout)[:16]}")
            if p.returncode != 0:
                tail = p.stdout.decode(errors="replace").strip().splitlines()[-1:] or [""]
                return "FAIL", f"{label.upper()}_FAILED:{tail[0][:120]}", refs
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    d = subprocess.run([sys.executable, "tests/spec/validate_design.py"], cwd=cand_wt, capture_output=True,
                       timeout=300, env=RR._env(cand_wt, Path(tempfile.gettempdir())))
    refs.append(f"design:exit{d.returncode}")
    return ("PASS", None, refs) if d.returncode == 0 else ("FAIL", "DESIGN_CHECK_FAILED", refs)


def evaluate(candidate: str, baseline: str, store: CREStore, policy: Policy, *, reproducers: list[str] | None = None,
             kind: str = "FIX", pool: RR.WorktreePool | None = None, repo: Path = REPO_ROOT,
             skip_quality: bool = False) -> dict:
    cand, base = _rev(candidate, repo), _rev(baseline, repo)
    own_pool = pool is None
    pool = pool or RR.WorktreePool(repo)
    gates: list[dict] = []
    reasons: list[str] = []
    repro_refs: list[str] = []
    stopped = False

    def stop_rest(names: list[str]) -> None:
        for n in names:
            gates.append(_gate(n, "NOT_RUN", [f"gate:{n}"], "SKIPPED_AFTER_HARD_FAIL"))

    order = ["protected_files", "policy_integrity", "reproducer", "prevention", "quality_process", "golden_benchmark",
             "holdout"]
    try:
        denied = protected_changes(base, cand, policy.get("security.protected_path_globs"), repo=repo, strict=True)
        if denied:
            gates.append(_gate("protected_files", "FAIL", [f"git-diff:{base[:12]}..{cand[:12]}"], "PROTECTED_PATH_CHANGE"))
            reasons.append(f"protected paths changed: {', '.join(denied[:5])}")
            deny(store, policy, f"candidate:{cand[:12]}", denied, "promotion-candidate")
            stop_rest(order[1:])
            stopped = True
        else:
            gates.append(_gate("protected_files", "PASS", [f"git-diff:{base[:12]}..{cand[:12]}"]))
        cand_wt = pool.get(cand)
        globs = policy.get("security.protected_path_globs")
        hardened = len(pool.harden(cand, globs)) + len(pool.harden(base, globs))  # CRE-T043, before any code runs
        reasons.append(f"sandbox: {hardened} protected paths read-only (OS) in the candidate/baseline worktrees")
        if not stopped:
            pol_issues = issues_of(load_yaml(cand_wt / "config/factory/reliability-policy.yaml"),
                                   load_yaml(cand_wt / "config/factory/supervisor-policy.yaml")) \
                if (cand_wt / "config/factory/reliability-policy.yaml").is_file() else ["RELIABILITY_POLICY_MISSING"]
            sup = load_yaml(cand_wt / "config/factory/supervisor-policy.yaml") or {}
            if sup.get("mode") != "NO_MODEL_IN_HEALTH_POLL":
                pol_issues.append("SUPERVISOR_MODE_WEAKENED")
            if pol_issues:
                gates.append(_gate("policy_integrity", "FAIL", ["policy:candidate"], pol_issues[0][:120]))
                reasons.append(f"policy integrity: {pol_issues[0][:160]}")
                stop_rest(order[2:])
                stopped = True
            else:
                gates.append(_gate("policy_integrity", "PASS", ["policy:candidate"]))
        reps, man_issues = RR.load_manifest()
        if not stopped:
            if reproducers:
                ok = True
                for rid in reproducers:
                    b = RR.run(store, policy, rid, base, "BASELINE", pool, reps)
                    c = RR.run(store, policy, rid, cand, "CANDIDATE", pool, reps)
                    good, why = RR.causal_verdict(b, c)
                    repro_refs += [f"reproducer-run:{b['run_id']}", f"reproducer-run:{c['run_id']}"]
                    ok &= good
                    if not good:
                        reasons.append(f"reproducer {rid}: {why}")
                gates.append(_gate("reproducer", "PASS" if ok else "FAIL", repro_refs, None if ok else "NOT_REPRODUCED"))
                if not ok:
                    stop_rest(order[3:])
                    stopped = True
            else:
                gates.append(_gate("reproducer", "NOT_RUN", ["gate:reproducer"],
                                   "NO_REPRODUCER_FOR_FIX" if kind == "FIX" else "NOT_APPLICABLE_FOR_CHANGE"))
        if not stopped:
            present = []
            refs = []
            for rid in sorted(reps):
                r = RR.run(store, policy, rid, cand, "PREVENTION", pool, reps)
                refs.append(f"reproducer-run:{r['run_id']}")
                if r["verdict"] != "SYMPTOM_ABSENT":
                    present.append(f"{rid}:{r['verdict']}")
            if man_issues:
                present += [f"MANIFEST:{i}" for i in man_issues]
            gates.append(_gate("prevention", "FAIL" if present else "PASS", refs, "RESOLVED_FAILURE_REAPPEARED"
                               if present else None))
            if present:
                reasons.append(f"previously resolved failures reappear: {', '.join(present)}")
                stop_rest(order[4:])
                stopped = True
        if not stopped:
            if skip_quality:
                gates.append(_gate("quality_process", "NOT_RUN", ["gate:quality"], "SKIPPED_BY_CALLER"))
            else:
                res, why, refs = _quality(pool.get(base), cand_wt)
                gates.append(_gate("quality_process", res, refs, why))
                if res == "FAIL":
                    reasons.append(f"quality/process: {why}")
                    stop_rest(order[5:])
                    stopped = True
        bench_runs = {}
        for name, kind_ in (("golden_benchmark", "golden"), ("holdout", "holdout")):
            if stopped:
                break
            b = BM.run_suite(kind_, base, pool, store, policy)
            c = BM.run_suite(kind_, cand, pool, store, policy)
            bench_runs[kind_] = (b, c)
            reg = BM.regressions(b, c)
            incomplete = [r["case_id"] for r in c["results"] if r["status"] in ("INCOMPLETE", "NOT_COMPUTABLE")]
            failing = [r["case_id"] for r in c["results"] if r["status"] in ("FAIL", "ERROR")]
            refs = [f"benchmark-run:{b.get('run_id')}", f"benchmark-run:{c.get('run_id')}"]
            if reg or failing:
                gates.append(_gate(name, "FAIL", refs, "REGRESSION" if reg else "CASE_FAILED"))
                reasons.append(f"{name}: regressions {reg} failing {failing}")
                stopped = True
                if name == "golden_benchmark":
                    stop_rest(["holdout"])
            elif incomplete:
                gates.append(_gate(name, "BLOCKED", refs, "INCOMPLETE_CASES"))
                reasons.append(f"{name}: incomplete/not computable {incomplete}")
            else:
                gates.append(_gate(name, "PASS", refs))
    finally:
        if own_pool:
            pool.close()
    hard_fail = any(g["result"] == "FAIL" for g in gates)
    required_missing = [g for g in gates if g["result"] in ("NOT_RUN", "BLOCKED")
                        and g["reason_code"] not in ("SKIPPED_AFTER_HARD_FAIL", "NOT_APPLICABLE_FOR_CHANGE")]
    decision = "REJECTED" if hard_fail else ("INCONCLUSIVE" if required_missing else "ELIGIBLE_FOR_OFFLINE_REVIEW")
    if decision == "INCONCLUSIVE":
        reasons += [f"{g['name']} not demonstrated: {g['reason_code']}" for g in required_missing]
    if "golden" in bench_runs:
        b, c = bench_runs["golden"]
        bd = sum(r.get("duration_s") or 0 for r in b["results"])
        cd = sum(r.get("duration_s") or 0 for r in c["results"])
        reasons.append(f"efficiency (informational, n=1 run each, not a gate): golden duration {bd:.1f}s -> {cd:.1f}s; "
                       "model tokens 0 -> 0")
    if decision == "ELIGIBLE_FOR_OFFLINE_REVIEW":
        reasons.append("all hard gates passed; eligible for OFFLINE review only - no automatic deployment")
    rec = {"schema_version": "1.0", "decision_id": "pd-" + sha256_bytes(f"{cand}|{base}|{utc_now()}".encode())[:20],
           "candidate_sha256": tree_sha256(cand, repo), "baseline_sha256": tree_sha256(base, repo),
           "policy_sha256": policy.sha256, "benchmark_sha256": BM.suite_sha256(*BM.SUITES.values()),
           "decision": decision, "evaluator_id": f"{EVALUATOR_ID}@{_rev('HEAD')[:12]}",
           "evaluator_kind": "INDEPENDENT_DETERMINISTIC_RUNNER", "evaluated_at": utc_now(), "hard_gates": gates,
           "reproducer_evidence_refs": repro_refs, "metrics_snapshot_ref": None, "reasons": reasons or ["no reasons"],
           "allowed_auto_deployment": False}
    errs = schema_errors(rec)
    if errs:
        raise ValueError("PROMOTION_DECISION_SCHEMA:" + "; ".join(errs[:3]))
    with store.conn() as c:
        c.execute("INSERT INTO cre_promotion_decisions VALUES (?,?,?,?,?,?)",
                  (rec["decision_id"], cand, base, decision, canonical_json(rec).decode(), rec["evaluated_at"]))
    out = state_dir() / "reliability" / "decisions"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{rec['decision_id']}.json").write_text(json.dumps({**rec, "candidate_revision": cand,
                                                                "baseline_revision": base}, indent=2, sort_keys=True))
    E.record(store, E.build("cre.promotion_evaluated", rec["decision_id"], {
        "decision": decision, "candidate": cand[:12], "baseline": base[:12],
        "gates": {g["name"]: g["result"] for g in gates}}, policy_sha256=policy.sha256,
        correlation_id=f"promotion:{cand[:12]}", evidence_refs=[f"promotion-decision:{rec['decision_id']}"]))
    return {**rec, "candidate_revision": cand, "baseline_revision": base}


def schema_errors(rec: dict) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = json.loads((CRE_CONTRACTS_DIR / "promotion-decision.schema.json").read_text())
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:160]
            for e in Draft202012Validator(schema).iter_errors(rec)]


# ---- CRE-T028: reversible operational interventions with atomic rollback -------------------------------------
def apply_reversible(store: CREStore, policy: Policy, action: str, changes: dict[str, str],
                     health_check: Callable[[Path], bool], *, infra: Path | None = None,
                     archives: Path | None = None, lessons=None, linked_lessons: list[str] | None = None,
                     stable_polls: int = 2) -> dict:
    """Pre-authorized reversible action (ACTIVE mode only) on the 002 infra runtime repo: commit, atomic CAS switch,
    health verification, CAS rollback to last-good on degradation. Released archives are hash-checked unchanged."""
    from ..repair.infra import REPAIRABLE, ensure_infra, git, validate_runtime
    from ..repair.promotion import _match, tree_hash

    if not policy.automatic_action_allowed(action):
        E.record(store, E.build("cre.policy_decision", f"{action}|refused|{utc_now()}",
                                {"decision": "REFUSED", "action": action, "mode": policy.mode},
                                policy_sha256=policy.sha256, correlation_id=f"action:{action}"))
        raise PermissionError(f"ACTION_NOT_AUTHORIZED:{action} (mode {policy.mode})")
    bad = [p for p in changes if not _match(p, REPAIRABLE)]
    if bad:
        deny(store, policy, f"action:{action}", [f"M:{p}" for p in bad], "operational-action")
        raise PermissionError(f"PATH_OUTSIDE_REVERSIBLE_SCOPE:{bad[0]}")
    infra = ensure_infra(infra)
    arch_before = tree_hash(archives) if archives else "absent"
    old = git(infra, "rev-parse", "main")
    for rel, content in changes.items():
        (infra / rel).parent.mkdir(parents=True, exist_ok=True)
        (infra / rel).write_text(content)
    git(infra, "add", "-A")
    git(infra, "commit", "-q", "-m", f"CRE reversible action {action}")
    cand = git(infra, "rev-parse", "HEAD")
    git(infra, "reset", "-q", "--hard", old)  # main stays at old until the CAS switch below
    git(infra, "update-ref", "refs/heads/main", cand, old)
    git(infra, "reset", "-q", "--hard", "main")
    healthy = not validate_runtime(infra) and all(health_check(infra) for _ in range(stable_polls))
    outcome, retracted = "APPLIED", []
    if not healthy:
        git(infra, "update-ref", "refs/heads/main", old, cand)  # atomic rollback to last-good
        git(infra, "reset", "-q", "--hard", "main")
        outcome = "ROLLED_BACK"
        for lid in linked_lessons or []:
            les = lessons.get(lid) if lessons else None
            if les and les["state"] == "VALIDATED":
                retracted.append(lessons.retract(lid, f"intervention {action} rolled back")["lesson_id"])
        with store.conn() as c:
            c.execute("INSERT INTO cre_rollbacks(subject,from_ref,to_ref,reason,retracted_lessons,at) VALUES (?,?,?,?,?,?)",
                      (f"action:{action}", cand, old, "health degraded after switch", json.dumps(retracted), utc_now()))
        E.record(store, E.build("cre.candidate_rolled_back", f"{action}|{cand}", {
            "action": action, "from": cand[:12], "to": old[:12], "retracted_lessons": retracted},
            policy_sha256=policy.sha256, correlation_id=f"action:{action}"))
    arch_after = tree_hash(archives) if archives else "absent"
    if arch_after != arch_before:
        raise RuntimeError("RELEASED_ARCHIVES_CHANGED")  # never expected; would be a security incident
    return {"outcome": outcome, "from": old, "candidate": cand, "main": git(infra, "rev-parse", "main"),
            "retracted_lessons": retracted, "archives_sha": arch_after}


def main(argv: list[str] | None = None) -> int:
    """python -m forge_factory.reliability.promotion <candidate-rev> <baseline-rev> [--kind FIX|CHANGE]
    [--reproducer RPR-xxx ...] [--repo PATH] - prints the decision; never deploys anything."""
    import argparse

    from .policy import load

    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("baseline")
    ap.add_argument("--kind", choices=["FIX", "CHANGE"], default="CHANGE")
    ap.add_argument("--reproducer", action="append", default=[])
    ap.add_argument("--repo", default=str(REPO_ROOT))
    ap.add_argument("--skip-quality", action="store_true")
    a = ap.parse_args(argv)
    d = evaluate(a.candidate, a.baseline, CREStore(), load(), reproducers=a.reproducer, kind=a.kind, repo=Path(a.repo),
                 skip_quality=a.skip_quality)
    print(f"{d['decision']} {d['decision_id']} candidate {d['candidate_revision'][:12]} baseline "
          f"{d['baseline_revision'][:12]}")
    for g in d["hard_gates"]:
        print(f"  {g['name']:17s} {g['result']:8s} {g.get('reason_code') or ''}")
    for r in d["reasons"]:
        print(f"  - {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
