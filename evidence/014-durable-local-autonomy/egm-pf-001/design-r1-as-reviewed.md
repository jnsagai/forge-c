# Forge-C Process-First Lab: SWE.1 with an Ornith Author and a Qwen Inspector

*   **Author:** jnsagai (owner), drafted by Claude (Elephant)
*   **Status:** Reviewed, NOT approved. EGM review concluded 2026-10-31 without resolution; the design gate is
    BLOCKED by open Blockers. See `evidence/014-durable-local-autonomy/egm-pf-001/REVIEW-SUMMARY.md`. Do not
    implement shape-dependent items (attempt plan, swap, scheduler, dispatch) from this revision.
*   **Date:** 2026-10-31
*   **Source of truth:** Feature 014 Spec Kit (`specs/014-durable-local-autonomy/`). This design implements
    `PROCESS-FIRST-ORNITH-QWEN-EGM-CLAUDE.md` (plan, `876d75f`). Source facts: 
    `evidence/014-durable-local-autonomy/egm-pf-001/SOURCE-INVENTORY.md`.

--------------------------------------------------------------------------------

## Overview

Forge-C turns owner scope plus frozen sources (reference manual, headers, existing code) into embedded-C drivers and
ASPICE-inspired work products, using local models on one 48 GB GPU (Omniverse2). Today every experiment runs the
whole SWE.1–SWE.6 graph. This design adds an opt-in **process lab** that runs **only SWE.1** (software requirements
analysis) on a small corpus of drivers. It scores each SWE.1 package against a frozen oracle that the author cannot
see, and passes the package to a minimal SWE.2 importer. A tiny CRC end-to-end smoke run stays green after each
increment. The lab uses two model roles on the same GPU, never at the same time: **Ornith-1.5-35B-A3B Q8_0** writes
requirements, then **Qwen3.8-27B Q8** inspects them read-only. Each role runs as its own batch, with a verified idle
handoff in between. The existing AFO queue, gateway, inspection and release code are reused. There is no new
scheduler, no new release authority and no EGM runtime.

## The Problem

1.  **Full-pipeline runs are slow and blur the cause of a failure.** The overnight Qwen cohort reached 2/3 scoped
    functional passes on a two-function CRC slice. Each trial needed hours and hundreds of requests, and its strict
    packages still had 16 and 35 open gaps. When a run fails in SWE.5, you cannot tell whether the SWE.1 requirements
    were the root cause. Improving one process by rerunning six is the wrong feedback loop.
2.  **SWE.1 output is not yet a usable interface.** Requirement IDs are renumbered on every assembly
    (`lrtx/swe1.py:508`). SWE.2 reads SWE.1 by regex over markdown. Two ID patterns disagree (`ears.py` vs
    `swtrace`/`swe2`). The reference manual RM0486 is hard-coded in several places. A downstream process cannot rely
    on SWE.1 output, and a different MCU cannot be tested.
3.  **SWE.1 quality is not measured against anything independent.** Gates check structure, and the same-family model
    inspects. Nothing checks whether the critical obligations of a driver were captured. Delivery-first oracles sit
    in `inputs/`, where the author can read them.
4.  **The factory cannot change models between roles.** One job is pinned to one model
    (`request_admission.py:49`). A profile serves one model. The gateway shares the provider's process namespace, and
    cache keys use the model *name*, not its digest (`lrtx/structured.py:172`). A model swap is either impossible or,
    if done by renaming, silently reuses stale cached answers.
5.  **The Ornith choice has no evidence behind it yet.** The only data is a 36-trial standalone speed study: about
    150 decode tokens/s, and 4/9 full-contract passes at best. That is a reason to run an experiment, not to make
    Ornith the default.

**Proposed solution in one line:** an opt-in `QM_PROCESS_LAB` mode that cuts the existing graph to SWE.1. It runs
author, inspection and rework as separate one-model AFO jobs with a fenced model handoff, and emits a versioned
`forge-c/process-handoff/1` package scored by a frozen external oracle.

## Goals

*   **G1 — SWE.1-only execution.** One work order in `QM_PROCESS_LAB` mode runs SWE.1 author → deterministic
    validation → inspection → at most two inspect/rework rounds (D4), then stops. It records a truthful terminal state and touches no
    SWE.2–6 node.
*   **G2 — Fenced per-role model handoff on one GPU.** Author and inspector run as separate jobs, each under its own
    one-model profile. A switch happens only after the existing quiescence proof. Stop/revoke and held leases block
    it, and every switch's load/unload time is recorded.
*   **G3 — Identity-correct caching.** Any change of model digest, profile sha, reasoning setting or source hash
    invalidates cached author, inspector and visit results (closes the name-only `input_hash` gap).
*   **G4 — Versioned handoff.** SWE.1 emits `forge-c/process-handoff/1` with stable requirement IDs, source refs,
    hashes, gaps, a per-package `criteria_result` and a separate strict-release status. Process maturity (USABLE) is
    decided only at corpus level (D5). A minimal SWE.2 importer accepts valid
    packages and rejects duplicate, missing or contradictory IDs.
*   **G5 — Independent scoring.** A frozen, hash-bound oracle per corpus driver (obligation inventory with
    critical/noncritical marks) scores each package. The author cannot read it. Model agreement never counts as a
    pass, and an inspector timeout is recorded as `NOT_INSPECTED`.
*   **G6 — Fair A/B readiness.** The lab can run configuration A (Ornith author + Qwen inspector) and B (Qwen author +
    Qwen inspector) on the same corpus and oracle. The report counts every failed or interrupted trial and the
    model-switch cost.
*   **G7 — No regression.** Strict graphs, `QM_DELIVERY_FIRST_DEMO`, Feature 015 workflows and the tiny CRC smoke
    keep passing their existing tests unchanged.

## Non-Goals

*   No SWE.2–SWE.6 process lab in this design; SWE.2 gets an importer only.
*   No model promotion. Ornith does not become the default author anywhere outside the opt-in lab, and the Qwen
    author profile stays unchanged as baseline and rollback.
*   No native GPU run, deployment, grant or remote activation. Cloud and loop10 CI report `NATIVE_NOT_RUN`. Live
    experiments need a new owner execution window.
*   No new scheduler, database, release authority, autonomous model router or EGM runtime.
*   No claim of Automotive SPICE compliance. RM-only driver exercises are labelled QM / ASPICE-inspired.
*   No change to strict release policy, stored release archives, safety policies or historical evidence (the 2/3
    cohort, the expired grant and the mission counters stay as recorded).
