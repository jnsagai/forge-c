# Targeted re-review of revision 3 (EGM Goldfish)

Target: `docs/designs/forge-c-process-first-ornith-qwen.md` revision 3 (1,196 lines), 2026-10-31. Revision 2 is kept as
`design-r2-as-reviewed.md`. Three fresh native reviewers were given `targeted_rereview_report.md` as context.

## Status of the 7 revision-2 Blockers

| # | Blocker | Design | Impl-readiness | Codebase | Consolidated |
|---|---|---|---|---|---|
| 1 | Provisioning / mission | Partial (Major) | Partial (Blocker) | Partial (B-1) | **OPEN Blocker**: mission limits are capped per order and the deadline is fixed at first registration |
| 2 | Handoff transport | Resolved (+Major) | Partial (Major) | Correct (+M-6) | Major: copied relative input paths break |
| 3 | Group documents | Partial (Major) | Partial (Blocker) | Correct | **OPEN Blocker**: INSPECT handoffs lack group documents; REWORK needs checkpoints to reach the repair path |
| 4 | Activation steps | Partial (Major) | Partial (Major) | Partial | Major: failure path vs `stack.stop` epoch; policy/grant install; unit text; deployment root |
| 5 | Trial binding | Partial (Blocker-class) | Partial (Blocker) | Mostly (M-7/M-8) | **OPEN Blocker**: needs `authorization_ref` and a context allocation for 262K Qwen |
| 6 | Disposition contract | Resolved | Resolved | Correct | **RESOLVED** |
| 7 | Leakage rules | Partial (N3: owner-contract text) | Resolved | Correct | Major: `IDR-CONTRACT.md` names the reviewed requirements and oracles |

The previous Majors (G3, time boxes, dead-letter, reasoning overrides vs admission) are **RESOLVED** by all three.

## New Blocker introduced by revision 3

- **Profile composition.** Under copy-plus-overrides, the Ornith profile inherits `fabro_context_tokens`/`context_limit_tokens`
  262144 against `OLLAMA_CONTEXT_LENGTH` 32768, so `fabro_config` raises `FABRO_CONTEXT_EXCEEDS_PROVIDER` at activation.
  It also inherits `reasoning_effort: medium` and the batch settings. The Qwen lab profile lacks `vram_required_gb` and
  inherits 262K context. Flagged by all three reviewers.

## New Majors

- Grant scopes take `pl-` request IDs, while the trial takes `afo-` order IDs.
- Node write bindings: `swe1-inspector` is read-only, and `swe1-author` cannot write `process-lab/`.
- `max_visits` is a builder constant, not a profile value.
- Gate-failed handoffs have no INSPECT path.
- The scorer has no work-order input.
- No re-attempt path, and no headroom for one.
- Disposition signing load is up to 5× per driver.
- The activation record is written on the wrong host.
- State is lost across `os.execv`.

## Native evidence received meanwhile (Q6)

See `../ornith-protocol-20261031/README.md`.
- **Strict json_schema works** with thinking on and off.
- **Thinking on, as the factory calls it today, failed 2/2 on a realistic SWE.1 packet**: the reserve was exhausted by
  thinking. Thinking off passed (16 requirements, 22.9 s).
- **Budget 0 is ignored**; only `enable_thinking: false` turns thinking off.
- **VRAM peak** 37.4 GB at 32K context with f16 KV; load time about 5.4 s.

---

## Raw report — `egm-design`

# Targeted re-review of revision 3 (Design Critic Goldfish, Mode REVIEW)

**Target:** `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md`, lines 1–904. "Detailed Implementation Plan" starts at line 905; I read it as context only. `ff/` = `factory/python/forge_factory/`.

**Inputs read:** the persona, the feature-spec standard, the re-review report, the constitution, the PROCESS-FIRST plan (relevant sections), SOURCE-INVENTORY and the target. I checked every claim below against the code.

**Verdict:** not ready to approve. Revision 3 is a real improvement:
- Blocker 6 and three of the four listed Majors are fully resolved.
- The other four original Blockers are reduced to Majors.
- One original Blocker (5) stays open in substance: the trial document as specified is refused at admission.
- Revision 3 adds one new Blocker: the Ornith profile as composed cannot be activated.
- It also adds several new Majors.

## Status of the 7 open Blockers

### 1. Lab provisioning step — PARTIALLY RESOLVED (now Major)

**Resolved:**
- §3 (lines 375–407) now follows `afo/overnight.provision_order` in the right order: register, link, submit, ID check (`ff/afo/overnight.py:21-47`).
- The order-ID formula matches `ff/afo/queue.py:136-137`.
- `MISSION_LINK_REQUIRED` (`ff/afo/mission_ledger.py:66-71`) is avoided.

**Major — mission limits and deadline are mis-stated (lines 385–389).**
- `mission_admin.register` caps `max_attempts` at `budgets.max_order_attempts` (`ff/afo/mission_admin.py:44,55`).
  - That value is 3 in the repository policy (`config/factory/afo-policy.yaml:35`), and the design says that policy stays unedited (line 423).
  - The design never says that the per-experiment policy must have `max_order_attempts ≥ 5`, or what its request and token caps are (`mission_admin.py:45-50`).
- The deadline is set once, at first registration: `≤ min(grant expiry, now + max_order_wall_seconds)` (`mission_admin.py:55-57`).
  - Later provisioning reuses the stored limits (`overnight.py:36-38`).
  - The cap is enforced on every order through `dispatch.enforce_deadlines` (`ff/afo/dispatch.py:375`) and the product job deadline (`ff/afo/product_job.py:42-43`).
- So the whole five-order chain per driver, including four operator switches, must finish within one `max_order_wall_seconds` of the AUTHOR provisioning. This cap is 28,800 s in the existing per-experiment policy (`aspice-stepwise-product-20261030/records/proposed-policy.yaml:33`).
- Line 389 ("capped … per order") is therefore wrong. With N drivers in batches, driver 1's deadline must cover all N AUTHOR orders, plus a switch, plus N INSPECT orders, and so on.
- **Fix:** state the per-experiment policy budget values, and either size the wall budget for the whole chain or use `mission_deadline.extend`. Add this to Risks.

**Major — grant scopes match request IDs, not order IDs.**
- `approve`, `request_for` and `cycle` all send `{"order_id": env["request_id"]}` (`ff/afo/cli.py:43`, `ff/afo/local_agent.py:64`, `ff/afo/scheduler.py:200`).
- So `scope.order_ids` in the submit, launch, recover and qualification grants must list the `pl-…` request IDs.
- The trial's `order_ids` must list the `afo-…` queue IDs (`ff/afo/product_role_trial.py:40`).
- Lines 383–384 and 405–406 blur the two. Filling grants with `afo-` IDs gives `AUTH_OUT_OF_SCOPE` (`ff/afo/authz.py:95-98`).

