# Feature 010 local RTX trials (profile local-rtx-v1)

Host: RTX 4070 Laptop 8 GB, i9-14900HX, 32 GB RAM. Every agent node runs on qwen3-coder:30b
(digest 06c1097e…, Q4_K_M) through the profile's own Ollama, admission gateway and Fabro server. These run inside
a user+network namespace with no external interface. No ACP and no cloud model were used.

## lrtx1 — baseline on the existing (monolithic agent) graph, factory cb89135, 2026-10-21 11:31–12:31 UTC

`WO-0009A-STM32N6-IWDG-LL-lrtx1`, `--profile local-rtx-v1 --model qwen3-coder:30b`, timeout scale 4 (profile).
Result: **BLOCKED at SWE.1** after 5 failed cycles (rework budget 3 + 2 progress extensions), 49 gaps.

| SWE.1 attempt | Deterministic rejection |
| --- | --- |
| 1 | SAFETY_SCOPE: QM claim in the ASIL B scope (safety statement) |
| 2 | CONTRACT_CASE_ID: duplicate effect case QUERY_WATCHDOG_STATUS |
| 3 | STARTUP_INVARIANT_ON_HOST_TEST: SWR-010 mapped to a host unit test |
| 4 | SAFETY_SCOPE: QM claim again |
| 5 | CONTRACT_CASE_ID again |

The QWEN-TRIAL GPU runs recorded the same failure classes; they are triaged in `../LRTX-T016-REPLAY/replay.json`.

Run verification (`lrtx1/verify.json`, `python -m forge_factory.lrtx.verify_run`): PASS on all eight checks:
- the profile is recorded;
- ACP was rejected and no ACP node exists;
- the network denial was observed (`DENIED_VERIFIED`, interfaces `lo` only);
- the model digest matches the profile;
- the roots are isolated;
- the Fabro providers are local loopback;
- admission metrics are present;
- the package is sealed.

Measurements: 93 model calls with a median prompt of 14,585 tokens (p95 20,754, max 22,568), 1,275,108 input and
18,357 output tokens, one model load of 76 s. Stage records show 3,486 s of inference and 54 s of tool time.
Two limitations of these measurements:
- **Single-chunk answers:** this run used the gateway of cb89135, which recorded the first-delta time as "prefill"
  even when the answer (a tool call) arrived in one chunk (69 of 93 calls). Later gateway code labels those
  UNKNOWN.
- **Queue waits:** these (max 220 s) include three capability-probe calls of the operator interleaved with the run.

## Fabro 0.362 probes (throwaway server in the profile namespace)

1. A command node's stdout is **not** available as `context.response.<node>`. The error was "stdin_source
   'context.response.a' was not found in workflow context". Structured runners therefore persist their reply and
   the gates read it by pipe (ADR-0014).
2. A command node with no activity for 1800 s is ended by the **stall watchdog**: "Stall watchdog timeout node=c
   idle_seconds=1800", then the run failed. Structured runners print one progress line per model call. Whether
   output counts as activity is probed separately (`fabro-probes.md` once complete).

## Host observation

With qwen3-coder:30b loaded (the `llama-server` resident set was 13 GB) and other owner workloads running, swap was
exhausted. The CRE promotion sandbox then failed to compile its reproducers (decision pd-7f4521cc52c2676c4638,
REJECTED, RESOLVED_FAILURE_REAPPEARED with build failures). The same candidate line was ELIGIBLE after the local
model was unloaded (pd-b6853328caf1e2190ecf). Local inference and factory verification compete for host memory on
this 32 GB machine; scheduling must keep them apart.

## lrtx2 — first structured SWE.1/SWE.2 run, factory eedfb5f, 2026-10-21 12:44–12:55 UTC

`WO-0009A-STM32N6-IWDG-LL-lrtx2`, same profile and model. SWE.1 author = structured tasks (ADR-0014).
Result: **BLOCKED at SWE.1** after 11 minutes (STUCK: identical rejection twice).

- **Tasks:** all six SWE.1 tasks became VALID with local repairs (`swe1-packets/`). Prompts were 2,221–3,884 tokens,
  against a median of 14,585 in lrtx1. The register tasks KR, SR_2 and cross-cutting were valid on the first answer;
  PR needed 2 repairs, RLR 1 and SR_1 1. That is 10 model calls and about 7 minutes of model time.
