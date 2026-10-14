# ADR-0005 — Local-model runtime findings and compensations (night run 2026-10-14)

- **Status:** Accepted · **Tasks:** T007, T009, T018, T042, T046, T048 · **Evidence:** `evidence/v0.4/live/`,
  run archives `WO-0002-STM32N6-RCC-r1..r6`

| # | Observation (verified on Fabro 0.362 + Ollama 0.34 + qwen3:8b) | Decision |
|---|---|---|
| 1 | Ollama's VRAM-based default context is **4096**; Fabro's prompt with ~50 tool schemas was truncated, the model never saw tools and emitted tool calls as plain text. | `OLLAMA_CONTEXT_LENGTH=16384`, flash attention, q8_0 KV cache (`scripts/forge_services.sh`); verified 9 k-token prompt fully processed, model fully GPU-resident (6.2/8 GB). |
| 2 | 50 tool schemas per request waste tokens and invite denied calls. | Gateway offers only the role's permitted tools, detecting the role deterministically from the node's `use_skill` instruction; the policy hook remains the enforcement point. |
| 3 | "Follow the skill" was insufficient: the 8B model froze baselines before writing workproducts. | Node prompts are explicit numbered procedures (`workflow/prompts.py`): read → write (exact formats) → validate → freeze → reply. |
| 4 | Large tool outputs (a 300-line section index, multi-MB manuals) derail the model into summarising tool output. | Reference manual is deterministically split into ≤38 kB per-section files; prompts name the exact files; "continue with the next step, never summarise" rule. |
| 5 | Fabro's deterministic **failure-cycle breaker** (3 identical signatures) terminates the run before our bounded rework loop decides, and the in-graph `finalize` node never runs. `loop_restart_signature_limit` as graph attribute validates but is not honoured. | Gate exit codes encode the attempt number (distinct signatures); our route gate (3 cycles) remains authoritative; the supervisor's **external finalizer** packages every terminal run without a package (live-verified). |
| 6 | Small models send `"PASS"` strings where an object is expected. | `check_inspection` accepts bare verdicts; evidence ref defaults to the frozen baseline record; deterministic items are recomputed regardless. |
| 7 | A tool-error loop can run indefinitely inside one agent node. | T042 governor: per-visit turn cap in the policy hook (reset by a `stage_start` hook), node `timeout`, and token governor in the supervisor poll that cancels on reported-usage excess (live-verified on run `…5A4`). |
| 8 | Agent self-reported status is unreliable (`AGENT_OUTPUT_SCHEMA` on a correct repair). | Promotion, gates and packaging never rely on agent claims; only deterministic checks decide. |