### 2. Handoff cannot enter the next order — RESOLVED, with one residual Major

**Resolved:**
- The git-ignored `<repo>/process-lab/` folder satisfies `prepare`'s rule that inputs live in the repository (`ff/workorder.py:210-216`) and the queue's manifest check (`ff/afo/queue.py:286-288`).
- `factory_revision` ignores untracked files (`ff/workorder.py:41`), and ignored files never appear in porcelain.
- `next` locates the source handoff through `runtime.workspace_of` (line 1004; `ff/afo/runtime.py:151-153`).

**Major — copying `workorder.json` breaks its input paths (line 294).**
- Input paths are relative to the example folder: `../0014-crc-st/…`, and `IDR-CONTRACT.md` in the example itself (`examples/0014g-st-crc-idr-qwen-delivery/workorder.json:35-92`).
- `prepare` resolves them as `example / item["path"]` (`ff/workorder.py:211`) and reads `load_upstream(example)` (`:236`).
- A copy placed at `process-lab/<exp>/<driver>/<seq>/` raises `FileNotFoundError`.
- **Fix:** state that `next` rewrites the paths relative to the new folder (or uses repository-absolute paths), and how upstream files are carried.

### 3. Rebuild needs group documents — PARTIALLY RESOLVED (now Major)

**Resolved:**
- The handoff carries the group documents and the cross-cutting document (lines 505–508, 568–570).
- `assemble` accepts `{"task", "doc"}` records (`ff/lrtx/swe1.py:499-506`; `base_hash` is optional at `:518`).
- Task names stay `requirements:<id>` (`swe1.py:742`).

**Major — partial REWORK drops the findings (lines 527–530).**
- `run_task` repairs locally only if a checkpoint exists in the workspace (`ff/lrtx/visit.py:158-174`).
- A fresh REWORK workspace has no `packets/requirements__<g>.json`. So `start` is None and `p = base`: the findings are dropped from the packet and the task is re-authored from scratch.
- **Fix:** `materialize` must write VALID checkpoint records (`doc`, `status`, and `base_hash` recomputed in this workspace), or REWORK must pass the handoff document as `start`.

**Major — gate-failed handoffs have no defined path in INSPECT (lines 354–356, 367; `next` at 1003–1004).**
- A handoff with `gate_status: FAILED` (or no baseline) is still `PROCESS_LAB_HANDOFF_SEALED`, and `next` accepts it.
- In INSPECT, the materialized documents go to `swe1_author_gate`, which rejects them again.
- In the strict graph, a gate failure routes to `swe1_route` and then `swe1_author` (`ff/workflow/builder.py:456-459`). Neither node is in the INSPECT graph.
- Also, `pipe` makes the gate read `.forge-run/lrtx/SWE.1/reply.json` (`builder.py:243-251, 291-292`), so `materialize` must write a PASS reply. The design does not say so.
- **Fix:** either `next` refuses gate-FAILED handoffs, or the INSPECT and REWORK gate-failure edges are defined.

### 4. Activation tool omissions — PARTIALLY RESOLVED (now Major)

**Resolved** (matching `evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py`):
- `serving_instance` / `serving_holder` removal (`activate.py:92-95`);
- `settings.toml` regeneration (`:107`);
- the environment switch and re-exec (`:105, 111`);
- the four `quiet()` conditions (`:21-26`);
- the deployed unit names (`:49, 102`);
- health polling.

**Major — the health-failure path contradicts `stack.stop` (lines 479–481).**
- Managed `stack.stop` calls `synchronize(store, "shutdown", …)` without `expected_epoch` (`ff/lrtx/stack.py:700`). That writes STOPPED at a new epoch E3 (`ff/afo/operations.py:89-113`).
- The next step, "pause with expected epoch E2", then raises `OPERATIONS_INTENT_SUPERSEDED` (`operations.py:94-95`).
- **Fix:** define the end state as STOPPED at E3 (no pause), and record E3.

**Major — the deployment root switch is unspecified.**
- The lab profile sets `deployment.default_root: /mnt/data/forge-c/process-lab` (line 720).
- But `stack.settings` prefers `root_env` (`FORGE_LRTX_ROOT`) over `default_root` (`stack.py:52`). The rendered units pin `FORGE_LRTX_ROOT` and `FORGE_STATE_DIR` to the old root (`ff/afo/services.py:105-116`).
- Step 5 only text-replaces the profile ID, so one of two things happens:
  - The new root is ignored, and the lab runs inside the production deployment's queue DB, missions and dead letters.
  - Or, if a separate root is intended, nothing creates it: the venv and `ollama-0.34.0` binaries (`stack.py:390`), the `ollama-models` with the 37.8 GB GGUF (`:381-389`) and the Conductor DB (`:354-356`). The tool also does not rewrite the root values in `conductor.env` and the units.
- **Fix:** decide which root is used, and specify provisioning and rewriting accordingly.

**Major — the policy and grants are never installed.**
- The source script installs the per-experiment policy and the grants (`activate.py:98-99, 106`).
- The design says only that they are "signed" (lines 191–194). Nothing points `FORGE_AFO_POLICY` (`ff/afo/policy.py:89`) at the per-experiment policy, or places the grants in `authz.AUTH_DIR`.

### 5. Trial binding — PARTIALLY RESOLVED (open; substantively still Blocker-class)

**Resolved:**
- the exact reference form (`product_role_trial.py:21`), the launch-manifest placement (`product_job.py:70`) and the `qualification-product-014:` grant (`:98`);
- `order_ids` predicted, `source_revision`, one profile and one model (`:37-47`);
- the nine `IDENTITY` fields (`ff/lrtx/role_capability.py:11-21`);
- model keys in `allowed_model_profiles` (lines 421–422; `scheduler.py:88`).

**Major — the trial field list omits `authorization_ref` (lines 410–418).**
- `authorized` reads `trial.get("authorization_ref")` (`product_role_trial.py:93`). Without it, `authz.find` returns `AUTH_NOT_REFERENCED` (`authz.py:106-107`), so every lab request is refused.
- The trial must name the grant ID while the grant names the trial sha. The signing order (grant ID first, then trial, then grant) needs stating.

