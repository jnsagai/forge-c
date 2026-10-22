# Feature 010: Isolated local RTX optimization

**Date:** 2026-10-21  
**Status:** owner accepted the recommendations and preservation requirement; runtime NOT IMPLEMENTED.  
**Branch:** `feat/010-local-rtx-optimization`  
**Baseline:** `86f1f40c030bc721e7e5125a572d69647c4ac041`.

## Outcome

Qualify an entirely local Forge-C execution profile for the owner's RTX 4070 Laptop (8 GB VRAM), i9-14900HX and
32 GB RAM. Preserve the existing Codex/Claude factory as a separately addressable source and deployment line.
Improve completed-work quality, latency and resource use through smaller coherent tasks and deterministic
support, with the same ASPICE SWE.1-SWE.6 gates and external offline review authority.

## Evidence and limitations

`evidence/v0.4/runs/QWEN-TRIAL/README.md` records q4 as concluded BLOCKED at SWE.1, followed by six GPU-available
trials: no stage timeout, three IWDG SWE.1 passes followed by SWE.2 rejection, three RCC SWE.1 rejections. Those
trials do not measure Qwen's SWE.3-SWE.6 or SWE.2+ inspection quality. Aggregate throughput is not a guarantee of
future latency or a substitute for prompt-processing and generation measurements.

Observed omissions (register effects, requirement allocations, interface IDs) are replay fixtures. They must be
triaged against source requirements and tool behavior; a gate rejection is not automatically a model defect.
An incomplete package's gap count is not a count of independent model errors.

## Requirements

| ID | Requirement |
|---|---|
| LRTX-FR-001 | Preserve the existing source at the pinned SHA and leave main/deployed services unchanged during experimental development. |
| LRTX-FR-002 | Require explicit selection of local optimization; absent selection preserves existing graph, prompts, providers, ACP integration and effective defaults. Reject unsupported combinations rather than silently change them. |
| LRTX-FR-003 | Isolate writable runtime state, archives, environments, services and ports. Refuse overlap with the existing deployment, including symlink aliases. |
| LRTX-FR-004 | Record the actual deployed revision, dirty changes, effective non-secret configuration and tool/model identities before host changes. Preserve external archives and verify their hashes. |
| LRTX-FR-005 | In local-only mode reject ACP/cloud endpoints and external fallback. Qualify with external networking denied and dependencies/manuals available locally. Record enforcement separately from a declared provider name. |
| LRTX-FR-006 | Admit one inference request at a time to the local backend, with observable bounded waiting, cancellation and backpressure. Do not silently accumulate concurrent agent prompts. |
| LRTX-FR-007 | Measure queue, model load, prompt processing, generation and tool time separately when observable. Label unsupported counters UNKNOWN. Record GPU residency, memory pressure and energy measurement coverage. |
| LRTX-FR-008 | Assemble task-specific context from original source excerpts, current artifact versions, relevant findings, full applicable criteria and permitted tools. Count the complete serialized prompt and reserve output space; refuse or repartition overflow without truncating required evidence. |
| LRTX-FR-009 | Reuse validated artifacts only with matching dependency hashes, policy/tool/model/prompt versions and role scope. Do not reuse author context or author judgments as inspector evidence. Measure runtime prefix-cache reuse rather than assume it. |
| LRTX-FR-010 | Split SWE.1 into coherent requirement groups, effects and verification mapping; retain a complete source-to-requirement inventory and a global consistency check. Do not limit completeness through a fixed arbitrary requirement count. |
| LRTX-FR-011 | Split SWE.2 into allocation, interfaces and behavior decisions. Require every SWR to be treated, including resource and reset invariants at the proper component level. Do not invent functions for component-level constraints. |
| LRTX-FR-012 | Validate structured intermediate outputs; deterministically render repetitive document tables and diagrams while preserving existing final formats. Missing semantic content must remain missing, never be synthesized as PASS. |
| LRTX-FR-013 | Repair only the identified invalid elements and impacted dependencies; preserve validated content through checkpoints. Reinspection of a valid unchanged baseline must not rerun authorship. |
| LRTX-FR-014 | Keep existing phase rework/turn constraints and shared accounting across subtasks. Decomposition must not reset budgets. Preserve the owner's unlimited total local-token policy unless separately changed. |
| LRTX-FR-015 | Keep author/inspector identities, contexts, tools and write permissions distinct. Each required inspection criterion receives its full text and primary evidence; deterministic aggregation refuses missing verdicts and preserves all findings. Include cross-artifact consistency review. |
| LRTX-FR-016 | Extend existing SWE.3-SWE.6 decomposition and scaffolds rather than duplicate them. Test expected results come from requirements/contracts, not uncritically from generated implementation. Retain complete phase gates. |
| LRTX-FR-017 | Distinguish infrastructure, performance, factory/oracle defects, product defects and unmeasured quality. Timeout is not a semantic quality verdict. Never declare successful completion from an agent's status alone. |
| LRTX-FR-018 | Keep qwen3-coder:30b and its measured digest/quantization as the initial comparison baseline. Qualify smaller local models per task before routing work to them; include loading/switching costs. |
| LRTX-FR-019 | Qualification includes frozen independent defect-injection and holdout cases, failed first attempts and all retries. No changes to gates, thresholds, test oracles, safety scope or promotion authority to improve results. |
| LRTX-FR-020 | Optimization and self-improvement candidates remain isolated proposals with independent regression evidence under existing CRE/AFO authority. No automatic deployment or weight training is introduced. |

