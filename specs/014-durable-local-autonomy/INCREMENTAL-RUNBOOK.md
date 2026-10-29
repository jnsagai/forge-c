# Incremental M1 execution entry point

M1 is the input-assisted IDR objective in IMPLEMENTATION-INCREMENTAL-E2E.md.
This runbook and its static tools do not deploy source, grant authority, reserve
inference or submit an order. Use Omniverse2 for all Qwen execution and loop10 for
new local files. Preserve the cloud benchmark terminal and its resources.

## Current source and review boundary — 2026-10-29

Candidatec8daeb1 is local and undeployed. Last confirmed runtime is e098b51.
Omniverse2 is offline by owner confirmation. All actual Qwen execution belongs
there. All former M1/role-trial grants expired29October05:00UTC. Do not infer
authority from the owner's requirements approval.

The original7-requirement IDR input was reviewed28October. The separate
`examples/0014d-st-cube-crc-idr-assisted/proposals/simulation-performance/`
contains the owner-reviewed9-requirement extension:64 instructions/call and
100microseconds Renode virtualtime/call at100MIPS; no physical WCET claim.
Payloadaf48340b…770463 has a real owner review record. Its preview preserves
the historical PENDING banner as immutable review evidence.

The normal import/freeze checks pass and preserve external-assistance provenance.
No inspection PASS is inserted: SWE.1 remains REINSPECT, delivery stays absent.
Run the executable preparation tool in a fresh private directory:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=factory/python \
  python factory/qualification/014/prepare_reviewed_requirements.py \
  --example examples/0014d-st-cube-crc-idr-assisted/proposals/simulation-performance \
  --state-root "$FC014_NEW_PRIVATE_STATE" --work-order WO-IDR-REVIEWED-UNIQUE \
  --out "$FC014_NEW_REPORT"
```

Set FORGE_DATA_ROOT to the pinned ST/manual inputs. On the workstation use loop10
for state, output and TMPDIR. This makes zero inference calls and grants no
admission. Its complete structured-request byte bounds exclude the gateway
reasoning transform and do not substitute for the full live role preflight below.

Local real-tool fixtures exercise compile/analysis/host/Renode/Robot/trace/release,
with explicitly scripted semantic inputs. The generic performance observer
requires actual direct calls to every declared function, pins ELF/source/test/
model/budget evidence and checks sealed raw instruction/time measurements again
at release. Missing, changed or over-budget proof blocks release. This validates
tooling; it does not qualify Qwen, a real product or continuous availability.

See [exact local evidence](../../evidence/014-durable-local-autonomy/m1-local-followup-20261029/README.md).

## Complete role request preflight

Capture or construct the complete candidate request for every actual role/task
context, including role skill, messages/history, evidence, output schema and tool
definitions. Keep full request files private; publish their measurement/hash only.
Do not substitute short smoke prompts for actual engineering contexts.

Use the existing product job record (or a clearly marked preparation draft) and a
JSON array of `{role, body}` entries. Multiple requests for the same role are
retained individually. Run against the exact clean checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=factory/python \
  python -m forge_factory.afo.product_role_trial \
  --workspace "$FC014_WS" --job "$FC014_JOB" \
  --requests "$FC014_REQUESTS" --out "$FC014_PREFLIGHT"
```

This tool derives the role inventory from the existing workflow builder, including
release-manager. Imported SWE.1 authorship can be marked NO_INFERENCE only when
the actual provided-input review/import receipt is valid. Other missing requests
remain NOT_RUN. It applies the same gateway reasoning transformation, measures
the complete serialized body with the existing conservative byte upper bound,
includes the effective output/reasoning cap and calls normal role admission.
It never turns a byte bound into a native tokenizer measurement.

Normal measured capability or a current separately signed finite product-role
trial must match the exact role/model/digest/precision/source/profile/configuration.
A qualification-only static PASS is not measured model competence. Static preflight
does not check all live mission/operator conditions and grants no launch authority.
The gateway rechecks current authorization, cumulative allowance and every actual
request under the existing admission path at execution time.

The historical prepared41a6c28 report on loop10 is NOT_RUN with
`PROVIDED_REQUIREMENTS_REVIEW_MISSING_OR_UNBOUND`; actual live role requests are not
captured. No order or mission was submitted, and no budget was reserved.

## Runtime bindings and execution

Prepare one explicitly prospective IDR objective through the existing signed AFO
intake, product-role-trial and MissionLedger mechanisms. Bind the clean source,
profile hash, exact Q8 model, deadline, finite attempts/jobs/requests/tokens/tools/
corrections, original source/input hashes and operator intent. Obtain current
authority for this distinct objective; do not infer it from an older grant's expiry.
An authorization draft is not an effective grant, and this runbook creates none.

Keep the old `F014-E2E5H-20261028-CRC` mission exhausted:3/3attempts,38requests,
1.9m conservative expenditure and UNKNOWN actual usage. Retain its original
deadline and archives. No renamed order, changed source or new input review
refunds/reset these amounts.

