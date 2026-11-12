# Targeted re-review of revision 4 (EGM Goldfish)

Target: `docs/designs/forge-c-process-first-ornith-qwen.md` revision 4 (1,417 lines), 2026-10-31. Revision 3 is kept
as `design-r3-as-reviewed.md`. Three fresh native reviewers were given `targeted_rereview_r3_report.md` and the
Ornith protocol README as context.

## Status of the revision-3 open items (all three reviewers agree)

| Item | Status |
|---|---|
| B1 Mission limits / deadline | PARTIAL → Major: request, tool and token floors unstated; queue wait inside a batch eats the per-order wall budget; deadline must also be ≤ grant expiry |
| B3 Group documents / REWORK checkpoints | **RESOLVED** |
| B5 Trial binding | PARTIAL → Major: `authorization_ref` must name the qualification grant itself, which is signed after the trial exists, with one grant per trial |
| N1 Profile composition | **RESOLVED** (`fabro_config` passes; no inherited reasoning flags) |
| Handoff transport / relative paths | **RESOLVED** |
| Owner-contract leakage | **RESOLVED** |
| Grant vs trial IDs, node write bindings, `max_visits`, gate-FAILED sources, scorer input, signing load, record host, state across exec | **RESOLVED** |

## New Blocker (all three reviewers)

- **Policy authorization.** The per-experiment policy keeps the production `authorization_ref`. Its new sha is not
  bound to that grant, so `policy.load` drops to OBSERVE_ONLY (`policy.py:109-111`, `authz.py:88-89`). Mission
  registration, submit and launch are then all refused. The fix needs its own policy grant (`launch_workorder` +
  `recover_workorder`, scoped to the `pl-` IDs and the model keys) and a defined signing order:
  1. reserve the grant IDs;
  2. write the policy naming its grant;
  3. sign grants that carry the policy sha;
  4. write the trial naming its qualification grant;
  5. sign the qualification grant with `signed_runbook_ref`.

## Remaining Majors (deduplicated)

- **Code revision (D11):** the production checkout's HEAD must be at the lab commit (trial and admission revision
  checks), and `activate`/`--restore` must move and restore it.
- **Qwen 65K context** is unproven for xhigh inspection with 32K extra output, which risks `CAPABILITY_LIMIT` in one
  arm only.
- **Activation edge cases:**
  - step 8 contradicts step 10;
  - `--restore` sequence undefined;
  - a foreign STOP vs managed `stack.stop`;
  - `model_identity` cannot reach Ollama from the host namespace.
- **Ornith argv** is not the measured S3 form (`--fit off`, `--spec-type none`, `--metrics` absent).
- **Cross-cutting rework wording** is wrong: with findings, it is a localized repair.
- **Terminal reasons and retries** do not cover BLOCKs before `verdict` (preflight, RUN_ABSENT, deadline).
- **Dispositions:** obligation-only `NOT_COVERED` dispositions persist across reworks.

---

## Raw report — `egm-design`

# Targeted re-review of revision 4 (Design Critic Goldfish, Mode REVIEW)

**Target:** `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md`, lines 1–1096. The section "Detailed Implementation Plan" starts at line 1097; I read it as context only. `ff/` = `factory/python/forge_factory/`.

**Inputs read:** the persona, the feature-spec standard, the r3 re-review report (consolidated tables and all three raw reports), the Ornith protocol README, the constitution, the PROCESS-FIRST plan (§2–§5), SOURCE-INVENTORY and the target. I checked every item below against the code. The review is complete.

**Verdict: not ready to approve.** Revision 4 fixes most r3 items correctly, including the r3 profile Blocker. But it adds one new Blocker: the per-experiment policy, as specified, can never become effective PILOT. Four Majors also remain open or are new.

## Status of the open r3 Blockers

| # | Item | Status | Evidence |
|---|---|---|---|
| B1 | Mission limits and deadline | **PARTIALLY RESOLVED (now Major)** | See below |
| B3 | INSPECT group documents, REWORK checkpoints | **RESOLVED** | See below |
| B5 | Trial `authorization_ref` and context allocation | **PARTIALLY RESOLVED (now Major)** | See below |
| N1 | Profile composition | **RESOLVED** | See below |

**B1. Mission limits and deadline.**
- **Resolved:** one mission per order (design 430–444) fits the code:
  - `validate_limits` accepts 0, so `max_corrections: 0` is valid (`ff/afo/mission_ledger.py:20`);
  - `max_attempts: 1` and `max_jobs: 1` fit within the caps at `ff/afo/mission_admin.py:43-58`;
  - a deadline computed per order matches `ff/afo/overnight.py:33`.
- **Residual Major:** the policy's request and tool caps are never stated.
  - `max_requests` and `max_tools` are capped by `budgets.max_inference_requests_per_order` and `budgets.max_tool_calls_per_order`. When those keys are absent, the cap defaults to `max_recovery_model_calls_per_order × 8` (`mission_admin.py:49-50`).
  - The repository policy has neither key and has `max_recovery_model_calls_per_order: 4` (`config/factory/afo-policy.yaml:34-42`), which gives a cap of 32.
  - Design 496–497 copies the production policy "unchanged" apart from the token cap, yet SWE.1 allows 256 author calls (line 871).
  - **Fix:** state minimum values for both keys in the per-experiment policy.

