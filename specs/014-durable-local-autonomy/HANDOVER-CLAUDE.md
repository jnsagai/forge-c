# Feature 014 handover to Claude — 2026-10-25

The owner requested transfer to Claude because Codex credits are running low.
Continue implementation, tests and qualification; do not produce another plan.
Feature 014 is INCOMPLETE. No completion, benchmark, learning-benefit or 24/7 claim is justified.

## Start here

- Repository: https://github.com/jnsagai/forge-c
- Existing branch: `feat/014-durable-local-autonomy`.
- Existing OPEN DRAFT PR: https://github.com/jnsagai/forge-c/pull/42
- Stack base: PR #41, `fix/013-local-autonomous-recovery`; required ancestor
  `f6ff873d5b4f3e9e46956ef26766181aaec2289d` remains present.
- Latest implementation commit at transfer:
  **`4f954e2ed752c0c69b71d86227959076bac4d696`**.
- The handover commit itself changes documentation/evidence only. Inspect current
  `git status`, remote branch and running processes before acting.
- Fetch this branch; do not reset to older main, recreate the specification, squash
  away history, merge the PR, or activate a production deployment.

Read applicable repository instructions, constitution, and all existing Feature 014
architecture/specification/acceptance documents listed in `codex-prompt.md` and the
owner's request: `spec.md`, `plan.md`, `tasks.md`, `acceptance-tests.md`,
`data-model.md`, `local-model-design.md`, `continuous-learning.md`,
`continuous-operation.md`, `research.md`, `evidence-baseline.md`,
`contracts/README.md`, `validation.md`. Inspect source before changing it.
Preserve all 52 requirement/task/acceptance mappings and existing behavior.

## Owner instructions and authority

- ALL actual Qwen tests must execute on remote Omniverse2, not this local machine.
- ALL new local task files, caches, logs, temporary files and worktrees go on
  **loop10**, mounted at `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0`.
- Preserve `/home/jefferson/forge-c`, all uncommitted changes, concurrent Claude
  Feature 015 Codex/Claude ST-driver benchmarks, their services and data. No
  unrelated GPU workload. Do not message the other Claude session.
- Owner explicitly approved Feature 014 live qualification after the expired-grant
  question: **"I do, I approve all"**. The earlier owner statement also approved
  their signing record. Do not ask that same permission again.
- This authorizes a concrete bounded qualification scope using the existing owner
  identity. It does NOT renew the old grant, reset historical missions, waive
  native prerequisites, permit automatic merge/promotion or activate production.
- Report implementation progress every five minutes while working.
- No subagents were used. Do not assume permission for parallel agent work.

## Local authoritative locations

Set these shell variables (task-specific names, never repurpose HOME):

```bash
FC014_BASE=/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c
FC014_OPS="$FC014_BASE/operations/feature014"
FC014_REPO="$FC014_BASE/repos/forge-c-014-implementation"
```

- Main isolated repository above owns the feature branch and is pushed at transfer.
- Clean exact implementation worktree: `$FC014_OPS/dispatch-boundary-followup`,
  detached at `4f954e2`.
- `$FC014_OPS/qualification-enrollment-followup` is another CLEAN detached worktree
  at `4f954e2`, created for the next intake implementation. **No enrollment code
  was written there**. Its name is not evidence that enrollment exists.
- Previous clean source worktrees: `qualification-intake-followup` at `fc7e6d7`,
  `native-admission-followup` at `354b206`, `native-boundary-controls` at `24be359`.
- Python: `$FC014_BASE/venv/bin/python` (3.13.13).
- Source `scripts/forge-env.sh`; it UNSETS PYTHONPATH. Then set
  `export PYTHONPATH="$PWD/factory/python"`.
- Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `TMPDIR="$FC014_OPS/tmp"` and private
  **both** `FORGE_STATE_DIR` and `FORGE_EVENTS_DIR` for every standalone probe.
- Normal umask 0022 is necessary for inherited cross-UID kernel tests. Raw logs
  should be individually mode 0600; do not globally use umask 077 for those tests.
- At transfer loop10 had approximately 25 GB free (99% used). Inspect before large
  downloads/copies; never delete evidence, another session's files or append-only
  history to free space.

