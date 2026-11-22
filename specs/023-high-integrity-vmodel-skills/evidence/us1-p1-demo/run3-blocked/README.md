# T041 run 3: Safety Supervisor, system requirements: BLOCKED (Sonnet / Terra)

- **Date:** 2026-11-22, 22:29–22:43 UTC. Run id `r20261122T222917Z-83d787`.
- **Configuration:** generic profile, HI-2. Author: Claude Sonnet (`claude -p --model sonnet`, owner account, reported
  as `claude-sonnet-5-5`). Inspector: GPT-6.1 Terra (`codex exec -s read-only -m gpt-6.1-terra`, ChatGPT login).
  Package at `3962d29f` (with the fixes found by runs 2 and 3-error).
- **Inputs:** stakeholder needs, constraints and the demo product-owner decisions (as run 2).

## What happened

| Step | Result |
|---|---|
| Author, create | gates failed once, fixed by one gate-fix call |
| Item inspection, rounds 1–3 | 18 → 10 → 1 findings; 18 single-item reworks; one more gate fix |
| Set inspection, rounds 1–4 | 15 → 16 → 14 → 14 findings; 3 set reworks; set rework limit reached |
| Final gates | validate, quality, trace, scope, independence all **PASS** |

Totals: 31 model calls (24 author, 7 inspector); 9.6 min of author time, 4.5 min of inspector time; 14 min wall clock.

## Outcome

**BLOCKED**, with 52 system requirements and 12 open points (6 blocking). 14 findings remain: 9 wait on an open
point; 5 do not, and each of those concerns a value the inputs leave open (the values of `<state>`, what GET FAULTS
returns with fewer than 8 reports, a service request for the reset cause, the reaction to fault code 8, report
ordering in a latched state). The author had recorded four of them as **non-blocking** open points
(OP-SYS-004, -005, -007, -011); the inspector judged them blocking. The skills do not yet tell author and inspector
how to decide between "needs a product decision" and "a later stage can settle it".

## Comparison with run 2 (same inputs, same package logic)

| | Run 2: Opus 5.5 / GPT-6.2-Sol | Run 3: Sonnet / GPT-6.1 Terra |
|---|---|---|
| System requirements | 90 | 52 |
| Open points (blocking) | 47 (42) | 12 (6) |
| Findings at the end | 63 distinct, 59 waiting on an open point | 14, 9 waiting on an open point |
| Model calls | 68 | 31 |
| Model time | 153 min | 14 min |
| Deterministic rule violations | 0 | 0 |
| Trace coverage | 100 % | 100 % |

Run 2's trace FAIL came from the set-rework defect fixed in `5e6958c9`; it is not a model difference.
