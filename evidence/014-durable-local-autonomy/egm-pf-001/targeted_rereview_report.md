# Targeted re-review of revision 2 (EGM Goldfish)

Target: `docs/designs/forge-c-process-first-ornith-qwen.md` revision 2 (1,034 lines), 2026-10-31.
Three fresh native reviewers were given the resolution record (`goldfish_review_report.md`) as explicit context.
Each was asked to verify RC-1 to RC-9 against code and to report new Blockers and Majors.

## Cluster verdicts (all three reviewers agree)

| Cluster | Design | Impl-readiness | Codebase | Consolidated |
|---|---|---|---|---|
| RC-1 shape / intake | Partial (Blocker: no mission link) | Partial (Blockers: intake artefacts, mission, handoff delivery, REWORK assembly) | Partial (B1, B2) | **OPEN Blocker** |
| RC-2 activation | Partial | Partial (Blocker: stale `serving_instance`, Fabro config) | Partial (M4, M5) | **OPEN Blocker** |
| RC-3 admission | Partial | Partial (Blocker: trial reference, model-key policy) | Partial (M6, M7) | **OPEN Blocker** |
| RC-4 QM exception | Resolved | Partial (call order) | Facts correct; call order | Major |
| RC-5 profiles | Partial | Partial | Partial (M9, M10) | Major |
| RC-6 inspector outcomes | Partial | Partial | Partial (M1, M2: continuation nodes, item-to-SWR map) | Major |
| RC-7 scorer | Partial (Blocker: disposition contract) | Partial (Blocker) | Partial (B4, M14) | **OPEN Blocker** |
| RC-8 leakage | Partial | Partial (Blocker: role rule) | Partial (B3, B5) | **OPEN Blocker** |
| RC-9 risks | Resolved | Resolved | Correct | Resolved |

## Open Blockers (deduplicated)

1. **No lab provisioning step.** `afo.cli submit` needs an envelope plus an in-repository launch manifest, an
   authorization and a mission link. With durable autonomy on, `MISSION_LINK_REQUIRED` BLOCKs the order. The
   existing pattern to follow is `afo/overnight.py`.
2. **The handoff cannot enter the next order.** `prepare` refuses inputs outside `REPO_ROOT`, and handoffs live under
   `state_dir`.
3. **The rebuild needs group documents.** REWORK/INSPECT `materialize` cannot rebuild from rendered artifacts:
   `swe1.assemble` needs the per-group documents, which the handoff must carry. `provided:` task names would also
   break `(task, key)`.
4. **The activation tool leaves out required steps:** the stale `serving_instance`, Fabro `settings.toml`, the
   tool's own environment and re-exec, the full quiescence checks (`RESERVED`, pending executions, verification
   jobs), the deployed unit names and the health polling.
5. **The trial binding is wrong.** It is a content-addressed trial document referenced in the launch manifest,
   authorized by a `qualification-product-014:<sha>` grant, and it needs `order_ids`. `allowed_model_profiles` takes
   model keys, not profile IDs.
6. **The disposition contract is wrong.** `review-disposition` is learning-only and cannot express obligation
   coverage, so a lab-scoped disposition contract is needed.
7. **The leakage rules are wrong.** The role denylist refuses the RM inputs themselves, and the only device header has
   an "oracle" role. `evaluation_holdout` is a launch-manifest argument, not a work-order field.

## Notable new Majors

- **G3 hash and `adapter_revision`.** `adapter_revision` is the factory commit, so hashing it invalidates every
  checkpoint on every commit and breaks `revalidate_author_tasks`. `IDENTITY` has 9 fields (`task_class`).
- **Time boxes are resumable.** The lab graphs drop the continuation nodes, and `DONE` is not a reply status.
- **A successful lab order dead-letters.** It ends BLOCKED, which raises an alert.
- **Ornith request overrides conflict with admission.** The `reasoning` comparison clashes, and `--reasoning-format`
  emission is undefined.

---

## Raw report — `egm-design`

# Targeted re-review of revision 2 (Design Critic Goldfish, Mode REVIEW)

**Target:** `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md`, lines 1–682. Lines 683 onward were used as context only.

I read the persona, the feature-spec standard, the resolution record, SOURCE-INVENTORY and the target, and checked every claim below against the repository code. In what follows, `ff/` means `factory/python/forge_factory/` under the repository root.

**Verdict:** Not ready to approve. Two of the nine clusters are resolved, and seven are only partly resolved. Two Blockers remain (in RC-1 and RC-7), plus a set of Majors. Most of the Majors are cases where the design names a mechanism that the code does not support.

## Cluster verdicts

### RC-1: Role/attempt shape. PARTIALLY RESOLVED

**What now fits:**
- Single-role orders go through `scheduler.preflight` one at a time. One attempt per order stays well under `max_order_attempts` (`ff/afo/scheduler.py:137`).
- `operations_epoch` is stamped at admission (`ff/afo/queue.py:412`). Orders submitted after `activate` are therefore not quarantined by the fence at `ff/afo/dispatch.py:84`.
- Skipping `recover` and going to VALIDATING matches `reconcile_running` (`dispatch.py:345-349`). `verified_attempt` returns None when there is no recovery plan (`ff/afo/completion_receipt.py:382-384`).

**Remaining problems:**

- **Blocker — lab orders are never linked to a mission (lines 315–317, CUJ 1 at 176–182).**
  - The design tells the operator to submit with `python -m forge_factory.afo.cli submit`. That command calls `store.submit` without registering or linking a mission (`ff/afo/cli.py:85-91`).
  - Under `FORGE_DURABLE_AUTONOMY=1`, preflight calls `MissionLedger.for_order`. With no link this raises `MISSION_LINK_REQUIRED` (`ff/afo/mission_ledger.py:66-71`).
  - The scheduler treats that as terminal and BLOCKs the order (`scheduler.py:92-123, 215-225`).
  - The existing safe pattern registers and links the mission before submitting (`ff/afo/overnight.py:21-47`).
  - The design never mentions missions. It does not say whether there is one mission per experiment, per driver or per order. It also gives no `max_attempts`, which counts every PRODUCT execution (`mission_ledger.py:179`), no deadline and no token limits. As written, every lab order BLOCKs on its first scheduler cycle.
  - **Fix:** specify mission provisioning and limits, and use an overnight-style provisioning step instead of a plain `afo.cli submit`.

- **Major — the handoff does not carry what partial REWORK needs (lines 285–287, §8).**
  - The design reuses the `provided_requirements.materialize` pattern and says unchanged groups "are copied from the materialized baseline". But that pattern rebuilds the artifacts from per-group structured documents through `swe1.assemble(ws, inv, results, cross)` (`ff/provided_requirements.py:66-85`).
  - The §8 handoff carries only the rendered artifacts (`.md`, `.reqif`, `.csv`, `register_effects.json`) and per-requirement hashes. It carries no group documents, so `assemble` cannot be fed for the groups that are not re-authored.
  - **Fix:** add the frozen per-group author outputs (and the crosscutting document) to `artifacts[]`.

