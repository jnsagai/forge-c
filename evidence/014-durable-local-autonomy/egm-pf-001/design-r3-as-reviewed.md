# Forge-C Process-First Lab: SWE.1 with an Ornith Author and a Qwen Inspector

*   **Author:** jnsagai (owner), drafted by Claude (Elephant)
*   **Status:** Revision 3 (owner go-ahead 2026-10-31, after revision 2 was frozen). It addresses the 7 Blockers and
    the Majors of the targeted re-review (`evidence/014-durable-local-autonomy/egm-pf-001/targeted_rereview_report.md`).
    A targeted re-review of revision 3 is pending. Not yet approved for implementation, except G3, which is
    implemented as CAPA-074 (`dc1dd059`).
*   **Date:** 2026-10-31
*   **Source of truth:** Feature 014 Spec Kit (`specs/014-durable-local-autonomy/`).
*   **Implements:** the plan `specs/014-durable-local-autonomy/PROCESS-FIRST-ORNITH-QWEN-EGM-CLAUDE.md` (`876d75f`).
*   **Source facts:** `evidence/014-durable-local-autonomy/egm-pf-001/SOURCE-INVENTORY.md`.
*   **Review trail:** `evidence/014-durable-local-autonomy/egm-pf-001/`, which holds:
    *   revisions 1 and 2 as reviewed;
    *   the stage 5–9 reports;
    *   `goldfish_review_report.md`;
    *   the targeted re-review.

--------------------------------------------------------------------------------

## Overview

Forge-C turns owner scope and frozen sources into embedded-C drivers and ASPICE-inspired work products. The sources
are reference manuals, device headers and existing code. It runs on local models on one 48 GB GPU (Omniverse2). At
`876d75f`, every experiment runs the whole SWE.1–SWE.6 graph.

This design adds an opt-in **process lab** that runs **only SWE.1**, software requirements analysis, for LL drivers.
*   **Orders.** Each lab work order has exactly **one role** (AUTHOR, INSPECT or REWORK) and one model.
*   **Chaining.** A driver goes through up to five orders. Each later order takes the earlier order's sealed SWE.1
    handoff as a hash-checked input. The operator copies the handoff into an ignored folder inside the repository.
*   **Models.** Ornith-1.5-35B-A3B Q8_0 authors and reworks. Qwen3.8-27B Q8 inspects (arm A). Qwen does every role in
    the reference arm (arm B).
*   **Operator tools.** Three model-free tools, built from existing AFO patterns, do the operator's work:
    *   `provision` creates the missions, order envelopes, launch manifests and product-role trial;
    *   `next` prepares the following role's orders;
    *   `activate` switches the factory's profile between role batches.
*   **Scoring.** A deterministic scorer pre-scores each handoff against a frozen oracle that the author never sees.
    Obligations that no deterministic predicate decides need an owner-signed lab disposition.
*   **SWE.2 check.** A minimal SWE.2 importer proves that a handoff can be consumed.
*   **Smoke test.** The two-function CRC Delivery-First smoke keeps passing.

There is no new scheduler, release authority, model router or EGM runtime. AFO never loads or unloads a model by
itself.

### Glossary

*   **AFO:** autonomous factory operations. The durable work-order queue, scheduler, dispatch, mission ledger and
    Conductor service (`ff/afo/`).
*   **Fabro:** the workflow engine that runs a work order's graph.
*   **Mission:** the AFO budget and lineage record that a durable order must be linked to (`ff/afo/mission_ledger.py`).
*   **Envelope:** the submitted work-order record (`specs/005-autonomous-factory-operations/contracts/work-order.schema.json`).
*   **Launch manifest:** the repository file that an envelope references, and that the launcher reads
    (`runtime._launcher`).
*   **Operations intent / epoch:** the operator mode (RUNNING, PAUSED, DRAINING, STOPPED). Its counter increases on
    every change.
*   **Inference owner:** the single job allowed to send model requests.
*   **QUIESCENCE evidence:** the ledger proof that a job has no open request.
*   **Owner window:** an owner-authorized, time-bounded live execution.
*   **Other short names:**
    *   **loop10:** the development host.
    *   **MTP:** multi-token prediction drafting.
    *   **F015:** Feature 015.
    *   **DA tasks:** the Feature 014 task ledger (30/58).
*   **Path shorthands:**
    *   `ff/` = `factory/python/forge_factory/`.
    *   `$B` = `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c` (loop10).
    *   `$R` = the Omniverse2 data root `/mnt/data/forge-c`.

## The Problem

