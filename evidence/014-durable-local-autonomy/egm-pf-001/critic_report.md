# Goldfish Review Report — Stage 7 (Critic Review), round 1

**Target:** `docs/designs/forge-c-process-first-ornith-qwen.md` (`Lines 1-464`, FeatureRange), 2026-10-31
**Dispatch:** direct (flat) — three fresh native subagents in parallel; egm 0.1.0 @403d888; standards:
egm-design + egm-structural → feature-spec-standard; egm-style → persona rules only.
**Round policy:** one round, then the Stage 7 gate (plan §8.2.4: at most one full review/resolution cycle).

## Reviewer Status

| Reviewer | Status | Blocker | Major | Nit |
| --- | --- | --- | --- | --- |
| `egm-design` | completed | 3 | 11 | 6 |
| `egm-structural` | completed | 1 | 5 | 9 |
| `egm-style` | completed | 0 | 12 | 20 |

## Consolidated findings (Elephant deduplication; raw reports follow verbatim)

Elephant code checks (not reviewer statements) are marked ✔.

### 🔴 Blockers

| ID | Finding | Raised by | Check |
|---|---|---|---|
| C7-B1 | Attempts 2–5 cannot inherit SWE.1: resume refuses a profile change (`brownfield/resume.py:314` `RESUME_LOCAL_PROFILE_CHANGED`), carries only PASS phases, and needs delivery orders. | design B1 (= Stage 5 B2) | ✔ |
| C7-B2 | Role batching cannot happen with the queue: only QUEUED orders get preflight, `max_concurrent_workorders: 1`, `max_order_attempts: 3`, and a mismatch deferral gets exponential backoff up to 3600 s. | design B2 (= Stage 5 B1) | ✔ |
| C7-B3 | The swap state machine is not runnable on existing commands: `stack.start` is fenced to intent RUNNING (`operations.py:366-375`); the probe needs admission; swap-STOP reuses operator `settle_shutdown`, which BLOCKs bound orders; there is no `expected_epoch` CAS. | design B3 | ✔ |
| C7-B4 | Risks & Mitigations section required by feature-spec-standard is missing (no failure-mode, operator-load or capacity estimate). | structural F1, design M9 | — |

### 🟡 Major (deduplicated)

| ID | Finding | Raised by |
|---|---|---|
| C7-M1 | D4/D2 not carried through: "three attempts", diagram seq 1–3, "Attempts 2 and 3", "2–3 swaps"; CUJ 1 says AFO swaps (contradicts D2); inspection count ambiguous. | design M1, structural F3/F4, style M1–M3 |
| C7-M2 | Diagram outdated: no seq 4–5, scorer shown as producing maturity, `decide` missing. | structural F2, style M4 |
| C7-M3 | Seals hash bytes that REWORK overwrites; the prior candidate is not auditable; no write-once store. | design M2 |
| C7-M4 | Scorer matching allows false coverage; resolvable ref ≠ supporting ref; "judgeable" undefined; NEEDS_HUMAN volume and disposition format open. | design M3, style M8 |
| C7-M5 | Oracle not bound to a preregistration; preregistration has no schema; thresholds could move after the fact. | design M4, structural F5 |
| C7-M6 | Validated-lesson retrieval in author packets can leak oracle-derived knowledge and confound A/B (`evaluation_holdout` not set); lab jobs' experience/learning disposition not covered. | design M5 |
| C7-M7 | G3 changes the shared `input_hash` globally (affects strict/Delivery-First checkpoints), contradicting G7/"unchanged"; which digest is hashed is unclear; cache field list differs across G3/§4/CUJ 5. | design M6, style M9 |
| C7-M8 | Ornith serving unverified: bundled Ollama-0.34 llama-server vs standalone binary, manifest sha vs GGUF sha, hard-coded `--reasoning-format deepseek`, no context/KV budget, no free-VRAM precondition. | design M7 |
| C7-M9 | Ledger key reuses the Alternative J defect for non-register requirements; key collisions; non-peripheral holdout cannot pass the register-inventory pipeline. | design M8 |
| C7-M10 | G6 has no owning component; initial-vs-final scoring, seeded-defect precision/recall and rework-regression not designed; AT11 deviation unrecorded. | design M10, structural F5 |
| C7-M11 | Per-role graph shape and identity unspecified; inspector budgets and "actionable finding" undefined; import "success" undefined vs AMBIGUOUS/MISSING. | design M11 |
| C7-M12 | Corpus "incomplete" → EXPERIMENTAL contradicts "missing trial counts as FAILS". | style M6 |
| C7-M13 | SWE.2 importer rejection terms and labels inconsistent across G4/CUJ 4/§10. | style M5 |
| C7-M14 | CUJ 3 condition matches no scoring rule. | style M7, design N1 |
| C7-M15 | Evidence figures (2/3 cohort, 16/35 gaps, speed study, 5/9 and 2/2) lack source links; the problem statement is not quantified. | structural F6, style M11 |
| C7-M16 | AT16 (and AT08/AT17) cited for different guarantees than the plan defines. | style M12, design N2 |
| C7-M17 | Non-Goal on DA ticks has no named rule. | style M10 |

### 🟢 Nits

Deduplicated: "Resolved decisions" nested under Open Questions and numbering starting at Q3; heading names vs the standard;
"10a" numbering and inconsistent tags; mixed path conventions and a truncated Qwen digest; undefined terms (AFO, Fabro,
MTP, DA, loop10, F015, KV); wrap/trailing-whitespace drift; per-driver 90% stricter than the plan's corpus-wide wording;
"operator-only directory" is not an OS boundary; Ornith named efforts unclear; arm B warm-reload not representative;
assorted wording (see raw reports).