*   No running both Q8 models resident at once, and no parallel inference.
*   No change to Feature 014 DA task ticks from this work, unless real evidence exists under the normal rules.

## Open Questions

*   **Q3 — Which corpus cases are unseen?** The F015 GPIO+CRC test set and the 9-baseline calibration subset are
    already spent. A held-out case (different MCU or non-peripheral component) does not exist yet.
*   **Q4 — Who writes and reviews the oracle?** The plan requires independent subject-matter review of each obligation
    inventory. The reviewer and the review record format are not decided.
*   **Q5 — Ornith reasoning setting for the A arm.** The speed study's best full-contract result (4/9) used default
    thinking, but one trial was truncated at 8,192 tokens; the 2,048-token budget was semantically 3/9. The value is
    fixed at preregistration, not in this design. The profile must carry it explicitly.

### Resolved decisions (owner, 2026-10-31)

*   **D1 — Role runs:** one work order per driver with planned attempts (author, inspect, rework, D4: up to five). Each attempt is its
    own one-model AFO job.
*   **D2 — Swap actor:** the operator performs model swaps by runbook. AFO never loads or unloads a model by itself.
*   **D3 — Ornith build:** the official `ornith-ai/Ornith-1.5-35B-A3B-GGUF` Q8_0, sha256
    `de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3`, 37,802,149,280 bytes. It is already in the
    Omniverse2 Ollama blob store. This replaces the plan's AtomicChat reference.
*   **D4 — Rework cap:** up to two semantic reworks (AUTHOR, INSPECT, REWORK, INSPECT, REWORK). The rework output
    is inspected once, and nothing is inspected a third time.
*   **D5 — USABLE scope:** USABLE is a process maturity decided only by a corpus decision report (≥ 5 drivers incl.
    one unseen, per-driver results visible). A single package gets only a `criteria_result`.

## Critical User Journeys (CUJs)

### CUJ 1: Owner runs one SWE.1 lab trial on a driver

*   **Given**: The stack is STOPPED, a `QM_PROCESS_LAB` work order for CRC is prepared with hash-bound sources, the
    Ornith and Qwen profiles are pinned, the oracle is frozen outside the author's workspace, and the owner has opened
    an execution window.
*   **When**: The owner queues the order and sets intent RUNNING.
*   **Then**: AFO runs the Ornith author job, proves quiescence, swaps to Qwen and runs inspection, then up to two
    inspect/rework rounds with Ornith as the rework author. The order ends in a terminal state with a `forge-c/process-handoff/1` package, an oracle score,
    and gap and switch-time records. No SWE.2–6 node runs.

### CUJ 2: Stop arrives during a model switch

*   **Given**: The author job finished, and the handoff to Qwen is in progress.
*   **When**: The owner sets intent STOPPED (or a grant is revoked).
*   **Then**: No new model is loaded and no inference starts. The order gets a truthful terminal disposition, and the
    partial records are kept.

### CUJ 3: Inspector times out or answers invalidly

*   **Given**: Qwen inspection of a requirement batch is running.
*   **When**: The time box or the repair budget runs out.
*   **Then**: Those requirements are marked `NOT_INSPECTED`, never PASS. The package can still be scored by the
    oracle, and its `criteria_result` cannot be MEETS if a critical obligation is uninspected and unmatched.

### CUJ 4: SWE.2 imports a handoff

*   **Given**: A sealed SWE.1 handoff package.
*   **When**: The SWE.2 importer reads it.
*   **Then**: It reports each requirement as usable, ambiguous or missing. It rejects duplicate or dangling IDs and
    hash mismatches. Its report is deterministic for the same package.

### CUJ 5: Model identity changes between trials

*   **Given**: A cached inspector verdict exists for a requirement batch.
*   **When**: The GGUF digest, profile sha or reasoning setting changes while the model alias stays the same.
*   **Then**: The cache misses, and the work is redone and recorded under the new identity.

## Technical Plan (Architecture)

### Components and data flow

```text
 operator (runbook)            AFO (existing)                       Fabro run (existing engine, cut graph)
 ------------------            --------------                       --------------------------------------
 lab intake  ───────────────▶  order WO-LAB-<drv>  attempt plan:
  (hash-bound sources,          seq1 AUTHOR  profile=lab-ornith ─▶  swe1_author → author_gate → lab_seal
   oracle stored OUTSIDE        seq2 INSPECT profile=lab-qwen   ─▶  swe1_inspector → lab_inspect_record → lab_seal
   the workspace)               seq3 REWORK  profile=lab-ornith ─▶  swe1_author(findings) → author_gate → lab_seal
                                scheduler: defer if attempt
 model swap (runbook):          profile ≠ resident profile
  DRAIN→QUIESCENT→STOP          (RESIDENT_PROFILE_MISMATCH)
  →START other profile
  →identity probe→RUNNING
                                order terminal ─────────────────▶  process-handoff/1 package (in workspace)
 lab score (CLI, no model) ◀── reads package + oracle store ──────  score report + maturity (outside workspace)
 SWE.2 importer (CLI)      ◀── reads sealed package
```

### 1. Lab mode and SWE.1-only graph

A new mode `QM_PROCESS_LAB` sits beside `QM_DELIVERY_FIRST_DEMO`. It follows the same pattern: a `process_lab.contract()`
validates a `forge-c/process-lab/1` block in the work order, and `process_lab.workflow()` asks the builder for a
**SWE.1-only** graph. The builder gains an explicit `stop_after="SWE.1"` option. When it is set, `_build` emits only
SWE.1 nodes, and the unconditional `swe1_inspect_gate → SWE.2` edge goes to a lab terminal node instead. The default
(`None`) leaves every existing graph byte-for-byte unchanged, and a test pins that.

Each attempt runs a different subgraph, selected by the attempt's `role`:

*   **AUTHOR** (seq 1): structured SWE.1 author (`lrtx.runner author --phase SWE.1`), the existing deterministic
    author gate (structure, EARS, ReqIF, source refs, register effects), then `lab_seal`.
*   **INSPECT** (seq 2): the existing stepwise inspector (`lrtx/review_semantic.py`) over the frozen SWE.1 baseline,
    then `lab_inspect_record`, then `lab_seal`. In lab mode, inspector FAILED/CONTINUE does **not** route to rework
    inside the run. The result is recorded as findings, and the run ends.
*   **REWORK** (seq 3, only if seq 2 produced actionable findings): the author receives the consolidated findings and
    the same sources, rewrites once, the author gate runs, then `lab_seal`.
