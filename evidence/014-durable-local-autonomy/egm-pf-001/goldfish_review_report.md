Status: resolved (auto accept, 2026-10-31). Applied to the design as revision 2; revision 1 kept as design-r1-as-reviewed.md (sha256 82a31dcb2ef2d35e…). Applied: 18 clusters PROPOSE FIX plus the fixable part of RC-19; DECLINE: 3 template/spelling nits; CONTEST 0; ESCALATE 0. Correction found during resolution: the Ornith speed study used the same bundled llama-server binary as the stack (SOURCE-INVENTORY corrected).

# Goldfish Annotated Review Report

**Target:** `docs/designs/forge-c-process-first-ornith-qwen.md` (`full file`, 832 lines at review)
**Inputs:** stage reports 5–9 in this directory (raw IDs: S5 = zoom_out_report, S6 = comprehension_report, C7 = critic_report,
Z8 = intermediate_zoom_out_report, R9 = implementation_readiness_report).
**Owner decisions taken during resolution (2026-10-31):**
- **D1′** (replaces D1): one order per (driver, role), up to five single-role orders per driver. Orders are linked by
  a hash-bound handoff input, with one stack session per role batch.
- **D6:** both model arms (Ornith and Qwen) in the first delivery.
- **D7:** lab purpose is QM, with a lab-scoped exception in `qm.validate_profile` so the stepwise inspector can be used.
- **D8:** cut the corpus-decision layer. Keep a frozen experiment-record oracle guard.
- **G3:** the identity hash is fixed globally, and G7 is amended to match.

Severity mapping: Blocker = High, Major = Medium, Nit = Low. Findings are grouped into resolution clusters. Each
cluster lists every raw finding it covers, so every finding has exactly one disposition.

---

## High

### [RC-1] Role/attempt shape does not fit queue, resume, epoch and admission [`egm-zoom-out`, `egm-design`, `egm-implementation-readiness`, `egm-codebase-details`] - Severity: High
*   **Affected Scope:** §2, §3 scheduler rule, diagram, Alternatives B/D, files 17–20 (lines 152–248, 375–400, 639–673).
*   **Discrepancy Description:** Planned attempts never reach `scheduler.preflight`, which only sees QUEUED orders.
    The concurrency limit is 1, and `max_order_attempts` is 3. A launch queued before a swap is quarantined by the
    epoch fence. Resume copies only phases whose gate passed and refuses a profile change. The attempt schema rejects
    `plan_entry`. The launcher never sees the attempt record.
*   **Rationale:** Covers S5-B1, S5-B2, S5-M2, C7-B1, C7-B2, C7-M3, Z8-B1, R9-B1, R9-B2, R9-B6, IR-M2, IR-M3, IR-M14,
    CD-M12, CD-M13, S6-#3, S6-#4, S6-#13, S6-#18, S5-M1, S5-N3 and S5-M12.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Code-confirmed (`queue.py:509-514`, `dispatch.py:84-87`, `workorder.py:494-500`,
    `brownfield/resume.py:314`, `attempt.schema.json`). The owner chose D1′.
*   ***Proposed Edit:***
    *   Location: D1 → D1′; §2 rewritten as "Single-role orders and the handoff link"; §1 graph per role; diagram;
        Alternative B becomes the chosen design; old D1 moves to Alternatives with these code reasons.
    *   Change:
        *   **Order shape.** Each lab order has a fixed `role`, `profile`, `model_profile`, `experiment_id`, `driver`
            and `seq`. A later order declares the earlier order's sealed `handoff.json` as a hash-bound input with
            role `process_lab_handoff`. For REWORK, it also declares the findings record.
        *   **Intake.** Intake materializes the handoff into SWE.1 through the author gate, following the
            `provided_requirements.validate/materialize` pattern: hash check, rebuild of the artifacts from the
            package, self-check, and an authorship receipt naming the source order.
        *   **What is removed:** `attempt_plan`, `planned_attempt`, the dispatch lab branch, `plan_entry`, the seal
            chain, and the separate ID ledger file. A handoff's `id ↔ (task, key)` map is now the ledger.
        *   **Seals.** These become the existing `BL-SWE.1-nnn` baseline. Its id and hash, plus the job identity, go
            into the handoff.
        *   **Terminal verdict.** `PROCESS_LAB_SEALED` is replaced by a distinct reason code,
            `PROCESS_LAB_HANDOFF_SEALED`, on the existing BLOCKED state (it can never be READY). The design lists the
            full set of terminal reasons.

