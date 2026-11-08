# Feature Specification: Model-Service Split (Omniverse2 mirrors the production deployment)

**Feature Branch**: `feat/017-model-service-split`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "Model-service split: mirror the production deployment on Omniverse2. Production (docs/ONPREM-DEPLOYMENT.md, sent to the platform team 2026-10-15; owner 2026-11-08 confirmed): an NVIDIA DGX with one H200 141 GB GPU runs a SHARED model service (vLLM-class, OpenAI-compatible API over HTTPS with per-tenant API keys; reference model Qwen3.6-35B-A3B BF16, non-thinking mode, 262k context, 11 sequences, 761k-token KV cache, prefix caching on, request logging off) that serves Forge-C and other applications; Forge-C runs in a CPU-only Ubuntu 22.04 VM whose LLM gateway is its only path to the model; the platform team's serving stack and auth are not yet known. [...] Deliver a reproducible recipe-as-code so production can be built the same way, and a requalification of the factory on the production-like model/engine before any cutover."

## Clarifications

### Session 2026-11-08

- Q: How does the mirror share the single 48 GB GPU with the live lanes during the transition? -> A: Option C: build and qualify in scheduled windows while the owner lane is paused, then move the owner lane onto the model service as its first tenant after the owner approves the qualification report; the production lane moves only by a separate approved cutover.
- Q (owner 2026-11-08): Is the model service only for this factory? -> A: "do it in a way that in the future I can have other factories using in concurrency the models. Therefore, the models are agnostic to the factory itself." The model service knows only tenants, never factories (FR-032, FR-033, SC-012).
- Q (owner 2026-11-08): How fast must a swap be? -> A: "as fast as possible. So maybe they should be cached or stored in the RAM memory to do the swap as soon as possible when it's required." (FR-031, SC-011)
- Q (owner 2026-11-08): Must the mirror serve one model or several? -> A: "I still want that both models are used at their full capacity, but the VM should be agnostic to that. When the VM requests one of those models, we should be able to do a swap in the model side, seamless to the VM." The model service therefore serves a catalog of models (today's Ornith-1.5 and the production reference Qwen3.6). Each loaded model gets the whole GPU at its full settings, and the service swaps on demand. The factory only names a model in its request.

## Context

Production will not look like Omniverse2 today. In production a separate, **shared** GPU server answers model requests for several applications, and Forge-C runs in its own CPU-only virtual machine that reaches the model through one network channel (see `docs/ONPREM-DEPLOYMENT.md`). On Omniverse2 the factory currently **owns** the GPU: it starts and stops the model server, swaps models during a run, holds a GPU lock and an inference-owner lease, and uses a different model, precision and reasoning setting than production.

Every hour the factory runs in the Omniverse2 shape produces evidence about a configuration that production will never have. This feature makes Omniverse2 a faithful, smaller-scale mirror of production, and turns the mirror into a recipe from which production is built.

**Actors**

- **Owner** (factory operator): approves cutovers, reads qualification results, hands the recipe to the platform team.
- **Platform team**: runs the shared model service in production; consumes the recipe and the interface contract.
- **Factory** (Forge-C, unattended): a tenant of the model service, never its operator.
- **Other tenants**: applications that share the model service (simulated on Omniverse2).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The factory runs as a tenant of an external model service (Priority: P1)

The factory completes a work order while the model is provided by a separate model service that the factory does not start, stop, swap or otherwise control. The factory reaches the model only through its own gateway and one network channel, and the run's evidence names exactly which model answered.

**Why this priority**: This is the production shape. Without it nothing measured on Omniverse2 transfers to production, and the factory code still contains GPU-ownership behaviour that production forbids.

**Independent Test**: Run one bounded work order (a phase that the line has already passed on the current setup) with the factory in "external model service" mode against a model service running in its own isolation. Verify the run completes or ends in an explicit blocked state, that no factory process touched the GPU or the model server, and that the evidence package records the served model's identity for every model call.

**Acceptance Scenarios**:

1. **Given** the factory is configured for an external model service, **When** a work order runs, **Then** no factory component starts, stops, restarts or swaps a model server, takes a GPU lock or holds an inference-owner lease, and the run's audit trail shows this.
2. **Given** a run in progress, **When** the model service reports a different served model identity than the one the run started with, **Then** the factory refuses further model calls for that run and ends it in an explicit blocked state naming the identity change; it never continues on a silently different model.
3. **Given** the model service is unreachable or restarting, **When** the factory needs a model call, **Then** it waits within a bounded time, records the outage as an infrastructure incident, and either resumes from the last quality-checked part or ends the run blocked; it never attempts to start a model itself.
4. **Given** a completed run, **When** the owner inspects the evidence, **Then** every model call is linked to the served model's name, revision fingerprint, precision and reasoning mode.

---

### User Story 2 - A shared model service on Omniverse2 behaves like the production one (Priority: P1)

The owner can run, on Omniverse2, a model service that has the production service's essential properties:

- one service owns the GPU;
- several tenants each have their own credential and share;
- a tenant cannot exceed its share or see another tenant's traffic;
- the service can prove which model it serves.

The service offers **several models**: today's Ornith-1.5 and the production reference Qwen3.6. Each model runs at its full capacity when loaded. When a request names a model that is not loaded, the service swaps models itself, and the requester sees only a longer wait.

**Why this priority**: The factory can only be qualified against a realistic neighbour. Quota exhaustion, waiting behind another tenant and credential rotation are exactly the conditions production will impose.

**Independent Test**: Start the model service with two tenants (the factory and a simulated "other application"), drive load from the simulated tenant, and run a factory phase at the same time. Verify per-tenant shares, refusals, waiting times and isolation from the service's own records.

**Acceptance Scenarios**:

1. **Given** two tenants with separate credentials, **When** a request arrives without a valid credential, **Then** it is refused and no model work is done.
2. **Given** the factory's share is fully used, **When** the factory sends another request, **Then** the service makes it wait or refuses it with an explicit reason, and the factory treats this as a bounded wait, never as a model failure.
3. **Given** the simulated tenant saturates its own share, **When** the factory runs, **Then** the factory's requests still receive at least its guaranteed share.
4. **Given** any tenant, **When** it asks which model is served, **Then** the service returns a verifiable identity (name, revision fingerprint, precision, context limit) that matches the pinned recipe.
5. **Given** default settings, **When** requests are served, **Then** the model service stores no prompt or response content.
6. **Given** model A is loaded, **When** a tenant requests model B from the catalog, **Then** the service finishes or drains the requests in flight on A, unloads A, loads B with B's full-capacity settings, verifies B's identity and answers the request. The tenant receives a normal answer, and the only visible difference is the longer wait (reported as queue time).
7. **Given** requests for both models keep arriving, **When** the service decides when to swap, **Then** it batches requests per model and keeps a loaded model resident for at least a configured time, so it never thrashes between models. Each tenant's guaranteed share still holds, and no request waits longer than the configured maximum.
8. **Given** a request names a model that is not in the catalog, **When** it arrives, **Then** it is refused with an explicit reason, and no swap happens.
9. **Given** a swap fails (the new model does not become healthy or its identity does not match), **When** this happens, **Then** the service refuses that model's waiting requests with an explicit reason, records the failure and returns to a healthy state. It never answers with a different model than the one requested.
10. **Given** two factories and another application are tenants at the same time, each preferring a different model, **When** they run concurrently, **Then** every tenant keeps progressing within the maximum wait, each guaranteed share holds, and no tenant can force swaps that starve another. Adding a further factory needs only a new tenant entry and no change to the model service.

---

### User Story 3 - The factory is requalified on the production-like model before any cutover (Priority: P2)

Before any lane is moved to the new shape, the owner sees a qualification report comparing the factory on its current setup with the factory on the production-like model and engine (the production reference model, non-thinking mode, in a precision that fits the 48 GB GPU), per phase and per AI node.

**Why this priority**: The production model, engine, precision and reasoning setting all differ from today's. The trial log already shows that about 98% of the SWE.1 author's generated tokens are hidden reasoning, so non-thinking mode may change both quality and speed sharply. A cutover without this evidence would be a blind change.

**Independent Test**: Run the qualification set on both setups and produce the report; it can be reviewed without any cutover.

**Acceptance Scenarios**:

1. **Given** the qualification set, **When** it runs on both setups, **Then** the report shows, per phase and per AI node, gate outcomes, rework and retry counts, model time, prompt and output tokens, and prompt-cache reuse, side by side.
2. **Given** a phase that passes on the current setup but fails on the production-like setup, **When** the report is produced, **Then** the failure is listed as a blocking qualification finding with its evidence, and no cutover can be approved while it is open.
3. **Given** the qualification uses a smaller precision or fewer concurrent sequences than production, **When** the report is produced, **Then** each such deviation is stated explicitly with the production value next to it.

---

### User Story 4 - The environment is reproducible from a recipe (Priority: P2)

The owner can rebuild the whole Omniverse2 mirror (model service and factory machine) from a versioned recipe, and hand the same recipe, with production values substituted, to the platform team.

**Why this priority**: The owner's stated goal is "a recipe about how to reproduce the very same environment in the production system". Without a recipe the mirror is a one-off.

**Independent Test**: Tear down the mirror (keeping data), rebuild it from the recipe alone on Omniverse2, and verify that the rebuilt environment reports the same pinned identities and passes the same smoke qualification.

**Acceptance Scenarios**:

1. **Given** the recipe, **When** it is applied to a clean target, **Then** it produces the model service and the factory machine with every model artifact, tool and runtime version pinned and verified by fingerprint, and refuses to finish if any fingerprint differs.
2. **Given** a running environment, **When** a drift check runs, **Then** any component whose identity differs from the recipe is reported.
3. **Given** the recipe, **When** the platform team reads it, **Then** every site-specific value (addresses, credentials, GPU size, number of sequences) is a named parameter with the Omniverse2 value and the production value documented, and no secret is stored in it.

---

### User Story 5 - The factory machine is isolated like the production VM (Priority: P3)

The factory runs on Omniverse2 inside its own machine boundary (a virtual machine once virtualization access is granted, a container boundary until then) whose only path to the model is the one channel to the model service.

**Why this priority**: Isolation proves that nothing in the factory silently relies on the host (local GPU, local model files, loopback services). It is P3 because User Stories 1 and 2 already remove the GPU ownership; isolation then makes the guarantee structural.

**Independent Test**: Start the factory machine, confirm from inside that the GPU, the host's model files and the host's other services are unreachable, and that a factory phase still runs.

**Acceptance Scenarios**:

1. **Given** the factory machine, **When** any factory component tries to reach the GPU, the model files or any host service other than the model channel, **Then** the attempt fails and is recorded.
2. **Given** virtualization access is not yet granted, **When** the factory machine is started, **Then** it uses the container boundary, and the report states which production properties this stand-in does not prove.

---

### User Story 6 - Per-node model exchange log, tenant-scoped (Priority: P3)

The owner keeps the per-node model exchange log (introduced 2026-11-08) in the new shape: it is produced inside the factory's own gateway, covers only the factory's own traffic, is private and off by default, and still never contains hidden reasoning.

**Why this priority**: The log is the owner's optimization tool. In the shared shape it can no longer be produced on the model service (other tenants' traffic, production logging is off), so it must move to the factory side.