---

## Raw report — `egm-design`

# Design Critic review: Stage 7, round 1

**Target:** `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md`, lines 1-464.

**Standard:** feature-spec-standard.md. I read the persona, the standard, all four GoldfishContext files, and the source files the design cites (paths below are relative to `factory/python/forge_factory/`).

**Verdict: not ready.** I found 3 Blockers, 11 Majors and 6 Nits. All three Blockers are mechanisms the design says it reuses "unchanged" that do not work the way it assumes.

**Disclosure:** one search returned a single line from `evidence/014-durable-local-autonomy/egm-pf-001/zoom_out_report.md`, which was not in my supplied context. I did not open that file. Finding B2 comes from my own reading of `afo/queue.py`, `afo/scheduler.py` and `config/factory/afo-policy.yaml`.

---

### B1. The attempt plan depends on a brownfield resume that refuses exactly this use
- **Severity:** Blocker
- **Affected scope:** lines 98-99, 191-193, 207-208; `brownfield/resume.py`
- **Finding:** Line 207 says later attempts "resume the previous attempt's workspace with the existing validated brownfield resume." The code rules this out in three ways:
  - **It refuses a profile change.** `resume()` raises `RESUME_LOCAL_PROFILE_CHANGED` when `old["local_profile"] != man["local_profile"]` (resume.py:314-315). It also raises `RESUME_CONTRACT_OR_RUNTIME_CHANGED` when the resume identities differ (:305-308). Every lab step from AUTHOR to INSPECT to REWORK changes the profile, by design.
  - **It only copies phases that passed.** A phase is copied only if its gate decision is PASS, it was inspected by `swe1-inspector`, and every required check passed (:321-335). After an AUTHOR-only attempt, SWE.1 has no inspection, so nothing is copied and the INSPECT attempt would start with no candidate. After a failed inspection, REWORK would also inherit nothing.
  - **It only accepts delivery orders and copies into a new work order.** It requires `man.get("delivery")` (:167-168), and it copies into a new work order rather than reusing "the previous attempt's workspace" (:298).
- **Recommendation:** Define a lab-specific way to hand state from one attempt to the next. For example: a hash-verified copy of the sealed artifacts, plus the seal chain, into the next attempt's workspace, with its own refusal codes and negative tests. Then remove the "existing validated brownfield resume" claim. Also fix line 207: with D4 there are up to five attempts, not just "2 and 3".

### B2. Role batching across drivers cannot happen with the existing queue
- **Severity:** Blocker
- **Affected scope:** lines 155-163, 222-226, 381-382, 398-399; `afo/scheduler.py:137,189,251`; `afo/queue.py:33,509-514`; `config/factory/afo-policy.yaml:27,35`
- **Finding:** The batching argument ("all seq-1 attempts run first. Seq-2 attempts wait…") fails on four counts:
  1. `scheduler.cycle` only considers orders in state `QUEUED` (`next_candidate`, queue.py:485). Attempts 2-5 of an admitted order never reach `scheduler.preflight`, so a `RESIDENT_PROFILE_MISMATCH` check placed there cannot hold them back.
  2. `queue.admit` refuses once `ACTIVE_STATES` (ADMITTED, RUNNING, WAITING_RECOVERY, VALIDATING) reaches `max_concurrent_workorders`, which is 1. A lab order stays active across all its attempts. Driver 2's AUTHOR therefore cannot start until driver 1's whole plan finishes. That means up to 4 swaps per driver, not the "about 2-3 per corpus" that justifies D2 (line 398).
  3. `budgets.max_order_attempts` is 3. That value is used by preflight (:137) and by the mission/recovery `max_attempts` field, but a lab order needs up to 5.
  4. `store.defer` backs off exponentially, capped at 3,600 s. Only the exact issue list `["NATIVE_INFERENCE_CAPACITY_HELD"]` gets the short retry (:232-236). So orders deferred for a profile mismatch could sit idle for up to an hour after a swap. That inflates the A/B latency the design wants to measure (AT13).
- **Recommendation:** Pick one model and specify it:
  - (a) Lab orders go back to `QUEUED` between attempts. They release their concurrency slot, and the profile check runs on the next attempt's profile.
  - (b) Revisit Alternative B (one order per role). It fits the QUEUED-only preflight naturally, and its rejection rationale (lines 380-382) does not consider this constraint.

  Either way, state the policy changes needed (attempt budget, concurrency, short retry for the mismatch deferral). Then recompute the expected swap count and feed it into the Alternative D rejection.