1.  **Full-pipeline runs are slow and blur the cause of a failure.** The overnight Qwen cohort
    ([report](https://github.com/jnsagai/forge-c/blob/45190ebca727d28225e9ee61e0908fd0ffdae166/docs/reports/ASTRA-OVERNIGHT-REVIEW-20261030-31.md),
    evidence revision `dce7ad27`) had three trials:
    *   2 of them reached a scoped functional pass on a two-function CRC slice.
    *   The original mission used 1,470 requests and 2,583 tool calls over 7 attempts.
    *   The strict packages still had 16 open gaps (trial 06) and 35 open gaps (trial 07).

    A SWE.5 failure does not show whether SWE.1 caused it.
2.  **SWE.1 output is not yet a usable interface.**
    *   Requirement IDs are renumbered on every assembly (`ff/lrtx/swe1.py:508`).
    *   SWE.2 reads SWE.1 by regex (`ff/inspection/swtrace.py:103`, `ff/lrtx/swe2.py:78`).
    *   Two ID patterns disagree with each other.
3.  **SWE.1 quality has no independent measure.**
    *   Gates check structure, and an inspector from the same model family checks meaning.
    *   The Delivery-First CRC example gives the author reviewed reference requirements and oracle C files as inputs
        (`examples/0014g-st-crc-idr-qwen-delivery/workorder.json`, entries 8 and 11–14).
4.  **The factory cannot use different models for different roles.**
    *   One job is pinned to one model (`ff/afo/request_admission.py:49`).
    *   The managed profile is pinned in the systemd units (`ff/afo/services.py:100-110`).
    *   Until CAPA-074, cache keys used the model *name* only.
5.  **Ornith is unproven.** The only evidence is a 36-trial standalone speed study
    ([evidence](../../evidence/014-durable-local-autonomy/ornith-reasoning-speed-20261031/README.md)), with these
    results:
    *   about 150 decode tokens per second;
    *   at best 4/9 full-contract passes.

**Proposed solution:** an opt-in `QM_PROCESS_LAB` order type with three parts:
*   single-role, single-model SWE.1 orders, linked by sealed handoffs;
*   operator-run provisioning and activation tools that reuse the existing AFO and activation patterns;
*   deterministic pre-scoring, completed by owner-signed dispositions.

## Goals

*   **G1 — SWE.1-only, single-role orders.** A lab order runs exactly one role's SWE.1 subgraph and ends with one of
    the terminal reasons listed in §2. No SWE.2–6, finalize or release node exists in its graph.
*   **G2 — Fenced role batches on one GPU.**
    *   The factory serves one lab profile at a time.
    *   The operator switches profiles only at an empty queue with proven quiescence, using a tested activation tool
        that follows the existing activation procedure and compare-and-sets every intent change.
    *   A lab order whose profile is not the resident one is refused before admission.
    *   Every switch writes a timed activation record.
*   **G3 — Identity-correct caching (done, CAPA-074).** The structured packet hash covers:
    *   the selected profile's id and config sha;
    *   the model digest and precision;
    *   the reasoning settings (served, gateway, and the role's own effort);
    *   the probed schema mode and the context tokens.

    It excludes `adapter_revision` (D10).
*   **G4 — Versioned handoff.**
    *   SWE.1 emits `forge-c/process-handoff/1`. It carries stable requirement IDs, source refs, trace edges, the
        group documents, baseline identity and per-requirement inspector outcomes.
    *   The next order rebuilds SWE.1 from the handoff without a model call, after hash checks.
    *   A minimal SWE.2 importer rejects duplicate IDs, dangling trace edges and hash mismatches.
*   **G5 — Independent, honest scoring.**
    *   A deterministic scorer checks hashes, ref resolution, ID integrity and register-effect predicates against a
        frozen per-driver oracle.
    *   An obligation counts as covered only through a satisfied deterministic predicate or an owner-signed
        `process-lab-disposition`.
    *   Inspector verdicts never decide coverage.
    *   An inspector timeout is `NOT_INSPECTED`, never PASS.
*   **G6** — removed by D8.
*   **G7 — No regression.** Strict graphs, `QM_DELIVERY_FIRST_DEMO`, Feature 015 workflows and the CRC smoke keep
    passing. Changes outside the lab:
    *   the one-time G3 checkpoint recompute;
    *   the D7 exception, which applies only to lab orders;
    *   the dead-letter skip, which applies only to successful lab orders;
    *   a refactor of `builder.structured_authors` that leaves its output unchanged (pinned by a golden test).

## Non-Goals

*   **NG1** — No lab for SWE.2–SWE.6; SWE.2 gets an importer only.
*   **NG2** — No model promotion, and no change to existing Qwen profiles.
*   **NG3** — No native run, deployment or grant from this design; CI reports `NATIVE_NOT_RUN`.
*   **NG4** — No new scheduler, database, release authority, autonomous model router or EGM runtime.
*   **NG5** — No ASPICE compliance claim. Lab outputs are QM / ASPICE-inspired and never release-eligible.
*   **NG6** — No change to strict release policy, stored archives, safety policies or historical evidence.
*   **NG7** — Never both models resident, and no parallel inference.
*   **NG8** — No Feature 014 DA ticks. The CLAUDE.md evidence rule applies.
*   **NG9** — No corpus maturity decision, A/B reporter or target-neutral manual handling (D8). Those are
    PF-QUAL-013, PF-BENCH-011 and Q3.
*   **NG10** — LL layer only; `swe1.visit` refuses other layers.
*   **NG11** — No tool-calling Ornith role. The lab uses structured packets only.

## Resolved Decisions (owner, 2026-10-31)

*   **D1′ — Orders.** One order per (driver, role), up to five per driver, linked by hash-checked handoff inputs.
*   **D2 — Swaps.** The operator performs model swaps. AFO never loads or unloads a model by itself.
*   **D3 — Ornith build.** The official `ornith-ai/Ornith-1.5-35B-A3B-GGUF` Q8_0.
    *   GGUF sha256: `de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3`.
    *   Size: 37,802,149,280 bytes.
*   **D4 — Rework limit.** At most two reworks. The order sequence is a prefix of AUTHOR, INSPECT, REWORK, INSPECT,
    REWORK. The second REWORK is not inspected. This supersedes the plan's "exactly one bounded correction"
    (plan §5.2, AT11).
*   **D6 — Arms.** Both arms in the first delivery.
*   **D7 — Purpose.** QM purpose, with a lab-scoped exception in `qm.validate_profile`.
*   **D8 — Scope.** Cut the corpus-decision layer, and keep the frozen experiment-record guard.
*   **D9 / D10 — G3.** A global fix, without `adapter_revision`. Implemented as CAPA-074.

Revision 3 adds no owner decision. Each choice below has a single defensible answer under D1′–D10 and the cited
code. The re-review may challenge any of them.

## Open Questions

*   **Q3 — Unseen corpus case.** Does not block this design (NG9).
*   **Q4 — Oracle and disposition reviewer.** Who reviews each oracle and signs the lab dispositions? This **blocks
    the first scored result**, not implementation. The owner must also add an allowed-signers line for namespace
    `forge-process-lab-disposition`.
*   **Q5 — Ornith thinking setting.** The effort and `thinking_budget_tokens` are fixed in the experiment record
    before the first order. Speed-study results:
    *   default thinking: 4/9, with one trial truncated at 8,192 tokens;
    *   a 2,048-token budget: 2/9 full-contract, 3/9 semantic.
*   **Q6 — Ornith behaviour on the bundled server under these settings.** A bounded protocol test is in progress
    (`evidence/014-durable-local-autonomy/ornith-protocol-20261031/`). Its result feeds §11. Until then it is
    `NATIVE_NOT_RUN`.

## Critical User Journeys (CUJs)

### CUJ 1: The operator runs one experiment

*   **Given**:
    *   An owner window is open.
    *   The owner has signed the per-experiment operator policy (PILOT mode, the lab model keys in
        `engineering.allowed_model_profiles`).
    *   The owner has signed the grants for `submit_workorder`, `recover_workorder` and `launch_workorder`, and the
        `qualification-product-014:<trial sha>` grant.
    *   The experiment record and the oracle hashes are frozen.
    *   `lab-ornith-q8` is resident.
*   **When**: The operator runs `process_lab.provision --role AUTHOR`.
*   **Then**:
    1.  Each driver gets a registered mission, a linked order and a submitted envelope. AFO runs the orders one at a
        time, and each ends `PROCESS_LAB_HANDOFF_SEALED` or with a listed failure reason.
    2.  When the queue is empty, the operator runs `process_lab.next --role INSPECT`, which copies the sealed
        handoffs into the repository's ignored `process-lab/` folder and writes the INSPECT orders.
    3.  The operator runs `process_lab.activate --to lab-qwen38-q8`, then `process_lab.provision --role INSPECT`.
    4.  The operator repeats these steps for each later role.

### CUJ 2: Stop during activation

*   **Given**: `activate` is anywhere between its pause and its final Conductor start.
*   **When**: The owner sets intent STOPPED, or a grant expires.
*   **Then**:
    *   The next re-read of intent and epoch, or the next grant check, fails.
    *   The tool stops the stack if it was started, and records `STOPPED_BY_OPERATOR` or `GRANT_EXPIRED`.
    *   The resume is compare-and-set, so it cannot overwrite the STOP.
    *   No order is affected, because the queue was empty by precondition.

### CUJ 3: Inspector time box, invalid answer or exhausted budget

*   **Given**: An INSPECT order is running.
*   **When**: A question's time box ends, or the question answers invalidly or runs out of repair budget.
*   **Then**:
    *   On a time box, the existing continuation nodes resume the visit. Outcomes recorded so far persist in the lab
        outcome file.
    *   On an invalid answer or exhausted budget, the requirements that question covers are `NOT_INSPECTED`, never
        `NO_FINDING`.
    *   No REWORK is prepared from `NOT_INSPECTED` alone.

### CUJ 4: SWE.2 imports a handoff

*   **Given**: A sealed handoff and its files.
*   **When**: `process_lab.import_swe2` reads them.
*   **Then**:
    *   It lists each requirement as `CONSUMABLE`, `AMBIGUOUS` or `MISSING`.
    *   It rejects duplicate IDs, dangling trace edges and hash mismatches with stable reason codes.
    *   Its output is byte-identical across runs.

### CUJ 5: Model identity changes (done, CAPA-074)

*   **Given**: A cached verdict exists.
*   **When**: Any identity field changes under the same alias.
*   **Then**: The cache misses.

### CUJ 6: Wrong or stale handoff input

*   **Given**: A handoff copy in `process-lab/` that does not match the sealed source.
*   **When**: `process_lab.next`, the intake or the run-time `materialize` node checks it. The possible mismatches
    are:
    *   a changed file;
    *   a different experiment or driver;
    *   different primary sources;
    *   a source order that is not terminal `PROCESS_LAB_HANDOFF_SEALED`.
*   **Then**: The order is refused with a `PROCESS_LAB_HANDOFF_*` reason before any model call.

## Technical Plan (Architecture)

### Components and data flow

```text
 OPERATOR (runbook, model-free tools)                AFO + Fabro (existing engine)
 ------------------------------------                -----------------------------
 experiment.json (frozen) + oracles (outside repo)
 provision --role AUTHOR:
   mission register+link, launch manifest, envelope,
   submit (afo/overnight.provision_order pattern) ─▶ order role=AUTHOR (one model, product_role_trial)
                                                     graph: swe1_author(+continuation) → author_gate → lab_handoff
                                                     terminal BLOCKED/PROCESS_LAB_HANDOFF_SEALED (no dead-letter)
 queue empty
 next --role INSPECT: verify sealed source, copy handoff
   into <repo>/process-lab/<exp>/<driver>/<seq>/ (git-ignored), write example dir
 activate --to lab-qwen38-q8 (activate.py procedure)
 provision --role INSPECT ────────────────────────▶ order role=INSPECT, inputs = handoff copy (sha256)
                                                     graph: materialize → author_gate → swe1_inspector(+continuation)
                                                            → lab_inspect_record → lab_handoff
 next --role REWORK (only drivers with FINDINGS) … activate … provision …
 score (oracle hash ∈ experiment.json) + process-lab-dispositions (owner-signed)
 import_swe2
```

Arm B uses one profile, `lab-qwen38-q8`, for every role and needs no switch.

### 1. Lab order, intake and the in-repository lab folder

**Where lab files live.**
*   Generated lab examples, launch manifests and handoff copies are written to `<repo>/process-lab/<experiment>/`.
    A new `.gitignore` line `/process-lab/` ignores that folder.
*   This satisfies `workorder.prepare`'s rule that inputs live inside the repository (`ff/workorder.py:210-225`) and
    `queue.submit`'s manifest location check (`ff/afo/queue.py:286-288`).
*   Ignored files never appear in `git status --porcelain`, so `factory_revision()` stays clean. So do the porcelain
    checks in `activate`, `qualification_inputs`, `evidence_run` and `inventory`.
*   Because inputs are flattened to `inputs/<basename>` (`workorder.py:216`), every lab file name is unique within an
    order. Handoff files carry the prefix `lab-handoff--`.

**Lab work order** (`<repo>/process-lab/<exp>/<driver>/<seq>/workorder.json`, schema
`forge-c/work-order-spec/0.4`).
*   Copied from the driver's base lab example (§13), with a `process_lab` block (`forge-c/process-lab/1`) that holds:
    *   `experiment_id`, `driver`, `seq` (1–5), `role`, `profile`, `model_profile` (the model key);
    *   for seq ≥ 2, `input_handoff {path, sha256}` (plus `findings {path, sha256}` for REWORK);
    *   `source_order_id`.
*   `delivery_first`, `development_execution_policy` and `provided_requirements` are forbidden.

**Input role allowlist.** A lab order's inputs may carry only these roles. Any other role is refused with
`PROCESS_LAB_INPUT_ROLE_FORBIDDEN`:
*   `datasheet`;
*   any role starting with `reference_manual_`;
*   `conversion_provenance`;
*   `development_guideline`;
*   `process_lab_owner_contract`;
*   `process_lab_device_header`;
*   `process_lab_api_declaration`;
*   `process_lab_handoff`;
*   `process_lab_handoff_file`;
*   `process_lab_findings`.

**Intake checks** (`process_lab.contract`, called beside the delivery-first contract at `workorder.py:406`):
*   the block schema and the role allowlist;
*   for seq ≥ 2, `check_handoff_input`:
    *   the input handoff's sha256 equals the declared value;
    *   every handoff file listed in the handoff matches its sha256;
    *   the handoff's `experiment_id`, `driver` and primary-source hashes equal this order's;
    *   the role sequence is valid.
*   Refusal codes: `PROCESS_LAB_HANDOFF_HASH_MISMATCH`, `PROCESS_LAB_HANDOFF_SCOPE_MISMATCH`,
    `PROCESS_LAB_ROLE_SEQUENCE_INVALID`.

**Holdout check.** `evaluation_holdout` is a launch-manifest argument, written into the workspace manifest after
`prepare` (`workorder.py:838-840`). `process_lab.require_effective(ws)` runs immediately after that write. It refuses
`PROCESS_LAB_HOLDOUT_REQUIRED` unless the effective workspace manifest has `evaluation_holdout: true` and the same
`process_lab` block as the spec.

**Purpose and the D7 exception.** `purpose` comes only from the launch manifest (`runtime.py:141`).
*   The launcher also passes the launch manifest's `process_lab` block to `workorder.run` as the new keyword
    `process_lab`.
*   The call at `workorder.py:732` therefore becomes `qm.validate_profile(purpose, prof, process_lab=...)` before the
    spec is read.
*   After the spec is read (`:763`), `workorder.run` refuses `PROCESS_LAB_LAUNCH_SPEC_MISMATCH` unless
    `spec.process_lab` equals the launch manifest's block.

### 2. Per-role graphs and terminal reasons

`builder._build` is unchanged. The closures `swap`, `pipe` and `continuation` inside `builder.structured_authors`
become module-level helpers with identical output, pinned by a golden test on the strict and Delivery-First example
graphs. Near `builder.py:212`, `builder.build` returns `process_lab.workflow(manifest, env, python)` for a lab
manifest. Like `delivery_first.workflow`, it returns `(dot, nodes)` with role bindings for every node (used by
`binding_for`, `agent_preflight`, `mcp_preflight` and `.forge-run/binding.json`).

| Role | Nodes (in order) | Node roles |
|---|---|---|
| AUTHOR | `swe1_author` + `continuation` → `swe1_author_gate` (existing bounded author rework loop) → `lab_handoff` → exit | author `swe1-author`; gate `swe1-author`; `lab_handoff` `swe1-author` |
| INSPECT | `materialize` → `swe1_author_gate` → `swe1_inspector` + `continuation` → `lab_inspect_record` → `lab_handoff` → exit | `materialize` `swe1-author`; inspector `swe1-inspector`; `lab_inspect_record` / `lab_handoff` `swe1-inspector` |
| REWORK | `materialize` → `swe1_author` (findings, partial) + `continuation` → `swe1_author_gate` → `lab_handoff` → exit | as AUTHOR |

Edge rules:
*   **Inspector to `lab_inspect_record`:** the inspector reaches `lab_inspect_record` on any final reply status. The
    existing statuses are PASS, REWORK and FAILED, and CONTINUE stays in the continuation loop. No new status is
    added.
*   **Gate exhaustion:** when the author gate is exhausted, the graph goes to `lab_handoff`, which writes a handoff
    with `gate_status: FAILED` and the last frozen baseline. The handoff has no baseline if the gate never froze
    one.
*   **Visit limits:** `max_visits` and the timeouts come from the profile's structured settings, as in
    `local_profile_structured` (`workorder.py:658-665`).

**Terminal handling.**
*   `ff/afo/dispatch.py` never calls the recovery planner for lab orders. A terminal Fabro run goes to VALIDATING.
*   `process_lab.verdict(workspace)` then reads the workspace and the attempt state (passed in by `validate`) and
    returns BLOCKED with one of the reasons below. A lab order never becomes `READY_FOR_OFFLINE_REVIEW`.

| Reason | Meaning |
|---|---|
| `PROCESS_LAB_HANDOFF_SEALED` | Handoff written and verified (also with `gate_status: FAILED`). |
| `PROCESS_LAB_MATERIALIZE_REFUSED` | The input handoff failed its run-time recheck. |
| `PROCESS_LAB_RUN_FAILED` | The attempt is FAILED, CANCELLED or UNKNOWN, and there is no handoff. |

**Dead-letter.** `ff/afo/deadletter.sweep` skips orders whose `terminal_reason` is exactly
`PROCESS_LAB_HANDOFF_SEALED`. Every other BLOCKED order, including the lab failure reasons, is dead-lettered as
before.

### 3. Missions, envelopes, launch manifests and admission (`process_lab.provision`)

`process_lab.provision --experiment <experiment.json> --role <ROLE>` follows
`afo/overnight.provision_order` (`ff/afo/overnight.py:21-47`) exactly, with no model call. For each order that `next`
(or, for AUTHOR, the experiment record) lists, it does the following.

1.  **IDs.** `request_id = "pl-" + experiment_id + "-" + driver + "-s" + seq + "-" + role.lower()` and
    `tenant_scope = "process-lab"`. The order id is therefore `afo-` + sha256(`process-lab|<request_id>`)[:16]
    (`queue.py:136`). That ID is known in advance for every possible order, which lets one trial and one grant set
    cover the whole experiment.
2.  **Mission.** One mission per (experiment, driver), `mission_id = "pl-" + experiment_id + "-" + driver`, registered
    with `mission_admin.register` (grant action `recover_workorder`). Its limits:
    *   `max_attempts` 5 (one PRODUCT attempt per order);
    *   the token and request caps from the experiment record (within the policy caps);
    *   `deadline` = the experiment end, capped by `budgets.max_order_wall_seconds` per order as in `overnight`.
3.  **Link.** `MissionLedger.link(mission_id, order_id)`.
4.  **Launch manifest** (`<repo>/process-lab/<exp>/<driver>/<seq>/launch.json`), with these fields:
    *   `example` (the order's folder);
    *   `profile`, `model_profile` (the model key);
    *   `purpose: "QM"`;
    *   `evaluation_holdout: true`;
    *   `process_lab` (the block);
    *   `product_role_trial` (`{path: "afo/product-role-trials/<sha>.json", sha256}`);
    *   `product_attempt_token_reservations: [<per-role reservation>]`.
5.  **Envelope** (`work-order.schema.json`):
    *   `request_id`, `tenant_scope`, `manifest_sha256` (of `launch.json`), `input_manifest_ref`, `approved_by`
        (owner);
    *   `authorization_ref` (the experiment's `submit_workorder` grant);
    *   `driver_class: "process-lab-swe1"`, `target`, `safety_scope`, `model_profile` (the model key),
        `submitted_utc`.
6.  **Submit.** `store.submit(env, repo=REPO_ROOT, max_queued=..., approve=...)`. This needs PILOT or ACTIVE mode
    and a grant check with action `submit_workorder` over `order_ids`, `driver_classes` and `models`. If the
    returned ID differs from the expected one, the tool fails with `PREAPPROVED_ORDER_ID_CHANGED`.

**Product-role trial.** The owner signs one trial document per (arm, profile, model) at experiment start.
*   `provision --prepare-trial` writes the document (`forge-c/product-role-trial/1`, `ff/afo/product_role_trial.py`)
    with these fields:
    *   `qualification_only: true`;
    *   `order_ids`: every possible order ID of that profile in the experiment;
    *   `source_revision` = the factory commit;
    *   `profile`, `profile_sha256`, `model`, `deadline_epoch`;
    *   `roles`: for each role, one identity with the nine `role_capability.IDENTITY` fields. `reasoning` is the
        gateway effort string for that role. `schema_mode` comes from the probe record, and `sampling` from the
        profile. The stepwise inspector's identity uses temperature 0 plus its seed (`review_semantic.py:285-287`).
*   The trial is authorized by a grant whose `signed_runbook_ref` is `qualification-product-014:<trial sha>`
    (`product_role_trial.py:93-99`).
*   The per-experiment policy lists the **model keys** `hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0` and
    `qwen3.8:27b-q8_0` in `engineering.allowed_model_profiles` (`scheduler.py:88`).
*   The repository `config/factory/afo-policy.yaml` is not edited.

**Resident-profile guard.** `scheduler.preflight` reads the launch manifest (`launch_manifest()`, `scheduler.py:39`).
For lab orders only:
*   It adds `RESIDENT_PROFILE_MISMATCH` when `process_lab.profile` differs from `FORGE_OPERATIONS_PROFILE`.
*   It adds `RESIDENT_PROFILE_UNKNOWN` when that variable is unset.
*   `cycle` adds both codes to its BLOCK list (`scheduler.py:213-240`). The operator submits only after activation,
    so a mismatch is an operator error and is refused fail-closed.

### 4. Role batches and the activation tool (`process_lab.activate`)

**Batching.** Batching is done by the operator: `next` then `activate` then `provision` per role (CUJ 1).

**Activation.** `python -m forge_factory.process_lab.activate --experiment <e> --to <profile> --units <file>` turns
the procedure in `evidence/014-durable-local-autonomy/mtp-speed-20261030/activate.py:5-133` into a tested tool.
*   The **unit list file** names the deployed units:
    *   `forge-conductor-local-omniverse2.service`;
    *   `forge-afo-watchdog-014-omniverse2.service` and `.timer`;
    *   `forge-qwen-mission-recorder.service`, when present.

    The file is recorded in the experiment record. Names are not derived from `services.UNITS`.
*   Every step re-reads intent mode and epoch and the experiment grant deadline. Any change ends the tool with the
    stack stopped and an outcome recorded.

1.  **Environment.** Load `state/afo/conductor.env` into the tool's environment.
2.  **`quiet()`** must hold. Otherwise the tool exits with `ACTIVATE_NOT_QUIESCENT` and changes nothing. The four
    conditions are:
    *   `Executions.pending()` is empty;
    *   no `afo_request_ledger` row has a state other than `QUIESCENT`;
    *   no `afo_resource_ownership` holder exists;
    *   no `afo_verification_jobs` row is READY, DISPATCHING, RUNNING or CANCELLING.

    The queue must also hold no QUEUED, ADMITTED, RUNNING, WAITING_RECOVERY, VALIDATING or
    WAITING_EXTERNAL_CHANGE order.
3.  **Pause.** `operations.synchronize(store, 'pause', uid, reason, expected_epoch=E0)`, which gives epoch E1.
4.  **Under `fenced`** (intent lock, epoch E1, mode PAUSED or STOPPED, `quiet()`), in order:
    1.  Stop the listed units.
    2.  `provider_process.stop(serving_instance, fenced_effect=fenced)`.
    3.  Stop Fabro by pid identity (SIGTERM, bounded poll; otherwise `FABRO_NOT_QUIESCENT`).
5.  **Install, under `fenced`:**
    *   Set `services.json` `processes = {}` and remove `serving_instance` and `serving_holder`
        (`stack._save_services`).
    *   Replace the `FORGE_LRTX_PROFILE` value in `conductor.env` and in the listed units, keeping immutable
        before-images.
    *   Set `os.environ` `FORGE_LRTX_PROFILE` and `FORGE_OPERATIONS_PROFILE` to the target.
    *   Write `fabro/settings.toml = stack.fabro_config(stack.settings(target))`.
    *   Run `systemctl --user daemon-reload`.
6.  **Re-exec.** `os.execv` the tool with `--installed`, so no stale module state remains.
7.  **Resume.** `operations.synchronize(store, 'resume', ..., expected_epoch=E1)`, which gives epoch E2. If the epoch
    is wrong, the outcome is `ACTIVATE_EPOCH_CHANGED`, and the stack is left PAUSED with the units stopped.
8.  **Free VRAM.** Free GPU memory must be at least the profile's `runtime.llama_server.vram_required_gb`.
    Otherwise the tool pauses with expected epoch E2 and records `STOPPED_VRAM_UNAVAILABLE`.
9.  **Start the stack.** Run `stack.start(settings, recovery=True)`. The Conductor is still down.
10. **Health and identity.** Poll `stack.status(settings)['health']` for up to 600 s: Fabro, gateway, Ollama and
    llama-server must all be healthy, and `profile.model_identity` must match. The timeout is
    `--health-timeout`, default 600 s, because a 37.8 GB load takes longer than the source script's 120 s.
    *   Health failure: `stack.stop` (managed), pause with expected epoch E2, record `STOPPED_FAILED_LOAD`.
    *   A `stack.stop` that returns an unsettled shutdown is recorded as `STOPPED_SETTLEMENT_PENDING`, and the tool
        exits non-zero for operator attention.
11. **Start the Conductor.** Under the lock: `quiet()`, then start the Conductor unit and the watchdog timer.
12. **Record.** Write `$B/operations/process-lab/<experiment>/activation-<n>.json` (`forge-c/model-swap/1`) with:
    *   from/to profile sha and model digest;
    *   epochs E0, E1, E2;
    *   per-step UTC times and `load_and_control_start_seconds`;
    *   the provider instance;
    *   `model_requests: 0`;
    *   the outcome: `RUNNING`, `ACTIVATE_NOT_QUIESCENT`, `ACTIVATE_EPOCH_CHANGED`, `STOPPED_BY_OPERATOR`,
        `GRANT_EXPIRED`, `STOPPED_VRAM_UNAVAILABLE`, `STOPPED_FAILED_LOAD` or `STOPPED_SETTLEMENT_PENDING`;
    *   the operator, and the reason `PROCESS_LAB_ROLE_BATCH`.

**Rollback.** Rollback is `activate --to <previous profile>`.

**Shared deployment.** Both lab profiles share one `deployment` block (§12), so the queue database, ledgers and
Fabro storage persist across switches.

### 5. Identity-correct caching

Implemented as CAPA-074 (`dc1dd059`): `structured.packet_identity`, `factory/python/tests/test_lrtx_packet_identity.py`
and reproducer RPR-073. The lab adds no further change here.

### 6. Handoff contents, group documents and stable IDs

**Group documents.** `lab_handoff` copies the VALID per-group author documents into the handoff:
*   the `doc` of `.forge-run/lrtx/SWE.1/packets/requirements__<group>.json`;
*   `requirements__crosscutting.json`;
*   the `swr` map from `assembly.json`.

**Rebuild.** `materialize` rebuilds SWE.1 without a model call:
*   It calls `swe1.inventory(ws)` on the order's own (hash-identical) RM inputs.
*   It requires `{g.id for g in swe1.groups(inv)}` to equal the handoff's group IDs; otherwise
    `PROCESS_LAB_MATERIALIZE_REFUSED:GROUPS_CHANGED`.
*   It calls `swe1.assemble(ws, inv, results, cross)`, where `results = [(g, {"task": "requirements:" + g.id, "doc":
    doc})]` and `cross = {"task": "requirements:crosscutting", "doc": doc}`. These are the same task names the author
    path uses (`swe1.py:742`), so `(task, key)` stays stable.
*   It writes through `visit.write_scoped` under the node's binding.
*   It runs `swe1.self_check`.
*   The author gate that follows freezes the baseline.

**Stable IDs.** IDs are keyed by `(task, key)`.
*   AUTHOR assigns `SWR-001…` in assembly order.
*   `materialize` and REWORK reuse the handoff's `ids` map, and append the next unused number for a new key.
*   IDs whose key disappeared move to `retired[]` and are never reused.
*   More than 999 IDs: `SWR_ID_SPACE_EXHAUSTED`.

**Partial REWORK.** In REWORK, `swe1.visit` (lab mode) calls the model only for tasks named in `findings.json`. The
consolidated findings for each task are passed as the `findings` of `visit.run_task`, which is the existing localized
repair path. Every other task keeps its materialized document. The cross-cutting task is re-authored only when it has
findings. If a changed group alters the cross-cutting inputs, the author gate's existing consistency checks catch it.

### 7. Inspector outcome per requirement

In lab mode, `review_semantic` writes outcomes incrementally to `.forge-run/lrtx/SWE.1-inspect/lab-outcomes.json`,
after every question. The file therefore survives `V.Continue`, and on resume it is rebuilt together with the VALID
checkpoints.

**Coverage rule.** Which requirements a question covers:
*   A checklist item (`SWE1-01`…`06`) covers **every** SWR.
*   A stepwise sub-question whose packet names SWR IDs (in `step-*`, `behaviours-*`, `coverage-*`, `effects` or
    `budgets`) covers exactly those SWRs.
*   A sub-question that names none covers every SWR.

**Outcome per SWR,** with precedence `FINDINGS` > `NOT_INSPECTED` > `NO_FINDING`:
*   `FINDINGS`: a claim with decision STANDS targets the SWR, or names it in `related_ids`, and was not WITHDRAWN.
*   `NOT_INSPECTED`: any covering question ended INVALID, `VISIT_CALL_BUDGET_EXHAUSTED`, or was never reached.
*   `NO_FINDING`: every covering question was answered validly, with no standing claim.
*   Claims on `document` or on input paths are listed under a `document` entry, not per SWR.

"Actionable" means at least one `FINDINGS` outcome. The "repair budget" is the existing per-task schema-repair
allowance in `visit.run_task` (2 + 2). `lab_inspect_record` writes `process-lab/SWE.1/findings.json`, with one row
per FINDINGS SWR and these fields: `swr`, `task`, `key`, `claim`, `assertion`, `remediation`. The inspector's reply
status (PASS, REWORK or FAILED) is recorded and routes to `lab_inspect_record` in every case.

**Strict JSON.** Lab profiles set `structured.strict_json: true`. `structured._parse_json` then treats a fenced or
wrapped answer as INVALID (`NOT_JSON:WRAPPED`) instead of accepting `WRAPPED_JSON`. Non-lab profiles are unchanged.
Inspector lessons are off, because lab profiles set `structured.inspection_lessons: false`
(`review_semantic.py:1036-1044`).

### 8. Handoff package `forge-c/process-handoff/1`

The handoff lives at `process-lab/SWE.1/handoff.json` and is immutable once written. Its fields:

*   **Identity:** `schema`, `experiment_id`, `driver`, `order_id`, `seq`, `role`, `process: "SWE.1"`.
*   **`job_identity`:** the packet identity of §5, plus the provider instance.
*   **`baseline`:** the `BL-SWE.1-nnn` id and `baseline_hash`, or null; plus `gate_status` (`PASSED` / `FAILED`).
*   **`inputs[]`:** path, sha256, role. Includes `input_handoff_sha256` when present. The oracle is never listed.
*   **`files[]`:** each handoff file with name (prefix `lab-handoff--`), sha256 and kind. The kinds are `artifact`
    (the four SWE.1 artifacts plus `upstream_gaps.md` and `safety/software_safety_requirements.md`, so a rebuilt
    baseline covers the same paths) and `group` (one per group document, plus the cross-cutting document).
*   **`requirements[]`:** each entry has:
    *   `id`, `task`, `key`;
    *   `statement_sha256`;
    *   `source_refs[]` from the row's `source`;
    *   `source_kind`: `RM` for an RM page reference, `BUDGET` for the work-order budget rows (`swe1.py:430`), `SIM`
        for the simulation rows (`swe1.py:447`);
    *   `criterion` (the `Verification:` line) and `verified_by`;
    *   `inspector_outcome`: `FINDINGS`, `NO_FINDING`, `NOT_INSPECTED` or `UNINSPECTED_ROLE`.
*   **`ids`, `retired[]`.**
*   **`trace[]`:** SWR → test ID edges from `requirements_to_tests.csv`.
*   **`gaps[]`:** `forge-c/advisory-gap/1` refs.
*   **`downstream_constraints[]`:** from `upstream_gaps.md`.
*   **`strict_release_status`:** always `NOT_APPLICABLE_PROCESS_LAB`.

The CRC lab has no owner-scope rows that need an assumption flag. `source_kind` distinguishes the non-RM rows
deterministically, so the scorer can treat them correctly (§9).

### 9. Experiment record, oracle, dispositions and scoring

**Experiment record.** `forge-c/process-lab-experiment/1` lives at `$B/operations/process-lab/<experiment>/experiment.json`
on loop10 and is copied to `$R/operations/process-lab/<experiment>/` on Omniverse2. It is written once, before the
first order, and holds:
*   `experiment_id`, arm, driver list;
*   lab profile shas, model keys and digests;
*   the units file;
*   the oracle sha256 for each driver, with reviewer and review date;
*   the Q5 values;
*   per-role reservations and mission caps;
*   the end time;
*   the scoring thresholds.

**Oracle.** `forge-c/swe1-oracle/1`, one file per driver, stored under `$B/operations/process-lab/oracles/`. That
folder is outside every workspace and outside the repository. Each obligation has:
*   `id`, `critical`, `kind`;
*   `accepted_source_refs[]` (RM pages);
*   an optional deterministic `predicate`: rows of `register/field/op[/value]`, all of which must appear in the
    handoff's `register_effects.json`.

**Lab disposition.** `forge-c/process-lab-disposition/1` is a new runtime schema. The learning-only
`review-disposition` contract is not reused. Fields:
*   `disposition_id`, `experiment_id`, `driver`, `handoff_sha256`, `obligation_id`;
*   `verdict` (`COVERED`, `NOT_COVERED` or `NOT_APPLICABLE`);
*   `covering_ids[]`, `rationale`;
*   `approver`, `decided_utc`, `signature_ref`.

The scorer verifies the signature with `ssh-keygen -Y verify`, namespace `forge-process-lab-disposition`, against
`config/factory/process-lab-allowed-signers`. This reuses the verify routine of `ff/offline/disposition.py:79-101`
with its namespace and signer file as arguments. The owner adds the signer line (Q4).

**Scorer.** `python -m forge_factory.process_lab.score --experiment <e> --handoff <h> --files <dir> --sections <dir> --oracle <o> [--dispositions <dir>] --out <dir>`
is deterministic and makes no model call or network access. `--sections` is the order's `inputs/sections/<manual>`
folder.

1.  It refuses unless the oracle's sha256 is in the experiment record, and `--out` is outside the workspace and the
    repository.
2.  It verifies every handoff file hash.
3.  **Refs.**
    *   Rows with `source_kind: RM` must cite pages that exist in `--sections`. This reuses `swe12.cited_pages`,
        `_pages` and `hardware.index`. A missing page is `UNRESOLVED_REF`.
    *   `BUDGET` and `SIM` rows are checked against the work order's budgets and simulation block, and are excluded
        from the RM-ref criterion.
4.  **Coverage.**
    *   `COVERED_BY_PREDICATE`: the predicate holds **and** a covering requirement cites an accepted page.
    *   `COVERED_BY_DISPOSITION` / `NOT_COVERED_BY_DISPOSITION` / `NOT_APPLICABLE`: a verified disposition bound to
        this handoff's sha256 decides it.
    *   `UNKNOWN_NEEDS_HUMAN`: anything else.
5.  **Judgeable criterion.** The `Verification:` line, lower-cased, must contain a method and an observable.
    *   Methods: `unit test`, `host test`, `target test`, `robot`, `review`, `analysis`, `inspection`.
    *   Observables: the patterns `==`, `returns`, `reads back`, `equals`, `is set`, `is cleared`, `within`, `at most`
        or `at least`, or an `0x…` / decimal literal.
    *   Rows with `verified_by` set count as judgeable when their `Verification:` line has an observable.
6.  **`criteria_result`** per driver:
    *   `MEETS`: no critical obligation is uncovered or `UNKNOWN_NEEDS_HUMAN`; at least 90% of noncritical
        obligations are covered (per driver, deliberately stricter than the plan's corpus-wide wording); no
        `UNRESOLVED_REF`; at least 90% of criteria are judgeable.
    *   `FAILS`: a critical obligation is uncovered, or a threshold is missed even when every unknown counts as
        covered.
    *   `NEEDS_HUMAN`: otherwise.
7.  **Output.** It writes `score-<order>.json` to `--out`.

Every role's handoff is scored, which shows the initial-vs-final difference and rework regressions.

### 10. Minimal SWE.2 importer

`python -m forge_factory.process_lab.import_swe2 --handoff <h> --files <dir> [--score <s>]`:
*   validates the schema and the hashes;
*   rejects with `HANDOFF_DUPLICATE_ID` (checked in code), `HANDOFF_DANGLING_TRACE`, `HANDOFF_HASH_MISMATCH` or
    `HANDOFF_SCHEMA_INVALID`;
*   lists each requirement as:
    *   `AMBIGUOUS`: `NOT_INSPECTED`, or `source_kind` not RM without a budget/simulation match;
    *   `MISSING`: when `--score` is given;
    *   `CONSUMABLE`: otherwise.

Its output uses sorted keys and has no timestamps.

### 11. Ornith serving and the gateway

**Measured so far.** The speed study served the D3 GGUF with the stack's own bundled binary
(`$R/ollama-0.34.0/lib/ollama/llama-server`, `server-instance.json`) with `--jinja --reasoning auto
--reasoning-format deepseek`. It controlled thinking per request with `chat_template_kwargs.enable_thinking` and
`thinking_budget_tokens` (`run_benchmark.py:332`).

**Changes:**
*   **`stack.llama_server_spec`:**
    *   resolves `hf.co/<org>/<repo>:<tag>` manifests under `manifests/hf.co/<org>/<repo>/<tag>`, with the same
        manifest-digest and blob-size checks;
    *   emits `--reasoning-format <runtime.llama_server.reasoning_format>` when that key is present, as well as in
        the existing case (`reasoning_effort` set, value `deepseek`). Existing profiles have neither the key nor a
        change, so their argv is byte-identical.
*   **Gateway thinking budget.**
    *   `gateway.reasoning[model]` gains an optional `thinking_budget_tokens` (int, 1–16384), passed by the stack in
        the existing `FORGE_GATEWAY_REASONING` env (`stack.py:591-605`).
    *   `sanitize_request` adds it to the body only when the effective effort is not `none`.
    *   `enable_thinking` keeps its existing derivation from the effort (`llm_gateway.py:142-148`).
    *   `body.reasoning_effort` stays the effort string. Role-capability admission and the product-role trial
        therefore compare it exactly as today (`role_capability.py:164`, `product_role_trial.py:125`).
    *   The budget is a profile value, so it is bound by the profile config sha in the identity (§5).
    *   The other `sanitize_request(policy=...)` callers (`product_role_trial.py:196`, `durable_agent.py:327,348`)
        pass the same policy object and therefore see the same budget.
*   **Context.** `runtime.ollama.OLLAMA_CONTEXT_LENGTH: 32768`, f16 KV, `vram_required_gb: 46` (37.8 GB of weights
    plus KV and buffers).

**Fixtures.** Recorded-response fixtures cover:
*   template on/off;
*   fenced or wrapped JSON INVALID under `strict_json`;
*   reasoning stripped;
*   `finish_reason: length` INVALID;
*   timeout `OUTCOME_UNKNOWN`;
*   the schema-mode probe keyed by digest.

The Q6 native protocol result replaces any assumption here when it arrives.

### 12. Lab profiles

Profiles are defined as **a copy of a named existing profile plus listed overrides**. Every key not listed stays as
in the base, so no key is left to the implementer.

*   **`local-rtx-v2-omniverse2-lab-qwen38-q8.yaml`:** a copy of `local-rtx-v2-omniverse2-q38-aspice-stepwise-medium.yaml`.
    Overrides:
    *   `id` and `status: EXPERIMENTAL_PROCESS_LAB`;
    *   `work_order_purpose: QM`, `process_lab: true`;
    *   `structured`:
        *   `phases_by_layer.LL: [SWE.1]`;
        *   `inspect_phases_by_layer.LL: [SWE.1]`;
        *   `semantic_inspect_phases: [SWE.1]`;
        *   `inspector_stepwise: true`;
        *   `reinspect_direct: false`;
        *   `strict_json: true`;
        *   `inspection_lessons: false`;
    *   `deployment.default_root: /mnt/data/forge-c/process-lab` and `deployment.ports` = the base ports + 100 (each
        port number plus 100);
    *   `gateway.reasoning["qwen3.8:27b-q8_0"]`: `effort` from the experiment record (author), with `role_efforts`
        for `swe1-inspector` from the experiment record.
    *   No development policy. Everything else, such as `runtime`, `admission`, `network` and
        `existing_deployment`, is inherited.
*   **`local-rtx-v2-omniverse2-lab-ornith-q8.yaml`:** a copy of the Qwen lab profile. Overrides:
    *   `id`;
    *   `models` (`default` and `allowed`): `hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0` with:
        *   `digest` = the sha256 of its Ollama manifest file (read on Omniverse2, read-only, before the file is
            completed);
        *   `quantization: Q8_0`, `role_qualification: EXPERIMENTAL_PROCESS_LAB`, `license: MIT`;
    *   `runtime.llama_server`: `model` = that key, `slots: 1`, no `mtp_draft`, `reasoning: auto`,
        `reasoning_format: deepseek`, `gpu_layers: all`, `vram_required_gb: 46`;
    *   `runtime.ollama.OLLAMA_CONTEXT_LENGTH: "32768"`, `OLLAMA_KV_CACHE_TYPE: f16`;
    *   `gateway.reasoning[<ornith key>]`: `effort` and `thinking_budget_tokens` from the experiment record (Q5);
    *   the same `deployment` block as the Qwen lab profile.

A profile test loads both files and asserts four things: the shared deployment block, the structured keys, that
`llama_server_spec` produces the expected argv, and that the copy-plus-overrides rule holds against the base file.

### 13. CRC lab example and leakage controls

`examples/0020-process-lab-crc/workorder.json` is a copy of the 0014g spec without these keys:
*   `delivery_first`;
*   `development_execution_policy`;
*   `operation_scope.prompt_overrides`.

It keeps:
*   `driver`, `target`, `scope`, `system_names`, `budgets`, `guideline`, `layer: LL`, `peripheral: crc`;
*   `operation_scope` (without `prompt_overrides`);
*   `simulation_performance`.

Inputs, using 0014g's entry numbering (by path, with roles):

| Input | Role |
|---|---|
| 1 datasheet | `datasheet` |
| 2 RM CRC chapter | `reference_manual_crc_chapter` |
| 3 RM memory map | `reference_manual_memory_map` |
| 4 RM register conventions | `reference_manual_register_conventions` |
| 5, 6 conversion manifests | `conversion_provenance` |
| 7 guideline | `development_guideline` |
| 9 `IDR-CONTRACT.md` | `process_lab_owner_contract` |
| 10 `forge_crc_device.h` | `process_lab_device_header` (declarations plus the host fixture instance; no reference answers) |
| 15 `IDR-API.h` | `process_lab_api_declaration` |

Omitted: entry 8 (the reviewed reference requirements) and entries 11–14 (oracle, probe, harness, target oracle).
The four ST input files are git-ignored and must be present locally, verified against `inputs-manifest.json`.

**Leakage tests** refuse:
*   any lab input with a role outside the allowlist;
*   a lab manifest without the holdout;
*   any lab packet, manifest or input list containing an oracle path or hash, a lesson, or a reviewed-requirement
    input.

### 14. CRC vertical smoke

The existing two-function CRC Delivery-First fixture tests keep passing. They are a smoke result, not SWE.1
qualification.

### What stays unchanged

*   The strict graphs and release policies.
*   `QM_DELIVERY_FIRST_DEMO`.
*   The Feature 015 workflows.
*   The existing profiles.
*   The release manager and stored archives.
*   The operations intent semantics.
*   Admission and the mission ledger.
*   `builder._build`.
*   `aspice.validate_profile`.
*   The queue state machine and the attempt schema.
*   The repository AFO policy.

## Alternatives Considered

### Alternative A: One order per driver with five planned attempts (revision 1's D1)

*   **Cons**: It conflicts with the code in several places:
    *   planned attempts bypass `scheduler.preflight`;
    *   `max_concurrent_workorders: 1` and `max_order_attempts: 3` get in the way;
    *   the epoch fence quarantines queued launches (`dispatch.py:84-87`);
    *   resume carries only phases that passed, and refuses a profile change (`workorder.py:494-500`,
        `brownfield/resume.py:314`);
    *   the attempt schema is closed.
*   **Reason for Rejection**: EGM review; the owner chose D1′.

### Alternative B: Keep A and requeue between attempts

*   **Cons**: It changes the shared queue state machine and the attempt schema, and needs a new carry-over rule.
*   **Reason for Rejection**: It changes AFO for every order, which conflicts with G7.

### Alternative C: Swap the model inside one job

*   **Reason for Rejection**: It breaks the one-job-one-model admission invariant. The gateway also shares the
    provider's namespace.

### Alternative D: The Conductor switches profiles unattended

*   **Reason for Rejection**: D2. That would be a new autonomous provider action. Arm A needs at most four switches
    per corpus run, and arm B needs none.

### Alternative E: Both models resident

*   **Reason for Rejection**: The Q8 weights alone exceed 48 GB.

### Alternative F: Score with the inspector or with model votes

*   **Reason for Rejection**: Plan invariant 6, and the recorded false rejections: 5/9 and 2/2 of clean baselines
    (`evidence/014-durable-local-autonomy/stepwise-inspector-20261026/`).

### Alternative G: The AtomicChat build

*   **Reason for Rejection**: D3.

### Alternative H: Universal 64K or 262K context

*   **Reason for Rejection**: Whole-workflow 64K already failed request sizing, and 262K is unmeasured. Context is a
    per-profile, measured setting.

### Alternative I: Call `lrtx.runner` from AFO, outside Fabro

*   **Reason for Rejection**: It loses the Fabro lifecycle, native liveness, admission and accounting.
    `_launcher` also requires a `fabro_run_id`.

### Alternative J: Content-hash requirement IDs

*   **Reason for Rejection**: They change when rework edits the text, and they break `SWR-\d{3}`.

### Alternative K: `lrtx/modelcmp.py` as the lab

*   **Reason for Rejection**: It bypasses AFO. Its load-time measurement is reused in the activation record.

### Alternative L: A new intake input kind that reads handoffs from the state directory

*   **Pros**: No in-repository copies.
*   **Cons**: It changes `workorder.prepare`'s rule that inputs live inside the repository, and the queue's
    manifest-location check, both of which are shared by every order.
*   **Reason for Rejection**: The git-ignored `process-lab/` folder satisfies both checks unchanged, and it is
    invisible to every porcelain cleanliness check.

### Alternative M: Reuse the `review-disposition` contract for coverage

*   **Reason for Rejection**: It is learning-only (`use: LEARNING_SET_ONLY`), and its subjects are GAP/FINDING. It
    cannot express obligation coverage.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Ornith fails under the managed stack (template, flags, health) | Q6 protocol test. The first native step is `activate --to lab-ornith-q8` with no orders. A failed load leaves `STOPPED_FAILED_LOAD` with the stack stopped. |
| 48 GB VRAM exceeded | 32K context, f16 KV, `vram_required_gb` and a free-VRAM check before start. |
| Long model load misread as failure | 600 s health timeout (`--health-timeout`), with load time recorded. |
| A stale serving instance or Fabro config after a switch | `activate` steps 5–6 remove `serving_instance`/`serving_holder`, regenerate `settings.toml` and re-exec. |
| An unsettled shutdown during a failed start | Recorded as `STOPPED_SETTLEMENT_PENDING`, with a non-zero exit for the operator. |
| The operator is unavailable at a switch | Accepted cost of D2: at most 4 switches per arm-A run, each timed. |
| Owner signing load | One policy, one grant set and one trial per (arm, profile) cover the whole experiment, because order IDs are known in advance (§3). |
| Human adjudication load | Predicates decide register obligations. Signed dispositions are needed only for behavioural obligations. Q4 blocks the first scored result only. |
| A wrong or stale handoff link | Hash, scope, source-order and role-sequence checks at `next`, at intake and in `materialize`. |
| Partial REWORK leaves a stale cross-cutting document | The cross-cutting task is re-authored when it has findings, and the author gate's consistency checks run on the reassembled set. |
| Oracle, reference or lesson leakage | Role allowlist, effective-manifest holdout check, `inspection_lessons: false`, oracle folder outside the repository, packet scan test. |
| Successful lab orders flooding the dead-letter queue | Skip only `PROCESS_LAB_HANDOFF_SEALED`. Failures still dead-letter. |
| The builder refactor changes existing graphs | A golden test on the strict and Delivery-First graphs, before and after. |
| Rework degrading correct requirements; uninspected last REWORK | Every handoff is scored and deltas are reported; `UNINSPECTED_ROLE` is explicit. |
| One-time recompute of non-lab checkpoints (G3) | Already accepted (D9/D10, CAPA-074). |
| Rough cost | Up to 5 orders per driver (SWE.1-only, timing measured per order) plus up to 4 switches per arm-A run. |

## Non-Functional Requirements

*   **Security & privacy.**
    *   Oracles, manuals and raw prompts or responses never enter source control or public evidence; `process-lab/`
        is git-ignored.
    *   Reasoning text is discarded.
    *   Dispositions are signed.
*   **Performance (measured, not targeted).**
    *   Per switch: step times and `load_and_control_start_seconds`.
    *   Per order: wall time, requests, tool calls, tokens and VRAM peak.
*   **Rollout & rollback.**
    *   Opt-in through the `process_lab` block and the lab profiles.
    *   Profile rollback is `activate`. Code rollback is reverting the lab commits; G3 is independent.
    *   No database migration.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Paths are relative to the repository root, and tests are under `factory/python/tests/`. Each increment must end with:
*   its tests passing;
*   the regression battery of the Verification Plan passing;
*   for factory code, the CRE path (reproducer or prevention test, CAPA, promotion gate), as for CAPA-074.

### Increment order

1.  The builder refactor (pure, golden-pinned), plus `.gitignore` `/process-lab/`.
2.  Runtime contracts: `process-lab`, `process-handoff`, `swe1-oracle`, `process-lab-experiment`, `model-swap`,
    `process-lab-disposition`.
3.  Lab intake: contract, allowlist, effective holdout, launch-spec match, the D7 exception, `strict_json`.
4.  The AUTHOR graph, `lab_handoff` (with group documents and IDs), the verdict, no recovery, and the dead-letter skip.
5.  `materialize`, the INSPECT graph with per-SWR outcomes and findings, and partial REWORK.
6.  The stack (`hf.co`, `reasoning_format`, `vram_required_gb`), the gateway `thinking_budget_tokens`, the lab
    profiles and the scheduler resident-profile BLOCK.
7.  `provision` (missions, envelopes, launch manifests, trial document), `next`, and `activate` (fixture systemd,
    ledger and intent).
8.  The scorer with lab dispositions, and the SWE.2 importer.
9.  The CRC lab example and the end-to-end synthetic test. Native runs stay `NATIVE_NOT_RUN`.

### Target Files to Create/Modify

#### 1. `ff/workflow/builder.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**:
    *   Move the `swap`, `pipe` and `continuation` closures out of `structured_authors` into module-level functions
        with the same parameters, plus explicit `nodes`/`dot` arguments. Their output stays identical.
    *   In `build`, near line 212, return `process_lab.workflow(manifest, env, python)` when `manifest` has
        `process_lab`.

#### 2. `.gitignore` (Modify)

*   **Proposed Changes**: Add `/process-lab/`.

#### 3. `specs/014-durable-local-autonomy/contracts/runtime/*.schema.json` (Create)

*   **Type / Scope**: JSON Schemas, loaded at runtime by item 4, following the `specs/005` pattern.
*   **Proposed Changes**: Six schemas for §1, §4 step 12, §8 and §9, each with `additionalProperties: false`:
    *   `process-lab`: role enum, seq 1–5, `input_handoff` required when seq ≥ 2, `findings` required for REWORK,
        no oracle field;
    *   `process-handoff`: `requirements[].id` pattern `^SWR-[0-9]{3}$`, `inspector_outcome` enum (§8),
        `source_kind` enum `RM`/`BUDGET`/`SIM`, `strict_release_status` const;
    *   `swe1-oracle`;
    *   `process-lab-experiment`;
    *   `model-swap`: outcome enum (§4);
    *   `process-lab-disposition`: verdict enum.

#### 4. `ff/process_lab/contracts.py` (Create)

*   **Proposed Changes**: `require(name, doc)` loads the six schemas, using the same validator as
    `ff/afo/contracts.py` (Draft 2020-12 with `FormatChecker`, plus a `NAMES` allow-list). On failure it raises
    `PROCESS_LAB_CONTRACT_INVALID:<name>:<path>`.

#### 5. `specs/014-durable-local-autonomy/contracts/validate_contracts.py`, `README.md`, `examples/manifest.json`, `examples/` (Modify)

*   **Proposed Changes**:
    *   The validator also checks `runtime/*.schema.json`. Fixtures are flat files in `examples/` with the prefix
        `process-lab-` (no subfolder, per `validate_contracts.py:78`), and each is registered in
        `examples/manifest.json`.
    *   Each schema gets one valid fixture and two invalid ones.
    *   The README marks `runtime/` as runtime-loaded. The `SPEC_CONTRACTS_ONLY_NOT_RUNTIME` statement stays true
        for the other schemas.

#### 6. `ff/process_lab/__init__.py` (Create)

*   **Proposed Changes**:
    *   `MODE`, `selected(manifest)`, `ROLE_ALLOWLIST`.
    *   `contract(spec)` and `check_handoff_input(spec, example_dir)` for §1, with the refusal codes listed there.
    *   `require_effective(ws, spec)` for the holdout and block match.
    *   `workflow(manifest, env, python) -> (dot, nodes)` for §2.
    *   `verdict(workspace, attempt_state)` for §2.

#### 7. `ff/process_lab/handoff.py` (Create)

*   **Type / Scope**: Python module, plus the command-node CLI (`materialize`, `inspect-record`, `handoff`).
*   **Proposed Changes**:
    *   `write_handoff(ws, role)` for §6 and §8: copies files with the `lab-handoff--` prefix into
        `process-lab/SWE.1/files/` and never overwrites them.
    *   `materialize(ws)` for §6.
    *   `inspect_record(ws)` for §7.

#### 8. `ff/process_lab/ids.py` (Create)

*   **Proposed Changes**: `assign(rows, prior_ids, prior_retired) -> (ids, retired)`, per §6.

#### 9. `ff/process_lab/provision.py`, `ff/process_lab/next.py`, `ff/process_lab/activate.py` (Create)

*   **Type / Scope**: Operator CLIs that make no model calls.
*   **Proposed Changes**:
    *   **`provision`** implements §3. It has two modes:
        *   `--prepare-trial` writes the trial document for owner signature;
        *   `--role <ROLE>` provisions and submits orders.

        Its refusal codes include `OVERNIGHT_INTAKE_NOT_AUTHORIZED:*` (reused), `PREAPPROVED_ORDER_ID_CHANGED` and
        `PROCESS_LAB_EXPERIMENT_MISMATCH`.
    *   **`next`** checks each source order in the queue: it must be terminal with `terminal_reason ==
        PROCESS_LAB_HANDOFF_SEALED`, its workspace comes from `runtime.workspace_of`, and its handoff hashes must
        verify. It then copies the handoff into `process-lab/<exp>/<driver>/<seq>/` and writes `workorder.json`
        with the inputs list. REWORK is written only when there is at least one FINDINGS outcome. It enforces D4's
        sequence and refuses `PROCESS_LAB_SOURCE_NOT_SEALED` and `PROCESS_LAB_SEQUENCE_EXHAUSTED`.
    *   **`activate`** implements §4 steps 1–12, with `--units`, `--health-timeout` and `--installed` (internal). It
        has no `--force`.

#### 10. `ff/process_lab/score.py`, `ff/process_lab/import_swe2.py`, `ff/process_lab/dispositions.py` (Create)

*   **Proposed Changes**:
    *   `score` and `import_swe2` implement §9 and §10.
    *   `dispositions.verify(record, allowed_signers)` calls the signature routine extracted from
        `ff/offline/disposition.py` (item 21), with namespace `forge-process-lab-disposition`.

#### 11. `ff/workorder.py` (Modify)

*   **Proposed Changes**:
    *   `run(..., process_lab=None)`.
    *   At line 732: `qm.validate_profile(purpose, prof, process_lab=process_lab)`.
    *   After the spec is read (line 763): `PROCESS_LAB_LAUNCH_SPEC_MISMATCH`.
    *   In `prepare`: copy `spec["process_lab"]` into the manifest (near line 293), and call `process_lab.contract`
        and `check_handoff_input` (near line 406).
    *   After line 840: `process_lab.require_effective`.

#### 12. `ff/afo/runtime.py` (Modify)

*   **Proposed Changes**: `_launcher` passes `process_lab=manifest.get("process_lab")` to `run`.

#### 13. `ff/afo/dispatch.py`, `ff/afo/scheduler.py`, `ff/afo/deadletter.py` (Modify)

*   **Proposed Changes**:
    *   **`dispatch`:** lab orders (launch manifest has `process_lab`) skip `recover`, and `validate` uses
        `process_lab.verdict(workspace_of(att), att["state"])`.
    *   **`scheduler`:** in `preflight`, the lab resident-profile issues; in `cycle`, both codes on the BLOCK list.
    *   **`deadletter.sweep`:** skips `terminal_reason == "PROCESS_LAB_HANDOFF_SEALED"`.

#### 14. `ff/release/qm.py` (Modify)

*   **Proposed Changes**: `validate_profile(purpose, prof, *, process_lab=None)` implements the exception: only
    `semantic_inspect_phases == ["SWE.1"]`, only when `prof.process_lab is True` and `process_lab` validates.

#### 15. `ff/lrtx/review_semantic.py`, `ff/lrtx/swe1.py`, `ff/lrtx/structured.py` (Modify)

*   **Proposed Changes**:
    *   **`review_semantic`:** lab-mode incremental `lab-outcomes.json` and the coverage rule (§7).
    *   **`swe1`:** lab-mode IDs via `process_lab.ids`, plus the partial REWORK task selection (§6).
    *   **`structured`:** `_parse_json` honours `strict_json` from the selected profile (§7).

#### 16. `ff/lrtx/stack.py`, `ff/llm_gateway.py` (Modify)

*   **Proposed Changes**: Both implement §11:
    *   `stack`: the `hf.co` manifest path, the `reasoning_format` key, the `vram_required_gb` check for
        `process_lab` profiles;
    *   `llm_gateway`: `sanitize_request` adds `thinking_budget_tokens` from the reasoning policy entry when the
        effort is not `none`, and validates it as an int in 1..16384 (`GATEWAY_REASONING_POLICY_INVALID`).

#### 17. `config/factory/profiles/local-rtx-v2-omniverse2-lab-qwen38-q8.yaml`, `...-lab-ornith-q8.yaml` (Create)

*   **Proposed Changes**: Per §12. The Ornith manifest digest is read on Omniverse2, read-only, before the file is
    completed.

#### 18. `config/factory/process-lab-allowed-signers` (Create)

*   **Proposed Changes**: An empty file with a header comment. The owner adds the signer line (Q4).

#### 19. `examples/0020-process-lab-crc/` (Create)

*   **Proposed Changes**: The base AUTHOR spec of §13 and a README. No oracle.

#### 20. `docs/runbooks/process-lab-omniverse2.md` (Create)

*   **Proposed Changes**:
    *   Prerequisites: an owner window; the signed policy, grants, trial and signer line; the Ornith manifest digest;
        the free-storage check.
    *   Writing the experiment record.
    *   First native step: `activate --to lab-ornith-q8` with no orders.
    *   Per-role commands: `next`, `activate`, `provision`.
    *   Scoring and dispositions.
    *   Rollback.
    *   `NATIVE_NOT_RUN` recording.

#### 21. `ff/offline/disposition.py` (Modify)

*   **Proposed Changes**: Extract the `ssh-keygen -Y verify` call (lines 79–101) into
    `verify_signature(record, signature_path, approver, namespace, allowed_signers)`. The existing behaviour is
    unchanged (existing tests).

#### 22. `docs/designs/forge-c-process-first-ornith-qwen.md` (Modify)

*   **Proposed Changes**: Record the re-review result and status.

#### 23. Tests (Create)

Each test is listed with its plan AT, where the meaning matches:

*   **`test_builder_structured_refactor_golden.py` (LAB-T00):** the strict and Delivery-First example graphs are
    identical before and after the refactor (`peripheral_golden.normalized_graph`).
*   **`test_lrtx_stack_hf_manifest.py` (LAB-T02):**
    *   the `hf.co` path resolves;
    *   wrong digest, wrong size or a missing blob are refused;
    *   the argv of existing profiles is byte-identical;
    *   `reasoning_format` is emitted when the key is set;
    *   a lab profile without `vram_required_gb` is refused.
*   **`test_gateway_thinking_budget.py` (LAB-T16a):**
    *   the budget is added only with effort ≠ none;
    *   it is validated;
    *   `reasoning_effort` is unchanged;
    *   trial matching still passes.
*   **`test_process_lab_contract.py` (LAB-T03):** refuses the allowlist roles, `delivery_first`, a missing holdout,
    an oracle key, seq 2 without a handoff, and a launch/spec mismatch.
*   **`test_process_lab_handoff_input.py` (LAB-T04):** hash, scope, source-not-sealed and role-sequence refusals.
*   **`test_qm_process_lab_exception.py` (LAB-T06):** fails before the change, passes after.
*   **`test_process_lab_graph.py` (LAB-T05):**
    *   the node lists and role bindings per role;
    *   continuation nodes are present for the author and the inspector;
    *   no SWE.2–6, finalize or release node.
*   **`test_process_lab_verdict.py` (LAB-T07):**
    *   every reason;
    *   never READY;
    *   no recovery call;
    *   the dead-letter skip applies only to SEALED.
*   **`test_process_lab_provision.py` (LAB-T08):** uses fixture store, policy and grants.
    *   mission registered and linked before submit;
    *   predicted order IDs;
    *   launch manifest fields;
    *   trial document fields;
    *   `MISSION_LINK_REQUIRED` never raised;
    *   model keys in the policy.
*   **`test_process_lab_resident_profile.py` (LAB-T08b):** mismatch and unknown resident profile give BLOCK; non-lab
    orders are unaffected.
*   **`test_process_lab_activate.py` (LAB-T09):** uses fixture ledger, intent, `services.json` and a systemd stub.
    *   every outcome code;
    *   `serving_instance` removed;
    *   `settings.toml` regenerated;
    *   the environment switched and re-exec performed;
    *   expected epochs E0, E1, E2;
    *   health timeout;
    *   no unit started on failure;
    *   the record validates.
*   **`test_process_lab_materialize.py` (LAB-T12a):**
    *   rebuild from the handoff equals the source artifacts;
    *   a groups-changed refusal;
    *   task names `requirements:*`;
    *   no model call.
*   **`test_process_lab_ids.py` (LAB-T10):** stable across REWORK; retired IDs never reused; the 999 limit.
*   **`test_process_lab_inspector_outcome.py` (LAB-T11, AT09):**
    *   the coverage rule;
    *   the precedence;
    *   `lab-outcomes.json` survives `Continue`;
    *   the inspector cannot write the baseline, inputs or handoff.
*   **`test_process_lab_strict_json.py` (LAB-T16b):** wrapped or fenced answers are INVALID under `strict_json`, and
    unchanged otherwise.
*   **`test_process_lab_handoff.py` (LAB-T12):** the field derivations; `source_kind`; no overwrite;
    `UNINSPECTED_ROLE`.
*   **`test_process_lab_rework_partial.py` (LAB-T12b):** only tasks with findings call the model; the cross-cutting
    task is re-authored only with findings.
*   **`test_process_lab_score.py` (LAB-T13, AT10):**
    *   a critical unknown blocks MEETS;
    *   keyword or ref-only coverage refused;
    *   BUDGET/SIM rows excluded from RM refs;
    *   the judgeable grammar;
    *   an oracle not in the record refused;
    *   a signed disposition covers, an unsigned one is refused.
*   **`test_process_lab_import_swe2.py` (LAB-T14, AT12).**
*   **`test_process_lab_isolation.py` (LAB-T15):** the allowlist, holdout and packet scan tests.
*   **`test_process_lab_next.py` (LAB-T17).**
*   **`test_lab_profiles.py` (LAB-T18):** the §12 copy-plus-overrides rule and the shared deployment block.
*   **`test_process_lab_e2e_fixture.py` (LAB-T19, AT15):** AUTHOR, then INSPECT, then REWORK over two drivers.
    *   It reuses the `_scripted` structured fakes (`test_lrtx_swe1.py:79`), the stepwise answers from
        `test_lrtx_v2_review.py`, and `FakeFabro.view` (`test_afo_m3_reconcile.py:18`).
    *   It runs command nodes directly.
    *   It then runs score and import, labelled `NATIVE_NOT_RUN`.

### Verification Plan

*   **Environment:** loop10, `source scripts/forge-env.sh`, `FORGE_DATA_ROOT=$B`, `$B/venv/bin/python`, a fresh
    worktree under `$B/repos/` for each regression run.
*   **Unit:** `$B/venv/bin/python -m pytest factory/python/tests/test_process_lab_*.py factory/python/tests/test_lab_profiles.py factory/python/tests/test_builder_structured_refactor_golden.py factory/python/tests/test_lrtx_stack_hf_manifest.py factory/python/tests/test_gateway_thinking_budget.py factory/python/tests/test_qm_process_lab_exception.py -q`.
    Each negative test is shown failing before its fix.
*   **Regression:** the related-file battery used for CAPA-074 (`evidence/014-durable-local-autonomy/process-lab-g3/`)
    plus `$B/operations/feature014/run_full_inherited.py`. The result must show no failure or error beyond the
    `876d75f` baseline. `test_delivery_first*.py`, the F015 tests and the strict-graph tests must pass unchanged.
*   **Static:** `ruff check`, `python3 tests/spec/validate_design.py`, `validate_contracts.py`, and Feature 014
    `validate_spec.py` (58 tasks, no row changes).
*   **CRE:** a frozen reproducer or prevention test, a CAPA and the promotion gate for each factory-code increment.
*   **Native:** `NATIVE_NOT_RUN`. The first native step needs an owner window and the runbook.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