## Initial configuration experiment

- RTX available to the factory; check rather than terminate another owner's workload.
- One inference request and one loaded model; existing Flash Attention and q8_0 KV configuration retained.
- Compare current context with 16k only after complete prompt measurement; aim for 3k-6k input tokens per task.
- Keep tool schemas, required source material, full inspection criteria and output reserve within the context.
- Existing total local token policy and phase rework criteria remain unchanged.
- Timeout values are a bounded execution safeguard; optimize task size before recalibrating them from measurements.
- qwen3:8b is a candidate for narrow tasks, not a qualified replacement inspector. Same-family isolated sessions
  do not prove independence of model errors.

## Acceptance

1. **Preservation:** all pre-existing tracked files unchanged in the initial separation increment; later local
   integration passes comparison tests for the existing default/ACP paths and relevant legacy tests.
2. **Local isolation:** rejected overlapping state roots/endpoints, rejected ACP/cloud selection, and a full
   campaign with external network access denied. Checkpoints and archive provenance identify the selected profile.
3. **Efficiency:** target at least 50% reduction of median prompt input against the frozen comparable baseline;
   no required content truncation. Compare total time/tokens/energy per accepted work order, including failures,
   queueing, model switches and retries; do not claim improvement from per-call metrics alone.
4. **Structure:** target fewer than 1% invalid structured responses in the evaluation set; schema correctness
   does not substitute for semantic correctness.
5. **Quality:** all seeded critical defects detected; no known false READY. At least 27 of 30 representative
   end-to-end local trials reach READY_FOR_OFFLINE_REVIEW, with all remaining failures honestly packaged BLOCKED.
   Freeze the case mix before running, include RCC/IWDG and LL/HAL, identify repeated/stochastic cases and report
   uncertainty. This is a pilot operational criterion, not a reliability proof or safety qualification.
6. **Inspection:** report semantic defect detection and false rejections separately from deterministic gate
   detection; include omitted requirements, inverted behavior, wrong test properties, commented-out code and
   safety-scope contradictions in independently held cases.
7. **Infrastructure:** no unclassified OOM/stall; failures preserve evidence and respect bounded recovery. Energy
   must state whether measured at the wall or GPU-only; unavailable readings remain UNKNOWN.

Targets above are proposed experiment criteria, not measured achievements. Host rollback, local throughput,
quality, energy, and cloud-provider live regression remain NOT_RUN until evidence is captured on the real host.