### [RC-2] Swap state machine is not runnable and conflates swap-STOP with operator STOP [`egm-design`, `egm-codebase-details`, `egm-implementation-readiness`, `egm-zoom-out`] - Severity: High
*   **Affected Scope:** §3 state machine, CUJ 2, files 14 and 27 (lines 121–126, 228–248, 611–619, 731–740).
*   **Discrepancy Description:** `stack.start` is fenced to intent RUNNING. The managed profile is pinned in the
    systemd units. The probe needs admission. The swap uses `settle_shutdown`, which BLOCKs bound orders. Intent
    writes do not use compare-and-set (CAS).
*   **Rationale:** Covers C7-B3, R9-B3, S5-M5, IR-M6, CD-M11, CD-N4 and S6-#8.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Code-confirmed (`operations.py:366-375`, `stack.py:341-364`, `services.py:100-110`). With
    D1′, a swap happens only at an empty queue, so no bound order exists to be BLOCKED.
*   ***Proposed Edit:***
    *   Location: §3, CUJ 2, files 14/27.
    *   Change: promote the procedure in `evidence/.../mtp-speed-20261030/activate.py:92-133` into a tested operator
        tool `ff/process_lab/activate.py`. The tool runs these steps, stopping on the first failure:
        1.  Refuse unless the queue holds no ACTIVE or QUEUED order for the current profile, the inference owner
            is free, and QUIESCENCE evidence exists. These are read-only checks against the named tables.
        2.  Operator STOP through `afo.cli shutdown` with `expected_epoch`.
        3.  Stop the units.
        4.  Re-render `conductor.env` and the units with the new `FORGE_OPERATIONS_PROFILE`, then `daemon-reload`.
        5.  `operations.synchronize('resume', expected_epoch=…)`.
        6.  `stack.start(settings, recovery=True)` while the Conductor unit is down. The intent and epoch are
            re-read before each step.
        7.  Check health and `model_identity`. No inference probe is used.
        8.  Start the Conductor.
        9.  Write the immutable activation record (`forge-c/model-swap/1`), with fields: from/to profile,
            timings, outcome, operator and reason `PROCESS_LAB_ROLE_BATCH`.
        *   **Failure handling:** a failed load stops the stack and records `STOPPED_FAILED_LOAD`, and the operator
            may re-activate the previous profile. An operator STOP seen at any re-read aborts with the stack
            stopped.
        *   **Shared deployment:** all lab profiles share one `deployment` block (root, ports, Fabro storage), so
            the queue database and ledgers persist across swaps.
        *   **`RESIDENT_PROFILE_MISMATCH`:** becomes a fail-closed refusal in `scheduler.preflight`, applied to lab
            orders only. Non-lab orders are unaffected.

### [RC-3] Ornith and lab jobs have no role-capability admission path [`egm-zoom-out`, `egm-implementation-readiness`, `egm-codebase-details`] - Severity: High
*   **Affected Scope:** file 19 and the runbook (lines 658–663, 746–756).
*   **Discrepancy Description:** `admit_job` requires a measured capability receipt or a `product_role_trial`.
    Without one, the job gets `CAPABILITY_LIMIT`.
*   **Rationale:** Covers R9-B4, S5-M6 and IR-B3.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** With D1′, every order has one profile and one model, which matches
    `product_role_trial.authorized` (one profile + one model per trial).
*   ***Proposed Edit:***
    *   Location: new §3a "Admission".
    *   Change: every lab order carries a `product_role_trial` binding for its (profile, model, role), signed in the
        per-experiment operator policy. The policy's `allowed_model_profiles` lists the lab profiles. The repository
        `afo-policy.yaml` stays untouched.

