# Feature 014 known issues

Owner decision 2026-10-26: "95/100 is good enough!!! Lets not forget to have a factory that is not perfect, but can evolve over time and report the known issues to be solved by a Human." Owner decision 2026-10-26 on the 17 tasks that need live evidence: "Known issues only".

This register lists what the factory cannot do yet or does imperfectly, with its evidence and the human decision or fix it needs. Machine-readable copy: [known-issues.json](known-issues.json).

| Id | Area | Issue | Status | Human action |
|---|---|---|---|---|
| KI-014-001 | protocol | Five diagnosis protocol trials not run: no qualified alternative local model | ACCEPTED_BY_OWNER | Decide whether a second local model is qualified (stepwise) for diagnosis, or accept single-model diagnosis. Owner 2026-10-26: 95/100 accepted. |
| KI-014-002 | accounting | Token usage UNKNOWN for 23 of 95 protocol trials | OPEN | Decide whether exact usage is required (adapter change) or the conservative UNKNOWN handling is acceptable. |
| KI-014-003 | inspector | Stepwise inspector: clean held-out baselines still falsely rejected | OPEN | Test set 2 is now spent (it may become learning set 4). Release another frozen batch of current-factory baselines (e.g. after the TIM review or new Feature 015 drivers) so a refreshed held-out set can measure further fixes. |
| KI-014-004 | ladder | Escalation ladder: CAPA retrieval rung not integrated | RESOLVED | None needed to decide; implementation pending. |
| KI-014-005 | regression | Two inherited test failures | RESOLVED | None: both were hermetic-harness artifacts, fixed in 1e2fd46 (test-only); DA-T029 ticked at 20650af. |
| KI-014-006 | runtime | No usable parallel model serving for the inspector | OPEN | Decide whether parallel serving is worth a separate qualification (another runtime or model), or keep one slot. |
| KI-014-007 | gates | Omniverse2 unit gate skips the review tests | OPEN | Decide whether the pinned engine and owner inputs may be placed on Omniverse2 (private data). |
| KI-014-008 | evidence | Record copier misses some evaluation records | OPEN | None needed to decide; harness change pending (write records next to the result). |
| KI-014-009 | offline loop | Signed dispositions and patch bundles not exercised live | OPEN | Owner: add the two allowed-signers lines and sign one disposition and one patch. |
| KI-014-010 | promotion | Independent CRE rejects promotion of the branch | OPEN | Owner review of PR #42 (draft); merge only after acceptance. |
| KI-014-011 | qualification | Long live campaigns not run | OPEN | Schedule dedicated Omniverse2 GPU windows for the campaigns. |
| KI-014-012 | live evidence | DA-T004: Complete serialized prompts and packet partitioning not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 3 trials below/at/above the allowance with the manifests retained. |
| KI-014-013 | live evidence | DA-T005: Semantic proposal negatives produced by Qwen itself not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: ~4 trials forcing absent hypothesis, wrong type, overlong field. |
| KI-014-014 | live evidence | DA-T007: Registered vs transmitted schema and the MCP tool path not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: One schema-capture trial per boundary (MCP and constrained mode). |
| KI-014-015 | live evidence | DA-T010: Separate request/tool/token/correction counters not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 2 tool-using trials up to the completion reserve. |
| KI-014-016 | live evidence | DA-T012: Concurrent admission, late usage and overshoot not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 3 trials: concurrent admission near exhaustion, cancel with late usage. |
| KI-014-017 | live evidence | DA-T013: Liveness after cancel failure/timeout, restart and late adoption not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 2 trials (cancel-ack with restart to quiescence; lost-ack with revocation before adoption). |
| KI-014-018 | live evidence | DA-T018: Status/scorecard dimensions with timestamps and a privacy scan not captured live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: Snapshots and a privacy scan during any live run. |
| KI-014-019 | live evidence | DA-T019: Obligation-scoped repair context not exercised on a real repair | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 1 product repair (reg32 mask) with independent oracle before/after. |
| KI-014-020 | live evidence | DA-T021: Independent author/inspector regression on a real repair not run | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: The DA-T019 product run plus seeded critical cases and tamper attempts. |
| KI-014-021 | live evidence | DA-T031: Per-role capability profile recorded only for diagnosis (INCOMPLETE) | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: The 5 qualified-local-alternative trials (KI-014-001) and one changed-identity trial. |
| KI-014-022 | live evidence | DA-T032: Short-horizon decomposition not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 1 product case with ~3 obligations and the three injections. |
| KI-014-023 | live evidence | DA-T033: Evidence-indexed memory and checkpoints only partly shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: A resume-from-checkpoint trial with injected stale memory. |
| KI-014-024 | live evidence | DA-T034: Sequential candidate selection and stall stop not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: A bounded 3-candidate search inside a product repair. |
| KI-014-025 | live evidence | DA-T035: Inspector qualification lacks author pairing and metamorphic/reference checks | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: A paired author/inspector run on a refreshed held-out set. |
| KI-014-026 | live evidence | DA-T036: Capability-limit disposition only partly shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 1 oversized trial ending in CAPABILITY_LIMIT or repartition. |
| KI-014-027 | live evidence | DA-T040: Native lesson retrieval before a job not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: Job A then job B with seeded lessons, plus one inspector job. |
| KI-014-028 | live evidence | DA-T041: Independent lesson candidate qualification not shown live | ACCEPTED_BY_OWNER | Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 1 curation run over candidates from the committed campaign rows. |
| KI-014-029 | local-author | Three ST LL pilots BLOCKED at SWE.1; required outputs missing | OPEN | Review author/output failures before a bounded retry; inspector freeze remains. |

