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

Feature 011's best earlier learning-set trial (m9, reasoning on, `evidence/v0.4/runs/F011-T045/README.md`)
for comparison:

- S1-EFFECT: 0/7
- S1-OMIT: 1/7 on target
- S1-NOBUDGET: 2/7
- 6/7 clean baselines passed

Learning-11 caught every one of these on target. The remaining miss in learning-11 (the IWDG-HAL rc4 clean
baseline) is addressed in `caa2d3e`; learning-12 measures that revision.

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

1. **Unit tests** inside the stack environment.
2. **Truthful preflight** (`seeded --preflight`). Every clean baseline is inspected with scripted truthful
   answers and zero model calls. If any is rejected, the script exits 2 and Qwen is never called.
3. **The measured run.** It stops itself (exit 3) after 3 inspections that record nothing.

Before each deploy the same preflight runs locally on loop10 over all seven holdouts. Recorded model answers of
a failing evaluation are replayed through the new code (`q014-replay.py`). The preflight caught 5 defects before
inference. The unit-test gate caught the SWE.4 unit build having no compiler outside the stack environment.
