# Stage 5 — Initial Zoom Out (EGM Goldfish)

- Reviewer: `egm:egm-zoom-out` (fresh native subagent, `omitClaudeMd`, Read/Grep/Glob only), plugin egm 0.1.0 @403d888
- Target: `docs/designs/forge-c-process-first-ornith-qwen.md` (full file, 832 lines), 2026-10-31
- GoldfishContext: constitution.md, Feature 014 spec.md, PROCESS-FIRST plan, SOURCE-INVENTORY.md
- Status: completed

**Elephant verification of blockers (not a reviewer statement):** B1 confirmed — `config/factory/afo-policy.yaml:27`
`max_concurrent_workorders: 1`, `afo/queue.py:513` CAPACITY refusal, `afo/dispatch.py:84-87` STALE_OPERATIONS_COMMAND
quarantine on epoch change. B2 confirmed — `workorder.py:496-500` carries only PASS phases; `inspection/engine.py:369-370`
REINSPECT for an uninspected baseline.

---

# Zoom Out review: forge-c-process-first-ornith-qwen.md (Stage 5, initial)

**Verdict: Needs revision.** There are 2 Blockers, 11 Majors and 6 Nits.

I read the target in full, the persona, the zoom-out standard, the constitution, spec.md, the plan, SOURCE-INVENTORY.md and the README. I also checked the design's claims against the code at `factory/python/forge_factory/`.

The design passes the context check. The objective, the motivation and how it fits the plan are all clear. It is aimed at the real root problem: SWE.1 quality cannot be measured or used on its own. The main problems are elsewhere. The design keeps saying "the existing queue does this" or "the existing resume does this", but the code does not support those claims. Several new parts also copy mechanisms that already exist.

---

## Blockers

### B1. Role batching does not work with D1 (one order holding up to five attempts)
- **Severity:** Blocker
- **Affected scope:** §3 "Scheduler rule" (lines 222-226); diagram (lines 159-162); §2 (lines 203-210); target files 17, 18 and 20 (lines 639-673); D2's reasoning in Alternative D (line 398).
- **Simplicity rationale:** Three facts in the code break the claim that batching "falls out of the existing queue with no new scheduler":
  1. **Only one order runs at a time.** `scheduler.preflight` only sees QUEUED orders. `queue.admit` refuses when the number of active orders reaches `queue.max_concurrent_workorders`, which defaults to 1 (`afo/scheduler.py:251`, `afo/queue.py:33,510-514`). A lab order stays RUNNING across all of its attempts, so driver 2's AUTHOR cannot start until driver 1 is finished. The result is a model swap after almost every attempt: up to 4 per driver, not the "2-3 per corpus" that D2 relies on.
  2. **Planned attempts never pass the new check.** Attempt seq+1 is written straight to the FABRO_LAUNCH outbox, the way `checkpoints.new_attempt` already does it. `dispatch_pending` launches it without calling `scheduler.preflight`. So the new `RESIDENT_PROFILE_MISMATCH` check in `preflight` never sees the attempts it is meant to hold back.
  3. **The swap kills the waiting attempt.** `dispatch_pending` quarantines any launch whose `operations_epoch` differs from the current intent epoch (`afo/dispatch.py:84-87`, `STALE_OPERATIONS_COMMAND`). The swap ends with "set intent RUNNING (epoch+1)" (line 239). The INSPECT attempt is created right after AUTHOR succeeds, before the swap, so it carries the old epoch and is quarantined after the swap.
- **Recommendation:** Put D1 back to the owner with this evidence. The simpler shape is one single-role order per (driver, role), close to Alternative B. The INSPECT or REWORK order would take the earlier order's sealed `process-handoff/1` by hash as its declared input, so the handoff itself is the cross-order link. Each order then goes through normal scheduler preflight and admission under the new epoch. That would remove `attempt_plan`, `planned_attempt`, the dispatch changes and the new carry rule in B2.

