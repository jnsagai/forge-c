# Validation — 24 October 2026

Runtime revisions and independent evidence are separate from this evidence-only documentation commit.

- Initial implementation `c008ba11d36e2e23b60c455115ac637a95cf7fd9`: exact-head targeted 41 passed; related regression on functionally equivalent `0960e6b` 294 passed, 3 live-only skipped. The c008 difference renames a ContextVar handle to remove a provenance-scanner false positive.
- Independent full-feature CRE against `360ad69`: `pd-f4cec1781f2bb1d1bc44`, ELIGIBLE_FOR_OFFLINE_REVIEW. All hard gates passed; all 72 frozen prevention symptoms absent; no model calls. Automatic deployment remains false.
- Provenance checks compared the private SafeC checkout and passed without findings. Static design and changed-file Ruff passed.
- Actual Omniverse host preflight passed inside the isolated local profile: exact Qwen digest, loopback-only network, verified denied external route, Bubblewrap confinement, no owner credentials/GPU devices exposed to verifier, 16-worker CPU capacity. See `omniverse-host-preflight-c008ba1.json`.

## Native activation and first observed failure

The owner-signed external policy verified AUTH_OK. Five existing RCC attempts were independently checked against their terminal native Fabro receipts and imported without launching new runs or copying accepted phases. All five packages are BLOCKED. The six-attempt cap leaves one product recovery attempt. The former blind retry launcher and its gpt-oss follow-on were stopped.

User services `forge-conductor-local-omniverse2.service` and `forge-qwen-mission-recorder.service` were enabled; owner-account linger was enabled so they survive SSH logout. The conductor reached healthy PILOT mode, then actually dispatched local Qwen planner `01M5QTF2X5M4WMSFKXPJ6KRHEJ`. This is live evidence, not proof of a successful repair.

The planner made five MCP calls. Its two submitted plans were rejected: overlong material_difference_ref/rationale_code, and initially wrong budget keys. The 120-character MCP issue limit clipped the error before the actual maximum-length constraint. Native Fabro then reported SUCCEEDED without a valid recorded compact reply; the conductor correctly retained the product BLOCKED but reported FileNotFoundError. The terminal order `afo-3f6e7e61ea3df31a` is preserved. Reported planner tokens: 15,507; reserved allowance: 16,000. No new product attempt was consumed.

## Corrective source revision

`a477a6d8676f7dc1f75bfef7b04be6eda280d860` preserves the original schema limits and places their diagnostic before the untrusted value. The tool input schema now explains the exact string bounds and budget keys. Native job success additionally requires a valid bounded recorded reply; missing/malformed/oversized replies become explicit FAILED jobs.

CAPA-069 records the native observation and frozen external reproducer. Independent contrast: c008 SYMPTOM_PRESENT; a477 SYMPTOM_ABSENT. CRE `pd-d87410a1bb6dc7eacd23` is ELIGIBLE_FOR_OFFLINE_REVIEW with protected/policy/reproducer/prevention/quality/golden/holdout all PASS. CAPA cause is VERIFIED, fix is FIX_CANDIDATE; operational effectiveness is not established. The external staged reproducer is hash sealed and its protocol matches the existing AFO Maintainer staging path. It has not been silently added to or substituted for a frozen prevention/holdout oracle.

Exact a477 related regression: **78 passed**. This includes the real MCP ticket/serialization boundary, actionable length feedback followed by a corrected accepted submission, and missing/malformed/oversized native output regressions. The initial check found a test fixture using an invalid next_action enum; it was corrected and the complete 78-case selection then passed. Ruff and provenance passed. Detailed XML, hashes and independent decision JSON are in `evidence/013-local-autonomous-recovery/`.

A qualified continuation keeps the original blocked order intact, adopts the same five historical product attempts, retains one remaining product attempt, deducts the first planner call from the four-call allowance, and deducts its full 16,000-token reservation. It requires a fresh signed grant bound to a477 and the continuation policy. Old workspaces stay immutable. No old accepted phases are eligible for cross-revision reuse.

## Overnight audit and limits

Progress commits use the separate branch `overnight/2026-10-24-qwen-omniverse2`; production source stays pinned. The recorder commits native state changes and periodic heartbeat/resource snapshots, and pushes that branch. It excludes raw prompts/reasoning, private manuals/vendor code and credentials. Its handoff names the requested morning Astra ultra review and asks for evidence-based improvements. It does not claim that a future assistant session has been scheduled.

Only mission inference/verification/supervision is authorized. The owner's later explicit exception permits a low-priority download of official `qwen3.8:27b-q8_0` for a future inspector test: one 8 MiB/s maximum stream, CPUQuota 20%, idle I/O, sequential content-addressed blob hashes checked before publishing its manifest. No inference or profile allowlist change is requested by that download.

RCC success means all six independent native SWE gates PASS and an intact hash-verified sealed READY archive. Fabro SUCCEEDED alone is insufficient. The selected genuinely new follow-on is STM32N6 GPIO LL, bounded GPIOA scope; it cannot launch until RCC succeeds and its own peripheral profile and authoritative frozen input package are ready. Those prerequisites are not yet qualified, so no GPIO launch or success is claimed. A blocked or exhausted run remains an explicit failure; no blind retry or gate relaxation is used to keep the GPU busy.