### [RC-4] QM purpose refuses the stepwise inspector [`egm-codebase-details`, `egm-implementation-readiness`] - Severity: High
*   **Affected Scope:** §1/§7, files 22/24/25 (lines 181, 271–275, 684–721).
*   **Discrepancy Description:** `qm.validate_profile` refuses `semantic_inspect_phases`, which is the only setting
    that selects `review_semantic`.
*   **Rationale:** Covers R9-B5 and CD-B4.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Code-confirmed (`release/qm.py:98-103`, `lrtx/runner.py:45-55`). The owner chose D7.
*   ***Proposed Edit:***
    *   Location: new file entry `ff/release/qm.py` (Modify) plus test.
    *   Change: `validate_profile` accepts `semantic_inspect_phases == ["SWE.1"]` only when the profile declares
        `process_lab: true` **and** the work order has a valid `process_lab` block. The failed-before test shows that
        an ordinary QM order with that profile, and a lab profile without a block, are still refused.

### [RC-5] Lab profiles under-specified; copying the named sources breaks the graph [`egm-implementation-readiness`, `egm-codebase-details`, `egm-zoom-out`, `egm-design`] - Severity: High
*   **Affected Scope:** files 2, 24, 25; §10a (lines 491–498, 701–721, 336–352).
*   **Discrepancy Description:** The delivery-first source has empty `phases_by_layer` plus the DEMO policy. The
    stepwise source has SWE.1–6 structured phases and `reinspect_direct`. There is no reasoning-budget flag and no
    shared deployment block. The bundled llama-server is unproven for Ornith, and `--reasoning-format deepseek` is
    hard-coded. Using a separate context key would create a second source of truth.
*   **Rationale:** Covers R9-B9, IR-B6, CD-M2, CD-M3, C7-M8, S5-M4, S5-M10, S5-N4 and CD-N8.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Code-confirmed (`stack.py:370-413`). The owner chose D6, both arms now.
*   ***Proposed Edit:***
    *   Location: files 2, 24, 25 rewritten with explicit key sets.
    *   Change:
        *   **Profiles.** Two lab profiles. `lab-ornith-q8` serves Ornith on llama-server. `lab-qwen38-q8` serves
            Qwen and carries both the author settings and the inspector settings, so arm B needs zero swaps. Each
            profile gets a full listed key set: `work_order_purpose: QM`, `process_lab: true`,
            `structured.phases_by_layer.LL: [SWE.1]`, `structured.semantic_inspect_phases: [SWE.1]`,
            `inspector_stepwise: true`, `reinspect_direct: false`, no development policy, the shared `deployment`
            block, `gateway.reasoning`, and `admission`.
        *   **Context.** Context is set only through `OLLAMA_CONTEXT_LENGTH`. The extra context key is dropped.
        *   **llama-server.** `llama_server` gains optional `reasoning_format` and `reasoning_budget` fields, with
            defaults that leave existing argv unchanged. The design pins a starting KV/context budget (32768) for
            Ornith, with a stated VRAM arithmetic check. `model_blob_sha256` is dropped. The model identity is the
            manifest digest, and the GGUF sha is recorded in the evidence only.
        *   **Binary feasibility.** Whether the bundled binary can serve Ornith is an explicit risk with a native
            pre-check in the runbook. CI reports NATIVE_NOT_RUN.

### [RC-6] Inspector outcome mapping and "actionable finding" undefined [`egm-implementation-readiness`, `egm-codebase-details`, `egm-comprehension`, `egm-style`] - Severity: High
*   **Affected Scope:** §7, files 10/18/22 (lines 271–275, 575, 651–653, 684–691).
*   **Discrepancy Description:** Verdicts are recorded per checklist item. A failed visit writes no record. There
    is no mapping from claims to SWRs, and "actionable" is not defined.
