# Qwen MTP draft-speed pilot — COMPLETE_DESCRIPTIVE_PILOT

Driver pipeline remains owner-aborted. Q8/f16/xhigh/262144 fixed; only MTP draft length changes.

| MTP variant | Recorded / 8 | Decode measured | Setup failures | Median decode tok/s | Expected decisions / 8 |
|---|---:|---:|---:|---:|---:|
| draft3 | 8 | 8 | 0 | 63.44 | 2 |
| draft2 | 8 | 8 | 0 | 56.94 | 2 |
| draft4 | 8 | 8 | 0 | 65.91 | 2 |
| draft6 | 8 | 8 | 0 | 64.70 | 2 |

| MTP variant | Case | Output tokens | Gateway seconds | Native decode tok/s | Observed | Expected |
|---|---|---:|---:|---:|---|---|
| draft3 | late-finding:0 | 2994.00 | 46.54 | 66.18 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft3 | late-finding:1 | 5789.00 | 94.18 | 62.39 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft3 | missing-primary:0 | 5556.00 | 86.57 | 65.03 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| draft3 | missing-primary:1 | 13402.00 | 214.46 | 62.79 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| draft3 | obligation-counterexample:0 | 5574.00 | 90.32 | 62.66 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft3 | obligation-counterexample:1 | 2433.00 | 38.58 | 65.39 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft3 | upstream-owner:0 | 6964.00 | 109.94 | 64.09 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft3 | upstream-owner:1 | 7822.00 | 127.53 | 62.01 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft2 | late-finding:0 | 3291.00 | 57.14 | 58.98 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft2 | late-finding:1 | 4883.00 | 86.08 | 57.67 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft2 | missing-primary:0 | 10191.00 | 181.71 | 56.41 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| draft2 | missing-primary:1 | 13863.00 | 246.28 | 56.56 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| draft2 | obligation-counterexample:0 | 4886.00 | 86.61 | 57.30 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft2 | obligation-counterexample:1 | 3064.00 | 53.46 | 58.76 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft2 | upstream-owner:0 | 3707.00 | 66.81 | 56.57 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft2 | upstream-owner:1 | 5184.00 | 92.93 | 56.57 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft4 | late-finding:0 | 4748.00 | 75.67 | 63.90 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft4 | late-finding:1 | 4225.00 | 65.16 | 66.32 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft4 | missing-primary:0 | 12061.00 | 189.16 | 64.12 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| draft4 | missing-primary:1 | 9118.00 | 139.95 | 65.72 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| draft4 | obligation-counterexample:0 | 3820.00 | 56.20 | 69.61 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft4 | obligation-counterexample:1 | 5369.00 | 82.52 | 66.10 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft4 | upstream-owner:0 | 4152.00 | 64.78 | 65.46 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft4 | upstream-owner:1 | 5341.00 | 82.06 | 66.14 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft6 | late-finding:0 | 1636.00 | 25.34 | 68.21 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft6 | late-finding:1 | 5238.00 | 82.50 | 64.54 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft6 | missing-primary:0 | 7969.00 | 124.91 | 64.35 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| draft6 | missing-primary:1 | 9510.00 | 154.55 | 61.96 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| draft6 | obligation-counterexample:0 | 1533.00 | 24.63 | 65.88 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft6 | obligation-counterexample:1 | 4529.00 | 70.48 | 65.41 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft6 | upstream-owner:0 | 4841.00 | 75.98 | 64.86 | NEEDS_EVIDENCE | PROPOSE_REPAIR |
| draft6 | upstream-owner:1 | 6015.00 | 94.64 | 64.47 | NEEDS_EVIDENCE | PROPOSE_REPAIR |

No speed/quality winner or production capability is established. Missing runs, setup failures, job wall time and unknown usage are retained in raw metrics. Load/control startup is recorded separately in activation receipts. Formal controlled-comparison measurements and learning overhead remain unqualified.

Runtime source: a9b2ddfccc326bdcf8287c95a4310c0408429ccb.

- Eight frozen diagnosis cases per setting; not authors/inspectors or full pipeline
- Serial3/2/4/6 order, thermal/cache effects recorded, not randomized
- Failed, rejected, blocked and unknown-usage outcomes remain in denominator
- No hidden reasoning collected; designated semantic proposals retained
