# Feature 006 assurance case summary (generated)

Generated 2026-10-19T05:00:44.057527Z at `0f7a97839990`.

This is bounded engineering evidence for offline human review. It is not an ISO 26262 or Automotive SPICE conformance statement, not an ASIL approval and not a safety sign-off.

## Readiness

- Implementation: PARTIAL; configured mode: PILOT (profile ENHANCED).
- Normative method catalog: RECONCILED (47 entries reconciled table by table against the owner-registered ISO 26262-6:2018 copy by the named human reviewer).
- Technical gates end to end: DEMONSTRATED; product yield: 0.0.
- Safety approval: none (outside the factory).

## Blocking items

- MODE:HUMAN_AUTHORIZATION_MISSING
- MODE:VALIDATED_PILOT_MISSING
- E2E:NO_READY_PACKAGE (42 finished pilot runs, 0 READY_FOR_OFFLINE_REVIEW)

## Top-level claims

| Claim | Status | Evidence / counterevidence |
|---|---|---|
| EASA-T069 | FAIL | status FAIL exit 1 |
| EASA-T079 | PARTIAL | LL r122/r125 and HAL r124/r136 pass AT-094 (six matrices, nothing uncovered). Scope ASIL B: packages stay BLOCKED until the human-written ASIL safety evidence exists, so no READY package; HAL r136 also escalated DEF-005 (Renode RCC_CR reset value vs RM) for an owner decision. |

## Stated limitations

- Renode is a behavioural model, not HIL; no physical target; RCC_CR reset value differs from the RM
- Formal checks (CBMC, Eva) cover runtime errors and bounded termination only, with registers as memory
- Author and inspector share one model and provider: independence PARTIAL
- False-positive rate on unseen packages NOT_MEASURED; the seeded corpus was designed by the implementer

## Task and requirement status

Tasks: FAIL 1, PASS 71. FRs: COVERED 69, PARTIAL 3, BLOCKED 0, OPEN 0. Details: `docs/assurance/EASA-STATUS.md`.
