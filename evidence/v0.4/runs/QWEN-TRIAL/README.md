# Local Qwen trial (owner "go", 2026-10-20): can the factory run exclusively on local qwen3-coder:30b?

Host: RTX 4070 Laptop 8 GB VRAM, i9-14900HX, 32 GB RAM; Ollama 0.34.0 standalone; every agent node (authors and
inspectors) on qwen3-coder:30b (MoE, partly offloaded), no ACP, no cloud model.

| Run | Factory | Result |
|---|---|---|
| WO-0009A-STM32N6-IWDG-LL-q1 | 2a7dae9 (default timeouts) | BLOCKED at SWE.1 after 70 min: the first author stage hit the 1500 s timeout, both inspector stages hit the 900 s timeout before recording an inspection |
| q2, q3 (IWDG LL), RCC LL q1-q3 | 2a7dae9 | cancelled by the agent: identical configuration, the same timeout wall expected |

Measured throughput during q1 (local gateway meter): 65 calls, median 27 s, max 9.5 min; prompts 11k-24k tokens;
about 3.2 output tokens/s including prompt processing; GPU 6.8/8 GB in use (the model runs largely on CPU).

## q4: WO-0009A-STM32N6-IWDG-LL-q4, --timeout-scale 4 (pd-bed51a0d6eb9ab1f88c6), 2026-10-20 21:45 - 2026-10-21 00:28 UTC

Result: BLOCKED at SWE.1 (49 gaps, SWE.2-SWE.6 not reached). Evidence: q4/gate-log.jsonl, q4/package.json, q4/model-profile.json.

| Stage | Duration | Outcome |
|---|---|---|
| swe1_author | 44 min | succeeded: 13 SWRs, forge-ears-check PASS (13 reqs, 0 major), 9 register effects |
| swe1_author_gate | 1 s | baseline BL-SWE.1-002 FROZEN (deterministic SWE.1 gates PASS) |
| swe1_inspector | 60 min | failed: handler timed out after 3600 s (scaled limit); two Ollama HTTP 500s; no inspection recorded |
| swe1_inspect_gate / route | <1 s | NO_INSPECTION_FOR_CURRENT_BASELINE -> REINSPECT via swe1_author |
| swe1_author (2nd visit) | 57 min | four parallel tool prompts queued at Ollama, two more HTTP 500s; Fabro stall watchdog (1800 s idle, not scaled by --timeout-scale) failed the run |

Throughput (local gateway meter, 38 calls): median 100 s per call, max 589 s, 379k input / 4.6k output tokens,
0.71 output tokens/s including prompt processing (q1: 3.2). Cause observed during the run: a CarlaUE4 simulator
(another owner workload) held 4.4 GB of the 8 GB GPU, leaving 2.0 GB of the 19.2 GB model in VRAM (~11 %); q1 ran
under the same contention.

Quality, as far as reached: Qwen's SWE.1 author output passed the deterministic SWE.1 gates. It is smaller than the
Codex runs of the same work order (13 SWRs vs 16 in i003 and rc1), and SWR-004 keeps the ambiguous "any other key
value, e.g., 0x0000" wording from the prompt. No inspector verdict exists for it, so its inspection quality is NOT_MEASURED.

## GPU runs (owner "put down carla" + "run again the qwen runs using GPU", 2026-10-21 03:37 - 06:51 UTC)

The owner stopped the CARLA simulator; qwen3-coder:30b then had 6.5 of its 19.2 GB in VRAM (34 %). Six runs, factory
0c1942a (PR #30 head), every agent node on qwen3-coder:30b, --timeout-scale 4, one at a time (Fabro
max_concurrent_runs = 1). Evidence: gpu/<run>/{gate-log.jsonl,package.json,model-profile.json}.

| Run | Wall | SWE.1 | SWE.2 | Package |
|---|---|---|---|---|
| IWDG-LL-g1 | 38 min | PASS: gates after 2 reworks, Qwen inspection PASS | BLOCKED after 4 attempts | BLOCKED, 43 gaps |
| IWDG-LL-g2 | 31 min | PASS: gates after 1 rework, inspection PASS | BLOCKED after 3 attempts | BLOCKED, 43 gaps |
| IWDG-LL-g3 | 30 min | PASS: gates after 1 rework, inspection PASS | BLOCKED after 5 attempts (2 progress extensions) | BLOCKED, 43 gaps |
| RCC-LL-g1 | 55 min | BLOCKED after 3 attempts | not reached | BLOCKED, 49 gaps |
| RCC-LL-g2 | 18 min | BLOCKED after 3 attempts | not reached | BLOCKED, 49 gaps |
| RCC-LL-g3 | 14 min | BLOCKED: identical deterministic rejection twice (STUCK) | not reached | BLOCKED, 49 gaps |

Throughput over the six runs (local gateway meter): 613 calls, median 6.5 s, p95 73 s, 9.27 M input / 157 k output
tokens, 14.0 output tokens/s (q4 with the GPU shared: 0.71). No stage timeout and no stall watchdog fired.

Repeated rejections (deterministic gates, not model variance):
- IWDG SWE.2, every run: SWR-010..SWR-013 (reset invariant and the three resource budgets) never allocated to a
  software component; the LL software component missing or an extra IWDG component; interfaces without an ID;
  diagram syntax errors; g2 also api_calls.json cases without a call (CONTRACT_CASE_WITHOUT_CALL).
- RCC SWE.1, every run: register_effects.json incomplete (CONTRACT_SWR_NOT_COVERED: SWR-003/005/006...), missing
  entirely once, or naming fields its requirement does not name (CONTRACT_FIELD_NOT_IN_SWR); a reset requirement
  mapped to a host test (STARTUP_INVARIANT_ON_HOST_TEST); one QM claim in the ASIL B scope (SAFETY_SCOPE).
- One Qwen SWE.1 inspector ended with a non-JSON reply (agent_status FAILED) after writing a PASS inspection record;
  the gate decides from the record.

The same work orders on Codex Sol 6.1 authors + Claude Opus 5.5 inspectors reached READY_FOR_OFFLINE_REVIEW with 0
gaps in the rc1 campaign (WO-0009A-STM32N6-IWDG-LL-rc1, WO-0002A-STM32N6-RCC-LL-rc1).

## Conclusion (agent recommendation, not an owner decision)

With the GPU free, speed is no longer the limit (14 output tokens/s, 14-55 min per run, no timeouts). The limit is
output quality: 0 of 6 runs passed SWE.2 (IWDG 3/3 passed SWE.1 and stopped at SWE.2; RCC 0/3 passed SWE.1), so
SWE.3-SWE.6, packaging and Qwen as SWE.2+ inspector are NOT_MEASURED. The factory cannot run exclusively on local
qwen3-coder:30b. Keep authors on Codex Sol 6.1 and inspectors on Claude Opus 5.5. The deterministic gates rejected
every incomplete work product, with no false READY.