- **Why the visit failed:** the cross-task consistency check failed. Three register tasks each repeated the startup
  invariant ("While no LL function has been called after reset ...") that belongs to the cross-cutting task. The
  visit therefore assembled nothing and replied FAILED.
- **Why it became STUCK:** the presence gate rejected first (missing outputs), so the visit's own findings never
  reached the gate log. The next visit had no findings, reused every checkpoint (11 s, no model call) and failed
  identically; the route gate stopped the phase as STUCK.
- **Factory defects found and fixed** in candidate bce3fe8 (pd-d781f1137dd1bb01c34d):
  - register tasks may not carry cross-cutting requirements (instruction plus a deterministic rule);
  - consistency findings are repaired in the task that must change, within the visit;
  - a FAILED visit's issues carry into the next visit;
  - findings are routed by the task they name.
- **Graph wiring:** the structured graph ran as designed (author -> time-box check -> gate -> route -> direct
  re-inspection check -> author).

## lrtx3 — structured SWE.1 with the lrtx2 fixes, factory bd644c9, 2026-10-21 12:59–13:11 UTC

Result: **BLOCKED at SWE.1** (STUCK after two visits, 12 minutes).
- The new rules repaired the startup invariant inside the register tasks and the cross-cutting task locally (KR,
  cross-cutting).
- Two tasks stayed INVALID after their 2 repairs in both visits, with falling finding counts:
  - **IWDG_PR** went from 4 to 3 to 2 findings: it kept adding write-access requirements that act on IWDG_KR.KEY.
  - **IWDG_SR_2** had requirements with 2-3 "shall" each; the bare EARS code told the model nothing.
- **Why STUCK:** the route gate compares the author rejections, and a visit that fails before assembly always
  produces the same presence rejection ("missing outputs"). The two visits therefore looked identical although their
  validated task issues differed.
- **Fixed** in e33a015 (pd-5bfcdeabbcc430990d29):
  - in-visit repair rounds, plus a bounded extension while findings fall;
  - actionable EARS and wrong-register findings;
  - for profile runs only, the runner's task issues join the author rejection record as `LRTX_TASK_INVALID:` codes, so
    STUCK compares real progress (the default and ACP lines are unchanged, as the frozen fixtures and tests show).
- **Also in e33a015:** structured SWE.3 for LL (unit code tasks and rendered design), tested against the real tools
  and the unchanged SWE.3 gate with scripted answers.
- **Rejected attempt:** decision pd-eca007977bf687460693 (REJECTED, PROTECTED_PATH_CHANGE) was an operator error.
  The first candidate commit included this evidence directory; it was recommitted without evidence before promotion.

## lrtx4 — factory 4393ca0, 2026-10-21 13:15–13:37 UTC: SWE.1 frozen three times, blocked at inspection

Result: **BLOCKED at SWE.1** after 5 failed cycles (22 minutes). The structured SWE.1 author was **frozen by the
unchanged deterministic gate three times** (BL-SWE.1-001..003). Each task was valid after at most one or two local
repairs (`swe1-packets/`), at about 10 minutes for the first visit.

- **Requirements quality (`software_requirements.md`):** structurally valid, semantically weak.
  - SWR-001 conflates starting the watchdog with refreshing it (0xAAAA).
  - SWR-007/009/010 cover IWDG_SR.EWIF/EWU/WVU, which the scope excludes (early wake-up interrupt, window option).
- **The structured Qwen inspection (INS-SWE.1-001/002):** failed SWE1-01..06, mostly with false findings:
  - it judged the owner's recorded PENDING allocation as a failure;
  - it claimed missing verification criteria that the document has;
  - it did not name the real defects above.
- **Then a factory defect blocked the run:** the inspector's answers echoed the packet's `SOURCE <path>` labels, and my
  validator rejected them three times per item. No inspection was recorded; the direct re-inspection path (LRTX-T018)
  worked, but the cycles ran out.
- **Fixed** in deaf6d3 (pd-118fefed910713a2dcfc):
  - source labels are accepted;
  - inspector findings refuted by the evidence or by the owner's decision go back to the inspector;
  - SWE.1 tasks receive RM field descriptions and out-of-scope hints;
  - explicitly excluded registers are a hard rule.
- **Same candidate:** structured SWE.4 and SWE.5 (LL), tested with scripted answers on the real tools, Renode and the
  unchanged gates.