**Independent Test**: With the switch on, run a phase and verify that every model call appears in the per-node log with its request and reply, tagged with run and node; with the switch off, verify that nothing is written.

**Acceptance Scenarios**:

1. **Given** the capture switch is off (default), **When** runs execute, **Then** no prompt or reply content is written anywhere.
2. **Given** the switch is on, **When** a run executes, **Then** each model call is recorded once, under its run and node, with request, reply, token counts and timing, and no other tenant's traffic is visible.
3. **Given** a model reply that contains reasoning content, **When** it is recorded, **Then** the reasoning text is absent and only its token count remains.

### Edge Cases

- **Model service restarts mid-call**: the in-flight call's outcome is unknown; the factory records it as unknown, never as success or as zero cost, and retries only through the normal bounded recovery.
- **Served model changes between calls** (operator upgrade on the service): blocked with the identity change named (User Story 1, scenario 2); a new run on the new identity requires requalification evidence for that identity.
- **Context limit**: a request that would exceed the factory's context setting is refused before it is sent; the factory repartitions the task. It is never truncated.
- **Prefix cache evicted by another tenant**: calls still succeed, only slower; the per-node log shows the lower cache reuse.
- **Reasoning content appears although non-thinking mode is configured**: it is stripped before storage and counted; repeated occurrences raise an infrastructure finding about the service configuration.
- **Credential expired or rotated**: requests are refused with an authentication reason; the factory raises an incident and does not retry blindly.
- **Channel interrupted** (network or certificate failure): treated like an unreachable service (User Story 1, scenario 3).
- **Swap during another tenant's long request**: the swap waits for in-flight requests on the loaded model up to a configured drain time. It never cuts a request off. A request still running at the drain limit delays the swap, and the waiting requests stay within their bounded wait.
- **Swap thrash**: alternating requests (for example an author on one model and an inspector on the other) are served in per-model batches with a minimum residency time. Swap count and swap time are recorded per hour, and a swap rate above a configured limit raises an infrastructure finding.
- **Factory asks for a model the site does not offer** (for example production serves only the reference model): the request is refused with "model not offered". The factory's profile for that site maps every role to an offered model, and this is checked before a run starts.
- **GPU contention on Omniverse2**: the existing lanes and the new model service cannot hold the GPU at the same time (see FR-019); a start of the model service while a lane owns the GPU is refused, and vice versa.
- **Factory machine cannot boot** (virtualization access missing): the container stand-in is used, and its limitations are stated (User Story 5, scenario 2).

