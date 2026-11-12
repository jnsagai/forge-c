# Qwen non-thinking/reasoning-speed pilot — COMPLETE_DESCRIPTIVE_PILOT

Driver pipeline remains owner-aborted. Q8/f16/MTP3/262144/output ceiling fixed; reasoning none, medium and xhigh.

| Reasoning mode | Recorded / 8 | Decode measured | Setup failures | Median decode tok/s | Expected decisions / 8 |
|---|---:|---:|---:|---:|---:|
| none | 8 | 8 | 0 | 61.76 | 2 |
| medium | 8 | 8 | 0 | 68.64 | 2 |
| xhigh | 8 | 8 | 0 | 63.29 | 2 |

| Reasoning mode | Case | Output tokens | Gateway seconds | Native decode tok/s | Observed | Expected |
|---|---|---:|---:|---:|---|---|
| none | late-finding:0 | 134.00 | 4.04 | 51.86 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| none | late-finding:1 | 134.00 | 3.70 | 51.56 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| none | missing-primary:0 | 142.00 | 3.32 | 61.44 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| none | missing-primary:1 | 141.00 | 2.80 | 62.35 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| none | obligation-counterexample:0 | 157.00 | 3.42 | 62.81 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| none | obligation-counterexample:1 | 157.00 | 3.44 | 62.19 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| none | upstream-owner:0 | 163.00 | 3.90 | 62.07 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| none | upstream-owner:1 | 156.00 | 3.70 | 57.12 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | late-finding:0 | 786.00 | 12.79 | 69.47 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | late-finding:1 | 700.00 | 11.82 | 67.31 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | missing-primary:0 | 1090.00 | 17.13 | 67.59 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| medium | missing-primary:1 | 1344.00 | 20.81 | 67.18 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| medium | obligation-counterexample:0 | 795.00 | 12.51 | 70.83 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | obligation-counterexample:1 | 788.00 | 12.50 | 70.24 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | upstream-owner:0 | 1421.00 | 22.05 | 68.35 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| medium | upstream-owner:1 | 1266.00 | 19.67 | 68.94 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | late-finding:0 | 6685.00 | 106.72 | 63.51 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | late-finding:1 | 11756.00 | 189.06 | 62.71 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | missing-primary:0 | 14307.00 | 223.71 | 64.36 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| xhigh | missing-primary:1 | 9079.00 | 141.03 | 64.97 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| xhigh | obligation-counterexample:0 | 6505.00 | 102.70 | 64.37 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | obligation-counterexample:1 | 7234.00 | 116.16 | 63.07 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | upstream-owner:0 | 5928.00 | 99.33 | 60.60 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| xhigh | upstream-owner:1 | 12292.00 | 199.42 | 62.09 | NEEDS_EVIDENCE | PROPOSE_REPAIR |

No speed/quality winner or production capability is established. Missing runs, setup failures, job wall time and unknown usage are retained in raw metrics. Load/control startup is recorded separately in activation receipts. Formal controlled-comparison measurements and learning overhead remain unqualified.

Runtime source: 12e601e4f53ab71b6d184ae19379faa1dd8f6e97.

- Eight frozen diagnosis cases per setting; not authors/inspectors or full pipeline
- Serial none/medium/xhigh order, thermal/cache effects recorded, not randomized
- Failed, rejected, blocked and unknown-usage outcomes remain in denominator
- No hidden reasoning collected; designated semantic proposals retained