## lrtx5 — factory 8e58c0b, 2026-10-21 13:43 UTC: refused by Fabro before launch

Fabro refused the generated workflow ("grammar error ... code: Char"). The structured-node swap replaced only the
first line of the SWE.4/SWE.5 agent prompts, whose unit-test code examples span several lines (the CAPA-051
pattern); the rest of the old statement was left in the graph. No agent ran and no model call was made.
`fabro validate` reproduces the refusal on the saved graph and accepts the fixed one (90 nodes, 138 edges). Fixed in
c888bdb (pd-7cc602f15599ef85ae35). Tests now check the statement shape and run `fabro validate` on every
profile-graph variant.

## lrtx6 — factory 7b19177, 2026-10-21 13:47–14:21 UTC: ended by Fabro's failure-cycle breaker at SWE.1

`verify.json` PASS (8/8 isolation and accounting checks); package BLOCKED (56 gaps); 34 model calls in three SWE.1
visits; median prompt **3,951 tokens** (lrtx1 monolithic: 14,585); GPU board energy 14.4 Wh, sample coverage 100 %
(`metrics.json`).

- **Model quality:** none of the three visits assembled.
  - The IWDG_SR task kept a reset-state requirement whose effects named PVU/RVU/WVU in all three visits.
  - In visit 2, the cross-cutting task added status-flag queries (ONF/EWU/EWIF) that the IWDG_SR task covers.
  - The route gate reported REWORK with measured progress, not STUCK.