### B3. The swap state machine cannot run on existing commands, and it confuses swap-STOP with operator-STOP
- **Severity:** Blocker (the plan's EGM gate blocks on an "incorrect state machine")
- **Affected scope:** lines 117-119, 121-126, 228-248; `lrtx/stack.py:341-364`; `afo/operations.py:89-123,366-375,378-458`; `afo/request_admission.py:184`
- **Finding:**
  - **Starting the new profile is refused while the intent is STOPPED.** `stack.start` wraps its effect in `fenced_call`, which raises `OPERATIONS_ADMISSION_FENCED` unless the mode is `RUNNING`. The machine runs `stack start --profile P_to` during UNLOADED→LOADING while the intent is STOPPED, and only sets RUNNING after READY.
  - **The identity probe cannot be admitted either.** The "one admitted probe" needs a mode of RUNNING, PAUSED or DRAINING (request_admission.py:184), plus an admitted job and order. The design never says which job or mission the probe belongs to, or which budget it charges.
  - **Setting RUNNING to enable the probe would let the scheduler dispatch real work first.** The "only calls existing commands" claim (line 228) is therefore false. Any workaround (calling `_start` directly, or running with intent unconfigured) bypasses the operator fence the plan protects (invariant 7).
  - **The swap uses the operator-shutdown path as a routine step.** `settle_shutdown` revokes VALID executions, marks ACTIVE ones `BLOCKED/OPERATOR_SHUTDOWN`, moves bound orders to `BLOCKED` (`_project_shutdown_orders`), and the Conductor exits. Line 240 ("STOP or revoke at any state → no further transition") has no field that tells a swap-STOP from a real operator abort.
  - **CUJ 2 promises "a truthful terminal disposition" for "the order", but the machine only leaves the stack STOPPED.** It does not say which queued or deferred lab orders become terminal, or with what reason.
  - **The RUNNING step is not compare-and-set.** `Intent.set` supports `expected_epoch`, but the design never uses it. A script reaching READY→RUNNING after a concurrent operator STOP could overwrite that STOP.
- **Recommendation:** Respecify the swap around the real fences:
  - Use a distinct swap reason or record, so STOPPED-for-swap is distinguishable from an operator abort.
  - Add a supported way to start the new profile while not RUNNING. One candidate is the `control_only` style start used in `recover_profile`, extended to bring up the model behind a fence.
  - Add a probe that is not a production admission, or a dedicated probe job with its own accounting.
  - Use `expected_epoch` on every intent write.
  - Make the script re-read the intent before each transition. A STOP during LOADING must actively stop the stack, not merely "not transition".
  - List the terminal disposition of every lab order in each abort case.

---

### M1. D4 and D2 are not carried through the rest of the document
- **Severity:** Major
- **Affected scope:** lines 117-118, 155-158, 207, 381, 398
- **Finding:**
  - CUJ 1 says "AFO runs the Ornith author job, proves quiescence, swaps to Qwen". That contradicts D2 (line 100: "AFO never loads or unloads a model by itself").
  - The data-flow diagram shows only seq 1-3.
  - Line 207 says "Attempts 2 and 3".
  - Alternative B's rejection cites "three planned attempts".
  - The swap count (line 398) assumes the pre-D4 three-attempt plan.
- **Recommendation:** Rewrite CUJ 1 with the operator as the swap actor, and add the operator's wait points. Then update the diagram, §2 and the Alternative B/D rationale for the five-attempt plan.

### M2. Seals are called immutable, but the bytes behind them are overwritten in place
- **Severity:** Major
- **Affected scope:** lines 191-193, 208
- **Finding:** `lab_seal` "writes or updates the handoff package" and "hashes the current SWE.1 artifacts". REWORK then rewrites those same artifact paths in the same workspace. A seal that holds only hashes cannot keep "the prior candidate … auditable" (AT11) once the bytes are gone. "They cannot change them" (line 208) has no enforcement mechanism behind it.
- **Recommendation:** Copy the artifacts into a content-addressed, write-once directory at each seal, for example `process-lab/seals/<seq>/<sha>/`. Make `handoff.json` an append-only chain of seal records. Add a test that tampering with an earlier seal's bytes is detected.

### M3. The scorer's matching rules allow false coverage
- **Severity:** Major (the plan's EGM gate blocks on "fake acceptance")
- **Affected scope:** lines 297-311
- **Finding:**
  - "Matches obligations by the oracle's keys" with "matching hints" is undefined. A requirement that cites the right source reference and register key but states the wrong behaviour would match unambiguously, so it counts as covered.
  - A source reference that resolves (exists in the bound inputs) is not evidence that the source supports the claim (plan §4 dimension 2).
  - "≥ 90% judgeable verification criteria" has no deterministic definition.
  - Behavioural obligations (caller preconditions, error semantics) will mostly fall to `UNKNOWN_NEEDS_HUMAN`. There is no estimate of the human adjudication load, and the disposition record format is open (Q4).
- **Recommendation:**
  - Define the matching algorithm precisely, including which fields must agree.
  - Make "covered" require a semantic-equivalence check: either an oracle-supplied deterministic predicate or a recorded human disposition.
  - Define "judgeable" as a checkable property.
  - Give a budget for the expected `NEEDS_HUMAN` volume and a schema for the human disposition record.

### M4. The oracle is not bound to a preregistration, so it can be swapped or edited after the fact
- **Severity:** Major
- **Affected scope:** lines 297-303, 317-326
- **Finding:** `score <package> <oracle>` accepts any oracle path. `decide <preregistration.json>` has no schema. Nothing checks that the oracle used for scoring matches a hash frozen before any inference ran. The design deliberately leaves `frozen_acceptance_oracle_ref` out of the manifest (a reasonable anti-leakage choice), but it puts no other binding in its place. Plan §3 says thresholds may change "only for a future preregistered cohort".
- **Recommendation:** Define `forge-c/process-lab-preregistration/1` to cover:
  - corpus and unseen marks
  - oracle sha256 values and reviewer records
  - profile shas and model digests
  - thresholds and the trial list
  - a timestamp that precedes the first attempt

  `score` should refuse an oracle whose hash is not preregistered, and `decide` should refuse score reports produced from a different oracle hash.

### M5. Lesson retrieval in lab author prompts can leak oracle knowledge and confound the A/B comparison
- **Severity:** Major
- **Affected scope:** lines 113-119, 179-185, 295-301; `lrtx/structured.py:129-163`
- **Finding:** `packet()` adds VALIDATED lessons to any `*-author` role unless the manifest sets `evaluation_holdout`. The design never mentions this. Lessons learned from earlier lab trials (rework findings, human dispositions on scored gaps) could carry oracle-derived obligations into later authors, including the unseen case. The lesson store also changes over time, so arms A and B run at different times would see different context. Separately, DA-FR-037/038 require a factual experience record and learning disposition for every terminal job. Lab orders create up to five jobs each, and the design does not cover them.
- **Recommendation:** Set `evaluation_holdout`, or an equivalent lab flag, on every lab manifest, or freeze the lesson set at preregistration. Extend the AT16-style test to cover lesson content. State how lab jobs produce experience and learning dispositions without feeding the scored corpus.

### M6. The G3 cache change is global, which conflicts with G7 and the "unchanged" list
- **Severity:** Major
- **Affected scope:** lines 57-58, 69-70, 250-254, 359-363
- **Finding:** `input_hash` (structured.py:237) is shared by every structured path. Adding digest, profile sha, reasoning and schema mode to it changes packet records and checkpoint keys for strict and Delivery-First orders too. In-flight strict orders lose checkpoint reuse, and any test that pins hashes changes. That contradicts "keep passing their existing tests unchanged" (G7) and "same manifests as at `876d75f`" (line 363). The design also does not say which digest goes into the hash: the profile's declared digest, or the served identity verified at the probe.
- **Recommendation:** Either scope the new fields to lab packets, or accept the global change openly. If global, list the strict-path effects (checkpoint invalidation, resume) and update G7 accordingly. Specify that the hashed digest is the probe-verified served identity.

### M7. The Ornith serving assumptions are unverified
- **Severity:** Major (the plan's EGM gate covers an "invalid 48-GB handoff")
- **Affected scope:** lines 101-103, 214-220, 336-352, 425-431; `lrtx/stack.py:370-413`
- **Finding:**
  - **Different binary.** The stack runs Ollama 0.34's bundled `llama-server` (`ollama-0.34.0/lib/ollama/llama-server`). The speed study used a standalone llama-server outside the stack (SOURCE-INVENTORY §A). Support for the Ornith architecture and chat template in the bundled build is assumed, not shown.
  - **Different digest.** The existing check compares the sha256 of the manifest file with the pinned digest and checks only the blob's size. D3's `de46c4…` is the sha of the GGUF file. "The same digest and blob-size checks" does not say which digest Ornith's identity, and therefore G3, binds to.
  - **Hard-coded reasoning flags.** `--reasoning-format deepseek` is applied whenever a reasoning effort is set. The plan notes that Ornith has a model-specific reasoning parser, and recorded-response fixtures (§10a) cannot check how the live server parses it.
  - **No memory budget.** With 37.8 GB of weights on 48 GB, no initial context or KV-cache budget is given (the plan suggests 32K or 64K). The swap never checks that GPU memory was actually freed before loading; "kernel-proven exit" does not prove that.
- **Recommendation:** State the runtime binary and its provenance for Ornith. Pin both the manifest digest and the blob content sha. Make the reasoning format a profile field. Give a starting context and KV-cache budget derived from the speed study. Add a free-VRAM precondition to UNLOADED→LOADING.

### M8. The stable-ID ledger and the holdout case do not fit the existing author pipeline
- **Severity:** Major
- **Affected scope:** lines 88-89, 256-269, 441-446; `lrtx/swe1.py:491-509`
- **Finding:**
  - For requirements not tied to a register, the ledger key is "a normalized statement hash". That has the exact defect used to reject Alternative J: a reworded requirement gets a new ID.
  - Two requirements on the same source reference and register/field/op (for example, a read-semantics rule and a caller precondition) collide, and the design has no tie-breaker.
  - `budgets` rows have no source key at all.
  - The SWE.1 author builds its work from the register inventory (`inv["registers"]`, one group per register), and the gate checks register effects. A "non-peripheral component" holdout (Q3) cannot go through that pipeline. §6 only removes the RM0486 string.
- **Recommendation:** Define a collision-free obligation key, for example adding a deterministic per-group ordinal or task ID, and a rule for keeping IDs across rewording, such as matching to the prior ledger entry by source and task. Either drop "non-peripheral" from the holdout options or scope the inventory and gate changes it would need.

### M9. The standard's Risks & Mitigations section is missing, and there is no capacity estimate
- **Severity:** Major (standard compliance)
- **Affected scope:** lines 450-461, whole document
- **Finding:** The standard requires the document to "explicitly call out its own constraints… failure modes, security implications, scalability limits, and how they will be mitigated". The NFRs say performance is "measured, not targets", and there is no consolidated risk section.
  - There is no estimate of corpus wall-time: drivers × up to 5 attempts × 2 arms × trials, plus swaps.
  - There is no estimate of operator presence. Under D2 a human must see each batch finish and run each swap, and no "batch drained" signal is defined.
  - Failure modes such as a rollback leaving deferred orders waiting with no deadline (DA-FR-047) are not listed.
- **Recommendation:** Add a Risks & Mitigations section that covers B1-B3, M3-M5 and M7, operator workload, and stranded deferred orders. Add a rough capacity budget per corpus run.

### M10. "A/B readiness" (G6) omits measurements the plan requires
- **Severity:** Major
- **Affected scope:** lines 66-68, 184-189, 303-315
- **Finding:**
  - Plan §5.4 requires scoring the initial author output separately from the output after inspection and rework. The scorer only scores "the package", so the AUTHOR seal is never scored.
  - Inspector precision and recall on seeded defects (plan §5.1 and §10) is not designed.
  - Given the recorded inspector false-rejection rates (5/9, 2/2), rework can degrade correct requirements, and the final rework is uninspected. The design has no keep-best or regression rule and does not even measure this effect.
  - Plan AT11 says "exactly one bounded correction". D4 deviates from that, but line 189 cites AT11 without noting the conflict.
- **Recommendation:** Score every seal, not just the final one. Report the initial-vs-final difference and how often rework made things worse. Add a seeded-defect set to the preregistration. Record the AT11 deviation explicitly against D4.

### M11. The graph shape, budgets and import success are underspecified
- **Severity:** Major
- **Affected scope:** lines 130-133, 171-189, 325-326, 330-333
- **Finding:**
  - §1 describes a single SWE.1 graph where `stop_after` reroutes `swe1_inspect_gate → SWE.2`. The role list that follows describes three different subgraphs, none of which contains `swe1_inspect_gate`. The design does not say how one work order yields a different workflow per attempt, or how that interacts with run/manifest identity.
  - CUJ 3's "time box or repair budget" for the inspector has no source: no profile field, no default value, and no tie to the mission budget. "Actionable finding" (line 209) is undefined.
  - USABLE requires every SWE.2 import "to succeed", but the importer's output includes `AMBIGUOUS` and `MISSING`. Whether those count as success is not defined.
- **Recommendation:** Specify the per-role graph builder output and its identity. Define inspector budgets as profile or work-order fields, plus a deterministic test for "actionable". Define import success, for example: no rejects and no `AMBIGUOUS` critical requirement.

---

### Nits
- **N1 (line 133):** "cannot be MEETS if a critical obligation is uninspected and unmatched" is redundant, because an unmatched critical obligation already fails. State whether a critical requirement that matched but was NOT_INSPECTED affects MEETS. Under lines 309-311 it does not.
- **N2 (line 301):** AT16 in the plan is the privacy test for source-controlled artifacts. The oracle-reference leakage test needs its own ID.
- **N3 (line 309):** Applying "≥ 90% noncritical coverage" to each driver is stricter than plan §3, which applies it "across the eligible corpus". Record this as a deliberate deviation.
- **N4 (line 299):** "Operator-only directory" is not an OS boundary if the factory and the operator share a uid. Say that confinement relies on the MCP path policy and the prompt-assembly test.
- **N5 (line 342):** "the named efforts that render identically in Ornith's template" is unclear. List the efforts and say what "identically" is compared against.
- **N6 (lines 244-246):** Arm B's same-model restart is measured honestly. Still, disclose that its cost (page-cache warm reload) is not representative of a real model change, so a reader does not mistake it for a like-for-like swap cost.

## Raw report — `egm-structural`

I read the persona (`structural.md`), the standard (`feature-spec-standard.md`), the target's lines 1-464, and all four context files. The review is complete.

# Structural Goldfish review: forge-c-process-first-ornith-qwen.md, lines 1-464 (Stage 7, round 1)

**Verdict:** 1 Blocker, 5 Major, 9 Nit. The document is not structurally compliant until the Blocker is fixed.

**Heading map (scope):** H1 title, then H2 Overview, The Problem, Goals, Non-Goals, Open Questions (with H3 Resolved decisions), Critical User Journeys (H3 CUJ 1-5), Technical Plan (Architecture) (H3: Components and data flow, 1-10, 10a, 11, What stays unchanged), Alternatives Considered (H3 A-J), Non-Functional Requirements. No heading levels are skipped and both fenced code blocks (152-167, 230-241) are closed.

---

### Finding 1
1. **Severity:** Blocker
2. **Affected Scope:** Whole document. There is no section between line 365 (Alternatives Considered) and line 464 (end of NFR), nor anywhere else in the file.
3. **Discrepancy Description & Rationale:** The section "Risks & Mitigations" required by the standard is missing. The standard's "Risks & Limits" clause says the spec must call out its own failure modes, security implications, scalability limits, and how they will be mitigated. It also lists "Risks & Mitigations" as a section. The words risk, mitigation, failure mode, scalability and limit appear nowhere in the file. The relevant material is scattered and never consolidated:
   - Failure cases appear in CUJ 2 and CUJ 3.
   - Timeout and rollback appear inside the swap state machine (233, 238).
   - Security appears in one NFR bullet (452-454).

   Some risks are not stated at all. Examples: throughput limits from operator-attended swaps, per-driver oracle authoring cost, Q4 (no oracle reviewer) blocking G5, stale or half-switched stacks, and seal or ledger corruption. A fresh reader cannot confirm that "all major risks ... have been addressed", which is the standard's core pass condition.

### Finding 2
1. **Severity:** Major
2. **Affected Scope:** Lines 152-167 (Components and data flow diagram).
3. **Discrepancy Description & Rationale:** The architecture diagram is out of date and contradicts the text in two ways:
   - It shows only seq1-seq3 (lines 156-158). D4 and section 1 (186-189) define a five-entry plan: AUTHOR, INSPECT, REWORK, INSPECT, REWORK.
   - Line 165 labels the scorer output "score report + maturity". D5 (106-107) and section 9 (317-319) say that only `process_lab.decide` produces process maturity, and `decide` is missing from the diagram.

   The arrow on line 165 also points from the Fabro column back to the scorer, which reverses the producer/consumer direction. Line 160 interleaves the swap-runbook column with the scheduler column, so neither reads cleanly. Because the diagram is the only component layout, it has to match the numbered sections.

### Finding 3
1. **Severity:** Major
2. **Affected Scope:** Lines 52, 98, 117-118, 199-200, 207, 381, 398.
3. **Discrepancy Description & Rationale:** The D4 change (two reworks, five attempts) was only partly carried through the document:
   - Line 207: "Attempts 2 and 3 resume the previous attempt's workspace" does not cover attempts 4 and 5.
   - Line 381: Alternative B still says "D1 chose one order with three planned attempts".
   - Line 398: Alternative D estimates "about 2-3 [swaps] per corpus". With batched seq1-5 alternating between Ornith and Qwen, arm A needs 4 swaps.
   - Lines 52 and 118: "inspection, then up to two inspect/rework rounds" reads as three inspections. That contradicts D4's "nothing is inspected a third time" (105).

   The irregular line wrapping at 52, 98, 118, 199-200 and 61 shows these were inline patches. The sections no longer agree with one another.

### Finding 4
1. **Severity:** Major
2. **Affected Scope:** Lines 117-118 (CUJ 1 Then), compared with line 100 (D2).
3. **Discrepancy Description & Rationale:** CUJ 1 says "AFO runs the Ornith author job, proves quiescence, swaps to Qwen and runs inspection". D2 says "the operator performs model swaps by runbook. AFO never loads or unloads a model by itself." Section 3 (222-226) also has AFO only deferring with `RESIDENT_PROFILE_MISMATCH`. The main user journey gives the swap to the wrong actor and leaves out the operator runbook steps, so the CUJ and the architecture disagree.

### Finding 5
1. **Severity:** Major
2. **Affected Scope:** Line 66 (G6), lines 109-146 (CUJs), lines 148-363 (Technical Plan).
3. **Discrepancy Description & Rationale:** Goals and architecture do not line up one-to-one. G1-G5 and G7 each have an owning Technical Plan section. G6 (the fair A/B report that counts failed trials and switch cost) has none. It appears only in passing at line 244 ("The A/B report sums these"). The `preregistration.json` input to `decide` (317) has no schema or field list in section 8 or 9. No CUJ covers the corpus-level journey either: running arms A and B, then `decide`, then a USABLE or NOT_USABLE decision. That journey is the feature's end goal under D5.

### Finding 6
1. **Severity:** Major
2. **Affected Scope:** Lines 26-29, 41-42, 92-93, 414 (link compliance).
3. **Discrepancy Description & Rationale:** The quantitative evidence has no source links. The only cited sources are the plan, commit `876d75f` and SOURCE-INVENTORY (6-8). These figures have no path or link:
   - The 2/3 cohort and the 16 and 35 open gaps.
   - The "36-trial standalone speed study", about 150 tok/s, 4/9 and 3/9 results, and the 8,192-token truncation.
   - The 5/9 and 2/2 false rejections.

   The speed-study figures do not appear in any supplied context file, so a fresh reader cannot check them. The plan (section 0) names `docs/reports/ASTRA-OVERNIGHT-REVIEW-20261030-31.md` and evidence revision `dce7ad27`, and the design should cite these, plus the speed-study evidence path.

### Finding 7
1. **Severity:** Nit
2. **Affected Scope:** Lines 86-107 (Open Questions, Resolved decisions), plus forward references at 52, 60-61.
3. **Discrepancy Description & Rationale:** "Resolved decisions" sits as an H3 under "Open Questions", so the hierarchy puts closed items inside a section for open ones. It should be a sibling H2. Open questions start at Q3 with no note on what happened to Q1 and Q2 (presumably they became D1 and D2). G1 and G4 cite D4 and D5 before the decisions are defined. The open questions also don't say whether they block implementation, and Q4 effectively blocks G5.

### Finding 8
1. **Severity:** Nit
2. **Affected Scope:** Lines 24, 49, 72, 148.
3. **Discrepancy Description & Rationale:** Headings differ from the standard's names: "The Problem" instead of "Problem Statement", and "Technical Plan (Architecture)" instead of "Proposed Architecture". The standard calls its list non-exhaustive, so this is acceptable, but using its names exactly would make audits mechanical. Goals are numbered (G1-G7) but Non-Goals are not, which breaks the symmetry of the paired sections.

### Finding 9
1. **Severity:** Nit
2. **Affected Scope:** Lines 196, 212, 250, 336 (Technical Plan H3 numbering and tags).
3. **Discrepancy Description & Rationale:** Sections are numbered 1-11, with an inserted "10a" and two unnumbered H3s at the start and end. Tags in the headings are inconsistent: section 2 is "(D1)", section 3 "(D2)", section 4 "(G3)", section 10a "(plan §5.2)", and the rest have none. Section 8 serves G4 and section 9 serves G5 but neither is tagged. Pick one convention, either goal tags on every section or none.

### Finding 10
1. **Severity:** Nit
2. **Affected Scope:** Lines 179-189.
3. **Discrepancy Description & Rationale:** In the attempt list, the first three bullets use role labels (AUTHOR, INSPECT, REWORK) while the fourth uses "Second pair" and bundles two attempts. A per-seq or per-role layout would keep the list parallel and match the five-entry attempt plan.

### Finding 11
1. **Severity:** Nit
2. **Affected Scope:** Lines 303-304.
3. **Discrepancy Description & Rationale:** A bullet list starts right after a paragraph with no blank line. GFM renders this, but every other list in the scope (e.g. 177-179, 319-321, 340-342) has a blank line first.

### Finding 12
1. **Severity:** Nit
2. **Affected Scope:** Lines 7, 52, 61, 98, 118, 199-200, 245-246, 304-305.
3. **Discrepancy Description & Rationale:** Formatting is inconsistent. Line 7 has trailing whitespace. Elsewhere the document hard-wraps at about 120 columns, but the listed lines run past that or break early, which is left over from inline edits.

### Finding 13
1. **Severity:** Nit
2. **Affected Scope:** Lines 10, 448, 463.
3. **Discrepancy Description & Rationale:** Horizontal rules appear before Overview and around NFR but not between other H2 sections. The rules don't reflect the section structure. Either use one between every H2 or only between the metadata and the body.

### Finding 14
1. **Severity:** Nit
2. **Affected Scope:** Lines 31-39, 206, 215, 267, 387-388.
3. **Discrepancy Description & Rationale:** Code paths use mixed conventions. Some carry a package directory (`lrtx/swe1.py:508`, `lrtx/structured.py:172`). Others are bare filenames (`request_admission.py:49`, `role_capability.py:155`, `ears.py`, `provided_requirements.py`), even though they live under `afo/` and `inspection/`. The root `ff/` is only defined at line 467, outside this scope. Line 7 also cites the plan by bare filename, while line 8 uses a repo-relative path. The Qwen digest at 215 is shortened (`8f5fb6b7…6039`), while D3 gives the full sha256. That breaks the identity-pinning convention the design itself relies on (G3).

### Finding 15
1. **Severity:** Nit
2. **Affected Scope:** Lines 77, 84, 189, 193, 336-352.
3. **Discrepancy Description & Rationale:**
   - **Undefined terms:** AFO, Fabro, MTP, DA tasks, loop10 CI, F015 and KV are never defined for a fresh reader.
   - **Mis-cited AT11:** lines 189 and 193 cite AT11 as support, but AT11 in the plan reads "exactly one bounded correction". D4 deliberately departs from that, and the citation should say so.
   - **Unregistered plan deviation:** section 10a sets tool-call qualification from plan §5.2 to NOT_APPLICABLE. The AtomicChat deviation got a decision entry (D3), but this one has no entry in Resolved decisions or Non-Goals.

## Raw report — `egm-style`

I read the persona and target lines 1-464. No document standard was assigned, so this review applies only the persona's own rules. I checked the plan's AT definitions in `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/specs/014-durable-local-autonomy/PROCESS-FIRST-ORNITH-QWEN-EGM-CLAUDE.md` to judge the citations.

**Verdict:** 0 Blockers, 12 Majors, 20 Nits. Most Majors come from text that was not updated after D4 and D5, so the same thing is described in different words or with different counts in different places.

## Major

**M1. Attempt count still says three after D4 raised it to five** (lines 98, 155-158, 192-193, 207, 262, 381, 398)
- D4 allows up to five attempts (AUTHOR, INSPECT, REWORK, INSPECT, REWORK), but several passages still assume three:
  - Line 98 reads "(author, inspect, rework, D4: up to five)". It mixes a role list with a decision reference.
  - The diagram (155-158) shows only seq1-3.
  - Line 192 says the REWORK seal references the AUTHOR seal. Seq 5 should reference the seq-3 seal.
  - Line 207 says "Attempts 2 and 3".
  - Line 262 says "The REWORK attempt" (singular).
  - Line 381 says "three planned attempts".
  - Line 398 says "about 2-3 swaps per corpus". With role batching, five roles need up to four swaps: Ornith, Qwen, Ornith, Qwen, Ornith.
- Lines 189 and 193 cite AT11 as support. The plan's AT11 says "exactly one bounded correction", which D4 changes. The design does not say it departs from AT11.

**M2. The number of inspections is ambiguous** (lines 51-52, 104-105, 117-118, 186)
- G1 and CUJ 1 say "inspection, then up to two inspect/rework rounds". That reads as up to three inspections.
- D4 says "The rework output is inspected once" but does not say which rework. Only the first rework's output is inspected.
- One concept has three names: "round" (52, 118), "pair" (186) and "semantic rework" (104). Pick one term and state the maximum inspection count as a number.

**M3. CUJ 1 says AFO performs the swap, which contradicts D2** (line 117)
- "AFO runs the Ornith author job, proves quiescence, swaps to Qwen" conflicts with D2 (line 100: the operator swaps; AFO never loads or unloads a model) and with Section 3.
- It also implies one order runs start to finish, while lines 224-226 run all seq-1 attempts across drivers as one batch.

**M4. The diagram says the scorer produces a maturity** (line 165)
- "score report + maturity" is attributed to `lab score`.
- D5 (106-107) and line 317-318 say only `decide` produces a process maturity.

**M5. The SWE.2 importer's terms differ across three passages** (lines 61-62, 139-140, 330-333)
- Rejection criteria:
  - G4: "duplicate, missing or contradictory IDs".
  - CUJ 4: "duplicate or dangling IDs and hash mismatches".
  - Section 10: duplicate IDs, dangling trace edges, statement-hash mismatch.
- Classification labels: CUJ 4 says "usable, ambiguous or missing", while Section 10 uses `CONSUMABLE`/`AMBIGUOUS`/`MISSING`.
- "usable" also collides with the maturity value USABLE. Use the Section 10 terms everywhere.

**M6. The outcome for an incomplete corpus contradicts itself** (lines 321-322 vs 326)
- Missing or interrupted trials "count as FAILS", which leads to NOT_USABLE.
- Line 326 assigns EXPERIMENTAL "when the corpus is incomplete".
- Define "incomplete" (fewer than five drivers? no unseen driver? missing trials?) and which rule takes precedence.

**M7. CUJ 3's acceptance condition matches no scoring rule** (line 133)
- "cannot be MEETS if a critical obligation is uninspected and unmatched": an unmatched critical obligation already fails under line 309, so the "uninspected" part adds nothing.
- Lines 314-315 also say inspector verdicts never override the score.
- Either remove the inspection condition or state the rule in Section 9.

**M8. "Judgeable verification criteria" is undefined** (line 310)
- The scorer is deterministic and makes no model call (line 303), but the design never says how "judgeable" is computed. As written, the 90% threshold cannot be checked.

**M9. The cache-identity fields differ across three passages** (lines 57-58, 145, 252-253)
- G3 lists source hash.
- Section 4 adds schema mode and does not mention source hash.
- CUJ 5 lists only digest, profile sha and reasoning.
- Give one canonical field list.

**M10. A Non-Goal has no clear boundary** (line 84)
- "unless real evidence exists under the normal rules": "real" and "normal rules" are undefined. Name the rule or document that governs task ticks.

**M11. The main problem statement is not quantified** (lines 26-27, repeated at 370)
- "slow" and "needed hours and hundreds of requests" carry the core motivation without figures. Cite measured wall time and request counts from SOURCE-INVENTORY.

**M12. AT16 is cited for the wrong claim** (line 301)
- The plan's AT16 is about privacy of source-controlled artifacts.
- The sentence it supports is about oracle paths not appearing in manifests or prompts. That is a different guarantee, so the citation misleads anyone tracing it.

## Nit

1. **"tiny" and "stays green"** (lines 18, 69, 356, 372): "tiny" is imprecise and "stays green" is jargon. Use "two-function" and "passes".
2. **Subjective verdict** (line 29): "is the wrong feedback loop". State the fact instead: six processes rerun to evaluate one.
3. **Second person** (line 28): "you cannot tell". Use an impersonal construction.
4. **"Today"** (lines 15, 199): replace with "at `876d75f`" for a fixed reference point.
5. **"truthful terminal state/disposition"** (lines 52, 125): this is plan vocabulary and cannot be checked as written. Point to the enumerated terminal states (`LAB_ATTEMPT_FAILED`/`LAB_ATTEMPT_STOPPED`, line 204).
6. **"Fair"** (line 66): G6's title is subjective. Name the criteria instead (same corpus, same oracle, all trials counted).
7. **Undefined jargon:**
   - "RM-only driver exercises" (line 80).
   - "already spent" (line 89; means used for calibration).
   - "semantically 3/9" (line 93).
   - "failed serialized-request sizing" (line 428).
   - "the named efforts that render identically" (line 342).
8. **Open Questions numbering** (line 88): it starts at Q3 with no note on Q1-Q2.
9. **References not expanded in this document** (lines 189, 193, 254, 315, 327, 334, 415, 336): AT03, AT10-AT13, "invariant 6" and "plan §5.2" are never defined here. Add a one-line gloss or a pointer.
10. **Unseen-case terminology drifts**: "unseen" (88, 106, 321), "held-out" (89), "holdout" (269). Pick one.
11. **Model naming drifts**: "Qwen3.8-27B Q8" (20), `qwen3.8:27b-q8_0` (215), "Qwen3.8 27B Q8" (405). "sha" as a noun (57, 145, 222) should be "SHA-256".
12. **Truncated digest** (line 215): `8f5fb6b7…6039`, while D3 gives the full hash. Give the full digest.
13. **Index ambiguity** (line 203): `attempt_plan[n]` with seq numbers starting at 1. State whether the index is 0- or 1-based.
14. **Overstated claim** (line 224): "all seq-1 attempts run first" is true only if the Ornith stack is resident first.
15. **Redundancy and filler:**
    - "actual measured cost" (246).
    - "no measure of requirement quality at all" (371).
    - "These stay unchanged:" repeats its heading (361).
    - "Proposed solution in one line:" introduces three lines (45).
16. **Superlatives and idioms:**
    - "largest change ... smallest benefit" (390): unprovable superlatives.
    - "saves little now" (398).
    - "Batching falls out of the queue order" (377-378).
17. **"with useful KV caches"** (line 405): vague. State both weight sizes against 48 GB. If the weights alone exceed 48 GB, the KV-cache qualifier is not needed.
18. **Vague references:**
    - "clean baselines" (414) does not say which arm produced 5/9 and which 2/2.
    - "small independent SWE.1 tasks" (430): "small" is undefined.
    - "legacy workflow" (428).
    - "CLAUDE.md guardrail" (438) does not name the guardrail.
19. **Gap counts** (line 28): "16 and 35 open gaps" gives two figures for a three-trial cohort. Say which trials they belong to.
20. **Formatting and grammar:**
    - Lines 52, 98 and 118 run past the wrap width, and line 198 wraps raggedly.
    - Line 7 has trailing whitespace.
    - Section number "10a" breaks the numbering.
    - Line 346 mixes noun forms ("timeout as OUTCOME_UNKNOWN, cancellation, and 429 handling").
    - Line 325 "every driver `MEETS`" needs a verb ("every driver result is `MEETS`").
    - "incl." (106) should be written out.