**B3. INSPECT group documents and REWORK checkpoints.**
- In INSPECT, the group documents are carried forward unchanged (610–611).
- `materialize` writes VALID checkpoints whose `base_hash` is the base packet's `input_hash`, built in this workspace (622–626).
- That is exactly what `visit.run_task` needs:
  - reuse on an unchanged base (`ff/lrtx/visit.py:166-169`);
  - `start = prev doc` when findings exist (`:173-174`).
- The packet identity includes the role effort and the profile sha (`ff/lrtx/structured.py:84-98`). `materialize` is bound to `swe1-author`, so its hash matches the later author node's hash.

**B5. Trial authorization and context.**
- **Resolved:** both lab contexts are ≤ 65536, so no allocation is needed (`ff/afo/product_role_trial.py:55-57`).
- **Residual Major:** the grant signing order contradicts the code (see M-2 below).

**N1. Profile composition.**
- The rule is now "replace whole top-level blocks". The `runtime` block lists every key the production profile has (`config/factory/profiles/local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector-capacity.yaml:26-46`).
- `stack.fabro_config`'s checks pass for both profiles (`ff/lrtx/stack.py:126-130`).
- Ornith has no `reasoning_effort`, so `--reasoning-effort` and `--reasoning-format` are not emitted (`stack.py:408-409`).
- Note only: line 892 claims the argv is the measured S3 form. The code's argv (`stack.py:400-411`) leaves out `--spec-type none`, `--fit off` and `--metrics` (README:39), and its alias differs.

## Status of the open r3 Majors

| r3 Major | Status | Evidence |
|---|---|---|
| Copied relative input paths | **RESOLVED** | Rewritten with `relpath` (311–314); seq 1 is written by `provision` (310). Note: the "upstream reference" is not a path. `load_upstream` reads the fixed `upstream/upstream-inputs.yaml` inside the example folder (`ff/upstream.py:17,32`), so that file must be copied, not rewritten. 0014g has no such file. |
| Health failure vs. `stack.stop` epoch | **PARTIALLY RESOLVED** | The health path ends STOPPED at E3 (572–574), which matches `stack.py:700`. Step 8 still contradicts itself: "pauses with expected epoch E2" (567) vs. "same procedure … with E3" (577). |
| Policy and grant install | **PARTIALLY RESOLVED** | Install step added (553–555). But the installed policy cannot be effective PILOT (Blocker NB-1). |
| Unit text | **RESOLVED** | 556–559 matches `ff/afo/services.py:105-122`. |
| Deployment root | **RESOLVED** | D11 (169–174, 532–533). `_managed_scope` compares roots resolved from the same `FORGE_LRTX_ROOT` (`stack.py:424`). |
| Owner contract leakage | **RESOLVED** | 935–952 removes everything at `examples/0014g-st-crc-idr-qwen-delivery/IDR-CONTRACT.md:27-41`, and a phrase test is added. |
| Grant IDs (`pl-`) vs. trial IDs (`afo-`) | **RESOLVED** | 426–429 matches `ff/afo/cli.py:43`, `ff/afo/local_agent.py:62-64` and `product_role_trial.py:40`. |
| Node write bindings | **RESOLVED** | The command nodes are not agents (377–380). That matches the builder: gates are not in `nodes` (`ff/workflow/builder.py:354-357`). |
| `max_visits` | **RESOLVED** | 392–394. |
| Gate-FAILED handoffs | **RESOLVED** | 386–391. |
| Scorer has no work-order input | **RESOLVED** | The `scope` file is in the handoff (685–686, 746). Leftover wording at 754 still says "work order's budgets". |
| No re-attempt path | **PARTIALLY RESOLVED (Major)** | See M-3. |
| Disposition signing load | **RESOLVED** | Dispositions are bound to statement hashes (733–737). |
| Activation record on the wrong host | **RESOLVED** | 579. |
| State lost across `os.execv` | **RESOLVED** | 528–531, 563. |
| Outcome precedence | **RESOLVED** | 520–527. Minor leftover: step 7 says "left PAUSED" (565), which conflicts with "left as the other writer set it" (526). |

## New findings

**NB-1. Blocker: the per-experiment policy keeps the production `authorization_ref`, so PILOT never takes effect (design 489–499, 207–210, 553–555).**
- **What the code requires:**
  - PILOT takes effect only if the policy's own `authorization_ref` names a grant bound to *this* policy's sha256 (`ff/afo/policy.py:107-111`, `ff/afo/authz.py:88-89`).
  - `launch_workorder` and `recover_workorder` are also decided against the policy's `authorization_ref` (`ff/afo/authority.py:67`, `ff/afo/scheduler.py:207`, `local_agent.py:73`, `ff/afo/runtime.py:113`).
