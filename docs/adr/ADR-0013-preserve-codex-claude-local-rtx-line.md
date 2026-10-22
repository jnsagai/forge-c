# ADR-0013: Preserve the Codex/Claude factory and isolate local RTX optimization

- Date: 2026-10-21
- Status: owner-approved direction; source branches established; runtime implementation and deployment pending.
- Feature: `010-local-rtx-optimization`.

## Context and evidence

The owner accepted smaller work packets, structured outputs, deterministic assembly, localized repairs,
independent bounded inspections and measured local-model selection. The owner explicitly requires retaining the
existing factory that works with Codex and Claude while developing an optimized local version.

The preserved source is main commit `86f1f40c030bc721e7e5125a572d69647c4ac041`, tree
`aedbf050d1fee9a9fedf1544cfb7996877298dcf`. It includes CAPA-067 and the rc4 evidence merged in PR #33.
The RC1 record reports a READY run for each of seven examples across the initial campaign and follow-up fixes;
this is not seven first-pass successes on a single revision. The IWDG HAL rc4 package records zero gaps and
`READY_FOR_OFFLINE_REVIEW`, not safety approval. The actual archive remains on the owner's data volume.

ADR-0011 and ADR-0012 define the retained Codex author and Claude inspector/Release Manager ACP integrations.
Existing CLI defaults remain exactly as implemented; this decision does not silently make ACP or local Qwen the
default, change subscriptions, or re-enable a suspended provider.

## Decision

1. Preserve `baseline/codex-claude-2026-10-21` at the source SHA above. Do not commit development changes to this
   reference. The SHA is the immutable identifier; no GitHub branch-protection rule is claimed to be installed.
2. Create `feat/010-local-rtx-optimization` from that same SHA. This feature has a separate experimental identity;
   do not relabel the shared v0.4/v0.5 evidence or publish an unqualified release version.
3. Keep one repository and shared engineering quality rules. Local scheduling, prompt preparation, assembly and
   model configuration will be explicit opt-in behavior. Existing commands and ACP flows must retain their
   behavior when that selection is absent. Local-only selection must reject ACP and external model endpoints.
4. Use separate checkouts and separate mutable deployment roots, virtual environments, state databases, queues,
   Fabro config/home/storage, archives, logs and service identities. Allocate non-conflicting local ports. Shared
   immutable tools/manuals/models may be read-only references with hashes. Never share writable runtime state.
5. Before any host deployment, record the actual working source revision (including uncommitted changes), pinned
   tool/adapter/model identities and effective configuration. Preserve external evidence and verify its hashes.
   Keep secrets out of Git and public manifests. This source snapshot is not a backup of that host state.
6. Leave the working deployment running from its existing checkout and configuration. Do not run service-install,
   migration or upgrade scripts against it. Schedule GPU experiments to avoid competing workloads; do not kill
   unrelated owner workloads automatically.
7. Require compatibility tests for the unchanged flow and separate local acceptance evidence. Never transfer a
   successful Codex/Claude run into a claim that Qwen passed. No automatic merge, activation or production promotion.

## Compatibility and rollback

- Preserve author/inspector separation, full checklists, gate criteria, rework limits and offline packaging.
- Compare existing workflow graphs, prompts, node bindings and ACP conversion before/after each relevant change;
  normalize only environmental paths, not meaningful fields. Include LL, HAL, brownfield and both peripherals.
- Shared fixes must have tests covering both lines. Local experiments never justify rewriting the preserved
  reference, archived work products or frozen expectations to make regression tests pass.
- Rollback means stopping only the experimental deployment and continuing the existing deployment. If a checkout
  must be reconstructed, create another checkout at the pinned SHA. Do not reset or clean an active checkout.
- Host-side rollback verification is NOT_RUN here; the running owner machine is not available in this environment.

## Initial delivery boundary

This increment contains version references, this decision, a baseline record and the authored feature plan.
It changes no runtime implementation, provider configuration, existing service, safety policy or release gate.
The task file distinguishes implemented preservation from pending optimization and host qualification.