## Formal progress and separate status axes

**22 of 52 tasks are checked (42% fully evidenced acceptance tasks, not code %):**
DA-T001, DA-T002, DA-T003, DA-T006, DA-T008, DA-T009, DA-T011, DA-T014,
DA-T015, DA-T020, DA-T022, DA-T023, DA-T030, DA-T037, DA-T038, DA-T039,
DA-T043, DA-T044, DA-T045, DA-T047, DA-T048, DA-T051.

Do not check native-containing tasks based only on fixture/static tests.
Implementation, per-role model capability, RCC/product acceptance, learning benefit,
operational availability and promotion are separate statuses. There have been
**ZERO new candidate Qwen requests**. All new live campaigns remain NOT_RUN.
Historical failure, expenditure and uncertainty remain authoritative.

## Latest implementation increments

1. `24be3592086cb6273097b21de19262b51b98b489` — hash-bound primary and semantic
   protocol fault controls in `afo/protocol_faults.py`, `durable_agent.py`,
   `qualification.py`; eight of twelve declared intervention types supported:
   administrative-forgery, empty-output, malformed-output,
   unqualified-local-alternative, cross-case-reference, reworded-strategy,
   stale-primary, symlink-escape. Signature, job/nonce/case/mission, path/hash and
   exact observed reason are checked. Immutable crash-recoverable primary mutation
   is confined to the explicitly seeded fixture. Actual fault exposure is required
   to count a result. Intervention is not unmodified model competence.
2. `354b206` — optional trial-scoped readiness/provision/step while retaining all
   100 bindings and campaign denominator; finite mission limits can be frozen and
   owner-signed before registration. Existing registered limits/lineage/auth must
   match exactly. Subset completion is never full campaign completion. QUEUED
   orders cannot bypass AFO admission.
3. `fc7e6d74b4a54b2827ab77800e775aa5e454f8f9` — archived signed manifests,
   immutable protocol observation rows and restart-safe collection in existing
   AFO artifacts/SQL. Explicit qualification wrappers close in neutral order state
   `QUALIFICATION_RECORDED`, with no product launch/native product ID/READY claim.
   Closure requires terminal role jobs, recorded result and independent native
   quiescence; first live-failure snapshot is retained. Actual gateway request
   ledger usage is distinguished from zero Fabro command-node token usage. Native
   command/MCP/hook environments explicitly receive private policy/auth/intent/data
   paths and selected profile without forwarding credentials. Source binding
   uncertainty produces UNKNOWN rather than fabricated failure/success.
4. `4f954e2ed752c0c69b71d86227959076bac4d696` — `LaunchNotStarted` marks only local
   failures BEFORE invoking the Fabro subprocess. Durable non-dispatch proof can
   release inference capacity without pretending native termination; original
   dispatch intent and reservation remain. Actual subprocess errors/timeouts and
   lost ACKs remain possibly live. Recovery after proof-publication crash is
   tested; an adopted native execution cannot be overridden by this proof.

Existing runtime includes mission/request ledgers, semantic broker receipts,
verification outbox, model-free supervisor/provider recovery, knowledge capture /
learning dispositions, holdout separation, lesson provenance and operator intent.
Inspect the actual implementation and incomplete task cases; the presence of a
module is not proof that all its acceptance cases are complete.

## Tests: inspect authoritative files, preserve failures

All paths below are under `$FC014_OPS`. Do not sum overlapping suites as separate
independent cohorts.

- Clean `24be359`: `provider-24be359-invocation.json`, core JUnit **492 passed,
  1 optional live-Fabro skip**, 243.773 s; release **13 passed**, 11.857 s.
- Clean `354b206`: `provider-354b206-invocation.json`, core JUnit **507 passed,
  1 optional skip**, 353.724 s; release **13 passed**, 11.035 s.
- `fc7e6d7`: targeted qualification suite **159 passed** before final tiny
  binding guard/README changes. Exact clean full core run **TIMED OUT at 900 s**
  after about 84% progress, with no final JUnit or assertion traceback. Release
  **13 passed**. `provider-fc7e6d7-invocation.json` records exit 124. Do not call
  that source fully regression-verified.
