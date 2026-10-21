# ADR-0014: Structured author tasks for the local RTX profile

- Date: 2026-10-21
- Status: implemented for the SWE.1 and SWE.2 authors of LL work orders under `--profile local-rtx-v1`; not qualified.
- Feature: `010-local-rtx-optimization` (LRTX-FR-008..FR-015), follows ADR-0013.

## Context

The QWEN-TRIAL GPU runs showed that qwen3-coder:30b on the 8 GB RTX 4070 is quality-limited, not speed-limited, when
one agent session authors a whole phase. Gates rejected IWDG SWE.2 three times out of three and RCC SWE.1 three times
out of three, for omissions in large outputs (unallocated SWRs, incomplete register-effect contracts, interfaces
without IDs). The monolithic SWE.1 agent prompt of the profile's first run (WO-0009A-...-lrtx1) had a median of
11,951 prompt tokens per call; prefill on this host runs at about 70 tokens/s without prefix-cache reuse.

Probe 2026-10-21 (throwaway Fabro 0.362 server in the profile namespace): a command node's stdout is **not**
available as `context.response.<node>` ("stdin_source ... was not found in workflow context").

## Decision

1. Under an explicit local profile, the author node of each phase listed in the profile's `structured.phases_by_layer`
   becomes a Fabro command node with the same id, edges, role binding and visit limit. It runs
   `forge_factory.lrtx.runner author --phase <SWE.n>`. Without a profile the graph is byte-identical to the
   preserved baseline (frozen fixtures `tests/compat/lrtx`).
2. The runner splits the phase into coherent tasks: SWE.1 gets one requirement group per RM register (at most five
   fields) plus a cross-cutting group. SWE.2 gets an interface/allocation task and a design-rationale task. Each task
   is one tool-less structured call through the profile's admission gateway. The packet carries the role, the role
   SKILL by path and hash (mission, work instruction and authoritative-input rules), the source excerpts and current
   artifacts with their hashes, the full criteria and the output JSON schema. The serialized prompt is counted; a
   packet that does not fit with its output reserve is refused, never truncated.
3. Every answer is validated deterministically: the schema, plus the rules the phase gates apply (EARS, register
   contract, coverage of every inventory field or an explicit scope exclusion, allocation of every SWR, safe call
   arguments, no compliance claims). Failures are repaired locally: the previous answer and only its findings go
   back to the model. Unaffected tasks are reused from checkpoints keyed by the task's base input hash. Changed
   upstream artifacts change that hash, which invalidates dependent tasks.
4. Repetitive content is rendered deterministically: SWR numbering, tables, trace CSV, upstream-gap tables, the
   safety statement prescribed for the manifest's allocation status, resource requirements from the owner's
   budgets, PlantUML views, the allocation note and `api_calls.json`. Semantic content (requirements,
   functions/allocation, design rationale) comes only from validated model answers. If any task is invalid,
   nothing is assembled: the reply is FAILED and missing content stays missing.
5. The runner writes only through the same role authorization the Fabro policy hook applies to that author node
   (`policy.authz.Authorizer` with the run binding). It persists the agent-output-contract reply to
   `.forge-run/lrtx/<phase>/reply.json`, and the unchanged author gate reads it by pipe. The runner deletes any earlier
   reply before a visit. Inspectors, gates, routing, rework limits and packaging are unchanged.
6. Budgets are shared. All calls of one visit count against the role's `max_turns` (agents.yaml). One visit is one
   author visit for the route gate's rework accounting, so decomposition never resets a budget (LRTX-FR-014).

## Consequences

- The CLAUDE.md requirement that production agents load a versioned SKILL.md and use only role-approved MCP
  operations is met as follows. Structured tasks carry the SKILL by hash and call no tools at all. Every write is
  authorized per role exactly as a tool write would be.
- HAL-layer work orders keep the agent authors until structured HAL tasks exist (the runner refuses HAL).
- Prefix-cache reuse across agent turns is lost for structured tasks. Efficiency claims must compare total time,
  tokens and energy per accepted work order, not per-call prompt sizes alone (spec acceptance 3).

## Rollback

Remove the phase from `structured.phases_by_layer` (or run without `--profile`). The agent author returns with the
same node id and edges.
