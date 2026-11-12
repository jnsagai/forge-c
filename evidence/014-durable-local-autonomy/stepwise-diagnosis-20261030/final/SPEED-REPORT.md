# Existing four-question Qwen diagnosis — COMPLETE_DESCRIPTIVE_PILOT

Medium/Q8/f16/MTP3/context262144/one inference, at most4requests/job.
Previously exposed cases; no fresh holdout, product or author/inspector qualification.
Incomplete-packet first question forces UNKNOWN; do not count that as independent missing-evidence recognition.

Recorded8/8; expected decisions8/8; provider requests26/32.

| Trial | Requests | Output tokens | Gateway seconds | Trial seconds | Native tok/s | Observed | Expected |
|---|---:|---:|---:|---:|---:|---|---|
| late-finding:0 | 4 | 4820 | 75.10 | 245.33 | 68.89 | PROPOSE_REPAIR | PROPOSE_REPAIR |
| late-finding:1 | 4 | 5267 | 78.58 | 143.53 | 70.60 | PROPOSE_REPAIR | PROPOSE_REPAIR |
| missing-primary:0 | 1 | 2070 | 31.40 | 406.03 | 68.69 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| missing-primary:1 | 1 | 2213 | 32.00 | 96.95 | 70.97 | NEEDS_EVIDENCE | NEEDS_EVIDENCE |
| obligation-counterexample:0 | 4 | 4742 | 71.73 | 157.05 | 70.21 | PROPOSE_REPAIR | PROPOSE_REPAIR |
| obligation-counterexample:1 | 4 | 3863 | 58.42 | 143.83 | 70.67 | PROPOSE_REPAIR | PROPOSE_REPAIR |
| upstream-owner:0 | 4 | 5490 | 80.83 | 161.63 | 71.38 | PROPOSE_REPAIR | PROPOSE_REPAIR |
| upstream-owner:1 | 4 | 4731 | 70.11 | 135.81 | 71.33 | PROPOSE_REPAIR | PROPOSE_REPAIR |

Every failure, block, unused trial and unknown usage remains; same-model agreement is not an independent oracle.
No raw prompts or hidden reasoning collected. Existing intermediate parser removes exact duplicate list items; final broker/gates unchanged.
LL/HAL product acceptance, learning benefit and continuous availability remain unproven.
