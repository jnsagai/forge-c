# Qwen reasoning-speed pilot — COMPLETE_DESCRIPTIVE_PILOT

Driver pipeline remains owner-aborted; results below are diagnosis speed measurements.

| Effort | Recorded / 8 | Decode measured | Setup failures | Median decode tok/s | Expected decisions / 8 |
|---|---:|---:|---:|---:|---:|
| xhigh | 8 | 6 | 2 | 62.49 | 2 |
| medium | 8 | 8 | 0 | 71.01 | 2 |

High: UNSUPPORTED by the installed template; never mapped to medium.

| Effort | Case | Output tokens | Gateway seconds | Native decode tok/s | Observed | Expected |
|---|---|---:|---:|---:|---|---|
| xhigh | late-finding:0 | NOT_RUN | NOT_RUN | NOT_RUN | FAILED_PROTOCOL | PROPOSE_REPAIR |
| xhigh | late-finding:1 | NOT_RUN | NOT_RUN | NOT_RUN | FAILED_PROTOCOL | PROPOSE_REPAIR |
| xhigh | missing-primary:0 | 17943.00 | 290.99 | 61.90 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| xhigh | missing-primary:1 | 16674.00 | 273.67 | 61.22 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| xhigh | obligation-counterexample:0 | 6293.00 | 102.88 | 61.86 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | obligation-counterexample:1 | 4889.00 | 76.46 | 65.06 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | upstream-owner:0 | 5718.00 | 91.91 | 63.14 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | upstream-owner:1 | 7021.00 | 112.67 | 63.08 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | late-finding:0 | 735.00 | 12.10 | 68.27 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | late-finding:1 | 620.00 | 10.05 | 70.80 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | missing-primary:0 | 798.00 | 12.35 | 70.19 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| medium | missing-primary:1 | 1079.00 | 16.00 | 70.78 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| medium | obligation-counterexample:0 | 994.00 | 14.79 | 73.27 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | obligation-counterexample:1 | 825.00 | 12.78 | 71.22 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | upstream-owner:0 | 2195.00 | 31.27 | 73.06 | REJECTED | PROPOSE_REPAIR |
| medium | upstream-owner:1 | 2162.00 | 31.03 | 72.61 | REJECTED | PROPOSE_REPAIR |

No speed/quality winner or production capability is established. Missing runs, setup failures, job wall time and unknown usage are retained in raw metrics. Load/control startup is recorded separately in activation receipts. Formal controlled-comparison measurements and learning overhead remain unqualified.

Runtime source: 37c0c354629312a70eb6a199989477036bb674d9.

- Two initial xhigh cases had host setup refusals before inference, retained in denominator
- Small diagnosis-only cohort; not author/inspector or pipeline qualification
- Serial xhigh-first order and thermal/cache differences are recorded; not randomized
- Model reasoning tokens included; no hidden reasoning content collected

## Paired latency versus full trial time

[Recompute](analyze-paired-speed.py) with `python3 analyze-paired-speed.py`;
[all input hashes, paired rows, exclusions and totals](paired-speed-analysis.json).
Six cases generated in both cohorts. Two original xhigh setup failures are excluded
only from paired timing, retained in the eight-case quality denominator.

| Six matched diagnosis trials | xhigh | medium | Speedup |
|---|---:|---:|---:|
| Gateway request seconds | 948.5801 | 118.2134 | 8.024x |
| Complete trial wall seconds | 1344.2748 | 383.0418 | 3.509x |
| Completion tokens, including reasoning | 58538 | 8053 | 7.269x fewer |

Full trial wall includes orchestration/polling/verification, excludes initial model
activation, and is still not full-pipeline performance. Much of the gateway gain
comes from fewer generated tokens rather than faster token decoding. Missing-primary
cases improved17–24x in gateway time, while upstream-owner cases improved3–4x and
medium's upstream-owner proposals were structurally rejected. Neither setting is
qualified for production by these timings. No hidden reasoning content was collected.
