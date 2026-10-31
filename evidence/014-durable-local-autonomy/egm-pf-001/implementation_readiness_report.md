# Goldfish Review Report — Stage 9 (Implementation Readiness), round 1

**Target:** `docs/designs/forge-c-process-first-ornith-qwen.md` (`Lines 465-832`, DetailedRange), 2026-10-31
**Dispatch:** direct (flat), three fresh native subagents in parallel; egm 0.1.0 @403d888; standards:
implementation-readiness + codebase-details → implementation-readiness-standard; style → persona rules only.
Design unchanged since Stage 5.

## Reviewer Status

| Reviewer | Status | Blocker | Major | Nit |
| --- | --- | --- | --- | --- |
| `egm-implementation-readiness` | completed | 7 | 14 | 7 |
| `egm-codebase-details` | completed | 6 | 13 | 8 |
| `egm-style` | completed | 0 | 19 | 17 |

## Consolidated findings (Elephant deduplication; raw reports follow verbatim). ✔ = Elephant code check

### 🔴 Blockers

| ID | Finding | Raised by | Check |
|---|---|---|---|
| R9-B1 | Planned attempts bypass `scheduler.preflight` (QUEUED-only); an epoch bump quarantines pre-swap launches; RUNNING orders hold the only concurrency slot → no role batching. | IR B1, CD B2 (= C7-B2, Z8-B1) | ✔ |
| R9-B2 | No carry-over between attempts: greenfield resume copies only PASS phases; `.forge-run/lab/` not carried; brownfield path needs `delivery`. | IR B2, CD B1 (= C7-B1) | ✔ |
| R9-B3 | Swap cannot rebind the managed operations profile (`FORGE_OPERATIONS_PROFILE` baked into units; `_managed_scope` mismatch; per-profile `default_root` means a different queue DB). | CD B3, IR M6 (= C7-B3) | ✔ (Stage 7) |
| R9-B4 | Ornith jobs have no role-capability admission path (`admit_job` needs a receipt or a `product_role_trial`, which is one profile+model per trial). | IR B3, CD B5 (= S5 M6) | — |
| R9-B5 | QM-purpose orders cannot use the stepwise inspector: `qm.validate_profile` refuses `semantic_inspect_phases`, the only selector of `review_semantic`; the source profiles conflict on purpose. | CD B4, IR B6 | ✔ |
| R9-B6 | Per-attempt profile cannot be plumbed: `attempt.schema.json` `additionalProperties:false`; `_launcher` never sees the attempt; `dispatch_pending` merges a fixed key list; authorization checks only the envelope `model_profile`. | CD B6, IR M2 | — |
| R9-B7 | Per-requirement inspector outcome mapping undefined; a failed visit writes no `inspection-record.json`; "actionable finding" undefined. | IR B4, CD M7, style M10 | — |
| R9-B8 | Scoring algorithm unspecified (match semantics, ambiguity, judgeability, ref resolution, artifact input). | IR B5, CD M10, style M9 | — |
| R9-B9 | Lab profile contents underspecified; copying the named sources breaks the graph (empty `phases_by_layer`, DEMO policy, SWE.1–6 structured phases, `reinspect_direct`); no reasoning-budget flag; no shared `deployment` block. | IR B6, CD M2/M3 | — |
| R9-B10 | CRC example would copy reference answers (0014f provided requirements, `idr_oracle.c`, prompt `requirement_example`) into the author workspace. | IR B7, CD M9 | — |

### 🟡 Major (deduplicated)

- Builder delegation circular, `role` not plumbed, INSPECT subgraph has no entry, rework-loop and redirection edges undefined (IR M1, CD M4).
- Policy/budgets: `max_order_attempts: 3` < 5; deadline runs from creation across swaps; reservations per seq; `planned_attempt` refusal outcome undefined (IR M3, CD M12).
- Scheduler rule unscoped → non-lab orders without `services.json` deferred (G7 regression); a stopped stack still reads as resident (IR M4, CD M11).
- Identity-hash inputs not available in `packet()`; schema mode chosen later; global effect on strict checkpoints (IR M5, CD M1).
- Context-length second source of truth (CD M2).
- Handoff field derivation (assumption, edges, constraints) and seal-chain predecessor undefined (IR M7, CD M10).
- Contracts: fixture manifest, runtime loader, inexpressible schema fixtures (IR M8, CD M8).
- Ledger key collisions; statement-hash fallback repeats the rejected Alternative J defect (IR M9, CD M5).
- Target-neutral list incomplete; existing peripheral-profile `rm.doc` is the source of truth (IR M10, CD M6).
- REWORK has no findings input path (IR M11).
- Operator-directory paths and preregistration contract undefined (IR M12).
- Test plan gaps (IR M13).
- Terminal reason codes not producible; STOPPED is not an attempt state (IR M14).
- `model_profile` meaning ambiguous, envelope policy name vs model key (CD M13).
- Style: undefined or abbreviated values (truncated digests, `...` paths), inconsistent hash terminology, NATIVE_NOT_RUN vs NOT_RUN, `$B` undefined, unnamed commands (style M1–M19).

### 🟢 Nits

Item 29 should be Modify; `ears` narrowing redundant; `NOT_RUN` undefined; intent CLI is `afo.cli`; `PATH_OUTSIDE_WORKSPACE`
does not apply to command nodes; `model_identity` checks Ollama tags rather than llama-server; reuse
`tests/peripheral_golden.py`; `swe1.visit` is LL-only; numbering and wording (see raw reports).

---

## Raw report — `egm-implementation-readiness`

**Implementation readiness review: `forge-c-process-first-ornith-qwen.md`, lines 465–832 (Stage 9, round 1)**

**Verdict: Not ready.** I read the persona, the standard, the target and all four context files. I also checked every module the plan names against the repository source. The plan has a clear increment order and a precise file list. But it fails the Zero-Decision Rule in several places, and some of those failures are not just missing detail. The specified mechanism would not work against the current code. Count: 7 Blockers, 14 Majors, 7 Nits.

---

### Blockers

**B1. Role batching cannot happen with the specified attempt dispatch.**
- **Lines:** 639–656 (items 17–18), 665–673 (item 20), 222–226, 778–779.
- **Finding:**
  - `planned_attempt` inserts the next attempt and a FABRO_LAUNCH intent directly from a RUNNING order. That path never goes through `scheduler.preflight`, because the scheduler only looks at QUEUED orders (`afo/scheduler.py:189`, `store.next_candidate`). So `RESIDENT_PROFILE_MISMATCH` is never checked for attempts 2–5.
  - If the swap has not happened yet, `dispatch_pending` launches the INSPECT attempt against the Ornith model that is still loaded.
  - If the swap happens first, the swap's "RUNNING (epoch+1)" makes the pending command's `operations_epoch` stale. `dispatch.py:84-87` then quarantines it as `STALE_OPERATIONS_COMMAND`.
  - An order waiting between attempts stays RUNNING, and RUNNING is in `ACTIVE_STATES` (`queue.py:33`). With `max_concurrent_workorders: 1` (`afo-policy.yaml:27`), no other driver's AUTHOR attempt can be admitted. So "all seq-1 attempts run first" is impossible, and the "AUTHOR-batch-first" test cannot pass.
  - A long wait for the operator also uses up `max_order_wall_seconds` (`enforce_deadlines`).
