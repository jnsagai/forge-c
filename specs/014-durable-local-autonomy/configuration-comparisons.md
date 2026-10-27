# Controlled comparisons (DA-T028)

The report command consumes recorded evidence; it never creates work, admits
inference, changes gates, selects a model or depends on RCC success.

```sh
python -m forge_factory.afo.configuration_comparison --plan PLAN.json \
  --baseline BASELINE_BUNDLE.json --candidate CANDIDATE_BUNDLE.json --out REPORT.json
```

Omit unavailable bundles to produce explicit `NOT_RUN` (exit 2). A partial or
unaudited cohort produces `INCOMPLETE` (exit 2). `MEASURED` means comparable evidence
exists, not that the candidate passed qualification or should be deployed. A quality
regression produces `REJECT_QUALITY_REGRESSION` in the report. No report auto-selects
or deploys anything.

The immutable plan uses `forge-c/configuration-comparison-plan/1`, with
`comparison_factor` from existing `qualification.COMPARISON_FACTORS`, exact
`baseline_identity`/`candidate_identity`, `registered_at` epoch, frozen ordered
`case_ids`, and six hash-bound `controls`: `prompts`, `oracles`, `workload`,
`admission`, `measurement`, `quality_gates`. Each control is a bounded regular file.
Only one declared identity factor may change; the role cannot change. The controls
must be inputs of both real qualification manifests. The candidate manifest must
also freeze the plan reference before execution. The unchanged measured baseline
may predate registration; candidate measurements cannot.

Each bundle contains the existing campaign `manifest_ref`, ordered `result_refs`
and, for the candidate, `plan_ref`. References use `{path, sha256}`. The report
supports the existing protocol/targeted and product benchmark cohorts. It compares
runtime revision, stage and actual frozen case definitions as well as IDs. Identity
comes from the actual campaign manifests. Missing, repeated or foreign cases cannot
change the denominator. Native runs must be on Omniverse/Omniverse2; synthetic test
fixtures are not published as live qualification.

Outcomes/costs come from the existing `qualification_capture.independent_audit`
producer and its original oracle artifacts, under its existing protected audit root.
A model's verdict or agreement is not an independent audit. The audit observation
`comparison_measurement` supplies factual `useful_plan`, `false_acceptance`,
`false_rejection`, `critical_defect_missed`, `accepted_work_order` booleans,
`closed_defect_ids`, `started_at`, and an `effective_settings_ref` included in its original `oracle_refs` (observed
`identity` and corresponding `native_run_id`, not merely planned settings), and costs `input_tokens`, `output_tokens`,
`learning_tokens`, `wall_seconds`, `learning_wall_seconds`. Tokens must reconcile
with the original result's `reported_tokens`. The producer must account for *all*
attempts and extraction, qualification, retrieval and failed learning candidates in
`includes_all_attempts_and_learning`; absent coverage stays unknown. These fields
extend the audit observation, not lesson or inspector governance.

Every measured failed/blocked outcome contributes cost. Total tokens/time per
accepted work order include all these costs; a zero accepted denominator yields
null. Missing or unaudited rows make full cost totals null while retaining the known
subset. Reports separate product success, learning benefit and operational availability.
Existing records without frozen common controls or independent cost/outcome sources
are historical observations, not retroactively qualifying comparisons.

Live DA-AT-028 remains NOT_RUN until an unchanged measured baseline, separately
bounded authorized candidate, actual effective settings, complete costs and
independent audits are available. The reporting implementation alone cannot tick it.