- **Major — where generated orders live is undefined.**
  - `process_lab.next` writes orders to an arbitrary `--out` (line 315).
  - `store.submit` requires `input_manifest_ref` to resolve inside the repository (`queue.py:286-288`). The launcher reads `REPO_ROOT / manifest["example"]` (`ff/afo/runtime.py:122`).
  - Generated INSPECT/REWORK example directories must therefore land inside the checkout. That interacts with `factory_revision()` dirtiness and with the trial's `source_revision` binding (`ff/afo/product_role_trial.py:41`).
  - **Fix:** state the location and its provenance.

### RC-2: Swap state machine. PARTIALLY RESOLVED

**What is now correct:**
- Every `Intent.set` increments the epoch and checks `expected_epoch` (`ff/afo/operations.py:89-101`). An operator STOP during activation therefore defeats the compare-and-set resume, as CUJ 2 (lines 184–191) requires.
- `stack.start` is fenced to RUNNING with an unchanged epoch (`operations.py:366-375`, `ff/lrtx/stack.py:341-364`).
- `stack.stop` performs shutdown and `settle_shutdown` (`stack.py:692-710`).
- Swap-STOP and operator STOP are now distinct.

**Remaining problem:**

- **Major — the 8-step procedure (lines 319–350) leaves out steps the code requires.** These steps are in the cited source script, `evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py:92-133`, but not in the design's step list or in the LAB-T09 stubs.
  - **Stale `serving_instance`.** `_stop` keeps `serving_instance` in `run/services.json`. On the next `_start`, `serving_instance(s)` refuses with `SERVING_INSTANCE_REFERENCE_INVALID` when the profile id or sha differs (`stack.py:450-474, 537-538`). With the shared deployment root (lines 349–350), every cross-profile switch fails this way. The source script removes `serving_instance` and `serving_holder` first (`activate.py:92-95`).
  - **Stale Fabro config.** `fabro/settings.toml`, including the model list and default model, is written only by `init` (`stack.py:213`). The source script regenerates it (`activate.py:107`). Without that, Fabro keeps advertising the previous profile's model.
  - **Wrong profile in the tool's own environment.** `_managed_scope` checks the calling process's `FORGE_OPERATIONS_PROFILE` (`stack.py:420-425`). The source script updates its environment and re-execs itself as a fresh process (`activate.py:105, 111`). Step 3 rewrites only `conductor.env` and the units.
  - **Health checked too early.** With `recovery=True`, `_start` waits only 5 s per process (`stack.py:661`). The source script then polls for up to 120 s (`activate.py:124-129`). Step 6 is a single check, so a 37.8 GB load would be recorded as `STOPPED_FAILED_LOAD`.
  - **Fix:** list these four actions as explicit steps, with test assertions.

### RC-3: Role-capability admission. PARTIALLY RESOLVED

**What is correct:** `product_role_trial` is the right path. It replaces the receipt requirement (`ff/lrtx/role_capability.py:132-136, 168-169`).

**Remaining problems (Major):**

- **The trial binding described at lines 303–305 does not exist in code.**
  - A trial is not "signed in the per-experiment operator policy". It is a content-addressed state document whose reference must be exactly `{"path": "afo/product-role-trials/<sha>.json", "sha256": <sha>}` in the launch manifest (`product_role_trial.py:17-26`, `ff/afo/product_job.py:70`).
  - It is authorized by a grant whose `signed_runbook_ref` is `qualification-product-014:<sha>` (`product_role_trial.py:93-99`).
  - The trial must also list every `order_id` (line 40), match the factory commit (41), name one profile and one model (42–43) and carry a deadline. Arm A therefore needs at least two trials, and the INSPECT/REWORK order IDs must be predicted (`order_id_for(tenant, request_id)`, `queue.py:295`) or the trial re-signed for each batch.
  - **Fix:** describe the real trial document and grant, the `order_ids` rule and the number of trials per arm.

- **`allowed_model_profiles` will hold the wrong values.**
  - Line 304 says the lab *profiles* go into `engineering.allowed_model_profiles`.
  - The scheduler compares the envelope's `model_profile`, which is a model key, against that list (`scheduler.py:88-89`; also `ff/afo/local_agent.py:110`). The existing policies list `qwen3.8:27b-q8_0` (`evidence/014-durable-local-autonomy/aspice-stepwise-product-20261030/records/proposed-policy.yaml:40-41`).
  - Listing profile ids gives `MODEL_NOT_ALLOWED`, which is terminal BLOCKED (`scheduler.py:224`).
  - **Fix:** say "model keys" here, consistent with line 264.

### RC-4: QM purpose and the stepwise inspector. RESOLVED

The scoped exception in §12 (lines 528–532) matches the refusal at `ff/release/qm.py:100-104`. The failed-before test design is adequate.

**Implementation note (not a Blocker):** `validate_profile` runs at `ff/workorder.py:732`, before `spec` is read (line 763) and before any manifest exists. "Passes the manifest flag" (line 836) therefore means reading the work-order spec earlier.

### RC-5: Lab profiles. PARTIALLY RESOLVED

**What is resolved:**
- The Ornith key set, the context source and the VRAM arithmetic are explicit.
- The `hf.co` path and the `reasoning_format` changes match `stack.py:383, 408-409`.
- The binary-feasibility correction is consistent with SOURCE-INVENTORY §A.

**Remaining problems (Major):**

- **The Q5 thinking settings conflict with admission.**
  - Lines 509–510 record `request_overrides` (`enable_thinking`, `thinking_budget_tokens`) in the identity's `reasoning` field.
  - Admission compares `identity["reasoning"]` with `body["reasoning_effort"]` (`role_capability.py:164`). Trial matching does the same (`product_role_trial.py:125`).
  - The result is either refusal (`ROLE_CAPABILITY_REASONING_OR_SCHEMA_CHANGED` or `PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED`), or the thinking budget never enters the identity, which defeats G3 (lines 95–97) for the Q5 knob.
  - Neither `role_capability.py` nor `product_role_trial.py` is in the change list.
  - **Fix:** define how the overrides enter the identity and the admission comparison, and add those two files.

- **The Qwen lab profile has no runtime block.**
  - The design body specifies context only for Ornith (§11).
  - Context item 21 gives no `OLLAMA_CONTEXT_LENGTH`, KV type, `llama_server` decision or `vram_required_gb`. Context item 3 makes `vram_required_gb` mandatory for `process_lab` profiles, and both profiles share the `llama` port.
  - The context and serving path for arm B and for the Qwen inspector are therefore undefined.

### RC-6: Inspector outcome mapping. PARTIALLY RESOLVED