- **Guidance:** Specify:
  - the order state used while waiting for a profile, and that this state does not count against capacity or the wall deadline;
  - that the next attempt's launch intent is created only after the resident profile matches, under the current epoch;
  - which component re-checks the resident profile at dispatch time;
  - the queue FSM change in `specs/005-.../queue-fsm.yaml`.

**B2. Workspace carry-over between attempts is undefined, and the existing resume would copy nothing.**
- **Lines:** 642–645, 207–208, 653.
- **Finding:**
  - Each recovery-style attempt gets a new work order and a new workspace (`afo/checkpoints.py` docstring).
  - The greenfield `workorder.resume_from` (`workorder.py:494-500`) copies only phases whose gate decision is PASS. After an AUTHOR-only attempt there is no inspection, so `Store.gate("SWE.1")` returns REINSPECT (`inspection/engine.py:369-370`) and nothing is copied: no SWE.1 artifacts and no baseline.
  - Nothing copies `.forge-run/lab/` (seals, `swr-ledger.json`, `inspection-<seq>.json`).
  - The "brownfield resume" the plan cites only applies when `manifest.delivery` is set.
  - Item 18 does not say which workspace `inspection-<seq>.json` is read from.
- **Guidance:** Define a lab-specific carry-over:
  - the exact file list (SWE.1 `PHASE_PATHS`, `configuration/baselines/SWE.1`, `.forge-run/lab/*`, `process-lab/`);
  - hash verification against the previous seal;
  - the failure code if verification fails;
  - which earlier workspace each attempt reads from.

**B3. Lab jobs have no defined way through role admission.**
- **Lines:** 658–663, 701–721.
- **Finding:**
  - Every product request goes through `request_admission.py:80-88` → `role_capability.admit_job`. That requires one of: a `role_capabilities[role]` identity, a `product_role_trial`, or a signed qualification campaign. The identity must match `model_digest`, `adapter_revision`, `precision`, `schema_mode`, `reasoning` and `sampling` (`role_capability.py:147-167`). Otherwise the request is refused with `CAPABILITY_LIMIT`.
  - No measured Ornith role capability exists, and the plan says admission is "unchanged". As written, every Ornith author request would be refused.
  - `product_job.prepare` picks `role_capabilities` through `qualified_local_alternatives` keyed by model. The plan does not say how each attempt's model binds to an identity.
  - `authority.decide` and the `MODEL_NOT_ALLOWED` check use the single envelope `model_profile` (`dispatch.py:93`, `scheduler.py:88`). The plan does not say what that value is for an order that uses two models.
- **Guidance:** Choose and document the admission path (for example, a `product_role_trial` binding per attempt), the identity records to create for each lab profile and role, and the envelope `model_profile` value.

**B4. The per-requirement inspector outcome has no mapping.**
- **Lines:** 684–691, 575–576, 653, 271–275.
- **Finding:**
  - `review_semantic._visit` decides per checklist item (SWE1-0x). Its claims target an SWR, `"document"` or an input path.
  - Any INVALID question adds to `issues` and returns FAILED before `inspection-record.json` is written (`review_semantic.py:1276-1277`).
  - The plan does not define:
    - how item verdicts and claims become per-SWR FINDINGS, NO_FINDING or NOT_INSPECTED;
    - what `inspect_record` reads when the visit failed and wrote no record;
    - what counts as a "never-reached" requirement;
    - how document-level claims are assigned to requirements;
    - what an "actionable finding" is (severity, or whether only standing claims count);
    - whether an inspection that produced only NOT_INSPECTED outcomes triggers REWORK.
  - This is exactly the AT09/CUJ 3 behaviour the plan exists to guarantee.
- **Guidance:** Give the deterministic mapping table, the record format, the rule for actionable findings, and the rework decision for each outcome mix.

**B5. The scoring algorithm (G5) is not specified.**
- **Lines:** 589–595, 303–315.
- **Finding:** The plan does not define:
  - the matching semantics for `match`: whether register/field/op come from `register_effects.json`, and how keywords match (all or any, case, normalization);
  - what makes a match "ambiguous";
  - how "judgeable verification criterion" is computed deterministically;
  - how a ref such as "RM0486 p.480" resolves against `--inputs` (by page index or by file);
  - how "could change the result" is computed.
  
  The handoff holds only a statement sha (lines 287, 454), and the CLI takes no workspace or artifact argument, so the scorer cannot keyword-match statements as specified.
- **Guidance:** Specify the matching algorithm, the judgeability rule, how refs resolve, the sensitivity computation for `UNKNOWN_NEEDS_HUMAN`, and the artifact input argument.

**B6. The three lab profiles are under-specified, and copying the named source profiles gives the wrong behaviour.**
- **Lines:** 701–721, 214–220.
- **Finding:**
  - **Deployment:** Each profile carries its own `deployment.default_root` and ports, and the state directory, queue and `services.json` live under that root (`stack.py:49-69`). The plan does not require the three lab profiles to share root, ports and Fabro storage. Without that, the order and mission ledger "disappear" after a swap.
  - **Inspector:** `review_semantic` is chosen only when `structured.semantic_inspect_phases` contains SWE.1 (`runner.py:45-55`). The stepwise-medium profile has this list empty, so copying "`inspector_stepwise` and sampling" from it gives the old `review` inspector.
  - **Author:** The delivery-first profile has no structured phases and sets `development_execution_policy: qm-pipeline-demonstration-v1`, which triggers the builder's DEMO rewrite. "Copy the author settings" names no keys.
  - **Ornith model entry:** It needs `quantization`, `role_qualification` and `license`. `model_identity` reads `role_qualification` directly, so a missing field raises KeyError. The `gateway.reasoning` block is also unspecified.
  - **Reasoning budget:** `llama_server_spec` only supports `reasoning` on/off/auto and a named effort (`stack.py:391-409`). There is no reasoning-budget flag, yet Q5 and item 24 require a "budget value".
- **Guidance:** Give the full key set for each profile, or an exact "copy these keys" list. Require a shared `deployment` block. Add reasoning-budget support to item 2 if the budget is meant to be a profile setting.

**B7. The CRC example's inputs are unspecified and include reference-answer material.**
- **Lines:** 723–729, 801–802.
- **Finding:**
  - The `0014g` inputs include `../0014f-st-cube-crc-idr-qm/provided-requirements.json` (role `delivery_first_reviewed_reference_requirements`), `idr_oracle.c` and `idr_target_oracle.c`.
  - Its `operation_scope.prompt_overrides.requirement_example` contains a model answer.
  - It also carries `development_execution_policy` and `delivery_first`.
  - "Reusing the frozen 0014g source entries" does not list which entries. If the provided requirements are carried over, the runner also switches to `materialize` instead of authoring (`runner.py:109-113`).
  - The isolation test only checks oracle paths and hashes, not reference-answer content. The plan's own EGM gate treats hidden oracle leakage as blocking.
