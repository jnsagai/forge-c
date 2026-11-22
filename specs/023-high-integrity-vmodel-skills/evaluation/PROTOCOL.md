# Evaluation protocol: forge-c-hi measurable impact (T072)

Written on 2026-11-22, **before** any evaluation run, and committed so that the targets cannot move afterwards. Results,
whatever they are, go to `../evidence/eval/` and `../evidence/impact-report.md`.

## Questions

1. **Quality (SC-006).** Does the package lower deterministic requirement-quality rule violations, compared with the same
   author model on the same inputs without the package?
2. **Defect detection (SC-005).** Does the package's inspection (independent inspector plus gates) find seeded defects in
   a requirement set?
3. **Traceability (SC-004).** Is every need covered and every requirement traced?
4. **Cost.** Wall time, model calls, and tokens where the harness reports them.

## Fixed inputs

- Needs and constraints: `packages/forge-c-hi/examples/safety-supervisor/needs/` (15 needs, 7 constraints), hashed in
  every run record.
- Stage: system requirements (`sys-req`). Profile `generic`, level HI-2.
- Reference configuration: author Claude through Claude Code (`claude -p`, the owner's account, no API key); inspector
  GPT through Codex CLI (`codex exec -s read-only`, ChatGPT login). Harness default models; the versions of both CLIs
  are recorded.

## Arms

| Arm | What runs | Output |
|---|---|---|
| `baseline` | The same author harness with a plain prompt: the needs and constraints, "write the system requirements as JSON items with id, text, sources (need ids) and verification method". No skills, no gates, no inspector. One call. | items converted into a requirement set without changing any text |
| `with_package` | The conductor (`hi-conductor`) with the package skills, gates and two-phase inspection, until the stage ends (accepted or blocked). | `hi/sys-req/requirements.json` at the end of the stage |
| `seeded` | The package inspector (item phase over all items, then set phase) and the deterministic gates on a requirement set with known injected defects; no rework. | findings and gate issues, scored against the answer key |
| `seeded_baseline` | The same inspector harness with a plain prompt: "review these requirements and list every defect with the requirement id". | the list, scored against the same answer key |

## Metrics (per run, `EvaluationRun` in `data-model.md`)

- `rule_violations_per_100`: deterministic quality-gate issues (`hi quality sys-req`) per 100 requirement items,
  counted the same way for both arms.
- `trace_coverage`: needs covered by at least one system requirement / all needs; plus dangling and orphan counts.
- `seeded_detected / seeded_total`: a seeded defect counts as detected when a finding or gate issue names the same
  target item (or `SET` for set-level defects) with a checklist item in the same class as the answer key (IQ-xx or
  SQ-xx; a gate issue code maps to its IQ class). Findings on other items are counted separately as non-seeded
  findings and are not scored as false positives, because the base set is not guaranteed defect-free.
- `gate_verdicts`, `wall_time_s`, `model_calls`, `tokens` (when reported; otherwise `null`, never estimated).

## Targets (stated in advance)

- **SC-006:** `rule_violations_per_100(with_package)` ≤ 50 % of `rule_violations_per_100(baseline)`.
- **SC-005:** `seeded_detected / seeded_total` ≥ 80 % for the `seeded` arm, with at least 20 seeded defects.
- **SC-004:** `trace_coverage` = 100 % in every package marked READY_FOR_OFFLINE_REVIEW.

If a target is missed, the report says so and keeps the number.

## Seeded corpus (T071)

- Built from a copy of the demo's system requirements after the `with_package` run, so the defects sit in realistic text.
- At least 20 defects across classes: ambiguity (IQ-03), incompleteness (IQ-04), non-atomic (IQ-05), unverifiable
  (IQ-06), wrong value against the need (IQ-02), inconsistency between two items (IQ-09), design detail (IQ-08), missing
  source or wrong source (IQ-12), a need left uncovered (SQ-01), a missing fault reaction (SQ-02), contradictory pair
  (SQ-05).
- The answer key (`evaluation/seeded/answer-key.json`) lists item id, class and a one-line description. It is never in
  the inspector's working directory and never in a prompt.

## Limits stated up front

- Small sample: one input set, few runs per arm, harness default models; model behaviour varies between runs.
- The deterministic rules measure form, not engineering correctness; the inspector's judgement is not ground truth.
- The baseline prompt is deliberately plain; a carefully engineered prompt without the package would narrow the gap.
- No certification claim: the numbers describe the package's checks, not the safety of any product.
