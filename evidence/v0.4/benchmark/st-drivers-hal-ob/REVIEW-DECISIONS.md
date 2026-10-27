# Owner decisions and remaining verification

The owner accepted all four current BLOCKED handovers as offline review evidence with every finding open:
[OD-2026-10-27-01](../../../easa/owner-decisions/OD-2026-10-27-01-blocked-onboarding-handovers.json).
The record binds the exact GPIO, SPI, USART and TIM archive hashes. This does not approve the drivers, safety or a
merge, and it changes no native package or gate status.

The owner also accepted the specific unused legacy GPIO description exception:
[OD-2026-10-27-02](../../../easa/owner-decisions/OD-2026-10-27-02-sc001-history-exception.json).
The strict literal SC-001 evidence remains FAIL. The exception is bound to the exact peripheral-profile diff and the
original raw and active-input audit hashes; additional changes are not covered. `OB-OWNER-REVIEW` checks both owner
records and the actual sealed archives. OB-T059/T060 and F015-T065 are marked through evidence checks.

The original [review brief](OWNER-REVIEW.md) and [combined record](record.md) remain unchanged as the reviewed snapshot.
Per-defect dispositions, requirement adequacy, TIM's unverified coverage-tool cause and all software/safety findings
remain open. The current four packages remain BLOCKED with 709 / 310 / 711 / 230 named gaps respectively.

Source `4f4442ba` adds measured author-cycle counts for interrupted runs and retains every declared model limit.
Its focused MCP/model check has 60 passed and 1 skipped; its data-volume sandbox/model check has 42 passed. The clean full suite on that exact source finished with **1,452 passed, 27 skipped and the same three known
baseline failures** (2,422.042 seconds). The raw result remains FAIL; `OB-NO-REGRESSIONS` independently passes the exact
failure-set comparison. The USART model-gate CLI also passes using the signed 64 MHz clock assumption. The preceding `b68bdbb` full suite is preserved as FAIL:
1,445 passed, 27 skipped, three baseline failures and two corrected test assumptions (catalog count and mount
ancestor existence). No result was relabeled.

Revised runtime candidate `4aac5aca561aa4f1d4603fcaa09760bf05282822` matches the `4f4442ba` snapshot outside evidence
and preserves the deployed evidence tree. CRE `pd-35e5ddd7ce46a2941d3c` is eligible for offline review, frozen in oracle
`22f1d80c`; six applicable gates pass and the FIX reproducer gate is not applicable to this CHANGE. It is not deployed.
Production remains on `9dd5b71`.

SC-007 / OB-T043 remains NOT_RUN because the approved Claude inspector is out of quota. No held-out authoring model
call or substitute inspection was started. Text-author roles remain open as allowed by the handoff. OB-T064 delivery checks pass and the PR is updated; held-out SC-007 remains separately open under OB-T043. The PR stays draft; no merge is authorized.
