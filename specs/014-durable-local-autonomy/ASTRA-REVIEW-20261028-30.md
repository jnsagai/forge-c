# Forge-C: three-day engineering review for offline Astra analysis

**Window:** 28–30 October 2026, through the read-only snapshots at approximately
18:33 UTC on 30 October. This covers three calendar work days, not a measured
72-hour availability campaign. Branch: `feat/014-durable-local-autonomy`; draft
PR [#42](https://github.com/jnsagai/forge-c/pull/42), stacked on PR #41.

**Reviewed source:** `c221b65ebc011cbed488db83af3e2804790c1129`.
The commit publishing this report adds documentation/evidence to that source.
The live Qwen checkout is a different, explicitly pinned revision, `451038c4`.
Do not equate branch HEAD, tested candidate, installed runtime and execution revision.

## Assessment

There is substantial implementation and diagnostic progress, including a real
Qwen-authored repair that passed the existing independent CRE gates after external
administrative/runner corrections, and a later scoped AFO product repair launched
without external intervention. There is still **no demonstrated clean complete
Qwen LL/HAL product**, no proven learning benefit, and no proven 24/7 operation.
The requested five-/six-/eight-hour production objectives were not demonstrated
as achieved. A running stack and isolated phase passes do not establish that result.

Formal Feature 014 progress remains **30/58 checked tasks**. The earlier brief
referred to 52; the current repository has 58. This report closes no additional
task. The exact checked/open IDs and 185 source-history entries in this date
window are in [review-scope.json](../../evidence/014-durable-local-autonomy/three-day-review-20261030/review-scope.json)
and [commits.tsv](../../evidence/014-durable-local-autonomy/three-day-review-20261030/commits.tsv).
Commit counts and test counts are not measures of delivered product success.

The main impediment has been the interaction of factory integration defects,
incomplete or incorrectly narrowed inputs, model/protocol limitations and
self-imposed admission/operational constraints. More GPU utilization alone does
not resolve those problems. Conversely, many failures were not evidence that
Qwen could not write the requested C: some stopped before any inference.

## Current execution state at the cutoff

| Axis | Observed status |
|---|---|
| Factory implementation | Many deterministic/integration checks pass; incomplete feature qualification |
| Qwen structured RCC LL | RUNNING, native LIVE, inference lease HELD, operator RUNNING epoch110 |
| Qwen SWE.1 | 62 valid author packets, 637 assembled requirements; four valid inspection packets PASS; full phase verdict pending |
| Author reuse | 49 previous author packets revalidated; this is neither imported inspection PASS nor measured learning benefit |
| Qwen HAL | Current dependent HAL order `afo-a1f5e36eecafc24c` NOT_SUBMITTED |
| Native Codex/Claude control r4 | Transport SUCCEEDED; product BLOCKED at SWE.3, 30 package gaps; SWE.1 and SWE.2 passed |
| Native Qwen same-workflow trial | Profile/graph tests prepared at c221b65e; NOT_STARTED |
| Full product/30-product campaign | NOT_PROVEN / NOT_RUN |
| Independent author/inspector/maintenance qualification | Not established by these pipeline observations |
| Learning benefit and 24/72/168-hour operation | NOT_PROVEN / NOT_RUN |
| Arbitrary embedded C targets/projects | NOT_QUALIFIED |

Live Qwen: order `afo-f2a638a42fadd518`, job
`afo-product-540644845473ac5b1f983d02`, native
`01M66YFFN0CJSFWVEMX0C89RHY`, runtime
`451038c4776db8e52c248148848d0f734af8b70b`. Its author visit closed at18:02:46UTC
after15 calls and one continuation. The total66 valid packet records include four
inspectors; they do not mean66 author obligations. No complete phase inspection
record was present at18:33. Same-model inspector agreement is not independent
correctness evidence. [Qwen snapshot](../../evidence/014-durable-local-autonomy/three-day-review-20261030/qwen-live-snapshot.json).

Cloud control: `WO-F014-CC-20261030-LL-r4`, native
`01M66YMZK9JTMZCF2PNV4JRGCY`, execution source
`f5e07c9e844b9ee09c391f50f74b2d30e4888246`. Finalized18:16:04UTC, archive SHA256
`86df0bb2d0e0bbc98ac20b1fdb1bb706a7f07da53f9284eac633691e703627a8`.
Its final upstream routing checks returned no upstream defects, but that output
does not explain the underlying SWE.3 author-gate failure. Detailed artifact/gate
triage is still required; no speculative root cause is asserted here.
[Terminal snapshot](../../evidence/014-durable-local-autonomy/three-day-review-20261030/codex-claude-r4-terminal-snapshot.json).

This report preparation used read-only runtime observation. It did not stop,
restart, deploy, change budgets or launch another inference campaign.

## 28 October: deployment, real failures, MTP and incremental delivery

1. Switched the installed model path to the owner's selected Qwen3.8-27B Q8
   alias, added explicit xhigh configuration and exercised complete serialized
   role admission. Fixed verified native-route reconciliation, staged target
   tool availability, API relay ownership and delayed recovery fencing. Connected
   actual remote runs to the dashboard; corrected an observation timeout that
   did not itself mean the model was dead.
2. Added the prospective ASPICE-only lane after the owner excluded safety. This
   removes safety-assurance applicability; it does not manufacture ASPICE
   conformance. Later QM demonstration policy is a separate development choice.
3. Fixed task coverage that omitted explicitly requested fields, preserved joint
   field obligations, and made cross-cutting author instructions self-contained.
   A CRC primary-reference field-name correction was input-specific; the coverage
   and packet fixes apply across supported peripheral profiles.
4. The real full-CRC attempt produced seven valid author packets, then four PASS
   and two FAIL inspector criteria. Native transport SUCCEEDED, product BLOCKED;
   downstream SWE.2–6 were NOT_RUN. Findings included joint-field treatment,
   reset/failure semantics and inconsistent coverage. Package gaps include absent
   downstream artifacts, so gap count is not unique defect count.
5. That failure did **not** prove Qwen attempted diagnosis and failed: the
   recorded diagnosis capability/admission path had zero diagnosis jobs and zero
   planner calls. A subsequent advisory continuation failed before launch because
   the brownfield contract included the attempt-specific administrative work-order
   ID. `98d066df` later corrected compatibility while retaining provenance.
6. Measured MTP on Omniverse's RTX6000 Ada48GB: weighted decode28.61→83.00tok/s
   (2.90×), four-call wall13.608→5.494seconds (2.48×). All eight small C outputs
   compiled and passed independent bounded CRC/popcount checks. This was a tiny,
   baseline-first, 65,536-context, thinking-closed microbenchmark, not xhigh
   engineering-role qualification or full-pipeline throughput.
7. Introduced incremental two-function CRC IDR delivery and a real-tool six-phase
   fixture. Fixture model responses are substitutions, not a successful live
   Qwen pipeline. Prepared verified reference examples through the existing lesson
   lane rather than declaring model learning.
8. Applied owner-requested very high finite development ceilings. An actual M1
   run still failed on safety/checklist applicability and absent CPU/time targets,
   then repeated cached failed inspections on an unchanged baseline. External
   containment stopped it after66 inspection records. `1dd54a0e` added the narrow
   no-progress guard. This was not token exhaustion or autonomous recovery.
9. Fixed host Git progress publication: the observer required explicit environment
   and a host administrative context rather than the inference network namespace.
   The model inference boundary remained separate.

Evidence: [MTP and terminal audit](../../evidence/014-durable-local-autonomy/mtp-and-terminal-audit-20261028/README.md),
[incremental delivery](../../evidence/014-durable-local-autonomy/incremental-e2e-20261028/README.md),
[high allowances and actual M1 failure](../../evidence/014-durable-local-autonomy/m1-high-allowance-20261028/README.md),
[resume compatibility](../../evidence/014-durable-local-autonomy/aspice-resume-98d066d/README.md).

## 29 October: later phases, tool integration and real maintenance attempts

1. During reported host unavailability, continued local work on simulation-only
   requirements, deadline handling, tool accounting and independent unit recheck.
   The owner approved nine IDR requirements, including64target instructions and
   100µs Renode virtual time per call at100MIPS. These are simulation allocations,
   not hardware WCET. An independent recheck may add evidence while preserving
   a failed/stale upstream state; it cannot turn the product green.
2. Read-only host investigation found the same boot since24September and overnight
   Wi-Fi/internet loss, restored29October09:02:56UTC. Evidence did not establish a
   shutdown; there was no physical reboot/power-loss qualification.
3. Added owner-selected QM applicability and all-phase demonstration routing.
   QM can produce development artifacts without safety claims. Demonstration
   continuation must preserve failed findings and its unqualified release status.
4. Increased context131,072→262,144, the installed model's reported context window.
   Q8/f16/MTP3 allocation succeeded, using roughly46.6GiB GPU memory with about
   1.9GiB free in one measured state. Allocation success is not context-quality
   proof and does not imply room for concurrent inference.
5. A real IDR demonstration reached SWE.6. Frozen SWE.2, SWE.4 and SWE.5 inspections
   passed; SWE.3 had diagram/tool lookup failures. The architecture structure
   checker checked zero register offsets; a separate audit verified one CRC IDR
   offset only. Do not generalize the structure pass into hardware correctness.
6. Found a factory environment defect: isolated Fabro/MCP servers did not retain
   the installed tool data root. `9f9a93f1` propagated it. This was external factory
   engineering, not something a constrained product author could repair itself.
7. Actual host/unit and Renode feedback drove model corrections. Recorded target
   checks went23PASS/1FAIL→27PASS/0FAIL in one sequence. A declared simulation
   performance artifact measured two functions at2instructions/20virtual ns per
   call at100MIPS, two samples each. That evidence is restricted to its instrumented
   simulation path. SWE.6 lacked a completed accepted result; last Robot snapshot
   was7/9. The owner's explicit stop was reconciled to QUIESCENT/RELEASED with no
   GPU compute process remaining. This interrupted demo was not a clean pipeline.
8. Added real authored LL/HAL performance-test routing to the existing verification
   path and actionable instrumented-test errors; removed assumptions that every
   SWE.6 measurement task used the older byte-budget syntax.
9. AFO maintenance trials exposed small navigation/output caps and confusion
   between cumulative job allowance and per-request context. Measured92Codex
   workspaces: the largest observed newly generated workflow source was7,278bytes;
   delivered LL RCC340,069bytes; device scaffold header3,599,048bytes. These are
   different origins, not evidence the model authored the vendor headers.
10. Increased AFO page target1,000→32,768characters, tool response2,048→65,536bytes,
    source-read ceiling65,536→4,194,304bytes and diagnosis/maintenance visits to
    200calls. Escaped complete JSON still governs page size. Added source inventory,
    hash-bound bounded edits, retained-work provenance and same-order repair loops.
    A larger page did not fix complete context overflow; context was raised
    separately. Some trials never submitted a candidate; others wrote real partial
    source/tests and were independently rejected.

Evidence: [host/recheck record](../../evidence/014-durable-local-autonomy/independent-unit-recheck-20261029/README.md),
[frozen SWE.2](../../evidence/014-durable-local-autonomy/context-expansion-20261029/swe2-frozen/README.md),
[SWE.4](../../evidence/014-durable-local-autonomy/mcp-root-followup-20261029/swe4-frozen/README.md),
[SWE.5/performance](../../evidence/014-durable-local-autonomy/mcp-root-followup-20261029/swe5-frozen/README.md),
[owner stop](../../evidence/014-durable-local-autonomy/owner-stop-20261029/README.md),
[paging census](../../evidence/014-durable-local-autonomy/afo-paging-20261029/README.md),
[maximum context](../../evidence/014-durable-local-autonomy/afo-max-context-20261029/README.md),
[brownfield attempts](../../evidence/014-durable-local-autonomy/afo-brownfield-repair-20261029/README.md).

## 30 October: accepted repair evidence, speed studies and broader scope

### Maintenance and product recovery

Qwen produced real maintenance candidates and its own reproducer/test, with root
plus two retained engineering reworks. Important rejections were reproducible:
an exact symptom marker had appended diagnostics; a registered signature wrongly
included `SYMPTOM_PRESENT:`; a committed effect became stranded because Git trimmed
one trailing space from its commit message. The broker is protected from the model,
so these contract/reconciliation defects needed external factory fixes.

`53e12347` reconciles only the exact legacy trailing-space normalization under
matching parent/tree/request; `5a288206` binds the one permitted administrative
signature correction. Original requests, failed decisions and expenditure remain.
External runner corrections supplied pinned tools and appropriate Java resources.
The unchanged complete CRE evaluator then accepted Qwen candidate
`bc931bd9274b0e1361bcc3d2b5e0ad23110d8db1` as ELIGIBLE_FOR_OFFLINE_REVIEW with all
seven hard gates PASS, including72frozen prevention cases. Integrated revision
`e21aa744` retained model authorship. The live inspector subsequently admitted a
73,677-token complete request beyond the former24,576 envelope and returned its
first PASS. This is real causal engineering evidence, **with disclosed external
bootstrap**; it does not prove completely unattended factory-code healing.

Later, on `a32d87a3`, Conductor autonomously diagnosed a real failed product and
executed REWORK_LOCAL. The missing SWE.2 static diagram appeared, its gate passed,
and all three retained SWE.1 files were byte-identical. No external intervention
occurred between failure and that repair launch/result. Scope limitation: the plan
declared the matrix while its explanation requested the diagram, so minimal
changed-file enforcement remains an open binder review. The owner then superseded
that run for a role experiment; that stop is not a model failure. A broad external
supersession filter also misclassified the already-finished diagnosis lifecycle;
an explicit erratum preserves its unchanged successful job/receipt and history.

Evidence: [maintenance recovery](../../evidence/014-durable-local-autonomy/maintenance-live-recovery-20261030/README.md),
[independent CRE and signature binding](../../evidence/014-durable-local-autonomy/maintenance-signature-binding-20261030/README.md),
[integrated live context repair](../../evidence/014-durable-local-autonomy/rcc-qwen-context-integration-20261030/README.md),
[unattended scoped product repair and erratum](../../evidence/014-durable-local-autonomy/aspice-stepwise-product-20261030/README.md).

### Correctness and workflow defects fixed

| Defect | Correction and boundary |
|---|---|
| Published findings truncated at200characters; author received only one summary | Preserve/deliver all published findings, legacy compatibility retained |
| Local source notes became global open points; wrong obligation reworked | Stable provenance and finding-to-note-owner routing |
| Startup invariant wrongly refuted a reset-bit finding | Narrow semantic distinction; preserve actual reset finding |
| Whole owner scope reduced to four seed sections | Select all25requested sections;21previously omitted sections were available |
| Legacy author quotas too small for real inventory | Profile-pinned all-phase allowances; identifiers above99 handled |
| Long structured author visits hit1800-second Fabro inactivity watchdog | Existing600-second checkpointed continuations; stdout alone did not reset watchdog |
| Existing whole-file loader rejected generated requirements | Profile1MiB loading capacity; actual context still measured independently |
| Conservative serialized bounds confused with native context | Measure complete JSON/native template plus non-message controls and reserve; retain refusals |
| Reused C compiled beside its already assembled definition | Replace only that definition in a temporary current header for real compilation |
| Restart discarded valid author work | Explicit hash-bound reuse under current validators; no imported phase/inspector PASS |
| Role preflight used an empty source-section map | Share the actual prepared launch section map and test missing-section rejection |
| Native ACP lost installed toolchain/data-root paths | Preserve pinned environment through existing gates |
| Codex replied in prose; strict worker parser rejected it | Declare compact reply contract in developer instructions; parser still strict |
| Query/no_write instructions ambiguous; manual hardcoded RM0486 | Clarify return/effect evidence and select declared manual; synthetic wrong-manual negative test |
| Native graph prompts imposed small example counts | Bind complete owner scope instead of fixed8–15/12–26requirement quotas |

These changes extend existing AFO/Fabro/MCP/governor/store mechanisms. They do not
establish generic support for every compiler, MCU, driver or embedded C application.
[Complete feedback defects](../../evidence/014-durable-local-autonomy/structured-inspection-feedback-20261030/README.md),
[scope audit](../../evidence/014-durable-local-autonomy/scope-inventory-20261030/README.md),
[watchdog/context](../../evidence/014-durable-local-autonomy/request-context-20261030/README.md),
[shared fixes and failed native checks](../../evidence/014-durable-local-autonomy/matched-controls-20261030/README.md),
[generic embedded C boundary](GENERIC-EMBEDDED-C.md).

### Model-speed and diagnosis measurements

| Study | Measured result | What it does not prove |
|---|---|---|
| xhigh vs medium diagnosis pilot | Median62.49 vs71.01decode tok/s; paired six-case gateway948.58 vs118.21s; complete trials1344.27 vs383.04s | Both only2/8expected decisions; xhigh had two setup refusals |
| Installed `high` effort | UNSUPPORTED by installed template | No silent mapping to medium or claimed high trial |
| MTP drafts3/2/4/6, xhigh | Median63.44/56.94/65.91/64.70tok/s | Small serial diagnosis cohort,2/8decisions each; no reliable production winner |
| Thinking none/medium/xhigh | Median61.76/68.64/63.29tok/s; total gateway28.32/129.29/1178.14s | All2/8decisions; faster output did not fix diagnosis correctness |
| Existing four-question medium diagnosis | 8/8expected decisions,26/32requests, median70.63tok/s | Exposed reference cases, not fresh holdout; incomplete input grammar forces UNKNOWN |

Most latency savings came from fewer generated reasoning/output tokens, not a
comparable increase in decode speed. Studies were serial and not randomized.
Author/inspector/maintenance roles need separate qualification. There is no
controlled comparable Qwen3.6 baseline here supporting a Qwen3.6 vs3.8 verdict.

A read-only Conductor sample also found journal/I/O waits while short non-thinking
requests took3–4seconds and complete trials took70–165seconds. An isolated local
32-transaction sample with a per-cycle retained WAL connection measured0.142→0.079s
and fewer writes, preserving FULL commits. This is a local storage result, not
measured whole-host or complete-pipeline acceleration. The original diagnosis
coordinator also hit a SQLite lock timeout and needed an external driver resume.

Evidence: [reasoning](../../evidence/014-durable-local-autonomy/model-speed-owner-abort-20261030/SPEED-REPORT.md),
[MTP](../../evidence/014-durable-local-autonomy/mtp-speed-20261030/SPEED-REPORT.md),
[thinking off](../../evidence/014-durable-local-autonomy/non-thinking-speed-20261030/v2/final/SPEED-REPORT.md),
[stepwise diagnosis](../../evidence/014-durable-local-autonomy/stepwise-diagnosis-20261030/final/SPEED-REPORT.md),
[WAL investigation](../../evidence/014-durable-local-autonomy/wal-cycle-20261030/README.md).

### Native Codex/Claude diagnostic controls

The owner requested parallel cloud controls to expose shared defects faster.
These use Codex gpt-6.1-sol/high authors and Claude claude-opus-5-5 inspectors,
without another Omniverse GPU workload. They share raw product inputs, scope and
functional criteria with Qwen, but execution decomposition, prompts and allowances
differ. They are **diagnostic controls, not an apples-to-apples model benchmark**.

| Attempt | Result |
|---|---|
| r1 | Preparation caller used unsupported model_gateway argument; never launched, zero model calls |
| r2,344b7051 | BLOCKED SWE.1,48gaps; missing CPU/time allocation and register-effect ownership issues |
| r3,c1244ecd | BLOCKED SWE.1,49gaps; missing artifacts/query effects, reply protocol and35-call allowance issues |
| r4,f5e07c9e | SWE.1/SWE.2 PASS; final BLOCKED SWE.3,30gaps; exact final root cause still needs triage |

The controls found genuine framework issues quickly, but did not reach a clean
complete LL/HAL result either. More capable models do not bypass broken tool
contracts or missing inputs. Supplied simulation-only allocations now match both
RCC paths; the cloud run's success is not presumed from configuration.

## Constraints, policy changes and engineering cost

| Constraint | What happened / current interpretation |
|---|---|
| Safety applicability and signatures | Owner moved from safety to ASPICE-only, then QM artifacts. Do not keep treating safety approval as a prerequisite for the latest QM objective |
| Very small tool pages/calls | Navigation consumed allowance before useful repair; measured sizes justified substantial increases |
| Context | Raised through131072 to262144; distinguish bytes, actual template tokens, physical allocation and cumulative allowance |
| Token accounting | Historical reservations are large conservative floors, not measured generated tokens; aggregate historical use remains UNKNOWN where recorded |
| Cancellation/liveness | A terminal business status never alone proved a request stopped; explicit stops required native/provider reconciliation |
| Model role admission | Per-source/profile/role signatures and preflight uncovered real binding defects but also added considerable setup latency |
| CPU/RAM test isolation | Four-core/1.5–8GiB native test limits describe verifier sandboxes, not the Qwen serving allocation or a claim host resources were maximized |
| Hardware | Q8/f16/262144 consumed almost all48GB VRAM in observed allocation; no duplicate factory inference campaign was launched |
| External load | Earlier other-account workload was disclosed and the owner allowed shared resources; no causal attribution of every slowdown to that workload is justified |
| Missing ignored fixtures/tools | Clean Git clones lack private manuals/vendor inputs; PATH, UID/passwd, Java and namespace mapping mistakes caused setup failures, retained as such |
| Time windows/operator intent | Earlier grants expired; explicit amendments were appended where approved. Restart/continuation did not erase old limits or failed history |
| Storage/local inspection | Local project artifacts use loop10; approved cleanup targeted reproducible candidates, with inventory and execution receipts; private full packages remain separate from public Git metadata |
| Cloud comparison fairness | Different native vs structured adapters confound model-only conclusions |
| Human intervention | Many source fixes, activations, runner corrections and some steering were external; report them rather than calling the entire sequence autonomous |

The **latest owner instruction** is to ignore trusted generation-role identity,
token-accounting enforcement and cancellation/admission controls for an immediate
artifact demonstration, retaining deterministic checks where possible. This is
a deliberate development-priority change, not an assertion that the original
Feature014 robustness requirements were implemented or qualified.

At c221b65e a native QM Qwen profile and shared six-phase graph are prepared without
structured task substitutions. The existing repair demonstration policy retains
findings and attempts later phases. A standalone operations launcher is drafted
on loop10 but **not executed**. It must not be mistaken for an already running
native trial. Outstanding launcher work includes correcting the Fabro dev-token
auth-file shape, preparing its isolated source/private inputs, and orderly
single-GPU handoff from the current run. Some existing MCP/file/protocol boundaries
and the physical context ceiling still apply. Do not advertise all constraints
as removed. No additional signing question is needed for the already approved
development scope. Observe available usage separately rather than pretending
untracked work is free, and preserve existing AFO histories.

## Verification record and its limits

Representative exact-source cohorts (overlap; **do not sum**):

| Revision | Recorded verification |
|---|---|
| e098b515 | Native79PASS and local29PASS; real-tool fixture with substituted model answers |
| f206e3aa | Local84PASS and native84PASS; independent recheck boundaries |
| 979dcb40 | Local152PASS/1FAIL/1SKIP then corrected single-case PASS; native152PASS/2SKIP after namespace correction |
| 92c49a6a | Local37PASS; native36PASS/1setup ERROR, retained |
| 53e12347 | Local94PASS; native83PASS; nested Podman case separately local |
| 5a288206 | Local107PASS; native96PASS |
| e21aa744 | Local164PASS; native124PASS/1setup ERROR, unchanged failed case then PASS with declared fixtures |
| 7fbefc40 | Local133PASS; native443PASS |
| 27f337e1 | Local283PASS/1inherited fixture skip; native482PASS |
| 20dccfcb | Local159PASS/1same skip; native492PASS |
| 9769911c | Native517PASS/1FAIL, cache compiler defect preserved |
| 9029f939 | Local192PASS; native575PASS/1optional Doxygen skip |
| c1244ecd | Local106PASS; native638PASS/1FAIL/1Doxygen skip, preflight inventory defect preserved |
| 451038c4 | Local62PASS; native640PASS/1Doxygen skip; actual deployed runtime |
| 76d79b46 / f5e07c9e /1089742d | Local56/33/49PASS, respectively |
| c221b65e | Focused31PASS after broader development run had six failures from QM placeholder compatibility; original retained |

Exact commands, durations, test IDs, versions, source hashes and isolation
provenance are in the linked evidence. Native deterministic cohorts made zero
Qwen requests and must not be described as model capability qualification.
The inherited entire repository suite was not repeatedly run on every increment.
The optional missing-Doxygen test is not a Doxygen qualification pass.

At1089742d, spec validation passed58requirement/task/acceptance mappings,
six schemas and38fixtures (16positive/22negative); contracts validation and
14design checks also passed. These are **static** checks, not native protocol,
product benchmark, learning or operational-campaign results.

The new shared-fixes export includes original failed native logs/XML alongside
corrected cohorts. The imported29-member simulation transfer was checked against
its recorded per-member size/hash manifest before publication. Full vendor/manual
inputs, model weights, private environments/databases and hidden reasoning are
not part of this review package. Public hash inventories support integrity,
not a blanket privacy or engineering correctness guarantee.

## What Astra should decide next

1. **Finish one artifact pipeline before further architecture expansion.** Audit
   the final cloud r4 SWE.3 gate failure. Separate code/design defects the author
   should rework from factory-contract defects requiring a shared fix. Run the
   already requested native Qwen six-phase QM trial after a deliberate single-GPU
   handoff; keep deterministic checks/findings and label its output unqualified.
2. **Assess shared workflow vs structured obligations using evidence.** The owner
   wants the same schema/workflow as Codex/Claude. Test common artifacts, tool
   schemas, loopbacks and completion contracts. Retain task decomposition only
   where it improves measured success without losing global scope; avoid two
   drifting product definitions and a new competing scheduler.
3. **Audit complete scope independently.** Previously green seed-scope runs omitted
   21sections. Verify the declared owner scope, generated requirements, API/field
   inventory, traceability and tool coverage before claiming generic capability.
4. **Reduce administrative friction in the explicit development lane.** Distinguish
   development artifact production from robustness qualification and release.
   Do not silently erase historical ledgers, broaden production claims or ask the
   owner to approve the same scoped development choice repeatedly.
5. **Resolve remaining recovery boundaries.** Review plan artifact_scope vs diagram
   write, overly broad supersession filters, receipt/commit normalization, repeated
   no-progress loops, SQLite contention and exact stop-versus-recovery races.
   The real scoped repair is encouraging but not a substitute for fault campaigns.
6. **Qualify roles and learning separately.** Fresh held-out diagnosis, authoring,
   inspection and maintenance tests need independent oracles. Record exposure,
   application and measured benefit separately, including failed jobs and learning
   overhead. Reuse of validated packets is caching, not proof of learning.
7. **Keep generic embedded C as an explicit product requirement.** The current
   LL/HAL/register/Arm Cortex-M55 assumptions need project/target adapters and
   independent verification for additional MCU/compiler/API classes. Synthetic
   MANUAL42 tests are not physical target qualification. See GENERIC-EMBEDDED-C.md.
8. **Run the missing qualification when prerequisites exist.** RCC recovery,
   30-product evaluation/comparison, learning-benefit measurement, independent
   fault observation, boot/hang/restart-limit/reboot/mount-loss tests, then actual
   24/72/168-hour campaigns. Do not tick tasks from prepared scripts or static
   fixtures alone. Preserve the already parked known issues unless reopened.

For offline analysis, return a ranked defect list with exact source/evidence
references, a minimal route to one complete measured run, and explicit conditions
for returning robustness controls. Separate observed facts from architectural
hypotheses. Do not claim benchmark success, ASPICE compliance, safety approval,
general autonomy or continuous learning from the current record.

## Reproduction and offline navigation

```bash
git fetch origin feat/014-durable-local-autonomy
git switch --detach origin/feat/014-durable-local-autonomy
cat specs/014-durable-local-autonomy/ASTRA-REVIEW-20261028-30.md
cat evidence/014-durable-local-autonomy/three-day-review-20261030/review-scope.json
```

Use an isolated checkout if the current workspace is dirty. The local loop10
private operational roots are documented in HANDOVER-CODEX.md; their existence
does not imply they are included in a Git-only offline clone. Snapshot IDs and
SHA256s identify packages that can be provided separately if required. Read this
review and its snapshots before older handover sections labelled latest.