- **Guidance:** List the exact input entries, the `operation_scope` and prompt overrides to use, and the fields to drop. Extend the isolation test to forbid reference or oracle roles.

---

### Majors

**M1. Builder integration is circular and its edges are undefined.**
- **Lines:** 629–637, 563–564.
- **Finding:**
  - `build()` has no `role` parameter, and the plan never says how the attempt's role gets into the workspace manifest.
  - `process_lab.workflow` "calls the builder", while the builder "delegates to `process_lab.workflow`". It is unclear whether `workflow` post-processes the dot (like `delivery_workflow`) or rebuilds it.
  - With the upstream chain removed, the targets of `swe1_route -> upstream_swe1` and of a failed author gate are undefined.
  - It is unclear whether the AUTHOR attempt keeps the existing route rework loop.
  - It is unclear whether the continuation, reinspect and advisory rewrites still apply. `pipe()` raises `STRUCTURED_GATE_MISSING` if the INSPECT subgraph drops `swe1_inspect_gate`.

**M2. The attempt contract and plumbing are missing.**
- **Lines:** 642–645, 658–663.
- **Finding:**
  - `record.plan_entry` violates `specs/005-autonomous-factory-operations/contracts/attempt.schema.json` (`additionalProperties: false`), which `contracts.require("attempt", rec)` enforces. That file is not in the change list.
  - Seq 1 is created by `store.admit` without a `plan_entry`.
  - `_launcher` receives the launch manifest, not the attempt record. `dispatch_pending` forwards only whitelisted payload keys (`dispatch.py:135-144`).
  - The `planned_attempt` signature lacks the `epoch` that `_enqueue` needs, and it lacks a `max_attempts` check.
  - The plan does not say where `attempt_plan` is read from (launch manifest or workspace manifest).

**M3. Policy and budget values for lab orders are missing.**
- **Lines:** 755–756.
- **Finding:** `budgets.max_order_attempts: 3` (`scheduler.py:137`, `new_attempt`) is less than the 5 planned attempts. The plan also does not give the mission ledger `max_attempts`, `product_attempt_token_reservations` per seq, `allowed_model_profiles`, or the content of the signed per-experiment policy.

**M4. The scheduler rule is not scoped to lab orders.**
- **Lines:** 665–673.
- **Finding:** As written, `RESIDENT_PROFILE_UNKNOWN` would defer every non-lab order that has no local `services.json` (for example the `codex-claude` profile). That is a G7 regression. The plan also does not say how the "attempt profile sha" is computed (`profile.load(...)["_sha256"]`?).

**M5. Inputs to the identity hash are not available where the hash is computed.**
- **Lines:** 484–489.
- **Finding:**
  - `structured.packet()` has no digest, profile sha, reasoning or schema-mode parameters. Schema mode is chosen later, in `call()`. `RECOVERY_WORKSPACE` is set only by the runner, and `durable-binding.json` contains none of these values.
  - The plan does not give the source of each value. For reasoning, candidates include `llama_server.reasoning`, `gateway.reasoning[model].effort` and `role_efforts`.
  - The change applies globally, not only in lab mode. Its effect on strict-path checkpoint reuse is not stated, and 11 test files reference `input_hash`.

**M6. The swap tooling is not actionable.**
- **Lines:** 611–619, 731–740.
- **Finding:**
  - `check-quiescent` does not say which job IDs it checks (the last job of the batch, or all jobs), or which tables (`afo_execution_evidence` with kind QUIESCENCE, `afo_request_ledger` states).
  - "Operations intent set" has no exact command. The `operations` CLI only offers boot-check, status and initialize.
  - `FORGE_OPERATIONS_PROFILE` binds the managed stack and `operations.recover`. Unless it changes, `stack._managed_scope` refuses the new profile with `MANAGED_PROFILE_SCOPE_MISMATCH`, and the watchdog restarts the old profile.
  - The `probe` needs a durable job binding to pass gateway admission; who owns that job is not defined.
  - The path and naming of the `model-swap/1` file are not given.

**M7. How handoff content is derived is unspecified.**
- **Lines:** 512–517, 568–578, 597–602, 192–193.
- **Finding:**
  - No derivation is given for `assumption`, `source_refs[]`, the verification criterion or `downstream_constraints[]` from the `swe1.assemble` rows, which have no assumption field.
  - Statement normalization before hashing is not defined.
  - The schema has no trace-edge field, yet the importer rejects `HANDOFF_DANGLING_TRACE`.
  - The importer's AMBIGUOUS rule ("NOT_INSPECTED critical") needs criticality, which the importer does not have without the oracle.
  - `NOT_RUN` (line 517) is not defined in §7.
  - The REWORK seal's "prior seal" is the AUTHOR seal in §1 but the "prior seal sha" (which would be the INSPECT seal) in item 10.

**M8. Some planned contract fixtures cannot be expressed in JSON Schema.**
- **Lines:** 542–552.
- **Finding:**
  - Duplicate SWR IDs, and `MEETS` in a sealed but unscored package, cannot be rejected by schema without a discriminator field (for example `scored_by`).
  - Fixtures must be registered in `examples/manifest.json`, or the validator fails with `FIXTURE_INVENTORY`.
  - The runtime `contract()` has no defined schema loader: `afo/contracts.py` only loads `specs/005`.

**M9. The ledger key can collide.**
- **Lines:** 580–587, 258–263.
- **Finding:** Requirements carry `effects[]`, a list. A requirement with several effects, or two rows with the same key, would get the same SWR. The plan has no collision rule, no normalization for the statement hash, and no ledger file schema (including how retired numbers are stored).

**M10. The target-neutral change list is incomplete.**
- **Lines:** 675–682, 693–699.
- **Finding:**
  - RM0486 also appears in `lrtx/swe1.py` at lines 240, 272, 343, 351, 358, 416, 502 and 505–506 (prompts, validation messages, upstream IDs).
  - `assurance/swe12.py` lines 66 and 74 parse `RM0486 p.` with regexes.
  - The directory name `inputs/sections/RM0486` is hard-coded.
  - The plan does not give the manifest field path for `primary_manual`, or the signature change for `ears.check_document` (it has no lab flag; callers are `swe1.py:642` and `swe12.py:96`).

**M11. How REWORK receives findings is not defined.**
- **Lines:** 184–185, 675–682.
- **Finding:** `lrtx.runner author` has no findings input. The plan does not say how consolidated findings reach `swe1.visit`, or whether all groups are re-authored or only the ones with findings.

**M12. Operator-directory paths and the preregistration schema are undefined.**
- **Lines:** 299–301, 604–609, 617.
- **Finding:** No concrete paths are given for the oracle store, score reports, swap records or preregistration files. No contract exists for `preregistration.json`, which `decide` validates against.

