# LRTX-T025 — deployment preserved, rollback planned, results packaged for offline review

## Host check

**Host check (`LRTX-T025-HOSTCHECK`, re-run 2026-10-21 22:01 UTC on factory pd-414b3233): PASS.** It compares the host
with the T003 snapshot:
- **Deployment checkout:** `~/forge-c` at 86f1f40 is unchanged and clean.
- **Configs:** the non-secret configuration hashes are unchanged.
- **Archives:** all 208 preserved review archives are present with their original SHA-256.
- **Profile state:** no profile work order, archive or meter is in the deployment's state.
- **Services:** the deployment's Ollama (same model digests) and Fabro answer on their own ports.
- **Network:** from inside the profile namespace, external network access is refused (DENIED_VERIFIED).
- **Rollback plan (dry run, nothing deleted):**
  1. Stop the profile stack by recorded PID, including the API relay.
  2. Remove the 16 profile run worktrees. They are selected by content since pd-414b3233.
  3. Remove the profile root.
  4. Remove the `forge-c-lrtx` source from the 8787 monitor.

  No removal lies inside, or contains, a deployment root.

## Offline review bundle

`$FORGE_LRTX_ROOT/archives/review-bundles/forge-c-feature-010-review-32b59c783c33.zip`
- sha256 `850d7c92666e8ad5b89784fa9d33ecf4d97a1315cea8b2bc590ebc35919855d5` (sidecar `.zip.sha256`).
- Built from the committed revision 32b59c783c33. It contains 393 files:
  - the spec, plan, tasks and validation record;
  - ADR-0013/0014, the start guide and the profile;
  - every LRTX evidence run;
  - the CRE decisions cited in the validation record.
- The manifest copies each task's tick state and the status of the evidence its tick cites. T001/T002 were ticked at
  spec time and cite `baseline.json` and the branch references (NO_EVIDENCE_RUN).
- The bundle predates this record and the T025 tick, so it shows T025 and T024 unticked.

Verification (`20261021T220920.*`, evidence_run PASS):
- the sidecar checksum and the zip integrity;
- the manifest names 32b59c783c33 and OFFLINE_REVIEW_CANDIDATE;
- a rebuild from the same revision is byte-identical;
- the host check record is PASS without rollback conflicts.

## Status

The bundle is an offline review candidate, not a release:
- Nothing was promoted, merged or deployed.
- PR #34 is merged only after the owner accepts it.
- No compliance, qualification or safety approval is claimed.
- T024 (the 30-case campaign) is NOT_RUN on owner hold, and the bundle says so.
