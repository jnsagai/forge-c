# Implementation and qualification status

Updated 2026-10-25. Exact runtime source candidate: `794e8d0e5b26fd24276ad1331f0ed90a7ecafe08`. Later evidence/documentation commits do not qualify a different running deployment. Feature 014 remains stacked on PR #41; neither PR was merged or activated by this work.

The original authored specification and its three Feature 014 contracts are retained. `traceability.csv` is the immutable design-time NOT_IMPLEMENTED inventory used by the original specification checker. The dated [implementation matrix](implementation-status.csv) and [machine-readable evidence ledger](../../evidence/014-durable-local-autonomy/implementation-status.json) record all 52 implementation/acceptance dispositions. Checked tasks have passing evidence for their required deterministic scope. Native/live-containing tasks remain unchecked, even where their implementation and fixtures passed.

## Independent status axes

| Axis | Result |
|---|---|
| Runtime implementation | Implemented; exact-revision deterministic core and release evidence below. Wider inherited coverage uses separately recorded revisions; combined-ordering and optional/native limits remain explicit. |
| Actual Qwen/Fabro/gateway interoperability | NOT_RUN on the new candidate. Fixture wire tests are not native qualification. |
| Diagnosis, author, inspector, maintenance capability | NOT_RUN separately; no model family or nominal context setting implies role competence. |
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

## Executed evidence

See the exact commands, timestamps, exit codes, hashes and JUnit reports in:

- [Core deterministic implementation](../../evidence/v0.4/runs/DA014-core/latest.json).
- [Independent release regression process](../../evidence/v0.4/runs/DA014-release/latest.json).
- [Restored fixture/ref/tool prerequisites](../../evidence/v0.4/runs/DA014-restored-prerequisites/latest.json).
- [Historical offline migration and accounting](../../evidence/v0.4/runs/DA014-history/latest.json).
- [Isolated systemd semantics](../../evidence/v0.4/runs/DA014-systemd/latest.json).
- [Independent CRE evaluation](../../evidence/014-durable-local-autonomy/cre/independent-evaluation.json).

Exact source `794e8d0`: core **429 passed, 1 skipped**, no failures/errors (180.319 seconds); separate release regression **13/13 passed** (10.965 seconds). The core command includes all eight Feature 014 test modules, inherited AFO, lessons, profiles/gateway/ACP, inspection/workflow/skill, brownfield and kernel confinement regressions. The source checkout was clean at start and end. Commands source `scripts/forge-env.sh`, then explicitly set `PYTHONPATH` to that checkout’s `factory/python`; `TMPDIR` and all test outputs are on loop10. Vendor fixtures are hash-verified private inputs; their provenance is published without their contents. The release file runs in a separate process with the generic Fabro token override unset. The recorded normal umask preserves inherited cross-UID fixture behavior; raw logs remain mode 0600. No live inference was performed.

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

The exact-`794e8d0` independent evaluator is `cre-promotion-runner@918c6a4`; it returns REJECTED / PROTECTED_PATH_CHANGE and does not run later promotion gates. Feature 014 deliberately changes protected recovery/lesson authority surfaces under this externally requested engineering PR. This result is retained, not converted to eligibility or bypassed. Candidate source is never promoted automatically.

A standalone delivery fixture probe emitted two diagnostic knowledge audit events into the shared local JSONL stream because it omitted the private event-path override. Benchmark jobs, services and outcome records were unchanged. Their exact event IDs are retained in [fixture event provenance](../../evidence/014-durable-local-autonomy/followup/fixture-event-provenance.json) for exclusion from operational/learning metrics. Append-only history was preserved; subsequent standalone probes require private state and event paths.

## Executable qualification handoff

Six [prepared manifests and dry-run reports](../../evidence/014-durable-local-autonomy/qualification/prepared/) freeze the 20x5 protocol denominator, RCC stage, 30-product cohort and 24/72/168-hour operation stages. They are structurally prepared and explicitly BLOCKED: real case/job/input bindings and current signed campaign authority are absent. A dry-run or specification validator is never runtime qualification.