## KI-014-001: Five diagnosis protocol trials not run: no qualified alternative local model

- **What:** The 20x5 protocol ran 95/100 trials (95 correct, 0 failures). The 5 'qualified-local-alternative' trials need a second, independently qualified local diagnosis model; none exists on Omniverse2 (qwen3.8:27b failed the single-response diagnosis; it was not tried stepwise).
- **Impact:** If the only qualified diagnosis model fails or is withdrawn, there is no qualified local fallback; recovery then closes BLOCKED for a human.
- **Evidence:** evidence/v0.4/runs/DA014-protocol-95/latest.json; evidence/014-durable-local-autonomy/omniverse2-preliminary-20261025/audit-5dc2df3.json
- **Human action:** Decide whether a second local model is qualified (stepwise) for diagnosis, or accept single-model diagnosis. Owner 2026-10-26: 95/100 accepted.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-002: Token usage UNKNOWN for 23 of 95 protocol trials

- **What:** The native path did not report usage for 23 trials; the ledger keeps them as UNKNOWN (never as zero).
- **Impact:** Mission budgets for those requests are reconciled conservatively; cost per trial is not exact.
- **Evidence:** evidence/014-durable-local-autonomy/omniverse2-preliminary-20261025/audit-5dc2df3.json (usage_unknown)
- **Human action:** Decide whether exact usage is required (adapter change) or the conservative UNKNOWN handling is acceptable.
- **Status:** OPEN

## KI-014-003: Stepwise inspector: clean held-out baselines still falsely rejected

- **What:** Re-measured 2026-10-27 at 9300475 after learning sets 1-3 passed live (49/49, 63/63, 14/14): on the refreshed held-out test set 2 (Feature 015 GPIOA and CRC, registered 48207f1), 3 identical runs: 12/12 seeded defects flagged (11 on target, 1 off target, 0 missed), but 2/2 clean baselines falsely rejected, so the seeded-case detections partly ride on baseline noise (10/12 add a finding code their clean baseline lacks). GPIOA: a model error on the effects step (the BSRR toggle write answered 'not_stated'). CRC: rule gaps the truthful preflight already shows (CRC_CR.REV_IN/RTYPE_IN/REV_OUT/RTYPE_OUT and CRC_DR.DR writes not matched to their requirements; the Budgets gap row not recognised). Earlier subset calibration (285d21e): 49/54 caught, 5/9 clean baselines rejected. Learning set 4 (the spent pair, rules e0c020d) then reached 13/14 with both clean baselines accepted (job 040, learning data only); development is frozen by the owner until >= 4 new frozen held-out baselines exist.
- **Impact:** On unseen drivers the advisory inspector registers false gaps for the end-of-run human review (advisory mode: it does not block). Detection carries over; clean-baseline acceptance does not yet.
- **Evidence:** evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md; evidence/014-durable-local-autonomy/stepwise-inspector-20261026/calibration-t2-runs.json; evidence/v0.4/runs/DA014-calibration-t2/latest.json
- **Human action:** Test set 2 is now spent (it may become learning set 4). Release another frozen batch of current-factory baselines (e.g. after the TIM review or new Feature 015 drivers) so a refreshed held-out set can measure further fixes.
- **Status:** OPEN