**M13. The test plan has gaps.**
- **Lines:** 762–804.
- **Finding:** There are no tests for:
  - the `primary_manual` default and override, and the narrowed ears ID pattern;
  - the lab `validate` path never producing READY;
  - `REWORKED_AFTER_LAST_INSPECTION`;
  - the seal's refusal to overwrite;
  - loading the three new profile YAMLs and the Ornith llama-server argv;
  - non-lab orders being unaffected by the scheduler rule;
  - validating swap records against their schema;
  - CUJ 2 (stop between attempts) at the dispatch level.
  
  The e2e test does not name its harness, so it is unclear how Fabro and the outbox are simulated in CI.

**M14. The terminal disposition reasons cannot be produced as specified.**
- **Lines:** 203–204, 565–566, 655.
- **Finding:** `verdict(workspace)` cannot see the attempt state, so it cannot return `LAB_ATTEMPT_FAILED` or `LAB_ATTEMPT_STOPPED`. "STOPPED" is not an attempt state (the enum has SUCCEEDED, FAILED, CANCELLED and UNKNOWN).

---

### Nits

- **N1 (line 207):** "Attempts 2 and 3" is out of date; D4 allows up to 5 attempts.
- **N2 (lines 758–760):** The design document already exists, so this item is "Modify", not "Create".
- **N3 (lines 559 and 626):** The signature is `contract(spec)`, but the call site at line 406 passes the manifest, following the `delivery_first` pattern.
- **N4 (lines 496–497 and 705–706):** The location of `model_blob_sha256` is ambiguous: the model entry or `runtime.llama_server`.
- **N5 (line 508):** "`max_semantic_rework` equals the number of REWORK entries" cannot be expressed in JSON Schema; it has to live in `contract()`.
- **N6 (line 559):** "Refuses any field naming an oracle" needs a concrete rule. Otherwise it duplicates `additionalProperties: false`.
- **N7 (lines 819–826):** Give the exact paths for `validate_spec` (`specs/014-durable-local-autonomy/validate_spec.py`) and for the inherited runner, which is not in the repository.

---

**Files referenced:**
- Target: `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md`
- Evidence (all under `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/`):
  - `factory/python/forge_factory/afo/{scheduler.py,dispatch.py,checkpoints.py,product_job.py,runtime.py,queue.py,request_admission.py,contracts.py,operations.py,mission_ledger.py}`
  - `factory/python/forge_factory/lrtx/{structured.py,stack.py,profile.py,runner.py,review_semantic.py,role_capability.py,swe1.py}`
  - `factory/python/forge_factory/workflow/builder.py`
  - `factory/python/forge_factory/workorder.py`
  - `factory/python/forge_factory/inspection/{engine.py,ears.py}`
  - `factory/python/forge_factory/assurance/swe12.py`
  - `specs/005-autonomous-factory-operations/contracts/attempt.schema.json`
  - `specs/014-durable-local-autonomy/contracts/validate_contracts.py`
  - `config/factory/afo-policy.yaml`
  - `config/factory/profiles/local-rtx-v2-omniverse2-q38-{delivery-first,aspice-stepwise-medium}.yaml`
  - `examples/0014g-st-crc-idr-qwen-delivery/workorder.json`

## Raw report — `egm-codebase-details`

# Codebase Details Goldfish: Stage 9 Implementation Readiness Review, round 1

**Target:** `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md`, lines 465–832 (lines 1–464 used as context only).
**Standard:** `/home/jefferson/.claude/plugins/cache/egm/egm/0.1.0/resources/document_standards/implementation-readiness-standard.md`
**Inputs read:** the persona, the standard, the constitution, the plan, SOURCE-INVENTORY, and every source file the plan cites.

**Verdict: FAIL (not implementation-ready).** There are 6 Blockers, 13 Majors and 8 Nits. Most cited line numbers are correct. The problems are in the plan's assumptions about how resume, dispatch, managed serving, inspector selection, purpose validation and role admission behave today. The code contradicts several of those assumptions, and many decisions are left to the implementer, which breaks the Zero-Decision Rule.

**Line references that check out:** structured.py:172/237, workorder.py:293/406, builder.py:212, dispatch.py:313–355/452, scheduler.py:118–121/232–237, runtime.py:69–89, swe1.py:491–595, provided_requirements.py:70, swe12.py:34, request_admission.py:49, role_capability.py:155. Every target file is marked Create or Modify.

---

## Blockers

**B1. Later attempts cannot resume the earlier attempt's SWE.1 work. The plan's "validated brownfield resume" does not apply here.**
- **Affected scope:** lines 642–645 (`planned_attempt`, "resumes from `source_wo`"), 651–655, 662; context line 207. Code: `ff/workorder.py:460–568`, `ff/inspection/engine.py:27–34, 353–376`.
- **Discrepancy:** `resume_from` only runs the brownfield path when `manifest["delivery"]` is set (lines 468–486). A lab order has no `delivery` block, so it takes the greenfield path, which copies only phases whose gate is `PASS`. After an AUTHOR attempt, SWE.1 has a baseline but no inspection, so `Store.gate` returns `REINSPECT / NO_INSPECTION_FOR_CURRENT_BASELINE` and nothing is copied.
  - The INSPECT attempt therefore starts with no requirements, no baseline and no seals.
  - `.forge-run/lab/` (seals, `swr-ledger.json`, `inspection-<seq>.json`) and `.forge-run/lrtx/` are not in `PHASE_PATHS` or `RESUME_EXTRA`, so they are never carried over.
  - As written, AT11 (immutable seal chain) and the ledger's "REWORK loads the AUTHOR ledger" cannot work. The plan has to define a new lab carry-over rule.

**B2. The resident-profile gate sits where seq ≥ 2 attempts never pass, and the operations epoch fence blocks every attempt queued before a swap.**
- **Affected scope:** lines 665–673, 642–645, 651–653; context lines 222–226. Code: `ff/afo/scheduler.py:172–259`, `ff/afo/checkpoints.py:86`, `ff/afo/queue.py:405–412, 33`, `ff/afo/dispatch.py:73–87`.
- **Discrepancy:**
  - `scheduler.cycle`/`preflight` only look at QUEUED orders (`next_candidate`). A planned attempt is enqueued straight into the outbox, as `new_attempt` does, and `dispatch_pending` launches it with no preflight. So seq 2 (INSPECT) would launch at once on the still-resident Ornith stack, and a `RESIDENT_PROFILE_MISMATCH` in `preflight` cannot stop it.
  - The alternative fails too. `_enqueue` stamps `operations_epoch`, and `dispatch_pending` quarantines any command whose epoch differs (`STALE_OPERATIONS_COMMAND` → order BLOCKED). The swap ends with "set intent RUNNING (epoch+1)", so a launch queued before the swap is always blocked afterwards.
  - `ACTIVE_STATES` includes RUNNING, and `store.admit` enforces `queue.max_concurrent_workorders`. A driver-1 order waiting RUNNING for a swap uses the slot, so driver 2's seq 1 cannot be admitted. The claim that "all seq-1 attempts run first" does not hold.