**What is resolved:** the mapping table, the definition of "actionable", the "repair budget", the removal of `NOT_RUN`, and writing the record on failure (lines 377–394).

**Remaining problem (Major) — "item covering the SWR" (line 386) is undefined.**
- Checklist items carry no mapping to SWRs. Each item is judged against every SWR target (`ff/lrtx/review_semantic.py:1133-1137`).
- The stepwise behaviour, step and check questions (`review_semantic.py:1142-1213, 1247-1257`) are not checklist items. Their failures only turn the visit FAILED (lines 1276–1277).
- Read literally, one INVALID item makes every SWR `NOT_INSPECTED`. A sub-question failure has no defined mapping at all.
- **Fix:** state the rule explicitly (for example, "every item covers every SWR; a stepwise question covers the SWRs it names"), so that `NO_FINDING` vs `NOT_INSPECTED` is deterministic.

### RC-7: Scorer. PARTIALLY RESOLVED

**What is resolved:**
- Deterministic checks are defined, keywords never decide, and the grammar for a judgeable criterion is fixed.
- The reused helpers exist (`ff/assurance/swe12.py:59-79`, `ff/assurance/hardware.py:98`).
- `register_effects.json` is always written by the structured SWE.1 path (`ff/lrtx/swe1.py:584`).

**Remaining problem:**

- **Blocker — `COVERED_BY_DISPOSITION` (lines 457–460) depends on a contract that cannot express it.**
  - The named contract is `specs/014-durable-local-autonomy/contracts/review-disposition.schema.json`. It has `additionalProperties: false` and `subject.kind` GAP or FINDING only.
  - Its verdict enum is CONFIRMED_DEFECT, FALSE_FINDING, MISSING_INPUT or OUT_OF_SCOPE. It requires `export_sha256` and `run_key`.
  - It has `use: const LEARNING_SET_ONLY`, and its description says a disposition "feeds the learning set only".
  - There is no field for an obligation id, the handoff sha, or a covered/not-covered verdict.
  - Predicates only decide register obligations. Every critical behaviour, caller_contract, interface, state or error obligation therefore stays `UNKNOWN_NEEDS_HUMAN`. MEETS becomes unreachable, and LAB-T13 ("a signed disposition covers an obligation") cannot be implemented as specified.
  - **Fix:** add a lab-scoped disposition contract to the five runtime schemas. Do not repurpose the learning-only contract.

### RC-8: Leakage. PARTIALLY RESOLVED

**What is resolved:**
- The omissions match the leaking inputs of the 0014g example (`examples/0014g-st-crc-idr-qwen-delivery/workorder.json:63-92, 97, 120-131, 141`).
- The holdout is honoured by author packets (`ff/lrtx/structured.py:130-136`) and by `ff/knowledge/context.py:29`.

**Remaining problems (Major):**

- **The role denylist refuses the primary sources (lines 548–549).**
  - Forbidding any input role that *contains* `reference` matches the reference-manual inputs themselves: `reference_manual_crc_chapter`, `reference_manual_memory_map` and `reference_manual_register_conventions` (0014g lines 39–48).
  - The `reference_manual` prefix is how the code identifies primary sources (`provided_requirements.py:45-46`). §1 line 270 depends on those inputs too.
  - The CRC lab example would be refused by its own rule.
  - **Fix:** use an exact denylist or an allowlist of roles.

- **The holdout is checked in the wrong place.**
  - `evaluation_holdout` is a launch-manifest argument (`runtime.py:140`). It is written into the workspace manifest only after `prepare` returns (`workorder.py:838-840`).
  - The intake contract is placed next to `delivery_first_contract` at `workorder.py:406`, where the flag is not yet visible. Context item 22 puts the flag in `workorder.json`, which the runtime never reads for this purpose.
  - A spec-based check can pass while the run executes without the holdout, so lessons would be retrieved.
  - **Fix:** check the effective workspace manifest after line 840.

### RC-9: Risks & Mitigations. RESOLVED

The section at lines 653–668 covers all ten risks the resolution asked for. It does not yet list the new risks below.

## New Majors introduced by revision 2

1. **Major — a successful lab order raises an operator alert (§2, lines 290–299).**
   - Using BLOCKED for a good outcome (`PROCESS_LAB_HANDOFF_SEALED`) feeds the dead-letter sweep, which records a case for every BLOCKED order (`ff/afo/deadletter.py:82-88`).
   - Each sealed handoff therefore opens a dead-letter case and enqueues a WARN alert asking the operator to "Review ... the BLOCKED evidence" (`deadletter.py:54-79`).
   - With up to 5 orders per driver, this puts noise into the dead-letter and alert channels, and could hide real failures.
   - **Fix:** exclude `PROCESS_LAB_*` reasons from dead-lettering, or add a lab-specific terminal handling path. Add this to Risks.

2. Revision 2 also introduces the activation-tool omissions (RC-2), the reasoning-override conflict with admission (RC-5) and the materialize/partial REWORK gap (RC-1). These are reported above.

**Outside the requested clusters (RC-10, Medium):** G3 and §5 (lines 95–97, 354–356) call their 8-field list "the `role_capability.IDENTITY` tuple". The real tuple has 9 fields and includes `task_class` (`role_capability.py:11-21`).

## Key files
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/scheduler.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/overnight.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/product_role_trial.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/deadletter.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/stack.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/role_capability.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/review_semantic.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/workorder.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/specs/014-durable-local-autonomy/contracts/review-disposition.schema.json`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py`

## Raw report — `egm-implementation-readiness`

**Implementation-readiness re-review: revision 2, lines 683 to end**

Result: **Not ready to implement.** RC-9 is resolved. RC-1 to RC-8 are each only partly resolved. Each owner choice (D1′, D7, `product_role_trial`, the activation tool, the scorer rules, the leakage controls) is the right direction and fits the code. But checked against the actual code, five of them still contain Blockers, and the other three still have Major gaps. The implementer would have to make design decisions to finish them.

I read the persona, the standard, the resolution record, the constitution, the source inventory and the whole target. Lines 1–682 were read as context. All file and line references below were checked in the repository at `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first`. `ff/` = `factory/python/forge_factory/`.

| Cluster | Status | Worst open severity |
|---|---|---|
| RC-1 Order shape vs queue/admission | PARTIALLY RESOLVED | Blocker |
| RC-2 Swap state machine | PARTIALLY RESOLVED | Blocker |
| RC-3 Role-capability admission | PARTIALLY RESOLVED | Blocker |
| RC-4 QM exception | PARTIALLY RESOLVED | Major |
| RC-5 Lab profiles | PARTIALLY RESOLVED | Major |
| RC-6 Inspector outcome mapping | PARTIALLY RESOLVED | Major |
| RC-7 Scorer | PARTIALLY RESOLVED | Blocker |
| RC-8 Leakage controls | PARTIALLY RESOLVED | Blocker |
| RC-9 Risks & Mitigations | RESOLVED | – |

