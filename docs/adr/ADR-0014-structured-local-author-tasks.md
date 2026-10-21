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

## Addendum 2026-10-21: all six phases (LL), time boxes, inspection, accounting

Implemented since the first version, each through a CRE CHANGE promotion, with tests on scripted answers against
the real tools and the unchanged gates:

- **SWE.3:**
  - One code task per SWE.2 interface function (software unit). It is validated against the signature, the
    generated defines and the register block, the trace tags of its own unit, and compilation in the generated
    header.
  - The units are assembled before the generator's marker, from a pristine copy of the generated header.
  - Compile (both profiles), swe3_all and cppcheck run through the role-granted operations, journaled to
    `evidence/tool-results.jsonl` exactly like agent calls (`lrtx/tools.py`).
  - Unit specifications and the detailed design are rendered from the validated tasks and the measured tool
    results.
- **SWE.4–SWE.6:**
  - Test tasks take their oracle from the requirements and the register contract and never see the implementation
    (unit tests per UT id; Renode target and host integration programs; target scenarios per requirement group with
    run_robot's observation rule).
  - A failing test is triaged per ADR-0008: a corrected test is declared with report_defect kind TEST, a correct test
    files a CODE defect upstream. Never silently bent.
  - The reports are rendered from the tool results.
- **Time boxes:** Fabro 0.362 ends a command node with no activity for 1800 s, and stdout does not count (two probes,
  2026-10-21). A visit therefore stops before a model call that could cross `visit_time_s` (1200 s). A separate
  continuation node with its own visit limit resumes the same visit (call budget and findings kept); the phase's
  rework budget is never consumed by a time box.
- **Inspection:**
  - One task per required checklist item on the frozen baseline (no author context). Verdicts are bound to the
    baseline hash and recorded through the unchanged `check_inspection` operation.
  - Findings that the evidence or the owner's recorded decision refutes return to the inspector: a PENDING
    allocation judged as a failure, a missing verification criterion that the document has, an unknown SWR. Other
    findings are kept as written.
  - A valid, never-inspected baseline goes back to the inspector without re-running authorship.
- **Accounting:**
  - A visit's model calls share the role's max_turns.
  - In-visit repair rounds continue only while the number of findings falls.
  - For profile runs only, a structured visit that failed before assembly adds its deterministic task issues to the
    author rejection record (`LRTX_TASK_INVALID:`). STUCK and the progress rule then compare real progress; without
    a profile the rejection record is unchanged (tests and frozen fixtures).
- **Graph safety:** the node swap replaces whole statements (quote-aware parser), and every profile-graph variant is
  checked with `fabro validate`.
- **Failure-cycle breaker:** check nodes whose normal path is a non-zero exit (continuation and direct re-inspection
  checks) print a digit-free per-phase counter, because Fabro stops a run after three identical failure signatures and
  normalises digits (ADR-0005 #5; run lrtx6 ended this way).

- **Structured-output mode (LRTX-T012):** `python -m forge_factory.lrtx.structured probe --model M` measures whether
  the served model honours a JSON schema or plain JSON mode. The record is stored under the profile state and bound to
  the model digest. Visits use the probed mode and log it per call. An unprobed or stale record keeps the JSON-schema
  request. Unconstrained output is never selected; answers are always validated against the full schema.

HAL work orders keep the agent nodes; structured HAL tasks are not implemented.
