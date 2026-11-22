# T041 run 1: Safety Supervisor, system requirements: BLOCKED (stopped)

- **Date:** 2026-11-22, 17:27–19:35 UTC. Run id `r20261122T172709Z-6763ed`.
- **Configuration:** generic profile, HI-2. Author: Claude through Claude Code (`claude -p`, owner account, no API key).
  Inspector: GPT through Codex CLI (`codex exec -s read-only`, ChatGPT login). Package as committed in `9c6529cf`.
- **Inputs:** `needs/stakeholder-needs.md` (15 needs) and `needs/constraints.md` (7 constraints) only.

## What happened

| Step | Result |
|---|---|
| Author, create (4.2 min) | 39 system requirements and 13 open points (3 blocking); every gate PASS at the first attempt |
| Item inspection round 1 | 37 findings on 25 items (26 blocking, 11 major); 43 % IQ-06 unverifiable, 27 % IQ-02 not source-faithful |
| Rework round 1 | 25 items reworked one at a time; no out-of-scope write, no change to another item had to be discarded |
| Item inspection round 2 | 46 findings on all 43 re-judged items (39 blocking); 34 of them IQ-06, 31 of those naming an open point as the reason |
| Rework round 2 | stopped by the operator after 28 of 43 items (19:35 UTC) |

Totals: 57 completed model calls (1 create, 1 gate fix, 2 item inspections, 53 item reworks) plus one interrupted
rework; about 120 minutes of author time and 7.5 minutes of inspector time. Gates and scope stayed clean throughout.

## Why it was stopped, and what changed

The stakeholder needs deliberately leave values open. The author did not invent them: it wrote open points. The
inspector then judged, correctly, that requirements depending on those open points cannot be verified (IQ-06). Rework
cannot supply a human decision, so each round the author split items and added open points (13 → 69, 59 blocking) and
the inspector flagged them again. The outcome (BLOCKED on open points) was already certain, so the run was stopped to
save model time.

Fix (commit `16fc7f8f`): a finding may name the open point it waits on (`blocked_by`). Such findings are not sent to
rework; they stay carried until the open point is answered, and the open point blocks the stage. The author skills
now reuse open points instead of adding duplicates.

## Result

`hi/sys-req/` here is the workproduct, gate results and inspection rounds at the time of the stop. The stage outcome
is **BLOCKED**: blocking open points remain and need product-owner decisions. Those decisions are recorded for the
fictional demo product in `examples/safety-supervisor/needs/product-decisions.md`, used by run 2.
