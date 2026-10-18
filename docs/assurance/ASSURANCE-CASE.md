# Feature 006 assurance case summary (generated)

Generated 2026-10-18T09:44:36.105749Z at `036dcad96b18`.

This is bounded engineering evidence for offline human review. It is not an ISO 26262 or Automotive SPICE conformance statement, not an ASIL approval and not a safety sign-off.

## Readiness

- Implementation: PARTIAL; configured mode: PILOT (profile ENHANCED).
- Normative method catalog: RECONCILED (47 entries reconciled table by table against the owner-registered ISO 26262-6:2018 copy by the named human reviewer).
- Technical gates end to end: DEMONSTRATED; product yield: 0.0.
- Safety approval: none (outside the factory).

## Blocking items

- MODE:HUMAN_AUTHORIZATION_MISSING
- MODE:VALIDATED_PILOT_MISSING
- E2E:NO_READY_PACKAGE (21 finished pilot runs, 0 READY_FOR_OFFLINE_REVIEW)

## Top-level claims

| Claim | Status | Evidence / counterevidence |
|---|---|---|
| EASA-T069 | PARTIAL | Owner-authorized PILOT active since 2026-10-18 (policy sha approved and PILOT transition ACCEPTED, Jefferson Nascimento). LL r125 (ASIL B scope) passes SWE.1-SWE.6 with all six matrices; its package is BLOCKED on the ASIL B safety evidence (HSI, allocation review, safety analysis, tool assessment) and READY is not claimed. HAL PILOT r126/r127 (SWE.4) and r128 (SWE.3) BLOCKED by agent quality (failing unit tests, design render errors); pilot false-positive/false-negative rates are not yet measured. |
| EASA-T079 | PARTIAL | LL r122/r125 and HAL r124 pass AT-094 (six matrices, nothing uncovered). Product scope decided ASIL (B): packages stay BLOCKED until the human-written ASIL safety evidence exists, so no READY package. |

## Stated limitations

- Renode is a behavioural model, not HIL; no physical target; RCC_CR reset value differs from the RM
- Formal checks (CBMC, Eva) cover runtime errors and bounded termination only, with registers as memory
- Author and inspector share one model and provider: independence PARTIAL
- False-positive rate on unseen packages NOT_MEASURED; the seeded corpus was designed by the implementer

## Task and requirement status

Tasks: PARTIAL 1, PASS 71. FRs: COVERED 69, PARTIAL 3, BLOCKED 0, OPEN 0. Details: `docs/assurance/EASA-STATUS.md`.
