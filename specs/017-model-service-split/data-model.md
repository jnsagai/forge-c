# Data Model: Model-Service Split (feature 017)

All records are files, written atomically. Privacy class is noted per entity:

- **public-safe:** may appear in review packages.
- **private:** stays under the data root (0600/0700) and is never exported.
- **secret:** never written by Forge-C; referenced by name only.

## ServedModelIdentity *(public-safe)*

| Field | Type | Rule |
| --- | --- | --- |
| `name` | string | The served model name, e.g. `qwen3.6-35b-a3b` |
| `revision_fingerprint` | sha256 hex | SHA-256 over the sorted list of `(relative_path, sha256)` for every weight file, plus tokenizer and chat-template digests |
| `precision` | enum `bf16 \| fp8 \| awq-int4 \| other` | Must equal the recipe parameter |
| `kv_cache_dtype` | string | Default or `fp8` (a deviation is listed in the report) |
| `reasoning_mode` | enum `off \| on` | Must be `off` for production-like qualification |
| `context_limit` | int | `max_model_len` reported by the engine |
| `max_sequences` | int | The engine's concurrent sequence limit |
| `engine` | `{name, version, image_digest}` | Pinned in the lock |
| `attested` | bool | True when served by `/forge/v1/identity`; false when inferred from `/v1/models` plus the recipe (stated deviation) |

**Validation:**
- At service start, the tenant gateway recomputes `revision_fingerprint` from the mounted weights and refuses to serve if it differs from the lock.
- The factory pins the identity on its first call; any later difference means `identity_changed`, which blocks the run.

## ModelCatalogEntry *(public-safe; one catalog per site, `deploy/recipe/model-tier/catalog.yaml`)*

| Field | Type | Rule |
| --- | --- | --- |
| `model` | string | The name tenants put in `model`; unique in the catalog |
| `engine` | `llama.cpp \| vllm` | Engine kind; the image or binary is pinned in the lock |
| `launch_kind` | `compose \| process` | `compose` for vLLM; `process` for the pinned host llama.cpp server binary Ornith uses today |
| `compose_service` | string | The engine's Compose service name (`compose` only) |
| `engine_url` | URL | The engine's internal address; never published |
| `full_capacity` | object | Context per sequence, sequences, KV cache type, batch sizes, GPU memory share, speculative or MTP settings. These are the model's own full settings and are never shrunk to co-reside |
| `reasoning_mode` | `off \| on` (+ `effort`) | Ornith keeps today's setting; Qwen3.6 is `off` |
| `identity` | ServedModelIdentity | Pinned; verified after every load |
| `vram_mib` | int | Expected GPU memory when loaded; the swap waits for this much free before loading |
| `load_timeout_s` | int | The load fails after this |
| `warm_strategy` | `vllm_sleep \| ram_staged_file \| none` | How the model stays ready in host RAM while off the GPU (FR-031, research R3c) |
| `ram_gib` | number | Host RAM the warm copy needs; counted against `ram_budget_gib` |

**Validation:** at catalog load, every entry's identity must match the lock. On Omniverse2 the sum of `vram_mib` over entries marked `co_resident: true` must fit the GPU; by default no entry is co-resident.

## SwapPolicy *(public-safe)*

`{drain_max_s, min_residency_s, swap_after_wait_s, max_wait_s, max_swaps_per_hour, idle_unload_s?, ram_budget_gib, ram_reserve_gib, stage_dir}`

These are recipe parameters, measured in the first window (research R3b).

## SwapEvent *(public-safe; metadata only, appended to the outcome log)*

`{ts, swap_id, from_model, to_model, trigger: queue_age|idle|explicit_window, drain_ms, unload_ms, load_ms, warm: bool, identity_verified, outcome: OK|LOAD_FAILED|IDENTITY_MISMATCH|DRAIN_TIMEOUT, waiting_requests, tenants_waiting}`

**State of the model tier:**

```text
EMPTY --request(m)--> LOADING(m) --healthy+identity ok--> SERVING(m)
SERVING(m) --request(n!=m) and policy says swap--> DRAINING(m) --in-flight done or drain_max_s--> UNLOADING(m) --GPU free--> LOADING(n)
LOADING(n) --fail/identity mismatch--> EMPTY (waiting requests for n -> 503 model_unavailable; others re-trigger normally)
any --request(model not in catalog)--> refused 404 model_not_offered (no state change)
```

## Tenant *(the key hash is private; the rest is public-safe)*

| Field | Type | Rule |
| --- | --- | --- |
| `tenant_id` | slug | Unique, e.g. `forge-qual`, `forge-owner`, `sim-neighbour` |
| `key_sha256` | sha256 hex | Only the hash is stored; the key itself is a secret, referenced by name in the recipe |
| `guaranteed_concurrency` | int ≥ 0 | Slots reserved for this tenant; the sum over tenants must not exceed the engine's `max_sequences` |
| `max_concurrency` | int ≥ guaranteed | May borrow idle slots up to this limit |
| `queue_limit` | int ≥ 0 | Waiting requests beyond concurrency; over the limit → 429 `share_exhausted` |
| `queue_timeout_s` | int | Longest wait in the queue → 429 `queue_timeout` |
| `priority` | int | Lower value wins for borrowed slots |
| `max_context` | int ≤ `context_limit` | A request estimated above it → 400 `context_exceeded` (never truncated) |
| `allowed_models` | list | Catalog models this tenant may name; anything else is refused with `model_not_offered` |
| `reasoning_mode` | `off \| on` | Enforced through `chat_template_kwargs` for models whose catalog entry is `off` |
| `enabled` | bool | False → 401 for every request |