### B2. "Existing validated brownfield resume" cannot carry an uninspected SWE.1 between attempts
- **Severity:** Blocker
- **Affected scope:** §2 (lines 207-208); target file 17 (lines 639-645); §5 ID ledger hand-over (line 262).
- **Simplicity rationale:**
  - The brownfield path is only used for `delivery` manifests (`workorder.py:468`).
  - The greenfield `resume_from` only copies the leading phases whose `gate()` is PASS (`workorder.py:496-500`). After the AUTHOR attempt, SWE.1 has a baseline but no inspection, so `gate()` returns REINSPECT (`inspection/engine.py:369-370`). Nothing is copied over.
  - After a failed INSPECT, `gate()` returns REWORK, so again nothing is copied.
  - `.forge-run/lab/` (seals, ledger, inspection records) is not in `RESUME_EXTRA` either.

  So every attempt after the first would start with an empty SWE.1. Making D1 work needs a new lab carry-over rule, and the design does not mention one. That adds hidden scope and goes against the resume rule that only phases that passed are carried. Taking the B1 recommendation (handoff as the declared input) removes this problem.

---

## Majors

### M1. `lab_seal` copies the existing SWE.1 baseline freeze
- **Affected scope:** §1 (lines 191-194); target file 10 (lines 568-578); AT11 claim (lines 188-189).
- **Simplicity rationale:** `InspectionEngine.freeze` already hashes the SWE.1 files and writes an immutable record (`configuration/baselines/SWE.1/BL-SWE.1-nnn.json`), opened with mode `"x"`, numbered in sequence and recording `author_role` (`inspection/engine.py:120-157`). The stepwise inspector already reads "the frozen baseline" and refuses `BASELINE_CHANGED_DURING_INSPECTION`.
  - A parallel `seal-<seq>.json` chain means two hash records for the same bytes.
  - It also makes the claim "inspection is valid only for the exact seal it read" weaker, because the inspector actually reads the BL record, not the seal.
- **Recommendation:** Record the attempt's model, profile and runtime identity against the existing `baseline_id` in the attempt or handoff record. Keep the `handoff()` step only.

### M2. `planned_attempt` copies `checkpoints.new_attempt`, and dispatch already has a recovery hook
- **Affected scope:** target files 17 and 18 (lines 639-656).
- **Simplicity rationale:** `new_attempt` already opens seq+1, resumes from `source_wo`, is idempotent on a plan id and enqueues FABRO_LAUNCH (`afo/checkpoints.py:60-89`). `reconcile_running` already takes a `recover(order, attempt)` callback for exactly this kind of decision (`afo/dispatch.py:313-350`).
- **Recommendation:** If D1 survives B1, pass a lab-aware `recover` callback and widen `new_attempt` to accept it. Do not write a second insertion function and a lab branch inside `reconcile_running`.

### M3. The builder gets two overlapping mechanisms (`stop_after` and delegation)
- **Affected scope:** §1 (lines 171-175); target files 9 and 16 (lines 563-564, 629-637).
- **Simplicity rationale:**
  - The plan has the builder delegate to `process_lab.workflow`, which in turn calls the builder with `stop_after`. That is a circular call.
  - It also breaks the documented `_build` rule that "all six phases are always in the graph" (`workflow/builder.py:348-349`).
  - The existing mode pattern is to post-process the built graph: `delivery_first.workflow(dot, nodes, …)` and `development_demonstration.workflow`.
- **Recommendation:** Each lab role graph is only three nodes (author→gate→seal or inspector→record→seal). Let `process_lab` emit that small DOT using the builder's existing node helpers (`gate_cmd`, `structured_authors`), and leave `_build` alone. G7 is then met by construction, and the golden byte-identical test and the `stop_after` option can go.

### M4. Arm B gets an extra profile and a made-up swap
- **Affected scope:** §3 (lines 216-218, 244-246); target file 25 (lines 713-721).
- **Simplicity rationale:** The profile schema already supports per-role reasoning and per-model inspector sampling (SOURCE-INVENTORY §B). A single `lab-qwen38-q8` profile can hold both the author settings and the inspector settings.
  - Splitting it into two profiles forces a restart of the same model file.
  - Arm B is then charged a cost its real configuration does not have, which skews AT13 against Qwen.
- **Recommendation:** Use one Qwen lab profile. B's swap cost is then genuinely zero, and that zero is measured, not assumed.