**Major — the Qwen context ceiling is unbound.**
- The Qwen lab profile inherits `OLLAMA_CONTEXT_LENGTH: 262144` (base profile, line 34), so the packet identity has `context_tokens` 262144 (`ff/lrtx/structured.py:56, 98`).
- A trial identity above 65,536 requires `context_allocation_ref` and `profile_sha256` with a `PASS_ALLOCATION_ONLY` record (`product_role_trial.py:55-79`). The design does not mention it.
- A trial identity at or below 65,536 refuses larger requests with `CAPABILITY_LIMIT` (`role_capability.py:173-178`).
- The value of `context_tokens` per role is not given.

### 6. Disposition contract — RESOLVED

- A new `forge-c/process-lab-disposition/1` contract has an obligation subject, a handoff sha binding and a COVERED / NOT_COVERED / NOT_APPLICABLE verdict (lines 609–618).
- Alternative M rejects reuse of the learning-only contract.
- The verify routine cited exists (`ff/offline/disposition.py:84-88`).

### 7. Leakage rules — PARTIALLY RESOLVED

**Resolved:**
- The exact role allowlist (lines 300–311) admits `reference_manual_*` and renames the oracle-labelled device header (`forge_crc_device.h` has no reference answers).
- The holdout check moves after the manifest write (`ff/workorder.py:838-840`).
- `purpose` and the `process_lab` block come from the launch manifest (`ff/afo/runtime.py:140-141`).

**New Major — see N3:** the kept owner contract leaks the reference material.

## Status of the listed Majors

- **G3 hash and `adapter_revision`: RESOLVED.**
  - `structured.packet_identity` leaves out `adapter_revision` and includes the profile config sha (`ff/lrtx/structured.py:60-99`).
  - The trial uses all nine `IDENTITY` fields (line 416).
- **Time boxes are resumable: RESOLVED.**
  - The continuation nodes are kept (lines 346–353), matching `builder.py:257-273`.
  - There is no `DONE` status. CONTINUE loops, and PASS, REWORK and FAILED all route to `lab_inspect_record`.
- **A successful lab order dead-letters: RESOLVED.**
  - Only `PROCESS_LAB_HANDOFF_SEALED` is skipped (lines 371–373).
  - `deadletter.sweep` is the only entry point (`ff/afo/conductor.py:142`, `ff/afo/deadletter.py:82-91`).
- **Ornith overrides conflict with admission: RESOLVED.**
  - `body.reasoning_effort` keeps the effort string, so the comparisons at `role_capability.py:164` and `product_role_trial.py:125` still hold.
  - `thinking_budget_tokens` travels in `FORGE_GATEWAY_REASONING` (`stack.py:37-39, 598`).
  - The `--reasoning-format` emission rule is defined (lines 677–679).
  - This is superseded in practice by N1.

## New findings introduced by revision 3

**N1 — Blocker: the Ornith profile, as composed, cannot be activated (lines 705–736).**
- The Ornith profile is "a copy of the Qwen lab profile" with only the listed keys overridden. The Qwen lab profile in turn inherits the base `runtime` block.
- It therefore keeps `fabro_context_tokens: 262144` and `context_limit_tokens: 262144` (base profile lines 26–27) while overriding `OLLAMA_CONTEXT_LENGTH` to 32768.
- `stack.fabro_config` raises `FABRO_CONTEXT_EXCEEDS_PROVIDER` (`stack.py:129-130`). This happens at activation step 5, mid-install, and there is no outcome defined for it.
- If `runtime.llama_server` overrides are merged key by key ("every key not listed stays as in the base"):
  - Ornith also inherits `reasoning_effort: medium` and `batch_tokens` / `microbatch_tokens` 1024 / 512 (base lines 42–45).
  - Its argv then gets `--reasoning-effort medium --reasoning-format deepseek` plus the new `--reasoning-format` (`stack.py:408-409`). This differs from the measured speed-study argv.
  - It contradicts plan §5.2: "Do not copy Qwen's MTP, sampling, tokenization or thinking controls to Ornith without native tests."
- The claim "no key is left to the implementer" (line 706) is false.
- **Fix:** list the full Ornith `runtime` block, and state whether nested blocks are replaced or merged.

**N2 — Major: no retry path, and the risk is not recorded.**
- Request IDs are fixed per (seq, role). The trial lists exactly those order IDs. Mission `max_attempts` is 5, with no slack. Dispatch skips recovery for lab orders.
- So any single infrastructure failure (`PROCESS_LAB_RUN_FAILED`, a wall-deadline BLOCK) permanently ends that driver's chain, and re-submission is impossible under the same IDs.
- **Fix:** pre-declare re-attempt request IDs, add trial and mission headroom, or accept this explicitly in Risks.

**N3 — Major: the kept owner contract leaks the reference material (§13, line 763).**
- `IDR-CONTRACT.md` is kept verbatim as `process_lab_owner_contract`.
- It says "The original nine externally reviewed requirements are supplied as a reference" (`examples/0014g-st-crc-idr-qwen-delivery/IDR-CONTRACT.md:27-29`). That input is omitted in the lab and is the likely oracle source.
- It also names the host oracle and target probe (`:31-37`), carries Delivery-First chronology instructions (`:39-41`), and states the expected behaviour (`:19-23`).
- The leakage tests (lines 770–774) look for oracle paths and hashes, so they would not catch this.
- **Fix:** write a lab-specific owner contract with no reference to the reviewed requirements or the oracle, and add a test for that.

**N4 — Major: the disposition signing load is understated (line 878).**
- Dispositions are bound to `handoff_sha256` (line 611), and every role's handoff is scored (line 651).
- Behavioural obligations therefore need a new signed disposition for each handoff: up to 5 per driver.
- The "Human adjudication load" risk row does not reflect this multiplier.

## Key files

- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/mission_admin.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/product_role_trial.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/cli.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/services.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/stack.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/visit.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/workflow/builder.py`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/config/factory/profiles/local-rtx-v2-omniverse2-q38-aspice-stepwise-medium.yaml`
- `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/examples/0014g-st-crc-idr-qwen-delivery/IDR-CONTRACT.md`

## Raw report — `egm-implementation-readiness`

# Implementation-readiness re-review: revision 3, "Detailed Implementation Plan" (line 905) to the end

**Result: not ready to implement.** Of the 7 open Blockers, 3 are now resolved and 4 are only partly resolved. Three of those four still contain a Blocker. Revision 3 also introduces one new Blocker, in the lab profile definitions. The direction of every fix fits the code. The remaining failures are cases where the specified values or steps fail against concrete checks in the code.

I read the persona, the standard, the re-review report, the constitution, SOURCE-INVENTORY and the whole target (1,196 lines; lines 1–904 as context). I checked every claim below in the repository. `ff/` = `factory/python/forge_factory/`.