*   **Second pair** (D4, `max_semantic_rework: 2`): seq 4 INSPECT re-inspects the seq-3 candidate. Seq 5 REWORK runs
    only if seq 4 has actionable findings. There is never a third inspection. Requirements changed by the final
    rework carry inspector outcome `NOT_INSPECTED` with reason `REWORKED_AFTER_LAST_INSPECTION`, because an
    inspection is valid only for the exact seal it read (AT11).

`lab_seal` is deterministic. It hashes the current SWE.1 artifacts, writes or updates the handoff package, and
records the attempt's model/profile/runtime identity. A seal is immutable. The REWORK seal references the AUTHOR seal
by hash, so the prior candidate stays auditable (AT11). The finalizer, release manager and SWE.2–6 nodes do not exist
in a lab graph, so no release package can be produced.

### 2. Attempt plan instead of recovery (D1)

The lab work order carries an immutable `attempt_plan`. It has 2–5 entries `{seq, role, profile, model_profile}` in
the fixed role order AUTHOR, INSPECT, REWORK, INSPECT, REWORK. Today an
order has one `profile` for all attempts, and a different `model_profile` exists only as a recovery action. For lab
orders:

*   Dispatch creates attempt *n* from `attempt_plan[n]`. The recovery planner is **not** consulted. A failed or stopped
    attempt makes the order terminal (`LAB_ATTEMPT_FAILED` / `LAB_ATTEMPT_STOPPED`) and never triggers recovery.
*   `product_job.prepare` takes `profile` and `model_profile` from the attempt entry. The job stays pinned to one
    model, so the `request_admission.py:49` and `role_capability.py:155` invariants are unchanged.
*   Attempts 2 and 3 resume the previous attempt's workspace with the existing validated brownfield resume. They may
    read the earlier seals, but they cannot change them.
*   A REWORK entry is skipped, and the order goes terminal, when the INSPECT before it produced no actionable
    finding. The order also goes terminal when the plan is exhausted.

### 3. Fenced model swap by runbook (D2)

There are two lab profiles: `lab-ornith-q8` (llama-server, D3 digest, its own sampling/reasoning/context, no MTP)
and `lab-qwen38-q8` (the existing pinned identity `qwen3.8:27b-q8_0`, digest `8f5fb6b7…6039`, with inspector
sampling). Configuration B's author attempts use a third profile, `lab-qwen38-author-q8`: same model and digest, with
the author settings copied from the measured Qwen author profile. The existing Qwen author profiles are not
modified. Each profile serves exactly one model, as `stack.llama_server_spec` already requires. It gains one change:
it resolves `hf.co/<org>/<repo>:<tag>` manifests under `manifests/hf.co/…`, with the same digest and blob-size checks
(the Ornith file was pulled under that namespace).

**Scheduler rule.** `scheduler.preflight` adds `RESIDENT_PROFILE_MISMATCH` when the attempt's profile sha differs from
the profile sha in the running stack's `services.json`. This is a deferral, not a failure, like the existing
`NATIVE_INFERENCE_CAPACITY_HELD`. Because author attempts of every driver match the Ornith stack, all seq-1 attempts
run first. Seq-2 attempts wait until the operator switches to Qwen. This gives role batches through the existing
queue, with no new scheduler.

**Swap state machine** (runbook script `process-lab-swap.sh <from> <to>`, which only calls existing commands):

```text
RUNNING(P_from) ──set intent DRAINING──▶ DRAINING
DRAINING ──inference owner released + QUIESCENCE record + no SENT/UNKNOWN request──▶ QUIESCENT
   (timeout → stay DRAINING, report; never force)
QUIESCENT ──set intent STOPPED + settle_shutdown──▶ STOPPED
STOPPED ──stack stop (provider retire, kernel-proven exit)──▶ UNLOADED
UNLOADED ──stack start --profile P_to──▶ LOADING
LOADING ──health + model_identity(digest) + one admitted probe──▶ READY(P_to)
   (failed load / identity mismatch → stack stop → STOPPED; operator may restart P_from = rollback)
READY(P_to) ──set intent RUNNING (epoch+1)──▶ RUNNING(P_to)
STOP or revoke at any state ──▶ no further transition; the stack is left STOPPED
```

Each transition writes a `forge-c/model-swap/1` record: from/to profile sha and model digest, timestamps per state,
and operator. The A/B report sums these as the switch cost (AT13). In arm B, the "swap" between the Qwen author and
inspector profiles restarts the same model file. It is recorded the same way, so the two arms are compared on actual
measured cost, not an assumed zero. An unknown provider outcome or a held inference
lease keeps the swap in DRAINING. This reuses `MissionLedger.release_inference` and `provider_recovery`, so no new
code decides quiescence.

### 4. Identity-correct caching (G3)

The structured packet `input_hash` (`lrtx/structured.py`) adds model digest, profile sha, reasoning mode/effort and
schema mode. Visit and inspector checkpoints keyed on it therefore miss after any identity change (AT03). Existing
caches become unreachable, not wrong: a fresh lab run recomputes.

### 5. Stable requirement IDs

The author run keeps an **ID ledger** (`.forge-run/lab/swr-ledger.json`). It maps each requirement's obligation key
(source ref + register/field/op, or a normalized statement hash for non-register requirements) to an `SWR-nnn`
number. Assembly reuses the ledger number for the same key, assigns the next unused number to new keys, and never
reuses a retired number. The ID format stays `SWR-\d{3}`, so `swtrace`, `swe2` and `review_semantic` keep working.
The REWORK attempt loads the AUTHOR ledger, so IDs survive rework. The ID pattern in `ears.py` is narrowed to the
same `SWR-\d{3}` for lab packages only.

### 6. Target-neutral sources

The hard-coded `RM0486` (`lrtx/swe1.py`, `provided_requirements.py`, `assurance/swe12.py`) becomes the
`primary_manual` declared in the work order's target profile. The default stays RM0486, so existing orders are
unchanged. This is needed for the different-MCU holdout case.

### 7. Inspector outcome per requirement

In lab mode the inspector record gives every requirement one outcome: `FINDINGS`, `NO_FINDING` or `NOT_INSPECTED`
(timeout, repair budget exhausted, invalid answer, or never reached). `NOT_INSPECTED` is never folded into
`NO_FINDING`. The existing fail-closed behaviour of the strict path is unchanged.

### 8. Handoff package `forge-c/process-handoff/1`

The package is a JSON file, `process-lab/SWE.1/handoff.json`, plus the artifacts it hashes. Its schema lives in
`specs/014-durable-local-autonomy/contracts/process-handoff.schema.json` and is checked by the existing
`validate_contracts.py`. Fields:

*   `schema`, `experiment_id`, `order_id`, `process: "SWE.1"`, `target_profile`.
*   `inputs[]` (path, sha256, role `source|owner_scope`). The oracle is **not** listed.
*   `attempts[]` (seq, role, profile sha, model digest, runtime id, seal sha, status).
*   `artifacts[]` (path, sha256).
*   `requirements[]` (id, statement sha, `source_refs[]`, `assumption: bool`, verification criterion,
    inspector outcome).
*   `gaps[]` (`forge-c/advisory-gap/1` refs).
*   `downstream_constraints[]`.
*   `criteria_result`: set **only** by the scorer in its scored copy, never by the run. Values: `UNSCORED` (as
    sealed) | `MEETS` | `FAILS` | `NEEDS_HUMAN`. It is a per-driver result, not a process maturity.
*   `strict_release_status`: always `NOT_APPLICABLE_PROCESS_LAB`.

### 9. Oracle and scoring

Per driver, an oracle file `forge-c/swe1-oracle/1` lists obligations with id, critical flag, accepted source refs and
matching hints. It also carries reviewer and review date, and the hashes of the sources it was written against.
Oracle files live in an operator-only directory under the data root, outside `state/workorders`. The author and
inspector workspaces are confined (`PATH_OUTSIDE_WORKSPACE`), and the oracle path never appears in an order manifest.
A test asserts that no lab manifest, prompt or input list references an oracle path or hash (AT16).

`python -m forge_factory.process_lab.score <package> <oracle>` is deterministic and makes no model call.
*   It checks the package hashes.
*   It resolves every source ref against the bound inputs. An unresolvable ref counts as fabricated unless it is
    marked as an assumption.
*   It matches obligations by the oracle's keys. Ambiguous matches are reported as `UNKNOWN_NEEDS_HUMAN`, never as
    covered.
*   It computes the plan's preliminary criteria for this one driver: no uncovered critical obligation, ≥ 90%
    noncritical coverage, 100% resolvable refs, and ≥ 90% judgeable verification criteria. Any
    `UNKNOWN_NEEDS_HUMAN` that could change the result gives `NEEDS_HUMAN`.
*   It writes a score report next to the oracle, not into the workspace.

`criteria_result` in a scored copy of the package is set from this report. Inspector verdicts are inputs to the
report and never an override (AT10).

**Corpus decision (D5).** `python -m forge_factory.process_lab.decide <preregistration.json> <score reports…>` is the
only producer of a process maturity. It writes `forge-c/process-decision/1` with value EXPERIMENTAL, NOT_USABLE or
USABLE for SWE.1 under one configuration. It requires:

*   the preregistered corpus (≥ 5 drivers, at least one marked unseen) with every preregistered trial present;
    missing, failed or interrupted trials count as FAILS;
*   a per-driver table that is always shown. No driver's FAILS can be hidden by an aggregate.

USABLE requires every driver `MEETS` (NEEDS_HUMAN blocks until a human disposition is recorded) and the SWE.2 import
of every package to succeed. Otherwise the result is NOT_USABLE, or EXPERIMENTAL when the corpus is incomplete.

### 10. Minimal SWE.2 importer

`python -m forge_factory.process_lab.import_swe2 <package>` validates the schema and hashes. It rejects duplicate IDs,
dangling trace edges, and requirements whose statement hash does not match the artifact. It then emits a deterministic
report that lists each requirement as `CONSUMABLE`, `AMBIGUOUS` (assumption or `NOT_INSPECTED` critical) or `MISSING`
(oracle-scored gaps, if a score report is supplied). It does not build an architecture. It proves that the interface
can be consumed (AT12).

### 10a. Ornith model protocol (plan §5.2)

The lab SWE.1 path calls models only through `lrtx` structured packets, using `response_format` json_schema with a
per-model probed schema mode (`lrtx/structured.py`). It does not use Fabro agent tool calls. Protocol qualification
for this design therefore covers:

*   chat-template rendering, with thinking on/off and the named efforts that render identically in Ornith's template;
*   strict JSON parsing, where a markdown fence or trailing text is INVALID and is never repaired silently;
*   reasoning content stripped and never logged;
*   `finish_reason: length` treated as INVALID, never as a partial answer;
*   timeout as OUTCOME_UNKNOWN, cancellation, and 429 handling;
*   the schema-mode probe result, recorded per digest.

`tools`/`tool_choice` and multi-turn tool-result validation are `NOT_APPLICABLE` to this path. They are required
before any tool-using Ornith role is added, and that work is out of scope. These checks run as recorded-response
fixtures in CI. The runbook's identity probe adds one native structured call per role before an attempt is admitted,
and this stays `NATIVE_NOT_RUN` until an owner window.

### 11. CRC vertical smoke

The existing tiny CRC Delivery-First smoke (two LL functions) keeps running with its frozen known-good inputs after
every increment. It is reported as a smoke result, never as SWE.1 qualification.

### What stays unchanged

These stay unchanged: the strict graphs and policies, `QM_DELIVERY_FIRST_DEMO`, Feature 015 workflows, the existing
Qwen author profiles, the release manager, stored archives, operations intent semantics, admission and the mission
ledger. A non-lab order produces the same graph and the same manifests as at `876d75f`.

## Alternatives Considered

### Alternative A: Keep improving SWE.1 through full SWE.1–6 runs

*   **Pros**: No new mode. Every change is tested in its real downstream context.
*   **Cons**: Each trial takes hours and hundreds of requests. A failure in SWE.5 hides whether SWE.1 caused it. The
    overnight cohort produced 2/3 scoped passes and no measure of requirement quality at all.
*   **Reason for Rejection**: The feedback loop is too slow and confounded. The plan keeps one tiny CRC smoke run for
    vertical integration instead.

### Alternative B: Three linked work orders per driver (one per role)

*   **Pros**: Each order is a plain one-model order with no exception to recovery or resume. Batching falls out of the
    queue order.
*   **Cons**: Three intakes per driver, budgets split across three missions, and a new cross-order link field whose
    check, if wrong, lets an inspector run on a stale candidate.
*   **Reason for Rejection**: Owner decision D1 chose one order with three planned attempts. It keeps one ledger and
    history per driver, at the cost of a lab-specific attempt plan in dispatch.

### Alternative C: Swap the model inside one job

*   **Pros**: One Fabro run per driver.
*   **Cons**: It breaks the "one job = one model" admission invariant (`request_admission.py:49`,
    `role_capability.py:155`). The gateway shares the provider's process namespace, so unloading the model kills the
    run's gateway. A stop mid-swap is the hardest case to make safe.