## Requirements *(mandatory)*

### Functional Requirements

**Factory as a tenant (external model service mode)**

- **FR-001**: The factory MUST support an "external model service" mode in which no factory component starts, stops, restarts or swaps a model server, takes a GPU lock, or holds an inference-owner lease.
- **FR-002**: In that mode the factory MUST reach the model only through its own gateway, and the gateway MUST reach only the configured model channel. Every other model endpoint MUST be refused.
- **FR-003**: Before a run's first call to each model, and again whenever the service reports a change, the factory MUST read and record that model's served identity: name, revision fingerprint, precision, reasoning mode and context limit. The identity is pinned per model name for the run. A mismatch with the identity pinned for that model MUST block the run. A swap that brings back the same identity is not a mismatch.
- **FR-004**: The factory's admission MUST follow the service's share for the factory tenant (concurrent requests and waiting), replacing the GPU-ownership lease. "Share exhausted" MUST be a bounded wait or an explicit refusal, never a model failure.
- **FR-005**: An unreachable service, a refused credential, an interrupted channel or an unknown call outcome MUST each produce a distinct, recorded reason. The run MUST resume from the last quality-checked part or end blocked.
- **FR-006**: Requests that need more context than the factory's configured limit MUST be refused before sending. Required evidence MUST never be truncated to fit.
- **FR-007**: The mode switch MUST be a configuration selection that is recorded in each run's evidence. The current GPU-owning mode MUST keep working unchanged until a cutover is approved (FR-020).

