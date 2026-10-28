# Incremental M1 execution entry point

M1 is the input-assisted IDR objective in IMPLEMENTATION-INCREMENTAL-E2E.md.
This runbook and its static tools do not deploy source, grant authority, reserve
inference or submit an order. Use Omniverse2 for all Qwen execution and loop10 for
new local files. Preserve the cloud benchmark terminal and its resources.

## Prepared source and checks

- Runtime source41a6c28 is prospective, not deployed. Production remainsfcb15cb.
- Example: `examples/0014d-st-cube-crc-idr-assisted/`, two original ST functions,
  FROZEN; source-backed candidate requirements remain REVIEW_PENDING.
- Selected prospective profile: `local-rtx-v2-omniverse2-q38-aspice-mtp`,v2,
  Qwen3.8-27B Q8_0/xhigh/MTP3, one slot,65536 context, f16 KV, no empty-reply retries.
- Independent tool fixture: real six-phase build/host/integration/Renode/Robot/
  release; scripted semantic artifacts/review explicitly disclosed.
- Latest native qualification source7a4bc51:169PASS,0skips,0Qwen calls.
- Actual backend/MCP smoke atd3f0b28 passed two requests. It does not qualify every
  role or permit inheriting a capability receipt across adapter revisions.

See the [exact evidence](../../evidence/014-durable-local-autonomy/incremental-e2e-20261028/README.md).

## Requirements review boundary

The supplied candidate specifies write/read of all32 IDR bits, no autonomous driver
write before explicit calls, no status polling, and4096/64/128-byte flash/static
RAM/stack budgets. Caller owns a valid accessible instance and its clock/power/
security setup. No invalid-pointer behavior, safe state or error return is invented.

The owner-review question is pending. Keep `review.status=PENDING` until an actual
review arrives. Then record the actual reviewer/date/session reference and digest
of `provided_requirements.payload(document)`. Do not sign a safety approval,
attribute review to an agent or use the test's synthetic reviewer in live input.
Commit the reviewed bundle and reprepare at the selected clean revision; old
prepared manifests are not launch permissions after source/binding changes.

Normal `provided_requirements.materialize` runs structural/semantic/primary-input
checks and writes an external-assistance receipt. It does not forge a Qwen author
or inspector outcome. Normal SWE.1 inspection remains required.

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

The prepared41a6c28 report on loop10 is NOT_RUN with
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