## OutcomeRecord *(public-safe; written by the tenant gateway, metadata only)*

`{ts, tenant_id, request_id, model, model_fingerprint_prefix, status, forge_reason?, queue_ms, swap_wait_ms, swap_id?, total_ms, prompt_tokens, completion_tokens, cached_tokens?, reasoning_tokens_stripped}`

It never contains messages, tool arguments, content or reasoning text.

## ModelServiceProfile *(public-safe; factory side, in the line profile or `config/factory/model-service.yaml`)*

| Field | Type | Rule |
| --- | --- | --- |
| `mode` | `owned \| external` | Default `owned` (unchanged behaviour) |
| `base_url` | URL | `external` only; must be the model channel and nothing else |
| `credential_ref` | name | Resolved from the private secret file; the value is never logged |
| `ca_bundle_ref` | name? | For an internal CA |
| `expected_identity` | map model → ServedModelIdentity subset | Per model: `precision`, `reasoning_mode` and minimum `context_limit`. Before a run, every role's model must be in this map and offered by the service |
| `share` | `{concurrency, queue_wait_max_s}` | Sets gateway admission; must be ≤ the tenant's `max_concurrency` |
| `outage_wait_max_s` | int | Bounded wait for unreachable or restarting service |

**State transitions of a run's model link (external mode):**

```text
(per model name)
UNPINNED --first identity read--> PINNED --identity differs--> BLOCKED(identity_changed)
PINNED --service swaps away and back with the same identity--> PINNED   (a swap is only a wait)
PINNED --unreachable/channel error--> WAITING --recovered within outage_wait_max_s--> PINNED
WAITING --timeout--> BLOCKED(service_unreachable | channel_interrupted)
PINNED --401/403--> BLOCKED(credential_refused)          (incident; no blind retry)
PINNED --429 share_exhausted/queue_timeout--> QUEUED --slot--> PINNED  (bounded by queue_wait_max_s, never a model failure)
in-flight call lost --> outcome_unknown recorded; normal bounded recovery decides
```

## ModelCallEvidence *(public-safe; one row per call, extends today's gateway meter row)*

The existing meter fields, plus `{model_service_mode, identity_fingerprint, tenant_id, forge_reason?, queue_ms}`. There is no content.

## ExchangeCapture *(private; only when the capture switch is on)*

`{ts, run_id, node_id, visit, tenant_id, identity_fingerprint, request: <redacted messages+tools>, reply: <redacted text + tool calls>, usage, timing_ms, reasoning_tokens_stripped}`

The `reasoning` keys are removed before the write. The `forge_execution` binding is never written.

## QualificationWindow *(public-safe)*

| Field | Rule |
| --- | --- |
| `window_id`, `planned_start`, `hard_end`, `max_minutes` | `max_minutes` is set by the owner; `hard_end` is enforced |
| `steps[]` | `drain_requested`, `lane_idle`, `lane_model_stopped`, `gpu_free_verified`, `tier_started`, `identity_verified`, `qualification_ran`, `tier_stopped`, `gpu_free_verified`, `lane_model_restarted`, `lane_resumed`, each with timestamp and result |
| `outcome` | `COMPLETED \| ABORTED_RESTORED \| RESTORE_FAILED` (`RESTORE_FAILED` → incident and owner notification; the conductor stays OBSERVE) |
| `refusal` | Set if the production lane holds the GPU or the owner lane cannot drain safely |

## QualificationReport *(public-safe)*

See `contracts/qualification-report.schema.json`.

- One row per (phase, node) with both setups side by side.
- Plus `deviations[]` (each with the production value) and `blocking_findings[]` (each with a CAPA id).
- A comparison without a run on one side is `NOT_RUN`.

## Recipe and RecipeLock *(public-safe; secrets by name only)*

- **Recipe parameters:** see `contracts/recipe-params.schema.json`. Each has a `site` value for `omniverse2` and for `production`, plus `confirmed: bool` for production values still awaiting the platform team.
- **Lock:** `{images: {name: digest}, model_files: [{path, sha256, bytes}], identity, factory_revision, fabro_version, toolchain: {name: version}}`.
- **DriftFinding:** `{component, expected, actual, severity}`.

## CutoverRecord *(public-safe)*

`{lane, from_shape, to_shape, qualification_report_sha256, owner_approval_ref, transport_proof_ref, rollback_procedure, rollback_rehearsed_at, executed_at?}`

It is created only after the owner approves. A rehearsal of the way back is required before `executed_at` can be set (SC-006).
