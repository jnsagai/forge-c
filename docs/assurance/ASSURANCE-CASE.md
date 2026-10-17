# Feature 006 assurance case summary (generated)

Generated 2026-10-17T19:18:04.729294Z at `bf27061397a3`.

This is bounded engineering evidence for offline human review. It is not an ISO 26262 or Automotive SPICE conformance statement, not an ASIL approval and not a safety sign-off.

## Readiness

- Implementation: PARTIAL; configured mode: OBSERVE_ONLY (profile ENHANCED).
- Normative method catalog: UNVERIFIED (47-entry secondary working index; no licensed ISO 26262-6:2018 copy registered).
- Technical gates end to end: NOT_DEMONSTRATED; product yield: 0.0.
- Safety approval: none (outside the factory).

## Blocking items

- MODE:HUMAN_AUTHORIZATION_MISSING
- MODE:VALIDATED_PILOT_MISSING
- MODE:ENFORCING_REQUIRES_PILOT_FIRST
- POLICY:FILE_ABSENT (built-in example policy, OBSERVE_ONLY)
- CATALOG:UNVERIFIED (no licensed ISO 26262-6:2018 source, no competent-reviewer reconciliation)
- E2E:NO_READY_PACKAGE (12 finished pilot runs, 0 READY_FOR_OFFLINE_REVIEW)

## Top-level claims

| Claim | Status | Evidence / counterevidence |
|---|---|---|
| EASA-T069 | BLOCKED | Owner-authorized PILOT not granted: EASA stays OBSERVE_ONLY as the kickoff requires (policy.request_mode needs a human authorization record). Real end-to-end LL pilots r108-r120 are recorded; none reached READY_FOR_OFFLINE_REVIEW. |
| EASA-T072 | NOT_RUN | - |
| EASA-T079 | NOT_RUN | - |

## Stated limitations

- Renode is a behavioural model, not HIL; no physical target; RCC_CR reset value differs from the RM
- Formal checks (CBMC, Eva) cover runtime errors and bounded termination only, with registers as memory
- Author and inspector share one model and provider: independence PARTIAL
- False-positive rate on unseen packages NOT_MEASURED; the seeded corpus was designed by the implementer

## Task and requirement status

Tasks: BLOCKED 1, NOT_RUN 1, PASS 70. FRs: COVERED 66, PARTIAL 6, BLOCKED 0, OPEN 0. Details: `docs/assurance/EASA-STATUS.md`.
