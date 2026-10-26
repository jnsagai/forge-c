# Feature 014 known issues

Owner decision 2026-10-26: "95/100 is good enough!!! Lets not forget to have a factory that is not perfect, but can evolve over time and report the known issues to be solved by a Human."

This register lists what the factory cannot do yet or does imperfectly, with its evidence and the human decision or fix it needs. Machine-readable copy: [known-issues.json](known-issues.json).

| Id | Area | Issue | Status | Human action |
|---|---|---|---|---|
| KI-014-001 | protocol | Five diagnosis protocol trials not run: no qualified alternative local model | ACCEPTED_BY_OWNER | Decide whether a second local model is qualified (stepwise) for diagnosis, or accept single-model diagnosis. Owner 2026-10-26: 95/100 accepted. |
| KI-014-002 | accounting | Token usage UNKNOWN for 23 of 95 protocol trials | OPEN | Decide whether exact usage is required (adapter change) or the conservative UNKNOWN handling is acceptable. |
| KI-014-003 | inspector | Stepwise inspector: held-out false-alarm rate not yet re-measured | OPEN | Release a frozen Feature 015 batch and decide its learning/test split (recorded seed) so the refreshed held-out set can measure the fixes. |
| KI-014-004 | ladder | Escalation ladder: CAPA retrieval rung not integrated | RESOLVED (5f6d540) | None needed to decide; implementation pending. |
| KI-014-005 | regression | Two inherited test failures | OPEN | Decide: fix in their own feature, or record a waiver. |
| KI-014-006 | runtime | No usable parallel model serving for the inspector | OPEN | Decide whether parallel serving is worth a separate qualification (another runtime or model), or keep one slot. |
| KI-014-007 | gates | Omniverse2 unit gate skips the review tests | OPEN | Decide whether the pinned engine and owner inputs may be placed on Omniverse2 (private data). |
| KI-014-008 | evidence | Record copier misses some evaluation records | OPEN | None needed to decide; harness change pending (write records next to the result). |
| KI-014-009 | offline loop | Signed dispositions and patch bundles not exercised live | OPEN | Owner: add the two allowed-signers lines and sign one disposition and one patch. |
| KI-014-010 | promotion | Independent CRE rejects promotion of the branch | OPEN | Owner review of PR #42 (draft); merge only after acceptance. |
| KI-014-011 | qualification | Long live campaigns not run | OPEN | Schedule dedicated Omniverse2 GPU windows for the campaigns. |

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

## KI-014-003: Stepwise inspector: held-out false-alarm rate not yet re-measured

- **What:** Calibration on the 9 registered held-out baselines (3 identical runs): 49/54 seeded defects caught, 5/9 clean baselines falsely rejected. Fixes were then developed on that spent subset as learning set 2 (L2 live: 59/63 after round 1; round 2 running). Their held-out effect is unmeasured.
- **Impact:** In real runs the advisory inspector may still register false gaps for the end-of-run human review (advisory mode: it does not block).
- **Evidence:** evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md; evidence/014-durable-local-autonomy/stepwise-inspector-20261026/calibration-runs.json
- **Human action:** Release a frozen Feature 015 batch and decide its learning/test split (recorded seed) so the refreshed held-out set can measure the fixes.
- **Status:** OPEN

## KI-014-004: Escalation ladder: CAPA retrieval rung not integrated

- **What:** Every gap's attempt record lists rework, progress extension, validated lessons, diagnosis repair (AFO) and stall detection. CAPA retrieval is not a rung yet.
- **Impact:** A gap may be registered although an open CAPA already describes its cause; the reviewer must check the CAPA registry.
- **Evidence:** factory/python/forge_factory/inspection/gate.py (_ladder); specs/014-durable-local-autonomy/tasks.md DA-T054
- **Human action:** None.
- **Status:** RESOLVED 2026-10-26 (5f6d540): the capa_retrieval rung records the linked CAPAs.

## KI-014-005: Two inherited test failures

- **What:** test_cre_d7_final::test_readiness_is_recomputable_evidence_based_and_never_a_safety_claim and test_sim_renode::test_renode_found_from_mcp_server_environment fail identically on the base f6ff873.
- **Impact:** The whole inherited suite is not green; the two failures predate Feature 014.
- **Evidence:** specs/014-durable-local-autonomy/validation.md (2026-10-26 regression table)
- **Human action:** Decide: fix in their own feature, or record a waiver.
- **Status:** OPEN

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