- **What the design says:** three changes, then "Everything else is copied unchanged". That keeps the production reference (`AUTH-AFO-PILOT-…`, `afo-policy.yaml:12`), whose grant is bound to the production policy sha.
- **What happens:**
  - The effective mode becomes OBSERVE_ONLY.
  - Step 5's assertion that the mode is PILOT fails mid-install. By then the units, the provider and Fabro are already stopped, and none of the step-12 outcome codes covers this case.
  - If the assertion were skipped, `mission_admin.register` would refuse (`mission_admin.py:18-19`), and so would `approve` (`cli.py:36-37`).
- **"Signing" is misdescribed:** a policy is never signed. A grant is bound to its sha, and that sha includes `authorization_ref`.
- **Fix:**
  1. Add a fourth change: `authorization_ref` = a pre-chosen grant ID. That grant's `allowed_actions` include `launch_workorder` and `recover_workorder`, and its scope lists the `pl-` IDs.
  2. State the order: grant ID → policy → policy sha → grants (each with `policy_sha256`) → trials → trial grants.
  3. Define an outcome, and a rollback from the before-images, for any failure inside step 5.

**M-1. Major: the 65536 Qwen context is not justified for the inspector, and Alternative H argues against it (851–861, 874–875, Risks row 1061).**
- The sizing argument cites a 3,840-token *author* packet: Ornith, a synthetic peripheral.
- The Qwen gateway block adds `extra_output_tokens: 32768` to every request (`ff/llm_gateway.py:149-152`). Admission refuses input + output > 65536 (`ff/lrtx/role_capability.py:173-178`).
- Inspector packets run at xhigh. They keep the base `inspection_max_source_chars: 1048576` and `complete_scope_sections: true`, settings sized for 262K (capacity profile lines 48–50).
- Alternative H (1026) says that 64K whole-workflow sizing already failed.
- **Consequences:**
  - `CAPABILITY_LIMIT` refusals become `NOT_INSPECTED` or `RUN_FAILED` in one arm only. That biases the arm A / arm B comparison.
- **Fix:** measure the largest SWE.1 inspector request at xhigh with the extra output, or lower `extra_output_tokens`. Record the margin.

**M-2. Major: the trial grant signing order contradicts `product_role_trial.authorized` (469, 485–486).**
- The code requires the *same* grant named by `trial.authorization_ref` to:
  - allow `recover_workorder`;
  - carry `signed_runbook_ref = "qualification-product-014:<trial sha>"` (`product_role_trial.py:93-99`).
- "Signs the grant documents first, then the trial names the grant ID" reads as naming a grant signed earlier. That grant cannot carry the trial's sha, so the result is `PRODUCT_ROLE_TRIAL_NOT_OWNER_SIGNED`.
- **Fix:** state it as "reserve ID → trial → sign that grant". Arm A needs one such grant per trial (two). Each must also be bound to the per-experiment policy sha (NB-1).

**M-3. Major: the per-order deadline also counts queue wait, and retry covers only `PROCESS_LAB_RUN_FAILED` (440–444, 487–488, 501–506, Risks 1063).**
- **Deadline:**
  - All drivers' orders are provisioned at the start of a batch and then run one at a time.
  - The mission deadline and `job.deadline_epoch = min(created_epoch + max_order_wall_seconds, mission deadline)` (`ff/afo/product_job.py:42-43`) therefore count the time each order spends waiting behind the earlier ones.
  - Late orders in a large batch hit `MISSION_ALLOWANCE_EXHAUSTED`, which is a BLOCK (`scheduler.py:112-117, 215-225`).
- **Retry:**
  - That block, and the new fail-closed `RESIDENT_PROFILE_MISMATCH` BLOCK, are not `PROCESS_LAB_RUN_FAILED`. So the `-r1` retry does not apply, and the driver's chain ends.
  - The Risks row says one retry covers "a single infrastructure failure", which overstates the coverage.
- **Fix:** either require batch size × measured per-order time ≤ `max_order_wall_seconds`, or provision just in time. Allow `-r1` for admission-time BLOCKs that consumed no attempt.

## Key files

- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/policy.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/authz.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/authority.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/product_role_trial.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/mission_admin.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/product_job.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/llm_gateway.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/visit.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/stack.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/config/factory/profiles/local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector-capacity.yaml`

## Raw report — `egm-implementation-readiness`

# Implementation-readiness re-review: revision 4, from "Detailed Implementation Plan" (line 1097) to the end

**Verdict: not ready to implement.** Revision 4 fixes most of what revision 3 left open. Two Blockers are fully fixed: the group documents for REWORK, and the profile composition (N1). Handoff transport and eight of the nine revision-3 Majors are also resolved. Five problems remain:
- **One new Blocker:** the per-experiment policy, as specified, leaves AFO in OBSERVE_ONLY.
- **Three items are only partly resolved,** each with a Major left: mission caps, the activation tool, and the trial binding.
- **Two new Majors.**

This review is complete. I read the persona, the standard, the revision-3 report, the constitution, SOURCE-INVENTORY, the Ornith protocol README and the whole target (1,417 lines; lines 1–1096 as context), and checked every claim below in the code. `ff/` = `factory/python/forge_factory/`.

## Status of the revision-3 open items

| # | Item | Status | What is left |
|---|---|---|---|
| 1 | Provisioning and mission | PARTIALLY RESOLVED | Major M-1 |
| 2 | Handoff into the next order | RESOLVED | – |
| 3 | Group documents, INSPECT and partial REWORK | RESOLVED | – |
| 4 | Activation tool | PARTIALLY RESOLVED | Major M-2 |
| 5 | Trial binding | PARTIALLY RESOLVED | Major M-3 |
| 7 | Leakage (owner contract) | RESOLVED | – |
| N1 | Profile composition | RESOLVED | New Major M-5 (argv) |
| r3 Majors | Grant vs trial IDs, node bindings, `max_visits`, gate-FAILED sources, scorer input, retry path, signing load, record host, state across `execv` | all RESOLVED | – |

**Evidence for the resolved items:**
- **Item 2.** The relpath rewrite (lines 311–314) works. `prepare` resolves `example / item["path"]` and checks that the result is inside the repository (`ff/workorder.py:211-213`). `load_upstream` reads the fixed name `upstream/upstream-inputs.yaml` (`ff/upstream.py:17,32`), and 0014g has no such file. `provision` now writes the seq-1 `workorder.json` (line 1198).
- **Item 3.** The planned checkpoint `{task, status: VALID, doc, base_hash, ...}` (lines 622–626) is exactly the record that `visit.run_task` reuses when there are no findings (`ff/lrtx/visit.py:166-169`). It is also the `start` record for a localized repair when findings exist (`:173-174`).
  - `swe1.write_scoped` already takes `node` (`ff/lrtx/swe1.py:663`).
  - `assemble` currently hard-codes the node (`:590`), and item 15 adds the keyword.
  - A fresh REWORK workspace has no `visits.jsonl`, so the only findings are the lab-routed ones (`swe1.py:691-697`).
- **N1.** Both profiles now pass `fabro_config`: Ornith 32768/32768/8192 and Qwen 65536/65536/16384, each against its own `OLLAMA_CONTEXT_LENGTH` (`ff/lrtx/stack.py:126-130`). The Ornith profile has no `reasoning_effort`, so the code adds no `--reasoning-effort`/`--reasoning-format` (`stack.py:408-409`).
- **Item 5, context part.** Both identities are at or below 65536, so the allocation branch in `product_role_trial.py:55-79` is never entered.
- **r3 Majors.**
  - Grants list `pl-` request IDs and the trial lists `afo-` order IDs (lines 425–429).
  - Command nodes write directly, the same way gate nodes do (`builder.py:356-484` binds only agent nodes).
  - A deterministic retry rule exists (lines 487–488).
  - Dispositions are bound to requirement statements (lines 733–737).
  - The activation record is written under `$R` (lines 579–580).
  - The state file and `--state` carry state across the `execv` (lines 528–531).

## New Blocker

**B-1. The per-experiment policy keeps the production `authorization_ref`, so effective mode drops to OBSERVE_ONLY**
- **Where:** §3 "Per-experiment policy" (lines 489–499); CUJ 1 (lines 207–210); §4 step 5 (lines 553–555); item 9 (lines 1192–1211); item 20.
- **What the plan says:** "Three things change … Everything else is copied unchanged."
- **What the code does:**
  - `policy.load` checks the grant that the *policy's own* `authorization_ref` names. If that grant is not bound to this policy's sha256 and mode, the effective mode becomes `OBSERVE_ONLY` (`ff/afo/policy.py:109-111`, `ff/afo/authz.py:88-89`).
  - The production grant is bound to the production policy sha (the repo policy names `AUTH-AFO-PILOT-20261026`, `config/factory/afo-policy.yaml:12`). The lab policy has a different sha, because its mode, model list and token budget differ.
- **Consequence:**
  - `mission_admin.register` refuses with `MISSION_ACTIVE_AUTHORITY_REQUIRED` (`mission_admin.py:18-19`).
  - Every launch and recover decision fails, because they go through the policy-level reference (`authority.py:67`, `scheduler.py:207`, `dispatch.py:377`, `local_agent.py:67-73`).
  - `product_job.reconcile` would revoke any job (`product_job.py:161-170`).
  - Step 5's "assert … its mode is PILOT" either checks the YAML field and passes while the factory is inert, or checks `policy.load().mode` (as `activate.py:106` does) and fails mid-install with no outcome code.
- **Design decision left to the implementer:** the grant topology.
  - The policy can name only one grant (`afo-policy.schema.json:393-416`). That grant must hold at least `launch_workorder` and `recover_workorder`, scoped to the `pl-` IDs, the lab driver class and both model keys. The precedent is `afo-max-context-20261029/signed-scope/primary-authorization.json`, which holds every WORK action.
  - The qualification grant must be a separate grant, because each trial needs its own `signed_runbook_ref`.
- **Fix:**
  1. Add a fourth policy change: `authorization_ref` = a new per-experiment primary grant ID.
  2. Specify the actions and scope of that grant.
  3. Give the full signing order: write the policy naming the grant ID, then sign the primary, submit and mission grants with the policy sha, then write the trial, then sign the qualification grant.
  4. Make step 5 assert `policy.load().mode == "PILOT"` and define its failure outcome.

## Majors

**M-1. Item 1 residual: mission and policy caps are still not fully determined** (lines 430–444, 489–499)
- **Requests and tool calls.** `max_requests` and `max_tools` come "from the experiment record". But `register` caps them at `budgets.max_inference_requests_per_order` and `max_tool_calls_per_order`, and without those keys the cap defaults to `max_recovery_model_calls_per_order × 8` (`mission_admin.py:48-50`). Enforcement happens per request (`mission_ledger.py:230-231`, `MISSION_REQUESTS_EXHAUSTED`).
  - The design copies these keys "unchanged", but the repo policy has neither key (cap 4 × 8 = 32). SWE.1 allows 256 author calls (`author_max_calls_by_phase`), and the stepwise inspector is multi-question.
  - **Fix:** state these two policy values, or state that they are ≥ the experiment record's values.
- **Token floor.** `max_tokens` is given only as "≤ cap". `MissionLedger.execution` also requires `charged + reservation ≤ max_tokens` (`mission_ledger.py:180`), so it must be ≥ that order's `product_attempt_token_reservations[0]` (`product_job.py:46-52`). State that floor.
- **Grant expiry.** The deadline formula leaves out the grant expiry that `register` enforces (`mission_admin.py:55-57`). Write it as min(experiment end, grant expiry, now + wall − 5), or require grant expiry ≥ experiment end.
- **Queue wait inside a batch.** Each deadline starts at provisioning, and `enforce_deadlines` measures from `created_epoch` (`dispatch.py:370-375`). With `max_concurrent_workorders: 1`, driver N's order spends its wall budget waiting behind N−1 orders. `max_order_wall_seconds` is "copied unchanged" from a production file whose value is not in the repository.
  - **Fix:** bound the batch size against the wall budget, or state the policy value.

**M-2. Item 4 residual: the step 8 VRAM refusal has two contradictory procedures** (line 567 vs line 577)
- Step 8 says "pauses with expected epoch E2" (PAUSED at E3).
- Step 10 says "same procedure, recorded … with E3", meaning the managed `stack.stop`, which runs `synchronize('shutdown')` (STOPPED at E3, `stack.py:700`).
- At step 8 the stack has not started yet (step 9 starts it). The implementer has to pick the final intent and decide whether `stack.stop` is called at all.
- **Minor residual:** step 7 (line 565) still says "left PAUSED", which contradicts the rule at lines 526–527 ("left as the other writer set it").

**M-3. Item 5 residual: it is unclear which grant the trial's `authorization_ref` names** (lines 469–470, 485–486)
- The code needs the grant named by `trial.authorization_ref` to carry `signed_runbook_ref == "qualification-product-014:<trial sha>"` (`product_role_trial.py:93-99`). That grant can only be signed after the trial exists.
- Line 485 says the owner "signs the grant documents first. Then `--prepare-trial` writes the trial naming the grant ID". Read literally, that points at an already-signed `recover_workorder` grant, which gives `PRODUCT_ROLE_TRIAL_NOT_OWNER_SIGNED`.
- **Fix:** state that `authorization_ref` = the ID of the (not yet signed) qualification grant. The precedent is `trial.json` → `AUTH-014-AFO-MAX-ROLE-20261029-V4` = `roles-authorization.json`. This ties into B-1.

**M-4. New: the `activate --restore` sequence is undefined** (lines 592–594; item 9, lines 1209–1211)
- "Runs the same procedure … and leaves the intent PAUSED" does not say:
  - whether steps 7–11 run (resume to RUNNING, load the production model, start the Conductor) and a pause follows, or whether they are skipped;
  - what happens to the lab grants in `AUTH_DIR`;
  - where the first activation's before-images are found.
- This decides whether the production model and Conductor come back up. The implementer has to choose.

**M-5. New: the Ornith argv is not "the measured S3 server form"** (lines 888–892; LAB-T18, lines 1387–1388)
- The protocol argv (README line 39) includes `--spec-type none --fit off --metrics`.
- `llama_server_spec` emits none of these (`stack.py:400-411`), and the plan adds no profile key for them.
- `--fit off` came from the speed study (README deviation 2). The default may change memory placement compared with the measured 37.4 GB peak.
- LAB-T18 asserts an "exact expected argv" that the plan never writes down.
- **Fix:** list the exact argv, and either add keys for `fit`/`spec-type` or record that the factory form differs from S3.

## Files most relevant to the open findings

- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/policy.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/authority.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/mission_admin.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/product_role_trial.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/stack.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/evidence/014-durable-local-autonomy/afo-max-context-20261029/signed-scope/primary-authorization.json
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/evidence/014-durable-local-autonomy/afo-max-context-20261029/signed-scope/roles-authorization.json

No files were modified.

## Raw report — `egm-codebase-details`

**Codebase-details review: revision 4 of `forge-c-process-first-ornith-qwen.md`**

**Verdict: not ready for implementation.** I read the persona, the implementation-readiness standard, the full target (1,417 lines), the r3 re-review report, SOURCE-INVENTORY, the Ornith protocol README and every cited source file, so the review is complete.

Revision 4 corrects most of what revision 3 got wrong in the code: one mission per order, request IDs vs `afo-` order IDs, the trial fields, whole-block profile replacement, VALID checkpoints, the `node` keyword, and E3 after a failed health check. But one new Blocker sits in the per-experiment policy. With it, every lab order is refused before admission. I found 1 Blocker, 12 Majors and 16 Nits.

## Status of the open Blockers from the r3 report

| r3 Blocker | Rev 4 fix (lines) | Correct code facts? | Remaining issue |
|---|---|---|---|
| #1 Provisioning / mission limits (also codebase B-1) | One mission per order, `mission_id = request_id`, limits 1/1/0, all six limit keys plus `lineage` and `request` (430–444) | **Yes.** Matches `mission_admin.py:20-58`, `mission_ledger.py:17-23,44` and `overnight.py:30-47`. Limits `max_attempts: 1`, `max_jobs: 1` and `max_corrections: 0` pass the caps, and `validate_limits` allows 0. The two ID kinds are now right: grants use `pl-` request IDs (`cli.py:43`, `scheduler.py:200`, `local_agent.py:64`, `mission_admin.py:101`) and the trial uses `afo-` IDs (`product_role_trial.py:40`, `product_job.py:24`). | Major M3, M4; Nits N1, N2. `register` also needs an effective PILOT mode (`mission_admin.py:18`), so this fix depends on the new Blocker B-1 below. |
| #3 Group documents / partial REWORK | `materialize` writes VALID checkpoints, `base_hash` from this workspace, PASS reply, `node="swe1_materialize"` (613–627, 1178–1179) | **Yes.** No findings plus a matching `base_hash` gives reuse (`visit.py:166-170`). Findings plus a VALID checkpoint give `start = prev doc` (`visit.py:173-174`). The checkpoint path is right (`visit.py:25-26`). `swe1.write_scoped` already has `node` (`swe1.py:663-664`); `assemble` hard-codes the default (`:590`). Task names match (`:742,749`). | Major M5 (cross-cutting description is wrong); Nit N3. |
| #5 Trial binding | `authorization_ref`, `adapter_revision = source_revision`, `task_class`, contexts ≤ 65536, so no allocation record (465–486) | **Mostly.** The field set matches `signed-scope/trial.json` without `context_allocation_ref`. The ceiling logic at `product_role_trial.py:55-57` is correct for 65536/32768. Stepwise sampling `{temperature: 0, seed}` matches `review_semantic.py:285-286` (the base seed is 1). | Major M1: the signing order splits one grant into two. |
| N1 Profile composition (r3's new Blocker; codebase B-2) | Whole-block replacement with full `runtime` blocks (838–902) | **Yes.** `fabro_config` passes for 65536/16384 and 32768/8192 (`stack.py:123-130`). Ornith has no `reasoning_effort`, so there is no `--reasoning-effort`/`--reasoning-format` (`stack.py:408-409`). Both profiles carry `vram_required_gb`. The Qwen `models` and `gateway` values match the production profile (lines 16-25, 100-115). | Major M10: the claim that the argv equals the measured S3 form is wrong. |

## Blocker

**B-1. The per-experiment policy cannot become PILOT, so submit, launch and mission registration are all refused.** (lines 205-210, 489-499, 553-555, 1069)
- **What the code requires.**
  - `policy.load` hashes the policy file (`policy.py:99`). It reaches PILOT only if the grant named by the policy's own `authorization_ref` is bound to that hash (`policy.py:109-111`, `authz.py:88-89`). Otherwise the mode drops to OBSERVE_ONLY.
  - Changing `mode`, `allowed_model_profiles` or `max_model_tokens_per_order` changes the hash. The production `authorization_ref`, which the design keeps ("Everything else is copied unchanged"), then fails with `AUTH_POLICY_MISMATCH`.
- **Evidence.** `activate.py:58,106` asserts the grants' `policy_sha256` and the effective PILOT mode. Every earlier per-experiment policy names its own grant, for example `proposed-policy.yaml:4`.
- **Which grant must allow `launch_workorder`.** `launch_workorder` is checked only against the policy-named grant (`scheduler.py:207`, `dispatch.py:71,377`, `authority.py:67`, `runtime.py:110-116`). So the launch grant must be that grant. Its scope must also cover the `pl-` IDs and both model keys.
- **Factual errors.**
  - "The owner signs the policy" (line 497) is wrong: policies are not signed. They are authorized by a grant bound to their sha.
  - The grant list "submit / recover / launch" never says which grant the policy names, or that every grant must carry the new policy's `policy_sha256`.
- **Fix.** Make `authorization_ref` a fourth policy change. Define the policy grant (actions and scope). Fix the signing order so the policy is written first, then grants carrying its sha.

## Majors

- **M1. The trial's grant and the `qualification-product-014` grant are one record** (lines 469-470, 485-486, 1069).
  - `authorized()` takes the grant named by `trial.authorization_ref`. It checks `recover_workorder` on that grant and also requires `signed_runbook_ref == "qualification-product-014:<trial sha>"` on the same record (`product_role_trial.py:93-99`). The evidence `roles-authorization.json` has exactly this shape.
  - So that grant can only be signed after the trial is written; only its ID can be fixed in advance. "Sign the grants first … then sign the qualification grant" makes it two grants, which gives `PRODUCT_ROLE_TRIAL_NOT_OWNER_SIGNED`.
  - Each trial (per arm and profile) needs its own grant, because a grant holds one `signed_runbook_ref`.
- **M2. D11 leaves out the code revision** (lines 169-174, 532-533).
  - The trial and admission require the job's commit to equal `source_revision` and `adapter_revision` (`product_role_trial.py:41,87`, `role_capability.py:157-159`).
  - So the production `repo` checkout must sit at the lab commit. `activate.py:84-91,113` fast-forwards and checks HEAD.
  - Revision 4 says only the profile, policy and grants change. Neither `activate` nor `--restore` moves or restores HEAD.
- **M3. Mission request and tool caps are unspecified** (lines 437, 496).
  - The `max_requests` cap is `budgets.max_inference_requests_per_order`, which defaults to `max_recovery_model_calls_per_order × 8` (`mission_admin.py:48-50`). That is 32 under the repository policy (`afo-policy.yaml:37`), and the key is absent there.
  - A copied production policy may therefore cap a 256-call SWE.1 author visit, or a stepwise inspection, at 32 requests.
  - The policy must state `max_inference_requests_per_order` and `max_tool_calls_per_order`.
- **M4. The deadline is set when the whole batch is provisioned** (lines 440-444).
  - `provision --role` registers every order in a batch at once. Each deadline is `now + max_order_wall_seconds − 5`, and the product job uses the same minimum (`product_job.py:42-43`).
  - Orders run serially (`max_concurrent_workorders: 1`), so time spent in the queue uses up later orders' wall budget.
  - "Never consume an earlier order's allowance" holds across batches, not within one.
- **M5. The cross-cutting statement contradicts `run_task`** (lines 641-643).
  - The base packet is `build(None, None)`, so findings never change it (`visit.py:160`).
  - With findings and a VALID checkpoint, the cross-cutting task gets a localized repair from `start = prev doc` (`visit.py:173-174`), not "re-authored from scratch".
  - It is re-authored from scratch only when `functional` changes (`swe1.py:748-750`) and there are no findings.
- **M6. Step 8 contradicts step 10** (lines 566-567 vs 577).
  - Step 8 pauses at expected epoch E2. Step 10 says a VRAM refusal follows "the same procedure", which is a managed `stack.stop` and STOPPED at E3.
  - The stack is not started yet at step 8.
- **M7. `--restore` cannot both run "the same procedure" and leave the intent PAUSED** (lines 592-594).
  - `stack.start` runs through `fenced_call`, which requires mode RUNNING at the current epoch (`operations.py:366-375`).
- **M8. Handling a foreign STOP contradicts `stack.stop`** (CUJ 2 lines 228-229 vs lines 526-527).
  - "Stops the stack if it was started" together with "never writes the intent" is impossible with managed `stack.stop`, which always writes shutdown without an expected epoch (`stack.py:700`).
  - The text also contradicts itself ("stays stopped" vs "stops"). It may also hit `SHUTDOWN_INTENT_SUPERSEDED` (`stack.py:707-708`).
- **M9. The step 10 `profile.model_identity` check cannot reach Ollama** (line 570).
  - It queries `/api/tags` with plain urllib (`profile.py:197-211`). The tool runs in the host namespace, but Ollama listens inside the stack's network namespace, reachable only through `nsenter` (`stack.py:273-311`, `_probe`).
  - As written it returns UNREACHABLE. `activate.py` does not do this check.
- **M10. The Ornith argv is not the measured S3 form** (lines 891-892, 902).
  - `llama_server_spec` emits neither `--spec-type none`, `--fit off` nor `--metrics`, and uses alias = model key on port 11457 (`stack.py:400-411`).
  - The S3 server had all three flags (README, Server section). The `--fit` default behaviour is unmeasured.
  - Either state the deltas, or add the keys and pin them in LAB-T18.
- **M11. Lab terminal reasons are incomplete** (lines 396-409, 487-488).
  - Orders can end BLOCKED before `process_lab.verdict` runs: the preflight BLOCK list (`scheduler.py:215-225`), `RUN_ABSENT` (`dispatch.py:327-331`) and the deadline BLOCK (`dispatch.py:358-377`).
  - `--retry` covers only `PROCESS_LAB_RUN_FAILED`.
  - A SUCCEEDED attempt with no handoff has no reason.
  - `next` and the retry rule are undefined for these cases.
- **M12. Obligation-only NOT_COVERED dispositions persist across reworks** (lines 737, 758-760).
  - A NOT_COVERED disposition signed on the AUTHOR handoff still decides a later REWORK handoff that may now cover the obligation.
  - For a behavioural obligation this masks an improvement. The precedence is undefined.

## Nits

- **N1** (line 433): `request_for(order)` needs a submitted order row (`local_agent.py:62-64`). Registration happens before submit, so build the dict from the envelope.
- **N2** (lines 440-441): the deadline must also be ≤ the grant expiry (`mission_admin.py:55-57`). Use min(grant expiry, experiment end, now + wall − 5).
- **N3** (line 615): `groups()` returns dicts, so write `g["id"]`, not `g.id` (`swe1.py:135,742`).
- **N4** (lines 312-313): no spec field holds an upstream reference. `load_upstream` reads the fixed file `example/upstream/upstream-inputs.yaml` (`upstream.py:17,30-34`), so it would have to be copied, not rewritten. 0014g has none.
- **N5** (lines 362-363): "role bindings for every node" is inaccurate. `nodes` holds only agent and model nodes (`builder.py:356-357,484`), not gates or command nodes.
- **N6** (lines 549, 586-587): the outcome list has no entry for `FABRO_NOT_QUIESCENT`, `SHUTDOWN_INTENT_SUPERSEDED` or an install-step failure.
- **N7** (lines 543-544): the quiet-queue state list still omits PAUSED and SUBMITTED (carried r3 N-9).
- **N8** (lines 669-670): `_parse_json` already strips fences silently (`structured.py:402-404`). Carried r3 N-2.
- **N9** (lines 1125-1126): the closures capture `run`, `t`, `box` and `structured`, not `nodes`/`dot` (`builder.py:253-273`). Carried r3 N-3.
- **N10** (lines 740, 1292): the `ssh-keygen` call is at `disposition.py:84-88`. Lines 79-101 are the whole `verify`, including the bundle and subject checks. Carried r3 N-6.
- **N11** (lines 198, 823-824): the 37,384 MiB peak is 39.2 GB in decimal units, so "39 plus margin" holds only in GiB. State the unit used by the step 8 check.
- **N12** (lines 880-882): an Ollama `hf.co` manifest for Ornith is assumed but not evidenced. Launch-time `profile.select` also needs Ollama `/api/tags` to list the key with `quantization_level` Q8_0 (`profile.py:205-209, 238`).
- **N13** (lines 219, 284, 1284): short names (`lab-qwen38-q8`) and full profile IDs are mixed, while `process_lab.profile` is compared to the full `FORGE_OPERATIONS_PROFILE`.
- **N14** (§13): the kept `driver` text and `operation_scope.dependencies[1]` say "Qwen-authored …" and carry delivery and compile-fixture framing into Ornith SWE.1 packets (0014g `workorder.json:3,115-118`).
- **N15** (lines 517, 578): the recorder unit is stopped in step 4 but never restarted.
- **N16** (line 178): "16 requirements, 22.9 s" is the S3 server-side-off run. The request-level `enable_thinking: false` run was 12 requirements in 18.6 s. The combination the lab uses (server off plus request false, plus `reasoning_effort: "none"` in the body) was not measured as one run.

## Checked and correct

- **Ornith thinking off through the gateway:** effort `none` sets `chat_template_kwargs.enable_thinking: false` and `reasoning_effort: "none"` (`llm_gateway.py:132-148`). This matches the trial's `reasoning` comparisons (`product_role_trial.py:125`, `role_capability.py:164`).
- **Activation steps against `activate.py`:**
  - the four `quiet()` conditions (`:21-26`);
  - `serving_instance`/`serving_holder` removal (`:92-95`);
  - grant and policy install (`:96-99`);
  - the `conductor.env` and unit replacement (`:100-104`);
  - the environment switch, `settings.toml` and `daemon-reload` (`:105-108`);
  - the unit text matches `services.py:105-122`;
  - E3 on health failure (`stack.py:700`, `operations.py:89-113`);
  - the unsettled-shutdown return (`stack.py:701-703`).
- **§13:** the 0014g entry numbering 1-15, the omitted entries 8, 9 and 11-14, and the kept and excluded contract passages all match `IDR-CONTRACT.md:7-41`. The five ST files are git-ignored (`.gitignore:21-22,27-28`).
- **Other citations:** the holdout write at `workorder.py:838-840`; the contract call at `:406`; the manifest field at `:293`; `local_profile_structured` at `:663-664`; `qm.validate_profile` at `qm.py:100-104`; `MAX_VISITS` at `builder.py:28` and `8 * MAX_VISITS` at `:268,271`; the `pipe` reply at `:243-251,291-292`; `runtime.py:141`; `queue.py:136-137,286-288`.

Key files:
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/policy.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/authz.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/authority.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/product_role_trial.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/mission_admin.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/visit.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/stack.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/profile.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/evidence/014-durable-local-autonomy/afo-max-context-20261029/signed-scope/roles-authorization.json