*   **Reason for Rejection**: It needs the largest change to safety-relevant admission code for the smallest benefit.

### Alternative D: Conductor performs the model swap unattended

*   **Pros**: Overnight corpus runs need no operator at swaps.
*   **Cons**: It is a new autonomous action on the provider, close to the autonomous model router the plan excludes.
    It needs an `operate_service` grant scope, stop-mid-swap and failed-load rollback tests, and handling of
    half-switched stacks with no human present.
*   **Reason for Rejection**: Owner decision D2. Expected swaps are about 2–3 per corpus with role batching, so
    automation saves little now. The runbook's state machine and `model-swap/1` records make later automation
    possible, but that would be a separate design.

### Alternative E: Keep both models resident on the GPU

*   **Pros**: No swap cost.
*   **Cons**: Ornith Q8 (37.8 GB) plus Qwen3.8 27B Q8 do not fit in 48 GB with useful KV caches. It would also break
    the one-admitted-inference rule.
*   **Reason for Rejection**: It is physically infeasible at Q8. A smaller quantization is a different model identity
    and would need its own measurements.

### Alternative F: Score SWE.1 with the inspector model or model votes

*   **Pros**: No oracle authoring effort per driver.
*   **Cons**: Both models can be wrong in the same way. In the Qwen arm, same-family inspection is correlated.
    Calibration already showed 5/9 and 2/2 false rejections of clean baselines.
*   **Reason for Rejection**: The plan forbids a model being its own sole oracle (invariant 6). The frozen oracle plus
    deterministic scorer and the corpus decision are the only judges of `criteria_result` and process maturity.

### Alternative G: Pin the AtomicChat Ornith build named in the plan

*   **Pros**: Matches the plan text.
*   **Cons**: It is not downloaded and not measured. Getting it needs network preparation before isolation, plus new
    hash, template and tool-call checks.
*   **Reason for Rejection**: Owner decision D3 pinned the official ornith-ai build that the speed study measured.

### Alternative H: Universal 64K (or advertised 262K) context for the lab

*   **Pros**: One setting for all tasks.
*   **Cons**: 64K for the whole legacy workflow already failed serialized-request sizing. 262K at Q8 on 48 GB is
    unmeasured for real tasks.
*   **Reason for Rejection**: Context is a per-profile, measured setting for small independent SWE.1 tasks. Mandatory
    data is never truncated silently.

### Alternative I: Run SWE.1 outside Fabro by calling `lrtx.runner` from AFO directly

*   **Pros**: There is no graph change.
*   **Cons**: It loses the Fabro run lifecycle, the run MCP policy, tracing and native-liveness reconciliation.
    `runtime._launcher` also requires a `fabro_run_id`.
*   **Reason for Rejection**: It would bypass production agent policy (CLAUDE.md guardrail). A builder option that
    stops the graph after SWE.1 keeps the existing engine.

### Alternative J: Content-hash requirement IDs

*   **Pros**: Stable without a ledger file.
*   **Cons**: Any text edit during rework changes the ID. The format breaks the `SWR-\d{3}` pattern used by `swtrace`,
    `swe2` and `review_semantic`.
*   **Reason for Rejection**: The obligation-keyed ledger keeps both stability and the existing format.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security & privacy:** Oracle files, vendor manuals and raw prompts or responses never enter source control or a
    public evidence directory. Reasoning text is discarded, and only counts are kept (as in the speed study).
    Handoff packages contain hashes and IDs, not manual text excerpts.
*   **Performance:** These are measured, not targets. Per swap: drain, unload, load and probe times. Per attempt:
    wall time, requests, tool calls, reported tokens vs reservations, and VRAM peak (from the existing native
    measurement records).
*   **Rollout & rollback:** Everything is opt-in through the `process_lab` work-order block. Removing the block, or
    using the existing profiles, gives the `876d75f` behaviour. Swap rollback means restarting the previous profile
    from STOPPED. No database migration: lab state uses existing tables plus files in the workspace and the operator
    directory.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Paths are relative to the repository root. `ff/` = `factory/python/forge_factory/`, `tests/` =
`factory/python/tests/`. Increments are ordered: each ends with its tests passing and the regression battery from the
Verification Plan, before the next starts.

### Increment order

1.  Identity hash (G3) and `hf.co` manifest resolution: independent and small, and they protect everything after.
2.  Contracts (`process-lab`, `process-handoff`, `swe1-oracle`, `process-decision`, `model-swap` schemas).
3.  Lab intake and the SWE.1-only graph (`stop_after`), AUTHOR attempt only.
4.  ID ledger and target-neutral `primary_manual`.
5.  Attempt plan dispatch (INSPECT, REWORK), lab terminal verdict, and inspector per-requirement outcome.
6.  Scheduler `RESIDENT_PROFILE_MISMATCH`, lab profiles, swap runbook and `model-swap/1` records.
7.  Scorer, corpus decision and SWE.2 importer.
8.  CRC lab example and the end-to-end synthetic-provider test. Native runs remain NOT_RUN until an owner window.

### Target Files to Create/Modify

#### 1. `ff/lrtx/structured.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: The packet `input_hash` (around lines 172 and 237) adds the job's `model_digest`,
    `profile_sha256`, reasoning mode/effort and the probed schema mode to the hashed tuple. This closes the
    name-only cache key. No other behaviour changes.

#### 2. `ff/lrtx/stack.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `llama_server_spec` resolves manifests for models named `hf.co/<org>/<repo>:<tag>` under
    `manifests/hf.co/<org>/<repo>/<tag>`. Names without a slash keep the `registry.ollama.ai/library` path. It keeps
    the digest-equals-manifest-sha and blob-size checks, and adds an optional `runtime.llama_server.model_blob_sha256`
    that must equal the layer digest when present. It reads the context length from `runtime.llama_server.context`
    when present; otherwise from `runtime.ollama.OLLAMA_CONTEXT_LENGTH`, as today.

#### 3. `specs/014-durable-local-autonomy/contracts/process-lab.schema.json` (Create)

*   **Type / Scope**: JSON Schema.
*   **Proposed Changes**: Defines the work-order block `forge-c/process-lab/1`:
    *   `purpose: QM`, `process_under_test: SWE.1` (enum, only SWE.1 for now), `experiment_id`.
    *   `attempt_plan[]`: 2–5 items in the fixed role order AUTHOR, INSPECT, REWORK, INSPECT, REWORK, each with
        `seq`, `role`, `profile`, `model_profile`.
    *   `target_profile.primary_manual`.
    *   `max_semantic_rework` (integer 0–2, equal to the number of REWORK entries), `quality_policy: advisory_with_blocking_integrity`,
        `strict_release_unchanged: true`.
    *   `additionalProperties: false`. There is no oracle field.