## KI-014-004: Escalation ladder: CAPA retrieval rung not integrated

- **What:** Every gap's attempt record lists rework, progress extension, validated lessons, diagnosis repair (AFO) and stall detection. CAPA retrieval is not a rung yet. Resolved 2026-10-26 (5f6d540): capa_retrieval rung records the linked CAPAs.
- **Impact:** A gap may be registered although an open CAPA already describes its cause; the reviewer must check the CAPA registry.
- **Evidence:** factory/python/forge_factory/inspection/gate.py (_ladder); specs/014-durable-local-autonomy/tasks.md DA-T054
- **Human action:** None needed to decide; implementation pending.
- **Status:** RESOLVED

## KI-014-005: Two inherited test failures

- **What:** test_cre_d7_final::test_readiness_is_recomputable_evidence_based_and_never_a_safety_claim and test_sim_renode::test_renode_found_from_mcp_server_environment fail identically on the base f6ff873. Resolved 2026-10-27: both failed only under run_full_inherited.py's private empty FORGE_STATE_DIR (test-isolation artifacts, not factory defects); fixed in 1e2fd46; whole suite at 20650af: 0 failures.
- **Impact:** The whole inherited suite is not green; the two failures predate Feature 014.
- **Evidence:** specs/014-durable-local-autonomy/validation.md (2026-10-26 regression table); evidence/v0.4/runs/DA014-regression/latest.json
- **Human action:** None: both were hermetic-harness artifacts, fixed in 1e2fd46 (test-only); DA-T029 ticked at 20650af.
- **Status:** RESOLVED

## KI-014-006: No usable parallel model serving for the inspector

- **What:** Ollama 0.34.0 serves qwen35moe with one request slot. The experimental llama.cpp profile (-ls) serves 2 slots but gives the prefill-bound inspector ~0 speed-up, changes answers (1 learning-set result broke) and crashed twice right after stack start (cause unknown).
- **Impact:** Inspector throughput stays one request at a time on Omniverse2.
- **Evidence:** evidence/014-durable-local-autonomy/parallel-serving-20261026/README.md
- **Human action:** Decide whether parallel serving is worth a separate qualification (another runtime or model), or keep one slot.
- **Status:** OPEN

## KI-014-007: Omniverse2 unit gate skips the review tests

- **What:** 40 of 46 review/seeded tests skip on Omniverse2 (no pinned SafeC engine or owner inputs there). Compensated: calibration requires a loop10 run of the same revision with none skipped.
- **Impact:** A remote-only change could pass the remote gate untested.
- **Evidence:** evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md (gate defects)
- **Human action:** Decide whether the pinned engine and owner inputs may be placed on Omniverse2 (private data).
- **Status:** OPEN

## KI-014-008: Record copier misses some evaluation records

- **What:** The periodic copier of the seeded harness keeps inspection records for about 40 of 49 evaluations; the rest are lost when the harness deletes its scratch.
- **Impact:** Replay-based development and audits cannot see every evaluation.
- **Evidence:** evidence/014-durable-local-autonomy/parallel-serving-20261026/README.md
- **Human action:** None needed to decide; harness change pending (write records next to the result).
- **Status:** OPEN

## KI-014-009: Signed dispositions and patch bundles not exercised live

- **What:** Export, owner-signed dispositions and the signed patch-import gate pass their deterministic tests. A live round trip needs the owner's allowed-signers lines for namespaces forge-review-disposition and forge-patch-bundle and the owner's own signatures.
- **Impact:** The offline improvement loop is implemented but unproven end to end.
- **Evidence:** evidence/v0.4/runs/DA014-US11/latest.json; specs/014-durable-local-autonomy/contracts/README.md
- **Human action:** Owner: add the two allowed-signers lines and sign one disposition and one patch.
- **Status:** OPEN

## KI-014-010: Independent CRE rejects promotion of the branch