| # | Item | Status | Worst open severity |
|---|---|---|---|
| 1 | Lab provisioning (missions, envelopes, submit) | PARTIALLY RESOLVED | Blocker |
| 2 | Handoff delivery into the next order | PARTIALLY RESOLVED | Major |
| 3 | Rebuild from group documents (INSPECT, REWORK) | PARTIALLY RESOLVED | Blocker |
| 4 | Activation tool steps | PARTIALLY RESOLVED | Major |
| 5 | Trial binding and model keys | PARTIALLY RESOLVED | Blocker |
| 6 | Lab disposition contract | RESOLVED | – |
| 7 | Leakage rules | RESOLVED | – |

---

## Previous Blockers

### 1. Lab provisioning — PARTIALLY RESOLVED (Blocker)

**Fixed:**
- The register → link → submit order follows `ff/afo/overnight.py:21-47`.
- Order IDs are predictable (`queue.py:136-137`).
- The launch-manifest fields are right: `runtime.py:121-144` and `product_job.py:46-70` consume them.
- The envelope fields match the `work-order.schema.json` required list.

**Still open:**
- **Blocker: the mission limits will be refused, and the policy that bounds them is unspecified** (§3 lines 385–389; item 9 lines 997–1002).
  - `mission_admin.register` caps every limit by the effective policy (`ff/afo/mission_admin.py:43-58`):
    - `max_attempts` ≤ `budgets.max_order_attempts`;
    - `max_tokens` ≤ `budgets.max_model_tokens_per_order`;
    - `max_jobs` ≤ `budgets.max_recovery_model_calls_per_order`;
    - `max_corrections` ≤ 1;
    - `deadline` ≤ min(grant expiry, now + `max_order_wall_seconds`).
  - The design sets `max_attempts 5`. The repository policy has `max_order_attempts: 3` (`config/factory/afo-policy.yaml:35`), so registration raises `MISSION_LIMIT_EXCEEDS_CURRENT_AUTHORITY_OR_POLICY`.
  - The design names a "per-experiment operator policy" (selected through `FORGE_AFO_POLICY`, `ff/afo/policy.py:89`). It specifies only the mode and `allowed_model_profiles`, not its `budgets.*` values.
  - One mission's token cap must cover all five orders but is capped at one order's `max_model_tokens_per_order`.
- **Blocker: the mission deadline cannot be "capped per order".**
  - The deadline is fixed when the mission is first registered (the AUTHOR batch). Later provisioning reuses the stored limits (`overnight.py:37-38`), and `register` refuses any change (`mission_admin.py:64-65`).
  - INSPECT and REWORK orders that start after now + `max_order_wall_seconds` hit `MISSION_DEADLINE_EXHAUSTED` (`mission_ledger.py:177-178`). Preflight turns that into a BLOCK through `MISSION_ALLOWANCE_EXHAUSTED` (`scheduler.py:112-117, 215-225`).
  - The plan must state the policy wall value (≥ the experiment duration) or a `mission-extend-deadline` step.
- **Major: the mission document is incomplete.**
  - `register` requires exactly `mission_id, lineage, limits, authorization_ref, request, orders` (`mission_admin.py:20-22`).
  - `validate_limits` requires `max_attempts`, `max_jobs`, `max_requests`, `max_tokens`, `max_tools`, `max_corrections` and `deadline` (`mission_ledger.py:17-23`).
  - The plan gives no `lineage` (which must be unique, `mission_ledger.py:44`), no `request` dict for the `recover_workorder` check, and no values for `max_jobs`, `max_tools` or `max_corrections`.
- **Major: the grant scope uses the wrong identifier** (line 406).
  - Grant `scope.order_ids` is matched against the envelope `request_id`, not the queue order ID (`ff/afo/cli.py:43`, `local_agent.py:64`, `scheduler.py:200`, `mission_admin.py:101`).
  - The trial's `order_ids` are queue IDs (`product_role_trial.py:40`).
  - The plan must say which list goes into which document. Otherwise the owner signs grants that fail with `AUTH_OUT_OF_SCOPE`.
- **Major: the ID components are undefined** (line 381).
  - `driver` and `experiment_id` have no defined format.
  - The spec's `driver` field is free text with spaces and a colon (`examples/0014g…/workorder.json:3`). That would break the `request_id` pattern `^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$` (`work-order.schema.json:26`).

### 2. Handoff delivery into the next order — PARTIALLY RESOLVED (Major)

**Fixed:**
- The git-ignored `<repo>/process-lab/` folder satisfies `prepare`'s in-repo rule (`ff/workorder.py:210-213`) and `queue.submit`'s manifest check (`queue.py:286-290`).
- `factory_revision()` uses `--untracked-files=no` (`workorder.py:41`).
- The `lab-handoff--` prefix avoids basename collisions under `inputs/<basename>` (`:214`).
- `next` gets the source workspace through `runtime.workspace_of`.

**Still open:**
- **Major: input paths break when the example is copied, and no tool writes the AUTHOR folder** (§1 lines 292–297; item 9 lines 1003–1007).
  - `prepare` resolves each input relative to the example folder (`workorder.py:211`).
  - The 0014g/0020 paths are relative to `examples/<name>/` (`../0014-crc-st/inputs/…`, and bare `IDR-CONTRACT.md`).
  - Copying the spec to `process-lab/<exp>/<driver>/<seq>/` breaks all of them. The plan does not say that `next` rewrites the paths, or how.
  - No tool is assigned to write `process-lab/<exp>/<driver>/1/workorder.json`, the AUTHOR order whose spec must carry the `process_lab` block. `next` writes seq ≥ 2, and `provision` writes only `launch.json`.

### 3. Rebuild from group documents — PARTIALLY RESOLVED (Blocker)

**Fixed:**
- The group documents and the cross-cutting document are carried in the handoff (§6 lines 505–508, §8 line 570).
- The `results`/`cross` shape fits `swe1.assemble` (`swe1.py:491-506`).
- Task names are `requirements:<id>`, as on the author path (`swe1.py:742`).
- A groups-changed refusal exists.

**Still open:**
- **Blocker: INSPECT handoffs carry no group documents, and partial REWORK cannot use the localized repair path** (§6 lines 505–530; item 7 lines 984–987; item 15 line 1049).
  - `lab_handoff` copies group documents from `.forge-run/lrtx/SWE.1/packets/requirements__<group>.json`. Those checkpoints exist only after `run_task` (`visit.py:25-26, 228-229`).
  - `materialize` calls `assemble` directly and writes no checkpoint. An INSPECT workspace therefore has none, so its handoff (the REWORK input) has no group documents.
  - In REWORK, `run_task` with findings and no checkpoint gets `start = None` (`visit.py:159-174`). It then sends the *base* packet without the findings, so the "existing localized repair path" never sees them.
  - "Every other task keeps its materialized document" has no mechanism. `_visit` calls `run_task` for every group (`swe1.py:741-750`). Without a matching checkpoint that is a model call.
  - The plan must say that `materialize` writes VALID checkpoints (with which `base_hash`) or that lab-mode `_visit` injects the records. It must also say how the cross-cutting `base_hash` behaves when `functional` changes (`swe1.py:748-750`). Otherwise the cross-cutting task is re-authored without findings, which contradicts line 529.
