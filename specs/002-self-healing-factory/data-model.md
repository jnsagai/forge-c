# Entity model and lifecycle contracts

## Entities

| Entity | Primary fields | Notes |
|---|---|---|
| `AgentDefinition` | role_id, skill_path, skill_sha256, allowed_tools, model, token_policy | Immutable per run snapshot |
| `ToolDefinition` | logical_tool, mcp_server, operation, tool_version, required, allowed_roles | Versioned manifest |
| `Run` | run_id, workflow_version, source_baseline, state, phase, started_at, release_archive_id | Fabro source-of-truth for run events |
| `Inspection` | inspection_id, phase, author_role, reviewer_role, baseline_hash, checklist_hash, results, findings | New inspection required after hash change |
| `HealthSample` | sample_id, component, observed_at, status, latency_ms, observed_metrics | Readiness is not proof of correctness |
| `Incident` | incident_id, fingerprint, type, severity, run_id, state, attempts, created_at, updated_at | Persistent state machine, dedup lease |
| `RepairAttempt` | attempt_id, incident_id, agent_skill_sha, patch_hash, tests, promote_result, rollback_ref, tokens | Separate product/infra workspaces |
| `Lesson` | lesson_id, candidate_from_attempt, validation_state, symptom, root_cause, action, constraints, versions, evidence_refs, expires_at | Unapproved lessons quarantined |
| `Event` | event_id, ts_utc, channel, level, run/phase/agent/tool/incident/correlation, msg, payload_ref, redacted | Capture and display policy separate |
| `TokenUsage` | run_id, role, model, input_tokens, output_tokens, total_tokens, counted_vs_estimated, budget, stage | Missing provider count => UNKNOWN |
| `ReleasePackage` | run_id, policy_version, package_status, gaps, manifest_sha256, archive_sha256 | No auto safety approval |

## Incident state machine

```text
DETECTED -> TRIAGED -> REPAIRING -> VERIFYING -> RESOLVED
                       |               |
                       v               v
                  ROLLED_BACK <---------+
                       |
                  (retry budget?) -> TRIAGED / REQUIRES_OFFLINE_ATTENTION
```

- Persist state before dispatch; retries are idempotent on incident+attempt id.
- A success requires test evidence and stable health, not model assertion.
- Terminal incidents are append-only (new incident ID for recurrence, links previous fingerprint).
- Safety protected path violation is `REQUIRES_OFFLINE_ATTENTION` immediately.

## Lesson state machine

`PROPOSED -> QUARANTINED | VALIDATING -> VALIDATED -> RETRACTED | EXPIRED`

- Only `VALIDATED` and not expired can be retrieved across workflows.
- Include invocation-usage references for later impact assessment.
- Do not let lesson text override input baselines/system rules.

## Trace capture and display

`effective_capture = per_channel_capture_policy AND privacy_policy`; `effective_display = authorized_query AND user_selected_filters`; independent operations. Mandatory audit minimum always captured even if user has hidden audit in the dashboard view.

## Relationship sketch

`Run` has many `Inspections`, `Events`, `TokenUsage`, `HealthSamples` and potentially `Incidents`. `Incident` has many `RepairAttempts`; validated repair may yield a `Lesson`, linked to future `Run` usages. `ReleasePackage` snapshots the applicable manifests, tool versions, event segment hashes and incident/lesson status relevant to its own run.