### M5. The swap state machine skips the systemd-pinned operations profile and existing switch procedures
- **Affected scope:** §3 state machine (lines 228-241); target files 14 and 27 (lines 611-619, 731-740).
- **Simplicity rationale:**
  - **Profile is pinned in the unit.** Under managed serving, the profile is written into the systemd unit as `Environment=FORGE_OPERATIONS_PROFILE=…` (`afo/services.py:100-110`). `_managed_scope` refuses any other profile, and `recover_profile` and the watchdog bring back that configured profile (`afo/operations.py:269-342`). A bare `stack start --profile P_to` is therefore not "only existing commands". The existing activation scripts switch profiles by stopping the units, re-rendering them with the new `FORGE_OPERATIONS_PROFILE`, running `daemon-reload` and restarting (for example `evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py:105-123`). The runbook should reuse that procedure.
  - **STOPPED is ambiguous.** The swap passes through STOPPED (line 234), but the next rule says "STOP or revoke at any state → no further transition" (line 240). There is no marker that tells a planned swap stop apart from an operator abort.
  - **`probe` mixes two things.** "One admitted identity probe through the gateway" (line 618) is a model inference with no job or mission behind it, so it is not covered by `request_admission`. The digest check it names, `profile.model_identity`, needs no inference.
- **Recommendation:** Use `model_identity`, or run the probe as a normal admitted job. Look at `lrtx/drill.py` (an existing recorded stop/restart/rollback drill) as a model for the `model-swap/1` records.

### M6. Admitting the unqualified Ornith role ignores `product_role_trial`
- **Affected scope:** target file 19 (lines 661-663, "existing allowed-model checks stay unchanged"); runbook (lines 746, 755-756, "signed per-experiment AFO policy").
- **Simplicity rationale:** `role_capability.admit_job` refuses any role that has no measured capability receipt (`lrtx/role_capability.py:147-156`). The existing way to measure unqualified roles "on exactly the frozen orders/configurations, without claiming competence" is `afo/product_role_trial.py`, which is already wired into `product_job.prepare`. Without it, every Ornith job fails with `CAPABILITY_LIMIT`.
- **Recommendation:** Name `product_role_trial` as the authorization mechanism rather than an unspecified operator policy.

### M7. G6 (A/B readiness) has no component, while an existing preregistered comparison is ignored
- **Affected scope:** G6 (lines 66-68); "The A/B report sums these" (line 244); file list (lines 482-810).
- **Simplicity rationale:** No file in the plan produces an A/B report. It is PF-BENCH-011, which is P1. Meanwhile `afo/configuration_comparison.py` (DA-T028) and `qualification.COMPARISON_FACTORS` already provide a preregistered, hash-controlled comparison. It has a `model_build` factor and fixed controls (prompts, oracles, workload, admission, measurement, quality gates).
- **Recommendation:** Either drop G6 from this design, or say that the A/B reporter will extend `configuration_comparison`.

### M8. `decide.py` and `process-decision/1` are built before any corpus exists
- **Affected scope:** §9 "Corpus decision" (lines 317-326); target files 5a and 13a (lines 527-533, 604-609); increment 7.
- **Simplicity rationale:** The decision needs at least 5 drivers with frozen, independently reviewed oracles, one of them unseen. The design itself says the unseen case does not exist (Q3) and the oracle reviewer is not chosen (Q4). The plan says to start with "the smallest code path to one real SWE.1 package". The decision is PF-QUAL-013, which is P1. This is speculative now.
- **Recommendation:** Defer it, together with its preregistration format. If it is built later, take the preregistration shape from M7's existing comparison plan.

### M9. Target-neutral `primary_manual` is speculative now, and its scope is understated
- **Affected scope:** Problem 2 (lines 32-33); §6 (lines 265-269); target files 21 and 23 (lines 681-682, 698-699); file 3 `target_profile` (line 507).
- **Simplicity rationale:** It is only "needed for the different-MCU holdout", and Q3 has not chosen that holdout. It might be a non-peripheral component instead.
  - The literal count is far off. I found RM0486/STM32N6 97 times across 33 files. In `lrtx/swe1.py` alone it appears at 228, 240, 272, 343, 351, 358, 416, 501-506 and 738, not just "228, 501, 738". It also appears in `swe1_semantic.py`, `inspection/regmap.py`, `gate.py`, `prompts.py` (23 times) and the docs MCP server, all of which are on the SWE.1 path.
  - Swapping three literals is a band-aid.
  - A peripheral profile (`peripheral.py`) already exists and carries the reference-manual `key_sections`. That is the right place for the manual identity, not a new process-lab block field.
- **Recommendation:** Defer this until Q3 is decided.