---

### RC-1: PARTIALLY RESOLVED

**What is fixed.** With D1′, the earlier code conflicts no longer apply:
*   Each order has one attempt and goes through `scheduler.preflight` as a normal QUEUED order.
*   Resume is not used.
*   Switches happen only at an empty queue, so the epoch fence cannot strand a launch.

**Blocker: the queue intake artefacts are not specified** (lines 805–814, 908–916; §1 lines 253–275).
*   `afo.cli submit` takes a work-order envelope. It needs `input_manifest_ref`, `manifest_sha256`, `authorization_ref`, `driver_class` and `model_profile` (`ff/afo/cli.py:32-45,85-93`).
*   That envelope must point to a launch manifest inside the repository (`ff/afo/queue.py:286-290`).
*   The launcher reads `example`, `profile`, `model_profile`, `evaluation_holdout` and `product_role_trial` from that launch manifest, not from `workorder.json` (`ff/afo/runtime.py:69-144`, `ff/afo/product_job.py:40,70`).
*   Item 11 only says `next` "writes one work order per eligible driver". The design never mentions an envelope, a launch manifest, `authorization_ref` or a `submit_workorder` grant.

**Blocker: no mission link.**
*   The activation tool needs managed serving, and managed serving needs `FORGE_DURABLE_AUTONOMY=1` (`ff/lrtx/stack.py:416-417`).
*   With that flag set, `preflight` calls `MissionLedger.for_order`. Without a mission link this raises `MISSION_LINK_REQUIRED`, and `cycle` BLOCKs the order (`ff/afo/scheduler.py:92-123,214-225`; `ff/afo/mission_ledger.py:66-71`).
*   The design never mentions missions. It does not say whether there is one mission per experiment, per driver or per order, nor what `max_attempts`, `max_jobs`, `max_tokens` and `deadline` should be. At 5 orders per driver, one mission would need `max_attempts` of at least 5N.

**Blocker: the handoff cannot be delivered into the next workspace** (items 9, 11 and 14).
*   `prepare` refuses any input outside `REPO_ROOT`. It also flattens every input to `inputs/<basename>` (`ff/workorder.py:210-216`).
*   The previous order's `handoff.json`, its artifact copies and `findings.json` live under `state_dir()/workorders/<wo>/workspace/…` (`ff/common.py:24-25`, `ff/afo/runtime.py:151-153`). That is outside the repository.
*   Nothing says how these files get into the INSPECT/REWORK workspace or at which paths.
*   Nothing says how `next --orders <dir>` finds "the latest terminal handoff per driver". The workspace name is only known from the attempt's `workspace_ref` in the queue database.

**Blocker: REWORK cannot be assembled as written** (§2 lines 285–287, item 19 lines 873–874).
*   The plan says "other tasks come from the materialized baseline". But `swe1.assemble` needs the structured group document for every task (`ff/lrtx/swe1.py:491-506`; `GROUP_SCHEMA` at `:51-56`).
*   The handoff carries only the rendered md/reqif/csv/effects files (§8 lines 406–407).
*   The implementer must choose: carry the `.forge-run/lrtx/SWE.1` task records in the handoff, rebuild them from markdown, or do something else.
*   It is also not stated how `findings.json` reaches the author. Today findings come from `V.rework_findings` over the inspection records (`ff/lrtx/swe1.py:694`).

**Major: the gate-exhausted handoff and the materialize baseline are undefined.**
*   On a rejection, the author gate freezes nothing (`ff/inspection/gate.py:168-176`). A FAILED SWE.1 visit assembles nothing (`ff/lrtx/swe1.py:756-757`).
*   So for `PROCESS_LAB_AUTHOR_GATE_EXHAUSTED` (line 297) there is no `baseline` and there are no `artifacts[]`. Neither the schema nor the graph edge from gate exhaustion to `lab_handoff` covers this case.
*   Item 9 says `materialize` "freezes a baseline through the existing author gate", but the INSPECT graph (line 288) has no gate node.
*   The SWE.1 baseline covers `traceability/` and `safety/` (`ff/inspection/engine.py:28`). `artifacts[]` omits `upstream_gaps.md` and the safety file, so the rebuilt baseline hash cannot equal the source hash. The plan does not say whether that is expected.

**Major: lab-order detection is unspecified.** Item 16 branches on "lab orders" in `reconcile_running`, `validate` and `preflight`. A queue row has no lab field, and the plan does not say where `process_lab` is read from (launch manifest, example `workorder.json`, or workspace manifest).

### RC-2: PARTIALLY RESOLVED

**What is fixed.** Resuming before `stack.start` satisfies `fenced_call` (`ff/afo/operations.py:366-375`, `ff/lrtx/stack.py:341-364`). The empty-queue precondition means no bound order can be blocked.

**Blocker: following §4 literally fails at step 5** (lines 330–341, item 12).
*   `_stop` clears `processes` but keeps `serving_instance` (`ff/lrtx/stack.py:767-771`).
*   On the next start, `_start` validates that record against the *new* profile and raises `SERVING_INSTANCE_REFERENCE_INVALID` on the profile and sha mismatch (`ff/lrtx/stack.py:537-538,450-474`).
*   The source script that §4 says it is "built from" removes `serving_instance` and `serving_holder` first (`evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py:92-95`). Step 3 does not.
*   Fabro's `settings.toml` lists only the active profile's models (`stack.py:131-136`). `_start` reuses that file and never regenerates it. The source script rewrites it (`activate.py:107`); step 3 does not.

**Major: the tool's own process environment is unspecified.**
*   `stack.stop` and `settle_shutdown` act on `os.environ["FORGE_OPERATIONS_PROFILE"]` (`ff/afo/operations.py:401-409`).
*   `stack.start` refuses unless that variable equals the target profile (`stack.py:420-425`).
*   Managed serving needs `FORGE_DURABLE_AUTONOMY` and `FORGE_OPERATIONS_INTENT`.
*   The source script loads `conductor.env` and switches `os.environ` between stop and start (`activate.py:5-7,105`). The plan does not.

**Major: the outcome rules contradict each other** (lines 343–347, 970–974, CUJ 2 lines 184–191).
*   The record's outcome list omits `ACTIVATE_EPOCH_CHANGED`.
*   `ACTIVATE_NOT_QUIESCENT` is described as "changes nothing", yet it is also listed as a record outcome.
*   An operator STOP between steps 2 and 4 matches both "epoch change → `ACTIVATE_EPOCH_CHANGED`" and "STOP before step 7 → `STOPPED_BY_OPERATOR`".
*   CUJ 2's "grant revoked" has no detection step.
*   `stack.stop` can return an unsettled result without raising (`stack.py:702-703`), and no outcome is defined for that.
*   Step 2's `stack.stop` calls `synchronize` without `expected_epoch` (`stack.py:700`). So G2's compare-and-set covers only the resume.

