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
