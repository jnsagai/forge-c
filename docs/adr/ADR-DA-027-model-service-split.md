# ADR-DA-027: Model-service split — the factory is a tenant, the models are a shared service

- **Status:** accepted for implementation (feature 017). The owner lane's cutover still needs owner approval (FR-020).
- **Date:** 2026-11-08
- **Context documents:** `specs/017-model-service-split/{spec,plan,research}.md`, `docs/ONPREM-DEPLOYMENT.md`

## Context

**Production:** a shared NVIDIA DGX (one H200, 141 GB) serves models to several applications. Forge-C runs in a CPU-only VM that reaches the models through one channel.

**Omniverse2 today:** the factory owns the GPU. It starts, stops and swaps its model server, and holds a GPU lock and an inference-owner lease.

**Owner (2026-11-08):**
- Mirror production as a recipe.
- Keep both of today's models in use at full capacity, swapped on the model side as fast as possible, with the models kept in RAM.
- Keep the models agnostic to the factory, so other factories can share them concurrently.

## Decisions

1. **Models and engine (owner 2026-11-08).** Omniverse2 and production serve the same two models, `qwen3.8:27b-q8_0` and Ornith-1.5-35B-A3B Q8_0, both GGUF on today's llama.cpp server with today's exact arguments, generated from the owner lane's profile and never retyped. Authoring uses Ornith-1.5-35B-A3B; the supervisor, monitor and inspector roles use qwen3.8 27B (owner 2026-11-08). Qwen3.6 and vLLM are not used (the vLLM engine stays as an example for sites that serve with it). On the 141 GB production GPU both models stay loaded; on Omniverse2's 48 GB the service swaps them at each author/inspector hand-over.
2. **One model on the GPU at a time, at full capacity; the service swaps on demand** (R3b). A swap drains in-flight work and never cuts a request off. It then unloads, loads and checks identity. A request is never answered by a model it did not name. Swapping is fair across tenants, by queue age weighted by priority, with a minimum residency and a maximum wait.
3. **Fastest swaps: models off the GPU stay warm in host RAM** (R3c, amended 2026-11-08).
   - On Omniverse2 both GGUF files (27.1 + 35.2 GiB) are kept resident in the page cache (warm strategy `page_cache`): no copy, so the 63 GiB `/dev/shm` limit does not apply. Residency is checked before every load; an evicted file is loaded from disk this time and re-warmed in the background, with a finding.
   - A swap is therefore a stop of one llama.cpp server and a start of the other on a file already in RAM.
   - A RAM budget and a reserve protect the shared host. When they cannot hold a model warm, that model loads cold and a finding is recorded.
   - The other strategies stay available for other sites: `ram_staged_file` (a copy in `/dev/shm`) and `vllm_sleep` (vLLM sleep mode).
4. **The model tier is factory-agnostic** (R3d). It is the `model_tier` package, which never imports `forge_factory` (enforced by a test). It knows tenants (key hash, share, priority, allowed models), never runs, nodes or lanes. Adding a factory is one tenant entry.
5. **The tenant gateway is ours, thin and audited** (R3): hashed keys, guaranteed and borrowable shares, an identity extension (`/forge/v1/identity`, `x-forge-model-identity`) and a metadata-only outcome log. LiteLLM was rejected: its tenant features need Postgres and are partly outside its open-source core.
6. **The factory talks to the channel only, through its unchanged gateway** (R6, R7). `llm_gateway.py` and four other sources are pinned by the owner lane's signed transport proof, so external mode is a new entry point (`gateway_external`). It runs the unchanged gateway with a model-channel transport that does the following:
   - uses the tenant key;
   - turns thinking off where the model's expected identity says off;
   - pins identity per model;
   - maps refusals and failures to the contract's reasons;
   - writes metadata-only call logs;
   - captures full calls for the exchange log only when the owner's switch is on.

   A test keeps the pinned sources byte-identical to the base.
7. **Transition, FR-019 option C.** Until the owner approves the qualification report, the model tier may use the GPU only inside qualification windows.
   - A window drains and stops the owner lane as a whole through its existing unsigned controls: admission hold, `deploy.lock`, and the deployer's stop and recover tooling. It never uses the operations intent.
   - It restores the lane on any failure.
   - It refuses to start if any foreign process holds the GPU.
8. **Qualification is evidence-only** (R12). The baseline is the newest run per phase that succeeded and whose gate decided PASS (CRC HAL SWE.1–SWE.6 today). The candidate is fresh runs in a separate qualification lane. No replay. NOT_RUN is never PASS.
9. **Recipe as code** (R10): parameters per site, a lock file, Compose, cloud-init (required) and Packer (optional, BUSL-1.1), with `plan`/`verify`/`drift`/`apply`.
10. **Factory machine isolation** (R9): a container stand-in until the `omniverse2` user is in group `kvm`, then a VM. `/dev/kvm` is not passed through Docker, which would bypass the host's restriction.

## Consequences

- **What production gets.** The factory depends only on a small OpenAI-compatible contract. Production can use any serving stack that meets it, with stated deviations when the identity extension is missing.
- **What windows cost.** Each window stops and restarts the owner lane, so windows are rare and run only when the lane is idle. The cutover removes them.
- **What the cutover requires.** The owner lane's own external mode (edits to `stack.py`, `execution_lifecycle.py` and the launcher) waits for it, because those files are pinned. The owner re-signs the transport proof as part of the cutover.
- **Measurement.** Swap times in both directions (Ornith to qwen3.8 and back, at each author/inspector hand-over) are measured in the first window. The swap policy defaults are estimates until then.
