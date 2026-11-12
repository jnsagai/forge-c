# Feature 012 validation

Final runtime source: `7a1a797b70fdf971cefa8a000e50f3fc12137b13`.
The subsequent evidence commit changes reports and documentation only.

## Acceptance

The final targeted run passed all 64 cases: 45 in `test_brownfield_resume.py`,
10 local-profile cases and 9 suspended-provider/ACP regression cases. The run
used the final source files before their commit; `BR-ACCEPTANCE/latest.json`
records their hashes and the matching source commit.

The resume cases cover terminal receipts, identity/input/tool mismatches, accepted
prefix selection, delivery isolation, FROZEN and FIX_ALLOWED preservation, source
immutability, atomic sibling budgets, lost ledgers, deadline guards, CLI/API/AFO,
offline provenance and inherited independence. Accepted assurance observations
are retained; stale and later-phase records are excluded.

Fabro receipts and inspector verdicts are fixtures. These deterministic tests
exercise native baseline hashes, gates and injection without model calls. They
do not demonstrate live model qualification or an actual remote resume.

Changed-file Ruff checks, 14 static design checks, 16 legacy demo tests and
7 reference-packager tests also passed during validation.

## Broader regression and baseline comparison

The full factory run completed with **1294 passed, 5 failed and 28 skipped**.
It began on `3fb73dc`; narrow source corrections landed while it was running, so
this report is not a full-suite certification of the final source revision.
The command excluded `test_cre_d0_baseline.py`, disabled external pytest plugin
autoload and unset live Fabro/systemd/browser opt-ins.

Two failures exposed a provider/profile refusal-order regression. Commit
`50968b1` restored validation before input parsing. Both tests passed when rerun
and are included in the final 64-case acceptance run.

Three failures remain and reproduce on unchanged baseline `8713c7f`:

- `test_latest_local_qwen_work_order_has_real_terminal_evidence`: the latest local
  attempt has zero CRE observations.
- `test_kpi_t012_observer_mcp_read_only_and_least_privilege`: a local observer/KPI
  evidence assertion fails.
- `test_kpi_t020_pilot_reconciles_with_raw_evidence`: local raw evidence counts
  four pilot records where the assertion expects one.

The five-test rerun on corrected source had two passes and those same three
failures. Baseline and corrected-source JUnit reports are retained beside the
acceptance report in `evidence/v0.4/runs/BR-ACCEPTANCE/`.
`regression-results.json` records report hashes, counts and failing test names;
the full broad report remains in the operator's operations directory.
Historical observations and KPI expectations were not rewritten to make this
feature's tests pass.

## Independent CRE review

The full feature through `50968b1` was evaluated against baseline `8713c7f`:
decision `pd-fe023baf7b0143c3830a` is **ELIGIBLE_FOR_OFFLINE_REVIEW**.
Commit `0cbe5a8` then recorded evidence without changing runtime source.

The final assurance-observation carry fix, `7a1a797`, was evaluated incrementally
against `0cbe5a8`: decision `pd-8e4ddfb61bded2afc156` is also
**ELIGIBLE_FOR_OFFLINE_REVIEW**. Protected-file, policy, prevention, quality,
golden benchmark and holdout gates passed; all 72 frozen reproducers reported
SYMPTOM_ABSENT. Model-token use was zero. Both decision records are retained in
`evidence/cre/decisions/`. Neither decision authorizes automatic deployment.

## Review handoff and operating boundary

Draft review: <https://github.com/jnsagai/forge-c/pull/40>, stacked on
`feat/011-omniverse2`. No merge or live deployment was performed. The monitored
remote work order remains on its pinned checkout. No competing GPU test or model
evaluation was started for this change.

Version 1 requires an identical clean factory/runtime identity and the durable
lineage ledger. Pre-feature work orders, including the currently pinned remote
attempt, must start fresh rather than bypass that validation.
