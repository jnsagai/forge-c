# Ornith-1.5-35B-A3B Q8 reasoning-speed study — 31 October 2026

Recorded 36/36 matched serial trials on Omniverse2, three cases × three repetitions per configuration.

RTX 6000 Ada 48 GB; full GPU placement; 262144 context capacity; f16 KV; MTP off; 12 generation / 24 batch threads.
Temperature 0.6, top_p 0.95, top_k 20, min_p 0, fixed matched seeds; prompt caching requested off.
Warm-up and model hash verification precede timed trials. This is not a paired comparison with historical Qwen runs.

| Configuration | Decode tok/s median (range) | Request seconds median | Thinking tokens median* | Cases passed / 9 | Truncated |
|---|---:|---:|---:|---:|---:|
| off | 148.92 (130.13–154.39) | 0.45 | 0.00 | 1 | 0 |
| budget512 | 154.69 (152.88–155.09) | 3.66 | 511.00 | 0 | 0 |
| budget2048 | 153.89 (152.39–154.38) | 13.71 | 2047.00 | 2 | 0 |
| default_on | 153.30 (152.22–155.07) | 21.25 | 2948.00 | 4 | 1 |

*Thinking counts are re-tokenized separately and may differ at special-token/whitespace boundaries.

The downloaded template has enable_thinking, with no reasoning_effort variable. The local rendered prompts for low, medium, high and xhigh have identical hashes. The measured alternatives therefore use explicit server thinking budgets: 512, 2048 or unrestricted within the common 8192 total-completion cap; off closes thinking before generation.

| Case | off passes / 3 | budget512 passes / 3 | budget2048 passes / 3 | default_on passes / 3 |
|---|---:|---:|---:|---:|
| numeric | 0 | 0 | 0 | 1 |
| author_c | 1 | 0 | 0 | 0 |
| review_c | 0 | 0 | 2 | 3 |

Numeric: exact integer CRT and 32-bit field arithmetic, strict final JSON. Author C: independent host compilation, UBSan and 31878 checks of field replacement and bounded callback polling. Review C: exactly three seeded defects among six functions; false rejections fail the case.

The sample is small and synthetic. Pass counts are task observations, not general accuracy, reliability, model selection or ASPICE qualification. A thinking-budget cutoff is an experimental intervention; faster answers that fail checks are not an accepted quality improvement. First-token latency includes reasoning. Actual prompt lengths are in the raw timings; 262144 is capacity, not measured full-context throughput.

No thought text is retained. Final answers, generated candidate C, oracle/compiler results, numeric usage, model SHA256, exact script and server flags are retained. Factory missions, production settings and old grants are unchanged.

Model/template references: [official model](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B), [official template](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B/blob/main/chat_template.jinja), [llama.cpp request parsing](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/server-common.cpp).