#### 4. `specs/014-durable-local-autonomy/contracts/process-handoff.schema.json` (Create)

*   **Type / Scope**: JSON Schema.
*   **Proposed Changes**: Defines `forge-c/process-handoff/1` with the fields in Technical Plan §8. `criteria_result`
    is an enum; `strict_release_status` is const `NOT_APPLICABLE_PROCESS_LAB`; `requirements[].id` matches
    `^SWR-[0-9]{3}$`; `inspector_outcome` is an enum FINDINGS | NO_FINDING | NOT_INSPECTED | NOT_RUN.

#### 5. `specs/014-durable-local-autonomy/contracts/swe1-oracle.schema.json` (Create)

*   **Type / Scope**: JSON Schema.
*   **Proposed Changes**: Defines `forge-c/swe1-oracle/1`:
    *   `driver`, `source_hashes[]`, `reviewer`, `review_utc`.
    *   `obligations[]` with `id`, `critical`, `kind` (behaviour | caller_contract | interface | state | error),
        `accepted_source_refs[]`, `match` (`register`/`field`/`op` and/or `keywords[]`), and `note`.

#### 5a. `specs/014-durable-local-autonomy/contracts/process-decision.schema.json` (Create)

*   **Type / Scope**: JSON Schema.
*   **Proposed Changes**: Defines `forge-c/process-decision/1`:
    *   `process`, `configuration`, `preregistration_sha256`;
    *   `drivers[]` (driver, unseen flag, trial ids, criteria_result per trial, import result);
    *   `maturity` (EXPERIMENTAL | NOT_USABLE | USABLE), and `reasons[]`.

#### 6. `specs/014-durable-local-autonomy/contracts/model-swap.schema.json` (Create)

*   **Type / Scope**: JSON Schema.
*   **Proposed Changes**: Defines `forge-c/model-swap/1` with: `swap_id`; from/to `profile_sha256` and
    `model_digest`; `transitions[]` (`state`, `utc`, `evidence_ref`); `outcome` (RUNNING | STOPPED_FAILED_LOAD |
    STOPPED_BY_OPERATOR | DRAIN_TIMEOUT); and `operator`.

#### 7. `specs/014-durable-local-autonomy/contracts/examples/` (Modify: add files)

*   **Type / Scope**: Contract fixtures.
*   **Proposed Changes**: Adds one valid and two invalid examples per new schema (for example an oracle path in a
    process-lab block, a duplicate SWR id, or `criteria_result: MEETS` in a sealed, unscored package). These
    are consumed by `validate_contracts.py`.

#### 8. `specs/014-durable-local-autonomy/contracts/validate_contracts.py` and `README.md` (Modify)

*   **Type / Scope**: Validator + doc.
*   **Proposed Changes**: Registers the five schemas and their examples, and lists them in the README.

#### 9. `ff/process_lab/__init__.py` (Create)

*   **Type / Scope**: Python package.
*   **Proposed Changes**:
    *   `MODE = "QM_PROCESS_LAB"`.
    *   `contract(spec) -> dict`: validates the block against the schema, refuses any field naming an oracle, and
        refuses `process_under_test != "SWE.1"`.
    *   `selected(manifest) -> bool`.
    *   `plan_entry(manifest, seq) -> dict`.
    *   `workflow(manifest, role) -> graph`: calls the builder with `stop_after="SWE.1"`, selects the role subgraph,
        and adds the `lab_seal` / `lab_inspect_record` command nodes.
    *   `verdict(workspace) -> {verdict, reason}`: `BLOCKED/PROCESS_LAB_SEALED` when the final planned seal exists
        and its hashes verify; otherwise `BLOCKED/<specific reason>`. It never returns `READY_FOR_OFFLINE_REVIEW`.

#### 10. `ff/process_lab/seal.py` (Create)

*   **Type / Scope**: Python module + CLI used as Fabro command nodes.
*   **Proposed Changes**:
    *   `seal(workspace, seq, role)`: hashes the SWE.1 artifacts, writes the immutable
        `.forge-run/lab/seal-<seq>.json` (artifact hashes, job model digest, profile sha, runtime id, prior seal
        sha), and refuses to overwrite an existing seal.
    *   `inspect_record(workspace)`: converts the stepwise inspector record into per-requirement outcomes and writes
        `.forge-run/lab/inspection-<seq>.json`.
    *   `handoff(workspace)`: builds `process-lab/SWE.1/handoff.json` from the seals, with
        `criteria_result: UNSCORED`.

#### 11. `ff/process_lab/ledger.py` (Create)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   `key(requirement) -> str`: source ref + register/field/op, or a normalized statement hash.
    *   `load(workspace)`, `assign(ledger, keys) -> {key: "SWR-nnn"}`: reuse, append, never reuse retired numbers.
    *   `save(workspace, ledger)`.
    *   Errors if more than 999 ids would be needed (`SWR_ID_SPACE_EXHAUSTED`).

#### 12. `ff/process_lab/score.py` (Create)

*   **Type / Scope**: CLI `python -m forge_factory.process_lab.score <handoff.json> <oracle.json> --inputs <dir> --out <dir>`.
*   **Proposed Changes**: Implements Technical Plan §9. It refuses if `--out` is inside the order workspace. The
    output is `score-<order>.json` with per-obligation status (COVERED | UNCOVERED | UNKNOWN_NEEDS_HUMAN), per-ref
    resolution, the four criteria, and `criteria_result`. It writes a scored copy of the handoff next to the report.
    No model calls and no network.

#### 13. `ff/process_lab/import_swe2.py` (Create)

*   **Type / Scope**: CLI `python -m forge_factory.process_lab.import_swe2 <handoff.json> [--score <score.json>]`.
*   **Proposed Changes**: Implements Technical Plan §10. Its output is deterministic: sorted keys and no timestamps
    in the body. It exits non-zero on rejection, with a stable reason code (`HANDOFF_DUPLICATE_ID`,
    `HANDOFF_DANGLING_TRACE`, `HANDOFF_HASH_MISMATCH`, `HANDOFF_SCHEMA_INVALID`).

#### 13a. `ff/process_lab/decide.py` (Create)

*   **Type / Scope**: CLI `python -m forge_factory.process_lab.decide <preregistration.json> <score…> --out <dir>`.
*   **Proposed Changes**: Implements the corpus decision (Technical Plan §9, D5). It checks that the score reports
    match the preregistered trial list (corpus, configuration, oracle hashes) and treats any missing trial as FAILS.
    It writes `forge-c/process-decision/1` with a per-driver table and the maturity value. No model calls.

