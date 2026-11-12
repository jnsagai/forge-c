# Forge-C Process-First Lab: SWE.1 with an Ornith Author and a Qwen Inspector

*   **Author:** jnsagai (owner), drafted by Claude (Elephant)
*   **Status:** Revision 2, FROZEN by owner decision 2026-10-31 ("accept and proceed" at the review cap). The
    targeted re-review left 7 Blockers open (`evidence/014-durable-local-autonomy/egm-pf-001/targeted_rereview_report.md`).
    Only increments untouched by those Blockers may be implemented, starting with G3. Lab intake, activation,
    admission, scoring and leakage controls stay blocked until a revision 3 is reviewed.
*   **Date:** 2026-10-31
*   **Source of truth:** Feature 014 Spec Kit (`specs/014-durable-local-autonomy/`).
*   **Implements:** the plan `specs/014-durable-local-autonomy/PROCESS-FIRST-ORNITH-QWEN-EGM-CLAUDE.md` (`876d75f`).
*   **Source facts:** `evidence/014-durable-local-autonomy/egm-pf-001/SOURCE-INVENTORY.md`.
*   **Review trail:** `evidence/014-durable-local-autonomy/egm-pf-001/` (revision 1 as reviewed, stage reports 5–9,
    `goldfish_review_report.md`).

--------------------------------------------------------------------------------

## Overview

Forge-C turns owner scope plus frozen sources (reference manual, device headers, existing code) into embedded-C
drivers and ASPICE-inspired work products. It uses local models on one 48 GB GPU (Omniverse2). At `876d75f`, every
experiment runs the whole SWE.1–SWE.6 graph.

This design adds an opt-in **process lab** that runs **only SWE.1** (software requirements analysis) for LL drivers:
*   Each lab work order has exactly **one role** (AUTHOR, INSPECT or REWORK) and one model.
*   A driver goes through up to five such orders. Each later order takes the earlier order's sealed SWE.1 handoff
    package as a hash-bound input.
*   **Ornith-1.5-35B-A3B Q8_0** authors and reworks. **Qwen3.8-27B Q8** inspects read-only (arm A). Qwen does every
    role in the reference arm (arm B).
*   The operator runs all orders of one role as a batch in one stack session. Between batches, the operator switches
    the factory's profile with a tested activation tool built from an existing activation script.
*   Each handoff is pre-scored by deterministic checks against a frozen oracle that the author cannot see.
    Obligations that no deterministic predicate decides need a recorded human disposition.
*   A minimal SWE.2 importer proves the package can be consumed.
*   The existing two-function CRC Delivery-First smoke test keeps passing.

There is no new scheduler, release authority, model router or EGM runtime.

### Glossary

*   **AFO:** autonomous factory operations. The durable work-order queue, scheduler, dispatch, mission ledger and
    Conductor service (`ff/afo/`).
*   **Fabro:** the workflow engine that runs a work order's graph of author, gate and inspector nodes.
*   **Operations intent / epoch:** the operator-controlled mode (RUNNING, PAUSED, DRAINING, STOPPED). Its counter
    increases on every change (`ff/afo/operations.py`).
*   **Inference owner:** the single job allowed to send model requests (`afo_resource_ownership` row `inference`).
*   **QUIESCENCE evidence:** the ledger record proving that a job has no SENT or UNKNOWN request left
    (`afo_execution_evidence`, kind QUIESCENCE).
*   **Owner window:** an owner-authorized, time-bounded execution grant for live runs on Omniverse2.
*   **loop10:** the development host. **MTP:** multi-token prediction drafting. **F015:** Feature 015 (ST driver
    benchmark). **DA tasks:** the Feature 014 task ledger (30/58).
*   **`ff/`** = `factory/python/forge_factory/`. **`$B`** = `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c`.

## The Problem

