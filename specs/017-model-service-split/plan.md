# Implementation Plan: Model-Service Split (Omniverse2 mirrors the production deployment)

**Branch**: `feat/017-model-service-split` | **Date**: 2026-11-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/017-model-service-split/spec.md`

## Summary

Omniverse2 gets two tiers.

- **Model tier:** one model service owns the GPU and serves a **catalog of models, each at full capacity**:
  - today's Ornith-1.5 (GGUF Q8 on its current llama.cpp server and settings);
  - the production reference Qwen3.6-35B-A3B (FP8 on vLLM, non-thinking).

  The 48 GB GPU holds one at a time, so a **swap controller** in the tenant gateway swaps on demand (owner 2026-11-08). It drains in-flight requests, unloads, loads, verifies identity and then serves, with an anti-thrash policy. The factory only names a model and sees a longer wait.

  The thin Forge-C **tenant gateway** also provides per-tenant keys, guaranteed shares with priorities, a metadata-only log and a per-model verifiable identity.
- **Factory tier:** the factory runs in an isolated **factory machine**. That is a container stand-in now, and a KVM virtual machine once the `omniverse2` user is in group `kvm`. Its only route to the model is the tenant gateway port.

The factory gains an **external model service** mode. In that mode it never starts, stops or swaps a model server and never holds a GPU lock or lease. Admission follows the tenant share, and every call is tied to the served-model identity.

**Transition (spec FR-019, option C):**

1. The model tier is built and the factory requalified only in **scheduled windows** while the owner lane is paused.
2. After the owner approves the qualification report, the owner lane becomes the **first tenant** under a re-measured, owner-signed transport proof.

The whole environment is a **recipe as code**: parameters per site, a fingerprint lock, Compose, cloud-init and Packer, with `apply`/`verify`/`drift`. Production is built from the same recipe.

Research and decisions: [research.md](research.md).

## Technical Context

**Language/Version**:
- Factory: Python 3.13 via `uv`.
- Model-tier gateway: Python 3.13 in its own pinned container image.
- Recipe: YAML, Compose, cloud-init and HCL (Packer).

**Primary Dependencies**:
- Model tier: vLLM (`vllm/vllm-openai`, digest-pinned).
- Factory side: Starlette and httpx, the same as the existing `llm_gateway`.
- Container boundary: Docker 29 with NVIDIA CDI.
- VM: qemu/KVM with an Ubuntu 22.04 cloud image and cloud-init.
- Production image build: cloud-init on the stock Ubuntu cloud image, with an optional Packer template.
- Unchanged: Fabro 0.362.0.

**Storage**:
- Files only. The tenant key file holds SHA-256 hashes (0600).
- Metadata-only outcome log (JSONL).
- Recipe lock (JSON).
- Private exchange captures (0600/0700), under the factory data root.
- Qualification reports in evidence.

**Testing**:
- pytest (factory test suite), with fake upstreams for the tenant gateway and the external mode.
- Contract tests against [contracts/](contracts/).
- `python3 tests/spec/validate_design.py`.
- On-host smoke and qualification runs are recorded as evidence. NOT_RUN is stated explicitly where a window has not happened yet.

**Target Platform**:
- Omniverse2: Ubuntu 22.04, RTX 6000 Ada 48 GB, shared host, no sudo.
- Production: a CPU-only Ubuntu 22.04 VM plus a DGX H200 141 GB shared model service.

**Project Type**: an infrastructure feature inside the existing factory monorepo (a Python package, a service and deployment recipes).

**Performance Goals**:
- The mirror must reproduce production behaviour, not production speed.
- Model tier: at least 2 sequences × 65,536 tokens of KV capacity, falling back to 1 × 65,536 (research R2).
- Under saturation the factory's guaranteed share holds, with 0 factory calls failing from neighbour load (SC-003).
- A rebuild from the recipe takes at most one working day (SC-004).

**Constraints**:
- **Hard limits:** no edit to signed controls, production rules or the production lane; the production observer stays in OBSERVE; no paid or cloud dependency; the owner's signing key is never touched; x-verse_fabric is not touched.
- **GPU:** never held by two owners at once (FR-019).
- **Gateway:** the gateway revision is pinned by the owner-lane proof, so the new revision runs only in the qualification lane until the cutover (research R7).
- **Data:** no hidden reasoning and no secrets stored; exchange capture is off by default.
- **Evidence:** CRE gating applies to every factory change.

**Scale/Scope**:
- One model service with a two-model catalog and three tenants on Omniverse2: `forge-qual`, `forge-owner` (after the cutover) and `sim-neighbour`.
- One factory machine.
- One qualification lane.
- Every SWE phase the line has already passed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle | How this plan complies | Status |
| --- | --- | --- |
| I. Safety and correctness first | No gate, rule or baseline changes. Phases that pass today but fail on the new setup become blocking findings (FR-016). There is no speed-for-quality trade | PASS |
| II. Evidence-driven | Identity is recorded per call; the qualification report is built from run evidence; NOT_RUN is explicit; the recipe lock pins versions and hashes | PASS |
| III. Unattended run, external authority | Windows and qualification run unattended. The cutover needs the owner's approval of the report (FR-020), which is an offline human decision outside the runtime | PASS |
| IV. Versioned SKILLs | AI roles and skills are unchanged; only the model behind them changes | PASS |
| V. MCP for AI tool calls | Tool paths are unchanged. The tenant gateway and the recipe CLI are non-agent infrastructure on native APIs, which the constitution allows | PASS |
| VI. Model-free supervision, bounded healing | The window controller and drift check make no model calls. Outages are recorded incidents with bounded waits; there are no restart storms (the factory never restarts the service) | PASS |
| VII. Evidence-based lessons | Not affected | PASS |
| VIII. Privacy-preserving traces | The tenant gateway logs metadata only. Exchange capture is off by default, private and redacted, with reasoning stripped (FR-022 to FR-024). `ai_hidden_reasoning_capture` stays false | PASS |
| IX. Minimal model cost | Non-thinking mode is expected to cut output tokens sharply. Budgets and governors are unchanged | PASS |
| X. Open-source first, clean interfaces | vLLM (Apache-2.0), Docker, qemu and cloud-init. Packer (BUSL-1.1) is an optional image-build convenience only; the required path is cloud-init on the stock image (research R10). There is no paid API. The factory depends only on the OpenAI-compatible contract | PASS |
| Governance | No change to the constitution, release gates or protected paths. The gateway revision change for the owner lane goes through the owner's signed control at the cutover | PASS |

No violations, so the complexity table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/017-model-service-split/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── model-channel.md                 # the OpenAI-compatible subset + identity extension the factory relies on
│   ├── served-model-identity.schema.json
│   ├── tenant-config.schema.json
│   ├── model-service-profile.schema.json  # the factory's `model_service` block
│   ├── recipe-params.schema.json
│   └── qualification-report.schema.json
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks (not created here)
```

