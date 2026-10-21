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

## Conclusion (agent recommendation, not an owner decision)

The factory cannot run exclusively on local qwen3-coder:30b on this host: NOT_RUN beyond SWE.1, so SWE.2-SWE.6,
packaging and inspector quality are NOT_MEASURED. The limit is throughput: 11k-24k-token prompts processed mostly
on the CPU. A further local trial needs a model that fits in VRAM, or a larger GPU, plus a configurable Fabro stall
watchdog. Until then: authors Codex Sol 6.1, inspectors Claude Opus 5.5.
