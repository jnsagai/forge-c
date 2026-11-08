# Research: Model-Service Split (feature 017)

Date: 2026-11-08. Facts probed on Omniverse2 the same day are marked *(probed)*.

## Host facts *(probed)*

| Fact | Value |
| --- | --- |
| GPU | RTX 6000 Ada, 49,140 MiB, driver 580.178.04. The owner lane's `llama-server` (Ornith-1.5 GGUF Q8) holds 41,816 MiB |
| CPU / RAM / disk | 24 cores, 125 GB RAM, `/mnt/data` 1.8 TB with 1.3 TB free |
| Containers | Docker 29.5.3, Compose v5.1.4, NVIDIA CDI spec at `/var/run/cdi/nvidia.yaml`; user is in group `docker` |
| Virtualisation | `/dev/kvm` belongs to `matss` and group `kvm`; user not in `kvm`; no `qemu`, `lxd`, `incus` or `virsh` installed; `genisoimage` present |
| Model files | Qwen3.6-35B-A3B exists only as an Ollama Q4 model (22 GB). No safetensors weights for vLLM yet |
| Python | 3.10.12 system; factory uses `uv` Python 3.13 |

## R1. Inference engine for the model tier

- **Decision:** vLLM, OpenAI-compatible server, from the official `vllm/vllm-openai` container image pinned by digest. The digest is the first release whose supported-model list includes the Qwen3.6 MoE architecture, and it is recorded in the recipe lock (FR-017).
- **Rationale:** production names vLLM (`docs/ONPREM-DEPLOYMENT.md`). The same engine removes a whole class of differences: chat template, tool-call parser, prefix caching and the `chat_template_kwargs` switch for non-thinking. The container already works with NVIDIA CDI on the host.
- **Alternatives considered:**
  - *Keep Ollama or llama-server:* this is today's engine, so it proves nothing about production.
  - *SGLang:* comparable, but production states vLLM.
  - *pip install on the host:* not reproducible as a recipe and pollutes a shared host.

## R2. Precision that fits 48 GB

- **Decision:** FP8 weights. Use the publisher's FP8 checkpoint if one is published; otherwise quantise the BF16 checkpoint with vLLM's `--quantization fp8` at load. Keep the KV cache in the model's default dtype first.
- **Acceptance at startup:** the engine must report a KV capacity of at least 2 sequences × 65,536 tokens, the factory's per-agent limit. If it does not, apply the fallback steps in order and record each one as a stated deviation (FR-015):
  1. FP8 KV cache.
  2. One sequence at 65,536 tokens.
  3. A 4-bit AWQ checkpoint.
- **Rationale:**
  - BF16 needs about 70 GB, so it cannot fit.
  - FP8 is the closest numerical behaviour to BF16 that fits: about 35 GB of weights, leaving roughly 8 GB for KV at 0.90 GPU utilisation.
  - Production's peak prompt is 39,524 tokens, so one 65k sequence is the floor for a faithful qualification.
- **Alternatives considered:**
  - *Ollama Q4 (already on disk):* wrong engine, and the furthest precision from production.
  - *AWQ first:* more KV room, but a bigger quality gap to BF16. It stays the last fallback.

## R3. Tenant gateway (keys, shares, priorities, identity)

- **Decision:** a thin, audited Forge-C tenant gateway in front of vLLM, in the same Python and ASGI stack as the existing `llm_gateway` (Starlette and httpx, already factory dependencies).
  - vLLM listens only on an internal container network and requires its own internal key.
  - The tenant gateway is the only published port.
  - It keeps a per-tenant API key file with the keys stored as SHA-256 hashes.
  - It enforces a per-tenant concurrency limit, a queue limit and a guaranteed share, with priority order between tenants.
  - It writes a metadata-only outcome log and serves `GET /v1/models` plus a `GET /forge/v1/identity` extension.
- **Rationale:**
  - The platform team's stack and authentication are unknown (owner 2026-11-08). The factory must therefore depend only on what any OpenAI-compatible service offers: chat completions, a bearer key and `/v1/models`.
  - A thin gateway is small enough to test fully (constitution V and X: thin audited wrappers).
  - It makes "guaranteed share under a saturating neighbour" (SC-003) observable.
- **Alternatives considered:**
  - *LiteLLM proxy:* its virtual keys and budgets need Postgres, and parts of its priority and tenant controls are outside the open-source core. That adds a stateful dependency the production platform may not use.
  - *vLLM `--api-key` alone:* a single key, with no shares and no tenants.
  - *nginx `limit_conn` per key:* cannot express a guaranteed share or report identity.