LA-T006 remains incomplete until measured operational recovery provides sufficient evidence. No SLO, model qualification, successful self-healing, safety compliance or automatic source promotion is claimed by these implementation tests.

## Structured contract correction

The a477 continuation planner `01M5QVAH97WCR7E9W0VPTSMK8Q` was correctly recorded FAILED after one schema-invalid plan and a prose final reply. It used 9,270 reported tokens against a 16,000 reservation and consumed no new product attempt. The parent `afo-2523e8cc245bf79b` remains terminal BLOCKED.

Inspection of actual MCP tool registration revealed that the shared SDK exposes annotations and drops Field metadata, so the earlier field-description hint was not transmitted. Source `335a2e0b326f40fd819d11753d7217566c6e702f` exposes the unchanged authoritative plan contract as a nested structured argument. The broker independently validates uncoerced values, scope, authority and budgets; legacy encoded input remains supported, ambiguous dual input is refused, and the existing 4,000-character bound remains. No shared SDK or contract/policy file changed. The native planner prompt also repeats the existing compact-output enum and issue limit.

Exact related regression: **82 passed**. It compares the actual registered MCP schema to the authoritative contract and exercises typed valid, numeric-version-invalid, string-budget-invalid and ambiguous submissions through real authorization tickets. CAPA-070's sealed external registration reproducer is present on a477 and absent on 335. Independent FIX CRE `pd-be298db3a11459345cda` is ELIGIBLE_FOR_OFFLINE_REVIEW with every hard gate PASS. CAPA-070 is CAUSE_VERIFIED, not operationally EFFECTIVE. Provenance and Ruff passed.

Continuation v3 deducts both earlier planner calls and their full 32,000 reserved tokens (24,777 reported). It retains two remaining diagnosis calls and one product attempt, preserving all prior terminal records and the five historical product receipts. Its exact source/policy owner grant expires at the same 09:00 UTC deadline. Activation and native progress must be read from the remote receipts; the qualification itself is not proof of successful product recovery.

## Diagnosis context and final bounded continuation

The v3 native planner reached its token allowance after three reads and no submitted plan. Reported use was 16,856 against a 16,000 reservation; a poll detected the overrun and requested cancellation. Parent `afo-7c96f1e5c47b7bb2` remains BLOCKED. This is neither a successful diagnosis nor an implementation attempt.

Single-role jobs were also advertising every product SKILL because the generic workspace builder copied them all. Runtime candidate `36ed0fc70bd8765f0cc90a45b21bbf02924b0269` optionally omits default product SKILLs and baselines only the same locked AFO role SKILL. Existing product callers retain the same default. No role instructions, grants, evidence, model settings, token/turn bounds or quality criteria changed. CAPA-071's frozen external workspace check observes the exposure on335 and its absence on36ed. This proves corrected workspace scope, not model speed or convergence.

V4 retains the original four-call diagnosis allowance: three calls consumed, one left. Conservative previous capacity is 48,856 tokens (maximum of reserved/reported use per call), against 48,000 reserved and 41,633 reported. This amount is deducted in the continuation policy. The five original product receipts still count toward six total attempts; one implementation recovery remains. No further replacement order may reset these bounds. All earlier terminal orders are retained. A failed final diagnosis remains BLOCKED for morning review.

Exact36ed checks: **51 passed / 1 live-only skipped** for local autonomy plus native Fabro capabilities; **25 passed / 2 live-only skipped** for existing MCP/policy workspace callers. Independent FIX CRE `pd-78232fccefedf68697fa` is ELIGIBLE_FOR_OFFLINE_REVIEW, every hard gate PASS. The frozen workspace reproducer is present on335 and absent on36ed; CAPA-071 is CAUSE_VERIFIED, not operationally EFFECTIVE. Provenance passed with zero findings. These results do not establish that the final diagnosis call will converge.

## Final measured outcome

V4 order `afo-dabbb015814e03ed`, planner `01M5QWC6CP1BJKGXKEXWG6HXHM`, also ended **BLOCKED**: three successful MCP reads, no submitted broker plan, no valid compact exit. The job reported 13,071 tokens within its 16,000 allowance; the deployed workspace advertised exactly the one locked planner SKILL. All four original diagnosis calls are now consumed. Total reported diagnosis tokens are 54,704; reservations total64,000, with an observed856-token overrun on call3. Conservative capacity consumed is64,856. No new product implementation attempt was launched. The original five RCC product packages remain BLOCKED.

The conductor and recorder remain enabled for audit; an active daemon is not active inference or a successful repair. No further diagnosis/model trial or blind retry is scheduled. The separate permitted Qwen3.8 Q8 download continues. Successful autonomous recovery, overnight convergence and the conditional GPIO implementation are **not demonstrated**. LA-T006 remains open. Morning review must examine the native completion/turn-limit behavior and planner contract handling, then propose improvements within explicit future bounds rather than resetting these records.