**Shared model service (Omniverse2 mirror)**

- **FR-008**: The model service MUST be the only process that owns the GPU while it runs, and MUST serve the production-compatible chat-completion interface that the factory's gateway already speaks.
- **FR-009**: The service MUST authenticate every request with a per-tenant credential and MUST refuse requests without a valid one.
- **FR-010**: The service MUST enforce a per-tenant share (concurrent requests and queue length) with a priority order. A tenant's guaranteed share MUST hold while other tenants saturate theirs.
- **FR-011**: The service MUST expose a verifiable served-model identity that matches the pinned recipe values.
- **FR-012**: The service MUST store no prompt or response content by default. Its operational records MUST contain only metadata (tenant, time, token counts, outcome).
- **FR-013**: The mirror MUST include a simulated second tenant that can generate configurable load, for qualification under contention.

**Several models at full capacity, swapped by the service (owner 2026-11-08)**

- **FR-025**: The model service MUST serve a catalog of models fixed by the recipe. On Omniverse2 the catalog holds today's Ornith-1.5 and the production reference Qwen3.6. Each catalog entry MUST carry its own engine, full-capacity settings (context, concurrent sequences, cache), reasoning mode and pinned identity.
- **FR-026**: When a model is loaded, it MUST have the whole GPU at its full-capacity settings. Models MUST NOT be shrunk to fit together. If the hardware can hold several catalog models at full capacity (production), the service MAY keep them loaded together, and the factory MUST NOT be able to tell the difference except by waiting time.
- **FR-027**: The service MUST swap models on demand when a request names a catalog model that is not loaded. A swap MUST:
  1. let in-flight requests finish, up to a drain limit;
  2. unload the current model completely;
  3. load the requested model;
  4. verify its identity;
  5. then serve the waiting requests.

  A swap MUST never answer a request with a model other than the one named.
