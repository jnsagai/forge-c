# Stage 8 — Intermediate Zoom Out (EGM Goldfish)

- Reviewer: `egm:egm-zoom-out` (fresh native subagent), egm 0.1.0 @403d888; full file; inputs: Stage 5–7 reports
- Status: completed. The design was not edited between Stage 5 and Stage 8.

**Elephant verification (not a reviewer statement):** Z8-B1's swap procedure exists at
`evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py:92-133`
(`operations.synchronize('resume', expected_epoch)` → `stack.start(recovery=True)` → Conductor unit started after).
It is a one-off evidence script, not a tested factory command, so reusing it means promoting it into a runbook tool
with tests.

---

I read the persona, the standard, the full target (lines 1-832), all three earlier stage reports, and the four GoldfishContext files: the constitution, spec.md, the plan and SOURCE-INVENTORY. Nothing was missing, so the review is complete.

# Zoom Out review, Stage 8 (intermediate): forge-c-process-first-ornith-qwen.md

**Verdict: Needs revision. 1 Blocker, 4 Majors, 2 Nits.**

The context check passes, and the design targets the right problem: SWE.1 quality cannot be measured or consumed on its own (Problems 1-3).

The three earlier stages raised about 80 findings, but most of them trace back to one decision. That decision is D1 (one order holding up to five attempts) combined with a custom swap state machine. Stage 5 B1/B2, Stage 6 #1-#5, #8 and #13, and Stage 7 B1, B2, B3, M1, M2, M10 and M11 all fail on the same point: the design treats a model swap as something the factory does while running. Under D2 it is really a redeploy done by the operator. If that one shape is fixed, about 20 of those findings disappear. If they are patched one by one, the design grows more new code than it already has.

The second pattern: the corpus-decision layer (Stage 5 M7/M8) attracted five more defects in Stages 6-7. That is evidence it cannot be specified correctly yet, which makes it a YAGNI cut, not a set of fixes.

---

## Blocker

### Z8-B1. Change the shape: one order per (driver, role), batched per stack session, with the swap done by the existing operator profile activation
- **Affected scope:** D1/D2 (lines 98-100); §2 (196-210); §3 (212-248); diagram (152-167); Alternative B (375-382); Alternative D (392-400); files 6, 10, 14, 17-20 and 27 (535-540, 568-578, 611-673, 731-740).
- **Simplicity rationale:**
  - **The swap procedure already exists.** `evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py:92-133` changes the factory's profile in these steps:
    1. stop the services;
    2. rewrite `conductor.env` and the systemd units with the new profile, then `daemon-reload`;
    3. `operations.synchronize('resume', expected_epoch=...)`;
    4. `stack.start(settings, recovery=True)` while the Conductor unit is still down;
    5. a health loop that re-checks intent mode and epoch at each step (114, 122, 125, 131);
    6. start the Conductor and record `load_and_control_start_seconds`.
  - **That procedure already answers Stage 7 B3.**
    - RUNNING is set before the model starts, but nothing can be dispatched because the Conductor is not running.
    - The intent write is a compare-and-set (`expected_epoch`).
    - The stop is an ordinary operator stop at an empty queue, so `settle_shutdown` moves no bound orders to BLOCKED (`operations.py:378-458`).
  - **The design's own data shows why one order per driver fails.** The profile is pinned in the unit environment (Stage 5 M5, `services.py:100-110`), so the whole factory serves exactly one profile at a time. The natural unit of work is therefore: one stack session = one role batch = N orders, each with a single role.
  - **What the reshape fixes, with no new mechanism:**
    - Every order is QUEUED when `scheduler.preflight` runs (Stage 7 B2.1).
    - `max_concurrent_workorders: 1` (`afo-policy.yaml:27`) becomes harmless, because one order at a time is what a batch needs.
    - `max_order_attempts: 3` (`afo-policy.yaml:35`) is never reached.
    - Next-role orders are queued after the swap, so the epoch quarantine does not apply (Stage 5 B1.3).
    - Nothing is carried through `brownfield/resume.py:314-315` (`RESUME_LOCAL_PROFILE_CHANGED`) (Stage 7 B1, Stage 5 B2).
  - **How the cross-role link works.** The INSPECT or REWORK order declares the earlier order's sealed handoff (plus findings, for REWORK) as a hash-bound input. That input is materialized through the author gate, following the existing `provided_requirements.validate/materialize` pattern (`provided_requirements.py:22-96`): hash check, `swe1.assemble`, `self_check`, receipt.
    - That pattern is already followed by normal inspection (spec.md lines 256-258).
    - Authorship would record the prior lab order's identity, not a review claim. The `REVIEWED` check at lines 36-42 does not apply.
  - **Further findings that disappear:**
    - Each role keeps its own workspace and its own `BL-SWE.1-nnn` baseline. Nothing is overwritten (Stage 7 M2), and `lab_seal` no longer duplicates `InspectionEngine.freeze` (Stage 5 M1).
    - Every candidate can be scored, so initial-vs-final scoring comes for free (Stage 7 M10, partly).
    - Each order has a fixed role, so the graph's identity is fixed per order (Stage 7 M11, partly).
    - The input handoff's `id ↔ (task, key)` map becomes the ID ledger (Stage 5 N3).
  - **Swap counts.** Arm A needs at most 4 swaps per corpus. Arm B needs 0 with one Qwen profile (Stage 5 M4). The rejection of Alternative D then rests on real numbers.
  - **Alternative B's rejection does not hold.**
    - "A new cross-order link field whose check, if wrong, lets an inspector run on a stale candidate": the link is an input sha256, checked the same way existing inputs are (`provided_requirements.py:31-32`).
    - "One ledger and history per driver": an `experiment_id` plus `driver` key on each order, and each handoff listing its input handoff's sha, give the same result.
  - **What can be deleted:** `attempt_plan`, `planned_attempt`, the lab branch in dispatch, `plan_entry` in runtime/product_job, `swap.py`, `process-lab-swap.sh`, the `model-swap/1` schema (reduce it to an activation record like `activation.json`), and the seal chain.
  - **What stays:** `RESIDENT_PROFILE_MISMATCH`, but as a fail-closed guard (refuse an order whose profile is not `FORGE_OPERATIONS_PROFILE`), not as the batching mechanism. This also avoids the backoff of up to 3,600 s (Stage 7 B2.4).