*   **Rationale:** Covers R9-B7, IR-B4, CD-M7, S6-#5, style M10 (both stages), C7-M11 (part) and S6-#14.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** The finding is valid. The mapping is a deterministic rule with one defensible form.
*   ***Proposed Edit:***
    *   Location: §7 rewritten with a mapping table; file 22.
    *   Change:
        *   **Records.** `review_semantic` in lab mode always writes `inspection-record.json`, including when the
            visit fails, and adds an `outcomes[]` list.
        *   **Per-SWR mapping:**
            *   A standing claim targeting the SWR gives FINDINGS.
            *   A checklist item that was answered validly and has no claim on the SWR gives NO_FINDING.
            *   Any INVALID, time-boxed or budget-exhausted item gives NOT_INSPECTED for every SWR that the item
                covers.
            *   Document-level claims attach to a `document` pseudo-entry and are reported, never spread across SWRs.
        *   **Actionable.** "Actionable" means at least one FINDINGS outcome. A REWORK order is queued only when the
            preceding INSPECT handoff has at least one FINDINGS outcome. An INSPECT result that is all NOT_INSPECTED
            produces no REWORK. It is recorded as an inspection gap.
        *   **`NOT_RUN`.** `NOT_RUN` is removed from the enum.

### [RC-7] Scorer allows false coverage; algorithm unspecified [`egm-design`, `egm-zoom-out`, `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`] - Severity: High
*   **Affected Scope:** G5, §9, CUJ 3, file 12 (lines 63–65, 128–133, 295–315, 589–595).
*   **Discrepancy Description:** Matching semantics, ambiguity, judgeability, ref resolution and the artifact input
    are all undefined. A requirement with a matching key but wrong behaviour counts as COVERED.
*   **Rationale:** Covers R9-B8, IR-B5, C7-M4, Z8-M1, CD-M10, S6-#6, style M8, C7-M14, S6-#15 and design N1.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** The plan already separates deterministic checks from expert review of semantics (plan lines
    152, 188–190). The `review-disposition` contract exists in `specs/014-durable-local-autonomy/contracts/`.
*   ***Proposed Edit:***
    *   Location: G5 restated; §9 rewritten.
    *   Change:
        *   **Deterministic checks.** The scorer runs these checks itself:
            *   hashes;
            *   ref resolution, where `RM0486 p.N` resolves to a page that exists in the bound section index, reusing
                `swe12.cited_pages` and `assurance.hardware.index`;
            *   ID integrity;
            *   candidate matches, where all of the oracle's `register/field/op` must equal a row in the package's
                `register_effects`, and keywords are optional hints that never decide.
        *   **Inputs.** The scorer takes the package and its artifact directory.
        *   **Coverage.** An obligation counts as COVERED only through a deterministic oracle predicate that is
            satisfied, or through a recorded owner-signed `review-disposition`. Every other obligation is
            UNKNOWN_NEEDS_HUMAN.
        *   **Judgeable.** A criterion is judgeable when it names a test method and an observable outcome. This is a
            deterministic grammar check on the `Verification:` line.
        *   **Results.** `criteria_result` = MEETS, FAILS or NEEDS_HUMAN, recorded in the score report only.
        *   **CUJ 3.** Reduced to "NOT_INSPECTED is never PASS".
        *   **Q4.** Declared blocking for the first scored result.
        *   **Workload.** The expected human adjudication volume is listed as a risk.

### [RC-8] CRC example leaks reference answers; hidden-oracle and lesson leakage [`egm-implementation-readiness`, `egm-codebase-details`, `egm-design`] - Severity: High
*   **Affected Scope:** file 26, §9 isolation, file 30 isolation test (lines 723–729, 295–301, 801–802).
*   **Discrepancy Description:** The 0014g inputs include the 0014f reviewed requirements, `idr_oracle.c`,
    `idr_target_oracle.c` and a prompt `requirement_example`. VALIDATED lessons are retrieved into author packets.