### M10. `runtime.llama_server.context` creates a second source of truth for context length
- **Affected scope:** target file 2 (lines 497-498); target file 24 (line 709).
- **Simplicity rationale:** `OLLAMA_CONTEXT_LENGTH` is read by `structured.profile_context_tokens` (packet fit accounting), `profile.py:60`, `product_role_trial.py:65`, `qualification_inputs.py:152` and `stack.py:129`. If only `llama_server_spec` reads the new key, the server's context can quietly differ from the context the packets are sized against. That undermines "never silently truncate".
- **Recommendation:** Set `OLLAMA_CONTEXT_LENGTH` in the lab profile and drop the new key.

### M11. The existing SWE.1 per-model author harness is not considered
- **Affected scope:** Alternatives Considered (lines 365-446).
- **Simplicity rationale:** `lrtx/modelcmp.py` (LRTX-T023) already does most of what the lab wants:
  - It runs the real structured SWE.1 visit for several models on a copy of a frozen start workspace.
  - It freezes the result through the unchanged author gate.
  - It measures validity, calls, tokens and model load time ("loading a different model is the switching cost").

  It may be rejected for the same governance reason as Alternative I (bypassing Fabro and AFO). Still, it should be listed, and its fresh-copy and measurement code reused where it fits.

### M12. `criteria_result` inside the handoff schema creates a sealed copy and a scored copy
- **Affected scope:** §8 (lines 291-292); §9 (line 314); target files 4, 7 and 12 (lines 515-517, 546, 594).
- **Simplicity rationale:** The same schema now describes two documents that differ in one field. The "invalid example" (`MEETS` in a sealed package, line 546) cannot be checked by the schema without yet another marker. The score report already holds the result, and `import_swe2` takes `--score` separately.
- **Recommendation:** Keep the handoff immutable and leave `criteria_result` only in the score report.

---

## Nits

- **N1. G3 should reuse the canonical identity tuple** (§4, lines 252-254; file 1, lines 487-489). `role_capability.IDENTITY` already defines role, model_digest, precision, reasoning, schema_mode, adapter_revision, context_tokens and sampling. Hash on `key(identity)` plus the profile sha rather than a hand-picked field list. Otherwise a change of context or adapter revision would not invalidate the cache, which is an AT03 gap.
- **N2. The lab-only `ears.py` narrowing is not needed** (lines 262-263, 697). Ledger-assigned `SWR-\d{3}` IDs already pass the looser pattern, and the handoff schema enforces `^SWR-[0-9]{3}$`. A per-mode regex branch adds nothing.
- **N3. The ledger key reinvents an existing key** (§5, lines 258-260; file 11, lines 584-587). Each requirement already has a schema-validated `key` within its `task`, and `assemble` already returns `{swr: {task, key}}` (`lrtx/swe1.py:44-45, 592`). Use `(task, key)` as the ledger key. The source-ref/register/op composite and `SWR_ID_SPACE_EXHAUSTED` are detail that belongs in the implementation.
- **N4. `model_blob_sha256` is redundant** (file 2, lines 496-497; file 24, line 706). The pinned manifest sha already fixes the layer digest, and Ollama blobs are named by their content sha. The optional field repeats an existing check.
- **N5. D4 contradicts the AT11 it cites** (lines 104-105, 186-189). AT11 and plan §5.2 say "exactly one bounded correction". The design cites AT11 while allowing two. State plainly that owner decision D4 replaces that wording.
- **N6. Altitude and housekeeping.** The Detailed Implementation Plan pins line numbers ("near line 293/406", "lines 313-356"), keyword signatures and reason codes. That is acceptable for this section but will go stale quickly. Open Questions start at Q3 with no note that Q1 and Q2 were resolved into D1-D5. `verdict()` returning `BLOCKED/PROCESS_LAB_SEALED` for a successful lab run (line 565) will confuse readers; a distinct terminal reason would be clearer.

---

## What is sound

- The no-new-scheduler / no-router / no-EGM-runtime stance.
- G3 as a small, targeted fix.
- Keeping the oracle outside the workspace, plus the AT16 test.
- The per-requirement `NOT_INSPECTED` outcome.
- The minimal SWE.2 importer as an interface proof.
- Keeping the CRC smoke.
- Rejecting Alternatives C, E and F.

Fixing B1 and B2 by moving to single-role orders linked by the handoff would remove the attempt plan, `planned_attempt`, the dispatch and scheduler changes and the resume problem together, and the result would be simpler than the current design.