1.  **Full-pipeline runs are slow, and they blur the cause of a failure.** The overnight Qwen cohort had three
    trials ([overnight report](https://github.com/jnsagai/forge-c/blob/45190ebca727d28225e9ee61e0908fd0ffdae166/docs/reports/ASTRA-OVERNIGHT-REVIEW-20261030-31.md),
    evidence revision `dce7ad27`). Results:
    *   2 of 3 reached a scoped functional pass on a two-function CRC slice.
    *   The original mission used 1,470 requests and 2,583 tool calls across 7 attempts.
    *   Strict packages still carried 16 open gaps (trial 06) and 35 open gaps (trial 07).

    A failure in SWE.5 does not show whether SWE.1 requirements were the root cause. Improving one process by
    rerunning six processes is a slow feedback loop.
2.  **SWE.1 output is not yet a usable interface.**
    *   Requirement IDs are renumbered on every assembly (`ff/lrtx/swe1.py:508`).
    *   SWE.2 reads SWE.1 by regex over markdown (`ff/inspection/swtrace.py:101`, `ff/lrtx/swe2.py:78`).
    *   Two ID patterns disagree (`ff/inspection/ears.py` against `swtrace`/`swe2`).
3.  **SWE.1 quality is not measured against anything independent.**
    *   Gates check structure, and an inspector from the same model family checks semantics.
    *   Nothing checks whether the critical obligations of a driver were captured.
    *   The Delivery-First CRC example puts reviewed reference requirements and oracle C files into the author's
        inputs (`examples/0014g-st-crc-idr-qwen-delivery/workorder.json`).
4.  **The factory cannot use different models for different roles.**
    *   One job is pinned to one model (`ff/afo/request_admission.py:49`).
    *   The managed profile is pinned in the systemd units (`ff/afo/services.py:100-110`).
    *   Cache keys use the model *name*, not its identity (`ff/lrtx/structured.py:172,237`). A model change under the
        same alias reuses stale cached answers.
5.  **The Ornith choice has no evidence behind it yet.** The only data is a 36-trial standalone speed study
    ([evidence](../../evidence/014-durable-local-autonomy/ornith-reasoning-speed-20261031/README.md)). It measured
    about 150 decode tokens/s and at best 4/9 full-contract passes. That justifies an experiment, not a default.

**Proposed solution:** an opt-in `QM_PROCESS_LAB` order type with three parts:
*   single-role, single-model SWE.1 orders, linked by sealed handoffs;
*   role batches switched by an operator activation tool;
*   deterministic pre-scoring against a frozen oracle, completed by human dispositions.

## Goals

*   **G1 — SWE.1-only, single-role orders.** A lab order runs exactly one role's SWE.1 subgraph and ends in a
    listed terminal reason (§2). No SWE.2–6, finalize or release node exists in its graph.
*   **G2 — Fenced role batches on one GPU.**
    *   The factory serves one lab profile at a time.
    *   The operator switches profiles only at an empty queue with proven quiescence, using a tested activation tool
        that uses compare-and-set on the operations intent.
    *   A lab order whose profile is not the resident one is refused before admission.
    *   Every switch writes a timed activation record.
*   **G3 — Identity-correct caching, everywhere.** The structured packet hash covers the full role-capability
    identity: role, model digest, precision, reasoning, schema mode, adapter revision, context tokens and sampling.
    It also covers the profile `config_sha256`. A change to any of these misses the cache on every structured path.
*   **G4 — Versioned handoff.**
    *   SWE.1 emits `forge-c/process-handoff/1`, which carries stable requirement IDs, source refs, trace edges,
        baseline identity and per-requirement inspector outcomes.
    *   The next order materializes it only after a hash check.
    *   A minimal SWE.2 importer accepts valid packages and rejects duplicate IDs, dangling trace edges and hash
        mismatches.
*   **G5 — Independent, honest scoring.**
    *   A deterministic scorer checks hashes, ref resolution, ID integrity and register-effect matches against a
        frozen per-driver oracle.
    *   An obligation counts as COVERED only through a satisfied deterministic oracle predicate or a recorded,
        owner-signed review disposition.
    *   Inspector verdicts never decide coverage.
    *   An inspector timeout is `NOT_INSPECTED`, never PASS.
*   **G6** was removed by D8. The A/B report moves to PF-BENCH-011.
*   **G7 — No regression.** Strict graphs, `QM_DELIVERY_FIRST_DEMO`, Feature 015 workflows and the CRC smoke keep
    passing. Two changes apply outside the lab:
    *   G3 recomputes non-lab structured checkpoints once.
    *   The `qm.validate_profile` exception (D7) applies only to lab orders.

## Non-Goals

*   **NG1** — No lab for SWE.2–SWE.6. SWE.2 gets an importer only.
*   **NG2** — No model promotion. Ornith is used only in the opt-in lab, and the existing Qwen profiles are not
    changed.
*   **NG3** — No native GPU run, deployment or grant from this design. CI reports `NATIVE_NOT_RUN`. Live runs need a
    new owner window.
*   **NG4** — No new scheduler, database, release authority, autonomous model router or EGM runtime. AFO never loads
    or unloads a model by itself.
*   **NG5** — No claim of Automotive SPICE compliance. Lab outputs are QM / ASPICE-inspired and never
    release-eligible.
*   **NG6** — No change to strict release policy, stored archives, safety policies or historical evidence (the 2/3
    cohort, the expired grant and the mission counters).
*   **NG7** — No both-models-resident operation and no parallel inference.
*   **NG8** — No Feature 014 DA ticks from this work. The CLAUDE.md rule applies: tick a box only with run evidence.
*   **NG9** — No corpus maturity decision (USABLE), no A/B reporter and no target-neutral manual handling in this
    design (D8). Those belong to PF-QUAL-013, PF-BENCH-011 and Q3.
*   **NG10** — No non-LL layer. `swe1.visit` refuses other layers.

## Resolved Decisions (owner, 2026-10-31)

*   **D1′ — One order per (driver, role).** Each driver gets up to five single-role orders. Each has one profile and
    one model, and they are linked by hash-bound handoff inputs. D1′ replaces D1 (one order with several attempts),
    which the review showed does not fit the queue, resume, epoch and admission code (Alternative A).
*   **D2 — The operator swaps models.** AFO never loads or unloads a model by itself.
*   **D3 — Ornith build.** The official `ornith-ai/Ornith-1.5-35B-A3B-GGUF` Q8_0. GGUF sha256
    `de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3`, 37,802,149,280 bytes. It is already in the
    Omniverse2 Ollama blob store, and it replaces the plan's AtomicChat reference.
*   **D4 — At most two reworks.** A driver's order sequence is a prefix of AUTHOR, INSPECT, REWORK, INSPECT, REWORK,
    and the second REWORK's output is not inspected. D4 supersedes the plan's "exactly one bounded correction"
    (plan §5.2, AT11).
*   **D6 — Both arms in the first delivery.** Arm A is Ornith author + Qwen inspector; arm B is Qwen for every role.
*   **D7 — Lab purpose is QM**, with a lab-scoped exception in `qm.validate_profile` that allows
    `semantic_inspect_phases: [SWE.1]`.
*   **D8 — Cut the corpus-decision layer.** Keep only a frozen operator-side experiment record that binds the oracle
    and profile hashes.
*   **D9 — G3 is a global fix**, and G7 is amended to match.

## Open Questions

Q1 and Q2 were resolved as D3 and §11. Q5 from revision 1 is now Q5 below.

*   **Q3 — Unseen corpus case.** The F015 GPIO+CRC test set and the 9-baseline calibration subset are already used.
    Q3 does not block this design (NG9).
*   **Q4 — Oracle reviewer and disposition practice.** Who reviews each oracle, and who signs the per-obligation
    review dispositions? This **blocks the first scored result**, not implementation.
*   **Q5 — Ornith thinking setting.** `enable_thinking` and `thinking_budget_tokens` are fixed in the experiment
    record before the first order. The speed study measured: default thinking 4/9 (one trial truncated at 8,192
    tokens); a 2,048-token budget gave 2/9 full-contract and 3/9 semantic.

## Critical User Journeys (CUJs)

### CUJ 1: Operator runs one role batch

*   **Given**:
    *   The experiment record is frozen.
    *   The stack is RUNNING with `lab-ornith-q8` resident.
    *   The per-experiment operator policy is signed and lists the lab profiles and `product_role_trial` bindings.
    *   An owner window is open.
*   **When**: The operator submits the AUTHOR orders for all corpus drivers.
*   **Then**:
    *   AFO runs them one at a time. Each ends with a sealed handoff (`PROCESS_LAB_HANDOFF_SEALED`) or a listed
        failure reason.
    *   When the queue is empty, `process_lab.next --role INSPECT` prepares the INSPECT orders from the sealed
        handoffs.
    *   The operator runs `process_lab.activate --to lab-qwen38-q8`, then submits those orders.

### CUJ 2: Stop during activation

*   **Given**: `process_lab.activate` is between "units stopped" and "Conductor started".
*   **When**: The owner sets intent STOPPED, or a grant is revoked.
*   **Then**:
    *   The tool's next intent re-read sees the change, stops the stack and writes outcome `STOPPED_BY_OPERATOR`.
    *   The epoch check makes the compare-and-set resume fail, so the tool cannot overwrite the STOP.
    *   No order is affected, because the queue was empty by precondition.

### CUJ 3: Inspector time box or invalid answer

*   **Given**: An INSPECT order is running.
*   **When**: A checklist item's time box or repair budget runs out, or the model answers invalidly.
*   **Then**:
    *   Every requirement covered by that item gets `NOT_INSPECTED`, never `NO_FINDING`, and an inspection record is
        still written.
    *   No REWORK is prepared from `NOT_INSPECTED` outcomes alone.

### CUJ 4: SWE.2 imports a handoff

*   **Given**: A sealed handoff and its artifact directory.
*   **When**: `process_lab.import_swe2` reads them.
*   **Then**:
    *   It lists each requirement as `CONSUMABLE`, `AMBIGUOUS` or `MISSING`.
    *   It exits non-zero with a stable reason on a duplicate ID, a dangling trace edge or a hash mismatch.
    *   The same input always produces byte-identical output.

### CUJ 5: Model identity changes between trials

*   **Given**: A cached inspector verdict exists.
*   **When**: Any field of the identity tuple, or the profile `config_sha256`, changes while the model alias stays
    the same.
*   **Then**: The cache misses, and the result is recomputed and recorded under the new identity.

### CUJ 6: Wrong or stale handoff input

*   **Given**: An INSPECT order whose declared handoff input sha256 does not match the file, or whose handoff names
    a different experiment, driver or primary-source set.
*   **When**: Intake or the run's `materialize` node checks it.
*   **Then**: The order is refused with `PROCESS_LAB_HANDOFF_HASH_MISMATCH` or `PROCESS_LAB_HANDOFF_SCOPE_MISMATCH`
    before any model call.

## Technical Plan (Architecture)

### Components and data flow

```text
 OPERATOR (runbook)                         AFO + Fabro (existing engine)
 ------------------                         -----------------------------
 experiment record (frozen: oracle shas,
   profile shas, thresholds, Q5 values)
 resident profile = lab-ornith-q8
 submit AUTHOR orders (drv1..drvN) ───────▶ order: role=AUTHOR, one model
                                             graph: swe1_author → author_gate → lab_handoff
                                             terminal: BLOCKED/PROCESS_LAB_HANDOFF_SEALED + handoff.json
 queue empty ◀───────────────────────────── (scheduler refuses non-resident lab profiles)
 process_lab.next --role INSPECT
 process_lab.activate --to lab-qwen38-q8
 submit INSPECT orders ───────────────────▶ order: role=INSPECT, input = prior handoff (sha256)
                                             graph: materialize → swe1_inspector → lab_inspect_record → lab_handoff
 next --role REWORK (only drivers with FINDINGS); activate --to lab-ornith-q8; submit
 ... at most AUTHOR, INSPECT, REWORK, INSPECT, REWORK per driver ...
 process_lab.score <handoff> <artifacts> <oracle> (refuses oracle not in experiment record)
 review dispositions (owner-signed) for UNKNOWN_NEEDS_HUMAN obligations
 process_lab.import_swe2 <handoff>
```

Arm B uses one profile, `lab-qwen38-q8`, for all roles, so arm B needs no swap.

### 1. Lab order and intake

A work order with a `process_lab` block (`forge-c/process-lab/1`) is a lab order. It is valid only when all of these
hold:
*   `purpose` is `QM`.
*   `delivery_first` and `development_execution_policy` are absent.
*   `evaluation_holdout` is `true`, so validated lessons are not retrieved into packets
    (`ff/knowledge/context.py:29`).
*   The block names `experiment_id`, `driver`, `seq` (1–5), `role`, `profile` and `model_profile`.
*   For seq ≥ 2, the block names the input handoff (and findings record) by path and sha256.

`model_profile` here is the model key under the profile's `models.allowed`. That is the meaning used by
`product_job.prepare` and `_launcher` (`ff/afo/product_job.py:40`).

Intake (`ff/workorder.py`, beside the `delivery_first` hook) checks the following for seq ≥ 2:
*   The declared handoff sha256 equals the file's sha256.
*   The handoff's `experiment_id` and `driver` equal the block's.
*   The handoff's primary-source hashes equal this order's declared reference-manual inputs.
*   The role sequence is a valid next step: INSPECT after AUTHOR or REWORK, REWORK after INSPECT with at least one
    `FINDINGS`, and at most two of each.

A failed check refuses the order with `PROCESS_LAB_HANDOFF_HASH_MISMATCH`, `PROCESS_LAB_HANDOFF_SCOPE_MISMATCH` or
`PROCESS_LAB_ROLE_SEQUENCE_INVALID`.

### 2. Per-role graphs and terminal reasons

`builder._build` is not changed. Near `ff/workflow/builder.py:212`, where the delivery-first hook sits,
`builder.build` hands a lab manifest to `process_lab.workflow(manifest)`. That function emits a small graph built
from the builder's existing helpers (`gate_cmd` and the `structured_authors` node forms):

*   **AUTHOR / REWORK:** `start → swe1_author → swe1_author_gate → lab_handoff → exit`.
    *   The existing bounded author-gate rework loop stays.
    *   For REWORK, a `materialize` node runs first. `swe1_author` then receives the consolidated findings (§7) as
        an extra frozen input, and re-authors only the groups (tasks) that carry FINDINGS. Other groups are copied
        from the materialized baseline.
*   **INSPECT:** `start → materialize → swe1_inspector → lab_inspect_record → lab_handoff → exit`.

Order terminal handling: `ff/afo/dispatch.py` never calls the recovery planner for lab orders. A terminal Fabro run
always goes to VALIDATING. `process_lab.verdict(workspace, run_status)` then returns BLOCKED with exactly one of these
reasons. A lab order never becomes `READY_FOR_OFFLINE_REVIEW`.

| Reason | Meaning |
|---|---|
| `PROCESS_LAB_HANDOFF_SEALED` | Handoff written and verified. The normal good outcome. |
| `PROCESS_LAB_AUTHOR_GATE_EXHAUSTED` | The author gate did not pass within its bounded loop. A handoff with `gate_status: FAILED` is still written, so it can be scored. |
| `PROCESS_LAB_MATERIALIZE_REFUSED` | The input handoff failed its run-time recheck. |
| `PROCESS_LAB_RUN_FAILED` | The Fabro run FAILED, CANCELLED or UNKNOWN, and no handoff exists. |

### 3. Admission (Ornith and every lab job)

Each lab order binds a `product_role_trial` (`ff/afo/product_role_trial.py`) for exactly its profile, model and role.
The per-experiment operator policy signs these bindings, and that policy also lists the lab profiles in
`engineering.allowed_model_profiles`. The repository `config/factory/afo-policy.yaml` is not edited. Because each
order has one profile and one model, the trial's single-profile, single-model rule (`authorized`, lines 29–47) holds.

### 4. Role batches and the activation tool

**Resident profile.** The resident profile is `FORGE_OPERATIONS_PROFILE` of the running Conductor. This is the
profile the managed stack is bound to (`ff/afo/services.py:100-110`). `scheduler.preflight` refuses a **lab** order
whose `profile` differs from it, with `RESIDENT_PROFILE_MISMATCH`, before admission and before any inference. Non-lab
orders are not checked.

**Batching.** Batching is done by the operator. `process_lab.next --experiment <record> --role <ROLE>` reads the
terminal handoffs and writes the next role's work orders. It writes REWORK orders only for drivers whose last
INSPECT handoff has at least one `FINDINGS`. The operator submits the orders with `python -m forge_factory.afo.cli submit`.

**Activation tool** `python -m forge_factory.process_lab.activate --to <profile>`. It is built from
`evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py:92-133`. The procedure re-reads the intent mode
and epoch before every step:

1.  **Precondition (read-only).** The tool checks all of these:
    *   no QUEUED, ADMITTED, RUNNING, WAITING_RECOVERY or VALIDATING order exists;
    *   the `afo_resource_ownership` `inference` holder is empty;
    *   the last lab job has QUIESCENCE evidence;
    *   no `afo_request_ledger` row is SENT or UNKNOWN.

    On failure, the tool exits with `ACTIVATE_NOT_QUIESCENT` and changes nothing.
2.  **Stop.** The managed `stack stop` performs `synchronize('shutdown')` and `settle_shutdown`. No bound order
    exists, so no order is blocked.
3.  **Rebind.** The tool stops the Conductor and watchdog units, then rewrites `conductor.env` and the units with
    the new `FORGE_OPERATIONS_PROFILE` / `FORGE_LRTX_PROFILE` and runs `systemctl --user daemon-reload`. Before
    images are kept as immutable files.
4.  **Resume.** It calls `operations.synchronize('resume', expected_epoch=<epoch read in step 1 + the stop>)`. If
    the epoch is wrong, it exits with `ACTIVATE_EPOCH_CHANGED` and leaves the stack STOPPED.
5.  **Start the stack.** `stack.start(settings, recovery=True)` runs while the Conductor is down, so nothing can be
    dispatched yet. A free-VRAM precondition (from `nvidia-smi`) must hold before the start. It requires at least
    the profile's `vram_required_gb`.
6.  **Health and identity.** The tool checks Fabro, gateway, Ollama and llama-server health, and that
    `profile.model_identity` matches. No inference probe is sent.
7.  **Start the Conductor and watchdog.**
8.  **Record.** It writes an immutable `forge-c/model-swap/1` record under `$B/operations/process-lab/<experiment>/`.
    The record holds the from/to profile sha and model digest, per-step UTC times, `load_and_control_start_seconds`,
    the outcome (`RUNNING`, `STOPPED_FAILED_LOAD`, `STOPPED_BY_OPERATOR` or `ACTIVATE_NOT_QUIESCENT`), the operator
    and the reason `PROCESS_LAB_ROLE_BATCH`.

A failed load stops the stack. The operator may run `activate` back to the previous profile; that is the rollback.
**Shared deployment.** All lab profiles share one `deployment` block (root, ports, Fabro storage), so the queue
database, the ledgers and Fabro history persist across switches.

### 5. Identity-correct caching (global, D9)

`structured.packet()` gains an `identity` argument. Its value is the `role_capability.IDENTITY` tuple (role,
model_digest, precision, reasoning, schema_mode, adapter_revision, context_tokens, sampling) plus the manifest's
`local_profile.config_sha256`.

*   **Model digest:** the profile-pinned manifest digest (`models.allowed[model].digest`).
*   **Schema mode:** resolved before hashing, with `schema_mode_for(model, digest)` reading the profile from the
    manifest, not from `FORGE_LRTX_PROFILE`.
*   **`without_lessons`:** passes the identity through.

Every structured path uses the new hash. Non-lab checkpoints therefore miss once after the change and are recomputed
(G7). Affected tests (those that reference `input_hash`) are updated in the same increment.

### 6. Stable requirement IDs

Requirement IDs are keyed by the assembly's existing `(task, key)` pair, which is schema-validated and unique within
a group (`ff/lrtx/swe1.py:44-45,592`).
*   **AUTHOR** assigns `SWR-001…` in assembly order.
*   **REWORK** loads the input handoff's `ids` map. It reuses the ID for an existing `(task, key)`, appends the next
    unused number for a new key, and moves IDs whose key disappeared to `retired[]`. Retired IDs are never
    reassigned.
*   The format stays `SWR-\d{3}`, which `swtrace`, `swe2` and `review_semantic` already require.
*   More than 999 IDs is refused with `SWR_ID_SPACE_EXHAUSTED`.

### 7. Inspector outcome per requirement

In lab mode, `review_semantic` always writes `.forge-run/lrtx/SWE.1/inspection-record.json`, including when the
visit fails. The record adds `outcomes[]`.

| Situation | Outcome |
|---|---|
| A standing (not withdrawn) claim targets the SWR | `FINDINGS` |
| Every checklist item covering the SWR was answered validly with no standing claim on it | `NO_FINDING` |
| Any item covering the SWR was INVALID, time-boxed (`Continue`), budget-exhausted (`VISIT_CALL_BUDGET_EXHAUSTED`) or never reached | `NOT_INSPECTED` |
| A claim targets `document` or an input path | Recorded under a `document` entry. Not spread across SWRs. |

**Actionable** means at least one `FINDINGS` outcome. The "repair budget" is the existing per-task 2+2 schema-repair
attempts in `visit.run_task`; repaired output is recorded as repaired, never silently. In lab mode, the inspector
reply ends the run instead of routing to an in-run rework. The strict path keeps today's behaviour.
`lab_inspect_record` writes the consolidated findings file
(`process-lab/SWE.1/findings.json`: SWR, claim, checklist item, source refs). A REWORK order receives this file as an
input.

### 8. Handoff package `forge-c/process-handoff/1`

The handoff is written by `lab_handoff` to `process-lab/SWE.1/handoff.json`. It is immutable once written. Fields and
where each comes from:

*   `schema`, `experiment_id`, `driver`, `order_id`, `seq`, `role`, `process: "SWE.1"`.
*   `job_identity`: the identity tuple from §5, plus profile sha, model digest and runtime/provider instance.
*   `baseline`: the existing `configuration/baselines/SWE.1/BL-SWE.1-nnn.json` id and `baseline_hash`. This replaces
    the separate seals from revision 1.
*   `inputs[]`: path, sha256 and role. Includes `input_handoff_sha256` when present. The oracle never appears here.
*   `artifacts[]`: path and sha256 for `software_requirements.md`, `.reqif`, `requirements_to_tests.csv` and
    `register_effects.json`.
*   `requirements[]`. Each entry has:
    *   `id`;
    *   `task`, `key`;
    *   `statement_sha256` (sha256 of the requirement line after whitespace normalization);
    *   `source_refs[]` (from the row's `source`);
    *   `assumption` (true when the source is `ASSUMPTION`, which is used only for owner-scope rows);
    *   `criterion` (the `Verification:` line);
    *   `inspector_outcome` (§7; `UNINSPECTED_ROLE` for AUTHOR/REWORK output).
*   `ids` (`{"<task>/<key>": "SWR-nnn"}`) and `retired[]`.
*   `trace[]`: edges from SWR to test ID, taken from `requirements_to_tests.csv`.
*   `gaps[]`: `forge-c/advisory-gap/1` refs.
*   `downstream_constraints[]`: the items in `traceability/upstream_gaps.md`.
*   `gate_status`: `PASSED` or `FAILED`.
*   `strict_release_status`: always `NOT_APPLICABLE_PROCESS_LAB`.

Requirements changed by the last REWORK carry `inspector_outcome: UNINSPECTED_ROLE` (the new handoff is never
inspected again under D4). The INSPECT handoff they came from keeps its own outcomes.

### 9. Experiment record, oracle and scoring

**Experiment record** `forge-c/process-lab-experiment/1`. The operator writes it once, before the first order, at
`$B/operations/process-lab/<experiment>/experiment.json`, and it is immutable. It holds:
*   arm, driver list and lab profile shas plus model digests;
*   the oracle sha256 per driver, with reviewer and review date;
*   Q5 values and scoring thresholds;
*   the maximum role sequence.

`process_lab.next` and `score` refuse inputs that disagree with it.

**Oracle** `forge-c/swe1-oracle/1`. One file per driver, stored under `$B/operations/process-lab/oracles/`. That
directory is outside every workspace, and no order manifest, packet or input names it. The confinement is a path
policy plus a prompt-assembly test. It is not an operating-system boundary. Each obligation carries:
*   `id`, `critical`, `kind` (behaviour, caller_contract, interface, state or error);
*   `accepted_source_refs[]` (pages);
*   an optional deterministic `predicate`: a set of `register/field/op[/value]` rows that must all appear in the
    package's `register_effects.json`;
*   `note`.

**Scorer** `python -m forge_factory.process_lab.score --handoff <h> --artifacts <dir> --oracle <o> --experiment <e> --out <dir>`.
It is deterministic and makes no model call or network access.

1.  Refuse unless the oracle's sha256 is in the experiment record and `--out` is outside the workspace.
2.  Verify every handoff artifact hash.
3.  **Ref resolution.** Each `RM0486 p.N` must name a page that exists in the bound section index. This reuses
    `assurance/swe12.cited_pages` / `_pages` and `assurance.hardware.index`. A ref that does not resolve and is not
    an assumption counts as `UNRESOLVED_REF`.
4.  **Coverage per obligation.**
    *   `COVERED_BY_PREDICATE`: the predicate is satisfied **and** a covering requirement cites an accepted source
        page.
    *   `COVERED_BY_DISPOSITION`: an owner-signed `review-disposition` record (existing contract
        `specs/014-durable-local-autonomy/contracts/review-disposition.schema.json`) names this obligation, the
        handoff sha and a verdict of covered.
    *   `UNCOVERED_BY_DISPOSITION`: the same record with a verdict of not covered.
    *   `UNKNOWN_NEEDS_HUMAN`: everything else. Keywords and source refs alone never cover an obligation.
5.  **Judgeable criterion.** The `Verification:` line names a method (`unit test`, `host test`, `target test`,
    `review`, `analysis`) **and** an observable outcome (a register value, return value, state or count). This is a
    fixed grammar check.
6.  **`criteria_result` for the driver.**
    *   `MEETS`: no critical obligation is uncovered or `UNKNOWN_NEEDS_HUMAN`; at least 90% of noncritical
        obligations are covered; there is no `UNRESOLVED_REF`; at least 90% of criteria are judgeable.
    *   `FAILS`: a critical obligation is uncovered, or any threshold is missed when the unknown obligations are
        counted as covered.
    *   `NEEDS_HUMAN`: otherwise.

    The 90% noncritical rule is applied **per driver** here. That is stricter than the plan's corpus-wide wording,
    and it is intentional, so that a failing driver cannot be hidden in an aggregate.
7.  **Output.** Write `score-<order>.json` to `--out`. The handoff is never modified.

Every role's handoff is scored. Comparing the AUTHOR, INSPECT and REWORK scores gives initial-vs-final quality and
shows when a rework made a correct requirement worse.

### 10. Minimal SWE.2 importer

`python -m forge_factory.process_lab.import_swe2 --handoff <h> --artifacts <dir> [--score <s>]`

*   **Validation.** It validates the schema and every hash.
*   **Rejections.**
    *   `HANDOFF_DUPLICATE_ID`: checked in code, because JSON Schema cannot express it.
    *   `HANDOFF_DANGLING_TRACE`: a trace edge to an unknown SWR, or an SWR that no test covers.
    *   `HANDOFF_HASH_MISMATCH`.
    *   `HANDOFF_SCHEMA_INVALID`.
*   **Classification.** It then lists each requirement:
    *   `AMBIGUOUS`: an assumption, or a `NOT_INSPECTED` requirement.
    *   `MISSING`: an oracle obligation reported uncovered by `--score`, listed when that file is given.
    *   `CONSUMABLE`: otherwise.
*   **Determinism.** Output uses sorted keys and has no timestamps.

### 11. Ornith serving and protocol

The speed study already served the D3 GGUF with the **same bundled binary** the stack uses
(`/mnt/data/forge-c/ollama-0.34.0/lib/ollama/llama-server`, `server-instance.json` argv), started outside the stack.
It used `--jinja --reasoning auto --reasoning-format deepseek` and per-request
`chat_template_kwargs.enable_thinking` / `thinking_budget_tokens` (`run_benchmark.py:332`). What has not been run is
that binary under the managed stack.

Changes to `stack.llama_server_spec`:
*   It resolves `hf.co/<org>/<repo>:<tag>` manifests under `manifests/hf.co/<org>/<repo>/<tag>`, with the same
    manifest-sha and blob-size checks.
*   It takes `reasoning_format` from the profile. The default stays `deepseek`, so existing argv is unchanged.
*   It requires `vram_required_gb` to be declared for lab profiles.

The gateway takes per-model `request_overrides` from the profile (`chat_template_kwargs`, `thinking_budget_tokens`)
and records them in the identity's `reasoning` field.

Context is set only through `runtime.ollama.OLLAMA_CONTEXT_LENGTH`. The Ornith starting value is 32768 with f16 KV.
The weights are 37.8 GB, which leaves about 10 GB of the 48 GB for KV, compute buffers and CUDA overhead. The value
is raised only after a measured native run.

Protocol fixtures run in CI with recorded responses, from public final answers only:
*   template rendering on and off (the named efforts low/medium/high/xhigh render to one identical template, sha
    `3a1e4036…`; thinking off renders differently);
*   a fenced or trailing-text JSON answer is INVALID;
*   reasoning content is stripped from records;
*   `finish_reason: length` is INVALID;
*   a timeout is `OUTCOME_UNKNOWN`;
*   the schema-mode probe is keyed by digest.

`tools`/`tool_choice` are not used by the lab's structured path. They must be qualified before any tool-using Ornith
role is added.

### 12. QM exception for the stepwise inspector (D7)

`release/qm.validate_profile` accepts `structured.semantic_inspect_phases == ["SWE.1"]` (and nothing else semantic)
only when the profile declares `process_lab: true` **and** the work order carries a valid `process_lab` block. Every
other QM order keeps the existing `QM_SCOPE_PROFILE_MISMATCH` refusal. `aspice.validate_profile` is unchanged.

### 13. CRC lab example and leakage controls

`examples/0020-process-lab-crc/workorder.json` declares only these inputs, by path and sha256:
*   the RM0486 CRC sections;
*   the CMSIS device header;
*   the owner scope, which is the two-function `LL_CRC_Write_IDR` / `LL_CRC_Read_IDR` scope.

It explicitly omits the following, all of which are present in `0014g`:
*   `../0014f-.../provided-requirements.json`;
*   `idr_oracle.c` and `idr_target_oracle.c`;
*   `operation_scope.prompt_overrides`;
*   `development_execution_policy`;
*   `delivery_first`.

The isolation test refuses any lab order with an input whose role contains `reference`, `oracle`,
`provided_requirements` or `reviewed`, and any packet that contains a lesson or an oracle path or hash.

### 14. CRC vertical smoke

The existing two-function CRC Delivery-First fixture tests keep passing after every increment. They are a smoke
result, not SWE.1 qualification.

### What stays unchanged

*   The strict graphs and release policies.
*   `QM_DELIVERY_FIRST_DEMO`.
*   The Feature 015 workflows.
*   The existing Qwen profiles.
*   The release manager and stored archives.
*   Operations intent semantics.
*   Admission.
*   The mission ledger.
*   `builder._build`.
*   `aspice.validate_profile`.
*   The queue state machine and attempt schema.

The only effects on non-lab orders are the one-time G3 checkpoint recompute and the D7 exception, which is scoped
by construction.

## Alternatives Considered

### Alternative A: One order per driver with up to five planned attempts (revision 1's D1)

*   **Pros**: One mission ledger and one history per driver.
*   **Cons**: It does not fit the code:
    *   Planned attempts bypass `scheduler.preflight`, which only sees QUEUED orders.
    *   `max_concurrent_workorders: 1` blocks batching across drivers.
    *   `max_order_attempts: 3` is too low for five attempts.
    *   The epoch fence quarantines launches queued before a swap (`ff/afo/dispatch.py:84-87`).
    *   Resume carries only phases whose gate passed, and refuses a profile change (`ff/workorder.py:494-500`,
        `ff/brownfield/resume.py:314`).
    *   `attempt.schema.json` forbids extra fields.
*   **Reason for Rejection**: The EGM review found this (Stages 5, 7, 8, 9), and the owner chose D1′.

### Alternative B: Keep A, but requeue the order between attempts

*   **Pros**: One ledger per driver.
*   **Cons**:
    *   It changes the shared queue state machine (`specs/005-.../queue-fsm.yaml`) and the attempt schema.
    *   It needs a new carry-over rule outside the rule that only passing phases are carried over.
    *   It needs `max_order_attempts` of 5 and new deadline semantics.
*   **Reason for Rejection**: It changes AFO semantics for every order (against G7). The owner chose D1′.

### Alternative C: Swap the model inside one job

*   **Pros**: One Fabro run per driver.
*   **Cons**: It breaks the "one job = one model" admission invariant. The gateway shares the provider's process
    namespace.
*   **Reason for Rejection**: It needs the largest change to safety-relevant admission code.

### Alternative D: The Conductor performs the profile switch unattended

*   **Pros**: Corpus runs need no operator at switches.
*   **Cons**:
    *   It is a new autonomous action on the provider, close to the model router the plan excludes.
    *   It needs an `operate_service` grant scope and failed-load handling with no human present.
*   **Reason for Rejection**: Owner decision D2. With D1′, arm A needs at most four switches per corpus run and arm B
    needs none.

### Alternative E: Keep both models resident

*   **Cons**: 37.8 GB of Ornith weights plus 27B Q8 Qwen weights exceed 48 GB before any KV cache.
*   **Reason for Rejection**: Not feasible at Q8.

### Alternative F: Score with the inspector or with model votes

*   **Cons**: Correlated errors. Recorded clean-baseline false rejections: 5/9 on the calibration subset and 2/2 on
    the F015 held-out set (`evidence/014-durable-local-autonomy/stepwise-inspector-20261026/`).
*   **Reason for Rejection**: Plan invariant 6.

### Alternative G: The AtomicChat Ornith build named in the plan

*   **Reason for Rejection**: Not downloaded and not measured. Owner decision D3.

### Alternative H: Universal 64K or advertised 262K context

*   **Cons**: A whole-workflow 64K context already failed serialized-request sizing in the overnight campaign. 262K
    at Q8 on 48 GB is unmeasured for real tasks.
*   **Reason for Rejection**: Context is a per-profile, measured setting (§11).

### Alternative I: Run SWE.1 by calling `lrtx.runner` directly from AFO, outside Fabro

*   **Cons**: It loses the Fabro run lifecycle, native-liveness reconciliation, AFO admission and accounting.
    `runtime._launcher` requires a `fabro_run_id`.
*   **Reason for Rejection**: Lab results must come from the same engine and accounting as production runs.

### Alternative J: Content-hash requirement IDs

*   **Cons**: The ID changes whenever rework edits the text, and the format breaks `SWR-\d{3}`.
*   **Reason for Rejection**: `(task, key)` keys are stable and already validated (§6).

### Alternative K: Use `lrtx/modelcmp.py` (LRTX-T023) as the lab

*   **Pros**: It already runs the real structured SWE.1 visit for several models on a frozen workspace copy. It
    freezes the output through the author gate and measures model load time.
*   **Cons**: It bypasses AFO admission, accounting and lifecycle, the same cost as Alternative I.
*   **Reason for Rejection**: Not the production path. Its load-time measurement approach is reused in the activation
    record.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| The bundled llama-server works for Ornith standalone but fails under the managed stack (template, flags, health) | Protocol fixtures in CI. The runbook's first native step is an activation of `lab-ornith-q8` with no orders queued. `STOPPED_FAILED_LOAD` keeps the stack stopped, and the owner decides. |
| 48 GB VRAM is exceeded (Ornith 37.8 GB + KV) | 32K context, f16 KV, `vram_required_gb` check before start. Raise context only after a measured run. |
| A stale VRAM holder after a stop | Free-VRAM precondition in `activate` step 5. Kernel-proven provider exit already exists. |
| The operator is unavailable at a switch, so the queue idles | Accepted cost of D2. At most 4 switches per arm-A corpus run. Each switch is timed in the activation record. |
| Human adjudication load (`UNKNOWN_NEEDS_HUMAN`) | Deterministic predicates for register obligations. A disposition is needed only for behavioural obligations. Q4 blocks the first scored result, not the implementation. Expected volume is reported per driver. |
| A wrong handoff link makes an inspector read the wrong candidate | Intake and the run-time `materialize` recheck sha256, experiment, driver and source hashes (CUJ 6). Negative tests. |
| Oracle or reference leakage into author prompts | `evaluation_holdout`, the role-based input refusal, the packet scan test, the oracle directory outside workspaces (§13). |
| Rework degrades correct requirements, and the last REWORK is uninspected | Every handoff is scored, and per-driver AUTHOR→REWORK deltas are reported. The uninspected status is explicit (`UNINSPECTED_ROLE`). |
| The global G3 change recomputes in-flight non-lab checkpoints | It is a one-time cost, stated in G7. Tests referencing `input_hash` are updated in the same increment. |
| The D7 exception leaks into ordinary QM orders | The exception requires both the profile flag and a valid lab block. A failed-before test covers ordinary QM orders. |
| A failed activation leaves no stack running | Rollback is `activate` back to the previous profile. Before-images of env and units are kept. |
| Rough cost | Per driver: up to 5 orders. SWE.1-only orders are expected in minutes to tens of minutes; this is unmeasured, and native timing is recorded per order. Plus up to 4 switches per arm-A corpus run. |

## Non-Functional Requirements

*   **Security & privacy.** Oracle files, vendor manuals and raw prompts or responses never enter source control or
    public evidence. Reasoning text is discarded, and only counts are kept. Handoffs contain hashes and IDs, not
    manual text.
*   **Performance.** These values are measured, not targets:
    *   per switch: step times and `load_and_control_start_seconds`;
    *   per order: wall time, requests, tool calls, reported tokens against reservations, and VRAM peak.
*   **Rollout & rollback.** Opt-in through the `process_lab` block. Without it, behaviour equals `876d75f` apart from
    the one-time G3 recompute. There is no database migration.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Paths are relative to the repository root. `ff/` = `factory/python/forge_factory/`, and test paths are under
`factory/python/tests/`.

Each increment ends with two conditions met before the next starts:
*   its new tests pass;
*   the Verification Plan regression battery passes.

### Increment order

1.  G3 identity hash (global) and `hf.co` manifest / `reasoning_format` / `vram_required_gb` in `stack.py`.
2.  Runtime contracts and loader (`process-lab`, `process-handoff`, `swe1-oracle`, `process-lab-experiment`,
    `model-swap`).
3.  Lab intake, the D7 QM exception and the AUTHOR graph with `lab_handoff`. Lab terminal verdict and no recovery.
4.  Stable IDs, the INSPECT graph (`materialize`, per-SWR outcomes, findings file) and the REWORK graph.
5.  Lab profiles, `product_role_trial` bindings in the CRC example, the scheduler resident-profile refusal and
    `process_lab.next`.
6.  The activation tool and `model-swap/1` records, using fixture systemd and ledger state only.
7.  Scorer and SWE.2 importer.
8.  CRC lab example and the end-to-end synthetic-provider test. Native runs stay `NATIVE_NOT_RUN`.

### Target Files to Create/Modify

#### 1. `ff/lrtx/structured.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   `packet(..., identity: dict)` hashes `identity` (the §5 tuple plus `profile_config_sha256`) into
        `input_hash`, which is computed in `build` near line 237.
    *   `schema_mode_for(model, digest)` gains a `profile` argument, taken from the manifest.
    *   `without_lessons` forwards `identity`.

#### 2. `ff/lrtx/visit.py`, `ff/lrtx/runner.py` (Modify)

*   **Type / Scope**: Python modules.
*   **Proposed Changes**:
    *   The runner builds `identity` from the workspace manifest (`local_profile.config_sha256`, the
        `models.allowed[model]` digest and precision, and the profile's reasoning and sampling) and passes it to
        `visit.run_task` and `structured.packet`.
    *   Schema mode is resolved before `build`.

#### 3. `ff/lrtx/stack.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: In `llama_server_spec`:
    *   `hf.co/<org>/<repo>:<tag>` resolves to `manifests/hf.co/<org>/<repo>/<tag>`. The library path stays the same
        for names without a slash.
    *   `reasoning_format` comes from `runtime.llama_server.reasoning_format`, default `deepseek`.
    *   If the profile has `process_lab: true`, it must declare `runtime.llama_server.vram_required_gb`, or the spec
        raises `LLAMA_SERVER_VRAM_REQUIREMENT_MISSING`.

#### 4. `ff/llm_gateway.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `sanitize_request` applies the profile's `gateway.request_overrides[model]`, which allows
    only `chat_template_kwargs.enable_thinking` (bool) and `thinking_budget_tokens` (int, 0–16384). Any other key is
    refused at profile load (`GATEWAY_REQUEST_OVERRIDE_INVALID`).

#### 5. `specs/014-durable-local-autonomy/contracts/runtime/` (Create)

*   **Type / Scope**: Runtime-loaded JSON Schemas. This follows the `specs/005-autonomous-factory-operations/contracts`
    pattern loaded by `ff/afo/contracts.py`.
*   **Proposed Changes**: Five schemas.
    *   `process-lab.schema.json`: the §1 block. `role` enum. `seq` 1–5. `input_handoff` `{path, sha256}` is required
        when `seq ≥ 2`. `findings` `{path, sha256}` is required for REWORK. `additionalProperties: false`, and no
        oracle field.
    *   `process-handoff.schema.json`: §8. `requirements[].id` pattern `^SWR-[0-9]{3}$`. `inspector_outcome` enum:
        `FINDINGS`, `NO_FINDING`, `NOT_INSPECTED`, `UNINSPECTED_ROLE`. `strict_release_status` const
        `NOT_APPLICABLE_PROCESS_LAB`.
    *   `swe1-oracle.schema.json`: §9.
    *   `process-lab-experiment.schema.json`: §9.
    *   `model-swap.schema.json`: §4 step 8.

#### 6. `ff/process_lab/contracts.py` (Create)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `require(name, doc)` loads the five schemas from item 5 with the same validator as
    `ff/afo/contracts.py`, and raises `PROCESS_LAB_CONTRACT_INVALID:<name>:<path>`.

#### 7. `specs/014-durable-local-autonomy/contracts/validate_contracts.py`, `README.md`, `examples/manifest.json`, `examples/` (Modify)

*   **Type / Scope**: Validator, docs, fixtures.
*   **Proposed Changes**:
    *   The validator also checks `runtime/*.schema.json` against fixtures in `examples/process-lab/`.
    *   Each runtime schema gets one valid fixture and two invalid ones. Examples: an oracle key in a lab block,
        `seq: 2` without `input_handoff`, and `strict_release_status` changed.
    *   Every fixture is registered in `examples/manifest.json`.
    *   The README lists the runtime directory as runtime-loaded.

#### 8. `ff/process_lab/__init__.py` (Create)

*   **Type / Scope**: Python package.
*   **Proposed Changes**:
    *   `MODE = "QM_PROCESS_LAB"`.
    *   `selected(manifest)`.
    *   `contract(spec)`. Applies the §1 rules. Refuses `PROCESS_LAB_MODE_CONFLICT` (with `delivery_first` or a
        development policy), `PROCESS_LAB_HOLDOUT_REQUIRED` and `PROCESS_LAB_INPUT_ROLE_FORBIDDEN` (§13 role list).
    *   `check_handoff_input(spec, inputs)`. Applies the §1 hash, scope and role-sequence checks.
    *   `workflow(manifest)`. Emits the §2 graphs.
    *   `verdict(workspace, run_status)`. Returns the §2 reason table.

#### 9. `ff/process_lab/handoff.py` (Create)

*   **Type / Scope**: Python module, plus CLI entry points used as Fabro command nodes.
*   **Proposed Changes**:
    *   `materialize(workspace)`.
        *   Re-checks the input handoff, then rebuilds the SWE.1 artifacts from the handoff's artifact copies. It
            uses `swe1.assemble`'s writers and `visit.write_scoped`, following `ff/provided_requirements.py:54-96`.
        *   Freezes a baseline through the existing author gate.
        *   Writes an authorship receipt that names the source order, its handoff sha and its job identity.
        *   Does not require a human review: the input is a lab handoff, not provided requirements.
        *   Refuses `PROCESS_LAB_MATERIALIZE_REFUSED:<reason>`.
    *   `inspect_record(workspace)`. Writes `findings.json` from the §7 outcomes.
    *   `write_handoff(workspace)`. Implements §8. It copies the artifacts into `process-lab/SWE.1/artifacts/`, with
        no overwrite.

#### 10. `ff/process_lab/ids.py` (Create)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `assign(rows, prior_ids, prior_retired) -> (ids, retired)` implements §6.

#### 11. `ff/process_lab/next.py` (Create)

*   **Type / Scope**: CLI `python -m forge_factory.process_lab.next`.
*   **Proposed Changes**:
    *   Arguments: `--experiment <experiment.json>`, `--role INSPECT|REWORK`, `--orders <dir>`, `--out <dir>`.
    *   It reads the latest terminal handoff per driver and writes one work order per eligible driver. REWORK orders
        are written only when the driver's last handoff is an INSPECT with at least one `FINDINGS`.
    *   It refuses a profile that is not the experiment's profile for that role, and refuses to go past D4's
        sequence.
    *   No model calls.

#### 12. `ff/process_lab/activate.py` (Create)

*   **Type / Scope**: Operator CLI `python -m forge_factory.process_lab.activate`.
*   **Proposed Changes**:
    *   Arguments: `--to <profile>`, `--experiment <e>`, `--reason PROCESS_LAB_ROLE_BATCH`.
    *   Implements §4 steps 1–8 and the outcome codes.
    *   The systemd unit names come from `ff/afo/services.py`. There is no `--force`.

#### 13. `ff/process_lab/score.py`, `ff/process_lab/import_swe2.py` (Create)

*   **Type / Scope**: CLIs.
*   **Proposed Changes**: Implement §9 and §10 exactly, with the reason codes listed there.

#### 14. `ff/workorder.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   Copies `spec["process_lab"]` into the manifest next to the `delivery_first` copy near line 293.
    *   Calls `process_lab.contract` and `process_lab.check_handoff_input` next to the delivery-first contract call
        near line 406.
    *   Passes the manifest flag to `qm.validate_profile` (item 17).

#### 15. `ff/workflow/builder.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: In `build`, next to the delivery-first hook at line 212: when the manifest has `process_lab`,
    return `process_lab.workflow(manifest)`. `_build` is not changed.

#### 16. `ff/afo/dispatch.py`, `ff/afo/scheduler.py` (Modify)

*   **Type / Scope**: Python modules.
*   **Proposed Changes**:
    *   **`reconcile_running`:** for lab orders, skip `recover` and go to VALIDATING.
    *   **`validate`:** lab orders use `process_lab.verdict` instead of `package_verdict`.
    *   **`scheduler.preflight`:** for lab orders only, add `RESIDENT_PROFILE_MISMATCH` when the order's
        `process_lab.profile` differs from `os.environ["FORGE_OPERATIONS_PROFILE"]`. This is a refusal, not a
        deferral.

#### 17. `ff/release/qm.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `validate_profile(purpose, prof, *, process_lab=False)` applies the §12 exception.

#### 18. `ff/lrtx/review_semantic.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: In lab mode:
    *   `visit` always writes `inspection-record.json` with `outcomes[]` (§7), including on failure.
    *   The reply finishes the run with status `DONE` instead of `REWORK` or `CONTINUE`.

    The non-lab path is unchanged.

#### 19. `ff/lrtx/swe1.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: In lab mode:
    *   `assemble` takes IDs from `process_lab.ids.assign`.
    *   For REWORK, `visit` re-authors only tasks listed in `findings.json`. Other tasks come from the materialized
        baseline.

#### 20. `config/factory/profiles/local-rtx-v2-omniverse2-lab-ornith-q8.yaml` (Create)

*   **Type / Scope**: Local profile.
*   **Proposed Changes**: Full key set:
    *   `schema: forge-c/local-profile/1`, `work_order_purpose: QM`, `process_lab: true`.
    *   `models.allowed["hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"]`:
        *   `digest`: sha256 of the Ollama manifest file. This is read on Omniverse2 (read-only) before the file is
            completed; it is never guessed.
        *   `quantization: Q8_0`.
        *   `role_qualification: EXPERIMENTAL_PROCESS_LAB`.
        *   `license: MIT`.
    *   `runtime.ollama.OLLAMA_CONTEXT_LENGTH: 32768`, `OLLAMA_KV_CACHE_TYPE: f16`.
    *   `runtime.llama_server`: `slots: 1`, no `mtp_draft`, `reasoning: auto`, `reasoning_format: deepseek`,
        `gpu_layers: all`, `vram_required_gb: 46`.
    *   `gateway.request_overrides`: the Q5 values.
    *   `structured.phases_by_layer.LL: [SWE.1]`, `structured.semantic_inspect_phases: [SWE.1]`,
        `inspector_stepwise: true`, `reinspect_direct: false`.
    *   `admission` and `deployment`: identical to item 21.

#### 21. `config/factory/profiles/local-rtx-v2-omniverse2-lab-qwen38-q8.yaml` (Create)

*   **Type / Scope**: Local profile.
*   **Proposed Changes**:
    *   Model `qwen3.8:27b-q8_0`, digest `8f5fb6b71ea00052cbe8545738c55ce61112c4e571cb60ca4dad00b131766039`,
        `quantization: Q8_0`.
    *   The same structured keys as item 20.
    *   Author reasoning and sampling taken from `local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector.yaml`
        (`gateway.reasoning.role_efforts` and `structured.inspector_sampling` keys only).
    *   No `development_execution_policy`.
    *   A shared `deployment` block (`default_root: /mnt/data/forge-c/process-lab`, one port set) used by both lab
        profiles.

#### 22. `examples/0020-process-lab-crc/` (Create)

*   **Type / Scope**: Example work order plus README.
*   **Proposed Changes**:
    *   AUTHOR (seq 1) `workorder.json` per §13.
    *   `process_lab` block with `role: AUTHOR`, `profile` and `model_profile` for arm A.
    *   `evaluation_holdout: true`.
    *   A `product_role_trial` reference placeholder name, which the operator's signed policy resolves.
    *   No oracle.

#### 23. `docs/runbooks/process-lab-omniverse2.md` (Create)

*   **Type / Scope**: Runbook.
*   **Proposed Changes**: Sections:
    *   Prerequisites: owner window, signed per-experiment policy with `product_role_trial` bindings, STOPPED intent,
        free storage, the manifest sha read for item 20.
    *   Writing the experiment record.
    *   The first native step: activating `lab-ornith-q8` with an empty queue.
    *   Per-role batch commands (`afo.cli submit`, `process_lab.next`, `process_lab.activate`).
    *   Scoring and dispositions.
    *   Rollback.
    *   What to record as `NATIVE_NOT_RUN`.

#### 24. `docs/designs/forge-c-process-first-ornith-qwen.md` (Modify)

*   **Type / Scope**: This design.
*   **Proposed Changes**: Record the targeted re-review result and the final status.

#### 25. Tests in `factory/python/tests/` (Create)

Each test lists the plan AT it maps to, when the meaning matches.

*   `test_process_lab_identity_hash.py` (LAB-T01, AT03):
    *   each IDENTITY field and `config_sha256` changes `input_hash`;
    *   the same identity reuses the hash;
    *   strict-path packets also change.
*   `test_lrtx_stack_hf_manifest.py` (LAB-T02):
    *   an `hf.co` manifest resolves;
    *   wrong manifest sha, wrong size or a missing blob are refused;
    *   library models and the default `reasoning_format` produce byte-identical argv;
    *   a lab profile without `vram_required_gb` is refused.
*   `test_process_lab_contract.py` (LAB-T03):
    *   a valid block is accepted;
    *   an oracle key, `delivery_first`, a missing holdout, a forbidden input role, and seq 2 without a handoff are
        all refused.
*   `test_process_lab_handoff_input.py` (LAB-T04, CUJ 6):
    *   hash, experiment, driver and source mismatches are refused;
    *   an invalid role sequence is refused (REWORK after AUTHOR, a third INSPECT).
*   `test_process_lab_graph.py` (LAB-T05, AT02):
    *   per-role graphs contain no SWE.2–6, finalize or release node;
    *   non-lab graphs for the strict and Delivery-First examples equal `876d75f`, using
        `tests/peripheral_golden.py` `normalized_graph`.
*   `test_qm_process_lab_exception.py` (LAB-T06): fails before the change and passes after.
    *   A lab profile plus a lab block is accepted.
    *   A lab profile without a block is refused with `QM_SCOPE_PROFILE_MISMATCH`.
    *   An ordinary QM profile with semantic phases is still refused.
*   `test_process_lab_verdict.py` (LAB-T07): every §2 reason is reachable, `READY_FOR_OFFLINE_REVIEW` is never
    returned, and the recovery planner is never called.
*   `test_process_lab_resident_profile.py` (LAB-T08, AT04): a lab order with a non-resident profile is refused
    before admission; non-lab orders are unaffected.
*   `test_process_lab_activate.py` (LAB-T09, AT04/AT05). Uses fixture ledger, intent and systemd stubs, with no
    real units.
    *   A non-empty queue, a held inference owner, a SENT or UNKNOWN request, or missing QUIESCENCE gives
        `ACTIVATE_NOT_QUIESCENT` with nothing changed.
    *   An epoch change gives `ACTIVATE_EPOCH_CHANGED` with the stack stopped.
    *   An operator STOP before step 7 gives `STOPPED_BY_OPERATOR`.
    *   A failed health or identity check gives `STOPPED_FAILED_LOAD`.
    *   The record validates against `model-swap/1`.
*   `test_process_lab_ids.py` (LAB-T10): IDs are stable across REWORK, retired IDs are never reused, and the 999
    limit is enforced.
*   `test_process_lab_inspector_outcome.py` (LAB-T11, AT09):
    *   an invalid item, time box or exhausted budget maps to `NOT_INSPECTED`;
    *   a record is written on failure;
    *   document claims stay separate;
    *   the inspector cannot write the baseline, inputs or handoff.
*   `test_process_lab_handoff.py` (LAB-T12):
    *   §8 fields derive from fixture artifacts;
    *   the handoff and artifact copies cannot be overwritten;
    *   a REWORK-changed requirement is marked `UNINSPECTED_ROLE`.
*   `test_process_lab_score.py` (LAB-T13, AT10):
    *   a critical obligation that is uncovered or unknown gives FAILS or NEEDS_HUMAN, even when every outcome is
        `NO_FINDING`;
    *   a keyword-only match does not count as coverage;
    *   an unresolved ref is reported;
    *   an oracle not in the experiment record is refused;
    *   `--out` inside the workspace is refused;
    *   a signed disposition covers an obligation and an unsigned one is refused.
*   `test_process_lab_import_swe2.py` (LAB-T14, AT12): a valid package imports; duplicate, dangling and
    hash-mismatch packages are rejected; output is byte-identical across runs.
*   `test_process_lab_isolation.py` (LAB-T15): no lab packet, manifest or input list contains an oracle path or
    hash, a lesson, or an input with a forbidden role.
*   `test_process_lab_ornith_protocol.py` (LAB-T16): the §11 fixtures; request overrides outside the allowed keys
    are refused.
*   `test_process_lab_next.py` (LAB-T17): REWORK orders are written only for drivers with FINDINGS; D4's sequence
    limit is enforced; a wrong profile is refused.
*   `test_process_lab_e2e_fixture.py` (LAB-T18, AT15): AUTHOR → INSPECT → REWORK over two drivers, then score and
    import. Outputs are labelled `NATIVE_NOT_RUN`. It reuses two existing fakes:
    *   the scripted structured-model fakes in `test_lrtx_swe1.py` / `test_lrtx_v2_swe1.py`;
    *   the fake Fabro run view from `test_afo_m3_reconcile.py` / `test_afo_m4_recovery.py`.

    Graph nodes run as direct command-node calls. No real Fabro server is used.

### Verification Plan

*   **Environment:** loop10, `source scripts/forge-env.sh`, `FORGE_DATA_ROOT=$B`, `$B/venv/bin/python`, a fresh
    worktree under `$B/repos/` per regression run.
*   **Unit:** `$B/venv/bin/python -m pytest factory/python/tests/test_process_lab_*.py factory/python/tests/test_lrtx_stack_hf_manifest.py factory/python/tests/test_qm_process_lab_exception.py -q`
    passes after each increment. Each negative test is shown failing before its fix.
*   **Regression:**
    *   `$B/operations/feature014/run_full_inherited.py <worktree> <out>` (outside the repository) reports 0 new
        failures against the `876d75f` baseline, except the listed tests updated for G3.
    *   `test_delivery_first*.py` and the F015 and strict-graph test files pass unchanged.
*   **Static:**
    *   `ruff check` on the changed files;
    *   `python3 tests/spec/validate_design.py`;
    *   `python3 specs/014-durable-local-autonomy/contracts/validate_contracts.py`;
    *   `python3 specs/014-durable-local-autonomy/validate_spec.py` (DA count stays 58, with no row changes).
*   **CRC smoke:** the existing Delivery-First CRC fixture tests pass. A native smoke is `NATIVE_NOT_RUN`.
*   **Native:** `NATIVE_NOT_RUN` in this design's scope. The first native step needs an owner window and follows
    the runbook.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