- Diagnostic exact `fc7e6d7` rerun started at ~16:30 UTC and was confirmed live
  at 16:38 UTC, ~92% complete, no failure then. Files:
  `provider-fc7e6d7-timeout-investigation-{core.log,core.xml,release.log,release.xml,invocation.json}`.
  Runner `run_provider_timeout_investigation.py` uses per-test names,
  `faulthandler_timeout=60` and 1500 s process bound. At transfer runner PID
  **3878591**, pytest PID **3878668**; verify command/start time before using a PID.
  **Do not restart merely because observation times out.** Poll actual process and
  invocation/XML; the parent writes final results after each group. If still live,
  let it finish and inspect the exact test/stack at the old timeout point.
- Launch-boundary regression: **107 passed**, 34.098 s, working-tree source then
  committed as `4f954e2`; files `launch-boundary-regression.{log,xml}`.
  A clean exact `4f954e2` rerun of these same four test modules PASSED all
  107 tests, with clean source start/end (16:36:25–16:37:09 UTC). Evidence: `launch-boundary-clean-4f954e2-{invocation.json}` and
  `launch-boundary-clean-4f954e2.{log,xml}`. Inspect completion and clean end state.
  Full inherited core/release regression has NOT yet run on `4f954e2`.
- First new launch-boundary run had three contract failures because the added
  NOT_STARTED path initially populated a forbidden quiescence reference. Fixed
  to retain proof in evidence SQL while respecting the existing schema; all seven
  new tests then passed. Preserve `launch-boundary-first.*` and fixed evidence.
- Earlier full exact runtime `9891b593dcea0949ad53c363ac2d3e8ca100a242` had
  479 passed/1 optional skip + 13 release; offline schema 4-to-9 history replay
  preserved 246 rows in 13 legacy tables and unknown product usage. Seven actual
  local transient-systemd cases passed. Neither is remote topology/soak evidence.
- The independent CRE evaluator at `918c6a4` rejects protected-path changes;
  later promotion gates remain NOT_RUN. Do not waive or recast this as promotion.
- Existing public `validation.md` and evidence aliases still describe older
  `9891b59` runtime in detail. They need a new exact-source evidence publication
  after current tests/auxiliary checks. This handover supplements, not overwrites,
  retained historical evidence.

Useful tooling already on loop10:

- `run_provider_regression.py`: requires clean exact worktree, environment sourced,
  private vendor fixture copy/hash verification, and unique `provider-<rev7>`
  artifact names. Refuses to overwrite raw logs. Core and release run separately.
- Three private ignored vendor fixtures come from
  `isolation-followup/examples/0002-arm_55_rcc_st/inputs/`; verify the first three
  entries of `provider-fixture-provenance.json`. Do not publish vendor content.
- `run_auxiliary_current.py`: prepared-stage skeletons, offline history copy,
  local transient-systemd semantics, exact-source independent CRE. Main isolated
  repository must first be clean at the candidate revision for CRE.
- `publish_provider_evidence.py`: set `FORGE_014_RUNTIME` to the exact clean tested
  worktree. Requires both completed regression results and auxiliary artifacts.
- `build_handoff.py`, `enhance_traceability.py`: existing redaction/evidence helpers.
- `publish_native_increment.py` is HARDCODED to old `9891b59` preparation. Do not
  rerun on a newer source without parameterizing and inspecting its scope.
- For PR updates use REST `gh api --method PATCH repos/jnsagai/forge-c/pulls/42
  --input <JSON-file>`; `gh pr edit` fails on obsolete GraphQL projectCards.

## Remote machine and preparation (last observed; revalidate before live work)

SSH: `ssh -o BatchMode=yes omniverse2@100.118.28.92 ...`.
Authoritative mount `/mnt/data`, UUID `9bc4621a-9543-4562-b24a-5da4faf6a7f1`.
Do not modify the old deployed runtime `/mnt/data/forge-c/lrtx-v2`, its source
`36ed0fc`, old mission/grant, or existing Conductor/Fabro/gateway/Ollama services.
Another generic Ollama exists; never kill it blindly or load competing models.

Private staging directory `/mnt/data/forge-c/qualification-014-17e6cbd` contains:

- clean source `repo-9891b59` (newer source is NOT yet staged remotely);
- `protocol-inputs-9891b59/inputs.json`: all 20 cases × 5 repeats = 100;
- private `input-state-9891b59`, `input-events-9891b59`;
- `protocol-9891b59-manifest.json`, SHA256
  `50dd22b89a1cde0a118c67eea17291bf774513fd221632fa7536ee3ab6348ae7`;
- concrete input preparation/source staging proof; no new grants, missions, jobs,
  service starts or inference were created by this preparation.

Compiler `/mnt/data/forge-c/toolchains/LLVM-19.1.7-Linux-X64/bin/clang`;
Python `/mnt/data/forge-c/venv/bin/python`.
Explicit seeded virtual REG32 fixture (NOT an STM32 product/real incident):
seed ORs bit 1 instead of required bit 0; independent compiled checker exercises
260 inputs plus idempotence, seeded implementation fails 194, reference fails zero.

Pinned profile `local-rtx-v2-omniverse2`, model `qwen3.6:35b-a3b`, digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, Q4_K_M.
Actual selected reasoning HIGH adds 16384 output tokens to raw cap 2048 = **18432**,
so the old 16000 diagnosis envelope cannot fit the output alone. Current code
measures the actual gateway transformation once and sends raw request once.
Complete conservative admission totals are 27647–32330; prospective 32768-token
qualification envelopes must be frozen/signed, never inferred as new permission.
Configured 65536 context is NOT a measured capability result.

### Existing owner signing path

Old `AUTH-OMNI-Q36-LOCAL-SELFHEAL-V4-20261024` expired 2026-10-25 09:00 UTC and its
four diagnoses are exhausted. Do NOT renew it or reset that mission.

Existing principal `jefferson`, ED25519 fingerprint
`SHA256:ckvy+ob0smG1Xbm2Zpvd9sKg6hR3xpwS948GhX2D7js` was verified against the
old remote allowed signer and the local SSH agent. Only public refs are stored at
`$FC014_OPS/qualification-owner/{owner.pub,allowed-signers,provenance.json}`.
After freezing exact new policy/manifest/finite scope, use the existing agent:

```bash
ssh-keygen -Y sign -U -f "$FC014_OPS/qualification-owner/owner.pub" \
  -n forge-afo-authorization <canonical-message-path>
```

Never read/copy private keys. `afo.authz.message()` defines canonical signed bytes
(excluding signature_ref and revoked_utc). No actual new owner grant has yet been
signed. Unit tests use ephemeral fixture keys; these are not campaign authority.

## Immediate next implementation work

1. Inspect the two in-progress test outputs above. Fix actual failures; do not
   hide the 900-second timeout or declare its longer rerun successful before exit.
2. Implement **qualification enrollment/intake** through existing AFO authorities.
   The next worktree is clean and there is NO enrollment implementation yet.
   `qualification.provision()` currently requires already submitted, mission-linked,
   admitted RUNNING orders; preparation generated only prospective envelopes/IDs.
   Concrete source facts to handle:
   - `qualification_inputs.prepare()` writes envelope.json and input-manifest.json
     but trial metadata currently does not hash-bind the administrative envelope,
     launch manifest and `.forge-run/{manifest,model-profile}.json`. Freeze these
     exact paths/hashes before enrollment; refuse unbound legacy input for intake.
   - `Store.submit(env, repo=<frozen-input-root>, approve=...)` validates intake and
     manifest hash. Check `authority.decide` for actual submit/launch/recover scope,
     exact current owner signature and signed_runbook_ref matching manifest SHA.
   - Register only the exact explicitly frozen distinct qualification mission;
     preserve immutable limits/lineage/auth and existing spent/unknown usage.
     Link mission BEFORE exposing a QUEUED order (mission-order link has no order FK),
     or make enrollment transactionally safe against concurrent scheduler admission.
   - Use existing scheduler lease, pause/drain, max-concurrency and operator epoch.
     `Store.admit(..., qualification_ref='qualification-014:<sha>')` already creates
     the wrapper attempt without FABRO_LAUNCH. It is not yet wired into scheduler.
   - `scheduler.preflight()` currently interprets max_attempts=0 as exhausted;
     explicit protocol-only mission must check finite job limits instead of product
     attempt limits, without bypassing ordinary product budgets.
   - `scheduler.launch_manifest()` resolves against REPO_ROOT; generated qualification
     inputs are outside the repository. Resolve only authenticated frozen intake
     roots, retaining all regular product-path checks.
   - Use existing artifact/SQL evidence tables to record signed intake context;
     no new scheduler, memory store or authority. Recover crash after admission
     before role preparation without duplicate admission/job reservation.
   - Wrapper RUNNING denotes qualification work only, no native product run or
     product success. `local_agent.prepare()` loads the source workspace's existing
     `.forge-run` profiles; `local_agent.supervise()` already runs every Conductor
     cycle and performs model-free completion collection even after revocation.
     `dispatch.reconcile_running()` skips wrapper attempts with no fabro_run_id.