**Major: unit names and re-rendering are wrong or undecided.**
*   Item 12 takes unit names from `ff/afo/services.py`, whose list has `forge-afo-watchdog.service`/`.timer` (`services.py:30-38`).
*   The deployed Omniverse2 units are `forge-afo-watchdog-014-omniverse2.{service,timer}` and `forge-qwen-mission-recorder.service` (`activate.py:49,102`).
*   The Conductor's `ExecStart` also pins `lrtx.stack exec --profile <selected>` (`services.py:117-122`). The plan does not decide between `services.render()` and the source script's text replacement.

### RC-3: PARTIALLY RESOLVED

**What is fixed.** The decision fits the code: one profile and one model per order matches `authorized()` (`ff/afo/product_role_trial.py:37-47`).

**Blocker: the binding mechanism contradicts the code** (§3 lines 301–306, item 22 line 915, item 23 line 922).
*   The trial reference is read from the launch manifest as `{"path": "afo/product-role-trials/<sha>.json", "sha256": …}` (`ff/afo/product_job.py:70`, `product_role_trial.py:17-26`).
*   It is authorized by an `authz` grant for `recover_workorder` with `signed_runbook_ref == "qualification-product-014:<sha>"` (`product_role_trial.py:93-99`), not by the policy.
*   Item 22's "placeholder name in `workorder.json` which the operator's signed policy resolves" has no counterpart in the code.

**The trial document's content is not specified anywhere.**
*   It needs `order_ids`, so the orders must exist before the trial is written.
*   It also needs `source_revision`, `profile`, `model` and `deadline_epoch`.
*   Each role needs identity entries with all nine `IDENTITY` fields, including `task_class` (`ff/lrtx/role_capability.py:11-21`). Their `reasoning`, `schema_mode` and `sampling` must exactly match every request (`product_role_trial.py:116-129`). For the stepwise inspector, sampling is forced to temperature 0 plus seed (`ff/lrtx/review_semantic.py:285-287`).
*   The plan does not say who writes it, when, or with what values.

**Blocker: `allowed_model_profiles` holds the wrong kind of value.**
*   §3 says the policy lists "the lab profiles" in `engineering.allowed_model_profiles`.
*   But `preflight` compares that list with the envelope's `model_profile`, which is the *model key* (`scheduler.py:88-89`; example in `ff/afo/qualification_inputs.py:346,361`).
*   As written, every lab order would be BLOCKED with `MODEL_NOT_ALLOWED`.

### RC-4: PARTIALLY RESOLVED

**What is fixed.** The rule in §12 and test LAB-T06 are precise.

**Major: the exception cannot be wired where item 14 says.**
*   `qm.validate_profile` is called in `workorder.run` at `ff/workorder.py:732`.
*   That is before `workorder.json` is read (`:763`) and before `prepare` and the contract call (`:406-408`).
*   So item 14's "passes the manifest flag" (line 836) is impossible at that call site.
*   The plan must say to read the spec and run `process_lab.contract(spec)` before line 732. That changes the documented refusal order (`:762`).

### RC-5: PARTIALLY RESOLVED

**What is fixed:** the context single source, the `hf.co` manifest path, the digest rule and the VRAM arithmetic.

**Major: the "full key set" is not full** (items 20–21, lines 876–906).
*   Item 20 is missing keys the code needs:
    *   `id`, `version`, `status`, `provider`, `models.default`;
    *   `runtime.llama_server.model`, which is required (`stack.py:381`);
    *   `runtime.timeout_scale` (`ff/lrtx/profile.py:245`);
    *   `deployment.root_env`, `ports`, `forbidden_ports`, `writable_env`, `shared_readonly`;
    *   `existing_deployment.roots` and `network.required` (`profile.py:111-125,233-237`);
    *   `admission.max_inflight`, `max_queue`, `max_wait_s` (`stack.py:590-596`).
*   "One port set" is never given, so the implementer has to pick ports.
*   Item 21 has no `runtime` block at all: no Qwen context, no KV setting, no `llama_server`/MTP.
*   Item 21 keeps "`role_efforts` only" from the source profile, but that profile's `gateway.reasoning` also holds `effort` and `extra_output_tokens`. Whether those are kept is left open.

**Major: the `reasoning_format` behaviour is undecided.**
*   Today `--reasoning-format` is emitted only when `reasoning_effort` is set (`stack.py:408-409`).
*   The Ornith profile has no effort.
*   The plan does not say whether the flag is emitted anyway, and still keep "byte-identical argv" for other profiles.

**Major: the `request_overrides` plumbing is missing** (item 4).
*   The gateway is a separate process configured by environment variables (`stack.py:591-599`, `ff/llm_gateway.py:83-90`). `sanitize_request` has no access to the profile, and no new environment variable is named.
*   Precedence over the existing `enable_thinking` rewrite (`llm_gateway.py:142-148`) is not decided.
*   "Refused at profile load" has nowhere to live: `profile.load` validates nothing (`profile.py:32-43`).
*   "Recorded in identity `reasoning`" (line 510) conflicts with the trial and admission check that `reasoning == body.reasoning_effort` (`role_capability.py:164`, `product_role_trial.py:125`).

### RC-6: PARTIALLY RESOLVED

**Major: "covers the SWR" is undefined** (§7 lines 382–387, item 18).
*   Checklist items cover the whole document.
*   Failures in sub-questions (`behaviours-i`, `step-<q>`, `coverage-i`) are plain issue strings with no SWR mapping (`review_semantic.py:1149-1151,1165-1167,1208-1210`).
*   There is no precedence rule for an SWR that has a standing claim while another item covering it is INVALID.

**Major: the time-box and status mechanics are unspecified.**
*   On a time box, `V.Continue` escapes `_visit` and all per-item state is lost (`review_semantic.py:1118-1121`). The plan does not say how partial outcomes are captured.
*   The reply status `DONE` does not exist. Replies only route on PASS (`ff/lrtx/review.py:278-281`), and the continue-check routes on CONTINUE (`ff/lrtx/runner.py:83-92`).
*   The lab inspector's edges and whether its continuation nodes stay are not defined.

### RC-7: PARTIALLY RESOLVED

**Blocker: `COVERED_BY_DISPOSITION` relies on a contract that cannot express it** (§9 lines 457–460, LAB-T13).
*   `specs/014-durable-local-autonomy/contracts/review-disposition.schema.json` allows `subject.kind` only GAP|FINDING (lines 51–55).
*   Its `verdict` allows only CONFIRMED_DEFECT|FALSE_FINDING|MISSING_INPUT|OUT_OF_SCOPE (lines 74–80).
*   It requires `export_sha256`/`run_key`, sets `additionalProperties: false`, and fixes `use: LEARNING_SET_ONLY`.
*   It has no obligation id, no handoff sha and no "covered" verdict. Signature checking (namespace, signer list) is also unspecified.