## R4. Served-model identity

- **Decision:** the identity has five fields: `name`, `revision_fingerprint` (SHA-256 of the sorted weight-file digests plus the tokenizer and chat-template digests), `precision`, `reasoning_mode` and `context_limit`.
  - The recipe computes it at build time and verifies it when the service starts. On a mismatch the tenant gateway refuses to serve.
  - The tenant gateway exposes it at `/forge/v1/identity` and in the `x-forge-model-identity` response header, which carries a fingerprint prefix.
  - On a service that lacks the extension (possibly production), the factory falls back to the `/v1/models` `id` and `max_model_len` plus the recipe's declared values, and states "identity not service-attested" as a deviation.
- **Rationale:**
  - FR-003 and FR-011 require the identity.
  - The response header lets the factory gateway detect a change between calls at no extra cost (User Story 1, scenario 2).
- **Alternatives considered:** trusting the `model` string only. Rejected because an operator can swap weights under the same name.

## R5. Non-thinking mode

- **Decision:** the factory gateway sends `chat_template_kwargs: {"enable_thinking": false}` on every request in external mode. The tenant gateway also enforces it per tenant policy (`reasoning_mode: off`). Any `reasoning_content` that still arrives is stripped and counted (existing `strip_reasoning`) and raises an infrastructure finding after a configurable count.
- **Rationale:**
  - Production is non-thinking.
  - Today's lane runs reasoning effort "medium", and about 98% of SWE.1 author output is hidden reasoning (per-node exchange log, 2026-11-08). Requalification must measure the change (FR-014), not assume it.

## R6. Factory "external model service" mode

- **Decision:** a new `model_service` block in the line profile selects `mode: owned | external`. `owned` is today's default and is unchanged (FR-007). In `external` mode:
  - The stack lifecycle (`afo/line_stack_lifecycle.py`, `lrtx/stack.py`) does not start, stop or swap any server. The GPU lock and the inference-owner lease (`afo/scheduler.py`, `afo/operations.py`, `afo/line_launcher.py`) are replaced by a **tenant-share admission**: the factory gateway's existing `admission.py` concurrency is set from the tenant's share, and "share exhausted" (HTTP 429 with `forge_reason: share_exhausted`) becomes a bounded wait.
  - A **model-service client** (`modelservice/client.py`) reads the identity before the first call and pins it on the run. It maps failures to distinct reasons: `service_unreachable`, `credential_refused`, `channel_interrupted`, `outcome_unknown` and `identity_changed`.
  - Every model call's evidence row carries the identity fingerprint.
- **Rationale:** this keeps one code path for everything above the gateway. Only ownership and admission differ, which is the smallest change that meets FR-001 to FR-006.

## R7. Gateway pinning and the cutover

- **Fact:** the owner lane's signed control binds the `llm_gateway.py` SHA-256 through the native transport proof (`afo/line_native_transport.py`, `owner_profile_bootstrap.require_context`). Any gateway edit breaks owner-lane launches until the proof is re-measured under the owner's signed control.
- **Decision:**
  - All gateway changes for this feature (upstream key, identity header check, non-thinking kwargs, tenant-scoped capture) go into a new gateway revision. Only the **qualification lane** uses it: a separate lane with its own Fabro instance, data root and port, which never touches the owner lane's proof.
  - The owner lane moves to that revision only at cutover (FR-020), with a re-measured transport proof that the owner signs.
  - The way back is the previous signed control and the previous gateway, kept unchanged.
- **Rationale:** hard limits. The signed controls are never edited by Claude, and the production lane stays untouched.

## R8. Qualification windows (FR-019 option C)

- **Decision:** a window controller (`modelservice/window.py`) runs these steps:
  1. Ask the owner lane to drain through its existing pause mechanism (no new orders; the running part finishes or reaches a checkpoint).
  2. Wait until the lane reports idle, then stop its model server through the lane's own lifecycle.
  3. Verify that GPU memory is free.
  4. Start the model tier and run the qualification set.
  5. Stop the model tier and verify that the GPU is free.
  6. Restart the owner lane's model server and lift the pause.

  Further rules:
  - The window has a hard end time and an owner-set maximum length.
  - If any step fails, the controller restores the owner lane first and records an incident.
  - The production lane's ports and units are never touched; the controller refuses to start if the production lane holds the GPU.
- **Rationale:** the GPU cannot hold both (41.8 GB plus about 44 GB). Option C keeps today's campaign safe while the new shape is proven.
- **Alternatives considered:** running both with smaller models. Rejected because it would qualify the wrong precision.

## R9. Factory machine isolation

