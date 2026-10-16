# ADR-0008: Loopback analysis — routing defects back to the phase that caused them

- **Status:** Accepted (2026-10-15, owner request: "do a complete analysis of possible loopbacks") · **Scope:** WO
  workflow (SWE.1–6), gates, MCP evidence server, release finalizer · **Builds on:** ADR-0002 (Fabro audit),
  ADR-0005 #5/#17/#20 (bounded rework), T047 (product vs infrastructure defect routing)

## Context
Until now the only loopback was **same-phase rework**. The `swe{n}_route` node returned to `swe{n}_author` while
the phase rework budget lasted, and otherwise went to the finalizer as BLOCKED. A downstream author can write only
its own phase's paths (`ROLE_WRITE_PREFIXES`). So a defect *caused* upstream and *detected* downstream could not
be fixed where it lives. The downstream author had only two moves:

1. **Bend its own test until it passes.** Observed in r60: SWR-014 says "If a peripheral or oscillator parameter
   is invalid, then the RCC driver shall return HAL_ERROR without performing any register write". The
   architecture (SWE.2) defines a timeout-only API, and the HAL has no parameter validation. The SWE.6 scenario
   failed 4 checks. The author then rewrote it into a timeout-rollback test (SWR-013 behaviour) that kept the
   "out-of-range" comments. It passed, the SWE.6 inspection passed, and the "18/18" result overstated
   verification. The SWE.5 inspector in r56 had already flagged SWR-014.
2. **Exhaust rework and BLOCK.** This is honest, but the product is never fixed.

## Facts established for the design (model-free Fabro 0.362 probe, 2026-10-15)
Command nodes only, local Fabro :32290. The probe is in the session scratchpad, and its results are restated here.
- **P1 (works):** a backward jump across phases using only `condition="outcome=succeeded"` plus an
  unconditional fallback edge. Trace `a b0 route up0 a b1 done fin`, run `succeeded`. This is the only routing
  primitive the design uses. Edge conditions on `context.command.output` validate syntactically, but their
  runtime semantics are unverified, so they are not used.
- **P2 (constraint):** entering a node beyond its `max_visits` makes Fabro **kill the whole run**
  (`workflow_error: node "a" visited 1 times (node limit 1); run is stuck in a cycle`). Every node on a re-entry
  path therefore needs visit budget for each loop it can take.