- **What:** Independent CRE evaluates the Feature 014 range as REJECTED / PROTECTED_PATH_CHANGE (the branch changes evidence and specification paths). No gate is waived.
- **Impact:** No automatic promotion; merging needs the owner's review.
- **Evidence:** evidence/014-durable-local-autonomy/cre/independent-evaluation.json
- **Human action:** Owner review of PR #42 (draft); merge only after acceptance.
- **Status:** OPEN

## KI-014-011: Long live campaigns not run

- **What:** Real RCC recovery, the 30-product benchmark, chronological learning benefit and the 24/72/168-hour operation campaigns are implemented with fixtures but NOT_RUN.
- **Impact:** Production readiness, product success, learning benefit and availability are unproven.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv
- **Human action:** Schedule dedicated Omniverse2 GPU windows for the campaigns.
- **Status:** OPEN

## KI-014-012: DA-T004: Complete serialized prompts and packet partitioning not shown live

- **What:** No live serialized-input manifest, admission receipt or partition/coverage manifest; every live case had one obligation.
- **Impact:** DA-T004 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 3 trials below/at/above the allowance with the manifests retained.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-013: DA-T005: Semantic proposal negatives produced by Qwen itself not shown live

- **What:** The live campaign separated PROPOSE_REPAIR/NEEDS_EVIDENCE/CLOSE_BLOCKED; its negatives were injected after the answer, and correction counts were not recorded.
- **Impact:** DA-T005 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: ~4 trials forcing absent hypothesis, wrong type, overlong field.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-014: DA-T007: Registered vs transmitted schema and the MCP tool path not shown live

- **What:** The closed-branch wire schema fix is recorded; no schema hash capture, and no live trial used MCP tools.
- **Impact:** DA-T007 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: One schema-capture trial per boundary (MCP and constrained mode).
- **Status:** ACCEPTED_BY_OWNER

## KI-014-015: DA-T010: Separate request/tool/token/correction counters not shown live

- **What:** Live trials used no tools; no reserve-boundary or exhaustion trial.
- **Impact:** DA-T010 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 2 tool-using trials up to the completion reserve.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-016: DA-T012: Concurrent admission, late usage and overshoot not shown live

- **What:** Request counts and UNKNOWN usage are recorded (KI-014-002); no concurrent admission near exhaustion, late usage, overshoot or input/cached/output split.
- **Impact:** DA-T012 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 3 trials: concurrent admission near exhaustion, cancel with late usage.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-017: DA-T013: Liveness after cancel failure/timeout, restart and late adoption not shown live

- **What:** Live cancel-ack and lost-ack rows exist; no quiescence after a supervisor restart, no revocation before adoption, no cancel failure or timeout.
- **Impact:** DA-T013 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 2 trials (cancel-ack with restart to quiescence; lost-ack with revocation before adoption).
- **Status:** ACCEPTED_BY_OWNER

## KI-014-018: DA-T018: Status/scorecard dimensions with timestamps and a privacy scan not captured live

- **What:** No live status or scorecard snapshot and no privacy scan.
- **Impact:** DA-T018 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: Snapshots and a privacy scan during any live run.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-019: DA-T019: Obligation-scoped repair context not exercised on a real repair

- **What:** The live mission made no product attempt; plans were accepted but never implemented.
- **Impact:** DA-T019 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 1 product repair (reg32 mask) with independent oracle before/after.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-020: DA-T021: Independent author/inspector regression on a real repair not run

- **What:** No live repair path, no author tampering attempt; inspector calibration missed 1/54 seeded defects.
- **Impact:** DA-T021 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: The DA-T019 product run plus seeded critical cases and tamper attempts.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-021: DA-T031: Per-role capability profile recorded only for diagnosis (INCOMPLETE)

- **What:** capability-5dc2df3.json pins the identity but status INCOMPLETE, record() refused; no invalidation receipt.
- **Impact:** DA-T031 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: The 5 qualified-local-alternative trials (KI-014-001) and one changed-identity trial.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-022: DA-T032: Short-horizon decomposition not shown live

- **What:** All live cases had one obligation; no injected omission/interface/global-constraint faults.
- **Impact:** DA-T032 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 1 product case with ~3 obligations and the three injections.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-023: DA-T033: Evidence-indexed memory and checkpoints only partly shown live

- **What:** Stale/missing primary evidence handled 5/5; no checkpoint resume, stale lesson or effective-context trial.
- **Impact:** DA-T033 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: A resume-from-checkpoint trial with injected stale memory.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-024: DA-T034: Sequential candidate selection and stall stop not shown live

