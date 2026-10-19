# Feature 005 (AFO): known limitations, SLO observation gap and release evidence (AFO-T074)

This file states what the evidence does **not** show. The readiness levels come from
`forge_factory.afo.readiness.assess()`; a snapshot is in `evidence/afo/readiness.json`.

## Not demonstrated

- **No AFO-launched real model order exists yet** (AFO-T066 BLOCKED: no PILOT authorization).
  - Every AFO decision path is tested with fake Fabro launchers, injected faults and the real-repository maintainer
    drill.
  - The factory yields reported elsewhere (e.g. HAL r161, rc-v1, six phases PASS) come from runs launched outside
    AFO and are not AFO results.
- **No soak, no availability figure.**
  - AFO-M01 is UNKNOWN: the Conductor heartbeat keeps no history, and the 24 h, 72 h and 168 h soaks (AFO-T068) are
    BLOCKED.
  - The soak runner counts only real, contiguous wall-clock time. Elapsed time is never simulated.
- **Restart and reboot drills are deferred** (owner decision 2026-10-19): AFO-T014 PARTIAL; AFO-T015, T034 and T069
  BLOCKED.
  - The data volume mounts only at login, so headless 24/7 operation is not possible until the operator configures
    boot-time mounting (OPERATIONS-AFO.md section 2).
- **The systemd units are rendered and verified but not installed.** The live services still run from
  `scripts/forge_services.sh`.
- **No agent output measured.** The recovery-planner and factory-maintainer agent runs are disabled by policy, so no
  model output of either role has been measured. Their deterministic validators, vetoes and brokers are tested.
- **The Autonomy dashboard view has not been checked in a browser or on a phone by a person** (AFO-T057 PARTIAL).
- **No signed operator readiness review exists** (AFO-T070 BLOCKED). No ACTIVE mode change is requested.

## Design limits (recorded, not hidden)

- The maintainer MCP file-write layer runs as the owner account. It is guarded by canonical-path checks, an
  allowlist, OS read-only bits and the git-diff veto. Candidate code execution runs as the sandbox UID
  `maintainer`.
- Fault-campaign scope (AFO-T065): injected faults on the real Conductor code paths.
  - The shared live Fabro server and gateway are never killed for a test.
  - SQLite disk-full inside the store itself is not simulated; disk-full of the notice log is.
- Escaped-failure rate (AFO-M07) is UNKNOWN: there is no post-release defect source.

## Safety and release evidence

- Packages are offline review candidates only. A BLOCKED archive is a valid terminal outcome, not an accepted
  delivery.
- Nothing here is an ISO 26262 or Automotive SPICE conformance statement, a safety approval or a production
  release.
- The ASIL B safety documents (software safety analysis, tool assurance assessment) are postponed by the owner.
  Current packages are therefore BLOCKED on those two gaps, and no READY package exists.
- **AFO attempt archives.** For a work order launched by AFO, READY and BLOCKED archives carry `operations/afo/`.
  - Contents: order, attempts, recovery plans, checkpoints, lifecycle events, dead-letter cases and service
    context.
  - Each file is hashed in `index.json`, and the bundle never changes the package status.
  - This is tested on synthetic workspaces only: no real AFO-launched archive exists yet.
