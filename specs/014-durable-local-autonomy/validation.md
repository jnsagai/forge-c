# Implementation and qualification status

Updated 2026-10-25. Exact runtime source candidate: `cb9f2e7a719a16098617b44242fcec42e60545ea`. Later evidence/documentation commits do not qualify a different running deployment. Feature 014 remains stacked on PR #41; neither PR was merged or activated by this work.

The original authored specification and its three Feature 014 contracts are retained. `traceability.csv` is the immutable design-time NOT_IMPLEMENTED inventory used by the original specification checker. The dated [implementation matrix](implementation-status.csv) and [machine-readable evidence ledger](../../evidence/014-durable-local-autonomy/implementation-status.json) record all 52 implementation/acceptance dispositions. Checked tasks have passing evidence for their required deterministic scope. Native/live-containing tasks remain unchecked, even where their implementation and fixtures passed.

## Independent status axes

| Axis | Result |
|---|---|
| Runtime implementation | Implemented; deterministic core evidence below. Wider regression remains partial because retained inherited/suite-state/prerequisite failures exist. |
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

Mission identity and expenditure survive continuation and duplicate adoption. Known old expenditure remains charged; unbounded old usage refuses new admission. The fresh-database migration includes the previously lazy local-agent table so disabled/empty continuous supervision can capture learning before any model job exists.

Every unique ordinary job/phase outcome can produce factual experience and a durable learning disposition. NO_NEW_LESSON and DEFERRED_BUDGET are valid outcomes. Ordinary/negative source qualification, exact applicability, independent applicable/adverse receipts, content/version identity, holdout isolation and atomic delivery/retraction fences extend the existing lesson store. Legacy PROMOTED-repair validation and separate inspector IL governance remain in force. Exposure, application and independently measured benefit are distinct; comparison costs include retrieval, curation and validation.

Continuous mode rejects production finite-cycle limits. Failed/capability-limited jobs, exhausted engineering allowances, empty queues and campaign completion do not terminate supervision. Operator intent uses an OS-owned private file, durable epochs and serialized bounded start effects. Pending outbox commands cannot rebind to a newer resume epoch. STOPPED remains unresolved until contrary service-manager effects and native work settle. Explicit operator exit 77 prevents `Restart=always` restart; a false boot condition remains inactive.

The Maintainer retains its existing restricted native/MCP candidate workflow under the shared mission ledger and per-role capability gate. Frozen submission intents reconcile a crash after commit without another commit; immutable case/submission/reproducer receipts drive completion even without final model text. A candidate receipt remains BLOCKED for independent review, and native terminal status never releases a still-live provider request. Legacy submissions retain independent validation; new submissions cannot downgrade after losing their receipt.

## Executed evidence

See the exact commands, timestamps, exit codes, hashes and JUnit reports in:

- [Core deterministic implementation](../../evidence/v0.4/runs/DA014-core/latest.json).
- [Independent release regression process](../../evidence/v0.4/runs/DA014-release/latest.json).
- [Restored fixture/ref/tool prerequisites](../../evidence/v0.4/runs/DA014-restored-prerequisites/latest.json).
- [Historical offline migration and accounting](../../evidence/v0.4/runs/DA014-history/latest.json).
- [Isolated systemd semantics](../../evidence/v0.4/runs/DA014-systemd/latest.json).
- [Independent CRE evaluation](../../evidence/014-durable-local-autonomy/cre/independent-evaluation.json).

Exact source `cb9f2e7`: core **379 passed, 1 skipped**, no failures/errors (175.660 seconds); separate release regression **13/13 passed**. The core command includes all five Feature 014 test modules, inherited AFO, lessons, profiles/gateway/ACP, inspection/workflow/skill and brownfield regressions. The source checkout was clean at start and end. Commands source `scripts/forge-env.sh`, then explicitly set `PYTHONPATH` to that checkout’s `factory/python`; `TMPDIR` and all test outputs are on loop10. The release file runs in a separate process with the generic Fabro token override unset, as recorded in its evidence. No live inference was performed.

The real isolated Conductor test runs the actual process with a missing/invalid engineering policy, an already exhausted zero-allowance mission and no model service. It observes several healthy cycles, verifies unchanged mission accounting and zero model requests, then records an explicit stop and exit 77. This is short deterministic runtime evidence, not an availability campaign.

