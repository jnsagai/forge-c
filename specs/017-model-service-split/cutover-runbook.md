# Cutover runbook: the owner lane becomes the first tenant of the model service (FR-019 stage 2, FR-020)

**Owner only.** Claude prepares and rehearses; it does not execute the cutover, sign anything or edit signed controls.

## Preconditions (all must hold)

1. A qualification report with verdict `QUALIFIED_FOR_OWNER_REVIEW`: every phase in the set has PASS on both sides, with no OPEN blocking finding.
2. The owner's written approval of that report. The cutover record names the report's SHA-256.
3. The owner-lane external-mode change set is ready on a branch and CRE-gated (ELIGIBLE for that exact commit). Today these files are pinned by the owner lane's transport proof (`afo/line_native_transport.py` ADAPTERS):
   - `lrtx/stack.py`: a `model_service` profile block; in external mode no Ollama or llama-server is started, the gateway runs `gateway_external`, and `serve()` returns `BY_SERVICE`.
   - `afo/execution_lifecycle.py` and the launcher/scheduler: the tenant share replaces the GPU lock and inference-owner lease.
4. **The way back has been rehearsed at least once in a window** (SC-006): switching the lane back to its previous signed control and gateway restores today's shape.

## What the owner signs

- A **re-measured transport proof** for the new source hashes, under the owner's signed line control (the same mechanism as today; only the measured ADAPTER hashes change).
- The cutover record: lane, from-shape, to-shape, report SHA-256, approval reference, proof reference, rollback procedure and rehearsal time.

## Steps

1. In the model tier's `tenants.yaml`, enable tenant `forge-owner`: set `enabled: true` with its key hash, and keep the key only in the secrets file.
2. Make the model tier permanent: enable the tenant gateway unit, so it owns the GPU from now on. The qualification window controller is retired.
3. Switch the owner lane's profile to `model_service.mode: external`, pointing at the channel, with its expected identities. Ornith keeps its exact model and settings; only the channel changes.
4. Deploy the CRE-gated owner-lane change set with the signed proof, through the deployer as usual.
5. Watch the first order end to end. The call log must show zero model-server actions by factory components (SC-001), with every call carrying an identity (SC-002).

## The way back

1. Hold admission, the same as at the start of a window.
2. Redeploy the previous owner-lane commit together with its previous signed control and proof, through the deployer.
3. Stop the tenant gateway unit (its stop also stops the engines), then verify that the GPU is free.
4. The owner lane's own model server starts through its normal bootstrap. Lift the hold.

## Not covered

The production lane (`production-local-014`) and the production observer are not part of this cutover. They move only through a separate, owner-approved cutover.
