# ADR-CRE-005: Statistical sampling, SPC thresholds and data-quality policy

Status: accepted (2026-10-16) · Tasks: CRE-T030..T034

* **Units.** The unit of production is the driver order (003 KPI-T003): retries of `<order>-rN` are attempts of
  the same order. First-pass measures use the first immutable inspection/run of the order; retries never add
  numerator or denominator (AT-027).
* **Cohorts/strata.** A cohort key is `(driver class, target MCU, compiler profile, model id, workflow mode)`
  (workflow mode: full run from SWE.1 vs resumed run). Pooling across different keys is refused unless a declared
  normalization exists (AT-031). Cloud-model benchmark runs and local-model runs are different strata.
* **Intervals.** Binomial rates carry a Wilson score interval at the policy confidence (default 95%) with n shown.
  Zero failures in n trials: upper bound by the exact one-sided bound ≈ 3/n (rule of three); never "100%" (AT-028).
  Runs of the same order or the same day are correlated; intervals assume independence and say so in `assumptions`.
* **SPC** is measurement-only: p-chart limits and EWMA (λ from policy) need a frozen calibration window of at least
  `min_samples_for_descriptive_charts` comparable samples; otherwise `INSUFFICIENT_BASELINE`. Signals are diagnostic
  events (`cre.spc_signal`), never gate changes or repair triggers (AT-029, AT-033).
* **Reliability growth** (Duane/AMSAA) is off by policy; enabling it requires exposure data and goodness-of-fit.
* **Data status** of every value: `MEASURED`, `ESTIMATED`, `UNKNOWN`, `NOT_APPLICABLE`, `NOT_COMPUTABLE`,
  `INSUFFICIENT_BASELINE`. Missing telemetry is never zero or success (INV-07).

## Contract extension (2026-10-16)
`reliability-measurement.schema.json` admitted only `CRE-R01..R08` and `K01..K20`. Two attempt-level diagnostics the
owner asked for need unique names: **CRE-R09** attempt completion (all SWE.1–SWE.6 inspection gates PASS, "successful
workflow yield" per cohort) and **CRE-R10-<phase>** attempt-level station first pass (K01 stays the order-level FPY).
The `metric_id` pattern was widened additively to `CRE-R01..R19` with an optional qualifier suffix (e.g. `CRE-R04-p50`);
every previously valid id stays valid. K-ids are used only for values copied verbatim from the 003 snapshot
(cohort `kpi-003-reused`), never for recomputed or redefined values.
