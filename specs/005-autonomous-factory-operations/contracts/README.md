# AFO typed contracts — specification-only

All JSON files ending `.schema.json` are **JSON Schema Draft 2020-12**, with unknown top-level fields rejected unless documented. No schema implies production runtime is available. Implementers must validate with `jsonschema.Draft202012Validator` (and FormatChecker when using `format`), and use deterministic server-side semantics in addition to syntactic validation.

| Contract | Consumer / action |
|---|---|
| `afo-policy.schema.json` + `.example.yaml` | AFO mode, budgets, external authorization and non-weakening invariants; OBSERVE_ONLY by default |
| `work-order.schema.json` | Approved immutable owner inputs and deduplication |
| `attempt.schema.json` | Unique work attempt and Fabro receipt |
| `outbox-command.schema.json` | Transactional launch/recovery/finalizer intent and fencing |
| `queue-event.schema.json` | Append-only correlated event, redacted provenance |
| `failure-bundle.schema.json` | Gate-derived signed/sanitized bounded failure context |
| `recovery-plan.schema.json` | Planner PROPOSAL only; not execution authority |
| `maintenance-proposal.schema.json` | Candidate PR and independent CRE promotion record, `auto_deployment_allowed=false` |
| `dead-letter.schema.json` | Terminal BLOCKED support case and required operator action |
| `authorization.schema.json` | Externally signed owner permission; this contract alone is not proof of signature validity |
| `operational-readiness.schema.json` | Report readiness/status separately from configured mode |
| `queue-fsm.yaml`, `failure-taxonomy.yaml` | State/transition and incident domain catalogues |
| `control-api.openapi.yaml` | Minimal versioned read-only APIs + authenticated operator writes (not agent MCP) |

**Important:** JSON Schema validates shape only. Verify external approval signatures and validity/expiry, input file content hashes, monotonic lease epochs, stage hashes, release gates, and no privilege escalation *in the deterministic implementation*. In particular, merely providing an `approved_by` string is not an approval. Schema samples in `examples/` are synthetic and never represent a real authorization to operate.