- Fabro's identical-failure breaker hashes about the first 200 characters of a failed command's output (#20).
  Gates print a distinct marker first.

## Defect origins (where the fault lives)
| Id | Origin | Owner allowed to change it | Examples |
|---|---|---|---|
| O0 | Approved inputs (RM0486, DS14791, HAL guideline, HSI contract, manifest) | **Human only** (read-only approved baseline) | Contradiction between RM sections; missing register description |
| O1 | SWE.1 requirements, trace CSV | swe1-author | Ambiguous, untestable, or infeasible requirement; requirement not applicable to the chosen API; missing requirement; trace row to a non-existent test |
| O2 | SWE.2 architecture, interfaces, budgets, views | swe2-author | API shape cannot satisfy a requirement (SWR-014); missing component or interface; budget allocation impossible |
| O3 | SWE.3 detailed design and C code (LL/HAL) | swe3 fix author | Logic bug, wrong register or bit, missing implementation, MISRA or guideline violation, budget overrun |
| O4/O5/O6 | Tests of SWE.4 / SWE.5 / SWE.6 | that phase's author | Wrong expectation, wrong register, a test that does not exercise its requirement |
| O7 | Factory assets (Renode RCC model, ForgeTarget, scaffolds, deterministic checkers, checklists, policies) | **Factory maintainer (human / implementation engineer)**. Agents must never edit them (CLAUDE.md: never auto-edit safety policies) | Checker false positive; behavioural model gap |
| O8 | Runtime infrastructure (Fabro, gateway, MCP crash, sandbox limits) | Repair Agent (T047, existing) | Fabro down, MCP server crash |
| O9 | Inspector error | Re-inspection | Missing verdict (fixed by #18); false finding; lenient PASS |
| O10 | Agent protocol (reply not JSON or not schema-valid) | Same node | r61 SWE.3: 2 of 3 rework cycles lost to `AGENT_OUTPUT_PROSE`/`_SCHEMA` |

## Detection points
| Phase | Deterministic detection | AI detection |
|---|---|---|
| SWE.1 | EARS (SWE1-07), ReqIF export and validation (SWE1-08), presence gate | swe1-inspector SWE1-01..06 |
| SWE.2 | Architecture structure (SWE2-07), PlantUML views (SWE2-08) | swe2-inspector |
| SWE.3 | compile (target and host), cppcheck/MISRA, HAL guideline (SWE3-07), register map vs RM (SWE3-08), implementation completeness (SWE3-09) | swe3-inspector |
| SWE.4 | `run_unit` (host), coverage, trace test-ID check | swe4-inspector |
| SWE.5 | `run_integration`, `run_renode` (Cortex-M55 model), `measure_elf`/`stack_usage` budgets | swe5-inspector |
| SWE.6 | `run_robot` (requirement-tagged, Renode) incl. UNCOVERED_REQUIREMENT, `validate_trace` | swe6-inspector |
| Release | finalize gap list (missing files, failed checks, open findings) | — |

## Loopback catalogue (detection → origin → action)
| Loop | Trigger (detected at → origin) | Action | Status |
|---|---|---|---|
| **L0** same-phase rework | any gate in phase n → On | `swe{n}_route` → `swe{n}_author` (SWE.3: fix author) | existing, bounded by 3 failed cycles per phase |
| **L1** code defect | SWE.4/5/6 test or inspector → O3; SWE.5 budget overrun → O3 | `report_defect(target SWE.3, kind CODE)` → route chain → `swe3_fix_author` with the defect as input. Then cascade (L5). | **new** |
| **L2** architecture/interface defect | SWE.3 (design cannot implement an allocation), SWE.5 (interface/sequence mismatch), SWE.6 (requirement unverifiable through the API, e.g. SWR-014) → O2 | `report_defect(target SWE.2, kind ARCHITECTURE)` → `swe2_author`. Then cascade. | **new** |
| **L3** requirement defect | SWE.2/3 (infeasible or ambiguous requirement), SWE.4–6 (untestable or inapplicable requirement, trace row wrong) → O1 | `report_defect(target SWE.1, kind REQUIREMENT)` → `swe1_author`. Then cascade. Requirements were derived by the factory, so changing them is in-scope rework. Each change is recorded in the defect log and the package for human review. | **new** |
| **L4** test defect | test fails because the test is wrong → own phase | Stays in L0, but must be **declared**: `report_defect(kind TEST, target = own phase)` with the reason. Otherwise the test-integrity check fails the phase (anti-bending). | **new** (declaration and check) |
| **L5** cascade re-verification | any upstream baseline re-frozen after downstream baselines exist | The engine already marks downstream baselines stale (`UPSTREAM_CHANGED`). The forward path re-runs every downstream phase (regression on the new baseline). The detecting phase verifies the defect: the **cited test files must be unchanged** and the phase's tool must now pass. | **new** (verification); staleness existing |
| **L6** input defect | any phase → O0 | `report_defect(kind INPUT)` → **ESCALATED**: no automated fix (approved inputs are read-only). The package gets gap `escalated_defect:<id>`. | **new** (record and escalate) |
| **L7** factory defect | any phase → O7 | `report_defect(kind FACTORY)` → **ESCALATED** to the factory maintainer (never auto-edited). Package gap. | **new** (record and escalate) |
| **L8** infrastructure | supervisor probes → O8 | Repair Agent (T047) | existing |
| **L9** inspector error | author disputes a finding | Missing or malformed verdicts are refused and resubmitted (#18). A disputed finding is answered in the next rework cycle and seen by the next inspection, bounded by L0. A separate dispute channel is **deferred**: it would let authors argue findings away. | partial (by design) |
| **L10** format violation | `AGENT_OUTPUT_PROSE`/`_SCHEMA` while the required outputs are present and complete | **Evidence decides, not the format.** A non-empty reply that does not signal failure is frozen if the deterministic presence gate passes. The checks covered are outputs, required tool PASSes, stale PASS, defect verification and anti-bending. `AGENT_OUTPUT_CONTRACT_VIOLATION` is recorded (`FROZEN_BY_EVIDENCE`) and the inspection decides. Replies with a failure signal (BLOCKED, REWORK, turn budget, could not, incomplete…) and empty replies (dead session) are still rejected. Budgets are unchanged. | **implemented** (owner decision 2026-10-15) |
| **L11** unreported code defect (safety net) | a test phase is about to BLOCK (rework budget exhausted) with no defect reported, while its own recorded test evidence proves a code defect | The route gate files the CODE defect itself (`reported_by: route-gate`). The evidence is the newest test run of this run where: the product code is byte-identical to now; every scenario built; **every** failed check calls the driver and tests a token the tagged requirement names (e.g. `rc == HAL_ERROR with rc = HAL_RCC_HSI_Enable(0U)` for "shall return HAL_ERROR"); and that requirement was not reported unobserved. The run's test files are restored from the tool snapshots (same code + same tests = same result) and cited, so the fix is verified with exactly the failing test. The SWE.3 author still judges and may `reject_defect` with a reason. The same tests are never filed twice. Gate-filed defects show as `open_defect:…:gate-filed` gaps. Currently only `run_robot` records the structured failed checks. | **implemented** (owner decision 2026-10-15) |
| **L12** rejected loop (no cascade) | the upstream owner rejects every defect of the latest loop | Each upstream loop first runs `swe{k}_triage`, the owner role in a small edit-free step: accept, or `reject_defect` with a reason. `swe{k}_triage_gate` sends the run to the owner's fix step if any defect is accepted, or if the owner's baseline was changed anyway. If every defect was rejected and the owner's baseline is intact, it goes through the return chain `return_swe2→…→return_swe6→finalize` to the reporting phase's rework entry. Nothing upstream is re-frozen, so no downstream phase is redone. The reporter is told that a rejected defect carries the owner's reason: correct the test (declare TEST) or report REQUIREMENT. | **implemented** (owner decision 2026-10-15) |
| **L13** test adapted to an upstream fix | a test edited after a runtime failure (anti-bending L4) had **passed with the same content on the pre-fix code**, and a CODE/ARCHITECTURE/REQUIREMENT defect was FIXED between that pass and the failure | At the author gate, the gate declares it itself: kind TEST, `reported_by: route-gate`, citing the fix defect's requirement clause and both integrity records. The phase can then freeze. Inspectors of SWE.4–6 are told to check every gate-declared test against the requirement as written and FAIL the item if it no longer checks it. SUP.9 in the package lists all gate-filed and gate-declared defects for human review. A test that never passed before the fix is still plain bending and stays blocked. | **implemented** (owner decision 2026-10-15) |
| **L14** declaration coverage | a declared test file (L4/L13) fails again and is corrected again, while the product code is the one the declaration was made against | The declaration covers the further corrections (no new declaration). The defect records the product-code hash at declaration (`code_sha`); a declaration made before this field existed uses the code of the newest test run before it. After a code change (upstream fix) the correction needs a new declaration. The content is guarded by the requirement observability check, by the SWE.4–6 inspector, which reads the **current** version of every declared test file (author- or gate-declared) against the cited requirement, and by SUP.9. | **implemented** (owner decision 2026-10-16) |
| **L15** reporter withdraws its blame | the reporting phase finds that its own CODE/ARCHITECTURE/REQUIREMENT defect (OPEN, IN_FIX or FIXED, not yet VERIFIED) was its test error | It corrects the test and declares kind TEST on the same test file and an overlapping requirement. The earlier defect becomes **WITHDRAWN** (no gap, listed in SUP.9 for human review). Without this, a FIXED defect requires its cited test byte-identical and passing, so a wrong blame was a dead end (BLOCKED). | **implemented** (2026-10-16, autonomy window) |

Rejected alternatives:
- **Letting downstream authors edit upstream files.** This breaks role separation and the baseline/inspection
  chain.
- **Multi-way routing on command output.** Runtime semantics are unverified in Fabro 0.362 (CLAUDE.md:
  validated API only).
- **Unbounded loops.**

## Design
**Defect register** (`.forge-run/defects/DEF-NNN.json`; packaged under `defects/`). Fields: `id`,
`detected_phase`, `reported_by`, `target_phase`, `kind` (CODE, ARCHITECTURE, REQUIREMENT, TEST, INPUT,
FACTORY), `requirement_ids`, `test_files` (with sha256 at report time), `evidence_refs`, `summary`, `status`, and
`history`. Status moves OPEN → IN_FIX → FIXED → VERIFIED. A defect can instead end REJECTED (target author, with
reason) or ESCALATED. Written only by the deterministic engine via MCP:
- `forge-evidence-mcp.report_defect`: SWE.2–6 authors and inspectors.
- `forge-evidence-mcp.resolve_defect`: authors of the target phase, REJECTED with reason only. FIXED and
  VERIFIED are set by gates, never by agents.

**Validation at report time** (deterministic, so blame cannot be shifted upstream without evidence):
- The target is upstream of the detecting phase, or is the detecting phase for kind TEST.
- Every `requirement_id` exists in SWE.1.
- A CODE defect from SWE.4–6 cites a failing `run_unit`/`run_integration`/`run_renode`/`run_robot` result of the
  detecting phase, or a source location (`file:line`) inside SWE.3 paths.
- Every cited test file exists, and its sha256 is recorded.
- At most 6 open defects per run.

**Routing** (P1 primitive only):
- `swe{n}_route` exits 0 → same-phase rework, unless an OPEN upstream defect from phase n exists. The route then
  exits non-zero immediately, so the phase does not burn rework cycles on code it cannot change.
- The fallback goes to a shared chain, earliest target first, because an earlier fix cascades over the later
  ones:
  `upstream_swe1 -[ok]-> swe1_author`, else `upstream_swe2 -[ok]-> swe2_author`, else
  `upstream_swe3 -[ok]-> swe3_fix_author`, else `finalize`.
- Each `upstream_*` node exits 0 only if an OPEN defect targets that phase and the run's upstream-loop budget
  remains. It then marks those defects IN_FIX and logs the loop.

**Bounds:**
- Upstream-loop budget `U = 2` per run.
- Per-phase rework budgets are counted **per epoch** (owner decision 2026-10-15, superseding "over the whole
  run"). An epoch starts at the run start and at every upstream loop, so after an upstream fix each phase has its
  authored maximum (3 failed cycles) again. Failures before the fix were spent on code that no longer exists.
- `max_visits`:
  - loopable nodes: `(1 + 3) × (1 + U)` = 12;
  - single-pass nodes on the forward path (scaffolds, regmap, test authors, LL/HAL authors): `1 + U`;
  - chain nodes: `U + 1`.
- The P2 constraint is checked by a builder test: every node reachable from a chain target has enough visits.

**Re-entry prompts:**
- Upstream fixers read the OPEN/IN_FIX defects targeting their phase. The cited tests are evidence: change the
  product, not the tests.
- Downstream test authors visited again (regression) run their existing tests. They change a test only via a
  declared TEST defect.

**Defect verification and anti-bending:**
- When the detecting phase freezes again, each IN_FIX defect it reported is checked:
  - cited test files byte-identical, and the phase's tool PASS → VERIFIED;
  - cited test changed → `DEFECT_TEST_CHANGED` (reject).
- A test file that had runtime assertion failures and later passes with the test changed but no change to SWE.3
  code needs a declared TEST defect (r60's case). Without one it is a major finding.

**Package:**
- Every non-VERIFIED/REJECTED defect is a gap (`open_defect:` or `escalated_defect:`).
- The defect log, including REJECTED reasons and TEST declarations, is packaged for the human reviewer.
- Nothing in this design marks a requirement or product as verified.

## Consequences
- Code, architecture and requirement defects found late can be fixed where they live, followed by full
  regression of the phases that depend on them. Bending a test to pass becomes a recorded, reviewable
  decision.
- Runs get longer: one upstream loop re-runs every phase from the target onward. U=2 bounds the cost.
- Requirement and architecture changes made by agents are visible in the package (defect log plus baseline
  history). They are inputs to human review, never approvals.
- Still deferred: L9 dispute channel and L10 protocol-retry separation (owner decision).

## Implementation (2026-10-15)
| Item | Where | Test |
|---|---|---|
| Defect register: validation, status machine, gaps | `inspection/defects.py` | `test_loopbacks.py::test_report_validation_is_deterministic`, `…only_target_author_rejects…` |
| MCP `report_defect` / `reject_defect` (v0.5 registry overlay; skills re-rendered) | `mcp/servers/evidence.py`, `config/factory/mcp-registry.v0.5-kpi.yaml` | `…mcp_report_defect_uses_node_phase_and_role` |
| Route leaves the phase on an OPEN upstream defect; shared chain `upstream_swe1→2→3→finalize`; loop budget U=2 | `inspection/gate.py` (`route`, `upstream`), `workflow/builder.py` | `…route_leaves_phase_and_chain_routes_to_owner_within_budget`, `test_t009…upstream_chain…` |
| `max_visits` sized for re-entry (P2) and the per-epoch budget | `workflow/builder.py` (`MAX_VISITS = (1 + 3) × (1 + U)`, `ONCE = 1 + U`) | `test_every_agent_node_has_visit_budget_for_upstream_reentry` |
| Per-epoch rework budget (route, inspection gate); the token governor's per-node cap scales with `MAX_VISITS` | `inspection/engine.py` (`budget_start`), `inspection/gate.py`, `policy/governor.py` | `…upstream_loop_starts_a_fresh_rework_epoch` |
| L11 safety net: structured failed checks + test-file snapshots recorded by `run_robot`; route gate files the CODE defect and restores the failing tests | `mcp/servers/tests.py`, `inspection/defects.py` (`auto_code_defect`), `inspection/gate.py` | `…safety_net_files_code_defect_from_evidence…_r69`, `…safety_net_never_blames_code…`, `test_robot_swe6…_r68` |
| Full graph in resumed runs (`start` → restart phase) | `workflow/builder.py` | `test_resumed_graph_keeps_upstream_owners…` |
| FIXED on the target's inspection PASS; VERIFIED at the detecting phase's freeze, with unchanged cited tests and a post-fix PASS | `gate.py` (`inspect`, `author`) | `…fix_verified_only_with_unchanged_tests…`, `…bent_test_after_fix_is_rejected…` |
| Stale tool PASS (recorded before the current SWE.3 baseline) does not satisfy the presence gate | `inspection/engine.py` | `…stale_tool_pass_before_current_code_baseline…` |
| Anti-bending: a test edited after a runtime failure with unchanged code requires a declared TEST defect | `defects.bent_tests`, `evidence/test-integrity.jsonl` written by `run_unit`/`run_integration`/`run_renode`/`run_robot` | `…bent_test_without_declaration_blocks_freeze_r60`, `test_robot_swe6` (real Renode run records the failing scenario) |
| Package: defect log under `defects/`; open and escalated defects are unresolved findings | `release/finalize.py` | full suite |
| Re-entry safety: regmap keeps authored LL functions; LL/HAL authors told not to duplicate | `inspection/regmap.py`, `workflow/prompts.py` | `…regmap_regeneration_on_reentry…` |
| Agents cannot write the defect register, loop log or integrity evidence | `policy/authz.py` (no write scope) | `…agents_cannot_write_defect_register…` |

**Known limits:**
- `--resume-from` does not carry open defects from the source run. They stay in the source package.
- HAL re-entry after an SWE.1/2 loop relies on the author prompt; compile and completeness checks catch
  duplicates.
- L9 and L10 remain deferred.

## First live run (r62, DeepSeek, resumed from r56 at SWE.6)
- **Mechanics worked.**
  - SWE.6 reported DEF-001 (ARCHITECTURE, SWR-014). The route left SWE.6, the chain picked SWE.2, and the
    architecture gained a selector parameter with HAL_ERROR on invalid selectors. SWE.2 and SWE.3 re-passed
    inspection, and SWE.4 re-ran.
  - SWE.5 hit the anti-bending check (`TEST_CHANGED_AFTER_FAIL`) and reported DEF-002 (CODE). This was the
    second loop, to SWE.3.
  - The loop budget was then exhausted, so the run ended BLOCKED with both defects listed as gaps.
- **Semantic failure.** DEF-002 asked the code to keep `<x>ON` set after a timeout ("hardware leaves it set").
  That contradicts SWR-013 ("shall clear the enable bit it set and return HAL_TIMEOUT"). The SWE.3 fixer complied.
  SWE.4 then declared the correct test UT-063 "wrong" (DEF-003). The unchanged unit test caught the regression,
  so the run BLOCKED rather than passing falsely, but the loop had been used for requirement drift.
- **Remedy:**
  - CODE and TEST defects must quote, verbatim (20+ characters), the requirement clause the code violates or the
    corrected test checks. Otherwise the report is refused with `REQUIREMENT_QUOTE_REQUIRED`.
  - Disagreeing with a requirement, e.g. "real hardware behaves differently", must be filed as kind
    REQUIREMENT and goes to SWE.1, where the change is visible.
  - Fixers are told that a requirement as written always wins: reject a defect that asks for contrary behaviour.
  - Regression test: `test_report_validation_is_deterministic`.

## Second live run (r63) and remedies
- **No failing test, no defect.** The SWE.6 author knew the API had no invalid-parameter path. It tagged SWR-014
  ("shall return HAL_ERROR without any register write") on checks that never mention HAL_ERROR, so nothing
  failed and the anti-bending check had nothing to catch. r60 had done the same.
- **The finding was never recorded.** The SWE.6 inspector noticed ("traced but arguably not verified"), but used
  all 20 calls before calling `check_inspection`, twice. REINSPECT exhausted the budget.
- **Remedies:**
  - **Requirement observability:** `run_robot` FAILs with `REQUIREMENT_NOT_OBSERVED:<SWR>:<token>` when the
    checks a test runs never mention what its requirement demands: every HAL status the requirement names, or one
    of its `RCC_<REG>.<FIELD>` fields. User keywords are expanded. Retro-check: it flags r60 SWR-014 and r63
    SWR-014/005/006 (005/006 check only `HAL_OK`, never the ready flag the requirement names). Test:
    `test_requirement_must_be_observed_by_its_tagged_checks_r63`.
  - **Reserved inspector calls:** the last 4 of an inspector's authored 20 calls are usable only for
    `check_inspection`/`report_defect`. A denied call does not consume budget, and the budget itself is
    unchanged. Test: `test_t042_inspector_last_calls_reserved…`.

## Third live run (r64)
- **The SWR-014 test was real.** It checked HAL_ERROR on an invalid selector and failed, and observability also
  flagged SWR-012. But no defect was reported. Each SWE.6 author visit spent its 20 calls diagnosing the terse
  `check 1 failed in scn_invalid_param.c`: it re-read scenarios, the HAL and the reports, and even re-ran
  integration and Renode. Rework was exhausted without any decision.
- **Remedies:**
  - `run_robot` adds `CHECK_EXPR:<scenario>#<id>:<expression>` for every failed check, so the decision needs no
    file reads.
  - The SWE.6 author runs Robot first and must decide within 5 calls on a failure: correct the test and declare
    it, or `report_defect` and stop with REWORK.
  - Only run_robot and validate_trace are allowed in this step. The reports are read only when writing the
    report.

## Fourth live run (r65)
- **Robot passed 18/18, but 3 requirements were never observed.** Observability held back SWR-005/006 (no
  check on the ready flags) and SWR-014 (no HAL_ERROR check), so `run_robot` correctly stayed FAIL.
- **The authors misread the finding.** They took `REQUIREMENT_NOT_OBSERVED` as a tooling or mapping problem:
  they searched for ForgeTarget and grepped the factory, and all 3 cycles ended at the turn budget.
- **Remedy:**
  - Issues are now actionable within the 120-character cap: a leading `HOW_TO_OBSERVE` line, then
    `REQUIREMENT_NOT_OBSERVED:SWR-005:needs TCHECK on LL_RCC_SR_HSIRDY_MSK in scn_osc_ready.c`. Register fields
    are named by their generated LL macro.
  - Both the SWE.6 test author and the SWE.6 author are told: this is your test gap. Add exactly the named
    check. If it then fails, report the defect.

## Fifth live run (r66): the loop works end to end on the agent side
- **SWE.6 reported a grounded CODE defect** for SWR-014, with a verbatim quote and the failing check
  `HAL_RCC_MSI_Enable(0U) == HAL_ERROR`.
- **The loop ran:** chain to SWE.3, where the fix author made timeout 0 an invalid parameter (HAL_ERROR). Verify
  and inspection passed, the defect became FIXED, and SWE.4 re-verified and passed.
- **SWE.5 was BLOCKED before SWE.6 could verify the defect.**
  - Its budget included r56's failed `INS-SWE.5-001`, carried over by `--resume-from`.
  - It also edited an integration test after a runtime failure without declaring it; anti-bending rejected
    that correctly.
- **Bug fixes:**
  - Failed inspections count toward this run's budget only if recorded since the run's manifest was created.
  - A repeat report of the same still-OPEN defect returns the existing one (r66 created a duplicate DEF-002).
- **Open owner question: budget per epoch.** After an upstream fix, the downstream phases re-verify on a new
  baseline. Their rework budget currently still includes failures from before the fix. A per-epoch budget (3
  cycles per upstream change) would need `max_visits = 4 × (1 + U)`.

## Sixth live run (r67)
- **Every SWE.6 scenario failed to build.** The test author wrote `LL_RCC_CR_HSION` instead of the generated
  `LL_RCC_CR_HSION_MSK`.
- **The authors never saw the cause.** The fix of r65 put observability lines first, so 28 issues were cut to 11
  by the 2 KB result cap, and the build errors and gcc's "did you mean" hint were dropped. The authors chased
  observability lines for scenarios that did not compile.
- **Remedies:**
  - `run_robot` issues are ordered by how fundamental they are: one `BUILD_FAIL:<scenario>:<line>: <error>; did
    you mean '<X>'` per scenario, then failed checks plus `CHECK_EXPR`, then observability (suppressed for
    scenarios that do not build), then per-test and coverage lines.
  - The suite header and the test-author prompt state the LL mask naming convention.
  - Test: `test_build_failures_come_first_once_per_scenario_with_compiler_hint_r67` (real Renode run).

## Seventh live run (r68)
- **The new ordering reached the authors.** Build errors and failed checks with their expressions came first.
- **Two gaps were still uninformative:**
  - Link failures showed only `collect2: error: ld returned 1 exit status`.
  - `CHECK_EXPR` showed `st == HAL_ERROR` without the call that set `st`.
- **The run BLOCKED without a defect report.** The authors kept fixing an `scn_osc_enable.c` link error and an
  SWR-013 check that expected HAL_TIMEOUT in the default (ready) scenario.
- **Remedies:**
  - The scenario build keeps `undefined reference` lines and is compacted to `link: undefined reference to
    '<sym>'`.
  - `CHECK_EXPR` appends the last assignment of the checked variable: `st == HAL_ERROR with st =
    HAL_RCC_HSI_Enable(0U)`.
  - Test: `test_check_expr_shows_the_call_that_set_the_checked_variable_r68`.

## Eighth live run (r69) and owner decisions
- **17/18 requirements passed on the Renode target.** The first `run_robot` showed exactly the right failing check:
  `CHECK_EXPR:scn_ready_wait.c#9:rc == HAL_ERROR with rc = HAL_RCC_HSI_Enable(0U)` (SWR-014).
- **The author bent the test instead of reporting it.** It replaced the HAL_ERROR check with a register check
  (`REQUIREMENT_NOT_OBSERVED:SWR-014`), never called `report_defect`, and the phase BLOCKED. Anti-bending did not
  fire because the edited test never passed. r66 reported correctly; r67–r69 did not: the decision is not reliable
  with this model.
- **Owner decisions (2026-10-15):**
  - *Safety net* (L11): the decision no longer depends on the model when the evidence is unambiguous.
  - *Per-epoch rework budget*: `MAX_VISITS` 6 → 12; the governor's per-node token cap is per visit × `MAX_VISITS`.
- **Prompts:** the SWE.6 test author stops at "only driver checks that test what the requirement names fail"
  instead of "repeat until it PASSes"; both SWE.6 authors are told such a check is never changed, weakened or
  removed.

## Ninth live run (r70): both owner decisions exercised
- **SWE.6 reported the SWR-014 CODE defect itself** (DEF-001, first cycle). SWE.3 fixed it and the inspection
  passed (FIXED). The safety net did not need to fire.
- **The per-epoch budget worked:** SWE.3 had one failed cycle in epoch 1 and got 3 fresh cycles after loop 2.
- **The second loop was a wrong blame.** The SWE.4 unit-test author called `HAL_RCC_PLL1_Disable`, which does not
  exist, and filed an ARCHITECTURE defect on SWR-008 (a peripheral clock disable) with the invented "quote"
  `SWR-008: MSI disable.`. SWE.2 rejected it correctly, but its author re-ran its normal steps, re-froze the
  architecture and so cascaded into SWE.3. SWE.3 then BLOCKED: new inspection finding SWE3-06 and two
  turn-budget exhaustions.
- **Turn budget:** 5 of 7 author rejections in r70 were `TURN_BUDGET_EXHAUSTED (21>20)` (SWE.2 ×2, SWE.3 ×3).
- **Remedy (implemented):** ARCHITECTURE defects need a verbatim `requirement_quote` like CODE and TEST; the defect
  rule tells test authors that calling an undeclared function is usually their TEST error.
- **Owner decisions (2026-10-15):** L12 triage (no cascade on rejection); `max_turns` 20 → 35 for the SWE.2,
  SWE.3 and SWE.6 authors (inspectors unchanged; per-visit token budgets unchanged).

## Tenth live run (r71): triage and return chain exercised
- **L12 worked:** SWE.6 filed an ARCHITECTURE defect (DEF-001) and a CODE defect (DEF-002). SWE.2's triage rejected
  DEF-001 in 3 tool calls and the return chain resumed SWE.6 directly (no re-freeze, no cascade). SWE.6 then declared
  its test correction (DEF-003 TEST) and reported DEF-004 (CODE, SWR-013). SWE.3's triage chose FIX; SWE.3 fixed both
  defects with one rework cycle (FIXED).
- **SWE.4** passed after two cycles (one turn-budget exhaustion at 20 calls).
- **SWE.5 BLOCKED on anti-bending:** the SWE.3 fix changed behaviour, so two integration checks (IT-017, IT-021)
  failed; the author adapted the test without declaring it (`TEST_CHANGED_AFTER_FAIL` three times; visit 1 also ran
  out of its 20 calls). The control is correct (a fix can break a correct test), but the model never declares.
- DEF-002/DEF-004 stay FIXED (not VERIFIED) because SWE.6 was not reached again.
- **Owner decisions after r71 (2026-10-15):** L13 gate-declared post-fix adaptation; `max_turns` 20 → 35 for the
  SWE.4 and SWE.5 authors too (all authors except SWE.1 now 35; inspectors 20).

## Eleventh live run (r72): triage twice, then a 18/18 suite blocked by anti-bending
- **L12 worked twice:** SWE.3's triage rejected two pairs of SWE.6 CODE defects (SWR-014 timeout as "invalid
  parameter"; SWR-015 "at most 1000 iterations" read as a floor) with sound, quoted reasons, and the run returned to
  SWE.6 each time (no re-freeze). SWE.6 declared its corrections (DEF-003/004 TEST).
- **The suite reached 18/18**, but the author had edited two scenario files again after later failures without a new
  declaration, so the author gate rejected it (`TEST_CHANGED_AFTER_FAIL`) in the last cycle and the phase BLOCKED.
- **Factory bug found:** `Target Check Should Pass    26` passed with no TCHECK 26 in the scenario (the target only
  reports failed ids), so SWR-018 (stack ≤ 128 B) "passed" vacuously. The library had no stack keyword; the author
  invented two. **Fixed:** an undefined check id fails; new keyword `Driver Stack Should Be At Most` computes the
  worst-case call chain from gcc `-fcallgraph-info=su` (indirect callbacks charged the deepest direct chain; calls
  outside the driver, recursion, unbounded dynamic frames or an empty graph fail). r72's driver: 48 B.
- **Owner decision after r72 (2026-10-16):** L14 (option A): a TEST declaration covers later corrections of the same
  file on the same product code; the inspector checks the current version of every declared test file. Replayed on
  r72's integrity log (one code hash throughout, declarations at 21:22): no `TEST_CHANGED_AFTER_FAIL` remains.
  Tests: `test_loopbacks.py::…declaration_covers_later_corrections…_r72`, `…does_not_cover_corrections_after_the_code_changed`,
  `…legacy_declaration_without_code_hash…`.

## Twelfth live run (r73): cost cap reached; three factory gaps found
- **Run stopped by the gateway cost cap**, not by the factory: at 03:21 UTC the cumulative DeepSeek spend
  (all runs r37–r73 since 2026-10-15 06:52) reached the $2.00 cap and every agent call failed; Fabro ended the run
  on the repeated deterministic failure. Raised to $3.00 within the owner's autonomy grant (≈ $0.06 per run).
- **SWE.3 triage accepted SWE.6's SWR-014 defect** (out-of-range timeout must return HAL_ERROR) and SWE.3 fixed
  it in one cycle (FIXED). This is the opposite of r72's triage; both readings are defensible (requirement
  ambiguity between SWR-014 and SWR-015), and each owner decision is recorded with its reason.
- **SWE.4 blamed the code for its own test** (as in r70): the unit test called `HAL_RCC_PLL1..4_Disable`, which
  the API never declared, for SWR-008 (a peripheral clock register clause). Filed as CODE, the triage accepted it
  in 8 s and the last upstream loop was spent. **Fixed:** `report` refuses a CODE defect while the newest failing
  test run of the phase does not build because it calls functions no product header declares
  (`CODE_DEFECT_ON_UNDECLARED_API`, unless a SWE.3 source location is cited); a missing API is ARCHITECTURE with a
  verbatim clause.
- **A no-op fix was marked FIXED:** the SWE.3 fix author replied in prose without changing a file; the gate
  re-froze the same baseline (idempotent freeze) and the unchanged inspection marked DEF-002 FIXED. **Fixed:** the
  author gate rejects a freeze while an IN_FIX defect of the phase exists and no work product changed since it was
  handed over (`DEFECT_NOT_ADDRESSED`): fix it, or `reject_defect` with a reason.
- **Dead end for a wrong blame:** a FIXED defect is VERIFIED only with its cited test unchanged and passing; a
  reporter whose test was wrong could neither change the test nor pass it. **Fixed:** L15 withdrawal.
- Tests: `test_loopbacks.py::…undeclared_api_is_refused_r73`, `…fix_step_that_changed_nothing_is_not_frozen_r73`,
  `…reporter_withdraws_its_own_defect…`.

## Thirteenth live run (r74): first clean fix loop; SWE.5 blocked on a late anti-bending verdict
- **The loop worked as designed:** SWE.6 reported SWR-014 (`HAL_RCC_HSI_Enable(0xFFFFFFFFU)` returned HAL_OK),
  SWE.3's triage accepted it, the fix author made a real change (new baseline BL-SWE.3-002: a timeout above
  `HAL_RCC_TIMEOUT_VALUE` returns HAL_ERROR with no register write), SWE.3 and SWE.4 re-passed inspection on the
  first try.
- **SWE.5 BLOCKED:** on re-entry the integration author rewrote its test model before the first run; the rewrite
  failed (IT-001/002/004/005) and was debugged blind for three cycles, because `run_integration` reported only
  `IT-001 FAIL`. In the third cycle the test passed, but the author gate then rejected it as
  `TEST_CHANGED_AFTER_FAIL`, so the author never had a chance to declare it.
- **Remedies:**
  - `run_unit`/`run_integration` report `CHECK_EXPR:<file>#<id>:<expression> with <var> = <call>` for every failed
    `CHECK`, like `run_robot` (r64/r68); the expression lookup is shared.
  - **Anti-bending at tool time:** `run_unit`, `run_integration`, `run_renode` and `run_robot` return FAIL when
    every test passes but a test was edited after a runtime failure on the same driver code and not declared
    (`HOW_TO_DECLARE` + `UNDECLARED_TEST_CHANGE:<file>`), so the author declares or restores within the same visit.
    The gate check is unchanged; L13 post-fix adaptations are still declared by the gate. Replayed on r74: the
    03:40 integration PASS would have been reported as this FAIL inside the last cycle.
  - Tests: `test_m2_mcp.py::test_t014…` (real clang runs), `test_loopbacks.py::…undeclared_test_change_at_once_r74`,
    `…leaves_post_fix_adaptations_to_the_gate`.
- **Decision under the owner's autonomy grant (2026-10-16):** SWR-014's "invalid parameter" includes a timeout
  argument of 0 or greater than `HAL_RCC_TIMEOUT_VALUE` (valid range 1..1000, consistent with SWR-015's bound and
  with the fixes SWE.3 accepted in r66/r73/r74). The SWE.1 author prompt now names the invalid values (NULL
  pointer, unknown selector, timeout 0 or > `HAL_RCC_TIMEOUT_VALUE`) and the HAL author checks them before any
  register write. Runs resumed from r56 keep the old wording; a full run from SWE.1 applies the new one.

## Fourteenth live run (r75): two loops, both caught by the layers below
- SWE.6 reported SWR-014 again (resumed r56 wording); SWE.3 needed two fix cycles (one lost to a cppcheck MISRA
  10.6 finding) and then invented "1000 itself is invalid" (`HAL_RCC_TIMEOUT_MAX 999U`), contradicting SWR-015. The
  SWE.3 inspector passed it; **SWE.4's unchanged unit tests caught it** (UT-001/002 for HSI/HSE/MSI) and SWE.4
  reported DEF-002 (CODE) - the second loop; SWE.3 fixed it.
- **Over-strict verification:** the SWE.4 author added new tests (UT-059..) to the cited `test_rcc.c` before its
  first post-fix run, so no run ever used the cited version and `DEFECT_TEST_CHANGED` rejected a correct fix.
  **Fixed:** when the cited files changed, the gate verifies itself (`inspection/reverify.py`): a scratch copy of the
  workspace with the cited files restored byte-identical from the test snapshots, the fixed code and the test tool
  of each cited file. PASS = VERIFIED (`gate-reverify`), FAIL = `DEFECT_NOT_FIXED` (the fix does not make the
  reported test pass), unavailable snapshot = `DEFECT_TEST_CHANGED` as before. The edited copies stay subject to
  anti-bending. Replayed on r75: DEF-002 (unit) and DEF-001 (Robot on Renode) both PASS in 41 s.