- **Factory defect:** Fabro ended the run (`fabro-termination.txt`) before the route gate's budget was exhausted.
  - Cause: the direct re-inspection check exited 1 with the identical output "no baseline" on each cycle, and Fabro's
    breaker stops at three identical signatures (ADR-0005 #5).
  - The continuation check already printed a digit-free counter to avoid this; the re-inspection check did not.
- **Fixed in the next candidate:**
  - the re-inspection check prints a digit-free per-phase counter;
  - reset/startup requirements must move to the cross-cutting task;
  - the cross-cutting task may not carry requirements on registers that a register task covers.

## lrtx7 — factory 5aaa229, 2026-10-21 14:44–15:07 UTC: SWE.1 frozen twice, blocked by inspection defects

Run summary:
- `verify.json` PASS (8/8 checks); package BLOCKED (52 gaps).
- 39 model calls in 23.5 minutes, 10.0 Wh GPU energy at 100 % sample coverage (`metrics.json`).
- Median prompt over all calls 6,114 tokens: the inspector packets carry the full frozen work products. The author
  calls stayed between 2,084 and 4,043 prompt tokens (`visits.jsonl`).

- **Author: the first local trial frozen on its first visit.** The structured SWE.1 author passed every task
  validator and the unchanged author gate froze BL-SWE.1-001 after 13 calls (11 minutes), then BL-SWE.1-002 on the
  rework visit after 3 calls.
- **Real defect, missed:** SWR-012..014 say the driver "shall set" IWDG_SR.WVU/RVU/PVU. These are hardware status
  flags that RM0486 marks read-only, and neither the task validator nor the Qwen inspector caught it.
- **Inspection (`inspection/`, `inspections.jsonl`):**
  - Visit 1 ended FAILED: the fact check returned SWE1-05 (the owner's PENDING allocation judged as a failure) until
    the item's repair limit. The direct re-inspection (LRTX-T018) then recorded INS-SWE.1-001 with one more call.
  - INS-SWE.1-001 failed SWE1-01/03/04/05/06, mostly with false findings:
    - the recorded NOT_PROVIDED HSI and budget gaps judged as failures;
    - test files and measurements demanded at SWE.1;
    - "no reset/startup behaviour" although SWR-015 specifies it.
  - The Claude inspector passed the same items on rc1 with the same recorded gaps.
  - Visit 3 judged all six items, but `check_inspection` refused the record: one item had more than 10 findings, which
    the operation's contract does not allow. The lost record was the third failed cycle, and the unchanged route gate
    BLOCKED the phase.
- **Fixed in the next candidates:**
  - SWE.1 effects may not write, set or clear a read-only RM field;
  - findings refuted by the recorded gaps, by later-phase evidence or by the document's startup rule go back to the
    inspector (real defects are kept);
  - the inspector task schema caps findings at 10, and the structured validator now enforces `maxItems`/`maxLength`;
  - a refused record is a FAILED reply with its reason.
- **Rework budget:** the owner offered to raise it (2026-10-21). It is unchanged: LRTX-FR-014 keeps the phase rework
  criteria, and the cycles lrtx7 lost were factory defects that a larger budget would have hidden.

## lrtx8 — factory d259a36, 2026-10-21 15:20–15:34 UTC: SWE.1 frozen, all cycles lost to unrecorded inspections

Run summary:
- `verify.json` PASS; package BLOCKED (49 gaps).
- 43 calls in 14.5 minutes, 7.5 Wh GPU energy at 100 % sample coverage.
- The probed json_schema mode was used (T012).

- **Author:** the structured SWE.1 author was frozen by the unchanged gate on its first visit (12 calls) for the
  second run in a row. The IWDG_SR status flags are now specified as reads (return 1U/0U); none is written.
- **Inspection:** all three visits ended FAILED and recorded no verdict, so the route gate counted three failed cycles
  and BLOCKED.
  - The Qwen inspector kept the findings that the evidence refutes through every repair: the recorded NOT_PROVIDED
    HSI gap, the owner's PENDING allocation, and a denied startup rule.
  - Each such item stayed invalid, and the visit was incomplete.
  - One refutation was wrong: a safe-state/failure-handling finding that acknowledged SWR-014 matched a loose startup
    pattern.
- **Fixed in the next candidates:**
  - an item whose only remaining errors are refutations is recorded as given, with all its findings
    (LRTX-FR-015);
  - the refutations are recorded beside it as contested;
  - the startup rule now matches only a finding that denies startup behaviour within one clause, without naming the
    startup requirement.

## lrtx9 — factory b7aef39, 2026-10-21 15:43–16:13 UTC: three recorded inspection FAILs, no cycle lost to the factory

Run summary:
- `verify.json` PASS; package BLOCKED (53 gaps).
- 61 calls in 26.4 minutes, 13.5 Wh GPU energy at 100 % sample coverage.

- **Author:** frozen on the first visit for the third run in a row (15 calls). Then 2 calls in each rework visit.
- **Inspection:** INS-SWE.1-001..003 were all recorded. The contested-verdict recording from lrtx8 worked: no visit
  ended without a record.
  - The refuted findings were preserved and marked contested (`inspection-record.json`).
  - Cycle 2 made progress: SWE1-04 and SWE1-05 passed.
  - In cycle 3 they failed again. SWE1-03 still said startup behaviour is missing while SWR-020 states it.
  - The Qwen inspector is unstable between visits on the same evidence; the profile records it as NOT_QUALIFIED.
- **Author defects the validation missed, now fixed:**
  - A repaired cross-cutting answer rewrote the IWDG_KR key writes with effects, which duplicated the register task.
    The duplicates had different wording, so they slipped past the identical-statement check.
  - In cycle 2 that repair also dropped the startup invariant. SWE1-03 was then a true finding.
  - The cross-cutting task may no longer act on a register that has its own task, and must keep the startup
    invariant.
  - Consistency also catches the same write (same field and value) in other words.
- **Inspector packets:** each structured SWE.1 item now carries the owner-scope note, which the agent inspector reads
  once for all items. Before, only SWE1-01 had it, while SWE1-05 judged the same gaps.

## lrtx10 — factory 1d1fc8a, 2026-10-21 16:22–17:23 UTC: author stable, blocked by the inspector

Run summary:
- `verify.json` PASS; package BLOCKED (52 gaps).
- 63 calls in 61 minutes, 19.9 Wh GPU energy at 100 % sample coverage.
- Median prompt: 5,832 tokens.

- **Author:** frozen on the first visit for the fourth run in a row (12 calls). Each rework visit took 2 calls. No
  author gate rejection.
- **Inspection:**
  - INS-SWE.1-001..003 were all recorded; no cycle was lost to the factory.
  - The second inspection used its time box once (CONTINUE) and took 36 minutes.
- **Inspector findings (model quality, not a factory defect):** after a refutation, the Qwen inspector kept the
  finding and reworded it.
  - "PENDING owner allocation review" became "without an approved safety allocation" or "lacks an approved safety
    allocation". It then carried the same objection under SWE1-02, -05 and -06.
  - SWE1-03 kept reporting missing safe states and failure handling.
  - SWE1-04 was resolved in cycle 3.
  - More wording rules would only chase the model's phrasing. The structured inspector stays NOT_QUALIFIED, as the
    profile records, and no further refutation patterns are added.
- **Shared route gate defect (outside feature 010; reported to the owner, not changed here per LRTX-FR-019):**
  - The cycle-3 route computed the owner's progress extension (`rework-policy.yaml`, 2026-10-18) with
    `progress: true` (SWE1-04 resolved, 5 -> 5 findings).
  - It still returned BLOCKED, because `Store.gate` already decides BLOCKED once `failed_inspections` reaches the
    checklist maximum.
  - So the extension only ever applies to author-gate cycles; every extended cycle in earlier evidence had
    `failed_inspections: 0`. It affects the Codex/Claude line in the same way.

## lrtxq1 — QM experiment, factory c31bda9, 2026-10-21 19:49–19:59 UTC: one inspector finding left; rework cycles burnt

- **Work order:** example `0009q-iwdg-ll-qm`, the 0009a IWDG LL work order under the owner QM scope
  SC-IWDG-QM-2026-10-21 (OD-2026-10-21-01).
  - It is not part of the T024 campaign and not comparable with the ASIL B line.
- **Run summary:** `verify.json` PASS; package BLOCKED (48 gaps). 22 calls in 9.5 minutes, 4.5 Wh GPU energy at
  100 % sample coverage.
- **Author:** frozen on the first visit (13 calls). The safety file states the QM scope as the author instructions
  prescribe.
- **Inspection:**
  - 7 of 8 SWE.1 items PASS on the first inspection, including SWE1-01, SWE1-02, SWE1-05 and SWE1-06, which failed
    in every ASIL B run.
  - The only finding is SWE1-03: "no failure handling or safe states specified". The rc1 work order has the same
    content (one reset/startup requirement, no failure-handling requirement), and the Claude inspector passed
    SWE1-03 on it at the first inspection.
  - So this is the local inspector being stricter than the reference inspector, not a defect of the work products.
- **Factory defect (structured rework):** cycles 2 and 3 were each spent in about 10 seconds without any change.
  - The SWE1-03 finding names no requirement, so it was routed to the cross-cutting task.
  - The model returned the same answer in one call (5.7 s), and the unchanged validator accepted it.
  - The identical baseline BL-SWE.1-001 was frozen again, and the inspection reused its verdicts for that baseline
    (0 calls).
  - The cross-cutting instructions only ask for the reset/startup behaviour and the coverage rules, so the task has
    no stated place for a failure-handling requirement.
  - A rework visit that leaves every answer unchanged should not count as a reworked baseline.

## lrtxq2 — QM experiment, factory fa1e7fa, 2026-10-21 20:12–21:03 UTC: real rework, unstable inspector

- **Work order:** the same QM example and scope as lrtxq1. The factory now includes pd-9a54ade5e46db037f847:
  - an unchanged answer to rework findings is not accepted;
  - the cross-cutting task owns the failure handling the scope states.
- **Run summary:** `verify.json` PASS; package BLOCKED (51 gaps). 41 calls in 50 minutes, 16.2 Wh GPU energy at
  100 % sample coverage.
- **Author:**
  - It froze on the first visit (12 calls) and reworked in 2 calls and 1 call.
  - Every rework produced a new baseline (BL-SWE.1-002, -003), so no cycle was spent on an unchanged baseline. The
    model changed its answer on its own; `LRTX_FINDING_NOT_ADDRESSED` never fired.
  - It added SWR-015 (no waiting on status flags; the caller bounds polling) and an open point on SWE1-03.
- **Inspection:**
  - INS-001: 7/8 PASS, only SWE1-03 (safe states), as in lrtxq1.
  - After the change, INS-002 and INS-003 failed 4 items (SWE1-02, -03, -04, -06) and called the unchanged budget
    requirements unverifiable or not measurable. INS-001 had passed those requirements on the same evidence.
  - The local inspector's verdicts change with the document's wording and between visits, the instability already
    seen in lrtx7–lrtx10. It stays NOT_QUALIFIED.
- **Gate:** the cycle-3 route computed the owner's progress extension with `progress: true` (3 items resolved) and
  still returned BLOCKED. This is the shared route gate defect recorded under lrtx10.