*   **Rationale:** Covers R9-B10, IR-B7, CD-M9, C7-M6, C7-M5, CD-N5 and design N4.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** These are blocking under the plan's own EGM gate ("hidden oracle leakage").
*   ***Proposed Edit:***
    *   Location: file 26 and the isolation test.
    *   Change:
        *   **Inputs.** Enumerate the exact input entries: the RM sections, the CMSIS/device header and the owner
            scope only. Explicitly drop `provided-requirements.json`, the oracle C files, `prompt_overrides`,
            `development_execution_policy` and `delivery_first`.
        *   **Holdout flag.** Set `evaluation_holdout: true` on every lab order (already honoured by
            `knowledge/context.py`, `experience.py` and `references.py`).
        *   **Isolation test.** The test forbids any input with a reference, oracle or reviewed-requirement role, and
            any lesson in lab author packets.
        *   **Wording.** "Operator-only directory" is described as a path policy plus a prompt-assembly test, not an
            OS boundary. `PATH_OUTSIDE_WORKSPACE` is removed from the structured-node test.
        *   **Experiment record.** The frozen experiment record (D8) binds the oracle hashes before the first order.
            `score` refuses an oracle whose hash is not in the record.

### [RC-9] Missing Risks & Mitigations section [`egm-structural`, `egm-design`, `egm-zoom-out`] - Severity: High
*   **Affected Scope:** whole document.
*   **Discrepancy Description:** The standard requires the section, and no consolidated failure, capacity or
    operator-load analysis exists.
*   **Rationale:** Covers C7-B4, structural F1, design M9 and Z8-M4.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Required by `feature-spec-standard.md`.
*   ***Proposed Edit:***
    *   Location: new H2 "Risks & Mitigations" after Alternatives.
    *   Change: list each risk with its mitigation:
        *   bundled-binary Ornith feasibility;
        *   48 GB VRAM and KV budget;
        *   operator presence (at most 4 swaps per corpus run in arm A, 0 in arm B);
        *   human adjudication load;
        *   a stranded queue after a failed activation;
        *   materialize-link correctness;
        *   lesson/oracle leakage;
        *   the global G3 checkpoint recompute;
        *   rework degrading correct requirements, mitigated by scoring every role's handoff and reporting
            regressions;
        *   a rough wall-time budget per driver.

## Medium

### [RC-10] Identity hash inputs not available; global effect undeclared [`egm-design`, `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`, `egm-zoom-out`] - Severity: Medium
*   **Affected Scope:** G3, G7, §4, file 1, CUJ 5.
*   **Rationale:** Covers C7-M7, IR-M5, CD-M1, style M9 and S5-N1.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** The owner chose the global fix.
*   ***Proposed Edit:***
    *   **Identity tuple.** `packet()` takes an `identity` argument built from `role_capability.IDENTITY` (role,
        model_digest, precision, reasoning, schema_mode, adapter_revision, context_tokens, sampling) plus
        `manifest.local_profile.config_sha256`.
    *   **Schema mode.** It is resolved before hashing via `schema_mode_for(model, profile)` from the manifest
        profile, not from `FORGE_LRTX_PROFILE`. `without_lessons` passes the identity through.
    *   **Digest.** The digest is the profile-pinned manifest digest.
    *   **G7.** Amended: non-lab checkpoints are recomputed once after the change. List the affected test files.
    *   **Field list.** One canonical field list, used in G3, §4 and CUJ 5.

### [RC-11] Builder delegation circular; per-role graph unspecified [`egm-zoom-out`, `egm-implementation-readiness`, `egm-codebase-details`, `egm-design`, `egm-comprehension`] - Severity: Medium
*   **Rationale:** Covers S5-M3, IR-M1, CD-M4, C7-M11 (part) and S6-#12.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Builder.** Leave `_build` unchanged, and drop `stop_after`.
    *   **Graph emission.** `process_lab.workflow(manifest)` emits a small graph using the builder helpers
        (`gate_cmd`, the `structured_authors` node forms), chosen by `manifest.process_lab.role`:
        *   AUTHOR/REWORK: `start → swe1_author → swe1_author_gate → lab_handoff → exit`. The existing bounded
            author-gate rework loop is kept. Gate exhaustion goes to exit with the reason recorded.
        *   INSPECT: `start → materialize → swe1_inspector → lab_inspect_record → lab_handoff → exit`.
    *   **Hook.** `builder.build` calls it near line 212, the same way the delivery-first hook works.
    *   **Golden test.** Drop the byte-identical golden test; G7 holds by construction.
    *   **Wording.** Correct "unconditional edge" to the `outcome=succeeded` edge.

