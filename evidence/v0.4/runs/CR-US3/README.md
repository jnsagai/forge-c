# CR-US3 evidence: quality and losses (feature 007)

Recorded 2026-10-19.

- **Tests.** `test_controlroom_spc_pareto.py` (8 tests) covers:
  - p-chart variable limits and I-MR limits checked against the formulas, with the lower limit clipped at 0;
  - Western Electric rules WE1, WE2 and WE3;
  - INSUFFICIENT_DATA below the minimum sample, with no limits drawn;
  - loss-code normalisation (category + code, or the tool or output named; instance details dropped);
  - Pareto order, cumulative share and evidence refs, where minor inspection findings are not losses;
  - first-pass subgroups per local day and time to pass from the previous station's pass.
- **Live, port 8766, 30 days, real state.**
  - The quality endpoint answers in 0.2 s.
  - Time to pass has control limits at every station; SWE.4 shows 7 rule violations.
  - First-pass yield is INSUFFICIENT_DATA: there are enough runs (for example n = 63 at SWE.4), but only 5
    days of history against the 10-subgroup minimum. That is reported, not hidden.
  - The SWE.4 Pareto leads with REQUIRED_TOOL_NOT_PASS:run_unit (32), MISSING_REQUIRED_OUTPUT:
    unit_verification_report.md (26), then inspection findings SWE4-02 and SWE4-06 (22 each).
  - The CAPA list, read-only from the CRE store, shows CAPA-046..050 as EFFECTIVENESS_OBSERVING.
- **Screenshot:** `cr-1440.png` (the full page, 1440 × 2200).