- **Action:** Put D1 back to the owner with this evidence. D2 makes the operator the swap actor, so the operator is also the natural batcher.

## Majors

### Z8-M1. G5 claims a deterministic judge, but the scorer can only pre-score
- **Affected scope:** G5 (63-65); §9 (295-315); CUJ 3 (128-133); Q4 (90-91); file 12 (589-595).
- **Simplicity rationale:**
  - Stage 7 M3/M4 and Stage 6 #6 show that a key match on source ref plus register/op counts a requirement with the wrong behaviour as COVERED. The plan's EGM gate blocks on exactly this ("fake acceptance", plan §8.2).
  - "Judgeable" has no deterministic definition.
  - Behavioural obligations (caller contracts, error semantics) will mostly come out as `UNKNOWN_NEEDS_HUMAN`.
  - This is not a wording fix. It changes what G5 promises. The plan already divides the work this way: "deterministic checks for structure/identity/traceability", "expert review for semantic ambiguity" (plan lines 152, 188-190).
- **Recommendation:**
  - Restate G5 as: deterministic checks (hashes, ref resolvability, ID integrity, candidate obligation matches), plus a recorded human disposition for each obligation that no deterministic predicate decides. Align that record with DA-FR-057's owner-signed, hash-bound disposition (spec.md line 201).
  - Declare Q4 a blocker for the first scored result.
  - CUJ 3 then reduces to "NOT_INSPECTED is never PASS". This settles Stage 7 M14.