- **Major: `materialize` cannot write under its own binding as specified.**
  - `assemble` writes through `swe1.write_scoped`, whose node is hard-coded to `"swe1_author"` (`swe1.py:590, 663-664`).
  - The INSPECT graph has no `swe1_author` node, so `Authorizer.decide` returns `UNBOUND_AGENT` (`ff/policy/authz.py:197-199`). Line 517 ("under the node's binding") needs a node parameter on `assemble`, or a stated binding entry.
  - The gate after `materialize` reads `.forge-run/lrtx/SWE.1/reply.json` (`builder.py:249, 291-292`). The plan does not say that `materialize` writes that reply.

### 4. Activation tool — PARTIALLY RESOLVED (Major)

**Fixed:** these now match `activate.py:5-133`:
- the stale `serving_instance` and `serving_holder` removal;
- the `settings.toml` regeneration;
- the environment switch and re-exec;
- the four `quiet()` conditions plus the order states;
- the unit-list file;
- 600 s health polling;
- the `STOPPED_SETTLEMENT_PENDING` outcome.

**Still open:**
- **Major: the health-failure path contradicts the code** (step 10, lines 479–481).
  - Managed `stack.stop` itself runs `synchronize('shutdown')`, which sets STOPPED at epoch E2+1 (`stack.py:700`).
  - The next action, "pause with expected epoch E2", then raises `OPERATIONS_INTENT_SUPERSEDED` (`operations.py:94-95`).
  - The plan must define the final intent (STOPPED at E2+1) and the order of pause and stop.
- **Major: no state survives the `os.execv`** (step 6, line 470; item 9 line 1008).
  - The record needs E0, E1, the per-step UTC times and the target. Step 7 needs E1 for its compare-and-set.
  - The source script passes `--epoch` (`activate.py:111`). The plan defines only `--installed`. Re-reading the epoch after the exec would defeat the compare-and-set.
- **Major: outcome precedence is still undefined.** An operator STOP between steps 3 and 7 fits both `STOPPED_BY_OPERATOR` (CUJ 2) and `ACTIVATE_EPOCH_CHANGED` (step 7). Also, "left PAUSED" cannot hold if someone else moved the intent.
- **Major: the deployment root is ambiguous** (§12 lines 720, 736; runbook item 20).
  - The lab profiles set `default_root: /mnt/data/forge-c/process-lab`. But `stack.settings` prefers `FORGE_LRTX_ROOT` (`stack.py:52`), which the deployed units pin (`services.py:109-115`).
  - If the root is meant to be new, `_start` requires `init` (`stack.py:480-481`) and `<root>/ollama-models` must hold the Ornith `hf.co` manifest and blob (`stack.py:381-389`). Neither step is in the runbook.
  - If the root is meant to be shared, `default_root` is dead text, and nobody says which `state/afo/conductor.env` step 1 loads.

### 5. Trial binding — PARTIALLY RESOLVED (Blocker)

**Fixed:**
- The reference form, the `qualification-product-014:<sha>` grant and `order_ids` are correct (`product_role_trial.py:17-26, 37-47, 93-99`).
- Model keys go in `allowed_model_profiles` (`scheduler.py:88`).