- The gate has to live in `dispatch_pending` or `planned_attempt`. The plan must also define how planned launches survive the epoch change and what concurrency setting to use.

**B3. The swap runbook cannot change profiles under managed serving using "only existing commands".**
- **Affected scope:** lines 701–721, 731–740; context lines 228–248. Code: `ff/lrtx/stack.py:341–367, 416–474, 692–710`, `ff/afo/services.py:100–122`, `ff/afo/operations.py:269–342, 401–410`, `ff/afo/provider_recovery.py:16–25`.
- **Discrepancy:**
  - Under managed serving, `stack.start` calls `_managed_scope`, which refuses with `MANAGED_PROFILE_SCOPE_MISMATCH` unless the profile equals `FORGE_OPERATIONS_PROFILE`.
  - That variable is baked into the systemd units together with `FORGE_STATE_DIR = <profile default_root>/state`, and the conductor runs inside `lrtx.stack exec --profile <selected>`.
  - The gateway admission check (`current_instance`), `settle_shutdown` and the watchdog's `recover_profile` all resolve `stack.settings(FORGE_OPERATIONS_PROFILE)`. After `stack start --profile P_to`, they would either reject the instance (`SERVING_INSTANCE_REFERENCE_INVALID`) or restart P_from.
  - Every existing profile has its own `deployment.default_root` and ports, so a different root means a different conductor database and the plan's queue disappears.
- Items 24/25 do not specify a shared `deployment` block, and item 27 does not say how the operations profile is re-bound.

**B4. The stepwise inspector `review_semantic` cannot be selected for a QM or ASPICE-purpose order, and the copied profiles conflict on purpose.**
- **Affected scope:** lines 684–691, 713–720, 504; context line 181. Code: `ff/lrtx/runner.py:45–55`, `ff/release/qm.py:100–104`, `ff/release/aspice.py:57–66`, `ff/workorder.py:731–732`.
- **Discrepancy:**
  - `runner.inspector_module` uses `review_semantic` only when the profile lists the phase in `structured.semantic_inspect_phases`. Otherwise it uses `review.py`, even when `inspector_stepwise: true`. The source profile `...-q38-aspice-stepwise-medium.yaml` has `semantic_inspect_phases: []`.
  - `qm.validate_profile` and `aspice.validate_profile` refuse any profile with `semantic_inspect_phases`.
  - The block declares `purpose: QM`. The inspector source profile is `ASPICE_ONLY` and the author source profile (`...-delivery-first.yaml`) is `QM` with `development_execution_policy: qm-pipeline-demonstration-v1`.
- So either the order is refused, or the item-22 changes never run. The work-order purpose for lab runs and the profile flags must be decided in the plan.

**B5. Ornith requests have no role-capability admission path.**
- **Affected scope:** lines 658–663, 701–711; context line 206 ("invariants are unchanged"). Code: `ff/afo/request_admission.py:79–88`, `ff/lrtx/role_capability.py:125–156`, `ff/afo/product_role_trial.py:29–47`, `ff/afo/runtime.py:81–85`.
- **Discrepancy:**
  - Product jobs call `admit_job` on every request. That needs either a measured capability receipt whose identity includes the role and `model_digest`, or a `product_role_trial`. Without one, the request is refused with `CAPABILITY_LIMIT` ("role capability has not been independently measured").
  - Ornith has no receipt.
  - `product_role_trial.authorized` requires `trial.profile == job.profile` and `trial.model == job.model`, which means one profile and one model per trial. The launch manifest carries a single `product_role_trial`.
- The plan never says how per-attempt role trials or receipts are bound, so no native Ornith attempt could be admitted.

**B6. Per-attempt profile selection cannot be implemented as written: the attempt contract, the dispatch merge and the launcher's inputs all block it.**
- **Affected scope:** lines 642–645, 658–663, 647–656. Code: `specs/005-autonomous-factory-operations/contracts/attempt.schema.json` (`additionalProperties: false`), `ff/afo/checkpoints.py:76–83`, `ff/afo/dispatch.py:135–144`, `ff/afo/runtime.py:48–89`.
- **Discrepancy:**
  - `record.plan_entry` would fail `contracts.require("attempt", rec)` because the schema forbids extra properties. That schema file is not in Target Scope.
  - `_launcher(manifest, wo, labels)` never receives the attempt record.
  - `dispatch_pending` merges only `resume_from, resume_upto, model_profile, lesson_ids, recovery_plan, recovery_exhausted` from the payload. `profile` is not on that list, and `dispatch_pending` is not in item 18's change list.
  - Authorization (`authority.decide`, dispatch.py:93) and `scheduler` `MODEL_NOT_ALLOWED` check only the order envelope's single `model_profile`, so per-attempt profiles are never authorized individually.

---

## Majors

**M1. The identity hash does not say where each value comes from.**
- **Affected scope:** lines 484–489. Code: `ff/lrtx/structured.py:98–116, 237–260, 485–497, 527–547`, `ff/lrtx/visit.py:160–196`.
- **Discrepancy:**
  - `packet()` takes only `model: str`. It has no digest, profile sha or reasoning input, and `probe_capabilities` calls it without a workspace.
  - The schema mode is chosen *after* `build()` inside `visit.run_task` (`budget["schema_mode"] = S.schema_mode_for(p["model"])`), and `schema_mode_for` resolves the profile from `FORGE_LRTX_PROFILE` (default `local-rtx-v1`), not the manifest.
  - The recursive `without_lessons` call would also need the new inputs.
- **Reuse:** `manifest["local_profile"]["config_sha256"]` (workorder.py:852), `profile["models"]["allowed"][model]["digest"]`, and the `role_capability.IDENTITY` tuple, which already lists role, model_digest, precision, reasoning, schema_mode, context_tokens and sampling.

**M2. The new `runtime.llama_server.context` setting would disagree with every other component that reads the context size, and "reasoning budget" has no implementation.**
- **Affected scope:** lines 496–498, 707–709. Code: `OLLAMA_CONTEXT_LENGTH` readers at `structured.py:56`, `profile.py:60`, `stack.py:129, 395`, `product_role_trial.py:65`, `qualification_inputs.py:152`.
- **Discrepancy:**
  - Only `llama_server_spec` would read the new key. Packet accounting, role job envelopes and trial context ceilings would keep using `OLLAMA_CONTEXT_LENGTH`. Setting `OLLAMA_CONTEXT_LENGTH` in the Ornith profile needs no code change.
  - `llama_server_spec` also requires `runtime.ollama.OLLAMA_KV_CACHE_TYPE`.
  - It supports `reasoning` on/off/auto plus `reasoning_effort`, but has no budget flag, so item 24's "reasoning/budget" (Q5: 2,048 or 8,192 tokens) is unimplementable without an unlisted change.

