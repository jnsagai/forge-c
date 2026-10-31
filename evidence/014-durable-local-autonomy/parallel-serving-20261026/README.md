# Parallel model serving on Omniverse2 (2026-10-26)

Owner decisions of 2026-10-26: after calibration, measure parallel serving for development iterations, then "install a
new runtime on Omniverse2 to allow parallel model calls". Model `qwen3.6:35b-a3b` (Q4_K_M, pinned digest
`a7eb95c5…`), inspector revision `285d21e` (P1, P2) and `45200fe` (llama-server run; same inspector logic), learning set
1 (7 holdouts × 7 cases = 49 evaluations), temperature 0, seed 1. Comparison rows (ids and counts only):
[learning-set-comparison.json](learning-set-comparison.json); reference = learning-14.

## Ollama 0.34.0 does not serve this model in parallel

With `OLLAMA_NUM_PARALLEL=2` (and the gateway admitting 2), Ollama logs `model architecture does not currently support
parallel requests` (`qwen35moe`) and starts its llama.cpp runner with one sequence (`n_seq_max = 1`). Two concurrent
harness processes therefore take turns: P2 ran 1.27 evaluations/min against P1's 1.30 and was stopped after 13
evaluations; P3 was skipped.

| Run | Server | Harnesses | Evaluations | Wall | Outcomes = learning-14 | Answer values = learning-14 |
|---|---|---|---|---|---|---|
| P1 | Ollama, 1 slot | 1 | 49 | 2,256 s | 49/49 | 761/769 (99.0%) |
| P2 | Ollama, `NUM_PARALLEL=2` (ignored) | 2 | 13 (stopped) | 617 s | 13/13 | — |
| ls-p2c | llama-server, 2 slots | 2 | 49 | 2,202 s | **48/49** | 707/750 (94.3%) |

P1 also shows the run-to-run noise of the unchanged configuration after a stack restart: outcomes identical, 8 of 769
answer values and more quote boundaries differ. Records were captured for 40 of 49 evaluations (the periodic record
copier misses some).

## The new runtime: llama.cpp server with request slots

Commit `45200fe` (profile `local-rtx-v2-omniverse2-q36-noreason-ls`): the stack starts the llama.cpp server bundled with
Ollama 0.34.0 on the same pinned model file (manifest digest checked, model layer by size), N slots, reasoning off,
the model's chat template (Jinja); the gateway routes only that model to it. No new software was installed; CUDA 12.8
is already on the host should a newer upstream build be needed.

Generation-heavy benchmark (8 structured requests of ~170 output tokens, short prompts, standalone server; 4-slot server
verified by pid):

| Server | 1 at a time | 2 at once | 3 | 4 |
|---|---|---|---|---|
| 4 slots | 163 tok/s | 218 | 220 | 240 |
| 2 slots + MTP draft | 183 tok/s | 211 | — | — |

Stability: the stack-started server crashed twice within seconds of a fresh stack start (`CUDA error: an illegal memory
access`, then `cublasSgemm ... internal operation failed`), once on the first request with no concurrency. It did not
reproduce in 8 later standalone, in-namespace and in-stack checks (long prompts, shared prefixes, cache on/off, the real
harness), nor during the 37-minute ls-p2c run. Cause unknown; treat the bundled server as not proven stable.

## Result and recommendation

- For the inspector the gain is negligible (-2% wall). Its requests are prompt-processing heavy (long packets, short
  answers), which already saturates the GPU; each evaluation took about 1.7× longer when two ran together.
- The llama.cpp server renders prompts with the model's own template instead of Ollama's renderer. That changed enough
  answers to break one learning-set result (IWDG-HAL rc4 clean baseline falsely rejected). It is a different
  configuration and would need its own qualification.
- Keep the qualified Ollama configuration for the inspector. The `-ls` profile stays EXPERIMENTAL, for future
  generation-heavy concurrent work (1.35–1.5× there), after its own qualification and a stability soak.
