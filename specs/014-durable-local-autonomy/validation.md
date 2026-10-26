# Implementation and qualification status

Updated 2026-10-26 (Claude continuation). Exact runtime source candidate: `de324a3c8686f06be566d479ea1a2d9dac48c61a` (`5dc2df3`, `dddf00e` before it; see [2026-10-25 continuation](#2026-10-25-continuation-intake-fault-controls-and-preliminary-omniverse2-trials)); the `9891b59` evidence below is retained history. Later evidence/documentation commits do not qualify a different running deployment. Feature 014 remains stacked on PR #41; neither PR was merged or activated by this work.

The original authored specification and its three Feature 014 contracts are retained. `traceability.csv` is the immutable design-time NOT_IMPLEMENTED inventory used by the original specification checker. The dated [implementation matrix](implementation-status.csv) and [machine-readable evidence ledger](../../evidence/014-durable-local-autonomy/implementation-status.json) record all 52 implementation/acceptance dispositions. Checked tasks have passing evidence for their required deterministic scope. Native/live-containing tasks remain unchecked, even where their implementation and fixtures passed.

## Independent status axes

| Axis | Result |
|---|---|
| Runtime implementation | Verified core increments; native qualification tooling remains partial. Exact-revision core/release evidence is below. Wider inherited coverage uses separately recorded revisions; combined-ordering and optional/native limits remain explicit. |
| Actual Qwen/Fabro/gateway interoperability | PRELIMINARY live trial subsets on Omniverse2 (one isolated runtime per revision, 836ae49..dddf00e): intake, admission, native Fabro runs, gateway metering, typed incidents, wrapper closure and the four dispatch/liveness fault controls exercised; seven runtime defects found and fixed. Grammar-friendly wire schema raised schema-valid answers from 0/6 to 23/24. Not a completed campaign. |
| Diagnosis, author, inspector, maintenance capability | Diagnosis: PRELIMINARY FAIL for `qwen3.6:35b-a3b` (reasoning high, single constrained response): NEEDS_EVIDENCE chosen for evident conformance repairs across 5 positive cases × 4 prompt/interface variants; the NEEDS_EVIDENCE case correct. Owner-chosen reasoning-off variant (3de1a44): same decisions at ~1/3 of the tokens. `qwen3.8:27b-q8_0` (bcb8cae, reasoning none): same pattern, 6/6 NEEDS_EVIDENCE. Stepwise diagnosis (owner-requested split; three small grammar-constrained questions, deterministic assembly, unchanged broker; qwen3.6 reasoning off, a206c54): 93/95 trials of the frozen matrix observed == expected with all fault exposures matched (24 accepted repair plans); independent REFERENCE_HARNESS audit (dbcec39): 0 false successes, 0 duplicate effects, 0 authority escapes over 95 rows; official protocol report 93/100 correct, FAIL (2 misses, 5 trials blocked by the measured-alternative prerequisite). Fixes b7ce315/5dc2df3 (obligation enum, separate strategy question, cited-findings context within the frozen job envelope): fourth matrix 95/95 eligible correct, audit 0/0/0, official report no failures, INCOMPLETE 95/100 (5 trials blocked only by the measured-alternative prerequisite). Inspector (owner 2026-10-26 "Stepwise inspector in 014"): stepwise local SWE.1 inspector on Feature 011's learning set (7 holdouts x 7 cases): learning-11 (`8064062`) 48/49 correct, 42/42 seeded defects caught, 6/7 clean baselines passed ([evidence](../../evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md)); PRELIMINARY, the frozen test set (F011-T046) is not yet measured. Author, maintenance: NOT_RUN. No model family or nominal context setting implies role competence. |
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

## Static checks

`python specs/014-durable-local-autonomy/validate_spec.py`, `python specs/014-durable-local-autonomy/contracts/validate_contracts.py` and `python tests/spec/validate_design.py` validate documentation/contracts and registry/design consistency only. The 52 requirements/tasks/acceptance mappings, three Feature 014 schemas and 25 structural fixtures retain their design validation. These checks cannot satisfy native capability, product or availability acceptance.