**M3. The lab profile contents are underspecified, and copying from the named sources breaks the graph.**
- **Affected scope:** lines 701–721. Code: `ff/workorder.py:634–677, 831–832`, `ff/workflow/builder.py:289–314`.
- **Discrepancy:**
  - `...-q38-delivery-first.yaml` has empty `phases_by_layer`, so its author is a Fabro agent node, not `lrtx.runner author`. That contradicts §10a ("only through lrtx structured packets").
  - Its `development_execution_policy` turns on the DEMO workflow transform.
  - `...-stepwise-medium.yaml` lists SWE.1–6 in its structured phases and sets `reinspect_direct: true`. With `stop_after="SWE.1"`, `swap()` raises `STRUCTURED_NODE_MISSING:swe2_author`, and the reinspect loop raises `STRUCTURED_ROUTE_MISSING` for SWE.2–6.
  - Items 24/25 must give each profile's full `structured`, `work_order_purpose`, `gateway.reasoning`, `admission`, `deployment` and `status` keys.

**M4. The builder delegation and the role subgraphs are not specified enough to implement.**
- **Affected scope:** lines 563–564, 629–637; context line 174. Code: `ff/workflow/builder.py:107–216, 334–489`, `ff/delivery_first.py:278`.
- **Discrepancy:**
  - `build()` has no `role` parameter, and nothing says how the role travels from the attempt to `workorder.run` to `build`.
  - `process_lab.workflow(manifest, role)`, which "calls the builder", recurses if it calls `build`. It also breaks the stated "same pattern" as `delivery_first.workflow(graph, nodes, manifest, env, python)`, which is a post-transform.
  - Entry is always the phase author (`restart = phases[0]`), so the INSPECT subgraph has no entry point at `swe1_inspector`.
  - Missing redirections: `swe1_route -> upstream_swe1`, author-gate failure (does the bounded author rework loop stay?), `lab_end -> exit`.
  - The context's "unconditional `swe1_inspect_gate → SWE.2` edge" is wrong. Line 444 emits it with `condition="outcome=succeeded"`.

**M5. The ID ledger key cannot be derived from existing rows, and the fallback brings back the defect the plan rejected.**
- **Affected scope:** lines 580–587. Code: `ff/lrtx/swe1.py:499–509, 591–593`.
- **Discrepancy:**
  - Assembled rows carry `effects[]` (zero or many register/field/op entries), a model-chosen `key`, and `source: "RM0486 p.N"`. There is no single register/field/op.
  - The key rule for multiple effects, page changes, and two requirements on one field is undefined.
  - The statement-hash fallback, which every cross-cutting requirement would use, changes whenever rework edits the text. That is the same instability the plan gives as its reason for rejecting Alternative J.
- **Reuse:** `.forge-run/lrtx/SWE.1/assembly.json` already maps `swr → {task, key}`.

**M6. The target-neutral change list is incomplete, and a source of truth already exists.**
- **Affected scope:** lines 679–682, 697–699.
- **Discrepancy:** Hard-coded RM0486/RCC values the plan does not list:
  - `swe1.py`: 240, 272 (prompts), 343/351/358 (validation messages), 505–506 (cross-cutting rows).
  - `swe1_semantic.py`: 212, 322, 490.
  - `swe12.py`: 66, 74 (`RM0486 p.` citation regexes) and 35–36, 40 (`RCC_`-only regexes).
  - `workorder.py:228`: only `inputs/RM*` files are split into `inputs/sections/<stem>`, so a non-ST manual is never indexed.
- **Reuse:** the peripheral profile already declares `rm.doc: RM0486` (`config/factory/peripherals/crc.yaml:12`, read by `layer.profile(ws)`). A new `process_lab.target_profile.primary_manual` would be a second source of truth, and the plan does not say how non-lab defaults read it.

**M7. Per-requirement inspector outcomes and "actionable" findings are undefined, and the record the plan converts does not exist on failure.**
- **Affected scope:** lines 575–576, 651–653, 686–690. Code: `ff/lrtx/review_semantic.py:1103–1296`.
- **Discrepancy:**
  - Verdicts are per checklist item (`SWE1-xx`), and claims target an SWR, `document` or inputs. There is no rule for mapping them to FINDINGS, NO_FINDING or NOT_INSPECTED per requirement (for example: an invalid item means all requirements NOT_INSPECTED? what about document-level claims?).
  - On any issue the visit returns FAILED before `inspection-record.json` is written (lines 1276–1290), so `seal.inspect_record` has nothing to read in exactly the NOT_INSPECTED cases.
  - "Actionable finding" (which decides whether REWORK runs) is undefined.
  - The plan says "CONTINUE/FAILED for rework". Rework is actually routed by `status = "REWORK"` (line 1294); CONTINUE is a time-box continuation.

**M8. Runtime use of the spec contracts conflicts with the validator's scope, and two planned invalid fixtures cannot be written in JSON Schema.**
- **Affected scope:** lines 542–552, 559. Code: `specs/014-durable-local-autonomy/contracts/validate_contracts.py:2, 17–24, 72, 97–99`, `contracts/examples/manifest.json`.
- **Discrepancy:**
  - The validator declares `SPEC_CONTRACTS_ONLY_NOT_RUNTIME`, yet `process_lab.contract` would validate against these schemas at runtime. The existing runtime pattern to reuse is `ff/afo/contracts.py` (`CONTRACTS` dir plus `_validator`) or `common.schema_errors`.
  - Fixtures must be registered in `examples/manifest.json`, which is not listed in item 7 or 8; otherwise `FIXTURE_INVENTORY` fails.
  - "Duplicate SWR id" cannot be expressed: `uniqueItems` compares whole objects, not `id` fields.
  - "MEETS in a sealed, unscored package" needs a sealed/scored discriminator field, which is not defined.

**M9. The CRC example would expose reference answers to the author, and "hash-bound" inputs have no mechanism.**
- **Affected scope:** lines 726–729; context line 114. Code: `examples/0014g-st-crc-idr-qwen-delivery/workorder.json:62–93`, `ff/workorder.py:210–216`.
- **Discrepancy:**
  - 0014g's inputs include `../0014f-st-cube-crc-idr-qm/provided-requirements.json` (role `delivery_first_reviewed_reference_requirements`), which are previously reviewed SWE.1 answers, plus `idr_oracle.c` and `idr_target_oracle.c`. "Reusing the frozen 0014g source entries" copies them into the author's workspace, which is the leakage the plan prohibits.
  - The exact subset must be enumerated.
  - `prepare` computes hashes but never checks declared ones, and the process-lab schema has no inputs or hash field.

**M10. Scorer and importer semantics are undefined.**
- **Affected scope:** lines 589–602; context lines 287–290, 303–311.
- **Discrepancy:**
  - No deterministic rule for "judgeable verification criterion" (the ≥ 90% criterion).
  - No matching algorithm for `register/field/op and/or keywords[]`: any keyword or all? what counts as "ambiguous"?
  - "Dangling trace edges": the handoff schema has no edge field.
  - No producer for `assumption: bool` (`GROUP_SCHEMA` has no such field; every row gets `RM0486 p.N`), `downstream_constraints[]` or `gaps[]`.
  - Zero noncritical obligations: behaviour undefined.