### Source Code (repository root)

```text
factory/python/model_tier/         # NEW, factory-agnostic model service (FR-032); never imports forge_factory
├── identity.py                    # served-model identity: fingerprint, build, verify (shared contract)
├── tenant_gateway.py              # tenants, keys, shares, priorities, identity endpoints, metadata log
├── swap.py                        # catalog, per-tenant per-model queues, fair swap decisions, drain/unload/load/verify
├── engines.py                     # engine definitions from catalog.yaml (process or compose), warm strategies
├── ramstage.py                    # keep models warm in host RAM (/dev/shm staging, residency, budget)
├── gpu.py                         # read-only GPU probe
├── neighbour.py                   # synthetic second-tenant load
└── schemas/                       # copies of the contract schemas (kept identical by a test)

factory/python/forge_factory/
├── modelservice/                  # NEW package
│   ├── identity.py                # re-exports model_tier.identity (the shared contract)
│   ├── catalog_gen.py             # generates the Ornith catalog entry from the owner-lane profile (factory side)
│   ├── client.py                  # factory side: identity pin, reason mapping, share-aware admission settings
│   ├── window.py                  # qualification window controller (drain owner lane, GPU handover, restore)
│   ├── qualify.py                 # qualification report (reads model_exchanges export + run metrics)
│   ├── neighbour.py               # simulated second tenant load generator
│   └── recipe.py                  # recipe CLI: plan / apply / verify / drift
├── llm_gateway.py                 # NEW REVISION (qualification lane only until cutover): upstream key,
│                                  #   identity header check, non-thinking kwargs, tenant-scoped capture tap
├── afo/line_stack_lifecycle.py    # external mode: no server start/stop/swap
├── afo/scheduler.py, afo/operations.py, afo/line_launcher.py
│                                  # external mode: tenant-share admission replaces GPU lock / owner lease
├── lrtx/stack.py, lrtx/profile.py # `model_service` profile block; owned mode unchanged
└── lrtx/model_exchanges.py        # reads gateway capture records in addition to Fabro events

config/factory/model-service.yaml  # mode selection + tenant share for the factory (default: owned)

deploy/recipe/
├── README.md                      # how to build Omniverse2 and production from the same recipe
├── params/omniverse2.yaml, params/production.yaml
├── recipe.lock.json               # image digests, model file sha256, factory revision, tool versions
├── model-tier/compose.yaml        # one engine service per catalog model (llama.cpp Ornith, vLLM Qwen3.6), internal network
├── model-tier/catalog.yaml        # models, engines, full-capacity settings, identities, swap policy
├── model-tier/tenant-gateway.service  # user systemd unit for the tenant gateway + swap controller
├── model-tier/tenants.example.yaml
├── factory-machine/cloud-init/user-data.yaml
├── factory-machine/container/Dockerfile   # stand-in built from the same provisioning script
├── factory-machine/provision.sh
└── factory-machine/packer/forge-c.pkr.hcl

factory/python/tests/
├── test_modelservice_tenant_gateway.py
├── test_modelservice_identity.py
├── test_modelservice_external_mode.py
├── test_modelservice_window.py
├── test_modelservice_recipe.py
├── test_modelservice_qualify.py
└── test_llm_gateway_external.py
```