### [RC-12] D4/D2 text drift, diagram and inspection count [`all reviewers`] - Severity: Medium
*   **Rationale:** Covers C7-M1, C7-M2, S6-#1, S6-#2, style M1–M4 (Stage 7), structural F2–F4, S5-N5 and S6-#10 (AT11).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Text and diagram.** Rewrite CUJ 1 with the operator as the batcher and swapper, and redraw the diagram for
        D1′.
    *   **D4 wording.** Restate D4: at most two INSPECT orders and two REWORK orders per driver, and the second
        REWORK's output is not inspected.
    *   **AT11.** Record that D4 supersedes the plan's "one correction" wording (plan §5.2, AT11).

### [RC-13] Corpus-decision layer, G6, primary_manual [`egm-zoom-out`, `egm-design`, `egm-structural`, `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`] - Severity: Medium
*   **Rationale:** Covers S5-M7, S5-M8, S5-M9, Z8-M2, C7-M5, C7-M10, C7-M12, C7-M13 (part), IR-M10, IR-M12, CD-M6,
    S6-#7 and structural F5.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** The owner chose D8.
*   ***Proposed Edit:***
    *   **Removed:** D5's `decide`, `process-decision/1`, files 5a/13a, the `test_process_lab_decide.py` entry, G6,
        §6 and the `primary_manual` edits.
    *   **Kept:** a Non-Goal, plus a pointer to PF-BENCH-011, PF-QUAL-013 and Q3.
    *   **Added:** `forge-c/process-lab-experiment/1`, a frozen operator-side record of oracle shas, profile shas,
        thresholds and order list. It is written before the first order and checked by `score`.
    *   **Scoring:** every role's handoff is scored, which gives initial-vs-final scoring and rework regression.

### [RC-14] Handoff schema, importer and contract fixtures [`egm-implementation-readiness`, `egm-codebase-details`, `egm-style`, `egm-zoom-out`] - Severity: Medium
*   **Rationale:** Covers IR-M7, IR-M8, CD-M8, C7-M13, S5-M12, S6-#17, style M3 and style M5 (Stage 7).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Derivation.** Define where each handoff field comes from:
        *   `source_refs` from the row's `source`;
        *   `assumption` from `source == "ASSUMPTION"`, emitted for owner-scope rows;
        *   `criterion` from `Verification:`;
        *   `trace[]` edges SWR → test id from `requirements_to_tests.csv`;
        *   `downstream_constraints` from `upstream_gaps.md` items.
    *   **Importer.** It rejects a duplicate id (checked in code, not by schema), a dangling trace edge or a hash
        mismatch. Its labels are CONSUMABLE / AMBIGUOUS / MISSING. AMBIGUOUS means an assumption or a NOT_INSPECTED
        requirement; criticality is used only when `--score` is given.
    *   **Contracts.** Runtime schemas go under `factory/contracts/` with the `afo/contracts.py`-style loader, and
        the spec copies are validated by `validate_contracts.py`. Fixtures are registered in
        `examples/manifest.json`.
    *   **Result field.** `criteria_result` lives only in the score report.

### [RC-15] Ledger key collisions [`egm-design`, `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`] - Severity: Medium
*   **Rationale:** Covers C7-M9, IR-M9, CD-M5, style M8 (Stage 9) and S5-N3.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **ID key.** IDs are keyed on the existing assembly `(task, key)`, which is schema-validated and unique within
        a group. A REWORK order reuses the input handoff's map and appends new keys. Retired IDs stay in the
        handoff's `retired[]` and are never reassigned.
    *   **Scope.** State that the lab is LL-only (`swe1.visit` refuses other layers). The non-peripheral holdout is
        out of scope.

