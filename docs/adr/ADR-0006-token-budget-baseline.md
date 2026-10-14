# ADR-0006 — Token budget accounting basis and measured re-baseline

- **Status:** Accepted · **Tasks:** T041, T042 · **FR:** FR-029, FR-030
- **Evidence:** Fabro `/runs/{id}/usage` for runs `01M4Y6H7K5Z5A96RAV8CKBV5A4` (r5) and `01M4Y7JE8KA3G7970BVB7CET4C` (r7)

## Context
`agents.yaml` budgets (4.2 k–12 k per stage) were proposed before any measurement. Measured on qwen3:8b via
Fabro 0.362, an SWE.1 author visit processes ≈17 k *new* tokens (27 222 uncached input + 6 713 output over two
visits) while re-reading ≈115 k cached prompt tokens per visit (an agent tool loop re-sends the conversation each
call). The governor (correctly) cancelled r7 at the proposed budget.

## Decision
1. Accounting basis = **uncached input + output** per node, summed across visits, provider-reported only
   (`basis: reported`); `cache_read` is reported separately and never hidden. Unknown usage stays UNKNOWN.
2. Per-visit budgets are re-baselined from measurement: **authors 32 000, all other roles 16 000**; per-node run cap
   = budget × 4 visits. `max_turns` (20) is unchanged and still enforced per visit by the policy hook.
3. These are cost-governance limits, not safety controls; exhaustion still yields `TOKEN_BUDGET_EXHAUSTED`, a
   cancelled run and a BLOCKED package — never a waived inspection or a false PASS.
4. Re-tune only from recorded KPI K15 data (tokens per READY package, per-stage usage).