The historical `AUTH-OMNI-Q36-LOCAL-SELFHEAL-V4-20261024` expired at 2026-10-25 09:00 UTC and its four diagnoses were exhausted. It was not renewed, reused or signed by this implementation. The owner explicitly approved Feature 014 qualification in this conversation on October 25 ("I do, I approve all"). That approval permits preparing the new bounded campaign through the existing signing process; it does not change historical expenditure. Concrete frozen case/job bindings, a signed runbook `qualification-014:<frozen-manifest-sha256>` and isolated runtime prerequisites remain to be provisioned. Role qualification also pins actual model digest/precision/reasoning/schema/sampling/context/task and adapter revision.

The owner is concurrently using another Claude terminal for Codex/Claude ST-driver benchmarks. Read-only process/service metadata and the Feature 015 specification locate its Conductor on local loop10 with the cloud Fabro configuration/storage, separate from the older Omniverse2 local-Qwen stack at `/mnt/data/forge-c/lrtx-v2`. Those services, source worktrees and benchmark data were preserved. Qualification must use a separate candidate checkout/data root and the existing owner principal; its allowed public-key fingerprint matches an available SSH-agent key. No private key was read, no new grant was signed yet, and no remote service or model request was changed. Frozen case/job bindings and bounded signed campaign provisioning remain the next execution prerequisites. A hash-verified clean source checkout is now staged at `/mnt/data/forge-c/qualification-014-17e6cbd/repo-794e8d0`; [source staging evidence](../../evidence/014-durable-local-autonomy/qualification/source-staging.json) records zero service starts and zero inference requests. The old runtime remains unchanged.

On the Omniverse2 host only, with the pinned clean runtime checkout, approved profile namespace, registered bounded mission/order lineage and independently frozen cases:

```bash
python -m forge_factory.afo.qualification dry-run --manifest <frozen-manifest.json>
python -m forge_factory.afo.qualification provision --manifest <protocol-manifest.json> --authorization-ref <current-signed-id>
python -m forge_factory.afo.qualification step --manifest <protocol-manifest.json> --authorization-ref <current-signed-id> --results <results-directory>
python -m forge_factory.afo.qualification report --manifest <protocol-manifest.json> --results <results-directory>
```

Provisioning binds predeclared jobs after signing without changing case hashes or creating a grant, mission, new allowance or model request. Each call is bounded. Repeated `step` calls use existing AFO/native reconciliation and the same jobs; no campaign scheduler or blind relaunch is added. Independent audit files live outside product workspaces under `state/lrtx/qualification-audits/<manifest-sha>/<trial>.json`; their source revision, observation hash, independent producer and oracle hashes must match. Missing audits cannot become zero authority escapes, false successes or duplicate effects.

For RCC/benchmark, existing Conductor intake owns execution; qualification `step` observes bound product jobs and sealed archives, independent gates and request metadata. For operation stages use `python -m forge_factory.afo.operational_campaign start|sample|fault|report`, or the existing `afo.soak` entry point. Only the fixed authorized service signal recipes are executable faults; reboot, storage/resource faults and other exposures require separately authorized host fixtures. Sampling/reconciliation continues without renewing engineering authority. Required fault/work/post-campaign/later-intake coverage and the complete wall-clock denominator cannot be dropped. Campaign completion never stops the factory.

Before live execution: qualify the actual installed constrained-output/MCP/native header path, per-role semantic envelopes, cancellation/late-usage behavior, namespace dependencies and approved operational recipes. Then execute the 100 protocol trials, genuine RCC recovery and all six gates, gated GPIO intake, the representative 30-product benchmark, chronological learning comparisons, and staged 24/72/168-hour campaigns. All remain NOT_RUN here.

## Static checks

`python specs/014-durable-local-autonomy/validate_spec.py`, `python specs/014-durable-local-autonomy/contracts/validate_contracts.py` and `python tests/spec/validate_design.py` validate documentation/contracts and registry/design consistency only. The 52 requirements/tasks/acceptance mappings, three Feature 014 schemas and 25 structural fixtures retain their design validation. These checks cannot satisfy native capability, product or availability acceptance.
