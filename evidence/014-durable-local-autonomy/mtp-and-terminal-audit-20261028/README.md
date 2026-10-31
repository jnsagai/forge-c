# Omniverse Q8 MTP experiment and terminal failure audit

Observed 2026-10-28. Production runtime source: **fcb15cba0bbc1b5e6e7c91c86aba08db244b5c61**.
Prospective author corrections remain f93f750fe4065472deb76eadcacb1ae963a1464a,
NOT DEPLOYED. These evidence commits do not promote runtime source.

## Measured option 3 result

Owner explicitly requested “test option 3”: MTP/speculative decoding.
Installed Qwen3.8-27B Q8_0 GGUF contains nextn/MTP tensors; bundled llama-server
supports draft-mtp. RTX6000 Ada, 48GB; exact binary hash/build and hardware recorded.
Same Q8 blob, one GPU request, context allocation65536, one slot, f16 KV,
GPU layers all, flash attention on, seed42, temperature0, max512 output tokens,
cache_prompt=false. Baseline spec-type none; candidate draft-mtp with3 draft tokens.
Two small C prompts, two repeats each, baseline then MTP. No other factory inference.

| Metric | Baseline | MTP |
|---|---:|---:|
| Weighted decoding tokens/s | 28.61 | 83.00 |
| Request wall seconds, four calls | 13.608 | 5.494 |
| Output tokens, four calls | 368 | 380 |

Decoding ratio **2.90×**; request wall ratio
**2.48×**. Loading excluded; separately recorded.
Draft acceptance 284/294.
Aggregation matches runtime throughput: sum(predicted_n−1)/sum(predicted_ms/1000).
Output lengths differ, so wall ratio is a task microbenchmark, not identical-token throughput.
Baseline-first order, tiny sample, short prompts and warm storage limit generalization.
No peak VRAM sampler; logs describe buffers, not measured process peak.

All8 outputs compiled with native Clang C11 -Wall -Wextra -Werror and passed initial checks.
All8 also passed extended independent functional checks: each CRC output compared against
a polynomial-remainder reference on all65536 two-byte messages,256 one-byte messages
and1000 deterministic variable-length messages; each popcount output compared against
compiler builtin on100000 generated values plus two extremes.
See extended-checks and executable checker. This is bounded fixture evidence,
not proof of model accuracy for arbitrary driver work.
Only2/4 paired outputs are byte-identical. CRC differs in braces around if/else bodies;
all measured cases pass behavior checks. No bit-exact equivalence claim.

**Thinking was explicitly closed in the raw prompt to isolate decoding.**
This is not requested xhigh reasoning qualification, factory tool protocol,
long engineering-context equivalence, inspector calibration, product benchmark,
or proven learning/availability benefit. No production backend switch.
Next test must exercise real role protocol, long contexts and independent held-out
correctness under a separately bounded authority; do not refill the exhausted CRC mission.

## Operational settlement

Experiment 2026-10-28T16:16:33.519989Z to 2026-10-28T16:17:02.103109Z.
Authenticated owner pause moved epoch16→17; existing model-free supervision stayed up.
Finally stopped only the experiment's own server, restored the exact previously signed
production policy83e78088c66df61e6513c466b9221e85f54ba34adbcddf0dcae48b69d91a96ad
and resumed epoch18. No grant renewal or mission allowance edits.
At 2026-10-28T16:17:44.115250Z: RUNNING18, controller/watchdog/recorder active, GPU790MiB/0%.
The epoch16 expiry cleanup is now fenced; original policy is already restored,
so no new expiry action is needed. Existing original grant expires29Oct05:00Z.
Experiment inference is recorded here, not claimed as free or as a CRC mission repair.

## Exact terminal product and recovery result

Original ASPICE run01M61F40BHTFTDTXW16WGVRN9Q ended15:49Z:
native transport SUCCEEDED, product BLOCKED. Seven author packets locally valid;
baseline BL-SWE.1-001 hashd96f4b3e0dd53f00865bb077818cea23b2f833ad50244109631799294375da33.
SWE1-01/04/05/06 PASS; SWE1-02/03 FAIL. Full original findings and package gaps included.
Findings include undefined safe-state text, coupled-field atomicity judgment, inconsistent
input-reversal coverage/open points and missing failure handling. Some may overlap or
be disputed; they are inspector findings, not six independently proven hardware defects.
Frozen inspector was not waived/retuned. Downstream SWE.2–6 NOT_RUN, delivery NOT_INJECTED.
Archive BLOCKED with50 gaps, mostly missing downstream evidence, not50 unique bugs.

Deterministic CLOSE_BLOCKED plan recorded LOCAL_DIAGNOSIS_FAILED:CAPABILITY_LIMIT,
with0 local diagnosis jobs and0 planner calls. This is not evidence Qwen executed
a diagnosis and failed. Existing advisory-final path then created attempt a2.

**Introduced implementation bug remains UNFIXED**: brownfield contract hashes the
historical safety scope's administrative work_order_id. a1→a2 changes that ID,
even with identical source/profile/purpose/policy, so ResumeRefused occurs before launch.
Read-only source check PASS and exact identity guard reproduces
RESUME_CONTRACT_OR_RUNTIME_CHANGED; sole contract difference is
/historical_safety_scope/scope/work_order_id. No mutating resume was called to reproduce.
No a2 native execution or inference occurred. Its conservative100k floor remains charged.

Mission F014-E2E5H-20261028-CRC:3/3 attempts,38 requests,1.9m conservative charged tokens,
UNKNOWN aggregate actual usage, original2m cap/deadline16:29:12Z. Historical failure,
1.4m SafeC floor,400k ASPICE floor and100k advisory floor preserved. Original order
BLOCKED/PRODUCT_LAUNCH_NOT_STARTED. Native executions QUIESCENT or NOT_STARTED with
released inference based on independent lifecycle evidence. No reset/refund or auto-retry.

## Offline Astra review

Read comparison/result, generated C, checks, exact failure audit, identity comparison
and read-only reproduction first. Then inspect:
- brownfield/resume.py contract(), workorder preparation and historical safety scope.
  Fix compatibility without discarding provenance or silently reinterpreting legacy hashes.
- Generic coherent obligations2c2971a and author input fixesf2d4dde/f93f750.
  These have deterministic evidence, but no native/candidate model benefit qualification.
- Whether MTP's 2.9× microbenchmark gain survives actual xhigh role protocol and large
  contexts while preserving independent correctness and one-request admission.
- Why the capability-limited diagnostic admission produced a final advisory that could
  not resume. Preserve cumulative accounting, source pins and operator stop fencing.

Formal Feature014 remains30/58; no new task tick. Product success, robust recovery,
learning benefit and24/72/168h operation remain unproven.
Latest physical status is a dated snapshot, not an unattended-run guarantee.

## Reproduction and privacy

Executable remote scripts and exact argv are included. The experiment script is an
auditable one-shot pinned to operator epoch16 and original policy; **do not blindly rerun**
after epoch18. Prepare a fresh bounded scope and confirm physical quiescence/current intent.
All Qwen inference was on Omniverse2; local audit artifacts stayed on loop10.
Dispatch nonces redacted in public snapshots; no raw hidden reasoning, model weights,
primary-reference documents, private keys or credentials published.
SHA256SUMS covers these artifacts. Privacy scan is pattern-based, not an absolute guarantee.