- **What:** Reworded strategy rejected 5/5; no multi-candidate search, verifier ranking or stall stop.
- **Impact:** DA-T034 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: A bounded 3-candidate search inside a product repair.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-025: DA-T035: Inspector qualification lacks author pairing and metamorphic/reference checks

- **What:** Learning sets pass; held-out calibration showed false alarms (KI-014-003); no paired author, metamorphic or reference manifests.
- **Impact:** DA-T035 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: A paired author/inspector run on a refreshed held-out set.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-026: DA-T036: Capability-limit disposition only partly shown live

- **What:** Unqualified alternative refused 5/5, CLOSE_BLOCKED and NEEDS_EVIDENCE correct; no typed CAPABILITY_LIMIT or repartition trial; qualified-alternative branch blocked (KI-014-001).
- **Impact:** DA-T036 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 1 oversized trial ending in CAPABILITY_LIMIT or repartition.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-027: DA-T040: Native lesson retrieval before a job not shown live

- **What:** Both delivery paths and APPLICATION recording are tested deterministically; no live job used a lesson.
- **Impact:** DA-T040 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: Job A then job B with seeded lessons, plus one inspector job.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-028: DA-T041: Independent lesson candidate qualification not shown live

- **What:** No live candidate curation.
- **Impact:** DA-T041 stays unticked; its behaviour is verified only by deterministic fixtures.
- **Evidence:** specs/014-durable-local-autonomy/implementation-status.csv; evidence mapping 2026-10-26 (validation.md)
- **Human action:** Owner 2026-10-26 'Known issues only': implemented and fixture-tested; no live work planned. Close with: 1 curation run over candidates from the committed campaign rows.
- **Status:** ACCEPTED_BY_OWNER

## KI-014-029: Three new ST LL pilots fail before release prerequisites

- **What:** Job 050 ran WWDG, RNG and LPTIM1 at clean `9a88fbc`: 0/3 READY, all BLOCKED at SWE.1 with 59 gaps. Repeated deterministic rejection includes absent register effects and traceability outputs.
- **Impact:** Full local ST LL authoring remains unproven; the pending owner safety signatures do not repair these earlier failures. Runtime-locality/package-sealing checks passed, which does not establish product correctness.
- **Evidence:** [ST3 pilot results](st3-driver-runs/summary.json).
- **Human action:** Review author/output failures and scoped remediation before a new bounded pilot. Inspector development remains frozen; no retry or owner signature was performed during collection.
- **Status:** OPEN

KI-014-029 triage: [recorded diagnostic codes](st3-driver-runs/author-diagnostics.json)
identify unsupported register-I/O semantics and some invalid model proposals. The
assembler refuses incomplete/invalid task results; missing files do not establish
an empty model response. No gate/domain rule was relaxed and no retry was run.

KI-014-029 follow-up: the owner-requested [bounded remote diagnosis](st3-diagnosis-study/README.md)
made three Qwen calls. Two responses passed reference checks; the third cited an
invented check ID. The independent pinned engine still rejects the selected WWDG
and RNG suggestions (unsupported access/RMW). One isolated LPTIM read passes,
which does not satisfy the original clearing requirement. This narrows the next
engineering work to source-grounded semantic-profile changes and correct intent
mapping; it is not a repaired driver, autonomous recovery or qualified lesson.


## KI-014-030: Full host-audit coverage is unavailable

- **What:** At clean fbd8bc8, finite user-bus visibility passes with both exact harmless probe/reply pairs. System-bus BecomeMonitor and boundary visibility are denied (native fallback diagnostics retained as byte counts only); kernel audit status remains unavailable. Software continuous/rotation accounting, authenticated-control/actor correlation and full intervention replay are still incomplete.
- **Impact:** Unexpected interventions remain UNKNOWN. User-bus visibility alone cannot qualify a host or make an operational campaign PASS.
- **Evidence:** evidence/014-durable-local-autonomy/host-bus-fbd8bc8/summary.json
- **Human action:** Host administrator must provide approved kernel-audit and system-bus visibility plus the reboot/mount-loss fixture window. Continue independent source integration and tests; do not bypass permissions or deploy persistent source.
- **Status:** OPEN