### [RC-16] Evidence links, AT citations, DA-tick rule, glossary [`egm-structural`, `egm-style`, `egm-comprehension`, `egm-design`] - Severity: Medium
*   **Rationale:** Covers structural F6, style M10–M12 (Stage 7), C7-M15–M17, S6-#8, S6-#9, S6-#10 and design N2.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Evidence links.** Link the overnight report (`docs/reports/ASTRA-OVERNIGHT-REVIEW-20261030-31.md` on main
        @45190eb, evidence revision `dce7ad27`), the speed study
        (`evidence/014-durable-local-autonomy/ornith-reasoning-speed-20261031/`) and the calibration evidence
        (`stepwise-inspector-20261026/`).
    *   **Test IDs.** Use the design's own test IDs (LAB-T01…), each mapped to a plan AT only where the meaning is
        the same.
    *   **DA ticks.** Name the DA-tick rule: CLAUDE.md, "update checkboxes only when run evidence exists".
    *   **Glossary.** Add a short glossary: AFO, Fabro, operations intent/epoch, inference owner, QUIESCENCE
        evidence, SENT/UNKNOWN, owner window, loop10, MTP, F015, DA.

### [RC-17] Alternatives incomplete or weak [`egm-zoom-out`] - Severity: Medium
*   **Rationale:** Covers S5-M11 and Z8-N1.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Add an alternative for `lrtx/modelcmp.py`, rejected because it bypasses AFO admission,
    accounting and lifecycle. Its load-time measurement is reused. Restate Alternative I's reason the same way.

### [RC-18] Detailed-plan precision (paths, commands, digests, env) [`egm-style`, `egm-implementation-readiness`, `egm-codebase-details`] - Severity: Medium
*   **Rationale:** Covers style M1, M2, M4–M7, M11–M19 (Stage 9), IR-M13, IR-N7, CD-N6 and CD-N7.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Values.** Full digests and full profile paths.
    *   **Commands.** Name the exact commands (`python -m forge_factory.afo.cli shutdown|resume`, `stack stop`,
        `stack start`).
    *   **Environment.** `$B` = `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c` and
        `$B/venv/bin/python`.
    *   **Labels.** A single native label, `NATIVE_NOT_RUN`.
    *   **Tests.** List the reason codes, the test assertions for each case, the missing tests from IR-M13, the
        reuse of `tests/peripheral_golden.py` where a graph is pinned, and the exact `validate_spec` path.
    *   **Bookkeeping.** Item 29 becomes Modify.

## Low

### [RC-19] Structural and style nits [`egm-structural`, `egm-style`, `egm-comprehension`] - Severity: Low
*   **Rationale:** Covers structural F7, F9–F14, style Nits (Stage 7: 1–20; Stage 9: 1–17), S6-#16, S6-#19–#21,
    S5-N6 and design N3/N5/N6.
*   ***AI Suggestion:*** PROPOSE FIX for these:
    *   "Resolved decisions" becomes its own H2.
    *   Q1/Q2 are noted as resolved.
    *   Section numbering and tags.
    *   Path conventions.
    *   Wrapping and trailing whitespace.
    *   "tiny" and "stays green".
    *   "repair budget" is defined.
    *   The per-driver 90% deviation is noted.
    *   Ornith efforts are listed.
    *   Arm B warm-reload is noted as not applicable after D1′.

    DECLINE these:
    *   Heading names. They follow the EGM template, `skills/egm-draft/references/design_doc.md`.
    *   The `*Drafted with EGM*` footer. It is the EGM template's provenance marker.
    *   British/American spelling.
*   ***Justification:*** The fixed items are cheap and help a human reader. The declined items follow the EGM
    template.
*   ***Proposed Edit:*** Applied during the rewrite.

---

**Summary:** 18 clusters PROPOSE FIX (9 High, 9 Medium); 1 Low cluster mixes PROPOSE FIX and DECLINE.
CONTEST: 0. ESCALATE: 0. Q4 (oracle reviewer) and Q5 (Ornith reasoning value) stay as open owner questions.