3. Finish the FOUR remaining real fault controls:
   `revoked-before-dispatch`, `expired-mission`, `lost-launch-ack`,
   `cancel-ack-still-live`. Keep exact signed exposure and actual native evidence.
   Never fabricate IDs/ACKs as native truth or count fake qualified alternatives.
   Do not expire the common mission and block the entire matrix just to satisfy
   one negative case. Lost launch ACK must use actual nonce/list adoption once;
   cancel acknowledgment alone never releases inference capacity.
4. Stage a clean candidate and concrete isolated qualification runtime on Omniverse2.
   Verify namespace/profile/root/ports/model digest and finite resource authority
   before inference; do not reuse the old gateway with a different AFO database or
   start competing Ollama replicas. Temporary qualification is not production
   promotion. Keep all 100 denominator slots even when only eligible trials run.
5. Qualify diagnosis, author, inspector and maintenance SEPARATELY; continue actual
   RCC, independent product benchmark, chronological learning-benefit evaluation,
   24/72/168-hour continuous-operation campaigns. Same-model agreement is not an
   independent correctness oracle. Do not stop model-free service when a job,
   capability, finite allowance, benchmark or campaign ends.

## Confirmed additional source gaps requiring scrutiny

- `diagnosis_packet.seal()` assigns all evidence refs to every obligation;
  `durable_agent.request_material()` still retains global inventory and can load
  all source text for a selected unit. Toy REG32 fitting does not prove coherent
  bounded RCC decomposition; preserve requirement/dependency coverage.
- Mission limits are immutable registration records; there is no audited explicit
  signed budget-amendment path. New orders cannot reset exhausted RCC history.
  Historical product usage is UNKNOWN; actual native usage may bound it, absence
  must never be treated as zero.
- `role_capability.admit_job()` diagnosis complexity is hardcoded to one and other
  roles may lack measured complexity checks; tiny protocol capability must not
  qualify arbitrary RCC/author/inspector work or a different task class.
- Configuration comparison counts individual changed identity fields; changing
  quantization also changes model digest. Inspect proper preregistered factor
  grouping rather than relaxing comparisons or asserting capability from download.
- Rejected proposal diagnostics discard useful validator path/shape details.
  Preserve bounded non-secret diagnostic facts if needed, not hidden reasoning or
  raw prompt/completion dumps.
- Controller-only terminal experience capture may lose heldout scope because the
  strict queue envelope cannot contain holdout fields. Native product/job capture
  already preserves scope; qualification wrappers now have neutral terminal state.
  Inspect never-native ordinary heldout orders separately.

## Evidence/publication caveats

Two earlier standalone fixture events accidentally reached shared local JSONL;
owner was informed and provenance is retained. Do not delete history. Exclude IDs
`fx-33782a5451904fcb931d7f1c35e48781` and
`fx-2d44a08dbf0c4da1a90232c39bcfcfab` from operational/learning success metrics.
No recurrence after both private state/event roots were required.

Keep raw private/vendor data out of Git. Commit reviewable source/test increments,
publish exact-revision sanitized evidence, update PR #42, and leave it draft.
Older `$FC014_OPS/RESUME-014-*.md/json` files are history; this document supersedes
stale HEADs, approval uncertainty and old four-fault-only implementation claims.