- **Reuse:** `swe12.cited_pages`/`_pages` and `assurance.hardware.index` for resolving references.

**M11. `check-quiescent` and the resident-profile read are not grounded in existing APIs.**
- **Affected scope:** lines 615–616, 669–673. Code: `ff/afo/mission_ledger.py:373–426`, `ff/lrtx/stack.py:713–772`, `ff/lrtx/profile.py:214–221`.
- **Discrepancy:**
  - There is no read-only ledger API for "no owner + QUIESCENCE + no SENT/UNKNOWN"; `release_inference` mutates state. The plan must give the tables (`afo_resource_ownership`, `afo_execution_evidence kind='QUIESCENCE'`, `afo_request_ledger`) and which job's evidence is checked.
  - `_stop` keeps `services.json` with the old `profile_sha256`, empty `processes` and a `stopped_at` timestamp. A stopped stack would therefore read as resident, and `RESIDENT_PROFILE_UNKNOWN` never fires.
- **Reuse:** `profile.runtime_record()`.

**M12. Order lifecycle edge cases and budgets are undecided.**
- **Affected scope:** lines 642–655. Code: `ff/afo/product_job.py:42–52`, `ff/afo/scheduler.py:137–138`, `ff/afo/dispatch.py:358–415`.
- **Discrepancy:**
  - When `planned_attempt` refuses because intent is not RUNNING (the normal swap case), the order's fate is not defined.
  - `deadline_epoch` and `enforce_deadlines` run from order *creation* across all swaps and other drivers' batches.
  - `budgets.max_order_attempts` must be ≥ 5, and the mission `max_attempts` must be sized.
  - The terminal codes `LAB_ATTEMPT_FAILED`/`LAB_ATTEMPT_STOPPED` (context line 204) are not wired into item 9 or 18.
- **Reuse:** `product_attempt_token_reservations` for per-seq reservations.

**M13. `model_profile` in plan entries is ambiguous.**
- **Affected scope:** lines 505–506, 642.
- **Discrepancy:** In the AFO envelope, `model_profile` is a policy profile name checked against `engineering.allowed_model_profiles`. In `_launcher` and `product_job.prepare` (`job["model"] = manifest.model_profile`), it is a model key under `models.allowed`. The plan does not say which meaning entries carry.

---

## Nits

- **N1.** Line 758: `docs/designs/forge-c-process-first-ornith-qwen.md` already exists, so it should be marked Modify, not Create.
- **N2.** Lines 693–697: `ears.check_document(markdown, systems)` has no lab context, so the signature and callers (`swe1.self_check`, gate) need a change. The narrowing is also redundant, since assembly always emits `SWR-nnn` and the handoff schema pins the pattern.
- **N3.** Line 517: `NOT_RUN` appears in the `inspector_outcome` enum but is not defined in §7.
- **N4.** Lines 734–738:
  - The intent command is `forge_factory.afo.cli drain|resume|shutdown`; `operations.main` has no setter.
  - A managed `stack.stop` already runs `synchronize("shutdown")` and `settle_shutdown`, so the state machine's QUIESCENT→STOPPED step duplicates work.
- **N5.** Lines 618, 801–802:
  - `PATH_OUTSIDE_WORKSPACE` is MCP tool-call confinement (`policy/authz.py`, `acp/gate.py`). It does not apply to structured command nodes, where the model has no file access, so the AT16 "file access outside workspace is refused" test is ill-defined.
  - `profile.model_identity` checks Ollama `/api/tags`, not what llama-server actually loaded.
- **N6.** Lines 770–771: reuse `tests/peripheral_golden.py` (`normalized_graph`, `graph_hashes`) and `tests/compat/lrtx/*.json.gz` for the byte-identical golden test.
- **N7.** Lines 819–821:
  - `operations/feature014/run_full_inherited.py` is not in the repo, so the baseline cannot be checked from here.
  - The "F015 workflow tests and strict graph tests" are not named as files.
- **N8.** Line 496: `model_blob_sha256` is compared against manifest metadata only; the 37.8 GB blob content is never hashed. Also, `swe1.visit` refuses non-LL layers (`LRTX_SWE1_LAYER_NOT_SUPPORTED_YET`), and the plan does not state that LL-only constraint for the corpus.

## Raw report — `egm-style`

# Style Review: forge-c-process-first-ornith-qwen.md, lines 465-832 (Stage 9, round 1)

**Summary**: 0 Blockers, 14 Majors, 17 Nits. The range is mostly dry and factual, with little hyperbole. The main problems are terms that are never defined, values that are cut short or left out, and terms used inconsistently. Each of these would leave a new implementer guessing.

## Major

**M1. Line 468-469**
- **Text**: "each ends with its tests passing and the regression battery from the Verification Plan, before the next starts."
- **Rationale**: The sentence is missing a verb for the regression battery. A reader cannot tell whether the battery must pass or only run. Suggested wording: "Each increment's tests and the Verification Plan regression battery pass before the next increment starts."

**M2. Lines 505 and 508**
- **Text**: "2–5 items in the fixed role order AUTHOR, INSPECT, REWORK, INSPECT, REWORK"
- **Rationale**: This does not say the plan must be a prefix of that sequence. It also does not say whether a plan of 3 items, ending on REWORK with no inspection after it, is valid. Line 508 also does not say whether `max_semantic_rework` is checked against the plan or derived from it. Suggested wording: list the allowed plans explicitly, for example "a prefix of length 2, 3, 4 or 5".

**M3. Line 515-516**
- **Text**: "`criteria_result` is an enum"
- **Rationale**: No values are listed here, while `inspector_outcome` on the next line has its full value list. Readers must collect the values from lines 546, 578, 793 and 798 (UNSCORED, MEETS, FAILS, NEEDS_HUMAN). List them in place.

**M4. Line 559**
- **Text**: "refuses any field naming an oracle"
- **Rationale**: "Naming an oracle" could mean a key name, a path value, or a hash value. Line 510 already sets `additionalProperties: false`, so the extra check needs a concrete rule, for example "any key or string value matching `oracle`, or any path under the operator directory".

**M5. Line 565**
- **Text**: "`BLOCKED/<specific reason>`"
- **Rationale**: The reason codes are not listed. Every other module in this plan names its stable reason codes (lines 587, 602, 627, 669, 672). List them, or point to where they are defined.

**M6. Lines 572-578 and 705**: hash terminology is inconsistent.
- **Text**: one concept appears as "sha", "sha256", "digest", "hash", "manifest sha", "profile sha", "prior seal sha" and "layer digest".
- **Rationale**: `model_digest` is defined at line 705 as the manifest sha256. Line 497 contrasts the layer digest with the manifest sha. Mixing these words makes it unclear which value each field holds. Use the field names (`model_digest`, `model_blob_sha256`, `profile_sha256`) consistently, and say "sha256 of <file>" everywhere else.

