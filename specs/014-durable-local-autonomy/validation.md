# Implementation and qualification status

Updated 2026-10-26 (Claude continuation). Exact runtime source candidate: `de324a3c8686f06be566d479ea1a2d9dac48c61a` (`5dc2df3`, `dddf00e` before it; see [2026-10-25 continuation](#2026-10-25-continuation-intake-fault-controls-and-preliminary-omniverse2-trials)); the `9891b59` evidence below is retained history. Later evidence/documentation commits do not qualify a different running deployment. Feature 014 remains stacked on PR #41; neither PR was merged or activated by this work.

The original authored specification and its three Feature 014 contracts are retained. `traceability.csv` is the immutable design-time NOT_IMPLEMENTED inventory used by the original specification checker. The dated [implementation matrix](implementation-status.csv) and [machine-readable evidence ledger](../../evidence/014-durable-local-autonomy/implementation-status.json) record all 52 implementation/acceptance dispositions. Checked tasks have passing evidence for their required deterministic scope. Native/live-containing tasks remain unchecked, even where their implementation and fixtures passed.

## Independent status axes

| Axis | Result |
|---|---|
| Runtime implementation | Verified core increments; native qualification tooling remains partial. Exact-revision core/release evidence is below. Wider inherited coverage uses separately recorded revisions; combined-ordering and optional/native limits remain explicit. |
| Actual Qwen/Fabro/gateway interoperability | PRELIMINARY live trial subsets on Omniverse2 (one isolated runtime per revision, 836ae49..dddf00e): intake, admission, native Fabro runs, gateway metering, typed incidents, wrapper closure and the four dispatch/liveness fault controls exercised; seven runtime defects found and fixed. Grammar-friendly wire schema raised schema-valid answers from 0/6 to 23/24. Not a completed campaign. |
| Diagnosis, author, inspector, maintenance capability | Diagnosis: PRELIMINARY FAIL for `qwen3.6:35b-a3b` (reasoning high, single constrained response): NEEDS_EVIDENCE chosen for evident conformance repairs across 5 positive cases × 4 prompt/interface variants; the NEEDS_EVIDENCE case correct. Owner-chosen reasoning-off variant (3de1a44): same decisions at ~1/3 of the tokens. `qwen3.8:27b-q8_0` (bcb8cae, reasoning none): same pattern, 6/6 NEEDS_EVIDENCE. Stepwise diagnosis (owner-requested split; three small grammar-constrained questions, deterministic assembly, unchanged broker; qwen3.6 reasoning off, a206c54): 93/95 trials of the frozen matrix observed == expected with all fault exposures matched (24 accepted repair plans); independent REFERENCE_HARNESS audit (dbcec39): 0 false successes, 0 duplicate effects, 0 authority escapes over 95 rows; official protocol report 93/100 correct, FAIL (2 misses, 5 trials blocked by the measured-alternative prerequisite). Fixes b7ce315/5dc2df3 (obligation enum, separate strategy question, cited-findings context within the frozen job envelope): fourth matrix 95/95 eligible correct, audit 0/0/0, official report no failures, INCOMPLETE 95/100 (5 trials blocked only by the measured-alternative prerequisite). Inspector (owner 2026-10-26 "Stepwise inspector in 014"): stepwise local SWE.1 inspector on Feature 011's learning set (7 holdouts x 7 cases): learning-14 (`285d21e`) 49/49 correct: 42/42 seeded defects caught, 7/7 clean baselines passed, 0 empty inspections ([evidence](../../evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md)); PRELIMINARY; frozen test-set calibration (F011-T046, 3 runs) in progress. Advisory continuation (`ad5447a`, owner decision) lets an exhausted ladder continue with its gaps registered for the end-of-run human review; the release rule is unchanged. Author, maintenance: NOT_RUN. No model family or nominal context setting implies role competence. |
| RCC recovery / sealed READY / GPIO follow-on | NOT_RUN. Historical RCC failures remain failures; GPIO requires all five explicit prerequisites. |
| Cross-job learning benefit | NOT_RUN. Capture, qualified retrieval and comparison fixtures do not establish measured benefit. |
| Continuous operation | Model-free controller and isolated systemd checks passed. Remote reboot/mount/load faults and 24/72/168-hour campaigns NOT_RUN. |
| Rolling 30-day SLO | NOT_DEMONSTRATED. |
| Source promotion / deployment | Not activated. Independent CRE vetoes protected-path changes; external engineering review is required. No automatic promotion switch was added. |

## Source changes

The existing Conductor, queue/outbox, supervisor/watchdog, native Fabro adapter, knowledge store, curator/MCP, CAPA/CRE and KPI paths own the implementation. No second scheduler, memory database or source authority was introduced.

Complete finding/primary-evidence indexes are hash-bound and phase/role/path scoped. The semantic adapter serializes the locked role instruction, full selected evidence, schema and output reserve before admission. Its current fallback is an explicitly labeled conservative UTF-8 byte bound, not a qualified native tokenizer measurement. Coherent obligations preserve global requirement/dependency inventories; a task outside the measured/available envelope blocks rather than dropping evidence. This implementation does not claim that the historical RCC case fits or that decomposition improves Qwen without the native comparison.

Strict semantic proposals exclude administrative identity and budget fields. Deterministic binding retains the authoritative recovery-plan validator. Append-only receipts, stable effect/nonces, request reservations and verifier epochs survive interruption. A task outcome and native/provider liveness are separate: a failed/blocked/succeeded job, timeout, cancel acknowledgement, listing gap or idle GPU never proves quiescence. Unknown provider requests retain inference ownership.

Managed local profiles now bind each request to immutable gateway/model PID-namespace lifetime evidence. The external watchdog fences subsequent generation before retiring the exact namespace init through a pidfd. Kernel termination proof settles provider requests without resetting usage, receipts or task outcomes; authoritative native reconciliation still owns inference-lease release. Fabro alone may be restored while that lease is held. Healthy active generation is preserved. Shutdown effects and resume share the operator-intent lock; pending stop settlement is checked even with a healthy Conductor heartbeat. Different boot/start identities permit forgetting stale PID projections without signaling their replacements. These paths have real-kernel and durable-ledger fixtures, not deployed native-topology qualification.

Mission identity and expenditure survive continuation and duplicate adoption. Known old expenditure remains charged; unbounded old usage refuses new admission. The fresh-database migration includes the previously lazy local-agent table so disabled/empty continuous supervision can capture learning before any model job exists.

Every unique ordinary job/phase outcome can produce factual experience and a durable learning disposition. NO_NEW_LESSON and DEFERRED_BUDGET are valid outcomes. Ordinary/negative source qualification, exact applicability, independent applicable/adverse receipts, content/version identity, holdout isolation and atomic delivery/retraction fences extend the existing lesson store. Legacy PROMOTED-repair validation and separate inspector IL governance remain in force. Exposure, application and independently measured benefit are distinct; comparison costs include retrieval, curation and validation.

Continuous mode rejects production finite-cycle limits. Failed/capability-limited jobs, exhausted engineering allowances, empty queues and campaign completion do not terminate supervision. Operator intent uses an OS-owned private file, durable epochs and serialized bounded start effects. Pending outbox commands cannot rebind to a newer resume epoch. STOPPED remains unresolved until contrary service-manager effects and native work settle. Explicit operator exit 77 prevents `Restart=always` restart; a false boot condition remains inactive.

The Maintainer retains its existing restricted native/MCP candidate workflow under the shared mission ledger and per-role capability gate. Frozen submission intents reconcile a crash after commit without another commit; immutable case/submission/reproducer receipts drive completion even without final model text. A candidate receipt remains BLOCKED for independent review, and native terminal status never releases a still-live provider request. Legacy submissions retain independent validation; new submissions cannot downgrade after losing their receipt.

AFO capture now preserves held-out workspace/qualification scope across jobs and phases. Late append-only classification excludes older facts of the same execution from lesson qualification and improvement routing. Previously validated ordinary lessons are retracted on retrieval; the transactional delivery fence also blocks a classification arriving between selection and exposure. Facts and dispositions remain durable. The three old-source counterexamples fail with explicitly pinned imports; the corrected 30-case learning/legacy/inspector run passes. See [held-out controls](../../evidence/014-durable-local-autonomy/followup/heldout-capture-provenance.json).

## Concrete protocol preparation and remaining implementation

Source increments `d629127`, `2de7ced` and `9891b59` add actual source-case preparation, effective gateway-envelope accounting, signed initial qualification reservations, four declared response interventions and typed empty-content refusal. Their separately recorded, overlapping regressions are retained in [increment evidence](../../evidence/014-durable-local-autonomy/followup/native-qualification-increments.json); they are not summed into independent native cohorts. The formal completed task count remains **22/52**. No native-containing task was checked from fixture results.

The old adapter measured before the profile added high reasoning and 16,384 output tokens. The [old-source control](../../evidence/014-durable-local-autonomy/followup/reasoning-envelope-before.json) shows the raw request passing its local 16,000-token fit check while the transformed provider request would be refused by gateway admission. This was an early accounting/preflight error, not evidence of overspending or the historical V4 cause. The new adapter measures the transformed copy and sends the original once. It also refuses boolean, zero, negative and otherwise invalid output caps rather than turning them positive through an extension.

On Omniverse2, clean `9891b59` generated all 20 cases x 5 repeats using the pinned Clang 19 binary and private state/events. A real compiled checker evaluates 260 inputs plus idempotence: seeded REG32 fails 194 checks; its independent reference fails zero. These are explicitly seeded virtual qualification fixtures, not manufactured historical product incidents or STM32 acceptance. Complete conservative admission totals (UTF-8 input byte upper bound plus effective output cap) range from **27,647 to 32,330** under the unchanged high-reasoning profile. The prospective 32,768-token envelopes fit these inputs; no grant, mission, order, runtime job or inference request was created. Configured context 65,536 remains distinct from a qualified role envelope.

The frozen manifest hash is `50dd22b89a1cde0a118c67eea17291bf774513fd221632fa7536ee3ab6348ae7`. It declares 20 response-fault trials (four recipe types x five repeats). Administrative forgery, dropped content, truncated JSON and an unqualified model switch require the exact owner-signed trial mapping, seeded case, current order/model scope, policy/deadline and held native execution. The ledger retains only original/injected visible-content hashes and bounded metadata. Changed replay is refused; missing exposure evidence cannot satisfy the report. Injected outcomes do not establish unmodified model competence. Unmodified empty/invalidly typed output creates a protocol incident and no semantic receipt.

The full native gate is **BLOCKED**, with exact preparation blockers `NATIVE_PROTOCOL_FAULT_EXECUTOR_NOT_PROVISIONED` and `INDEPENDENTLY_MEASURED_AUTHORIZED_LOCAL_ALTERNATIVE`. Source/symlink/cross-case intervention, strategy replay, revocation/expiry, lost launch acknowledgement and cancel-with-live-request executors remain to be implemented and qualified. The alternative must be genuinely measured and authorized. Frozen job IDs are prospective; existing AFO intake, mission registration and lazy admission must be completed without pretending that a product run exists or admitting 100 concurrent orders. See [executable input instructions](../../factory/qualification/014/README.md).

Next execution is to finish those exact native boundary controls and eligible per-case provisioning, then use the already approved signing path for a distinct bounded qualification mission. Preserve the 100-case denominator, independent audits, all failed attempts, one inference lease and existing historical expenditure. No new signature was made yet, and no persistent source deployment was activated. Product/role/learning/operational campaigns remain separate and NOT_RUN.

## Executed evidence

See the exact commands, timestamps, exit codes, hashes and JUnit reports in:

- [Core deterministic implementation](../../evidence/v0.4/runs/DA014-core/latest.json).
- [Independent release regression process](../../evidence/v0.4/runs/DA014-release/latest.json).
- [Restored fixture/ref/tool prerequisites](../../evidence/v0.4/runs/DA014-restored-prerequisites/latest.json).
- [Historical offline migration and accounting](../../evidence/v0.4/runs/DA014-history/latest.json).
- [Isolated systemd semantics](../../evidence/v0.4/runs/DA014-systemd/latest.json).
- [Independent CRE evaluation](../../evidence/014-durable-local-autonomy/cre/independent-evaluation.json).

Exact source `9891b59`: core **479 passed, 1 skipped**, no failures/errors (234.822 seconds); separate release regression **13/13 passed** (11.364 seconds). The core command includes all eleven Feature 014 test modules, inherited AFO, lessons, profiles/gateway/ACP, inspection/workflow/skill, brownfield and kernel confinement regressions. The source checkout was clean at start and end. Commands source `scripts/forge-env.sh`, then explicitly set `PYTHONPATH` to that checkout’s `factory/python`; `TMPDIR` and all test outputs are on loop10. Vendor fixtures are hash-verified private inputs; their provenance is published without their contents. The release file runs in a separate process with the generic Fabro token override unset. The recorded normal umask preserves inherited cross-UID fixture behavior; raw logs remain mode 0600. No live inference was performed.

The [supplemental regression index](../../evidence/014-durable-local-autonomy/followup/supplemental-regression-index.json) retains separate source revisions, commands, denominators and follow-ups. The first 44-file group recorded 316 passes, seven skips and one timeout; the timed-out unchanged LRTX suite subsequently passed all 18 cases with its declared longer bound. The 103-file group recorded 644 passes, 25 skips and two missing-prerequisite failures; both unchanged assertions passed after restoring a private read-only CRE snapshot and the Renode discovery root. Further runs passed 71 pinned SafeC cases, 20 historical-corpus cases and the opt-in clean-environment reproduction. These overlapping groups are not summed into a fabricated independent cohort or relabeled as current-revision native qualification.

The real isolated Conductor test runs the actual process with a missing/invalid engineering policy, an already exhausted zero-allowance mission and no model service. It observes several healthy cycles, verifies unchanged mission accounting and zero model requests, then records an explicit stop and exit 77. This is short deterministic runtime evidence, not an availability campaign.

Seven actual local systemd tests cover unexpected clean exit, bounded immediate restart exhaustion, later slow start, process kill, notify watchdog hang, intentional stop, operator-exit prevention and boot-condition behavior (the report groups related observations into seven cases). They use only uniquely named transient `forge-c-014-qual-*` units and clean up those units. They do not deploy or qualify the remote production unit graph.

Read-only reconstruction exported the Omniverse2 unit/native event inventory without prompts, private inputs or hidden reasoning. An immutable private SQLite dump was replayed into a new loop10 database. The final history tool reads the Conductor's authoritative migration table (an earlier development report incorrectly read SQLite's unrelated `user_version=0`; that report is retained). Schema 4 -> 9 preserves all 246 historical rows in 13 legacy tables. Duplicate imports retain five unique product executions from 20 adoption rows and four diagnoses. Reported diagnosis tokens remain 54,704; conservative diagnosis charge remains 64,856. Unknown product usage stays unknown and prevents fresh capacity. V4's native stopping cause remains UNKNOWN. No original remote database was modified.

## Retained failures and limits

The broad `e0b340b` run reached 832 passes, seven failures and 17 skips before the declared 900-second limit and forced cleanup (exit 137). It did not complete all 1,445 collected tests. The later `d2e71bf` remainder recorded 383 passes, 12 failures, 133 skips and 15 setup errors. These runs and later contrasts are retained in [development attempts](../../evidence/014-durable-local-autonomy/development-attempts/); retries do not erase them.

- The earlier CRE symptoms for RPR-041, RPR-044 and RPR-047 were reproduced as a compiler environment failure: inherited `TMPDIR` pointed outside writable sandbox scratch. Runtime `e973286` binds compiler temporary files to scratch. Before/after controls, nine kernel compilation cases and all 12 unchanged CRE promotion regressions passed afterward; frozen oracles were retained. This does not establish the historical Qwen V4 stopping cause.
- The inherited live-local-Qwen evidence check cannot find an eligible package in the isolated test state. It is not new Qwen execution or candidate product qualification. Qwen tests must run on Omniverse2.
- Holdout-permission and KPI event-reference failures reproduced on unchanged `918c6a4`. Test-only `754e93c` selects the actual intended no-sandbox holdout backend and pins the evaluation window for frozen October 14 events. Their original assertions pass (37 passes, one optional native-state skip). Earlier broad-suite traceability failures remain retained alongside isolated passing checks.
- The external-finalizer credential assertion fails in the same combined ordering on the unchanged baseline and candidate; its isolated test and full isolated release file pass. The original failed output is private; published copies redact credentials.
- Missing private inputs, absent local historical branch refs and a tool-discovery environment assumption caused remainder failures. Available inputs/refs/tool settings were restored without changing oracles; all 45 targeted prerequisite regressions and 50 peripheral/traceability regressions then passed.
- One explicitly disabled live-Fabro check remains skipped in the core command. Relevant native acceptance cases remain NOT_RUN.

The first Maintainer receipt development run exposed an artifact-directory bug; it is retained, the path was corrected, and the final run includes the new receipt tests and all inherited Maintainer regressions.

The [provider development record](../../evidence/014-durable-local-autonomy/followup/provider-development-attempts.json) retains the generic-Conductor shutdown regression and its production fix, plus a failed broad invocation that omitted the pinned environment/private fixtures and used an incompatible cross-UID fixture mask. The corrected exact-revision run above passes; earlier failures are not discarded.

The exact-`9891b59` independent evaluator is `cre-promotion-runner@918c6a4`; it returns REJECTED / PROTECTED_PATH_CHANGE and does not run later promotion gates. Feature 014 deliberately changes protected recovery/lesson authority surfaces under this externally requested engineering PR. This result is retained, not converted to eligibility or bypassed. Candidate source is never promoted automatically.

A standalone delivery fixture probe emitted two diagnostic knowledge audit events into the shared local JSONL stream because it omitted the private event-path override. Benchmark jobs, services and outcome records were unchanged. Their exact event IDs are retained in [fixture event provenance](../../evidence/014-durable-local-autonomy/followup/fixture-event-provenance.json) for exclusion from operational/learning metrics. Append-only history was preserved; subsequent standalone probes require private state and event paths.

## 2026-10-25 continuation: intake, fault controls and preliminary Omniverse2 trials

Source commits on `feat/014-durable-local-autonomy` after the handover (`72edbec`): `d446ef6` signed qualification intake
(enrollment through existing AFO authorities, mission linked before QUEUED, frozen-root launch resolution, protocol-only
mission limits, wrapper start); `836ae49` the four remaining fault controls (revoked-before-dispatch, expired-mission,
lost-launch-ack, cancel-ack-still-live; all twelve declared interventions now have executors); then fixes found by the
live runs: `cc2b39c` packet import at intake, item-local wrapper refusal, `expose-api --host-port`; `20f6b02` typed
incident codes and required operations intent; `8e1aee5` /proc race in provider identity; `2dfd32f` value-free
rejection diagnostics; `c6850ac` pidfd syscall fallback; `e35ed0a` closed-branch wire schema; `7f197d2` bridge
identities for managed stop; `677d45a`, `b759094`, `dddf00e` single-response contract, evidence aliases and decision rule.

Exact `dddf00e` (clean dedicated worktree, private state/event roots): core **559 passed, 11 skipped**, 0 failures
(500.1 s); release **13/13** (9.0 s); history replay and transient-systemd semantics PASS; independent CRE
`cre-promotion-runner@918c6a4` **REJECTED / PROTECTED_PATH_CHANGE** (retained, later gates NOT_RUN). The 11 skips (the
`9891b59` run had 1) are 8 real-workspace history cases absent from the private state root, 2 cross-UID probes without a
0600 owner file and the disabled live-Fabro check; earlier `4f954e2`, `836ae49`, `8e1aee5`, `677d45a` clean runs also
passed with 0 failures.

Stepwise diagnosis commits `bdba4c1`..`5dc2df3` (signed task class `two-step-diagnosis`; four grammar-constrained
questions, deterministic assembly, unchanged broker), independent auditor `afo/qualification_audit.py` (`dbcec39`).
Exact `5dc2df3` (clean dedicated worktree, private state/event roots): core **576 passed, 11 skipped**, 0 failures
(499.0 s); release **13/13** (9.2 s); history replay and transient-systemd semantics PASS; six prepared manifests BLOCKED
as before; independent CRE `cre-promotion-runner@918c6a4` **REJECTED / PROTECTED_PATH_CHANGE** (retained, not waived).
Clean `a206c54` (570 passed) and `dbcec39` (575 passed) runs also had 0 failures.

Exact `de324a3` (after `455e1dd` measured objective/work class and capability report, `74ba546` preregistered
comparison factors, `c8af6fe` intake-manifest holdout scope, `de324a3` killable-group fix): core **579 passed, 11
skipped**, 0 failures (506.9 s); release **13/13**; history replay and transient-systemd semantics PASS; independent CRE
**REJECTED / PROTECTED_PATH_CHANGE** (retained).

Whole inherited suite on `74ba546` (197 files, one process each with private state, two native e2e files
excluded; [summary](../../evidence/014-durable-local-autonomy/inherited-whole-suite-74ba546.json)): 1,648 tests,
44 skipped, 3 failures in 3 files plus one killed file. `test_cre_d7_final`, `test_lrtx_drill` and `test_sim_renode`
fail identically on the base `f6ff873` in this environment (inherited, not waived). `test_da014_integration` was a
Feature 014 defect: an in-process verification claim by a group/session leader was marked killable and lease
expiry SIGKILLed the runner; fixed in `de324a3` (file passes in its own session). The run's worktree was left
modified by the inherited `test_t050_t051_docs_status` status regeneration (timestamp/commit only). DA-T029 stays
partial: three inherited failures and the retained CRE rejection.

Retained: the `fc7e6d7` full run that exceeded 900 s was re-run: 507 passed/11 skipped in 1,007 s; one test took 328 s
(normally ~2 s) during host memory pressure (systemd-oomd kill at 16:45:54) before a clean host shutdown at 16:50; the
runner's final JSON lacks the release entry although its log/JUnit show 13 passed. A `cc2b39c` regression is invalid
evidence: source files in its worktree were edited while it ran (its two failures exposed the real /proc race fixed in
`8e1aee5`). One driver attempt started 33 s before its grant's issue time and was refused `AUTH_NOT_CURRENT` (no effect).
Stuck wrappers from the 836ae49 attempt and stacks that the older code could not stop managed were closed/stopped
through existing FSM edges or the unmanaged stack path after setting that runtime's intent to STOPPED with the reason.

Preliminary live results, findings table and exposure facts:
[omniverse2-preliminary-20261025](../../evidence/014-durable-local-autonomy/omniverse2-preliminary-20261025/README.md)
(`summary.json` rows are sanitized; no reasoning, raw prompts or vendor content). They are trial subsets of separate
per-revision campaigns; no report reduces the 100-trial denominator and no task is ticked from them.

## Executable qualification handoff

Six [stage skeleton manifests and dry-run reports](../../evidence/014-durable-local-autonomy/qualification/prepared/) freeze the 20x5 protocol denominator, RCC stage, 30-product cohort and 24/72/168-hour operation stages. They remain explicitly BLOCKED with their missing input/job bindings. The separate [concrete Omniverse2 protocol preparation](../../evidence/014-durable-local-autonomy/qualification/concrete-9891b59/concrete-input-preparation-9891b59.json) now freezes all 100 source cases and prospective job bindings, actual model/configuration identity, compiler oracle and a full manifest. No runtime job was admitted. A dry-run or specification validator is never runtime qualification.

The historical `AUTH-OMNI-Q36-LOCAL-SELFHEAL-V4-20261024` expired at 2026-10-25 09:00 UTC and its four diagnoses were exhausted. It was not renewed, reused or signed by this implementation. The owner explicitly approved Feature 014 qualification in this conversation on October 25 ("I do, I approve all"). That approval permits preparing the new bounded campaign through the existing signing process; it does not change historical expenditure. The concrete 100-case bindings and requested finite 32,768-token initial job envelopes are frozen; they are not authorized ledger reservations. A new signature over `qualification-014:<frozen-manifest-sha256>`, exact private qualification policy/namespace and registered bounded mission/intake remain to be provisioned after the remaining case prerequisites. The conversation approval already exists; this is implementation/signing work, not a new permission question. Role qualification also pins actual model digest/precision/reasoning/schema/sampling/context/task and adapter revision.

The owner is concurrently using another Claude terminal for Codex/Claude ST-driver benchmarks. Read-only process/service metadata and the Feature 015 specification locate its Conductor on local loop10 with the cloud Fabro configuration/storage, separate from the older Omniverse2 local-Qwen stack at `/mnt/data/forge-c/lrtx-v2`. Those services, source worktrees and benchmark data were preserved. Qualification must use a separate candidate checkout/data root and the existing owner principal; its allowed public-key fingerprint matches an available SSH-agent key. No private key was read, no new grant was signed yet, and no remote service or model request was changed. The hash-verified clean current checkout is staged at `/mnt/data/forge-c/qualification-014-17e6cbd/repo-9891b59`; [current source staging evidence](../../evidence/014-durable-local-autonomy/qualification/concrete-9891b59/source-9891b59-staging.json) records zero service starts and zero inference requests. The prior `repo-794e8d0` checkout is retained. All new writes are inside the separate qualification directory; the old runtime remains untouched.

On the Omniverse2 host only, with the pinned clean runtime checkout, approved profile namespace, registered bounded mission/order lineage and independently frozen cases:

```bash
python -m forge_factory.afo.qualification dry-run --manifest <frozen-manifest.json>
python -m forge_factory.afo.qualification provision --manifest <protocol-manifest.json> --authorization-ref <current-signed-id>
python -m forge_factory.afo.qualification step --manifest <protocol-manifest.json> --authorization-ref <current-signed-id> --results <results-directory>
python -m forge_factory.afo.qualification report --manifest <protocol-manifest.json> --results <results-directory>
```

Provisioning binds predeclared jobs after signing without changing case hashes or creating a grant, mission or model request. When the manifest explicitly freezes initial per-job envelopes, their exact owner signature, source/case/mission/model, per-order cap and declared context are checked before the first ledger charge. Existing job reservations cannot be rebound and production calls retain the registry allowance. Each call is bounded. Repeated `step` calls use existing AFO/native reconciliation and the same jobs; no campaign scheduler or blind relaunch is added. Independent audit files live outside product workspaces under `state/lrtx/qualification-audits/<manifest-sha>/<trial>.json`; their source revision, observation hash, independent producer and oracle hashes must match. Missing audits cannot become zero authority escapes, false successes or duplicate effects.

For RCC/benchmark, existing Conductor intake owns execution; qualification `step` observes bound product jobs and sealed archives, independent gates and request metadata. For operation stages use `python -m forge_factory.afo.operational_campaign start|sample|fault|report`, or the existing `afo.soak` entry point. Only the fixed authorized service signal recipes are executable faults; reboot, storage/resource faults and other exposures require separately authorized host fixtures. Sampling/reconciliation continues without renewing engineering authority. Required fault/work/post-campaign/later-intake coverage and the complete wall-clock denominator cannot be dropped. Campaign completion never stops the factory.

Before live execution: qualify the actual installed constrained-output/MCP/native header path, per-role semantic envelopes, cancellation/late-usage behavior, namespace dependencies and approved operational recipes. Then execute the 100 protocol trials, genuine RCC recovery and all six gates, gated GPIO intake, the representative 30-product benchmark, chronological learning comparisons, and staged 24/72/168-hour campaigns. All remain NOT_RUN here.

## 2026-10-26: US11 (stepwise inspector, advisory continuation, offline improvement) and regression

The owner decisions of 2026-10-26 are recorded as US11 (DA-FR/T/AT-053–058, commit `7726942`). None is ticked; 22/58 tasks have their full evidence.

- DA-T053: the stepwise inspector passed the learning set (learning-14 at `285d21e`: 49/49). Rows and changes: [stepwise-inspector-20261026](../../evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md).
- DA-T054: advisory continuation after the existing bounded ladder (`ad5447a`; v1 records kept byte-identical in `674bc07`). Lesson/CAPA and diagnosis-repair rungs are not integrated.
- DA-T055: calibration runs on the 9-baseline subset pre-registered in `1067d40`. Two gate defects of the first full-set run are recorded in the evidence README.
- DA-T056–058: `forge_factory.offline.{export,disposition,patch}` with contracts `offline-export-manifest`, `review-disposition` and `patch-bundle` (`dc000e8`, `53a853e`, `763f356`, `a23a611`). Deterministic tests only; no live offline round trip yet. Signing a disposition or a patch is an owner act in namespaces `forge-review-disposition` and `forge-patch-bundle`.

Regression on loop10 (no live Qwen; private owner inputs copied with their recorded hashes; operations directory `operations/feature014/`):

| Source | Core (`run_provider_regression.py`) | Release | Whole inherited suite (`run_full_inherited.py`) |
|---|---|---|---|
| `b180c97` | 594 passed, 1 skipped, 0 failed | 13/13 | 198 files, 1,713 tests, 4 failed |
| `674bc07` | 610 passed, 1 skipped, 0 failed | 13/13 | 201 files, 1,729 tests, 2 failed |

On `b180c97`, two of the four failures came from `ad5447a`: `test_lrtx_compat` (the v1 structured record gained `"advisory": false`) and `test_da014_advisory` (a substring check matched a state path). Both are fixed in `674bc07`. The two remaining failures, `test_cre_d7_final` and `test_sim_renode`, fail identically on base `f6ff873`. The end-of-run dirty `docs/IMPLEMENTATION-STATUS-v0.4.md` and `evidence/v0.4/implementation-status.json` come from the inherited `test_t050_t051_docs_status` side effect.

## 2026-10-26: owner accepts 95/100; known issues reported for humans

Owner decision: "95/100 is good enough!!! Lets not forget to have a factory that is not perfect, but can evolve over time and report the known issues to be solved by a Human." The native protocol gate passes at 95/100 (campaign `5dc2df3`: 95 correct, 0 failures; the 5 qualified-local-alternative trials not run), and [DA-AT-024](acceptance-tests.md) records the amendment. Everything the factory cannot yet do, or does imperfectly, is listed with evidence and the human action it needs in the [known-issues register](../../evidence/014-durable-local-autonomy/known-issues.md) (11 entries).

Evidence records and ticks (27/58 tasks; `scripts/mark_task.py`, each record PASS with exit code 0):

| Task | Evidence | Revision | Scope |
|---|---|---|---|
| DA-T024 | `DA014-protocol-95` | `5dc2df3` | live native protocol, 95/100 owner-accepted |
| DA-T053 | `DA014-stepwise-learning`, `DA014-US11` | `9f001ed`, `e8e7fb6` | live learning set 49/49 (preliminary), 91 deterministic tests |
| DA-T056, DA-T057, DA-T058 | `DA014-US11` | `e8e7fb6` | deterministic (live round trip: KI-014-009) |

Core regression at `e8e7fb6`: 627 passed, 1 skipped, 0 failed; release 13/13 (records `DA014-core`, `DA014-release`). The implementation-status ledger is re-baselined to 58 rows at `e8e7fb6`; `verify_handoff.py` accepts only PASS_DETERMINISTIC or the two recorded live statuses for ticked tasks, requires model capability to stay PARTIAL and product success, learning benefit and availability to stay NOT_RUN.

## 2026-10-27: inspector learning sets 1-3 perfect; refreshed held-out set calibrated (DA-T055)

Revision `9300475` (learning-set-3 rules: safety-scope fact question, one-bit 'write 1/0', configuration writes, field named after 'shall', waits as reads, fixed-state assumptions) was tested on loop10 first: review and seeded tests 61 passed and 0 skipped; lrtx and DA014 suites 538 passed and 2 skipped (no pinned SafeC engine, no frozen SWE.2 baseline). The truthful preflight passed on all 18 learning baselines, and a replay of the recorded answers of learning-16, learning2-2 and learning3-1 left every baseline with 0 standing claims. The racy namespace-holder drill test (`setsid` fork, orphan sleeps) was fixed in the same commit.

GPU job 030 on Omniverse2 ran learning-19 (49/49), learning2-5 (63/63) and learning3-2 (14/14). Its learning gate passed, so the job started the 3 registered runs on test set 2 (GPIOA and CRC, split `48207f1`). The runs were identical: 12/12 seeded defects flagged (11 on target, 1 off target, 0 missed), 2/2 clean baselines falsely rejected, 0 empty inspections, truthful preflight FAIL on CRC. Details and the causes are in the [stepwise-inspector README](../../evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md). [KI-014-003](../../evidence/014-durable-local-autonomy/known-issues.md) stays OPEN, and test set 2 is now spent.

DA-AT-055 expects complete registered runs with honest rates and sets no rate threshold. `verify_calibration.py` checks that protocol for both calibrations from the published records (47 checks PASS at `291a1ff`; a tampered copy fails). DA-T055 is ticked with record `DA014-calibration-t2` (29/58). `verify_handoff.py` now also accepts `PASS_LIVE_PROTOCOL`.

## 2026-10-27: main merged into feat/014; DA-T029 at the merged candidate

`247562c` merges main `38e2740` (Feature 015 ST driver benchmark, 54 commits) into the feature branch. The 16 conflict hunks in 10 AFO and policy files were resolved so both features keep their behaviour; the merge commit lists each one, and one behaviour change is for the owner's review: AFO recovery of delivered code now resumes its validated phases (Feature 012), where main started a fresh work order. The two inherited failures (KI-014-005) failed only under `run_full_inherited.py`'s private empty state and were fixed test-only in `1e2fd46`. The auxiliary run then found a raw crash when freezing the uncatalogued `targeted` stage, so `20650af` makes it refuse with a reason.

Exact `20650af`, clean dedicated worktree: whole inherited suite **215 files, 1,840 tests, 0 failures, 0 errors**, 49 skipped with their reasons (the runner reports PARTIAL only because `test_t050_t051_docs_status` rewrites a generated timestamp); core **645 passed**, 1 skipped; release **13/13**; history replay and transient-systemd semantics PASS; every stage dry-run blocked as designed; independent CRE **REJECTED / PROTECTED_PATH_CHANGE** (retained, KI-014-010). DA-T029 is ticked with record `DA014-regression` (30/58); KI-014-005 is RESOLVED.

## 2026-10-27: learning set 4, new ST LL drivers, handover to Codex

GPU job 040 on `e0c020d`: learning sets 1–3 49/49, 63/63, 14/14; learning set 4 (the spent held-out pair) 13/14 with
both clean baselines accepted (learning data; KI-014-003 stays OPEN). The owner froze inspector development. WWDG,
RNG and LPTIM1 ST LL drivers were onboarded (`74c3aa4`, `60fccfd`, `4b71e6f`; Renode models smoke-tested in real
Renode), the owner set ASIL B (OD-2026-10-27-01, `de54734`), and unsigned SSA-STC-001/TAA-STC-001 v0.1 drafts were
committed (`9a88fbc`). GPU job 050 started the frozen st3 driver runs on Omniverse2 at 08:13 UTC (inputs verified,
peripheral tests 12 passed); its results are collected by the next engineer (`HANDOVER-CODEX.md`).

## Static checks

`python specs/014-durable-local-autonomy/validate_spec.py`, `python specs/014-durable-local-autonomy/contracts/validate_contracts.py` and `python tests/spec/validate_design.py` validate documentation/contracts and registry/design consistency only. The 58 requirements/tasks/acceptance mappings, six Feature 014 schemas and 38 structural fixtures retain their design validation. These checks cannot satisfy native capability, product or availability acceptance.

## 2026-10-27: Codex resumes; job 050 collected

The completed remote job 050 (08:13:13–08:19:24 UTC) ran all three frozen ST LL
cases at clean `9a88fbc5b28864e45917cdc77f7e6ab9c9f59825`: **0/3 READY, 3/3 BLOCKED
at SWE.1**, 59 gaps each. Repeated deterministic output rejection is recorded as
KI-014-029. Local-provider/digest/isolation/package-sealing verification passed;
that does not imply product acceptance. [Sanitized results](../../evidence/014-durable-local-autonomy/st3-driver-runs/summary.json)
retain native IDs, case denominator, request/token/energy measurements and package
hashes. Collection is read-only, no new inference or retry. No task was ticked.
Inspector development stays frozen; safety drafts remain unsigned/unregistered.

## 2026-10-27: initial independent operational observer

Source **`c72992ad1fe7a16fdbaa4850af5f6ccc66653994`**, clean dedicated worktree:
core **662 passed, 11 skipped, 0 failures/errors** (504.886 s); release **13/13**
(8.980 s). The 11 skip reasons are retained: eight missing historical workspaces,
one disabled live-Fabro test and two absent owner-only permission fixtures. The
last two were then exercised with a private nonsecret 0600 sentinel: **2/2 PASS**.
This is supplemental coverage, not a second independent whole-suite cohort.

The new read-only observer binds its source, isolated endpoints, mount, input plan
and artifacts to the campaign; collects bounded SQLite/unit/health/intent facts
outside the controller; recomputes signal-fault restoration and accounting checks;
and refuses handwritten recovery verdicts. HTTP redirects/proxies, out-of-root
artifacts, corrupted/truncated state, clock gaps and verdict tampering are covered.
It is **partial tooling**, not full DA-T052: host intervention auditing, other
fault-class exposure fixtures and an independent oracle for READY remain required.
Missing facts stay UNKNOWN; no operational campaign can pass from those omissions.

`run_auxiliary_current.py` on that exact candidate: offline history replay and
seven isolated local systemd cases PASS; stage preparation remains blocked on its
real prerequisites; independent CRE **REJECTED / PROTECTED_PATH_CHANGE**, retained.
The full inherited 1,840-test suite was not repeated on this narrow increment;
its previous clean `20650af` evidence remains distinct. Static spec/contracts,
14 design checks and handoff reconciliation pass separately (documentation only).

[Exact commands, JUnit, skipped reasons and hashes](../../evidence/014-durable-local-autonomy/operational-observer-c72992a/summary.json)
and task-style record `evidence/v0.4/runs/DA014-operational-observer/latest.json`.
No task checkbox changed (30/58); no source deployment, new Qwen request, pilot
retry, owner signature or inspector development was performed. The three recorded
pilot author diagnostics identify unsupported register-I/O effects and invalid
proposals; no correctness gate was relaxed to emit partial artifacts as accepted.

## 2026-10-27: bounded remote engineering diagnosis while local regression runs

At the owner's request, Omniverse2's existing serial GPU queue ran a separate
read-only ST3 engineering study on the clean remote source `9a88fbc`. It made
**3 requests**, 15,803 prompt and 3,498 output tokens. A complete-context preflight
refused the second packet before inference; coherent register-group repartition
resumed the same study with prior expenditure and the three-call limit retained.
The initial failed queue invocation remains evidence. Total elapsed wall was
144.122 seconds; actual request wall was 24.004 seconds.

Two proposals had valid references. LPTIM's invented diagnostic ID failed the
reference check. Pinned SafeC checks independently rejected three selected
WWDG/RNG suggestions as UNSUPPORTED; an isolated LPTIM read passed without
establishing the original clearing requirement or a complete driver. Existing
LessonStore APIs durably captured eight real phase outcomes and dispositions
(seven DEFERRED_BUDGET, one NO_NEW_LESSON); no lessons were qualified/promoted,
no repair incident invented and no benefit measured. [Sanitized study evidence](../../evidence/014-durable-local-autonomy/st3-diagnosis-study/summary.json)
retains source/packet/proposal hashes, complete-context accounting and engine
verdicts. Raw model prose and vendor data remain private. This study is not native
AFO recovery qualification, a driver retry, a new held-out cohort or inspector
calibration. Inspector development and all original failed pilot evidence remain
unchanged. No task was ticked.


## 2026-10-27: complete fault-catalogue observer predicates and bounded capture

Exact source **`c86d5773ff7238cb2195a2f1ec0484dbdfa24ec3`**, clean start/end:
**712 core PASS, 11 SKIP, zero failures/errors** (673.428 s), release **13/13 PASS**
(11.194 s). The two missing 0600 permission fixtures were separately exercised
with a private nonsecret sentinel: **2/2 PASS**. Other skips: eight unavailable
historical workspaces and one disabled optional live-Fabro test. [Exact commands,
JUnit and hashes](../../evidence/014-durable-local-autonomy/operational-observer-c86d577/summary.json).

The observer now derives exposure/restoration for thirteen external fixture
classes alongside the three existing signal recipes, covering the full sixteen
case catalogue. Predicates require actual queue/order/attempt, boot, unit, intent,
dependency and heartbeat transitions. Later terminal status cannot replace native
liveness; shutdown settles before effective stop, then rejects new identities.
The manifest must contain the complete fault catalogue and finite declared
resource/timing bounds. Single-read hash/parse binding, cumulative read-only SQLite
byte bounds, typed accounting and trace limits preserve UNKNOWN on incomplete
facts. Tests include positive/negative fault timelines, real private SQLite/HTTP
fixtures, stale/contradictory facts and reduced-manifest refusals.

Exact-source history replay and seven isolated local systemd checks PASS.
Independent CRE **REJECTED/PROTECTED_PATH_CHANGE**, preserved without waiver.
Static validation passes separately: 58 requirement/task/acceptance mappings,
six schemas/38 fixtures, 14 design tests, handoff 30/58, and selected changed-module
Ruff checks. These are not native or elapsed-time qualification. Full inherited
1,840-test regression was not repeated here; its prior `20650af` record remains.

DA-T026/046/049/050/052 remain unchecked. Host intervention audit is still not
implemented/integrated; an independent READY package oracle is not integrated.
Omniverse2 also lacks the approved host-admin reboot/authoritative-mount-loss
fixture window; actual work/fault campaigns and their 24/72/168 hours were not run.
The current observer deliberately returns UNKNOWN for missing audit/oracle facts,
so it cannot silently pass a campaign. No deployment or automatic merge occurred.

## 2026-10-27: independent native work/READY audit binding and continuity

Exact tested source **`08cc4326063074878b876c4aec36b9062fbde970`**: clean start/end,
**235 affected checks PASS, one historical HAL-r154 workspace SKIP, zero failures**
(26.223 s); release **13/13 PASS** (9.226 s). [Exact commands, JUnit, skip and hashes](../../evidence/014-durable-local-autonomy/operational-work-08cc432/summary.json).
The previous `ccd10f0` observation-consumption record is retained separately,
including its subsequently corrected historical-work-count limitation.

The new `afo/operational_work.py` reuses `qualification_capture`'s existing
independent audit, binds its exact native observation to the campaign and captured
order/latest-attempt/mission/nonce/native/request identities, and requires actual
captured quiescence/released capacity. READY requires all six native SWE gates and
the sealed package result plus the independent correctness audit. A BLOCKED job
can be independently verified as an outcome without becoming product success.
Missing or edited audits, same-model producer labels, changed oracle bytes and
missing/extra gate sets cannot turn into accepted evidence. Request identities
are explicit; a genuine zero-request native outcome differs from missing telemetry.

The existing Store now provides `ReadSnapshot`: one bounded read-only SQLite
transaction, no migrations or database creation, SQL mutation refusal, and row,
byte and deadline bounds. Tests use actual SQLite writer/read concurrency and
verify the database remains unchanged. The observer's executable `product` and
`work` commands bound workspace/archive reads and refuse FIFOs, symlinks, live or
held executions, out-of-root paths and late publication. They execute no model,
compiler, job dispatch or service change. Source hashes are frozen in the plan.

Campaign reporting recomputes work and fault evidence. Legacy success/continuity
booleans alone no longer count. It binds the actual stage/window/manifest,
keeps missing or contradictory clocks/probes UNKNOWN and unavailable in the gross
denominator, and derives later job processing/post-campaign continuity from source
records. Work exposure requires an attempt created during the window or native
activity observed there under fresh reconciliation. Re-reading historical terminal
work cannot inflate the real-work counter; historical outcome proofs remain usable
for READY auditing. Unknown timing stays unknown.

Exact-source history replay and seven isolated local systemd cases PASS.
Independent CRE remains **REJECTED / PROTECTED_PATH_CHANGE**, without waiver.
Spec/contracts (58 mappings, six schemas, 38 structural fixtures), 14 static design
checks, handoff reconciliation and changed-module/new-test Ruff checks PASS
separately. The full 712-pass core run remains at `c86d577`; the full inherited
1,840-test record remains at `20650af`. Neither cohort is claimed on this revision.

This advances DA-T026/052 tooling; no formal task was ticked (30/58). The independent
product audit consumer is implemented, but genuine product-correctness oracle
production/evidence for this candidate is still unavailable. Host intervention
audit production/integration is still incomplete. The actual authorized host
reboot/mount-loss fixtures, native workload/fault exposure and 24/72/168-hour
campaigns have not run. Current UNKNOWN host-audit facts still prevent campaign
PASS. No additional Qwen request, deployment, inspector tuning or merge occurred.

## 2026-10-27: bounded kernel-audit source capture and actual host prerequisites

Exact clean source **`2928a9377c3ef96aab7cef7cf94355b96bdaa381`**:
**273 affected PASS, one historical HAL-r154 workspace SKIP, zero failures/errors**
(27.347 s); release **13/13 PASS** (10.301 s). [Exact commands, JUnit and hashes](../../evidence/014-durable-local-autonomy/host-audit-2928a93/summary.json).
The new leaf adapter/parser has 38 tests including real subprocess resource/output
limits. The earlier seven local systemd/history checks remain at `08cc432`; they
were not repeated for this unused-by-runtime leaf. Current independent CRE again
**REJECTED / PROTECTED_PATH_CHANGE**, retained without waiver. Static spec/contracts,
handoff and new-source/test Ruff checks pass separately.

`afo/host_audit.py` exports bounded read-only native kernel status/rule/log facts,
not a complete host intervention verdict. Source capture binds a protected,
root-owned regular source prefix; compound identities, duplicate/truncated records,
path-item consistency, privacy exclusions, missing counters, historical losses,
counter resets, daemon/policy/boot/clock changes and input bounds are tested.
The implementation executes no audit configuration, package installation, counter
reset, service mutation or model call. Global intervention count remains UNKNOWN.

On Omniverse2, a clean isolated qualification checkout at this exact source ran
`host_audit preflight`: **BLOCKED / exit 2**, with durable invocation/exit record.
Auditctl/ausearch are unavailable, auditd is inactive, and noninteractive sudo
listing returned 1. This is native prerequisite evidence, not runtime qualification.
The existing `repo-b309039`, services, GPU queue and model setup were preserved;
no shared-factory source deployment, grant renewal or inference occurred.

Source work remains for continuous/rotation-safe segments, systemd-bus capture,
authenticated-control/actor correlation and complete intervention-source replay.
The current kernel counter comparison is not a complete coverage verifier and
must not be used to set the campaign's unplanned-intervention count to zero.
The actual host setup/privileged fault window, independent product oracle evidence
and full native campaigns remain unavailable/unrun. No task was ticked (30/58);
product success, learning benefit, availability and self-healing remain separate
unproven qualifications.


## 2026-10-27: native bus visibility source and measured permission boundaries

Exact clean source **`fbd8bc89967b68ed4e99e4c63fe12784f135e62f`**:
**318 affected PASS / one historical HAL-r154 workspace SKIP / zero failures or
errors** (31.083 s); release **13 PASS** (8.794 s). [Commands, JUnit, source
profiles and native receipts](../../evidence/014-durable-local-autonomy/host-bus-fbd8bc8/summary.json).
The 83 host/bus tests include isolated native D-Bus Manager and Unit calls, unknown
actor preservation, exact third-party call/reply visibility, malformed/truncated
headers, monitor clean exit/fallback, child cleanup, bytes/messages/duration
bounds, source freezing and response-body injection/privacy. No shared service
was exercised by those isolated tests. Spec/contracts (58 mappings, six schemas,
38 structural fixtures), 14 design checks, handoff 30/58 and selected Ruff pass
separately. Current independent CRE remains **REJECTED/PROTECTED_PATH_CHANGE**.
Earlier full-core/inherited/systemd cohorts retain their original revisions.

`bus_audit` collects the native header-only profile and exact stream hash, not
classic unescaped message bodies. It proves BecomeMonitor via loss of the
monitor's acquired unique name and both harmless GetId query/reply boundaries,
binds the systemd owner at both ends and detects ownership/disconnect/clock
uncertainty. Optional frozen bus scopes extend the existing host capture; legacy
plans continue working. The finite source never supplies a global intervention
count or clears continuous coverage/authentication prerequisites.

Actual Omniverse2 probes from isolated clean
`/mnt/data/forge-c/inspector-014-b309039/host-bus-fbd8bc8/repo`:
**user bus visibility PASS/exit 0**; **system bus BLOCKED/exit 2** (BecomeMonitor
and boundary visibility not proven; fallback diagnostics); **kernel preflight
BLOCKED/exit 2** (status unavailable). Native invocations preserve source SHA,
clean start/end, command, exit, clocks and artifact hashes. No raw body, private
credential, model call, service mutation, grant renewal or factory deployment.
KI-014-030 distinguishes actual host prerequisites from incomplete software.

Formal task count stays **30/58**. Remaining software includes continuous and
rotation-safe sources, authenticated-control/actor correlation and complete
source-derived intervention verification. Genuine product oracle production,
the approved host fault window and elapsed 24/72/168-hour campaigns remain unrun;
product success, learning benefit and operational availability are unproven.


## 2026-10-27: caller/control provenance, transactional intent effects and useful bounded Qwen assistance

Latest exact source **`7e1abb2849dfc6272a00c8b56f6be7a8ea0588d1`** (bus-name
fix `818ab90`, oracle-test clarification `91f5ef4`, control source `7e1abb2`).
The original 899-case core invocation had **846 PASS / 11 SKIP / 42 setup errors**,
exit 1; all 42 errors were missing ignored ST documents in its worktree. No source
assertion failed. A worktree with all 22 document hashes verified then passed the
complete **45-case brownfield** file; the **two permission cases** also passed with
an explicit private canary. The source-bound JUnit identity reconciliation is
**890 PASS / 9 SKIP / zero open failures/errors across 899 unique cases**, not a
single green full invocation. Both failed and successful invocations remain in
Git. [Commands, artifacts and executable reconciliation](../../evidence/014-durable-local-autonomy/control-provenance-7e1abb2/summary.json).

Release **13 PASS**; real Omniverse2 isolated control/bus tests **62 PASS** and
finite user-bus visibility **PASS/exit 0**. History replay and all **seven isolated
local systemd cases PASS** at this source. Current CRE remains
**REJECTED/PROTECTED_PATH_CHANGE**. Spec/contracts, 14 design checks, handoff and
changed-source/test Ruff PASS separately; full 1,840-test inherited cohort was
not rerun here. Remaining skips are unavailable historical workspaces and the
explicitly disabled live-Fabro validation.

The existing CLI/dashboard authentication boundary now contributes a sanitized
context to Intent and the existing lifecycle/action ledger. It binds epoch/mode,
request/source hashes, process boot/start/namespace facts, UID mapping and bearer
fingerprint without credentials, actor/reason text or arbitrary caller fields.
The same intent lock spans one database transaction for both controls and all
receipt/action rows. A pinned-old-function counterexample demonstrates stale
resume effects contradicting a newer stop; the fixed concurrency case passes.
Existing admission already honored STOPPED intent, so no unsafe service restart
is inferred. SQL failure retains durable stop fencing; missing process metadata
stays UNKNOWN and cannot prevent stop. Legacy control callers remain compatible.
KI-014-031 is resolved deterministically; KI-014-030 retains incomplete independent
audit ingestion/correlation and source coverage.

The requested [external Qwen helper study](../../evidence/014-durable-local-autonomy/qwen-bus-query-review-20261027/summary.json)
used the existing GPU queue and single-inflight gateway on Omniverse2: **one client
and upstream request**, 1,819 input + 793 output tokens, 9.4334 s request wall.
Total study wall 249.612356 s includes an initial zero-call UID-namespace preflight
failure and its corrected continuation; the same one-call accounting was kept.
The response was schema-valid but failed literal source references. A ceiling
complaint was unsupported. A nonnumeric-name lead was independently checked
against the primary D-Bus contract/native library, reproduced and externally
fixed. Native library permissiveness on degenerate names is retained as an oracle
limit; normative negative fixtures remain authoritative. Exact serialized-context
hash replay passes without another inference call. Four factual experiences have
three DEFERRED_BUDGET and one NO_NEW_LESSON dispositions, zero qualified lessons.
No measured learning benefit, role competence or autonomous repair is claimed.
The study's call budget is spent; do not retry it under a new name.

Formal progress remains **30/58**, no task tick or ledger/CRLF rebaseline. Complete
observer ingestion, native actor/control correlation, continuous/rotation-safe
capture and full source-derived intervention verification remain software work.
Kernel/system-bus prerequisites, genuine product oracle evidence, the approved
external fault window and elapsed 24/72/168-hour campaigns remain unrun. No
persistent deployment, promotion, inspector tuning, owner safety signature or
merge occurred. Product success/learning benefit/availability remain separate and
unproven.


## 2026-10-27: frozen application-control source ingestion and replay

Exact clean source **`2246a58b0a36ed4627e44462e4ca3b9fb0bb8097`**:
**380 affected PASS / one historical HAL-r154 workspace SKIP / zero errors or
failures** (34.483 s), **13 release PASS** (9.214 s). Actual isolated Omniverse2
control/observer tests **83 PASS**, zero skips/errors (123.011 s). [Exact commands,
clean revision receipts, JUnit and hashes](../../evidence/014-durable-local-autonomy/control-ingestion-2246a58/summary.json).
Current independent CRE still **REJECTED/PROTECTED_PATH_CHANGE**. Static spec and
contracts (58 mappings, six schemas, 38 fixtures), 14 design checks, handoff and
new-source/test Ruff PASS separately. The broader reconciled 899-case cohort,
history and seven systemd cases remain at `7e1abb2`; unchanged runtime service
paths were not rerun for this observer-only increment. Full inherited 1,840-test
cohort remains at `20650af`, not claimed on this source.

`afo/control_observation.py` is now integrated into the existing external observer.
An optional frozen `control_sources` object binds the reader and expected intent/
CLI/dashboard source hashes. Legacy plans can omit it. The reader validates exact
record/context fields and hashes before exporting event JSON and binds applied
controls to real action rows in the same SQLite read transaction. Actual writes
during observation, missing/mutated/duplicated rows, source mismatch, arbitrary
fields, credentials, bad UID maps, malformed values, replayed flags and publication
bounds are tested. Unsupported/corrupt sources preserve their hashes and UNKNOWN
reason without leaking arbitrary source text. Historical producers can remain
explicitly unmatched, not reclassified as authenticated.

UID mapping is relative to the parent namespace; no host-principal inference is
made. Provenance is exported as `intent_control_source`, separate from semantic
mode/epoch/stop fields. A tested recovery-counter update changes source bytes
without changing operator intent or breaking existing restoration comparisons.
Custom action text is hashed; invalid paused/draining or stop-boolean values are
not exported. Complete serialized observation size is bounded before publication.
Loading captured samples recomputes context/source/action facts rather than
trusting supplied match flags.

This completes application-source ingestion only. Native actor/control/write/
service correlation, continuous segmented/rotation-safe sources and full
all-channel intervention verification remain software work; intervention count
stays UNKNOWN. Genuine product oracle evidence and authorized external host
fixtures/campaigns remain required. No new Qwen request, grant renewal, factory
source activation, inspector change, merge or task checkbox. Formal **30/58** and
ledger source_revision/CRLF remain unchanged. Product success, learning benefit,
24/72/168-hour operation and the 30-day SLO remain unproven.


## 2026-10-27: protected audit segments and executable byte-prefix replay

Exact tested source `c38158cd687ac974056296662aa48b46e2fcdeca`: **434 affected
PASS / 1 historical HAL-r154 SKIP / zero failures or errors**, 38.832 s; **13
release PASS**, 9.124 s. Isolated Omniverse2 segment/kernel/bus source tests:
**152 PASS**, 46.871 s. [Commands, raw JUnit/logs and hashes](../../evidence/014-durable-local-autonomy/audit-segments-c38158c/summary.json).

`host_audit capture --previous-ref` and `verify-segments --segment-refs` extend the
existing frozen observer/host plans and immutable qualification evidence. They
provide bounded capture/resume and adjacent-prefix replay with retained-file
identity/hashes, rolling anchors, parent/sequence bindings and descriptor-derived
single-rotation handoff checks. Failed observations do not advance the cursor or
erase history. Negative cases cover gaps, reordering, duplicates, malformed
references, changed/truncated/deleted history, late retired writes, false writer
handoffs, daemon PID mismatch, metadata/source budgets and privacy. See the
[executable usage and limits](audit-source-capture.md).

Ownership/UID protection is deliberately synthetic in deterministic fixtures;
actual child-process descriptors and file IO are tested. A replayed byte prefix
is not a complete compound-event/time/boot/host observation. Missed multiple
rotations, missing retained history or aggregate bounds refuse. Batched continuous
replay and complete compound-event replay remain unfinished. No global
intervention count is inferred; it stays UNKNOWN.

The same-revision **actual Omniverse2 preflight BLOCKED / exit 2** records
`AUDITCTL_UNAVAILABLE`, `KERNEL_AUDIT_STATUS_UNAVAILABLE`,
`SYSTEMD_BUS_AUDIT_COVERAGE_REQUIRED`, `AUTHENTICATED_CONTROL_CORRELATION_REQUIRED`.
These host prerequisites and incomplete correlation are separate from the source
tests. No rule, privilege, daemon, shared service or persistent deployment changed.
Independent CRE remains **REJECTED / PROTECTED_PATH_CHANGE**. Static spec/contracts,
fourteen design checks, handover and Ruff pass separately; no runtime qualification
is inferred from static validation.

Formal acceptance stays **30/58**, no new checkbox or ledger rebaseline. Prior
broader reconciled 899-case core/systemd/history checks stay at 7e1abb2 and the
full inherited 1840-test cohort at 20650af. No new model requests; spent studies
remain spent. Product success, learning benefit, 24/72/168-hour operational campaigns
and the thirty-day SLO remain unproven. Inspector freeze/owner signing boundaries
and the seventeen known-issues-only omissions remain unchanged.


## 2026-10-27: incremental selected-event replay on verified source segments

Exact clean source `6b4166832ace78e791a5cb14c0a2ec8fc675648d`: **465 affected
PASS / 1 historical HAL-r154 SKIP / zero failures/errors**, 38.570 s; **13 release
PASS**, 9.086 s. Actual isolated Omniverse2 event/segment/kernel/bus source tests:
**183 PASS**, 59.782 s. [Commands, JUnit/logs, preflight and hashes](../../evidence/014-durable-local-autonomy/event-replay-6b41668/summary.json).

One bounded kernel-fact parser now handles legacy buffers and incremental ranges.
Verified bytes are fed once; no second source pass or new persistence authority.
Interleaved identities, partial UTF-8/line bytes and compound records survive
capture and retained rotation boundaries. The new output binds input byte/hash
and parser source, selected whitelisted fields, integrity records and duplicates.
A native ENRICHED compatibility defect is fixed: Python `splitlines()` previously
split 0x1D enrichment into invalid separate records. Private bodies remain excluded.

Selected events need PATH index coverage and an observed PROCTITLE/EOE boundary;
EOF does not force completion. Pending compound records, orphan groups and partial
lines stay explicit. Malformed input or changed/unbound recorded boot produces
blocked event facts (`null`), independently of retained byte-prefix replay. Byte,
line, group, unique-record and final serialized-output bounds preserve uncertainty.
Deterministic tests include independent expected record hashes, every-byte UTF-8
splits, interleaving/duplicates, native separators, pending records, malformed
sources, cumulative bounds, boot change, single-pass feed and retained rotation.
Root/UID protection is synthetic; actual child-process/file IO is tested.

[Tool usage and scope](audit-source-capture.md): this is selected-record replay,
not full native payload completeness, independent host authentication or continuous
window/boot/loss coverage. Native timeout inference and qualified batched continuous
verification remain unfinished, alongside actor/control/write/service correlation.
Global interventions stay UNKNOWN. Same-source actual remote preflight remains
**BLOCKED / exit 2**, `AUDITCTL_UNAVAILABLE`, kernel status unavailable, continuous
bus coverage and authenticated-control correlation required.

Independent CRE remains **REJECTED / PROTECTED_PATH_CHANGE**. Static spec/contracts,
fourteen design checks, handover and Ruff pass separately, with no runtime claim.
Formal **30/58** stays unchanged; no new task or ledger baseline. Broader reconciled
899-case core/systemd/history remain at 7e1abb2; full inherited 1840 at 20650af. No
new model request, deployment, shared-service mutation, grant/mission reset or merge.
Product success, learning benefit, operational campaigns and the thirty-day SLO
remain unproven. Existing owner omissions/freeze/signing decisions stay in force.


## 2026-10-27: owner development signature policy, A1 revalidation and remote Qwen assistance

Owner **OD-2026-10-27-02** explicitly defers SSA/TAA signatures during Forge-C
development. Source `1b32534eecfaa0481d4eb00ebf30fe478b42cb01` binds this policy
and unchanged formal-policy hashes into new DEVELOPMENT work orders and brownfield
identity. The finalizer defers exactly the two document files and seals explicit
policy/deferral records. ASIL, all other quality checks and absence of safety
approval remain. FORMAL_REVIEW and legacy orders use strict policies; malformed,
changed or revoked bindings produce a blocking finding. Drafts remain unsigned.
[Policy behavior and owner quote](development-safety-policy.md).

Exact clean source: **1232 core/assurance PASS / 15 SKIP / zero failures or errors**,
580.655 s; release **13 PASS**, 9.066 s. Final Omniverse2 **49 PASS**, 47.171 s.
Native initial 44 PASS/5 FAIL (missing tool/data-root settings) and second 48
PASS/1 FAIL (directory used as Fabro binary) are retained. The final environment
uses the existing executable/PlantUML/LLVM with private state/home/archives. No
source/test gate was weakened to pass. Total native test time including failures
119.653 s. Skips list exact historical workspace/RM/archive, disabled live Fabro
and two OS-identity fixture prerequisites. [Raw attempts, commands and hashes](../../evidence/014-durable-local-autonomy/development-safety-1b32534/summary.json).

Synthetic READY fixture results prove mechanical packaging behavior only, not real
driver success or safety approval. Native kernel-audit preflight remains BLOCKED
(auditctl absent, continuous bus/control correlation missing). CRE retains
REJECTED/PROTECTED_PATH_CHANGE. Static spec/contracts, design, handover and Ruff
pass separately. Last full inherited 1840 cohort remains 20650af; this source's
expanded core/assurance cohort has 1247 cases. No deployment or automatic merge.

**Backlog A1:** Job 050 was already terminal. Existing 0/3 READY, three SWE.1 blocks,
59 gaps each, source/package hashes and all 76 requests / 324810 input / 51810
output tokens are revalidated against read-only remote artifacts. The published
metadata secret-pattern scan and executable hash/count replay pass; an altered-count
private copy is refused. [Terminal recheck](../../evidence/014-durable-local-autonomy/st3-driver-runs/publication-recheck-20261027.json).
No live status/scorecard capture is invented; KI-014-018 rechecked and DA-T018 stays
unticked. The actual SWE.1 failures still need engineering fixes; development
signature deferral cannot repair them.

Owner requested useful remote Qwen work. New distinct bounded job 080 reviewed the
new policy source: **one upstream request**, 2574 input + 531 output tokens,
7912.9 ms. Reference check FAIL (one exact quote, one inexact); both suggestions
depend on hypothetical changes to protected fixed policies outside the input
contract. Actual baseline replay PASS with zero actionable findings/code changes.
Existing LessonStore APIs retain factual review and independent-check dispositions
(DEFERRED_BUDGET, NO_NEW_LESSON), no invented repair incident, zero promoted lessons
or measured benefit. [Sanitized study/accounting](../../evidence/014-durable-local-autonomy/qwen-development-safety-review-1b32534/summary.json).
This one-call budget is SPENT; older ST3/bus-study budgets remain SPENT. It does not
qualify a model role or prove autonomous self-healing. Final native qualification
ran after the Qwen request completed; no competing inference or shared-service
mutation was introduced.

Formal **30/58** remains unchanged, no task/ledger baseline change. Product, learning
benefit and actual 24/72/168-hour campaigns remain unproven. Continue backlog A2's
independent observer, A3 comparison tooling, then A4 clean-worktree housekeeping.
Owner-signature deferral is specific to development SSA/TAA; the remaining signing,
authority, inspector-freeze and parked-case decisions remain in force.


## 2026-10-27 — crash-replayable collection, Qwen authoring and controlled reports

Runtime increments: collector `75d4bdc19dc95f1fdc469326adb3dd2c1c0e5632`, controlled
reporting `d9d70e16523f1b928fd2d5f9ff265594e8f266f8`. Existing soak, frozen observer,
host segment reader, qualification identities and independent audit producer reused.
No scheduler, memory store, inference authority or production activation introduced.

Exact clean collector checks: 521 PASS / 1 SKIP affected (41.437 s), release 13 PASS
(9.319 s); isolated Omniverse2 194 PASS (386.299 s). Native preflight exits 2/BLOCKED:
KERNEL_AUDIT_STATUS_UNAVAILABLE, SYSTEMD_BUS_AUDIT_COVERAGE_REQUIRED,
AUTHENTICATED_CONTROL_CORRELATION_REQUIRED. Global interventions remain unknown.
Latest exact clean d9d70e1 affected 541 PASS / 1 SKIP (49.069 s), release 13 PASS
(9.047 s). Skip is the deliberately disabled live Fabro fixture. Exact commands,
clean revisions, raw XML/logs and hashes are in the two increment folders' invocation
and summary JSON. Initial WIP observer failure (changed refusal code) and comparison
fixture failure (stale expected /99 after reducing fixture to two cases) are retained;
fixes preserve inherited contracts and do not weaken gates.

The collector serializes existing soak writers, records bounded immutable attempts,
reuses captures/receipts after crashes, rejects partial/mixed histories, retains
host failure/cursor chains and replays original sources in reports. Test clocks and
probe fixtures are synthetic. Host-wide control/write/service correlation, native
full-window evidence and batched continuation beyond 128 MiB remain unfinished.
Read-only preparation confirms no durable AFO product binding exists for any Job050
workspace. Those failed normal workorders are not relabeled as campaign jobs; no
operation manifest or grants were created/renewed. Host-admin and fault-window
prerequisites are recorded exactly. A2 remains IN_PROGRESS.

A3's controlled report generator is tested. It requires one declared factor,
unchanged source/cases/prompts/oracles/workload/admission/measurement/quality gates,
frozen candidate registration, actual observed settings and independently audited
outcomes/costs. All failed attempts and learning overhead count. Missing totals are
null; no model self-assessment qualifies. Recorded-run suitability assessment found
no qualifying pair; live DA-AT-028 remains NOT_RUN. RCC success is no prerequisite.

New external Qwen authoring job 081 ran only on Omniverse2 through the existing
one-admitted gateway, versioned role and structured packet: one client/upstream call,
996 input + 579 output tokens, 7513 ms. Complete serialized context accounting,
actual meter delta, terminal queue status and learning dispositions retained. Raw
validator candidate accepted integer subclasses, contrary to the strict contract;
manual independent adaptation corrected numeric types and explicitly checked hash
strings before integration/testing. Raw candidate contract FAIL is retained, not
claimed as self-healing or role qualification. Two factual learning dispositions are
DEFERRED_BUDGET, zero qualified lessons and no measured benefit. One-call budget is
SPENT; previous studies remain SPENT. No new inspector tuning, driver retry or
baseline exposure occurred.

A4 removed exactly the four owner-listed detached clean worktrees after no-live-use
checks and verified backups of all ignored files. Private backups remain on loop10;
public cleanup record reports 35.9 GiB available at that time.

Evidence: `operational-collection-75d4bdc/`, `configuration-comparison-d9d70e1/`,
`qwen-collection-validator-008c3e8/`, `worktree-cleanup-20261027.json` under the
Feature014 evidence directory. Static checks are documentation/contract validation,
separate from runtime tests and native qualification. No formal task tick (30/58),
ledger-source change, live comparison, product/learning/availability success,
protected-source promotion, grant renewal, merge or deployment is claimed.


## 2026-10-27 — WWDG required SafeC capability limit, zero model cost

After the owner questioned outcome progress, further uncommitted observer-window
work was parked. The unchanged full WWDG scope was checked directly against the
pinned native SafeC engine on Omniverse2. Twelve minimal required operation forms:
9 UNSUPPORTED, 3 ordinary reads PASS plus independent Python contract derivation.
The profile cannot represent rs or rc_w0 access, nor RMW beside rs. This is a
specific verification-capability ceiling; no conclusion that every model answer
was correct is drawn. Another model response cannot add missing engine semantics.

Full-scope phase 14.055950 s; initial four-intent phase 2.243598 s; 16 engine
invocations total, zero Qwen requests and no new product attempt. SDK source
75d4bdc, unchanged pinned engine cf3b01b/binary hash in the evidence. Existing
request/domain hashes bind the original source. Raw vendor domains, engine outputs
and private source stay private. Sanitized checks/accounting and factual learning
dispositions are published in wwdg-required-capability-20261027. No qualified
lesson, measured benefit, semantic change, gate waiver or budget reset.

Concrete proposed next scope: a versioned rs/rc_w0 SafeC extension with compatible
Forge-C independent contract checks, legacy regressions and actual formal checks,
then one new bounded WWDG attempt under valid authority. The private SafeC AGENTS
requires confirmation for functional changes; the proposal does not authorize them
or reopen parked DA-T036. See wwdg-safec-unblock.md. Formal 30/58 unchanged.

## 2026-10-27 — approved opt-in WWDG capability extension

Owner explicitly approved “I - Approve the scoped SafeC/Forge-C extension”.
Only the relevant mandatory-operation preflight portion of parked DA-T036 is
reopened; the full task remains unticked. Formal ledger/source/CSV stay30/58.

Exact clean Forge-C a74baa91f15383012b997461c551b1e1c066e279:
256 affected PASS, one missing local SPI-state fixture SKIP, 433.012s.
Release/legacy quality/OSS gates29 PASS,9.822s. Omniverse2 new native bridge,
preflight and WWDG tests35 PASS,1.830s. Separate static spec (58 mappings),
contracts (six/38),14 design tests, handoff and Ruff PASS. Static validity is not
runtime, model or operational qualification.

New explicit register-io-0.2/domain3 and contract/oracle/obligations2 preserve
legacy schema/default behavior. Rust remains semantic authority; Python derives
accepted arithmetic, oracle cases and formal text independently. New WWDG work
orders freeze12 mandatory forms; actual pinned-engine preflight happens before
author packets/model calls, with finite60s/32form bounds and changed-scope refusal.
Actual source-timeout/engine failure remains distinct from capability absence.

Private semantic source c241a9a, opt-in register-io-v02 build, hash
d1df63cea412d672fbe042b1a2b0e31f5167cfd1ea21c717c4dfcbdf81e8ef72:
core31 PASS plus explicit actual CBMC formal run; bridge33 PASS each legacy/new.
Affected fmt/Clippy pass with warnings denied. Actual CBMC6.11.0 proves five
generated correct cases and rejects ten semantic/frame mutants within one-call
32-bit register-image assumptions. No arbitrary hardware/timing/concurrency claim.
Whole-private-workspace checks fail: inherited Linux CLI unused-mut lint and one
retained-evidence replay failure. No-fail-fast workspace at docs-only30bea77:
264 PASS/1 FAIL. S014-T008 remains unchecked; no golden is fabricated/auto-accepted.
Private draft PR4 retains these failures; only interfaces/counts/digests are public.

Native frozen WWDG domain:12/12 required forms pass versus prior9 UNSUPPORTED/3PASS.
All36 validation/oracle/obligation derivations survive independent materialization.
Unsafe values and profile mismatch controls reject. Final study accounting:
53 bridge calls,52 engine run requests,1 client domain-binding refusal,0 model calls,
0 product attempts. Original52-call harness completed the checks but failed while
capturing unsupported SUCCESS; separate reconciliation captured factual PASS and
NO_NEW_LESSON without redispatch. Additional correctly bound legacy-domain control
was evaluated and refused by the actual engine. All raw failed runs are retained.

Candidate WWDG-LL-v02-001 is prepared on Omniverse2 with original full scope,
frozen12form manifest and accepted ST target-compiler intake after PATH correction.
Its initial BUILD_NOT_RUN is retained. It is NOT_ADMITTED: available19 signed
protocol grants do not name it, cumulative continuation mission and explicit
isolated profile binding remain required. No grant renewal, historical mission
reset, default pin/service change, inspector tuning, deployment or automatic merge.
Original WWDG expenditure floor and later diagnosis uncertainty remain preserved.
No driver READY, author/inspection/maintenance qualification, self-healing,
learning-benefit, product benchmark or24/72/168-hour claim follows from this result.

Evidence/commands/versions/hashes:
evidence/014-durable-local-autonomy/wwdg-v02-a74baa9/.

Follow-up: nonfunctional private CLI cleanup3256cb6 now passes whole-workspace
fmt/Clippy with warnings denied. Exact3256cb6 no-fail-fast workspace264 PASS/1FAIL.
tools/check.py reaches and refuses retained-evidence replay.16 original raw
payload inputs are missing across eight retained cases; no matching original
available, no logs fabricated, no manifest changed or check skipped. Restore exact
recorded bytes to unblock. Candidate's fresh domain separately passed12 native
preflight contracts in7.460138s (12 additional engine requests,0 model calls);
its disposition is NO_NEW_LESSON. It remains NOT_ADMITTED.