- **FR-028**: The swap policy MUST prevent thrashing: requests are batched per model, a loaded model stays resident for at least a configured time, and the maximum wait for any request is bounded. Tenant shares and priorities MUST still hold across swaps.
- **FR-029**: The factory MUST be agnostic to swapping. It names a model per request and treats any swap as a bounded wait. In external mode, the factory's own swap step (today's serve node in the workflow) MUST make no model change and only record which model the next part will use.
- **FR-030**: Every swap MUST be recorded as metadata: time, from-model, to-model, drain time, load time, outcome and the requests that waited. Swap count and total swap time MUST appear per phase in the qualification report.

- **FR-031**: Swaps MUST be as fast as the hardware allows (owner 2026-11-08: "the model should be swapping as fast as possible ... cached or stored in the RAM"). Every catalog model that is not on the GPU MUST be kept ready in host RAM so a swap never reads model files from disk.
  - The service warms all catalog models once when it starts.
  - When host RAM cannot hold all of them within the configured RAM budget, the service MUST fall back to loading from disk for that model, record an infrastructure finding, and still answer correctly.
  - Swap time MUST be measured and reported per direction.

**Factory-agnostic model service (owner 2026-11-08)**

- **FR-032**: The model service MUST be agnostic to the factory. It serves any number of independent tenants concurrently: several factories, other applications, or several lanes of one factory. It MUST hold no knowledge of factory concepts (runs, work orders, workflow nodes, lanes, roles), and none of its code may depend on factory code. Adding a factory MUST need only a new tenant entry (credential, share, allowed models).
- **FR-033**: Swap decisions MUST be fair across tenants. A tenant's demand for a model that is not loaded counts against that tenant's share. The swap controller serves model batches by weighted queue age and tenant priority, within the minimum residency and the maximum wait, so no tenant can starve another tenant's guaranteed share by forcing swaps.

**Requalification**

