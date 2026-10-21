# Implementation plan: preserve baseline, qualify an opt-in local profile

## Architecture

Use one repository, the preserved source SHA and an experimental development branch. Maintain one set of quality
gates. Put local preparation, scheduling and structured-task logic behind explicit versioned profile selection.
Do not replace the current workflow globally or maintain a second, weaker copy of the assurance rules.

The implementation selector is to be designed and tested before adding it to `workorder.py`; there is no new
working CLI flag in the separation increment. Current `--acp-authors codex` and `--acp-inspectors claude` behavior
is retained. Explicit local-only selection must fail before launch when combined with ACP or external endpoints.

## Increment order

| Increment | Scope | Required evidence |
|---|---|---|
| P0 | Source reference, branch, baseline record, host preservation/isolation design | References resolve to pinned SHA; initial diff adds files only; host state backup remains separately tracked |
| P1 | Explicit profile, manifests, isolated runtime roots, local endpoint enforcement, admission queue and metrics | Existing behavior comparisons; queue/cancellation/endpoint tests; no service switch |
| P2 | Context packets, structured requirements/effects/architecture data, deterministic rendering for SWE.1-SWE.2 | Replay real rejection cases; source coverage, missing-item and no-truncation tests; original gates still apply |
| P3 | Checkpoints, dependency-aware localized repairs, direct reinspection and inspection partition/aggregation | Stale-baseline refusal, budget accounting, complete checklist coverage and independent defect detection |
| P4 | Extend existing SWE.3-SWE.6 scaffolds and coherent task boundaries | Cross-artifact and complete-phase tests; fresh full local runs |
| P5 | Model routing experiments and final offline campaign | Frozen 30-case evaluation, all-attempt costs, inspection quality, failure classification, baseline comparison |

## Integration points to inspect before editing

- `factory/python/forge_factory/workorder.py`: explicit selection, launch validation and provenance.
- `workflow/builder.py`, `workflow/prompts.py`: preserve existing output when the local profile is absent.
- `llm_gateway.py`: admission queue, timing, cancellation and progress. Its buffered streaming currently permits
  retrying empty responses; do not forward partial tool calls and then replay them on retry.
- `fabro/runconfig.py`, `acp/`: unchanged legacy provider behavior and isolation assumptions.
- Existing deterministic register-map, trace matrices and scaffolds: extend instead of duplicating functionality.
- Existing `config/factory/token-policy.yaml` and Ollama service already enable several proposed optimizations;
  measure actual enforcement before adding new switches.

Each task packet carries input/artifact hashes, role, task/phase IDs, applicable criteria and expected output
schema. Persist validated results outside chat history. Define explicit invalidation dependencies before reuse.
Cross-cutting safety, resources, invariants and consistency are phase-wide obligations, not optional summaries.

## Protect the existing execution line

Before shared runtime edits, freeze representative generated workflows and node bindings for greenfield LL/HAL,
brownfield RCC, IWDG and the current ACP conversion. Compare output with the original snapshot in a separate
process/worktree; normalize only machine-specific paths and timestamps. Include relevant ACP policy and proxy
tests plus v0.1/v0.3 regression and the design checker. Do not refresh expected results merely to accept a drift.

Version-specific application environments must not inherit conflicting `FORGE_*` state, archive or service
settings. Use resolved paths to reject equal/nested roots and symlink overlap. Never source an experimental
environment into the running service definition. Ports, queues and model gateway ownership must be explicit.
Read-only tool/model/manual sharing needs hashes; writable caches and state remain separate.

Before deployment on the RTX host, capture the actual dirty working tree and effective configuration in a secure
backup, record tool/model digests, and verify access to original archives. A Git reference cannot preserve OAuth
availability or externally installed software by itself. Preserve credentials through existing secure operations,
never by committing them or logging their contents.

## Validation and experiment design

Start with deterministic replay fixtures from QWEN-TRIAL failures, then fresh SWE.1/SWE.2 runs, then complete runs.
Keep original source requirements and independent test oracles frozen. A developer-model repair and the runner
that decides acceptance have different authority. Stage failures must be classified and all attempts counted.
Use matched inputs/revisions for performance comparisons; retain the GPU-available 30B run as historical context,
not a directly comparable full-success latency baseline. Source-level compatibility is not a live cloud run.

No autonomous safety-policy modification, production promotion, merge or deployment is part of feature 010.
The preserved source line remains available regardless of local qualification results.
