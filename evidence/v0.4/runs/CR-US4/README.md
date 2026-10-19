# CR-US4 evidence: model usage and cost (feature 007)

Recorded 2026-10-19.

- **Proxy (CR-T027/T029).** `test_acp_proxy.py::test_cr_t027_usage_is_recorded_per_prompt_result_without_content`:
  - one `usage` line per prompt result, from ACP `usage` or the adapter's `_meta.quota`;
  - counts and the model ID only; the prompt text never reaches the log;
  - nothing is written when nothing is reported.
- **token_usage (CR-T030).** `test_controlroom_usage.py::test_token_usage_tolerates_acp_stages`: model-null (ACP)
  stages are listed as `not_reported_stages`. They no longer turn the whole run's usage into `unknown`, and the
  basis stays inside the 002 enum.
- **Aggregation (CR-T028/T031).** Native Fabro records and ACP proxy records are merged. A completed ACP stage
  without a record is `not_reported`, never counted as 0. Cost comes only from the configured price table; a
  subscription model is NOT_MEASURED ("subscription; no per-token price").
- **Live, port 8766, 7 days, all runs.**
  - 1,517 agent stages, 1,220 reported (19.6 % not reported).
  - 51.7 M new tokens reported. DeepSeek flash: authors 35.6 M, inspectors 15.1 M.
  - Codex Sol 6.1 authors: 297 stages, all not reported (they ran before the proxy recorded usage).
  - Tokens per READY package: NOT_MEASURED (0 READY packages).
  - Cost: NOT_MEASURED for every model (no price configured).
