# Ornith protocol test on Omniverse2, 31 October 2026

This is a protocol test, not a speed or capability qualification. It ran under two owner decisions on 2026-10-31:
"have a subagent testing Ornith model", then "Run, guard GPU queue".

The first preflight, at 12:12:11Z, aborted correctly ([preflight-abort.json](preflight-abort.json)). The owner then
relaxed the rule only for the idle processes listed there. One standalone server ran at a time on 127.0.0.1:18591,
started four ways (S1 to S4). All four used the same binary and blob as the speed study. All 55 chat requests passed
the guard and no guard ever failed. The servers were up from 12:20:45Z to 12:32:04Z on the omniverse2 clock, which
used 679 s of the 3600 s bound. Full data: [ornith-protocol-result.json](ornith-protocol-result.json). No reasoning
text was kept anywhere: only re-tokenized counts, `finish_reason`, usage and final content.

## Verdicts

| Q | Verdict | Evidence |
|---|---|---|
| Q1: strict `json_schema` gives exact JSON, with reasoning only in `reasoning_content` | **PASS** | 27 raw json_schema requests: all 23 that ended with `stop` are exact, schema-valid JSON (no whitespace, fences or trailing text), 15 of them with thinking on. 0 fences, 0 `<think>` tags in content. The adversarial prompt asked for a fence, an extra `confidence` field and a trailing sentence; it was still valid with thinking off and with a 1024 budget. The no-schema control returned fence + extra field + prose. Reasoning appeared only in `message.reasoning_content` / `delta.reasoning_content`. Formats `deepseek` (S1, S4) and the server default `auto` (S2) gave identical results (313/526 thinking tokens for the same seeds). |
| Q2: Forge `probe_capabilities()` | **PASS with thinking off; UNRELIABLE with thinking on** | S3 `--reasoning off`: json_schema selected, all 3 modes valid. With thinking on (S1, S2, S4) json_schema was selected 6 of 7 times, but **S1 recorded `json_object`**: its json_schema attempt hit `OUTPUT_TRUNCATED_AT_RESERVE` because default thinking used up `output_reserve=256`. In S2 run 1 the json_object attempt truncated the same way. The selected mode depends on how long the model thinks, not on schema support. |
| Q3: truncation | **PASS** | All 5 truncation cases gave `finish_reason: length`. Content was empty (thinking used `max_tokens=64`), partial (`{"x": 349025, "` after an 8-token budget), or cut-off JSON with thinking off. All 5 are detectable as invalid JSON plus `length`. The stream gives the same result. `structured.call()` with reserve 16 reported `NOT_JSON` + `OUTPUT_TRUNCATED_AT_RESERVE` and doc None. |
| Q4: `thinking_budget_tokens` together with json_schema | **PASS for budgets > 0; FAIL for budget 0** | Budget 256 gave 255 thinking tokens; 1024 gave 1023 (with and without schema); 2048 gave 2047 (Q6 packet). Budget **0 was ignored**: 2362 thinking tokens, identical to unbounded with the same seed (the server's `--reasoning-budget` help says 0 = immediate end). Budget-cut numeric answers were wrong (256 and 1024); unbounded was correct (x=487050, extracted=92). `usage` has no reasoning breakdown: `completion_tokens` includes thinking. |
| Q5: streaming with `include_usage` | **PASS** | With `include_usage`: exactly one usage chunk, with `choices: []`, before `data: [DONE]`. Without `include_usage`: no usage chunk. `structured.call()` received usage (182 prompt / 166 completion). Reasoning streams as `delta.reasoning_content`, which `call()` ignores as intended. |
| Q6: realistic SWE.1 packet (synthetic XTMR peripheral, real `swe1-author` SKILL and `GROUP_SCHEMA`) | **FAIL as the factory would call it with thinking on; PASS with thinking off** | Prompt: 3840 tokens (estimate 5146). S1 factory `call()` (no kwargs, reserve 4096): 2 of 2 runs truncated, all 4096 tokens were thinking, content empty, 27.9–28.4 s. S1 with `enable_thinking: false`: valid, 12 requirements, 2673 tokens, 18.6 s. S1 with budget 2048 and max_tokens 6144: valid, 10 requirements, 33.5 s. S3 (`--reasoning off`) factory `call()`: valid, 16 requirements, 3282 tokens, 22.9 s. The requirements' semantic validity (`swe1.validate_group`) was not checked. |

Other measured behaviour:
- **`--reasoning off` does not override the request.** A request with `chat_template_kwargs.enable_thinking: true`
  on S3 still thought for 313 tokens.
- **`--reasoning-effort medium` had no effect.** S4 gave the same 313 tokens as without it. The template caps report
  `supports_reasoning_effort: false`.
- **`maxLength` constraints cut text mid-word.** The grammar enforces `maxLength: 120` by cutting the string mid-word
  ("...cannot be objectively ver"). One cut-off note also contained a Chinese token. The JSON is valid but the text
  is semantically damaged.
- **Prompt caching was active.** `call()` does not send `cache_prompt: false`, so S1's second Q6 run reported
  3838 cached prompt tokens.

## Server

Common argv (only the reasoning flags differ):
```
/mnt/data/forge-c/ollama-0.34.0/lib/ollama/llama-server --model /mnt/data/forge-c/production-local-014/ollama-models/blobs/sha256-de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3 --alias ornith-1.5-35b-a3b-q8 --host 127.0.0.1 --port 18591 --no-webui --offline -c 32768 -np 1 --jinja <REASONING> --cache-type-k f16 --cache-type-v f16 --flash-attn on --gpu-layers all -b 2048 -ub 2048 --spec-type none --fit off --metrics
env LD_LIBRARY_PATH=<lib>:<lib>/cuda_v13 GGML_BACKEND_PATH=<lib>/cuda_v13/libggml-cuda.so   (lib=/mnt/data/forge-c/ollama-0.34.0/lib/ollama)
```

| Server | `<REASONING>` | Model loaded (log) | Health OK | VRAM peak MiB | Stop |
|---|---|---|---|---|---|
| S1 | `--reasoning auto --reasoning-format deepseek` (speed study) | 5.40 s | 6.28 s | 37384 | SIGTERM, exit 0, 1.06 s |
| S2 | `--reasoning on` (factory form, no effort) | 5.42 s | 6.31 s | 37366 | SIGTERM, exit 0, 1.06 s |
| S3 | `--reasoning off` (factory form) | 5.40 s | 6.27 s | 37384 | SIGTERM, exit 0, 1.06 s |
| S4 | `--reasoning on --reasoning-effort medium --reasoning-format deepseek` (factory form with effort) | 5.41 s | 6.29 s | 37364 | SIGTERM, exit 0, 1.07 s |

The GPU baseline before the test was 936 MiB, so the peak sits about 36.4 GB above it. That leaves about 11.6 GB of
the 49140 MiB free at 32K with f16 KV. Build: b1-0f3a71be1, n_ctx 32768, 1 slot.

## Cleanup proof

- After each stop the PID was gone from /proc, the GPU was back to 936 MiB with 0 compute processes, and port
  18591 was closed.
- The final check at 12:32:04Z found no own llama-server or server.sh process.
- The ssh port-forward and the ssh control master on loop10 were closed.
- The runner (PID 2742646) and the conductor (PID 3699940) were still running and were never signalled.
- Factory intent stayed STOPPED, epoch 7, and was never modified.

## Deviations

1. **The gpuq STOP file was NOT created.** `gpuq-runner.sh` loops `while [ ! -f $QD/STOP ]` and exits once the file
   exists. Creating STOP would have ended runner PID 2742646, which contradicts "do not stop ... any of them".
   Removing STOP afterwards would not have restarted it. The queue was guarded instead: a watcher checked every
   ~1 s and would have killed the server on any job, plus a guard check before every request. Neither ever fired.
   STOP did not exist before or after the test.
2. **Flags beyond the brief, kept for parity.** `-b 2048 -ub 2048` (factory defaults) and `--fit off` (speed study)
   were added. `-t`/`-tb` were left at their defaults.
3. **Four starts instead of one or two.** Each was a restart of our own single server, one at a time.
4. **More than one Q6 call.** Q6 used several calls instead of one, to separate the thinking-on, thinking-off and
   budget effects. The first S1 Q6 run crashed in my driver after the factory call, and its values are transcribed.
   The first S2 probe file was overwritten by a driver bug, and its values are transcribed from the printed output.
   Both are marked `TRANSCRIBED`.
5. **Model sha256 not recomputed.** Only the size was checked (37802149280). The hash basis is the speed study's
   verification.
6. **Requests ran from loop10.** Chat requests went from loop10 through an ssh port-forward. Forge code ran
   unmodified from the loop10 worktree with `PYTHONDONTWRITEBYTECODE=1`. Nothing was copied to omniverse2.
7. **Server logs stay on omniverse2 only.** They are in `work/` and contain no prompt or generated text.

## Contradictions with, and gaps in, design section 11

1. **The argv claim does not match the code.** Section 11 says the default "stays `deepseek`, so existing argv is
   unchanged". `llama_server_spec` emits `--reasoning-format deepseek` only when `reasoning_effort` is set. On this
   build, the default `auto` behaved like `deepseek` (S2 = S1), so the effect is nil, but the argv statement is
   inaccurate.
2. **Fenced or trailing-text JSON would be accepted.** Section 11 says such answers are INVALID, but
   `structured._parse_json` accepts fenced JSON and `WRAPPED_JSON` without an error. The no-schema control
   (fence + prose) parsed with note None and was rejected only because its keys did not match. Under json_schema
   no fence ever occurred, so the gap matters for the `json_object`/`none` modes. The S1 probe would record
   `json_object` for this model.
3. **`call()` sends no thinking controls.** It sends neither `chat_template_kwargs` nor `thinking_budget_tokens`.
   With `--reasoning on|auto`, thinking consumes the output reserve: the probe (256) becomes nondeterministic, and
   the SWE.1 packet (4096) truncated 2 of 2 times. Section 11's gateway `request_overrides` are therefore required
   before any thinking-on Ornith profile. Per-request `thinking_budget_tokens: 0` does not disable thinking; use
   `enable_thinking: false`.
4. **Truncation handling matches section 11, but token accounting is coarse.** `finish_reason: length` handling
   agrees with section 11 (measured). But `usage` cannot separate thinking from answer tokens.
5. **`--reasoning-effort` changes nothing on this template.** This is consistent with section 11's
   identical-template finding.

Nothing was committed.