#### 14. `ff/process_lab/swap.py` (Create)

*   **Type / Scope**: CLI helpers called by the runbook script.
*   **Proposed Changes**:
    *   `check-quiescent`: reads the mission ledger. It succeeds only when there is no inference owner, a
        QUIESCENCE record exists, and there is no SENT/UNKNOWN request (all read-only, using existing ledger APIs).
    *   `record <state>`: appends a transition to the `model-swap/1` file in the operator directory.
    *   `probe`: one admitted identity probe through the gateway, checking `model_identity` against the profile.
    *   It never sets intent or starts/stops the stack itself; the script calls the existing commands for that.

#### 15. `ff/workorder.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   Near line 293, copies `spec["process_lab"]` into the manifest, like `delivery_first`.
    *   Near line 406, calls `process_lab.contract`.
    *   Refuses a spec that has both `delivery_first` and `process_lab` (`PROCESS_LAB_MODE_CONFLICT`).

#### 16. `ff/workflow/builder.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   Adds the keyword `stop_after: str | None = None` to `build` and `_build`. When it is `"SWE.1"`, emits only
        SWE.1 nodes and routes the SWE.1 inspect-gate exit to a `lab_end` node. There are no `upstream_*`, finalize
        or release nodes.
    *   Near line 212, when `manifest.process_lab` is present, delegates to `process_lab.workflow(manifest, role)`.
    *   With `stop_after=None` the output is unchanged; a golden test pins it.

#### 17. `ff/afo/checkpoints.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: Adds `planned_attempt(store, order_id, *, seq, plan_entry, source_wo) -> str`. From a RUNNING
    order whose last attempt is terminal and SUCCEEDED, it inserts attempt `seq` with `record.plan_entry` and a
    FABRO_LAUNCH intent that resumes from `source_wo`. It is idempotent on `(order_id, seq)`. It refuses if
    `seq != last.seq + 1`, if the order is not a lab order, or if operations intent is not RUNNING.

#### 18. `ff/afo/dispatch.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   In `reconcile_running` (lines 313–356), for lab orders, before `recover`:
        *   If the attempt SUCCEEDED and a next plan entry exists, and is required (REWORK only when
            `inspection-<seq>.json` has an actionable finding), call `planned_attempt`.
        *   Otherwise transition to VALIDATING.
        *   A FAILED, CANCELLED or STOPPED attempt goes to VALIDATING with no recovery.
    *   In `validate` (line 452+), lab orders use `process_lab.verdict` instead of `package_verdict`.

#### 19. `ff/afo/runtime.py` and `ff/afo/product_job.py` (Modify)

*   **Type / Scope**: Python modules.
*   **Proposed Changes**: When the attempt record has `plan_entry`, `_launcher` (lines 69–89) and
    `product_job.prepare` take `profile` and `model_profile` from it instead of the order manifest. This happens
    before the existing allowed-model checks, which stay unchanged. The job remains single-model.

#### 20. `ff/afo/scheduler.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   `preflight` adds the issue `RESIDENT_PROFILE_MISMATCH` when the next attempt's profile sha differs from the
        `profile_sha256` in the running stack's `services.json`. It is a deferral, with the same handling as
        `NATIVE_INFERENCE_CAPACITY_HELD` (lines 118–121, 232–237).
    *   If `services.json` is absent, the issue is `RESIDENT_PROFILE_UNKNOWN` and the order is deferred, never
        launched.

#### 21. `ff/lrtx/swe1.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   In lab mode, `assemble` (lines 491–595) assigns IDs through `process_lab.ledger` instead of positional
        numbering.
    *   The RM0486 literals at lines 228, 501 and 738 come from `target_profile.primary_manual`, with default
        `RM0486`.

#### 22. `ff/lrtx/review_semantic.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: In lab mode (`manifest.process_lab`):
    *   `visit` records a per-requirement outcome. An INVALID task, `VISIT_CALL_BUDGET_EXHAUSTED`, a time box
        `Continue`, or a never-reached requirement maps to `NOT_INSPECTED`.
    *   The reply finishes the run instead of returning CONTINUE/FAILED for rework.
    *   The strict and Delivery-First paths are unchanged.

#### 23. `ff/inspection/ears.py`, `ff/provided_requirements.py`, `ff/assurance/swe12.py` (Modify)

*   **Type / Scope**: Python modules.
*   **Proposed Changes**:
    *   `ears.check_document` uses `^SWR-[0-9]{3}$` when called for a lab package.
    *   `provided_requirements.py:70` and `swe12.py:34` read `primary_manual` from the target profile, defaulting
        to `RM0486`.

#### 24. `config/factory/profiles/local-rtx-v2-omniverse2-lab-ornith-q8.yaml` (Create)

*   **Type / Scope**: Local profile.
*   **Proposed Changes**:
    *   Pins `hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0`, with digest = the sha256 of its Ollama manifest
        file and `model_blob_sha256: de46c4ba…58c3`.
    *   Uses `llama_server` with `slots: 1`, no MTP, and an explicit `reasoning`/budget value (left open by Q5 until
        preregistration).
    *   Sets `context` explicitly (32768 or 65536, decided at preregistration).
*   **Prerequisite**: The manifest sha must be read on Omniverse2 read-only before this file can be completed. It is
    never guessed.

#### 25. `config/factory/profiles/local-rtx-v2-omniverse2-lab-qwen38-q8.yaml` and `...-lab-qwen38-author-q8.yaml` (Create)

*   **Type / Scope**: Local profiles.
*   **Proposed Changes**:
    *   Both pin `qwen3.8:27b-q8_0`, digest `8f5fb6b7…6039`.
    *   The inspector profile copies `inspector_stepwise` and inspector sampling from
        `...-q38-aspice-stepwise-medium.yaml`.
    *   The author profile copies the author settings from `...-q38-delivery-first.yaml`.
    *   The source profile files are not modified.

#### 26. `examples/0020-process-lab-crc/` (Create)

*   **Type / Scope**: Example work order.
*   **Proposed Changes**:
    *   Contains `workorder.json` with a `process_lab` block (5-entry plan) for the two-function CRC IDR scope, an
        inputs manifest reusing the frozen `0014g` source entries by hash, and a README.
    *   No oracle file. The CRC oracle lives in the operator directory and is produced in PF-SWE1-006.

#### 27. `scripts/process-lab-swap.sh` (Create)