**Major: ref resolution has no section input** (§9 line 446, step 3).
*   `swe12._pages` and `hardware.index` need the RM section directory (`ff/assurance/swe12.py:59-79`, `ff/assurance/hardware.py:98`).
*   The scorer CLI has no workspace or sections argument, and the artifacts directory holds only four files.

**Major: budget rows break the scoring thresholds.**
*   Budget rows cite "work-order budget (owner development target)" (`ff/lrtx/swe1.py:430-442`).
*   That is neither an RM ref nor ASSUMPTION; no lrtx code emits ASSUMPTION.
*   Their `Verification:` lines ("SWE.6 Robot suite checks…") contain none of the five method phrases.
*   If these count as `UNRESOLVED_REF` or as non-judgeable, MEETS becomes unreachable. The plan does not say which.
*   The "observable outcome" grammar has no lexicon or regex.

### RC-8: PARTIALLY RESOLVED

**Blocker: the forbidden-role rule rejects the lab's own required inputs** (§13 lines 548–549, item 8 line 780, LAB-T15).
*   Any role containing `reference` is refused.
*   But the RM inputs the lab must declare use roles such as `reference_manual_crc_chapter` (`examples/0014g-st-crc-idr-qwen-delivery/workorder.json:39-49`).
*   §1's primary-source check also selects inputs by the `reference_manual`/`datasheet` role prefix (`ff/provided_requirements.py:45-46`).
*   The plan must either rename those roles or narrow the rule.

**Major: the input list is not enumerated** (item 22).
*   "The CMSIS device header" does not exist for CRC. The only device header is `forge_crc_device.h`, whose role contains `oracle`.
*   It is not stated which inputs are kept: datasheet, memory map, register conventions, `conversion_provenance`, guideline.
*   It is not stated whether `operation_scope` (minus `prompt_overrides`) and `simulation_performance` are kept.

**Major: `evaluation_holdout` is set in the wrong place.**
*   Item 22 puts it in `workorder.json`.
*   Holdout actually comes from the launcher argument and is written *after* `prepare` (`ff/afo/runtime.py:140`, `ff/workorder.py:838-840`).
*   So `contract(spec)` at intake cannot see the manifest flag, and nothing links the spec flag to the manifest flag.

### RC-9: RESOLVED

The Risks & Mitigations section (lines 653–668) covers every risk the resolution record listed.

---

### New Majors outside RC-1 to RC-9

1.  **G3 identity mismatch (affects items 1–2).**
    *   `role_capability.IDENTITY` has nine fields, including `task_class` (`ff/lrtx/role_capability.py:11-21`). §5 and item 1 list eight.
    *   Many builders call `packet()` inside `run_task` lambdas (for example `swe1.group_packet`). Item 2 threads `identity` only through the runner, `visit.run_task` and `structured.packet`.
    *   The plumbing (a ContextVar like `RECOVERY_WORKSPACE` at `ff/lrtx/structured.py:118`, or explicit arguments) is undecided.
2.  **Lab graph contract (item 15).**
    *   `process_lab.workflow(manifest)` must return `(dot, nodes)` with node role bindings, as `build` does. Those bindings are used by `binding_for`, `agent_preflight` and `mcp_preflight` (`ff/workorder.py:948-965`).
    *   It also needs the structured model, `timeout_s` and `visit_time_s`, which come from `local_profile_structured` (`ff/workorder.py:658-665`) and not from the manifest.
    *   Edge conditions, `max_visits` and continuation nodes are unspecified.

The Verification Plan (lines 1010–1027) is concrete, and the test paths it names exist (`tests/spec/validate_design.py`, `factory/python/tests/peripheral_golden.py`). But several of its tests (LAB-T09, LAB-T13, LAB-T15) assert behaviour that the gaps above leave undefined.

## Raw report — `egm-codebase-details`

**Codebase-details re-review: revision 2 of `forge-c-process-first-ornith-qwen.md`**

I read the persona, the standard, the target file (all 1034 lines), the resolution record and SOURCE-INVENTORY. I checked every cited code fact against the repository. **Verdict: not ready for implementation.** Five Blockers and many Majors remain. Most of the line citations are accurate. The failures are in the reuse claims and in how existing behaviour is described.

## What checks out

- **Line references:**
  - `workorder.py:293` and `:406`
  - `builder.py:212`
  - `dispatch.py:84-87`
  - `services.py:100-110`
  - `product_job.py:40`
  - `request_admission.py:49`
  - `structured.py:172,237`
  - `swe1.py:508`
  - `qm.py:100-104`
  - `runner.py:45-55`
  - `brownfield/resume.py:314`
  - `knowledge/context.py:29`
  - `run_benchmark.py:332`
- **Policy values:** `max_order_attempts: 3` and `max_concurrent_workorders: 1`.
- **Ornith speed study:** the binary path in `server-instance.json`, `--jinja --reasoning auto --reasoning-format deepseek`, the GGUF sha and size, the 4/9, 2/9 and 3/9 figures, and template sha `3a1e4036…` all match the evidence.
- **Reuse targets that exist:** `swe12.cited_pages` / `_pages`, `assurance.hardware.index`, `profile.model_identity`, and `stack.status()['health']` keys (fabro, gateway, ollama, llama_server).
- **Test fakes:** `_scripted` (`test_lrtx_swe1.py:79`, reused by `test_lrtx_v2_swe1.py`), `FakeFabro.view` (`test_afo_m3_reconcile.py:18`, reused by `test_afo_m4_recovery.py:187`) and `peripheral_golden.normalized_graph` all exist.
- **`afo/contracts.py` loader pattern:** described correctly. It uses `Draft202012Validator` with `FormatChecker`, a `NAMES` allow-list and `require()`.

## Blockers

**B1. A later order cannot receive the handoff through intake (§1 l.262, l.267-272; CUJ 6; item 9).**
- `workorder.prepare` refuses every input outside `REPO_ROOT` (`workorder.py:211-213`).
- `provided_requirements` follows the same rule (`:218-221`).
- `afo.cli submit` requires the launch manifest inside the repo (`queue.py:286-288`).
- A sealed `handoff.json`, its findings file and its artifact copies live in a prior workspace under `state_dir`. So "names the input handoff by path and sha256" fails before the new checks run.
- The design never says how the handoff and the `process-lab/SWE.1/artifacts/` copies get into the new workspace. It also never says where `process_lab.next` writes the work order, the launch manifest and the submit envelope. They must sit under the repo, which leaves the tree dirty.

**B2. `materialize` cannot "rebuild from the handoff's artifact copies using `swe1.assemble`'s writers" (item 9 l.790-791).**
- `assemble(ws, inv, results, cross)` (`swe1.py:491`) takes per-group JSON task documents. It does not take rendered artifacts. `provided_requirements.materialize` (`:54-96`) works only because it is given group documents.
- The artifacts lose data that a rebuild needs:
  - `not_covered` is gone.
  - `value` is dropped for non-write effects (`swe1.py:554-555`), but `EFFECT_SCHEMA` requires it.
  - `key` appears only in `assembly.json`.