**M7. Lines 575-577**
- **Text**: `inspect_record(workspace)` writes `inspection-<seq>.json`.
- **Rationale**: The signature has no `seq` parameter. `seal` at line 572 takes `seq` explicitly. The described signature does not match the output file it names.

**M8. Lines 584-585**
- **Text**: "source ref + register/field/op, or a normalized statement hash" and "reuse, append, never reuse retired numbers"
- **Rationale**:
  - The condition for choosing one key form over the other is not given.
  - "Reuse" appears twice with opposite meanings: reuse a known key's ID, and never reuse a retired ID.
  - "Retired" is not defined.
  - Suggested wording: "Existing keys keep their ID. New keys get the next unused number. IDs whose key no longer appears are retired and never reassigned."

**M9. Lines 593-594**
- **Text**: "the four criteria" and "per-ref resolution"
- **Rationale**: The criteria are not named, and "per-ref resolution" is shorthand that is never expanded. Name the four criteria, or give the exact §9 subsection.

**M10. Line 653 and line 774**
- **Text**: "actionable finding"
- **Rationale**: This term controls whether REWORK runs, but it is never defined. Say which `inspector_outcome` values, or which finding fields, count as actionable. For example: "at least one requirement with `inspector_outcome: FINDINGS`".

**M11. Line 655 vs line 775**: attempt states and their result are inconsistent.
- **Text**: Line 655 says "A FAILED, CANCELLED or STOPPED attempt goes to VALIDATING". Line 775 says "a FAILED or STOPPED attempt goes to a terminal state".
- **Rationale**: CANCELLED is missing from the test. VALIDATING is called a "terminal state", which it is not. Use one state list and one target state in both places.

**M12. Line 690**
- **Text**: "The reply finishes the run"
- **Rationale**: "The reply" has no antecedent. It is unclear whether it means the inspector model reply, the `visit` result, or the node's return value. Name the function or node.

**M13. Lines 705-706 and 717**
- **Text**: "`de46c4ba…58c3`" and "`8f5fb6b7…6039`"
- **Rationale**: The digests are cut short. A profile cannot pin a value with an ellipsis in it. Line 710 explains why the manifest sha is still missing, but the blob sha and the qwen digest are presented as known. Give the full values, or mark them as an explicit prerequisite like line 710 does.

**M14. Lines 713-720**: the profile paths are abbreviated and the inspector profile is unnamed.
- **Text**:
  - Paths are written as `...-lab-qwen38-author-q8.yaml`, `...-q38-aspice-stepwise-medium.yaml` and `...-q38-delivery-first.yaml`.
  - The sentence "The inspector profile copies..." never says which of the two new files is the inspector profile.
- **Rationale**: The reader has to guess both the path prefix and that the file without "author" is the inspector. Every other item gives full paths. Write out the paths, and label each file's role.

## Additional Majors (cross-reference and reproducibility)

The next five items are also Major. They are listed separately because they concern cross-references and reproducibility rather than wording.

**M15. Lines 735-738**
- **Text**: "operations intent set;" and "the existing stack stop/start;"
- **Rationale**: The script is said to call "only existing commands", but those commands are not named. Give the exact command or entry point for each step.

**M16. Lines 758-760**
- **Text**: Item 29 marks this design document as "(Create)".
- **Rationale**: The file already exists; this review is reading it. Item 29 also has no "Proposed Changes" field, which every other item has. Change it to "(Modify)" and state what "finalized" involves.

**M17. Lines 783-785**
- **Text**: "Template rendering on/off;" and "schema-mode probe keyed by digest."
- **Rationale**: These describe conditions but not expected results. The other test lines in item 30 state the expected outcome. State what each case must assert.

**M18. Line 804 vs lines 480, 753, 827 and 829**
- **Text**: `NATIVE_NOT_RUN` at line 804, and `NOT_RUN` everywhere else.
- **Rationale**: Two labels are used for one status. `NOT_RUN` is also an `inspector_outcome` value (line 517), so the bare form is ambiguous. Pick one label for native-run status and use it everywhere.

**M19. Line 814**
- **Text**: "`FORGE_DATA_ROOT=$B`" and "the repo venv python"
- **Rationale**: `$B` is not defined, and the interpreter is described informally. The environment cannot be reproduced as written. Give the concrete path, or a reference to where it is defined.

## Nit

**N1. Line 473**: "they protect everything after". This is vague and cannot be measured. State what they protect, for example "later increments depend on the corrected cache key and manifest lookup".

**N2. Line 489**: "This closes the name-only cache key." "Closes" is figurative. Suggested wording: "This removes the defect where the cache key contained only the model name."

**N3. Lines 487, 625, 626 and 636**: "around line…" and "near line…". These approximate anchors drift as the code changes, and they sit next to exact ranges (lines 651, 656 and 661). Anchor them to function names.

**N4. Line 498**: "as today". This is a relative time reference. Use "as in `876d75f`".

**N5. Lines 527 and 604**: the item numbers "5a" and "13a" are left over from editing. Renumber the items.

**N6. Lines 531-533 and 735-738**: these list items end in semicolons and "and", while all other lists use fragments with no trailing punctuation. Make them match.

**N7. Lines 551 and 570**: "Validator + doc." and "module + CLI". The "+" is informal. Use "and".

**N8. Lines 591 and 599**: the Type / Scope field holds a full CLI invocation, while other items put a category there. Move the invocation into Proposed Changes.

**N9. Line 606**: `<score…>`. The ellipsis inside a placeholder is unclear. Use `<score.json>...`.

**N10. Lines 618 and 637**: "admitted identity probe" and "a golden test pins it". These are informal terms. Suggested wording: "an identity probe admitted by the gateway" and "a golden-output test asserts it".

**N11. Line 643**: "terminal and SUCCEEDED". SUCCEEDED already implies terminal, so "terminal" is redundant.

**N12. Lines 681-682**: "The RM0486 literals … come from `target_profile.primary_manual`". This reads as current behaviour. Suggested wording: "are replaced by `target_profile.primary_manual`".

**N13. Lines 710-711**: "must be read on Omniverse2 read-only … It is never guessed." The word "read" is repeated, and the second sentence restates the first. Suggested wording: "Obtain the manifest sha256 from Omniverse2 (read-only access) before completing this file."

**N14. Lines 480, 747 and 828-829**: "owner window" is jargon and is not defined in this range. Line 480 also lacks a verb ("until an owner window"). Line 828 has one ("opens").

**N15. Line 827**: "tiny" is a subjective size word. Name the fixture file.

**N16. Spelling is mixed.** British forms ("behaviour" at 489 and 524, "labelling" at 804) appear alongside American forms ("normalized" at 584, "finalized" at 760). Choose one.

**N17. Line wrapping and footer.** Lines 508, 591, 803 and 816 exceed the wrap width used elsewhere in the range. Line 832, "*Drafted with EGM*", is tool attribution that carries no engineering content.

Files reviewed:
- /home/jefferson/.claude/plugins/cache/egm/egm/0.1.0/agents/style.md
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md