Do not use a standalone workflow launch to bypass AFO. The existing Conductor must
admit the order with its finite mission, current operator epoch, one inference
lease and bounded verification resources. Inspect actual deployed systemd/backend
configuration before activation; prospective source/profile files are not a
deployment. Preserve newer pause/drain/shutdown intent and provider-quiescence
fencing. Stop only this experiment's processes if its own finite scope ends.

For M1, keep general product diagnosis, advisory relaunch and maintenance explicitly
DEFERRED_BY_DEVELOPMENT_POLICY. A reservation is not an executed inference. The
shared initial-plus-one-repair bound survives task/phase re-entry. Current routing
blocks when dependency independence is unproven; a positive, independently verified
provisional-continuation path still needs implementation/qualification (IE-T004).
Unresolved required findings always prevent final acceptance.

After an authorized run, recompute the package through the ordinary finalizer and
archive verifier. Record every phase, native liveness, artifacts/hashes, tool exits,
coverage/fidelity limits, actual usage or UNKNOWN separately from conservative
charges, wall time, repairs, assistance and package gaps. Only an independently
recomputed READY_FOR_OFFLINE_REVIEW satisfies M1. Then attempt M2's three fresh
unassisted requirements-author executions with reference answers withheld, followed
by M3 repair and later broad/learning/availability qualification.


## Resume the same M1 mission after host recovery

1. Reconcile actual operator intent, provider/native liveness and resource leases.
   Do not use a terminal order or offline host as evidence of quiescence.
2. Inspect the real ledger for F014-IDR-M1-HIGH-20261028. Preserve its original
   100m conservative charge, one attempt, six requests and UNKNOWN aggregate
   usage. The old full-CRC3/3 mission is exhausted and remains ineligible.
3. If the existing M1 deadline must change, prepare an explicit time-only request
   from the **current full ledger snapshot**. The operator CLI accepts exactly:

```json
{
  "schema": "forge-c/mission-deadline-extension/1",
  "mission_id": "F014-IDR-M1-HIGH-20261028",
  "snapshot_sha256": "<digest(current MissionLedger.snapshot)>",
  "deadline_epoch": 0,
  "authorization_ref": "<new specifically signed grant id>",
  "request": {
    "order_id": "<prospective envelope request_id>",
    "driver_class": "LL",
    "model": "local-rtx-v2-omniverse2-q38-aspice-mtp"
  },
  "reason": "<explicit finite prospective time window>"
}
```

Replace0 with an actual future finite deadline within the signed grant and
current policy wall limit. Compute the document digest with afo.durable.digest.
A current owner grant must bind the exact active policy, recover_workorder
action, requested scope and
`signed_runbook_ref=mission-deadline-extension-014:<document digest>`.
Ordinary production/role-trial authority alone is insufficient.
No tool signs or renews that grant automatically.

Authenticated state owner only, after review/signing:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=factory/python \
  python -m forge_factory.afo.cli mission-extend-deadline \
  "$FC014_EXTENSION_REQUEST" --reason "Apply the explicitly signed time-only window"
```

The existing AFO database stores a hash-sealed receipt in its decision table;
original mission row and all non-time caps remain unchanged. At most8 explicit
increments are accepted. Stale snapshot, exhausted product allowance, invalid
signature/current scope or held native lease refuses. Replay returns a historical
receipt without restoring execution authority. No order is submitted or resumed.

4. Deploy only with actual current source-bound runtime and role-trial authority.
   Reprepare the reviewed9-requirement example on that exact clean revision;
   run the complete role preflight, including gateway reasoning/output overhead.
5. Submit through the existing serial intake using the SAME mission and an
   explicit continuation_of the old order. Normal Conductor dispatch/accounting/
   inspections/release remain authoritative. No new scheduler or renamed budget.
6. Record real Qwen SWE.1 results before attempting later phases. Stop this job
   and rethink if unchanged failures recur; continue model-free supervision.
   M1 is accepted only after independent six-phase/package evidence. M2–M5 follow
   the existing milestone gates.

Host recovery, current grants, native role qualification and real M1 execution
are NOT_RUN here. This runbook creates no authority or claim of completion.


## Tool-accounting reconciliation before live continuation

Current source charges structured tool calls and standard/semantic inspection
receipts to the same mission cap as native hooks, before handler execution.
It also applies the existing development failed-verification guard. Denial is a
recorded BLOCKED result; no tool or inspection PASS is synthesized.

Historical direct structured calls may have been omitted from that count.
After host recovery, retain original journals/inspection receipts and inspect
the actual ledger. Establish unique operations and provable accounting identity
before any explicit deduplicated backfill; retain UNKNOWN where linkage is
missing. Do not silently reset expenditure or pretend the source fix reconstructed
history. The current M1 token charge remains100m conservative with UNKNOWN
aggregate actual usage. No historical ledger was changed in this local work.
