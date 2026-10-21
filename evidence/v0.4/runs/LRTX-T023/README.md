# LRTX-T023 — smaller model per task vs qwen3-coder:30b (structured SWE.1 authors)

Run: 2026-10-21 17:57–19:00 UTC, factory c660da0 (run worktree `forge-c-run-t023`), inside the profile namespace.
- Command: `python -m forge_factory.lrtx.modelcmp --workspace <start> --model qwen3:8b --model qwen3-coder:30b --repeat 3`.
- Record: `20261021T175714.json` (evidence_run PASS). It is marked dirty only because the record directory itself was
  untracked in the run worktree.
- Start workspace: the IWDG LL lrtx10 workspace, copied. Each attempt removed its SWE.1 authorship from the copy.
  - The start was never written; its tree hash is unchanged after the run (`start-workspace.tree.sha256`).
- Both models matched their profile digests: qwen3-coder:30b `06c1097efce0…`, qwen3:8b `500a1f067a9f…`.
- A first attempt (`20261021T172654.*`, FAIL exit 124) was cut off by evidence_run's 1800 s default after one repeat
  per model.
  - Its partial report is kept as `modelcmp-report-cutoff-20261021T172654.json`, with the same outcome: 8b FAILED,
    30b FROZEN.

## Result (MEASURED, `modelcmp-report.json`)

| | qwen3:8b | qwen3-coder:30b |
|---|---|---|
| SWE.1 visits passing / frozen by the unchanged author gate | 0/3 / 0/3 | 3/3 / 3/3 |
| Calls per visit (median, retries included) | 23 | 13 |
| Visit wall time (median) | 764 s | 484 s |
| Model load (median, observed by the gateway) | 16.0 s | 58.1 s |

Per task:
- **qwen3:8b:**
  - Valid after repair on all five register tasks.
  - Never valid on the cross-cutting task (0/3): its verification criteria had no pass criterion. The validator's
    localized repair did not fix this within the call budget.
  - It also used more tokens per task than the 30B model (e.g. IWDG_PR median 13,970 vs 7,011) because it needed
    more repairs.
- **qwen3-coder:30b:** valid on every task in every attempt. Valid at the first call only once (IWDG_SR_2), so the
  localized repair is part of its normal path.
- Per-task call wall time was similar for both models; the 8B model does not answer faster on this hardware once
  repairs are counted.

## Mixed routing (DERIVED from the per-task medians, not measured)

The 8B model would take the five register tasks and the 30B model the cross-cutting task, with one model switch.
- Estimated call wall time: 575 s, including the 58 s switch.
- 30B alone: 541 s.

Mixed routing saves nothing on this work order. The model switch costs more than the 8B model gains.

## Decision record

- No routing to qwen3:8b is proposed. qwen3-coder:30b stays the only author model of the profile.
- Inspector qualification is not part of this comparison and remains a separate decision (LRTX-FR-016). Both models
  stay NOT_QUALIFIED as inspectors.
- This is pilot evidence on one work order and one phase (3 repeats per model), not a model qualification.

## Owner decision (2026-10-21)

The owner chose coder-only authoring ("ok, coder only"):
- qwen3-coder:30b is the only author model of the profile.
- qwen3:8b stays listed in the profile as measured, but is not used or routed to.
- The inspector decision waits for the T021 seeded evaluation and the QM experiment (example 0009q-iwdg-ll-qm).
