# Tasks: Model-Service Split (Omniverse2 mirrors the production deployment)

**Input**: Design documents from `specs/017-model-service-split/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: required. CLAUDE.md says "implement one small testable task at a time with tests before moving on", and quickstart steps 1 to 3 name the test files. A test task comes before its implementation and must fail first.

**Organization**: tasks are grouped by user story (spec.md, US1 to US6), so each story can be built and checked on its own.

## Ground rules (apply to every task)

- **Base:** implementation works in `repos/forge-c-017-impl` on branch `feat/017-model-service-split-impl`, created from the campaign branch of record (`feat/owner-lane-campaign-v21-20261107`), because the GPU-ownership code lives there (plan, Structure Decision). Never edit a worktree a live service runs from.
- **CRE:** every factory code commit that will be deployed needs a CRE CHANGE gate that is ELIGIBLE for that exact commit before deploy.
- **Hard limits:** no edit to signed controls, the production lane (`production-local-014`, :11460) or its units. The production observer stays OBSERVE. Claude never touches the owner's signing key. No paid or cloud dependency. x-verse_fabric is not touched.
- **GPU:** host tasks marked **[WINDOW]** may use the GPU only inside a qualification window run by the window controller (T014). Every other host task must not start anything that allocates GPU memory.
- **Evidence:** NOT_RUN or BLOCKED is recorded explicitly. A checkbox is ticked only with run evidence.
- **Paths:** paths are relative to the repository root. The Python package is `factory/python/forge_factory`; tests are in `factory/python/tests`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task).
- **[Story]**: US1 to US6 from spec.md.

---

## Phase 1: Setup (shared infrastructure)

**Purpose**: the implementation branch, package skeleton, configuration default and recipe skeleton.

- [X] T001 Create the worktree `repos/forge-c-017-impl` on a new branch `feat/017-model-service-split-impl`, starting from the current tip of `feat/owner-lane-campaign-v21-20261107` (host `repo.git`). Merge `feat/017-model-service-split` into it with a merge commit, to carry `specs/017-model-service-split/`. Record the base SHA in `specs/017-model-service-split/BASE.md`.
- [X] T002 [P] Create the package `factory/python/forge_factory/modelservice/__init__.py`. Its docstring names the feature, links `specs/017-model-service-split/plan.md` and states the hard limits above.
- [X] T003 [P] Create `config/factory/model-service.yaml` with `mode: owned`, which keeps today's behaviour, and commented `external` example values per `specs/017-model-service-split/contracts/model-service-profile.schema.json`. Copy the six contract schemas to `config/schemas/model-service/`, and extend `tests/spec/validate_design.py` to validate `model-service.yaml` against its schema.
- [X] T004 [P] Create the recipe skeleton:
  - `deploy/recipe/README.md`
  - `deploy/recipe/params/omniverse2.yaml` and `deploy/recipe/params/production.yaml`, per `contracts/recipe-params.schema.json`. Production values come from `docs/ONPREM-DEPLOYMENT.md`. Unknown platform values (serving stack, authentication method, API URL, CA) get `confirmed: false`.
  - An empty `deploy/recipe/recipe.lock.json`.
  - A `deploy/recipe/.gitignore` that excludes `secrets*`.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: identity, reason codes, the secret resolver, pinned artefacts and the GPU window controller. Every story depends on these.

**⚠️ CRITICAL**: no user-story work starts until this phase is complete.

- [X] T005 [P] Write `factory/python/tests/test_modelservice_identity.py`. It must fail first and cover:
  - The fingerprint is stable under file order and changes when one weight byte, the tokenizer or the chat template changes.
  - Verifying against the lock refuses on a mismatch.
  - An identity document validates against `config/schemas/model-service/served-model-identity.schema.json`.
  - The inferred identity from a `/v1/models` payload has `attested: false`.
- [X] T006 [P] Write `factory/python/tests/test_modelservice_reasons_secrets.py`. It must fail first and cover:
  - Every factory reason from `contracts/model-channel.md` (`credential_refused`, `share_exhausted`, `context_exceeded`, `identity_changed`, `service_unreachable`, `channel_interrupted`, `outcome_unknown`) maps from the status and `forge_reason` table.
  - The secret resolver reads only a 0600 file, refuses group- or world-readable files, and never puts a secret value in `repr`, logs or exceptions.
- [X] T007 Implement `factory/python/model_tier/identity.py` (re-exported by `forge_factory/modelservice/identity.py`):
  - `fingerprint(weights_dir, tokenizer, chat_template)`
  - `from_lock(lock)`, `verify(lock, observed)`
  - `inferred_from_models_endpoint(payload, recipe_params)`

  T005 must pass.
- [X] T008 Implement `factory/python/forge_factory/modelservice/reasons.py`, holding the reason enum and the mapping of `(status, forge_reason, exception)` to a reason, and `factory/python/forge_factory/modelservice/secrets.py`, holding the name-to-value resolver from a private file whose path is given by `FORGE_MODEL_SERVICE_SECRETS`. T006 must pass.
- [X] T009 [P] Write `factory/python/forge_factory/modelservice/artefacts.py`, which downloads to a target directory and records SHA-256 and size, and `factory/python/tests/test_modelservice_artefacts.py`, which tests resume, a wrong hash leading to refusal, and the lock writer. It is non-GPU and writes only under the given directory.
- [ ] T010 (host, non-GPU) Pin the S0 artefacts under `/mnt/data/forge-c/model-service/` on Omniverse2 using T009:
  - The `vllm/vllm-openai` image digest of the first release that supports the Qwen3.6 MoE architecture. Check its release notes; if no release supports it, record BLOCKED with the reason.
  - The Qwen3.6-35B-A3B weights: the publisher's FP8 checkpoint if one exists, else BF16 for FP8-at-load (research R2).
  - The Ubuntu 22.04 cloud image.
  - Ornith-1.5: no download. Record the SHA-256 of the GGUF blob and of the `llama-server` binary the owner lane uses today, read from the owner-lane profile pins (`models.allowed[*].digest`, `runtime.llama_server.model_blob_sha256`) and verified on disk.

  Pulling the image with `docker pull` allocates no GPU. Write the digests and SHA-256 values to `deploy/recipe/recipe.lock.json`, then commit the lock.
- [X] T011 [P] Write `factory/python/tests/test_modelservice_window.py`. It must fail first and use fakes for the lane control, the GPU probe and the model tier. It covers:
  - The steps run in order, per data-model QualificationWindow.
  - Start is refused when the production lane holds the GPU, or when the lane cannot drain before a timeout.
  - The tier stops and the lane is restored on any step failure (`ABORTED_RESTORED`).
  - The hard end is enforced.
  - `RESTORE_FAILED` raises an incident and never touches the production lane or the production observer.
  - Two windows never overlap (lock).
- [X] T012 Find and document the owner lane's existing safe-pause and resume controls in `specs/017-model-service-split/window-controls.md`. Candidates are the conductor pause or latch, the deployer latch file (`owner-lane-autodeploy`), and `afo/operations.py` requested stop with inference-owner quiescence. Name the exact command or file for each step: drain, idle check, model stop, model restart, resume. If a step has no existing non-signed control, mark it BLOCKED and note that the window controller must not invent one.
- [X] T013 Implement the GPU probe in `factory/python/model_tier/gpu.py`. It runs `nvidia-smi --query-compute-apps` and maps each holding PID to its unit or lane by cgroup. The production lane is identified from its unit names, and the probe is read-only.
- [ ] T014 Implement `factory/python/forge_factory/modelservice/window.py`, the window controller with the CLI `python -m forge_factory.modelservice.window run --plan <smoke|qualification> --max-minutes N`:
  - It uses only the T012 controls and the T013 probe.
  - It writes its record to `<state>/model-service/windows/<window_id>.json`.
  - It holds a host flock so two windows cannot run at once.
  - It accepts a dry-run mode.

  T011 must pass.

**Checkpoint**: identity, reasons, secrets, pinned artefacts and a tested window controller exist. User stories can start.

---

## Phase 3: User Story 1 - The factory runs as a tenant of an external model service (Priority: P1) 🎯 MVP

**Goal**: a `mode: external` factory never starts, stops or swaps a model server and never takes a GPU lock or lease. It reaches the model only through its gateway, pins and records the served-model identity, and maps every failure to a distinct reason.

**Independent Test**: with fakes, run the line-launch and stack paths in external mode and assert zero server and GPU actions. On the host, the acceptance runs in the first window (T044).

### Tests for User Story 1 ⚠️ (write first, must fail)

- [X] T015 [P] [US1] `factory/python/tests/test_modelservice_external_mode.py`, using fakes. With `model_service.mode: external` it checks that:
  - `lrtx/stack.py` `_start` and `serve` never spawn `llama-server` or Ollama;
  - `afo/line_launcher.py` never acquires `gpu.lock` and uses tenant-share admission instead;
  - `afo/line_stack_lifecycle.py` `swap_fence` is never set;
  - `afo/scheduler.py` and `afo/operations.py` treat "inference owner" as the tenant share;
  - the run evidence records `model_service_mode: external`;
  - in external mode, `lrtx/stack.py` `serve` (the workflow's serve node) makes no model change and only records which model the next part uses. Alternating author and inspector models produces zero factory swap actions (FR-029, SC-010);
  - the per-model identity pin holds across a service swap away and back (data-model);
  - with `mode: owned`, the existing tests `test_line_stack_lifecycle.py`, `test_lrtx_admission.py` and `test_cloud_line_scheduler.py` pass unchanged (FR-007).
- [X] T016 [P] [US1] `factory/python/tests/test_llm_gateway_external.py`, using a fake upstream. It covers:
  - The bearer key is sent upstream and never logged.
  - `chat_template_kwargs.enable_thinking=false` is on every request.
  - The identity is pinned on the first call; a changed `x-forge-model-identity` leads to 409 `identity_changed` and blocks the run.
  - A 429 is retried as a bounded wait, never as a model failure.
  - A 401 means `credential_refused` and no retry.
  - A connection drop after the send means `outcome_unknown`, with no zero-cost row.
  - An over-limit context is refused before sending (FR-006).
  - `reasoning_content` is stripped and counted.
  - Each meter row carries `identity_fingerprint`, `tenant_id` and `queue_ms` (ModelCallEvidence).
- [X] T017 [P] [US1] `factory/python/tests/test_modelservice_client.py`. It covers:
  - Loading the profile validates against `model-service-profile.schema.json`; external mode without `base_url`, `credential_ref`, `expected_identity` or `share` is refused.
  - The identity-read state machine per data-model: UNPINNED, PINNED, WAITING, QUEUED, BLOCKED.
  - The outage wait is bounded by `outage_wait_max_s`.

### Implementation for User Story 1

- [X] T018 [US1] Implement `factory/python/forge_factory/modelservice/client.py`: profile loading, the identity read (`/forge/v1/identity`, falling back to `/v1/models` via `identity.inferred_from_models_endpoint`), the run-link state machine and reason recording. T017 must pass.
- [ ] T019 [US1] Add the `model_service` block to the profile in `factory/python/forge_factory/lrtx/stack.py` (`settings`, `envmap`, `_start`, `serve`, `_serve_model`). In external mode:
  - follow the `cloud_bridge` precedent (`stack.py` near the `cloud_bridge(prof)` branch in `_start`): no Ollama, no llama-server, gateway upstream = `base_url`, key from `credential_ref`;
  - `serve` returns `{"model_swap": "BY_SERVICE", "model": m}` without any process action (FR-029);
  - the pre-run check verifies that every role's model is offered (`/forge/v1/catalog` or `/v1/models`). `owned` must stay byte-for-byte the same behaviour.
  **DEFERRED to the cutover (S6), 2026-11-08:** `lrtx/stack.py`, `afo/execution_lifecycle.py`, `afo/product_job.py`, `fabro/client.py` and `llm_gateway.py` are pinned by the owner lane's signed transport proof (`afo/line_native_transport.py` ADAPTERS); changing them now would break owner-lane launches (`ADAPTER_CHANGED`). External mode is delivered now by new modules only (qualification lane: `modelservice/lane.py`, `gateway_external.py`, `transport.py`, `client.py`). The owner lane's own external-mode edits are made with the re-measured proof the owner signs at cutover (T069 runbook).
- [ ] T020 [US1] In `factory/python/forge_factory/afo/line_launcher.py` (`gpu_lock`, the launch path near `with gpu_lock(cfg.gpu_lock)`, `plan`, status), skip the host GPU lock in external mode and record the step as `gpu_lock: NOT_USED_EXTERNAL`. Admission comes from the tenant share. Status and plan output name the mode.
  **DEFERRED to the cutover (S6), 2026-11-08:** `lrtx/stack.py`, `afo/execution_lifecycle.py`, `afo/product_job.py`, `fabro/client.py` and `llm_gateway.py` are pinned by the owner lane's signed transport proof (`afo/line_native_transport.py` ADAPTERS); changing them now would break owner-lane launches (`ADAPTER_CHANGED`). External mode is delivered now by new modules only (qualification lane: `modelservice/lane.py`, `gateway_external.py`, `transport.py`, `client.py`). The owner lane's own external-mode edits are made with the re-measured proof the owner signs at cutover (T069 runbook).
- [ ] T021 [US1] In `factory/python/forge_factory/afo/line_stack_lifecycle.py` (`_prelaunch`, `_native_handoff`, `swap_fence`), external mode means no model swap and no swap fence; swapping belongs to the service. Identity is pinned per model name, and a model whose identity differs from its pin yields `identity_changed` → BLOCKED.
  **DEFERRED to the cutover (S6), 2026-11-08:** `lrtx/stack.py`, `afo/execution_lifecycle.py`, `afo/product_job.py`, `fabro/client.py` and `llm_gateway.py` are pinned by the owner lane's signed transport proof (`afo/line_native_transport.py` ADAPTERS); changing them now would break owner-lane launches (`ADAPTER_CHANGED`). External mode is delivered now by new modules only (qualification lane: `modelservice/lane.py`, `gateway_external.py`, `transport.py`, `client.py`). The owner lane's own external-mode edits are made with the re-measured proof the owner signs at cutover (T069 runbook).
- [ ] T022 [US1] In `factory/python/forge_factory/afo/scheduler.py`, `afo/operations.py` and `afo/execution_lifecycle.py`, external mode replaces "inference owner lease" and "GPU idle observation" with the tenant-share state from the client. Requested stop no longer waits for native inference-owner quiescence; it waits for in-flight gateway calls to finish or reach `outcome_unknown`. T015 must pass.
  **DEFERRED to the cutover (S6), 2026-11-08:** `lrtx/stack.py`, `afo/execution_lifecycle.py`, `afo/product_job.py`, `fabro/client.py` and `llm_gateway.py` are pinned by the owner lane's signed transport proof (`afo/line_native_transport.py` ADAPTERS); changing them now would break owner-lane launches (`ADAPTER_CHANGED`). External mode is delivered now by new modules only (qualification lane: `modelservice/lane.py`, `gateway_external.py`, `transport.py`, `client.py`). The owner lane's own external-mode edits are made with the re-measured proof the owner signs at cutover (T069 runbook).
- [X] T023 [US1] (Delivered without editing the pinned `llm_gateway.py`: `modelservice/gateway_external.py` runs the unchanged gateway app with `modelservice/transport.py` as its upstream transport, and a test proves the source is byte-identical to the base.) Build the new gateway revision in `factory/python/forge_factory/llm_gateway.py`, keeping it backward compatible with the current behaviour when `FORGE_MODEL_SERVICE_MODE` is unset:
  - upstream bearer from `FORGE_MODEL_SERVICE_KEY_REF`, resolved via `modelservice/secrets.py`;
  - `enable_thinking=false`;
  - identity header check;
  - the reason mapping via `modelservice/reasons.py`;
  - context pre-check;
  - the ModelCallEvidence fields in `Meter.record`.

  T016 must pass. Record the new gateway SHA-256 in `specs/017-model-service-split/gateway-revision.md`, with the note that it is not valid for the owner lane until the cutover (research R7).
- [X] T024 [US1] Define the **qualification lane** in `deploy/recipe/factory-machine/qualification-lane.env.example` and `factory/python/forge_factory/modelservice/lane.py`. It has its own Fabro instance, data root (`/mnt/data/forge-c/model-service/qual-lane/`), ports (not 11460 and not the owner lane's), its own state directory and `mode: external`. Add a test in `factory/python/tests/test_modelservice_external_mode.py` that refuses any configuration whose ports or data root collide with the owner or production lane.
- [ ] T025 [US1] Run the CRE CHANGE gate for the US1 commit, via `promotion.evaluate` from the oracle checkout, with kind `CHANGE`. Store the decision insert-only in the host incidents store. No deploy to the owner lane: the qualification lane is not deployed until T044.

**Checkpoint**: external mode is fully covered by unit tests, and owned mode is unchanged.

---

## Phase 4: User Story 2 - A shared model service on Omniverse2 behaves like the production one (Priority: P1)

**Goal**: one model service owns the GPU and serves a catalog of models (Ornith-1.5 on llama.cpp, Qwen3.6 FP8 on vLLM), each at full capacity. It swaps on demand without the caller noticing (owner 2026-11-08), behind the tenant gateway, which provides keys, guaranteed shares, priorities, per-model verifiable identity and a metadata-only log. A simulated neighbour completes the setup.

**Independent Test**: unit and contract tests against a fake engine; the on-host smoke and contention checks run in the first window (T044).

### Tests for User Story 2 ⚠️ (write first, must fail)

- [X] T026 [P] [US2] `factory/python/tests/test_modelservice_tenant_gateway.py`, using a fake engine. It covers:
  - A missing or wrong key gets 401 and makes no engine call (FR-009).
  - Over `max_concurrency` plus `queue_limit` gets 429 `share_exhausted`; a queue wait beyond its limit gets 429 `queue_timeout`.
  - A guaranteed share holds while a neighbour saturates, and priority orders borrowed slots (FR-010, SC-003).
  - `max_context` is enforced as 400 `context_exceeded` with no truncation.
  - `enable_thinking=false` is enforced for tenants with `reasoning_mode: off`.
  - `/forge/v1/identity` and `x-forge-model-identity` work, and the gateway refuses to start on a lock mismatch (FR-011).
  - The outcome log contains no content: assert that no request or response text appears in the log bytes (FR-012).
  - Above the threshold, `reasoning_content` produces an infrastructure finding.
  - The start check rejects a configuration where the sum of guaranteed shares exceeds `max_sequences`.
- [X] T027 [P] [US2] Write `factory/python/tests/test_modelservice_swap.py`, using fake engines with load delays. It checks that:
  - alternating requests are each answered by the model they name;
  - the drain finishes before the unload, and nothing in flight is cut off;
  - per-model batching and `min_residency_s` hold;
  - `max_wait_s` leads to 429 `queue_timeout`;
  - a load failure or identity mismatch gives 503 `model_unavailable` to that model's waiters, the state returns to EMPTY, and no request is ever answered by another model;
  - an unknown model gives 404 `model_not_offered` with no state change;
  - a swap rate above `max_swaps_per_hour` raises a finding;
  - SwapEvent records hold metadata only and carry `warm`;
  - with warm strategies, a swap performs no model-file read from disk (the fake engine records the source of each load); when the RAM budget is short, that model falls back to a cold load with a finding and the request is still answered (FR-031);
  - tenant priority applies within a model queue, and guaranteed shares hold across swaps (FR-025 to FR-030, SC-009);
  - fairness: two factory tenants and a neighbour, each preferring a different model, all progress within `max_wait_s`, and a tenant flooding requests for the non-loaded model cannot take another tenant's guaranteed slots (FR-033, SC-012).
- [X] T028 [P] [US2] Write the contract test `factory/python/tests/test_modelservice_channel_contract.py`. Run the same client against two fakes:
  - (a) the full tenant gateway;
  - (b) a bare OpenAI-compatible service with only `/v1/models` and chat.

  It proves the factory works with (b) and that the identity there is `attested: false` (contracts/model-channel.md).

### Implementation for User Story 2

- [X] T029 [P] [US2] Write `factory/python/tests/test_model_tier_boundary.py`. It checks that no module under `factory/python/model_tier/` imports `forge_factory`, by AST scan of every import (FR-032, SC-012); that `model_tier/schemas/*.json` are byte-identical to `config/schemas/model-service/`; and that the `model_tier` modules name no factory concept (run, work order, node, lane) in their configuration keys.
- [X] T030 [US2] Implement `factory/python/model_tier/tenant_gateway.py`, using Starlette and httpx with no new dependency:
  - configuration per `config/schemas/model-service/tenant-config.schema.json`;
  - SHA-256 key check;
  - per-tenant semaphores with guaranteed and borrowed slots and a priority queue;
  - engine forwarding with the internal key;
  - identity endpoint and header;
  - the metadata outcome log (OutcomeRecord).

  T026 and T028 must pass.
- [X] T031 [US2] Implement `factory/python/model_tier/engines.py`. It builds engine definitions from the catalog:
  - `process` kind: starts the pinned binary with the explicit argument list from `catalog.yaml`. The model tier never reads a factory profile (FR-032).
  - `compose` kind: starts and stops a Compose service by name.
  - Health and `/v1/models` checks.
  - Waits for free GPU memory (`vram_mib`) through `model_tier/gpu.py` before a load.
- [X] T032 [P] [US2] Write `factory/python/tests/test_modelservice_ramstage.py`. It checks that:
  - staging copies to the stage directory with verification against the pinned SHA-256 (a mismatch is refused and the copy is deleted);
  - `MemAvailable` minus reserve below the need leads to no staging and a `cold` decision with a finding;
  - the residency check (`mincore`, faked) below 95% leads to a re-stage plus a cold load for this swap;
  - a changed size or inode is detected;
  - the stage directory is 0700 and the files are 0600;
  - `unstage` removes only Forge-C files.
- [X] T033 [US2] Implement `factory/python/model_tier/ramstage.py`: stage, verify, residency check via `mincore` through `ctypes`, budget check from `/proc/meminfo`, unstage. Add the warm strategies to `model_tier/engines.py`:
  - `vllm_sleep`: POST `/sleep?level=1` and `/wake_up` on the internal engine URL, with health and identity checked after wake;
  - `ram_staged_file`: llama.cpp started on the staged path.

  T032 must pass.
- [X] T034 [US2] Implement `factory/python/model_tier/swap.py`:
  - catalog loading, validated against `config/schemas/model-service/model-catalog.schema.json` and the lock;
  - per-model queues;
  - the state machine EMPTY / LOADING / SERVING / DRAINING / UNLOADING (data-model);
  - the swap policy;
  - SwapEvent records;
  - the `x-forge-swap-ms` header;
  - warm-up at tier start (stage Ornith, load Qwen3.6 then sleep it, serve the first requested model).

  Wire it into the request path of `tenant_gateway.py`. The swap sequence is ported from `lrtx/stack.py` `_serve_model` (refuse while requests are in flight, wait for VRAM, fail closed). T027 must pass.
- [ ] T035 [US2] Write `deploy/recipe/model-tier/catalog.yaml` for the Omniverse2 site:
  - Ornith-1.5 GGUF Q8 as `process`, with today's full settings generated from the owner-lane profile by `factory/python/forge_factory/modelservice/catalog_gen.py` (factory side, reusing `lrtx/stack.py` `llama_server_spec`), never retyped by hand;
  - Qwen3.6-35B-A3B FP8 on vLLM as `compose`, with `warm_strategy: vllm_sleep`, `--enable-sleep-mode`, `VLLM_SERVER_DEV_MODE=1` (internal network only) and unlimited memlock;
  - Ornith with `warm_strategy: ram_staged_file` and `stage_dir: /dev/shm/forge-model-tier`;
  - `ram_budget_gib: 80` and `ram_reserve_gib: 24`;
  - initial `swap_policy` values marked "to be measured in T044".

  Also write `deploy/recipe/model-tier/tenant-gateway.service`, a user systemd unit for the gateway and swap controller. It is enabled only inside windows until the cutover.
- [X] T036 [P] [US2] Implement `factory/python/model_tier/neighbour.py`, the simulated second tenant. It is configurable for concurrency, prompt size and duration, and records its own latencies (metadata only). It uses synthetic prompts only and never customer or vendor inputs.
- [X] T037 [P] [US2] Write `deploy/recipe/model-tier/gateway.Dockerfile`, for sites that run the gateway in a container (a production option). It uses a pinned Python base image digest, installs only the factory package's runtime dependencies, runs as non-root, and records its digest in the lock. On Omniverse2 the gateway runs as the host user unit from T035 (research R3b).
- [X] T038 [US2] Write `deploy/recipe/model-tier/compose.yaml`:
  - an `engine-qwen36` service (vLLM, digest from the lock, NVIDIA CDI GPU, internal network only, `--api-key` from secret, prefix caching on, request logging off, `max_model_len` and `max_num_seqs` from params, FP8 per research R2);
  - no `tenant-gateway` service on Omniverse2, which uses the T035 host unit; its published port is the only route in, bound to the address in params;
  - read-only model volume mount.

  Also write `deploy/recipe/model-tier/tenants.example.yaml`, with tenants `forge-qual`, `forge-owner` (`enabled: false` until cutover) and `sim-neighbour`, hashes only, and `allowed_models` for each tenant.
- [X] T039 [US2] Add `compose config` validation and a lint check to `factory/python/tests/test_modelservice_recipe.py` (skipped with NOT_RUN if Docker is absent on the test machine). The check: no published engine port, the GPU only on engine services, no `--enable-log-requests` (or equivalent) flag on the engine.

**Checkpoint**: the tenant gateway and the model-tier definition are tested offline.

---

## Phase 5: First window — on-host acceptance of US1 + US2 (S4) [WINDOW]

**Purpose**: the first real use of the GPU by the model tier: a smoke test, the KV capacity check, identity and contention. It proves US1 and US2 on the host.

- [ ] T040 (host, non-GPU) Install the qualification lane from the T025-gated commit into `/mnt/data/forge-c/model-service/qual-lane/`, using the T024 configuration. Units are disabled until a window. Verify that there are no port or data-root collisions with the owner or production lanes.
- [ ] T041 (host, non-GPU) Create the private secret file `/mnt/data/forge-c/model-service/secrets/model-service.secrets` (0600, directory 0700) with generated tenant keys and the engine key. Put only the hashes in the live `tenants.yaml`. Nothing goes into git.
- [ ] T042 Define the window plan `smoke` in `factory/python/forge_factory/modelservice/window_plans.py`:
  1. Tier start and identity verify.
  2. KV capacity check against at least 2 × 65,536, else apply the R2 fallbacks in order and record each deviation.
  3. Ten factory calls through the qualification-lane gateway.
  4. The neighbour saturates for 10 minutes while the factory runs a bounded SWE.1 part.
  5. Swap measurements: Ornith to Qwen3.6 and back, ten times each, recording drain, unload and load times, `warm`, and the sleeping vLLM's GPU residue. Report the p95 per direction against SC-011 (30 s) and the cold first load separately.
  6. An alternating-model factory part (author on one model, inspector on the other), checking that 100% of answers come from the named model and that factory components make 0 swap actions (SC-009, SC-010).
  7. Write the measured `swap_policy` values and the factory's `queue_wait_max_s` into `catalog.yaml` and `params/omniverse2.yaml`. Check that `queue_wait_max_s` is at least the worst swap time plus `max_wait_s`.
  8. Tier stop.

  Add a test in `factory/python/tests/test_modelservice_window.py`.
- [ ] T043 Ask the owner, through the usual floor and summary channel, for the window limits: `max_minutes` and allowed hours. Until they answer, use the default of 120 minutes at a time when the owner lane is between orders. Record the values in `deploy/recipe/params/omniverse2.yaml` (`window_max_minutes`, `window_hours`).
- [ ] T044 [WINDOW] Run `python -m forge_factory.modelservice.window run --plan smoke`. Collect into `evidence/017/window-<id>/`:
  - the window record;
  - the identity;
  - the KV capacity;
  - the outcome-log metadata;
  - per-tenant latency;
  - the audit check that 0 factory model-server or GPU-lock actions occurred (SC-001);
  - 100% of calls carrying a fingerprint (SC-002);
  - 0 factory call failures under neighbour load (SC-003);
  - swap times in both directions, with p95 against SC-011;
  - SC-009 and SC-010.

  Outcome `ABORTED_RESTORED` is recorded as such, never as PASS.

**Checkpoint**: US1 and US2 accepted on the host, or BLOCKED with evidence.

---

## Phase 6: User Story 3 - The factory is requalified on the production-like model before any cutover (Priority: P2)

**Goal**: a side-by-side report, per phase and per node, of the current setup against the production-like setup, with deviations and blocking findings through CRE.

**Independent Test**: the report is generated from existing evidence plus qualification-window runs, and validated against `contracts/qualification-report.schema.json`.

### Tests for User Story 3 ⚠️

- [ ] T045 [P] [US3] `factory/python/tests/test_modelservice_qualify.py`. Build fixtures from the `model_exchanges` export layout (`nodes.csv` and `runs/<WO>__<run>/<node>/visit-N.jsonl`) and the run metrics. It checks:
  - Rows per (phase, node).
  - A missing side is `NOT_RUN`.
  - The verdict is never `QUALIFIED_FOR_OWNER_REVIEW` with an OPEN finding or a NOT_RUN phase.
  - Every deviation carries its production value.
  - The schema is valid.

### Implementation for User Story 3

- [ ] T046 [US3] Create `config/factory/qualification-set.yaml`. It lists every SWE phase the line has already passed on the current setup, with the baseline WO lineages and run IDs taken from evidence (for example the CRC HAL SWE.1 to SWE.6 lineage and the GPIO orders). Each entry links its evidence path. Include no entry without evidence.
- [ ] T047 [US3] Implement `factory/python/forge_factory/modelservice/qualify.py`, `report --out <dir>`. It reads the baseline from existing evidence and the per-node exchange export; it never replays C, B or L90 runs. It reads the candidate from qualification-lane runs, computes the measures per `contracts/qualification-report.schema.json` (including swaps and swap wait per phase from the SwapEvent records, FR-030), lists deviations from `params/omniverse2.yaml` against `params/production.yaml`, and writes JSON plus a plain-language markdown summary. T045 must pass.
- [ ] T048 [US3] Define the window plan `qualification` in `factory/python/forge_factory/modelservice/window_plans.py`. It queues fresh qualification-lane orders for the qualification-set phases, using the existing order mechanism for the qualification lane only. It resumes across windows from the last quality-checked part and stops cleanly at the window's hard end.
- [ ] T049 [US3] [WINDOW] Run qualification windows until every qualification-set phase has a candidate result or is explicitly BLOCKED, within the owner's window limits (T043). Evidence goes to `evidence/017/qualification/`.
- [ ] T050 [US3] For every phase that passes on the baseline and fails on the candidate, open a CAPA via the CRE registry, attach the evidence and set `blocking_findings[].capa_id`.
- [ ] T051 [US3] Produce the qualification report (`evidence/017/qualification/report.json` and `report.md`) and hand it to the owner on the floor and in the summary. The verdict is one of `QUALIFIED_FOR_OWNER_REVIEW`, `NOT_QUALIFIED` or `INCOMPLETE`.

**Checkpoint**: the owner has a report to decide on; no cutover has happened.

---

## Phase 7: User Story 4 - The environment is reproducible from a recipe (Priority: P2)

**Goal**: rebuild the mirror from the recipe alone, with fingerprint verification, a drift check and production parameters handed over.

**Independent Test**: `recipe plan`, `recipe verify` and `recipe drift` against the lock; a rebuild drill with 0 drift.

### Tests for User Story 4 ⚠️

- [ ] T052 [P] [US4] Extend `factory/python/tests/test_modelservice_recipe.py`. It checks that:
  - every parameter file validates against `recipe-params.schema.json`;
  - `plan --site production` prints every parameter with its production value or `confirmed: false`, and never prints a secret value;
  - `verify` fails on one changed SHA-256 and names the file;
  - `drift` reports image-digest, model-fingerprint and factory-revision differences;
  - the recipe tree contains no secret, via a grep for key patterns and the `secrets*` ignore rule.

### Implementation for User Story 4

- [ ] T053 [US4] Implement `factory/python/forge_factory/modelservice/recipe.py` with the subcommands `plan`, `verify`, `apply` and `drift`, all taking `--site`:
  - `apply` brings up the model tier (Compose) and the factory machine (container stand-in, or VM when available), and refuses to finish on any mismatch.
  - On Omniverse2, `apply` of the model tier is allowed only from inside a window (T014).

  T052 must pass.
- [ ] T054 [P] [US4] Complete `deploy/recipe/README.md`:
  - build Omniverse2;
  - build production (parameter mapping table: Omniverse2 value, production value, confirmed);
  - the list of what the Omniverse2 build does not prove (FP8 against BF16, 48 GB against 141 GB, sequences, container stand-in);
  - a reference to `specs/017-model-service-split/contracts/model-channel.md` as the interface the platform team must provide.
- [ ] T055 [P] [US4] Write the optional `deploy/recipe/factory-machine/packer/forge-c.pkr.hcl`, which uses the same `provision.sh` and cloud-init. Mark it optional in its header, because Packer is BUSL-1.1 (research R10).
- [ ] T056 [US4] [WINDOW] Run the rebuild drill: tear down the tier and the factory machine (keeping data), `recipe apply --site omniverse2`, then `recipe drift`. Record the duration and 0 drift findings in `evidence/017/rebuild-drill/` (SC-004).

**Checkpoint**: the recipe rebuilds the mirror, and the production parameters are documented.

---

## Phase 8: User Story 5 - The factory machine is isolated like the production VM (Priority: P3)

**Goal**: the factory runs inside its own boundary whose only route to the model is the model channel. That is a container now, and a VM once the `kvm` group is granted.

**Independent Test**: isolation checks from inside the boundary, while a factory phase still runs.

### Tests for User Story 5 ⚠️

- [ ] T057 [P] [US5] `factory/python/tests/test_modelservice_isolation.py`. It unit-tests the isolation checker with a fake environment: GPU device present means FAIL; host model path visible means FAIL; a host port other than the channel reachable means FAIL; the stand-in report lists the unproven properties.

### Implementation for User Story 5

- [ ] T058 [US5] Write `deploy/recipe/factory-machine/provision.sh`. It installs and provisions the factory exactly as `docs/ONPREM-DEPLOYMENT.md` "Software on the VM" describes, with version pins from the lock and no GPU packages. It is idempotent, and is used both by cloud-init and by the container build.
- [ ] T059 [US5] Write `deploy/recipe/factory-machine/cloud-init/user-data.yaml` (service account `forge`, lingering, data volume at `/srv/forge-c`, runs `provision.sh`) and `deploy/recipe/factory-machine/container/Dockerfile` (the stand-in, built by running the same `provision.sh`).
- [ ] T060 [US5] Implement `factory/python/forge_factory/modelservice/isolation.py`, the in-boundary checker that writes a stand-in report, and wire the factory container into `deploy/recipe/model-tier/compose.yaml` or a sibling `deploy/recipe/factory-machine/compose.yaml`:
  - an `--internal` network shared only with `tenant-gateway`;
  - no GPU;
  - only the data volume mounted.

  T057 must pass.
- [ ] T061 [US5] (host, non-GPU) Start the factory container stand-in and run the isolation checks and quickstart step 3. Record them in `evidence/017/isolation/`.
- [ ] T062 [US5] VM path (BLOCKED until the `omniverse2` user is in group `kvm`; owner 2026-11-08 says an admin can do this). Write `deploy/recipe/factory-machine/vm/run-vm.sh`:
  - qemu from host packages or a pinned image, as the admin approves;
  - a seed ISO built with `genisoimage`;
  - network forwarding only to the tenant gateway.

  Do not pass `/dev/kvm` through Docker (research R9). Record BLOCKED with the reason until access is granted.

**Checkpoint**: container isolation proven; the VM path is ready or explicitly BLOCKED.

---

## Phase 9: User Story 6 - Per-node model exchange log, tenant-scoped (Priority: P3)

**Goal**: capture moves into the factory gateway revision, behind the existing switch. It covers only the factory's own traffic, contains no reasoning or secrets, and is private.

**Independent Test**: with the switch off, 0 bytes are written; with it on, one record per call, tagged with run, node and visit, appears in the per-node export.

### Tests for User Story 6 ⚠️

- [X] T063 [P] [US6] `factory/python/tests/test_llm_gateway_capture.py`. It checks that:
  - with the switch file missing or false, no capture file is written;
  - with it true, one record per call has run, node, visit, tenant and identity fingerprint, uses 0600 files in 0700 directories, has no `reasoning*` keys, no `forge_execution` and no secrets, and is written after `strip_reasoning`;
  - a capture failure never fails the call.
- [X] T064 [P] [US6] Extend `factory/python/tests/test_model_exchanges.py`. When gateway capture records exist for a run, the exporter uses them (one per call, with no double count against Fabro events or structured captures), and `by-node/<node>.md` keeps its format.

### Implementation for User Story 6

- [X] T065 [US6] (Delivered in `modelservice/transport.py`, because `llm_gateway.py` is pinned by the owner lane's signed proof; the exporter joins each record to its turn by model, exact prompt tokens and time.) Add the capture tap to the gateway revision in `factory/python/forge_factory/llm_gateway.py`. It is behind `<state>/model-exchanges/capture.json` `"gateway": true`, separate from the existing `"structured"` key, and reuses the redaction from `lrtx/structured.py` `_capture`. The run, node and visit come from the request's `forge_execution` binding, which is read and never written. T063 must pass.
- [X] T066 [US6] Teach `factory/python/forge_factory/lrtx/model_exchanges.py` `export` to read `<state>/model-exchanges/gateway/<run>/...` records with de-duplication. T064 must pass.

**Checkpoint**: the per-node log works in the new shape; capture is off by default.

---

## Phase 10: Polish, cutover preparation and cross-cutting

- [ ] T067 [P] Write the ADR `docs/adr/ADR-DA-027-model-service-split.md` with the decisions R1 to R12, why the factory never owns the GPU in production, and why the gateway revision waits for the cutover.
- [ ] T068 [P] Update `docs/ONPREM-DEPLOYMENT.md` "Questions for Infrastructure":
  - add "does the service offer the Forge-C identity extension, or only `/v1/models`?";
  - add a per-tenant share question;
  - link `deploy/recipe/README.md` and `contracts/model-channel.md`.

  Keep the existing text unchanged otherwise.
- [ ] T069 Write the owner-only cutover runbook `specs/017-model-service-split/cutover-runbook.md`, per data-model CutoverRecord:
  - what the owner signs (the re-measured transport proof for the new gateway SHA-256);
  - how `forge-owner` is enabled;
  - how the owner lane's profile switches to `mode: external`;
  - the way back (previous signed control and previous gateway);
  - how the way back is rehearsed before approval (SC-006).

  Claude does not execute the cutover.
- [ ] T070 Run the full factory test suite, `ruff` and `python3 tests/spec/validate_design.py` on the implementation branch. Record the results in `specs/017-model-service-split/evidence.md`, and confirm that the owned-mode tests are unchanged against the base SHA (T001).
- [ ] T071 Run the quickstart steps 1 to 6 and record each as PASS, FAIL, NOT_RUN or BLOCKED, with evidence paths, in `specs/017-model-service-split/evidence.md`. Then open a draft PR to `main` for owner review; it is merged only after the owner accepts, with merge commits only.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: needs Setup. Blocks all stories. T010 (artefact pull) can run in the background while T011 to T014 are written.
- **US1 (Phase 3)** and **US2 (Phase 4)**: need Foundational. They are independent of each other and can run in parallel.
- **First window (Phase 5)**: needs US1 (T025 gate) and US2 (T038). This is the first GPU use.
- **US3 (Phase 6)**: needs Phase 5 to complete (smoke `COMPLETED`).
- **US4 (Phase 7)**: T052 to T055 need only Foundational and US2's Compose file; T056 (drill) needs Phase 5.
- **US5 (Phase 8)**: needs Foundational and US2's network definition (T038); it does not need the GPU. T062 is BLOCKED on the `kvm` grant.
- **US6 (Phase 9)**: needs T023, the gateway revision.
- **Polish (Phase 10)**: after the stories in scope. T069 has no code dependency.

### User story dependencies

- **US1:** independent offline. Its host acceptance shares the first window with US2.
- **US2:** independent offline.
- **US3:** needs US1 and US2 accepted on the host.
- **US4:** needs US2's definitions; its drill needs a window.
- **US5:** needs US2's network.
- **US6:** needs US1's gateway revision.

### Within each story

Tests come first and must fail; then implementation; then the CRE gate before any host install.

## Parallel Opportunities

- **Setup:** T002, T003 and T004.
- **Foundational:** T005, T006, T009 and T011 (tests and artefacts); T010 runs in the background on the host.
- **US1:** T015, T016 and T017 in parallel; then T019, T020 and T021, which touch different files, can run in parallel after T018.
- **US2:** T026, T027, T028 and T032 in parallel; then T030 → T031 → T033 → T034; T036, T037 and T035 in parallel with T030.
- **US1 and US2:** fully parallel until Phase 5.
- **US4, US5 and US6:** offline parts in parallel after their prerequisites.

### Parallel example: User Story 2

```text
Task: "T026 tenant gateway tests in factory/python/tests/test_modelservice_tenant_gateway.py"
Task: "T027 swap tests in factory/python/tests/test_modelservice_swap.py"
Task: "T028 channel contract test in factory/python/tests/test_modelservice_channel_contract.py"
Task: "T036 neighbour load generator in factory/python/model_tier/neighbour.py"
Task: "T037 gateway image in deploy/recipe/model-tier/gateway.Dockerfile"
```

## Implementation Strategy

### MVP (US1 and US2 through the first window)

1. Phase 1 and Phase 2, including the pinned artefacts and the tested window controller.
2. US1 and US2 offline, in parallel.
3. Phase 5: the first window. The factory runs as a tenant of the shared service on the host, and SC-001 to SC-003 are measured.
4. **Stop and report:** the owner sees the production shape working on Omniverse2, with its stated deviations.

### Incremental delivery

1. MVP.
2. US3, requalification. The owner gets the report (S5).
3. US4, the recipe and drill. The platform team gets the recipe.
4. US5, isolation: the container now, the VM after the `kvm` grant.
5. US6, the exchange log in the new shape.
6. The cutover (S6) happens only by the owner (T069 runbook).

### Notes

- **[WINDOW]** tasks are the only ones that may use the GPU. Every other host task is non-GPU.
- No task edits signed controls, the production lane or the owner's signing material.
- Every factory commit goes through CRE before any host install. The owner lane is never redeployed by this feature before the cutover.
