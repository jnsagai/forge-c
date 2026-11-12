# Cohort observation tooling, not a milestone decision

Tested observer source **e5cdc45ff5983486a32c452ff226d6404245307c**, fileSHA
`c5bf3b9cb7eb4c2a4f7890696da67d746779cbebc70a10005701e489b703ffbd`.
Producer runtime remains0e342eef, external source auditor30371da5, cohort
a14bfe74.../binding8fa0c166... unchanged. The observer is staged only as
E/control/repeatability-20261031-v4b/collect_delivery_trial-e5cdc45f.py;
it was not activated into the factory source or any job.

The script resolves each preregistered order's own actual attempt/job/native/
workspace through read-only AFO SQL. It binds the frozen contract/input hashes,
captures actual native events/usage, candidate/phase hashes and verifier receipts,
and preserves request/execution liveness separately. Terminal observations check
the actual sealed archive and contained final receipt/report entry. Output is an
immutable content-addressed file outside product workspaces. Every observation
remainsREQUIRES_EXTERNAL_AUDIT_NOT_INFERRED. The existing303source CLI and
session observer are still needed; no compilation or Qwen call is performed.

Actual Omniverse checks:

- Live06: captured initial functionalPASS and currentRUNNING native/candidate
  e52e3763...; absent terminal archive stays absent. No milestone inferred.
- Queued07: capturedQUEUED/zero native attempts, not a fabricated result.
- Prior M1order outside this cohort: rejectedORDER_NOT_IN_FROZEN_COHORT.
- Nonlocal API URL: rejectedOBSERVER_API_MUST_BE_LOCAL before credentials/API use.

These four observer-tooling cases are not model-capability tests or additional
functional products, and are not added to the existing95framework-test count.
Full terminal-branch runtime checking is **NOT_RUN** until06actually finishes;
the previous case05 terminal collector remains separately preserved.
Ruff and CLIhelp pass. Initial import-order/line-length lint findings were fixed
before staging, without modifying a product, model, input, grant or runtime.

`native06-observation-ref.json` binds the actual private remote packet. A local
copy onloop10 matches its SHA. The public readable view and deterministic raw
gzip preserve that snapshot; it may already be older than current pipeline
progress. `integration-controls.json` retains exact refusal outputs.

Run on the host with E/venv/bin/python, --instance-rootE, --cohort-root
E/control/repeatability-20261031-v4b/repeatability-prepared-20261031-v4b and the
actual --order-id; see the existing qualificationREADME for full syntax.
E is `/mnt/data/forge-c/delivery-first-afo-014-20261030-v1`.
All3results remain in the denominator, expiry07:57:59UTC. No source hotpatch,
new scheduler, grant renewal, task closure, repeatability or availability claim.
