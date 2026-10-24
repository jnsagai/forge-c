# Feature 013 — Connect local autonomous recovery to production

The owner reaffirmed on 2026-10-24 that the factory must be fully local and
autonomous with self-healing. This completes production integration gaps in
Feature 005; its authored requirements remain authoritative.

The q36c operator retry controller stopped after three BLOCKED attempts. Production
AFO did not supply its existing planner to recovery. Admission used a fixed
gateway port, local model switching was absent, agent tool authorization did not
load the AFO overlay, case/source data was truncated through 120-character issue
fields, and strategy details did not reach the new author attempt. Maintainer
preparation existed, but its agent and independent verifier required manual calls.

## Acceptance requirements

- LA-001: Wire the signed, enabled local planner into production recovery after
  deterministic rules. Keep inference and long candidate evaluation outside the
  model-free Conductor cycle. (AFO-FR-037..041, 049..054)
- LA-002: Use the selected local profile, pinned served-model identity, local
  namespace/gateway and role SKILL/MCP grants; no paid or cloud fallback.
  (AFO-FR-007, 016, 041, 048)
- LA-003: Persist one budgeted job per role/attempt before launch, adopt native
  receipts by nonce, refuse ambiguous repetition, retain uncertainty and react
  to revocation/deadlines. (AFO-FR-027..030, 044..046)
- LA-004: Independently validate plans for the exact failure and carry the scoped
  strategy into the new author attempt without changing inspectors or exposing
  downstream code to SWE.1. Preserve native gates and brownfield resume checks.
  (AFO-FR-031..035, 042, 043, 047)
- LA-005: Carry bounded case/source data through paged MCP payloads, with hashes
  and explicit continuation; never silently use truncated diagnostic fields as
  engineering input. (AFO-FR-037, 041, 050)
- LA-006: For enabled factory-source proposals, dispatch the isolated Maintainer
  and independent existing reproducer/CAPA/CRE/broker path without source merge
  or deployment. (AFO-FR-049..057)
- LA-007: Supply a reviewable local activation configuration while preserving
  signature, policy-floor and external source-deployment requirements. Do not
  activate or claim a live autonomous run without the actual owner authorization.
- LA-008: Use spare host CPU/RAM for bounded independent verification jobs, retaining
  every case, its oracle and deterministic result order. Leave capacity for Qwen;
  do not change model accuracy, phase dependencies or quality thresholds.
- LA-009: Provide tested namespace confinement on the remote host without Podman,
  preserving credential/source/network protection before any candidate execution.

The owner explicitly approved activation and the signing record later in this
session. The existing SSH agent can sign via its public-key reference; no private
key material is read. The current `q36-n2` run is preserved during enrollment.

No safety, supervisor, release or reliability policy, frozen oracle, holdout or
historical release evidence is changed. Verification is CPU-only; the owner's
restriction on additional competing GPU tests remains in force.