- The handoff (§8) carries none of the group documents.
- The provided path also renames tasks to `provided:<id>`, while the author path uses `requirements:<id>` (`swe1.py:742`). That changes every `(task, key)` pair and breaks §6 ID reuse.

**B3. The isolation rule in §13 refuses the lab's own required inputs (l.548-549).**
- Every RM0486 input role contains "reference": `reference_manual_crc_chapter`, `_memory_map` and `_register_conventions` (`0014g` workorder.json l.40-49).
- The only device header available, `forge_crc_device.h`, has role `delivery_first_oracle_or_device_fixture`, which contains "oracle".
- §1 l.270 compares handoff hashes against the "declared reference-manual inputs", and `provided_requirements.py:46` looks those up by role prefix `reference_manual`.
- So every lab order would hit `PROCESS_LAB_INPUT_ROLE_FORBIDDEN`. No CMSIS header exists among the 0014g inputs.

**B4. The existing `review-disposition` contract cannot do what §9 step 4 (l.457-460) and LAB-T13 need.**
- `review-disposition.schema.json` has:
  - `additionalProperties: false`;
  - `subject.kind` limited to `GAP|FINDING`;
  - `verdict` limited to `CONFIRMED_DEFECT|FALSE_FINDING|MISSING_INPUT|OUT_OF_SCOPE`;
  - `export_sha256`, with no handoff sha;
  - `use: const LEARNING_SET_ONLY`, and a description saying it "feeds the learning set only".
- It has no obligation subject, no handoff binding and no covered / not-covered verdict.
- No file entry lists a schema change, and `validate_contracts.py` pins the schema inventory.

**B5. `evaluation_holdout` is not a work-order field, and intake runs before it is set (§1 l.259; item 8 `PROCESS_LAB_HOLDOUT_REQUIRED`; item 22 l.914).**
- It is a `run()` keyword (`workorder.py:706`), supplied by the AFO launch manifest (`runtime.py:140`).
- It is written to the manifest only after `prepare` returns (`:838-840`). The delivery-first contract hook at `:406` therefore cannot see it.
- `prepare` never reads the key from `workorder.json`, so setting it in the example has no effect. The leakage control depends on this flag.

## Majors

**M1. Time boxes are resumable, not terminal, and the lab graphs drop the continuation nodes (§2 l.283-288; §7 table l.386; item 18 l.864).**
- `V.Continue` saves the task checkpoint and returns `CONTINUE`. `structured_authors.continuation()` then adds `_cont` / `_more` nodes that resume the visit (`builder.py:257-273`, `runner.py:83-92`).
- The design's AUTHOR and INSPECT graphs have no such nodes. With the default `visit_time_s` of 1200, a long author visit or a stepwise inspection would end at the first time box.
- `DONE` is not a reply status. Only `PASS`, `REWORK`, `FAILED` and `CONTINUE` exist, and `_reply` maps any non-PASS status to `next_action: rework` (`review.py:280-281`).

**M2. The per-SWR outcome mapping depends on a relation the code does not have (§7 l.385-386).**
- "Every checklist item covering the SWR" assumes an item-to-SWR covering map. Inspection items are checklist IDs, and claims carry `target_id`. Nothing in `review_semantic._visit` maps items to SWRs.
- When `Continue` is raised, the per-item state in `_visit` is lost before `visit()` catches it (`review_semantic.py:1118-1121`). So "always writes the record" also needs a code restructure that the design does not describe.

**M3. The identity tuple is incomplete, and "miss once" is wrong (§5 l.354-356; G3; G7; item 2).**
- `role_capability.IDENTITY` has 9 fields. It includes `task_class` (`role_capability.py:11-21`), and `key()` refuses any other field set.
- `adapter_revision` equals the factory commit (`:157-159`). Hashing it invalidates every structured checkpoint on every commit, not once.
- It also breaks the existing cross-revision `revalidate_author_tasks` reuse, which matches on `base_hash` (`visit.py:123-143`, `workorder.py:790-796`).
- Item 2 names no source for `role`, `schema_mode`, `adapter_revision`, `context_tokens` or `task_class`.

**M4. The activation tool leaves out steps that `activate.py` needs (§4 l.319-347; item 12).**
- **Fabro config:** `activate.py:107` rewrites `fabro/settings.toml` with `stack.fabro_config`. `_start` never rewrites it; only `init` does (`stack.py:213`). The model catalogue and default model are profile-specific (`stack.py:131-175`).
- **Process environment:** `activate.py` sets `FORGE_OPERATIONS_PROFILE` and `FORGE_LRTX_PROFILE` in its own process (l.105) and re-execs itself so stale cached modules are not used (l.111-113). This matters because `_managed_scope` compares the caller's environment with the profile (`stack.py:423-425`). The tool needs the old profile for `stack stop` and the new one for `stack start`.
- **Quiescence checks:** `activate.py` `quiet()` refuses any request-ledger row that is not `QUIESCENT` (`RESERVED` included), any `Executions.pending()` row, and any active `afo_verification_jobs` row. The design checks only `SENT` / `UNKNOWN` and omits the other two.
- **Unit names:** `activate.py` stops `forge-afo-watchdog-014-omniverse2.{service,timer}` and `forge-qwen-mission-recorder.service`. Neither is in `services.UNITS`, so "unit names come from `services.py`" (l.822) is wrong for the real deployment.
- **Health polling:** `recovery=True` waits only 5 s per service (`stack.py:661`). `activate.py` then polls health for 120 s. The design gives no timeout.

**M5. `stack stop` is not compare-and-set and does not return the stop epoch (§4 steps 2 and 4; G2).**
- `stack.stop` calls `synchronize('shutdown')` without `expected_epoch` and returns `{"stopped": …}` (`stack.py:700-709`).
- If `settle_shutdown` is not settled, it returns early and stops no processes. The design has no outcome for that case.
- The expected epoch in step 4 must therefore be stated exactly (step-1 epoch + 1).

**M6. `allowed_model_profiles` holds model keys, not profile IDs (§3 l.304-305; CUJ 1).**
- The scheduler checks `env["model_profile"]` against it (`scheduler.py:88`), and §1 defines that value as the model key.
- The policy must list `hf.co/ornith-ai/…:Q8_0` and `qwen3.8:27b-q8_0`, not `lab-*` profile IDs.

