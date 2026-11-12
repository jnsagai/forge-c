# PF-ENG-002 — Source inventory for the process-first design (read-only)

Revision: `876d75f6` (= `origin/feat/014-durable-local-autonomy`, 2026-10-31). `ff/` = `factory/python/forge_factory/`.
Static reading only: no test run, no model, no remote host. Facts below are from source, not reports.

## A. Branch state vs plan
- All prepared fixes are ancestors of HEAD: `d2e083e3` (GPU-capacity retry), `50a4813d`/`3788ace6` (MCP optional
  defaults), `60619be0` (admission before reservation), `d0090099` (declared target API), `a4bc71d1`, `c0777ead`,
  `6a4721ec`, `b8ecd269`. PF-ENG-003 is therefore *evidence collection* (regression receipts), not integration.
  Their **native** effectiveness remains NOT_RUN.
- Overnight report is on main at `45190eb`; pinned evidence revision `dce7ad27` resolves locally.
- Ornith speed study used the **official ornith-ai** Q8_0 GGUF (37.8 GB, sha256 `de46c4ba…58c3`), served by the
  **same bundled Ollama-0.34 llama-server binary** the stack uses (`/mnt/data/forge-c/ollama-0.34.0/lib/ollama/llama-server`,
  `server-instance.json` argv), started outside the factory stack, with `--jinja --reasoning auto --reasoning-format
  deepseek`; thinking budgets were per-request body fields (`chat_template_kwargs.enable_thinking`,
  `thinking_budget_tokens`, `run_benchmark.py:332`). Correction 2026-10-31: an earlier wording said "standalone". The plan text names the **AtomicChat** build (~36.9 GB). The
  plan itself states builds are not interchangeable → owner must pin one.

## B. Model / GPU runtime (exists)
- One job = one model: `request_admission.reserve` requires `job.model == body.model` (`afo/request_admission.py:49`);
  `ROLE_CAPABILITY_MODEL_OR_ROLE_CHANGED` (`lrtx/role_capability.py:155`).
- Single inference/generation ownership rows (`afo/durable.py:111`); `MissionLedger.acquire_inference`/
  `release_inference` require QUIESCENCE evidence and no SENT/UNKNOWN requests (`afo/mission_ledger.py:373-426`).
- Provider quiescence and retirement: `lrtx/provider_process.py:53-200`; `afo/provider_recovery.py:28-79`
  (GENERATION_FENCE). Operations intent RUNNING/PAUSED/DRAINING/STOPPED + epoch (`afo/operations.py`);
  `recover_profile` refuses restart while an inference owner exists (`:309-336`).
- Bounded admission before reservation (`llm_gateway.py:535-553`, `lrtx/admission.py:34-88`); timeouts →
  `*_OUTCOME_UNKNOWN`, no retry (`llm_gateway.py:608-616`).
- Profile schema `forge-c/local-profile/1` (`lrtx/profile.py:32-43`), digest/quantization pinning, per-model
  inspector sampling and per-role reasoning effort; per-role **model** only for SWE.3/4 code nodes
  (`workflow/builder.py:168-172`).
- Scheduler picks one `model_profile` per order (`afo/scheduler.py:88`, `afo/runtime.py:69-89`).

## C. Model / GPU runtime (absent or blocking)
- No resident-model record, no load/unload/switch API, no role-batch scheduling, no model-handoff fence.
- `stack.llama_server_spec` serves one model per profile and only from an Ollama `library` manifest
  (`lrtx/stack.py:370-413`); a raw HF GGUF does not fit that path.
- Gateway + provider share one serving PID namespace (`stack._start` :615-664): retiring the model kills the gateway
  and changes the provider-instance digest (in-flight reservations refuse, `request_admission.py:186-191`).
- No Ornith profile under `config/`.
- **Identity gap (AT03):** structured packet `input_hash` (`lrtx/structured.py:172,237`) includes model *name* and
  sampling but not digest/profile sha/reasoning; visit and inspector checkpoints reuse on it
  (`lrtx/visit.py:154-169`, `lrtx/review.py:241`).

## D. SWE.1 path (exists)
- Structured local author `lrtx/swe1.py` (`inventory`, `group_packet`, `validate_group`, `assemble` :491-595);
  standalone `python -m forge_factory.lrtx.runner author|inspect --phase SWE.1`.
- Artifacts: `workproducts/SWE.1/software_requirements.md`, `.reqif`, `traceability/requirements_to_tests.csv`,
  contract-mode `register_effects.json` (`inspection/engine.py:37-48`). Gates `inspection/gate.py:107-215`, EARS
  `inspection/ears.py:115-140`, baselines `configuration/baselines/SWE.1/BL-*.json`.
- Stepwise inspector `lrtx/review_semantic.py` (grammar-constrained, temperature 0, reads frozen baseline only,
  `BASELINE_CHANGED_DURING_INSPECTION`, author≠inspector role check `inspection/engine.py:280`).
- Advisory gap register `forge-c/advisory-gap/1` with ladder (`inspection/gate.py:353-409`).
- Inbound requirements importer `ff/provided_requirements.py` (`forge-c/provided-requirements/1`).
- Experience capture append-only, PENDING disposition, no inference (`knowledge/experience.py:47-128`); lessons
  PROPOSED→VALIDATED, retrieval VALIDATED-only (`knowledge/store.py:293`).

## E. SWE.1 path (absent or blocking)
- Graph cannot be cut to SWE.1: `_build` always emits six phases (`workflow/builder.py:334-489`); release policy and
  `delivery_first.workflow` expect all (`DELIVERY_FIRST_GENERATOR_ROUTE_AMBIGUOUS`, :300).
- No SWE.1→SWE.2 handoff schema/importer; SWE.2 consumers regex-scrape markdown (`inspection/swtrace.py:101`,
  `lrtx/swe2.py:78-87`).
- SWR IDs positional, renumbered on every assembly (`lrtx/swe1.py:508-509`) — not stable across runs.
- ID pattern mismatch: `ears.py` allows `SWR-[A-Z0-9…]`; `swtrace`/`swe2`/`review_semantic` require `SWR-\d{3}`.
- RM0486/STM32N6 hard-coded (`lrtx/swe1.py` 228/501/738, `provided_requirements.py:70`, `assurance/swe12.py:34`) —
  blocks a different-MCU holdout.
- No `NOT_INSPECTED` state: timeout/invalid → FAILED/CONTINUE → rework (fail-closed, but unlabelled).
- Delivery-first oracles are declared `inputs/` readable by the author (no leakage fence).
- Corpus: F015 queue covers CRC/SPI/USART/GPIO/TIM (`config/factory/benchmark/st-driver-queue.yaml`); IWDG only as
  `examples/0009*`. F015 GPIO+CRC test set 2 and the 9-baseline calibration subset are already SPENT (learning only).
- Inspector calibration on unseen clean baselines is weak (5/9 and 2/2 false rejections recorded).