**Still open:**
- **Blocker: every Qwen order would be refused for lack of a context allocation** (lines 409–418).
  - The Qwen lab profile inherits `OLLAMA_CONTEXT_LENGTH: '262144'` (base profile line 34). The identity's `context_tokens` is therefore 262144 (`structured.py:98`).
  - Above 65536, `authorized()` requires `trial.context_allocation_ref` pointing to a `PASS_ALLOCATION_ONLY` record that matches digest, precision, slot count 1 and f16 KV (`product_role_trial.py:55-79`).
  - The trial field list has no such reference. As written, every Qwen order (all of arm B, and arm A's INSPECT) is refused with `PRODUCT_ROLE_TRIAL_CONTEXT_ALLOCATION_UNBOUND`.
- **Major: the trial field list is incomplete.**
  - It omits `schema` (`:24`), `authorization_ref` (`:93`), `adapter_revision` (must equal `source_revision`, `:87`) and a `task_class` value.
  - "`sampling` from the profile" is undefined for the author. Author packets carry no sampling (`structured.py:227, 443`), yet `key()` requires a non-empty dict (`role_capability.py:37-38`), and matching compares `body.get(k)` (`product_role_trial.py:126`).

### 6. Disposition contract — RESOLVED

The new `forge-c/process-lab-disposition/1` contract has an obligation, a handoff sha and a COVERED verdict. Alternative M rejects the learning-only contract. The verify routine to extract exists (`ff/offline/disposition.py:40-41, 79-88`), and its message format (canonical JSON without `signature_ref`) carries over.

### 7. Leakage — RESOLVED

- The role allowlist admits `reference_manual_*` and the renamed device-header role (lines 300–311, 755–765). `forge_crc_device.h` holds only the layout and the fixture instance.
- The holdout check now reads the effective workspace manifest after `workorder.py:838-840`.
- Lessons are off through `inspection_lessons: false` (`review_semantic.py:1036-1044`).

### Previous Majors

- **G3 `adapter_revision` / nine-field IDENTITY:** RESOLVED. CAPA-074 is done, and the `packet_identity` docstring confirms `adapter_revision` is excluded (`structured.py:60-99`).
- **Time boxes:** RESOLVED. The continuation nodes are kept, there is no `DONE` status, and outcomes are written incrementally.
- **Dead-letter of a successful order:** RESOLVED. Exact `terminal_reason` skip in `deadletter.sweep` (`:82-91`).
- **Ornith overrides vs admission:** RESOLVED. `reasoning_effort` is unchanged, and the budget travels in `FORGE_GATEWAY_REASONING` (`stack.py:37-39, 598`). The `--reasoning-format` emission rule is only partly resolved; see New Blocker N1.

---

## New Blocker

**N1. The lab profiles fail deterministically under the copy-plus-overrides rule** (§12 lines 705–736; item 16 lines 1052–1058; item 17; LAB-T02 lines 1101–1106).
- **Ornith context check.** The Ornith profile inherits `runtime.fabro_context_tokens: 262144` and `context_limit_tokens: 262144`, but sets `OLLAMA_CONTEXT_LENGTH: "32768"`. `stack.fabro_config` then raises `FABRO_CONTEXT_EXCEEDS_PROVIDER` (`stack.py:129-130`). Activation step 5 calls it (line 468), so `activate --to lab-ornith-q8`, the first native step, always fails.
- **Qwen VRAM value.** The Qwen lab profile has `process_lab: true` and inherits a runtime with no `vram_required_gb`. Item 16 and LAB-T02 refuse a lab profile without that key, so the Qwen lab profile can never start. Step 8 also needs the value, and the plan gives no number.
- **Ornith inherited flags.** The Ornith profile inherits `runtime.llama_server.reasoning_effort: medium`, `batch_tokens: 1024` and `microbatch_tokens: 512` (base lines 42–45).
  - The argv then gets `--reasoning-effort medium --reasoning-format deepseek` (`stack.py:408-409`), and the new rule adds a second `--reasoning-format`.
  - That differs from the speed-study argv in §11 (lines 669–670).
- **Fix.** List the removals (`reasoning_effort`, `fabro_context_tokens`/`context_limit_tokens`, or set them ≤ 32768) and give a Qwen `vram_required_gb`. Also define the emission rule when both the effort and the format key are set.

## New Majors

- **N2. INSPECT gate failure and FAILED-gate sources are undefined** (§2 table line 347, edge rules 350–358; `next` lines 1003–1007).
  - INSPECT has `swe1_author_gate` but no author node, so the gate's rejection edge has no target.
  - `next` accepts any `PROCESS_LAB_HANDOFF_SEALED` source, including handoffs with `gate_status: FAILED`. A handoff "with no baseline" (a FAILED author visit assembles nothing, `swe1.py:756-757`) has no group documents to materialize.
  - The plan must say whether `next` refuses such sources and where an INSPECT gate rejection goes.
- **N3. Inspector write isolation contradicts the node bindings** (line 347 vs LAB-T11 line 1153).
  - In INSPECT, `lab_inspect_record` and `lab_handoff` are bound to `swe1-inspector`, yet LAB-T11 asserts that "the inspector cannot write … handoff".
  - The plan does not say whether these command nodes write through `write_scoped`, or which role write globs allow `process-lab/**`.
- **N4. The scorer has no work-order input** (§9 lines 620–631).
  - Step 3 checks BUDGET and SIM rows "against the work order's budgets and simulation block".
  - The CLI has `--experiment --handoff --files --sections --oracle --dispositions --out`, and no argument or rule for locating the work order or workspace manifest.

## Test plan note

LAB-T08, LAB-T09, LAB-T12a, LAB-T12b and LAB-T18 assert behaviour that the gaps above leave undefined or contradictory: mission limits, the health-failure outcome, materialize checkpoints, partial-REWORK reuse and the profile rule. They cannot be written as specified until those points are decided.

## Key files

- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/mission_admin.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/mission_ledger.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/product_role_trial.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/cli.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/visit.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/swe1.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/lrtx/stack.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/services.py
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/config/factory/profiles/local-rtx-v2-omniverse2-q38-aspice-stepwise-medium.yaml
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py

No files were modified.

## Raw report — `egm-codebase-details`

# Codebase-details re-review: revision 3 of `forge-c-process-first-ornith-qwen.md`

**Verdict: not ready for implementation.** I could read the persona, the standard, the target (all 1,196 lines), the targeted re-review, SOURCE-INVENTORY and every cited source file, so this is a complete review.

Most line citations in revision 3 are now accurate. The fixes for Blockers 2, 3, 6 and 7 rest on correct code facts. The fixes for Blockers 1, 4 and 5 rest on correct citations, but each has a gap where the described behaviour contradicts what the code does. One new Blocker is in the §12 profile rule: the Ornith profile cannot render a Fabro config, so the first activation fails. I found 2 Blockers, 12 Majors and 11 Nits.

## Verdict on the 7 targeted Blockers

| # | Blocker | Code facts behind the rev 3 fix | Remaining problem |
|---|---|---|---|
| 1 | Provisioning and mission link | **Partly correct.** These are accurate: `overnight.provision_order` (`overnight.py:21-47`), `mission_admin.register` (grant action `recover_workorder`, `mission_admin.py:30`), `MissionLedger.link` (`mission_ledger.py:53`), `order_id_for` (`queue.py:136`), and `submit` with its location check (`queue.py:286-288`). | The mission limits contradict `mission_admin.register` (B-1, M-1). |
| 2 | Handoff cannot enter the next order | **Correct.** The repository rule (`workorder.py:210-216`) and the manifest check are as stated. `.gitignore` has no `/process-lab/` yet, so "Modify" is right. `factory_revision()` uses `--untracked-files=no` (`workorder.py:41`), so even untracked files keep it clean; ignored files never appear in the other porcelain checks either (`qualification_inputs.py:161`, `evidence_run.py:56`, `afo/inventory.py:61`, `activate.py:84,91`). | Copying a work order moves its relative input paths (M-6). |
| 3 | Rebuild needs group documents | **Correct.** The checkpoint path is `.forge-run/lrtx/SWE.1/packets/requirements__<g>.json` (`visit.py:26`). The `swr` map is in `assembly.json` (`swe1.py:592`). Task names are `requirements:<id>` (`:742`) and `requirements:crosscutting` (`:749`). `assemble` reads `rec["task"]` and `rec["doc"]` (`:499-506`). | Nit N-5. |
| 4 | Activation omits steps | **Partly correct.** Steps 2 and 4–7, 9 and 11 match `activate.py:21-26, 46-111, 115-132`. | The tool omits the policy and grant install, its failure path contradicts `stack.stop`, and the unit rewrite is described wrongly (M-2, M-3, M-4, M-5, B-2). |
| 5 | Trial binding | **Mostly correct.** The reference form (`product_role_trial.py:21`), the `qualification-product-014:` grant (`:93-99`) and model keys in `allowed_model_profiles` (`scheduler.py:88`) are accurate. | Trial fields and ID kinds are missing or conflated (M-7, M-8). |
| 6 | Disposition contract | **Correct.** A new schema plus extraction of the signature check is feasible (`disposition.py:27,40-41,84-88`). | Line range is imprecise (N-6). |
| 7 | Leakage rules | **Correct.** The allowlist keeps `reference_manual_*`. The 0014g entry numbering 1–15 matches `examples/0014g-st-crc-idr-qwen-delivery/workorder.json:33-93`. The holdout handling (`runtime.py:140`, `workorder.py:838-840`) and the lessons flag (`review_semantic.py:1036-1044`) are as stated. | Nit N-7. |

## Blockers

**B-1. The mission limits for one mission per (experiment, driver) are refused, or exhausted, by the code.** (§3 step 2, lines 385–389)

The design reuses `mission_admin.register` for a mission that spans up to five orders, but that function enforces per-order policy caps on the whole mission (`mission_admin.py:43-58`):

- **Caps.** It requires `max_attempts ≤ budgets.max_order_attempts`. The design sets `max_attempts: 5`, but the only documented policy value is 3 (`config/factory/afo-policy.yaml:35`, and the design's own Alternative A, line 801). The result is `MISSION_LIMIT_EXCEEDS_CURRENT_AUTHORITY_OR_POLICY`. Nowhere does the design say the per-experiment policy raises this to at least 5.
- **Shared token cap.** `max_tokens` is capped by `max_model_tokens_per_order` (120,000 in the repository policy). That one per-order cap is then shared by all five orders: `scheduler.py:112-117` blocks on `charged_tokens >= max_tokens`.
- **Missing limit keys.** `validate_limits` requires all six keys: `max_attempts`, `max_jobs`, `max_requests`, `max_tokens`, `max_tools` and `max_corrections`, where `max_corrections` may be at most 1 (`mission_ledger.py:19`, `mission_admin.py:51`). The design gives only attempts, tokens, requests and the deadline. Any absent key is refused (`limits.get(k, cap + 1) > cap`). The document also needs `lineage` and `request` (`mission_admin.py:20`), which the design does not mention.
- **Deadline.** "Capped by `max_order_wall_seconds` per order" (line 389) is wrong. The cap is applied once, when the first AUTHOR order registers the mission. The record cannot change afterwards: `overnight.py:36-38` reuses the stored limits, and a change raises `MISSION_ALLOWANCE_RESET_FORBIDDEN` (`mission_admin.py:64-65`). As a result, every later INSPECT or REWORK order inherits the first order's deadline (registration time + 86,400 − 5 s). Once that passes, the order is blocked as `MISSION_ALLOWANCE_EXHAUSTED` (`scheduler.py:113`) or `ORDER_WALL_BUDGET_EXHAUSTED` (`dispatch.py:370-375`). `product_job.py:42-43` uses the same minimum.

**B-2. Under the copy-plus-overrides rule, `stack.fabro_config` raises for the Ornith profile, so activation fails at step 5.** (§12, lines 726–736; §4 step 5, line 468)

- **Inherited context.** The base profile sets `runtime.fabro_context_tokens: 262144` and `context_limit_tokens: 262144` (`local-rtx-v2-omniverse2-q38-aspice-stepwise-medium.yaml:26-27`). The Ornith overrides change only `OLLAMA_CONTEXT_LENGTH` to `"32768"`, and line 705 says every unlisted key stays as in the base.
- **What the code does.** `fabro_config` raises `FABRO_CONTEXT_EXCEEDS_PROVIDER` when `fabro_context_tokens` is present and larger than `OLLAMA_CONTEXT_LENGTH` (`stack.py:129-130`).
- **When it happens.** It fails inside the fenced install, after the units, provider and Fabro are already stopped. The design defines no outcome code for this case.

## Majors

**M-1. Grant `order_ids` and trial `order_ids` are different kinds of value, and the design treats them as one.** (lines 383–384, 406, 413)

- AFO grants match `request["order_id"] = env["request_id"]` (`cli.py:43`, `scheduler.py:200`, `local_agent.py:64`, `authz.py:95`).
- The trial matches the queue ID `afo-…` (`product_role_trial.py:40`, through `job["order_id"]` at `product_job.py:24`).
- The design must say that grants list `pl-…` request IDs and trials list `afo-…` order IDs.

**M-2. The activation tool never installs the per-experiment policy or the grants.**

- `activate.py:96-99` copies the grants into `authz.AUTH_DIR` and replaces the file at `FORGE_AFO_POLICY`. Line 106 then asserts the policy hash and PILOT mode.
- §4 omits all of this. No other step in the design or the runbook (item 20) says how the signed per-experiment policy (CUJ 1, line 191; line 423) becomes effective.

**M-3. The step 10 failure path contradicts `stack.stop`.** (lines 479–481)

- With managed serving on, `stack.stop` itself calls `synchronize(..., "shutdown")` without an expected epoch (`stack.py:700`). That raises the epoch to E3 with mode STOPPED.
- The next step, "pause with expected epoch E2", then fails with `OPERATIONS_INTENT_SUPERSEDED` (`operations.py:94-95`).
- The intent ends STOPPED, not PAUSED.

**M-4. "Replace the `FORGE_LRTX_PROFILE` value … in the listed units" (line 465) misdescribes the units.**

- The rendered units carry the profile as `Environment=FORGE_OPERATIONS_PROFILE=` and as `lrtx.stack exec --profile <id>` in `ExecStart` (`services.py:105-122`). They do not carry `FORGE_LRTX_PROFILE` (grep finds no match in `afo/services.py`).
- `activate.py:101,104` replaces every occurrence of the previous profile ID. Taken literally, the design's step leaves the Conductor on the old profile.

**M-5. `deployment.default_root: /mnt/data/forge-c/process-lab` has no effect under the listed units.** (line 720)

- `stack.settings` prefers `FORGE_LRTX_ROOT` over `default_root` (`stack.py:52`).
- The rendered units set `FORGE_LRTX_ROOT` explicitly (`services.py:109-115`).
- `activate.py` runs in `/mnt/data/forge-c/production-local-014`. No profile has that `default_root`, so it must come from `conductor.env` (`activate.py:4-7`).
- The lab would therefore run in the existing production root, sharing its queue and mission history. §4 never changes `FORGE_LRTX_ROOT`, and the design does not state which root it intends.

**M-6. Copying the work order breaks its input paths.** (lines 292–294, 743)

- `prepare` resolves `example / item["path"]` (`workorder.py:211`).
- The 0014g inputs are relative to the example folder: `../0014-crc-st/…`, `../0002-…`, `../0015-…`, and the example-local files `IDR-CONTRACT.md`, `forge_crc_device.h` and `IDR-API.h` (0014g `workorder.json:35-92`).
- A copy under `examples/0020-process-lab-crc/` or `process-lab/<exp>/<driver>/<seq>/` resolves those paths to files that do not exist. The design gives no rule for rewriting them or copying the files.

**M-7. The trial document is missing fields the code reads.** (lines 410–418)

- `authorized()` reads `trial["authorization_ref"]` to locate the owner grant (`product_role_trial.py:93`). That grant is checked for action `recover_workorder` with `request_for(order)` (`:94`). Neither is listed.
- Every identity's `adapter_revision` must equal `source_revision` and the job's commit (`:87`, `role_capability.py:157-159`).
- If any identity has `context_tokens > 65536`, the trial needs `context_allocation_ref` and a `profile_sha256` match (`product_role_trial.py:55-79`). This applies to the Qwen lab profile (M-8).

**M-8. The Qwen lab profile inherits a runtime the design elsewhere forbids or requires otherwise.** (lines 708–725)

The base runtime brings in:

- **Unmeasured context.** `OLLAMA_CONTEXT_LENGTH: '262144'` (base, line 34). Alternative H calls 262K unmeasured.
- **Trial context ceiling.** The packet identity takes `context_tokens` from that value (`structured.py:56,98`), so the trial identity exceeds the 65,536 ceiling.
- **Missing VRAM key.** There is no `vram_required_gb`, yet item 16 and LAB-T02 refuse a lab profile without it (lines 1055, 1106). The design's own rule would therefore refuse the Qwen lab profile.

**M-9. The Ornith profile inherits `runtime.llama_server.reasoning_effort: medium`.** (lines 732–733)

- The base sets it at line 42, and only `mtp_draft` is listed for removal.
- `llama_server_spec` then emits `--reasoning-effort medium --reasoning-format deepseek` (`stack.py:408-409`), plus the new `--reasoning-format` from the key.
- The flag would appear twice, and Ornith would get an effort that was never decided.

**M-10. "`max_visits` … come from the profile's structured settings" (lines 357–358) contradicts the code.**

- `local_profile_structured` supplies only `timeout_s` and `visit_time_s` (`workorder.py:663-664`).
- `max_visits` is the builder constant `MAX_VISITS` (`builder.py:28,239`), and `8 * MAX_VISITS` for continuation nodes (`:268,271`).

**M-11. The node role bindings cannot write the handoff.** (§2 table, lines 346–347; LAB-T11, line 1153)

- `swe1-inspector` is `readonly: true` (`config/factory/agents.yaml:60`). `write_scoped` refuses it with `READONLY_ROLE_WRITE_DENIED` (`policy/authz.py:240-241`).
- `swe1-author` may write only `workproducts/SWE.1/`, `safety/…` and `traceability/` (`authz.py:42`), not `process-lab/SWE.1/`.
- INSPECT's `lab_inspect_record` and `lab_handoff` are bound to the inspector and must write `findings.json` and `handoff.json`. LAB-T11 asserts that the inspector cannot write the handoff.
- The design must name the write path for these nodes (not `write_scoped`) or rebind them.

**M-12. The activation record path is on the wrong host.** (line 483)

- `activate` runs on Omniverse2, but the record goes to `$B/operations/process-lab/…`, which is the loop10 root (line 65).
- §9 itself copies the experiment record to `$R`.

## Nits

- **N-1** (lines 399–404): The envelope list omits the required `schema_version: "1.0"` (`work-order.schema.json:7,22`). Without it, `submit` raises `INTAKE_SCHEMA`.
- **N-2** (line 555): `_parse_json` already strips code fences silently with no note (`structured.py:402-406`). Only text around braces gets `WRAPPED_JSON`. "Instead of accepting `WRAPPED_JSON`" describes only half the current behaviour.
- **N-3** (lines 933–934): Besides `dot`, the closures capture `structured`, `run`, `t` and `box` (`builder.py:253-263`). `dot` is already a parameter and `nodes` is unused, so "plus explicit `nodes`/`dot`" is inaccurate.
- **N-4** (lines 541–542): With `inspector_stepwise` on, `entries` is forced off and the coverage branch is skipped (`review_semantic.py:285-287,1172,1186`). The `coverage-*`, `effects` and `budgets` questions therefore never run in the lab.
- **N-5** (lines 514–516): The rebuilt `assembly.json` `open_points` origins differ, because `packet_input_hash` and `record_sha256` are taken from the record dict (`swe1.py:517-518`). The rendered artifacts are identical.
- **N-6** (lines 617, 1087): The `ssh-keygen` call is at `disposition.py:84-88`. Lines 79–101 are the whole `verify` function, including the bundle and subject checks.
- **N-7** (line 768): Five ST files are git-ignored, not four. The guideline `examples/0002-arm_55_rcc_st/hal_driver_guideline.md` is ignored too (`.gitignore:22`).
- **N-8** (line 324 vs line 976): `require_effective(ws)` vs `require_effective(ws, spec)`.
- **N-9** (lines 455–456): The quiet-queue state list omits `PAUSED` and `SUBMITTED` (`queue.py:306,321`).
- **N-10** (line 1022): The call at `workorder.py:732` is a conditional expression; `aspice.validate_profile` takes no `process_lab` keyword argument.
- **N-11** (line 444): Deliberate differences from `activate.py` are not stated:
  - it has no `--epoch` operator argument;
  - it drops the `history()==before` invariants;
  - it drops the HEAD equals `source_revision` check;
  - it defers the Conductor start, which the source script starts in `finally`.

## Checked and correct

- **Workorder and launcher:** `workorder.py:293, 406, 732, 763, 838-840, 658-665`; `runtime.py:122, 140, 141`; `workspace_of` (`runtime.py:151`).
- **Scheduler and dispatch:** `scheduler.py:39, 88, 213-240` (BLOCK list); `dispatch.py:313-350, 452-476`.
- **Dead-letter:** `deadletter.sweep` (`deadletter.py:82-91`) is the only producer of cases.
- **Stack and gateway:** `stack.py:120, 428, 591-605` (`FORGE_GATEWAY_REASONING`); `llm_gateway.py:90, 142-148`.
- **Admission and trial:** `role_capability.py:11-21, 164`; `product_role_trial.py:125, 196`; `durable_agent.py:327, 348` (same policy object).
- **SWE.1 and inspector:** `review_semantic.py:285-287, 1036-1044` and the reply statuses PASS, REWORK, FAILED and CONTINUE; `visit.run_task` with 2 repairs plus 2 extensions; `swe1.py:430, 447, 508, 742`.
- **Other citations:** `qm.py:100-104`; `services.py:100-110`; `request_admission.py:49`; `swtrace.py:103`; the base profile file exists; port +100 values do not collide with other profiles; `activate.py:5-133`.
- **Existing artefacts:** CAPA-074, RPR-073 (`tests/reliability/reproducers/rpr073_packet_identity_alias.py`), `test_lrtx_packet_identity.py` and `$B/operations/feature014/run_full_inherited.py` all exist.

No files were modified.