- **Decision:** two stages.
  1. **Container stand-in now:**
     - The factory image is built from the same cloud-init steps as the VM, applied with a Dockerfile `RUN` of the same provisioning script.
     - It runs with no GPU device, attaches only to a Docker `--internal` network shared with the tenant gateway, and has one data volume mount.
     - It has no host network and no host model paths.
  2. **VM once the `omniverse2` user is in group `kvm`:**
     - The Ubuntu 22.04 cloud image is booted with a cloud-init seed ISO built with `genisoimage`, which is installed.
     - qemu comes from the recipe's pinned container image or from host packages added by the admin, whichever the admin approves.
     - Its network is a user-mode or tap path that forwards only to the tenant gateway port.

  Packer is the production build path for the same cloud-init.
- **Not used:** passing `/dev/kvm` into a Docker container. It would work through the root Docker daemon, but it bypasses the host's deliberate restriction of `/dev/kvm` to `matss` and `kvm`. That stays the host admin's decision (owner 2026-11-08: "someone can add omniverse2 to kvm group").
- **Rationale:** User Story 5 and FR-021. The stand-in report states what it does not prove: a separate kernel, VM network stack, VM memory limits and boot from the production image.

## R10. Recipe as code

- **Decision:** a `deploy/recipe/` tree with these parts:
  - Named parameters, with one parameter file per site: `omniverse2.yaml` and `production.yaml`.
  - A lock file (`recipe.lock.json`) holding the image digests, model-file SHA-256s, the factory revision, Fabro 0.362.0 and the toolchain versions.
  - The model-tier Compose file and the factory cloud-init.
  - A Packer template.
  - A small CLI, `python -m forge_factory.modelservice.recipe`, with the subcommands `plan`, `apply`, `verify` and `drift`.

  Rules:
  - `apply` refuses to finish on any digest mismatch.
  - `drift` compares a running environment with the lock.
  - Secrets are referenced by name only and resolved from a local secret file outside the repo (mode 0600).
- **Rationale:** FR-017, FR-018 and SC-004/SC-008. Compose and cloud-init are the formats the platform team can read without Forge-C knowledge.
- **Packer licence:** Packer is BUSL-1.1, not an OSI open-source licence. The required build path is therefore cloud-init on the stock Ubuntu 22.04 cloud image, using only open-source tools. The Packer template is an optional convenience for platform teams that already use it; nothing in the factory runtime depends on it (constitution X).
- **Alternatives considered:**
  - *Ansible:* adds a tool the VM does not otherwise need.
  - *Nix:* too far from the platform team's practice.

## R11. Per-node exchange log in the factory gateway

- **Decision:** the new gateway revision gains a capture tap behind the same switch file as today's structured capture (`<state>/model-exchanges/capture.json`). The default is off.
  - It writes one private record per call, tagged with run, node, visit and the identity fingerprint, after `strip_reasoning` and secret redaction.
  - The existing exporter (`lrtx/model_exchanges.py`) reads these records in place of the Fabro events plus packet records, so the per-node report keeps its format.
- **Rationale:**
  - FR-022 to FR-024. On a shared service the capture cannot happen at the service, where logging is off and other tenants' traffic is present.
  - Today's gateway cannot be edited without breaking the owner-lane proof (R7), which is why capture currently lives in `structured.py` and the exporter. The new revision consolidates it.

## R12. Requalification method

- **Decision:**
  - **Baseline:** the qualification set is every SWE phase the line has already passed on the current setup (SWE.1 to SWE.6 lineage on the CRC HAL and GPIO orders).
  - **Fresh runs:** each phase is re-run on the production-like setup as a fresh order in the qualification lane. Completed earlier runs are read from evidence and never replayed (hard limit: no C/B/L90 replay).
  - **Report:** it is built from the per-node exchange export plus the run metrics. It shows gate outcome, rework and retries, model time, prompt and output tokens and cache reuse per phase and per node.
  - **Missing comparisons:** a comparison without a matching earlier run is labelled `NOT_RUN`, never PASS.
  - **Blocking findings:** each one goes through CRE as a CAPA (FR-016).
- **Rationale:** the evidence rules. Earlier revisions' results are never relabelled as the new revision's pass.

## Remaining unknowns (outside this feature's control)

- **Production serving stack and authentication:** the platform team has not answered yet. The mirror depends only on the contract in `contracts/model-channel.md`, and each production value stays a recipe parameter with "to be confirmed".
- **Exact vLLM digest and the FP8 checkpoint's availability:** resolved by the first build task and recorded in the lock. Neither changes the design.