**Structure Decision**:
- The feature lives in a new `forge_factory/modelservice` package, plus a deployable `deploy/recipe` tree. Changes to existing modules are limited to mode switches (`owned` stays the default).
- **Implementation base:** the GPU-ownership code paths it changes (`afo/*`, `lrtx/stack.py`) are on the campaign branch of record (`feat/owner-lane-campaign-v21-20261107`), not yet on `main`. Implementation branches therefore start from that branch tip, and this spec branch's documents are carried along. Merge to `main` follows the owner's acceptance, with merge commits only.

## Delivery stages (for /speckit-tasks)

| Stage | Content | Needs GPU window | Touches owner lane |
| --- | --- | --- | --- |
| S0 | Pull and pin artefacts: vLLM image digest, model weights with SHA-256, Ubuntu cloud image. Write the lock | no (download only) | no |
| S1 | Tenant gateway, identity and recipe CLI. Unit and contract tests against a fake engine | no | no |
| S2 | Factory external mode, gateway revision and client, behind `mode: external`. Unit tests, with `owned` unchanged | no | no |
| S3 | Factory container stand-in from the shared provisioning script; isolation checks | no | no |
| S4 | Window controller. First window: model tier smoke test, KV capacity check (R2), identity per model, swap measurements in both directions, alternating-model run (SC-009, SC-010), neighbour contention test | **yes** | paused, then restored |
| S5 | Qualification windows: every passed SWE phase on the production-like setup; report; CAPAs for blocking findings | **yes** | paused, then restored |
| S6 | Owner review of the report. On approval: re-measured transport proof for the new gateway (owner signs), owner lane as first tenant, rehearsed way back | yes (permanent) | **cutover, owner-approved** |
| S7 | VM factory machine once `kvm` is granted; recipe rebuild drill (SC-004); production parameter handover (SC-008) | no | no |

Stages S0 to S3 are fully autonomous and CRE-gated. S4 and S5 are autonomous inside the owner's window limits. S6 cannot happen without the owner.

## Post-design Constitution re-check

Phase 1 artefacts ([data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)) introduce:

- no prompt content in any service log;
- no reasoning field in any record;
- no secret in the recipe (secrets are referenced by name only);
- no edit to signed controls.

The identity and share contracts are deterministic and model-free. **Result: PASS**, with no violations.

## Complexity Tracking

No constitution violations to justify.
