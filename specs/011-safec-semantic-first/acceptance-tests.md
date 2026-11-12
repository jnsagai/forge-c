# Acceptance tests — Feature 011

**Status:** authored only; no tests executed yet. PASS requires real command/test evidence on pinned revisions. Tests prefixed F011-AT; synthetic harness PASS is not live-local model qualification.

## M0 — Preservation, baseline and trust

| ID | Test and expected result |
|---|---|
| F011-AT-001 | Compare old default, ACP and local-v1 workflow/provider fixtures on same inputs: byte/semantic equivalence, no v2 side effect. |
| F011-AT-002 | Verify base/head revisions, deployed state and 208 historical archives (when host available): no write or deletion. Missing host evidence = NOT_RUN. |
| F011-AT-003 | Force network-denied execution with SafeC pinned; no remote provider, leaked token, open external socket or cloud fallback. |
| F011-AT-004 | Present SafeC wrong SHA, wrong binary digest, wrong schema, missing executable, wrong repository revision: REFUSED/STALE, never PASS. |
| F011-AT-005 | Feed private-source excerpt/credential to public-summary collector: sanitize/refuse and do not persist secret. |

## M1 — Bridge contract / status normalization

| ID | Test and expected result |
|---|---|
| F011-AT-006 | Canonical request/response roundtrip with exact expected id, input digest, policy, binary, source and artifact digests. |
| F011-AT-007 | Malformed JSON, repeated keys, unknown fields, missing required property, duplicate findings, oversized output or invalid UTF-8: ERROR. |
| F011-AT-008 | Timeout, cancellation, crash, nonzero tool exit with forged PASS, missing evidence file or malformed hash: not accepted. |
| F011-AT-009 | Return unsupported operation, incomplete proof, stale contract or insufficient source: UNSUPPORTED/INCONCLUSIVE/STALE with explicit blocker. |
| F011-AT-010 | Repeat identical request with same frozen inputs: byte-stable semantic result; changed source or tool hash invalidates cache and old evidence. |

## M2 — Register semantic domain

| ID | Test and expected result |
|---|---|
| F011-AT-011 | Validated 1-bit field at bit 5: logical 1 fits width, mask/encoded bits 0x20, no logical-value substitution; boundary widths tested. |
| F011-AT-012 | Nonzero/oversized field write, negative where unsigned, unknown register/field/alias or invented page: FAIL with exact source-linked finding. |
| F011-AT-013 | RO field write, reserved bits, W1C/RC/WO semantics without dedicated model, unsafe read-modify-write: FAIL or UNSUPPORTED, no guessing. |
| F011-AT-014 | IWDG start key vs refresh key, prescaler/reload and write-only KEY plus status flags: correct source-backed operations and negative mutants. |
| F011-AT-015 | RCC ADC12EN width/mask and a mismatched reset/clock or out-of-scope field: exact expected rejection on target. |
| F011-AT-016 | Conflicting operations, cross-task field duplicates, unsupported side effect and contradictory startup invariant: preserve conflicts, no synthesized success. |

## M3 — Author and inspection

| ID | Test and expected result |
|---|---|
| F011-AT-017 | Generate deterministic numbered EARS, effects, verification mapping, scope coverage inventory, hashes and source trace from typed contracts; no author-invented register facts. |
| F011-AT-018 | Repair one known invalid intention: unchanged valid tasks retain checkpoint; same invalid result twice -> STUCK with reason. |
| F011-AT-019 | Inspector request contains frozen baseline and independent source, not author chat/hidden hiddenholdout outcomes; missing required criterion cannot yield PASS. |
| F011-AT-020 | Replay the 2 clean T021 READY holdouts: 0 known false rejection; PENDING allocation treated according to recorded owner policy, neither approved nor fabricated blocker. |
| F011-AT-021 | Replay 7 inspection-relevant seeded defects: each required critical defect identified **on target** or configuration NOT_QUALIFIED; tally off-target/missed separately. Include new unseen holdouts. |
| F011-AT-022 | Reword previously refuted invalid finding with synonyms: stable claim identity/contestation and no repeated incorrect rework. True independent defect still blocks. |
| F011-AT-023 | Remove mandatory ASIL B evidence or set QM without approved rationale: existing EASA gate still BLOCKED. |

## M4 — SWE.2 through SWE.6

| ID | Test and expected result |
|---|---|
| F011-AT-024 | Frozen IWDG requirement `LL_IWDG_IsEnabled`: generated SWE.2 exact interface name, allocation and trace. `IsActive` drift rejected and actionable. |
| F011-AT-025 | Execute 3 fresh IWDG-LL and 3 RCC-LL SWE.1 independent author+inspection visits using real selected local models; preserve exact result evidence. |
| F011-AT-026 | On genuine SWE.1 accepted holdouts, 3 fresh SWE.2 author+inspection attempts per pilot: measure PASS/FAIL/NOT_RUN honestly. |
| F011-AT-027 | Candidate code mutation (inverted key, omitted register write, unauthorized RO write) is caught by applicable source-derived oracle/static/contract checks. |
| F011-AT-028 | Vacuous independent test/incorrect expected value is rejected by seeded mutation suite; implementation is never the source of test expectation. |
| F011-AT-029 | Verify CBMC/Frama-C/Kind 2 tool identities, supported semantics, proof bounds, limits and QEMU/Renode isolation; lack of valid capability produces explicit NOT_RUN/UNSUPPORTED. |

## M5 — Runtime/quality qualification and rollback

| ID | Test and expected result |
|---|---|
| F011-AT-030 | Compare chosen local inspector/model versus Qwen benchmark on exact host: model digest, RAM/VRAM, cold model load, context, retries, time, energy; reject unmeasured routing. |
| F011-AT-031 | Check rework progress-extension bug in isolated shared-path PR: same 3+2 bound, identical STUCK behavior, no loosened gate or changed ACP trace; no silent incorporation into this feature. |
| F011-AT-032 | After upstream gates, run frozen new 30-case campaign (10 RCC-LL, 10 IWDG-LL, 5 each HAL) without lookahead/benchmark contamination. Report >=27/30 goal or NOT_PASS with limits. |
| F011-AT-033 | Stop/restart host-local services and run rollback drill: v2-only state changed, ACP/v1 and archived products preserved, no auto-promotion. |
| F011-AT-034 | Final package includes exact trace, unresolved assumptions, compliance non-claims and baseline-versus-v2 cost per accepted workorder. No READY if any mandatory unresolved status. |
| F011-AT-035 | A lesson with an injection, a gate-weakening statement, a driver-specific identifier or no recorded source is QUARANTINED; a validated lesson reaches the packet as reference data with provenance; the same input always selects the same lessons (packet hash stable). |
| F011-AT-036 | Promote a lesson only when its source false rejection is removed and every paired must-still-detect defect is still detected on target; a lesson that hides a paired defect is refused by CRE. |
| F011-AT-037 | The frozen test set (clean baselines + seeded mutations) is selected by a recorded seed and hashed before any local inspection; no lesson cites a test-set case; a test-set hash change voids the measurement. |
| F011-AT-038 | Repeated runs (>=3 per case) on the frozen test set: report false rejections and on-target detection per run and the worst run; QUALIFIED only with 0 false rejections and all paired defects on target in every run. |

## Qualification order

`AT-001..010` -> `AT-011..016` -> `AT-017..023` -> `AT-024..031` -> `AT-032..034`. No advance into an expensive 30-case campaign if the inspector is still NOT_QUALIFIED. Do not manipulate goldens or evaluation data to pass. A failed test requires the original failure evidence, specific repair and a fresh result.