### Z8-M2. Cut the corpus-decision layer now; later reports confirm Stage 5 M7/M8
- **Affected scope:** D5 (106-107); G6 (66-68); §9 "Corpus decision" (317-326); files 5a and 13a (527-533, 604-609); `test_process_lab_decide.py` (796-798); §6 and Q3 (88-89, 265-269).
- **Simplicity rationale:**
  - After Stage 5 flagged `decide` and G6 as speculative, Stages 6-7 found more defects that exist only in this layer:
    - the preregistration has no schema (Stage 6 #7, Stage 7 M5);
    - "incomplete" contradicts "missing counts as FAILS" (Stage 7 M12);
    - "import success" is undefined (Stage 7 M11/M13);
    - seeded-defect recall is missing (Stage 7 M10);
    - no CUJ covers the corpus journey (structural F5).
  - The layer depends on Q3 (no unseen case exists) and Q4 (no reviewer).
  - Stage 7 M9 adds that a "non-peripheral" holdout cannot pass the register-inventory pipeline. That reinforces deferring `primary_manual` (Stage 5 M9).
- **Recommendation:**
  - Remove `decide`, `process-decision/1`, the preregistration format, G6 and `primary_manual` from this design.
  - Keep one small guard from Stage 7 M5: an operator-side experiment record, frozen before the first attempt, that lists the oracle sha256 and the profile shas. `score` refuses any oracle whose hash differs.

### Z8-M3. Separate the lab from the Ornith question, and put Ornith's serving feasibility first
- **Affected scope:** Problem 5 (41-43); increment order (471-480); files 2 and 24 (491-498, 701-711); §10a (336-352).
- **Simplicity rationale:**
  - Problems 1-3 (slow feedback, unusable output, no independent score) are independent of which model authors.
  - Stage 7 M8 shows the Ornith arm rests on unverified assumptions:
    - the stack runs Ollama 0.34's bundled `llama-server`, while the speed study used a standalone binary;
    - `--reasoning-format deepseek` is hard-coded;
    - manifest sha vs GGUF sha is ambiguous;
    - there is no KV-cache budget.
  - Stage 5 M6 adds that Ornith jobs need `product_role_trial` (`afo/product_role_trial.py:1-6`) to be admitted at all.
  - If the factory stack cannot serve Ornith, the A arm does not exist. Yet increment 1 builds `hf.co` manifest resolution on the assumption that it can.
- **Recommendation:**
  - **Phase 1:** run the lab with one Qwen profile (author and inspector settings in one profile, zero swaps). This delivers G1, G3, G4, G5 and the CRC package, which is the plan's "smallest code path to one real SWE.1 package" (plan line 311).
  - **Phase 2:** add the Ornith profile, `hf.co` manifests, `product_role_trial` and the activation-based swap (Z8-B1).
  - Phase 2 should be gated on a read-only check in an owner window that the bundled binary can load the D3 GGUF with its template.

### Z8-M4. The missing Risks section can be written much more simply after the reshape
- **Affected scope:** whole document; Stage 7 B4 / structural F1.
- **Simplicity rationale:** This stays a compliance gap. After Z8-B1 and Z8-M3, its content becomes short and concrete:
  - operator presence: at most 4 swaps per corpus run in arm A, 0 in phase 1;
  - the human adjudication load from Z8-M1;
  - Ornith serving feasibility;
  - stranded deferred orders (avoided if mismatch refuses instead of deferring).
- **Recommendation:** Write the section after the reshape, not before.

## Nits

- **N1. Alternative I's rationale (lines 433-439) is weaker than stated.**
  - The lab path makes no agent tool calls (§10a, lines 338-341), so "bypass production agent policy" is not the real cost. The real reason is AFO's accounting, admission and lifecycle.
  - Also list `lrtx/modelcmp.py` (Stage 5 M11). It measures author validity and load time as the switching cost (`modelcmp.py:18`) and could serve as a pre-AFO smoke test.
- **N2. Altitude.** Do not polish items 14 and 17-20, 27 or their tests (lines 611-673, 731-740, 772-782); Z8-B1 deletes them. The remaining line-number pins ("near line 293/406") are acceptable in the detailed section only.

---

## How the earlier findings sort

**They change the design's shape (fold into Z8-B1 to Z8-M3):**
- Stage 5 B1, B2, M2, M5
- Stage 7 B1, B2, B3, M2, M10 (part), M11 (part)
- Stage 6 #1-#5, #8, #13
- Stage 5 M7, M8, M9; Stage 7 M5, M9 (holdout), M12, M13; Stage 6 #7
- Stage 7 M3/M4 (scorer)
- Stage 7 M8 and Stage 5 M6 (Ornith feasibility)

**They disappear entirely under the reshape:**
- Stage 5 M1, M4, N3, N5 (the AT11 wording stays only if D4 stays)
- Stage 6 #4, #13, #18 (`plan_entry` profile)
- Stage 7 N6

**Local fixes that stay valid under any shape (apply as-is):**
- **G3 cache key (Stage 7 M7, Stage 5 N1).** Make the change global on purpose: the name-only key is a bug for strict orders too. Hash `role_capability.IDENTITY` plus the profile sha, and amend G7 and "What stays unchanged" to match.
- **Lesson leakage (Stage 7 M6).** Set the existing `evaluation_holdout` manifest flag on every lab order. It is already honoured in `knowledge/context.py:29`, `knowledge/experience.py:249` and `knowledge/references.py:69`.
- **Smaller items:**
  - Stage 5 M3: emit the small role graph and leave `_build` alone.
  - Stage 5 M10: keep a single `OLLAMA_CONTEXT_LENGTH`.
  - Stage 5 M12: `criteria_result` lives only in the score report.
  - Stage 5 N2/N4.
- **Document fixes:** the remaining Stage 6 terminology and definitions, Stage 7 M15-M17 (evidence links, AT citations, DA ticks), and every structural and style Nit.

## What is sound (unchanged since Stage 5)

- No new scheduler, router or EGM runtime.
- The oracle stays outside the workspace.
- The per-requirement `NOT_INSPECTED` outcome.
- The minimal SWE.2 importer as an interface proof.
- The CRC smoke run.
- The rejections of Alternatives C, E and F.

After the reshape, the design keeps everything the plan asks for (G1, G3, G4, G5, the importer, the smoke run, and a fenced, recorded handoff on one GPU) with clearly less new code than the current draft.

Reviewed file: /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md

Main code evidence:
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py (lines 92-133)
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/afo/operations.py (lines 366-458)
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/provided_requirements.py (lines 22-96)
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/config/factory/afo-policy.yaml (lines 27, 35)
- /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/factory/python/forge_factory/brownfield/resume.py (line 315)