- **FR-014**: Before any cutover the factory MUST be qualified on the production-like configuration: the production reference model, non-thinking mode, in the precision that fits the Omniverse2 GPU. The qualification set MUST cover every SWE phase the line has already passed on the current setup.
- **FR-015**: The qualification report MUST compare both setups per phase and per AI node: gate outcomes, rework and retries, model time, prompt and output tokens, and prompt-cache reuse. It MUST list every deviation from production values (precision, concurrent sequences, context, cache size) next to the production value.
- **FR-016**: A phase that passes on the current setup and fails on the production-like setup MUST be recorded as a blocking qualification finding through the factory's corrective-action process (CRE).

**Recipe**

- **FR-017**: The environment MUST be buildable from a versioned recipe that pins every model artifact, runtime, tool and the factory revision by fingerprint. The recipe MUST refuse to complete on any mismatch, and MUST include a drift check for a running environment.
- **FR-018**: Every site-specific value in the recipe MUST be a named parameter with the Omniverse2 and production values documented. The recipe MUST contain no secret, and MUST state which production properties the Omniverse2 build does not prove (precision, scale, virtualization stand-in).

**Transition and safety**

- **FR-019**: The model service and the existing GPU-owning lanes MUST NOT hold the GPU at the same time. GPU use on Omniverse2 during the transition MUST follow two stages (owner 2026-11-08, option C): (1) **qualification windows** - the model service is built and requalified only in scheduled windows while the owner lane is paused at a safe point, and the owner lane resumes on today's setup after each window; (2) **owner lane as first tenant** - only after the owner approves the qualification report (FR-020) does the owner lane move onto the model service as its first tenant. The production lane stays on its own setup until a separate owner-approved cutover. Because the catalog contains the owner lane's current model at its current settings (FR-025), the owner lane's cutover can keep its model unchanged; only the channel changes.
- **FR-020**: Moving any lane to the new shape MUST require an owner-approved cutover backed by the qualification report. The production lane, signed controls and the owner lane's CRE gating MUST stay unchanged until then, and every cutover MUST have a tested way back to the previous shape.
- **FR-021**: The factory machine MUST run inside its own boundary whose only route to the model is the model channel: a virtual machine once virtualization access is granted, a container boundary until then. Its reports MUST state which production properties the stand-in does not prove.

**Per-node exchange log in the new shape**

- **FR-022**: The per-node model exchange log MUST be produced inside the factory's own gateway, MUST cover only the factory tenant's traffic, MUST be off by default, and MUST tag each call with run, node and visit.
- **FR-023**: Hidden reasoning text MUST never be stored by any component of this feature; only its token count may be kept.
- **FR-024**: Secrets MUST be redacted before anything is written, and captured content MUST stay in private storage that is never part of a review package or public export.

### Key Entities

