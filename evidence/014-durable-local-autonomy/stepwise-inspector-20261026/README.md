# Stepwise local SWE.1 inspector — learning-set runs (Omniverse2, 2026-10-26)

Owner decision 2026-10-26: "Stepwise inspector in 014". The inspector is split into small, closed,
temperature-0 questions with deterministic assembly. This is the approach that took local diagnosis from 0 to
95/95. Answers become typed claims, and the existing adjudicator decides them, so the model still decides every
claim and no gate is added. The inspector is measured with Feature 011's seeded-defect harness
(`forge_factory.lrtx.seeded`, catalogue `lrtx-seeded-2`) on Feature 011's **learning set**: 7 holdout work
orders, each with a clean baseline and 6 seeded SWE.1 defects, giving 49 evaluations.

**Preliminary. This is not inspector qualification.** Feature 011's rule applies: the frozen test set
(F011-T046) is spent only on a candidate that already passes the learning set. No task is ticked from these
runs (owner 2026-10-26: "Keep unticked").

Model `qwen3.6:35b-a3b`, profile `local-rtx-v2-omniverse2-q36-noreason` (reasoning off), temperature 0,
seed 1. The runtime is an isolated plain local stack (`/mnt/data/forge-c/inspector-014-b309039`) with no AFO
authority and no durable autonomy.

## Results ([learning-runs.json](learning-runs.json): every row, no findings text)

| Run | Source | Evaluations | Correct | Note |
|---|---|---|---|---|
| learning-1 | 8d410f7 | 49 | 20 | first stepwise run; 13 inspections recorded nothing |
| learning-2…9 | 199bf43…9aadfe8 | 4–32 each | — | stopped by the operator as soon as a defect was fixed |
| learning-10 | 2e1af36 | 49 | **46** | 41/42 seeded defects; 5/7 clean baselines pass |
| learning-11 | 8064062 | 49 | **48** | **42/42 seeded defects** (34 on target, 8 by the gate); 6/7 clean baselines pass |
| learning-12 | caa2d3e | 6 | — | stopped: a closed self-check of citations withdrew a true S1-OMIT detection (removed) |
| learning-13 | 964a8e3 | 49 | **48** | IWDG-HAL clean baseline passes; IWDG-HAL S1-OMIT missed ('leaving the already started watchdog') |
| learning-14 | 285d21e | 49 | **49** | **first complete learning-set pass: 42/42 seeded defects, 7/7 clean baselines, 0 empty inspections** |

Feature 011's best earlier learning-set trial (m9, reasoning on, `evidence/v0.4/runs/F011-T045/README.md`)
for comparison:

- S1-EFFECT: 0/7
- S1-OMIT: 1/7 on target
- S1-NOBUDGET: 2/7
- 6/7 clean baselines passed

Learning-14 (`285d21e`) is the first run with every evaluation correct, so it meets Feature 011's precondition for the
frozen test set. The test set is measured as **calibration** (owner decision "Advisory + calibrate"): 3 runs,
recorded as a result and never used to tune the inspector before all runs are done.

## Calibration scope (owner ruling 2026-10-26: "Both: subset now, refresh later")

Calibration-1 ran all 22 F011-T046 test baselines. Its truthful preflight showed that **13 of the 22 are rejected by
today's deterministic SWE.1 author gate** (`STARTUP_INVARIANT_ON_HOST_TEST`: a startup requirement verified by a host
unit test). Under the current factory they are not clean baselines, so calibration-1's detections are gate-inflated.
It is recorded, not used as the inspector measurement.

- **Now:** calibrate on the 9 baselines the current gate freezes. They were selected by the gate alone (truthful
  preflight, zero model calls) and registered with tree hashes in
  [calibration-subset.json](calibration-subset.json) (commit `1067d40`) before measurement. Two of the 9 (`b009`,
  `h005`) are already rejected by an inspection rule under truthful answers. That is an expected result, not fixed
  from test data.
- **Later:** freeze a larger, refreshed held-out set from current-factory baselines (recorded seed), including
  Feature 015 drivers.

## Gate defects found while preparing calibration (2026-10-26)

1. **The test-set integrity check did not run in calibration-1.** A comment placed mid-line in the ops script
   swallowed the verifier's arguments. The verifier failed with `IndexError`, and the redirect-only next line
   "succeeded", so the log says `test set verified:` with nothing after it. The subset script runs the verifier with its
   arguments, requires the `"status": "UNCHANGED"` line, and also checks each subset tree against its registered hash.
   A local dry run on loop10 returned UNCHANGED for all 22 trees and for the subset.
2. **The remote unit gate ran only 6 of 46 tests.** On Omniverse2, all 40 tests in `test_lrtx_v2_review.py` skip
   because the pinned SafeC engine and owner inputs (git-ignored) are not on that host. The learning runs' remote
   gate had the same limit. On loop10 the same 46 tests at exactly `285d21e` give **46 passed, 0 skipped**. The subset
   script refuses to start without that loop10 record for the deployed revision, and it logs the remote skip count.
   For earlier learning revisions, no loop10 record of a non-skipping run is kept, so for those runs the remote unit
   gate counts as partial.

## What changed between runs

Each change was driven by one measured failure. Each has a regression test (`tests/test_lrtx_v2_review.py`,
`tests/test_lrtx_seeded.py`).

- **Closed answer sets.**
  - Coverage fields come from the sources' own REGISTER.FIELD names or REGISTER.*.
  - `evidence_checked` lists only the provided sources.
  - Effect answers include `set_then_clear`.
- **Scope coverage.**
  - Behaviours come from the scope sentence alone, with the requirements hidden.
  - Each behaviour gets one closed question.
  - Citations are checked against the verb the requirement imposes ("shall …", including and/then).
  - Purpose words and documented values tell writes on one field apart, with one closed check when only a
    synonym differs.
  - Non-register sentences are not asked.
- **Startup.** One question per field, where startup is stated per field.
- **Adjudication rules.** Each refutes only what the baseline contradicts:
  - ambiguities quoted from Open points or the gaps table;
  - recorded upstream inputs (labels with explanations, PENDING/NOT_PROVIDED objections);
  - count bounds;
  - ranged and parameterised writes.
- **One closed TRUE/FALSE check per standing judgement no rule decides.** FALSE keeps the claim in the record as
  WITHDRAWN.
- **Harness fixes.**
  - On-target scoring reads every item's findings: the capped 200-character summary line hid detections, so
    Feature 011's earlier counts may be undercounted the same way.
  - The ADJUDICATED_PASS note crash is fixed.

## Deterministic gates before any inference (owner request)

`q014-inspector-run.sh` runs these steps in order:

1. **Unit tests** inside the stack environment (on Omniverse2 the review tests skip; see gate defect 2).
2. **Truthful preflight** (`seeded --preflight`). Every clean baseline is inspected with scripted truthful
   answers and zero model calls. If any is rejected, the script exits 2 and Qwen is never called.
3. **The measured run.** It stops itself (exit 3) after 3 inspections that record nothing.

Before each deploy the same preflight runs locally on loop10 over all seven holdouts. Recorded model answers of
a failing evaluation are replayed through the new code (`q014-replay.py`). The preflight caught 5 defects before
inference. The unit-test gate caught the SWE.4 unit build having no compiler outside the stack environment.
