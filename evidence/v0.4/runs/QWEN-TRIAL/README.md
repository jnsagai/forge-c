# Local Qwen trial (owner "go", 2026-10-20): can the factory run exclusively on local qwen3-coder:30b?

Host: RTX 4070 Laptop 8 GB VRAM, i9-14900HX, 32 GB RAM; Ollama 0.34.0 standalone; every agent node (authors and
inspectors) on qwen3-coder:30b (MoE, partly offloaded), no ACP, no cloud model.

| Run | Factory | Result |
|---|---|---|
| WO-0009A-STM32N6-IWDG-LL-q1 | 2a7dae9 (default timeouts) | BLOCKED at SWE.1 after 70 min: the first author stage hit the 1500 s timeout, both inspector stages hit the 900 s timeout before recording an inspection |
| q2, q3 (IWDG LL), RCC LL q1-q3 | 2a7dae9 | cancelled by the agent: identical configuration, the same timeout wall expected |

Measured throughput during q1 (local gateway meter): 65 calls, median 27 s, max 9.5 min; prompts 11k-24k tokens;
about 3.2 output tokens/s including prompt processing; GPU 6.8/8 GB in use (the model runs largely on CPU).

Next: q4 with --timeout-scale 4 (pd-bed51a0d6eb9ab1f88c6) to separate speed from quality.
