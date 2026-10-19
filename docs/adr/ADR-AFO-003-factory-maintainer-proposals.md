# ADR-AFO-003: Factory Maintainer proposals: isolation, veto, independent evaluation, broker

- Status: accepted for implementation (Feature 005, M5: AFO-T045..T053)
- Date: 2026-10-19

## Context

- A run can fail on a factory-source defect (FACTORY_CODE_DEFECT); the order then waits for an external change
  (M4).
- Infra `fabric-repair` may only touch `runtime/**` and `services/**`, and the CRE never auto-promotes code
  (ADR-006).
- The spec asks for:
  - a separate maintainer role that can propose a narrow source patch;
  - a reproducer that fails on the baseline;
  - the existing independent 004 promotion runner;
  - a broker-made branch/PR only.

## Decision

1. **Role and tools.**
   - `afo-factory-maintainer` (overlay role, its own SKILL, locked in `skills.afo.lock.json`) reaches only
     `forge-maintainer-mcp`: `read_case`, `read_source`, `write_source`, `run_candidate_tests` and `submit_candidate`.
   - It has no `forge-repo-mcp`, no git or GitHub operation, and no shell.
   - Disabled by policy (`maintenance.enable_factory_maintainer: false`).
2. **Path rules** (`afo/maintainer.py`). Writes are allowed only under:
   - `factory/python/forge_factory/**`;
   - the candidate-owned test namespace `factory/python/tests/afo_candidate/**`.

   Never writable:
   - every CRE protected glob;
   - the deciders and grants: `afo/`, `reliability/`, `registry/`, `mcp/sdk.py`, the maintainer server, `repair/`,
     `supervisor/`, `release/` and `policy/`.

   Reads exclude protected paths (holdouts, reproducer oracles, evidence, policies).
3. **Isolation.**
   - The candidate is a detached `git worktree` of the baseline, on the sandbox data volume.
   - Every non-writable file is made read-only by the OS.
   - Writes are canonical: no traversal, no symlink component, size-capped.
   - Candidate tests run as a new sandbox identity `maintainer` (container UID 2003, distinct from verifier 2001 and
     repair 2002), with:
     - the source mounted read-only;
     - network off;
     - HOME and state in a private scratch directory;
     - every credential-like variable removed.
   - Verified by a real rootless-Podman test: no read of owner 0600 files or the Codex profile, no token variable,
     no network, no write to the source.
4. **The veto judges the git diff, never the agent's claim.** Each of these quarantines the candidate:
   - a path outside the allowlist;
   - a protected path;
   - a symlink, submodule or new executable file;
   - more than 12 paths or more than 600 added lines;
   - credential access (`auth.json`, `.ssh/`, token variables, `codex-home`) or self-merge/deploy text in added lines;
   - a candidate that is not a descendant of the baseline.
5. **Reproducer.**
   - The maintainer writes it in the candidate namespace.
   - At submit, the broker seals the committed content outside the repo (`<state>/afo/maintainer/<id>/reproducer/`,
     sha256 manifest, id `AFO-<id>`).
   - Triage runs it on the unchanged baseline under the CRE verifier identity. A reproducer without
     SYMPTOM_PRESENT is an unsupported claim: the candidate is REJECTED and never evaluated.
   - The 004 CAPA is linked or opened; its cause stays a HYPOTHESIS, because only the CRE frozen-manifest process
     verifies a cause.
6. **Independent evaluation.**
   - `reliability.promotion.evaluate(..., staged_manifest=...)` is the one CRE change in M5.
   - Staged `AFO-*` reproducers serve the reproducer gate only.
   - Prevention, quality, golden and holdout gates keep the frozen suites, which no candidate can modify.
   - The best possible outcome is ELIGIBLE_FOR_OFFLINE_REVIEW; `allowed_auto_deployment` must be false, otherwise
     the candidate is quarantined.
7. **Records are append-only.**
   - Table `afo_maintainer_proposals`: SQLite triggers abort UPDATE and DELETE.
   - Each record validates against `maintenance-proposal.schema.json`.
   - REJECTED and QUARANTINED candidates lose their worktree and get no branch. They create no lesson.
8. **Broker.**
   - It is deterministic, runs as the operator account, and has its own credentials.
   - `publish` re-runs the veto and creates the local branch `afo/proposal/<id>`.
   - Only with `maintenance.allow_proposal_pr: true` does it push that branch and open a **draft** PR.
   - An argv guard refuses:
     - `gh pr merge` and `gh pr ready`;
     - `git merge`, `git rebase` and `git reset`;
     - force, admin or auto flags;
     - any push to `main` or `master`;
     - a non-draft PR.
   - Nothing changes the revision production runs use.
9. **Waiting for the change is bounded.**
   - WAITING_EXTERNAL_CHANGE records `waiting_since_epoch`.
   - The scheduler finalizes the order BLOCKED (`WAITING_EXTERNAL_CHANGE_TTL`) after
     `budgets.max_order_wall_seconds`, the existing policy key (24 h). No new key is added to the authored policy
     schema.
   - The wait holds no capacity, so unrelated orders keep being admitted.
   - `cli external-change <order> --revision <sha> --approval-ref <ref>` (operator) re-queues the order after an
     externally approved and deployed change. Admission then creates a new attempt.
10. **Process boundaries.**
    - The Conductor only prepares cases (cheap, PILOT/ACTIVE, when enabled).
    - Evaluation (up to about 1 h) and publishing are separate operator/broker commands (`cli maintainer-process`
      and `cli maintainer-publish`), never inside the watchdog-supervised cycle.

## Consequences

- No new trusted path to `main` exists. A human still reviews and merges outside AFO.
- The file-write layer runs as the owner account and is guarded by MCP checks plus OS read-only bits. Code
  execution (the riskier part) runs as the sandbox UID. Moving the MCP writer itself into the sandbox needs a
  sandboxed MCP host (recorded limit, as in CRE-T049).
- The maintainer agent run (a Fabro single-node run) stays disabled by policy, like the recovery planner. No model
  output has been measured for this role.