Seven actual local systemd tests cover unexpected clean exit, bounded immediate restart exhaustion, later slow start, process kill, notify watchdog hang, intentional stop, operator-exit prevention and boot-condition behavior (the report groups related observations into seven cases). They use only uniquely named transient `forge-c-014-qual-*` units and clean up those units. They do not deploy or qualify the remote production unit graph.

Read-only reconstruction exported the Omniverse2 unit/native event inventory without prompts, private inputs or hidden reasoning. An immutable private SQLite dump was replayed into a new loop10 database. The final history tool reads the Conductor's authoritative migration table (an earlier development report incorrectly read SQLite's unrelated `user_version=0`; that report is retained). Schema 4 -> 9 preserves all 246 historical rows in 13 legacy tables. Duplicate imports retain five unique product executions from 20 adoption rows and four diagnoses. Reported diagnosis tokens remain 54,704; conservative diagnosis charge remains 64,856. Unknown product usage stays unknown and prevents fresh capacity. V4's native stopping cause remains UNKNOWN. No original remote database was modified.

## Retained failures and limits

The broad `e0b340b` run reached 832 passes, seven failures and 17 skips before the declared 900-second limit and forced cleanup (exit 137). It did not complete all 1,445 collected tests. The later `d2e71bf` remainder recorded 383 passes, 12 failures, 133 skips and 15 setup errors. These runs and later contrasts are retained in [development attempts](../../evidence/014-durable-local-autonomy/development-attempts/); retries do not erase them.

- CRE prevention reproducers RPR-041, RPR-044 and RPR-047 report SYMPTOM_PRESENT on both unchanged `918c6a4` and the candidate parent. Two inherited promotion assertions therefore stop before their intended later gates. No oracle was relaxed.
- The inherited live-local-Qwen evidence check cannot find an eligible package in the isolated test state. It is not new Qwen execution or candidate product qualification. Qwen tests must run on Omniverse2.
- The inherited holdout-permission and KPI event-reference failures reproduce on unchanged `918c6a4`. Isolated traceability checks pass; a broad-suite traceability failure remains a suite-state concern, not silently removed evidence.
- The external-finalizer credential assertion fails in the same combined ordering on the unchanged baseline and candidate; its isolated test and full isolated release file pass. The original failed output is private; published copies redact credentials.
- Missing private inputs, absent local historical branch refs and a tool-discovery environment assumption caused remainder failures. Available inputs/refs/tool settings were restored without changing oracles; all 45 targeted prerequisite regressions and 50 peripheral/traceability regressions then passed.
- One explicitly disabled live-Fabro check remains skipped in the core command. Relevant native acceptance cases remain NOT_RUN.

The first Maintainer receipt development run exposed an artifact-directory bug; it is retained, the path was corrected, and the final run includes the new receipt tests and all inherited Maintainer regressions.

The exact-candidate independent evaluator is `cre-promotion-runner@918c6a4`; it returns REJECTED / PROTECTED_PATH_CHANGE and does not run later promotion gates. Feature 014 deliberately changes protected recovery/lesson authority surfaces under this externally requested engineering PR. This result is retained, not converted to eligibility or bypassed. Candidate source is never promoted automatically.

## Executable qualification handoff

Six [prepared manifests and dry-run reports](../../evidence/014-durable-local-autonomy/qualification/prepared/) freeze the 20x5 protocol denominator, RCC stage, 30-product cohort and 24/72/168-hour operation stages. They are structurally prepared and explicitly BLOCKED: real case/job/input bindings and current signed campaign authority are absent. A dry-run or specification validator is never runtime qualification.

The historical `AUTH-OMNI-Q36-LOCAL-SELFHEAL-V4-20261024` expired at 2026-10-25 09:00 UTC and its four diagnoses were exhausted. It was not renewed, reused or signed by this implementation. New live work needs its existing bounded authorization process and a signed runbook `qualification-014:<frozen-manifest-sha256>`; mission registration/import must preserve historical identity and expenditure. Role qualification also pins actual model digest/precision/reasoning/schema/sampling/context/task and adapter revision.

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