**M7. The `product_role_trial` binding is described wrongly (§3; item 22 l.915; runbook).**
- The trial is its own document. It must be referenced exactly as `{"path": "afo/product-role-trials/<sha>.json", "sha256": <sha>}` (`product_role_trial.py:21`).
- That reference must sit in the AFO launch manifest (`product_job.py:70`). The `workorder.json` spec is the wrong place.
- The trial must list `order_ids`, `source_revision` equal to the commit, and a `deadline_epoch`. It is authorized by a grant whose `signed_runbook_ref` is `qualification-product-014:<sha>` (`:37-47`, `:93-99`). It is not "signed in the operator policy".
- Nothing resolves a "placeholder name". REWORK order IDs must be predictable in advance, so the design has to fix a `request_id` scheme.

**M8. The Ornith reasoning overrides conflict with existing gateway and admission behaviour (§11 l.509-510; item 4).**
- `sanitize_request` already sets `chat_template_kwargs.enable_thinking` from `gateway.reasoning` (`llm_gateway.py:142-148`). The new `request_overrides` has no stated precedence over it.
- Admission compares `identity.reasoning` with `body.reasoning_effort` (`role_capability.py:164`, `product_role_trial.py:125`). Putting the overrides into `reasoning` would refuse every request.
- No "profile load" validation hook exists; `profile.load` checks only schema and id. `stack._start` would also need a new gateway environment variable, which item 3 does not list.
- Three other `sanitize_request(policy=…)` callers (`product_role_trial.py:196`, `durable_agent.py:327,348`) would measure requests without the overrides.

**M9. The rule for `--reasoning-format` is unclear (§11 l.506; item 3).**
- Today the flag is emitted only when `reasoning_effort` is set (`stack.py:408-409`).
- The Ornith profile has no effort. Either Ornith gets no flag, which differs from the speed study, or emitting a default `deepseek` changes the argv of existing profiles that have no effort.
- The speed-study argv also has `-t 12 -tb 24 --spec-type none --fit off --metrics` and `-c 262144`, which the stack never emits. If the bundled build defaults to `--fit on`, the VRAM and context budget in §11 is affected.

**M10. The lab profiles do not have a full key set (items 20 and 21).**
- `llama_server_spec` requires `runtime.llama_server.model` (`stack.py:381`), which item 20 does not list.
- `inspect_phases_by_layer` is missing, so the inspector stays an agent node (`workorder.py:644`).
- Also missing: `id`, `version`, `status`, `provider`, `models.default`, `runtime.timeout_scale`, `existing_deployment`, `network`, `deployment.{root_env, ports, forbidden_ports, writable_env, shared_readonly}`.
- Item 21 copies only `role_efforts`, which covers inspectors only. The author effort lives in `gateway.reasoning[model].effort` and `runtime.llama_server.reasoning_effort`.

**M11. The resident-profile check needs a `scheduler.cycle` change (item 16 l.850-852).**
- `cycle` blocks only on listed issue codes and defers everything else (`scheduler.py:215-237`). To make `RESIDENT_PROFILE_MISMATCH` a refusal, `cycle` must change too.
- `preflight` reads the launch manifest, not the workspace manifest, so it is unclear where it finds `process_lab.profile`.
- `os.environ[...]` raises when the variable is unset.

**M12. `qm.validate_profile` runs before the work order is read (item 14 l.836; item 17).**
- Its only call site is `workorder.py:732`. The spec is read at `:763`, and the manifest does not exist yet. "Passes the manifest flag" needs a change in call order.

**M13. The builder reuse claim needs refactoring (§2 l.279-281; item 15).**
- `swap`, `pipe` and `continuation` are closures nested inside `structured_authors` and cannot be imported.
- `build` must return `(dot, nodes)`, as `delivery_first.workflow` does. Nodes feed `binding_for` and the `.forge-run/binding.json` that `write_scoped` authorizes against.
- The design gives no roles for the new `materialize`, `lab_inspect_record` and `lab_handoff` nodes.

**M14. The scorer definitions do not fit the real artifacts (§8 l.413-414; §9 l.451-468).**
- No row ever has source `ASSUMPTION`. Budget rows use `"work-order budget (owner development target)"` and simulation rows use their own string (`swe1.py:430,447`). These rows would become `UNRESOLVED_REF`, and `MEETS` would be impossible.
- The scorer arguments do not include the section directory that `_pages` / `index` need.
- The "judgeable" grammar ignores the structured `verified_by` field. The budget rows' fixed text ("SWE.6 Robot suite checks…") contains none of the listed method words.

**M15. Contract fixtures in a subdirectory would be rejected (item 7).**
- `validate_contracts.py:78` rejects any fixture name with a directory part. `examples/process-lab/` breaks this unless the validator changes.
- The manifest scope is `SPEC_CONTRACTS_ONLY_NOT_RUNTIME`, which conflicts with runtime-loaded schemas.

## Nits

- Item 1 l.712: `structured.py` has no `build` function. `input_hash` is computed in `packet()` at line 237.
- §6 l.369: `swe1.py:44-45` is only the key pattern. Uniqueness is enforced in `validate_group` at `:319-320`. Re-authoring one group also changes the cross-cutting packet (`:749`).
- Item 25 l.959: the file is `factory/python/tests/peripheral_golden.py`. The stepwise-inspector scripted answers live in `test_lrtx_v2_review.py`, not the two files cited.
- RC-8 / §13: inspector lessons are controlled by the profile flag `structured.inspection_lessons` (`review_semantic.py:1036-1044`), not by `evaluation_holdout`.
- §4 step 1: `WAITING_EXTERNAL_CHANGE` is missing from the list of order states.
- Problem 2: the cited `swtrace.py:101` is actually at `:103`.

## RC-1 to RC-9: are the code facts behind each fix correct?

| Cluster | Verdict | Reason |
|---|---|---|
| RC-1 | Partly | The rejection reasons for revision-1's D1 are correct. The fix's reuse claim (the `provided_requirements` pattern, rebuild from artifacts) is wrong: B1, B2. |
| RC-2 | Partly | The cited fence, stack, units, shutdown and expected-epoch facts are correct. The activation procedure leaves out required `activate.py` steps: M4, M5. |
| RC-3 | Partly | The single-profile, single-model rule (`authorized` l.42-43) is correct. The signing, reference form, `order_ids` and policy meaning are wrong: M6, M7, M8. |
| RC-4 | Correct facts, incomplete fix | `qm.py` and `runner.py` are cited correctly. The call order is missing: M12. |
| RC-5 | Partly | `llama_server_spec` facts are correct. The `--reasoning-format` rule and the profile key set are wrong or incomplete: M9, M10. |
| RC-6 | Partly | "No record on failure" is correct. The meaning of time boxes and the reply status are wrong, and the item-to-SWR mapping does not exist: M1, M2. |
| RC-7 | Partly | The `swe12` and `hardware` reuse is correct. The disposition contract claim is wrong (B4), and so are the source and assumption facts (M14). |
| RC-8 | Partly | The 0014g inventory is correct. Holdout placement and the role rule are wrong: B3, B5. |
| RC-9 | Correct | Few code facts, and the ones cited (provider exit proof, before-images) are right. |

No files were modified.