*   **Type / Scope**: Operator script.
*   **Proposed Changes**: Implements the swap state machine (Technical Plan §3) by calling only existing commands:
    *   operations intent set;
    *   `process_lab.swap check-quiescent`;
    *   the existing stack stop/start;
    *   `process_lab.swap probe` and `record`.

    It stops at the first failed check and leaves the stack STOPPED. It has no `--force`.

#### 28. `docs/runbooks/process-lab-omniverse2.md` (Create)

*   **Type / Scope**: Runbook.
*   **Proposed Changes**: Covers:
    *   prerequisites (owner window, signed per-experiment AFO policy listing the lab profiles, STOPPED intent, free
        storage);
    *   staging an exact revision;
    *   queueing orders;
    *   when to swap;
    *   scoring and importing;
    *   rollback;
    *   what to record as NOT_RUN.

    The repository `config/factory/afo-policy.yaml` is **not** edited. Lab profiles are allowed only by the signed
    per-experiment operator policy.

#### 29. `docs/designs/forge-c-process-first-ornith-qwen.md` (Create)

*   **Type / Scope**: This design, finalized.

#### 30. Tests in `tests/` (Create)

*   `test_process_lab_identity_hash.py`: a digest, profile, reasoning or schema-mode change invalidates the
    packet hash and checkpoint reuse; the same identity reuses (AT03).
*   `test_lrtx_stack_hf_manifest.py`: the `hf.co` manifest resolves; wrong manifest sha, wrong blob sha, wrong
    size and missing blob are refused; library models are unchanged.
*   `test_process_lab_contract.py`: valid block; the oracle field, `process_under_test: SWE.2`, a combined
    `delivery_first` block and a missing plan are refused.
*   `test_process_lab_graph.py`: the lab graph per role has no SWE.2–6, finalize or release node. The golden test
    shows the non-lab graph is byte-identical to `876d75f` for the strict and Delivery-First examples (AT02).
*   `test_process_lab_attempt_plan.py`:
    *   seq 2 is created only after a seq 1 success;
    *   REWORK only with actionable findings;
    *   a FAILED or STOPPED attempt goes to a terminal state with no recovery planner call;
    *   `planned_attempt` is idempotent and refuses when the intent is not RUNNING;
    *   each job stays single-model (AT11, AT17 for the terminal disposition).
*   `test_process_lab_resident_profile.py`: mismatch defers; unknown resident profile defers; a matching profile
    admits; a mixed queue gives AUTHOR-batch-first order (AT04, AT08).
*   `test_process_lab_swap.py`: `check-quiescent` fails with a held lease, a SENT or UNKNOWN request, or a missing
    QUIESCENCE; a failed probe leaves the stack STOPPED; STOPPED intent mid-sequence stops further transitions
    (AT04, AT05). Uses fixture ledgers only.
*   `test_process_lab_ornith_protocol.py`: recorded-response fixtures (no model). Template rendering on/off;
    fenced or trailing-text JSON INVALID; reasoning stripped from records; `finish_reason: length` INVALID;
    timeout OUTCOME_UNKNOWN; schema-mode probe keyed by digest. Fixtures are built from the speed study's public
    final answers only, with no reasoning text.
*   `test_process_lab_ledger.py`: IDs are stable across rework, retired IDs are never reused, and the ID space is
    exhausted at 999.
*   `test_process_lab_inspector_outcome.py`: time box, invalid answer and budget exhaustion map to `NOT_INSPECTED`
    and never to `NO_FINDING`; the inspector cannot write seals or sources (AT09).
*   `test_process_lab_handoff.py`: the seal chain is immutable; a modified artifact after a seal is detected; the
    handoff validates against the schema.
*   `test_process_lab_score.py`: a critical uncovered obligation gives FAILS even with every inspector outcome
    `NO_FINDING` (AT10); a fabricated ref is detected; an ambiguous match gives UNKNOWN_NEEDS_HUMAN; `--out` inside
    the workspace is refused.
*   `test_process_lab_decide.py`: four MEETS drivers give EXPERIMENTAL (corpus too small); five with no unseen give
    EXPERIMENTAL; a missing trial counts as FAILS; one FAILS driver gives NOT_USABLE and is shown in the table;
    NEEDS_HUMAN blocks USABLE.
*   `test_process_lab_import_swe2.py`: valid import; duplicate, dangling and hash-mismatch inputs are rejected; the
    output is byte-identical across runs (AT12).
*   `test_process_lab_oracle_isolation.py`: no manifest, prompt packet or input list of a lab order contains an
    oracle path or hash; author and inspector file access outside the workspace is refused (AT16).
*   `test_process_lab_e2e_fixture.py`: a full five-attempt order (and a two-attempt early-terminal order) with a synthetic scripted provider (no model), then
    score and import, asserting `NATIVE_NOT_RUN` labelling (AT15).

#### 31. `evidence/014-durable-local-autonomy/egm-pf-001/` (Modify: add files)

*   **Type / Scope**: Evidence.
*   **Proposed Changes**: Adds the EGM review report(s) and the resolution record next to `PREFLIGHT.md` and
    `SOURCE-INVENTORY.md`. Reviewer output is redacted of secrets and manual text.

### Verification Plan

*   **Environment**: loop10, `source scripts/forge-env.sh`, `FORGE_DATA_ROOT=$B`, the repo venv python, in a fresh
    worktree per regression run.
*   **Unit tests**: `python -m pytest factory/python/tests/test_process_lab_*.py factory/python/tests/test_lrtx_stack_hf_manifest.py -q`
    passes after each increment. Each new negative test is shown failing before its fix.
*   **Regression**:
    *   the inherited per-file runner (`operations/feature014/run_full_inherited.py <worktree> <out>` on the
        loop10 data volume, outside the repo) with 0 new failures compared to the `876d75f` baseline;
    *   plus `test_delivery_first*.py`, the F015 workflow tests and the strict graph tests, all unchanged (AT02).
*   **Static**:
    *   `ruff check` on the changed files;
    *   `python3 tests/spec/validate_design.py`;
    *   `python3 specs/014-durable-local-autonomy/contracts/validate_contracts.py`;
    *   the Feature 014 `validate_spec` (`COUNT=58` unchanged; no DA row changes).
*   **CRC smoke**: the existing tiny CRC Delivery-First fixture tests pass. A native smoke is NOT_RUN until an owner
    window opens.
*   **Native**: NOT_RUN in this design's scope. The first native step is the runbook in an owner-authorized window:
    one CRC lab order per arm, with every result kept.

*Drafted with EGM*
