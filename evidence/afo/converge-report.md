# Feature 005 (AFO): Spec Kit analyze/converge assessment (AFO-T075)

## Method

- Every FR (requirements.csv), acceptance test (acceptance-tests.md) and task (tasks.md, planned-traceability.csv)
  was compared with the code, the tests and the executed evidence.
- Sources: `forge_factory.afo.status.report()` (evidence plus the blocker register),
  `forge_factory.afo.acceptance.report()`, `forge_factory.afo.audit.matrix()` (code checks) and
  `forge_factory.afo.readiness.assess()`.

## Outcome: no new task appended

`tasks.md` was left byte-for-byte unchanged:
- Every remaining gap is already an authored task whose status is BLOCKED or PARTIAL for a recorded, owner-gated
  reason.
- Appending a Convergence phase would duplicate those tasks.
- The owner rule keeps the 005 `tasks.md` checkboxes unchecked; status comes from evidence.

## Findings (all traced to existing tasks)

| Gap | Source | Type | Severity | Existing task(s) | Reason |
|---|---|---|---|---|---|
| Reboot / mount-removal / in-flight reboot drills | FR-012, FR-030, FR-036, FR-070, FR-072 | partial | HIGH | AFO-T015, T034, T069 | owner deferred restart/reboot work (2026-10-19); data volume mounts only at login |
| Install-time restart drills of the other services | FR-009 | partial | MEDIUM | AFO-T014 | same deferral; units not installed |
| Real failed SWE.5/SWE.6 gate not yet observed | FR-046, FR-048 | partial | MEDIUM | AFO-T044 | needs a real run that fails there |
| Autonomy view not checked by a person in a browser or on a phone | FR-061, FR-063 | partial | LOW | AFO-T057 | human visual check |
| Real AFO-launched READY + deliberate BLOCKED pair | FR-067 | partial | HIGH | AFO-T066 | needs a signed PILOT authorization |
| 24 h / 72 h / 168 h soak | FR-069 | partial | MEDIUM | AFO-T068 | operator authorization + boot-time mount |
| Signed operator readiness review | FR-071, FR-072 | missing | HIGH | AFO-T070 | owner signature |

## Constitution and plan checks

- **No MUST principle is violated.** All four are covered by tests:
  - no automatic source deploy, merge or promotion: AFO policy FLOOR, CRE `allowed_auto_deployment` false, broker
    argv guard;
  - no safety or compliance claim;
  - deterministic Conductor without model calls;
  - agents reach only role-scoped MCP operations.
- **Additions not named explicitly in the spec, each justified by a task:**
  - the `staged_manifest` option of the 004 promotion runner (AFO-T048, ADR-AFO-003);
  - the dashboard operator token (AFO-T058);
  - the `maintainer` sandbox UID (AFO-T046).