- **Model service**: the single GPU owner. Attributes: served-model identity, tenants, shares, outcome records (metadata only).
- **Served-model identity**: name, revision fingerprint, precision, reasoning mode, context limit. It is pinned in the recipe and recorded per run and per call.
- **Tenant**: a consumer of the model service. Attributes: credential, guaranteed share, priority, queue limit.
- **Model channel**: the single authenticated network path from the factory machine to the model service.
- **Factory machine**: the isolated boundary (VM or container stand-in) that runs all factory software and has no GPU.
- **Qualification report**: per-phase and per-node comparison of the two setups, with deviations and blocking findings.
- **Recipe**: the versioned, fingerprint-pinned description of the whole environment, with site parameters and a drift check.
- **Cutover record**: owner approval, the qualification report it relies on, the lane moved, and its way back.
- **Model catalog entry**: model name, engine, full-capacity settings, reasoning mode, pinned identity. One catalog per site.
- **Swap event**: from-model, to-model, drain time, load time, outcome, waiting requests.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In external model service mode, 100% of the model calls of a qualification run are answered by the separate model service, and the run's audit trail shows zero model-server starts, stops, swaps or GPU locks by factory components.
- **SC-002**: Every model call in a qualification run (100%) can be traced to the served-model identity that answered it.
- **SC-003**: Under a saturating second tenant, the factory still receives its guaranteed share, and its waits are recorded and bounded. 0 factory calls fail because of the other tenant's load.
- **SC-004**: The mirror can be rebuilt from the recipe alone within one working day, and the rebuilt environment reports identical pinned identities (0 drift findings).
- **SC-005**: The qualification report covers 100% of the SWE phases the line has already passed, per AI node, and states every deviation from production values.
- **SC-006**: No cutover happens with an open blocking qualification finding, and every cutover's way back is exercised at least once before approval.
- **SC-007**: With the exchange-log switch off, a full run writes 0 bytes of prompt or reply content anywhere. With it on, 100% of the factory's model calls appear in the per-node log, and 0 contain hidden reasoning text.
- **SC-009**: With requests alternating between the two catalog models, 100% of requests are answered by the model they named, 0 requests fail because of a swap, and every wait stays within the configured maximum.
- **SC-010**: A run that alternates models in external mode completes with 0 swap actions by factory components; all swaps appear only in the service's swap records.
- **SC-011**: After the first warm-up, 95% of swaps in each direction complete within 30 seconds (from the last drained request to the first answer from the new model), measured in the first window. The cold first load is reported separately and is not counted.
- **SC-012**: With two factory tenants and a third application running concurrently and preferring different models, 100% of requests are answered within the maximum wait, each tenant's guaranteed share holds, and an automatic check finds 0 dependencies of the model service's code on factory code.
- **SC-008**: The platform team can map every recipe parameter to a production value without asking the factory team for missing information (checked in the handover review).

## Assumptions

- **Reference document**: `docs/ONPREM-DEPLOYMENT.md` (2026-10-15) is the production description. Production is one H200 141 GB GPU (owner 2026-11-08), serving the production reference model in BF16, non-thinking, with 262k context, 11 sequences and a 761k-token cache, request logging off, and an OpenAI-compatible interface over HTTPS with API keys. The platform team's actual serving stack and authentication are not yet known (owner 2026-11-08); the mirror therefore depends only on the chat-completion interface, a per-tenant credential and a model-identity query.
- **Scale on Omniverse2**: the RTX 6000 Ada (48 GB) cannot hold the production model in BF16. The mirror uses a lower precision that fits, with fewer concurrent sequences and a smaller cache. Production speed and concurrency are not claimed; production qualification on BF16 remains a separate step on the production hardware.
- **Model catalog**: on Omniverse2 the catalog is today's Ornith-1.5 (GGUF Q8, served by the same llama.cpp server and full-capacity settings the owner lane uses today) and Qwen3.6-35B-A3B (FP8, vLLM, non-thinking). The 48 GB GPU holds one of them at full capacity at a time, so the service swaps. In production the catalog and whether models are co-resident or swapped are the platform team's choice. They are recipe parameters, and the factory is unaffected either way.
- **Virtualization**: the `omniverse2` user can be added to the `kvm` group (owner 2026-11-08, one-time admin action). Until then the factory machine uses a container boundary. Docker with GPU access is already available for the model tier.
- **Reasoning**: production runs non-thinking. Today's lane uses reasoning effort "medium". Moving to non-thinking is part of the requalification (FR-014), not an assumed equivalence.
- **Factory gateway**: the factory keeps its existing gateway, which already strips reasoning, enforces admission and records usage. Its upstream becomes the remote service. The gateway source is bound into the owner lane's signed transport proof, so changing it requires a re-measured proof under the owner's signed control. This is part of the cutover (FR-020), not of the mirror build.
- **No paid or cloud dependency**: all components of the mirror are open source and run on Omniverse2.
- **Unchanged until cutover**: the production observer stays in OBSERVE. Signed production rules, the owner's finite allowance, CRE gating and merge rules are unchanged by this feature.
- **Shared host**: Omniverse2 is shared with other projects (for example x-verse_fabric). The mirror touches only Forge-C resources.
