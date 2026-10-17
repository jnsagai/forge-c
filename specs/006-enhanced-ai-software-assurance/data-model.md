# Data Model — Feature 006

All new records are immutable/revisioned and bound to existing work-order ID, run ID, artifact SHA and factory commit. Migrations shall be additive and idempotent. Reuse existing SQLite event ledger whenever possible; do not create competing schemas/sources-of-truth.

| Entity | Key fields / reference | Persistence rule |
|---|---|---|
| ProductSafetyScope | `scope_id`, `work_order_id`, `target_asil` (`QM/A/B/C/D`), `source_requirements_hash`, `hsi_hash`, `allocation_review_ref` | Approved inputs read-only; changing ASIL requires external authorization |
| AssurancePolicy | `profile`, `edition`, `catalog_digest`, `methods`, `limits`, `authorization`, `policy_sha` | Versioned, fail closed; starts OBSERVE_ONLY |
| NormMethod | `method_id`, `table`,`row`, A/B/C/D recommendation, `source_status`, `normative_checked` | Working-index vs authorized norm separated |
| MethodApplicability | `work_order_id`, `method_id`,`decision`,`reason`,`alternative_ref`,`owner_ref` | No implicit auto-waiver; record applicability decision |
| OracleRecord | `oracle_id`,`requirement_ids`,`source_hashes`,`author_role`,`implementation_hash_seen`,`holdout_digest`,`contamination` | Expected result derived independently and cryptographically frozen |
| VerificationExecution | `run_id`,`tool`,`version`,`args_digest`,`returncode`,`environment`,`stdout_digest`,`stderr_digest`,`measurements` | Only actual executed evidence supports tool PASS |
| CoverageRecord | instrumented source SHA, kind, executable SHA, measured counts, uncovered IDs, justifications | Distinguish branch/statement/MC/DC and support truth status |
| MutationCampaign | operator set, target code SHA, eligible/invalid/equivalent/killed/survived, result refs, campaign SHA | Never infer success from one aggregate score |
| HardwareEvidence | class `HOST/RENODE/EMU/HIL/PHYSICAL`, target MCU, model metadata, assumptions, observed peripherals | No environment escalation |
| AssuranceClaim | claim ID, objective, scope, argument nodes, evidence IDs, counterevidence, state | Claims may be SUPPORTED/CONTESTED/UNSUPPORTED/UNKNOWN |
| GateDecision | phase, profile, input refs/hashes, method decisions, claims, independent reviewer, raw evidence, disposition | Hard fail closes gate; preserve original attempt |
| AssurancePackage | sealed package hash, report/manifest hashes, limitations, missing evidence | READY_FOR_OFFLINE_REVIEW/BLOCKED only |

### Independence model

Trust is a graph: `requirements -> oracle -> test -> raw execution -> verdict`. If a test oracle depends on the implementation being judged or shares author-controlled expected values, mark `CONTAMINATED` and disallow independent-test proof. Different agent identities alone do not remove shared LLM model/provider/common-source failure risk.

### Schema migrations

Follow existing CRE idempotent migration strategy, use a single transaction per journal append and audit schema version. Replays have stable event ID; changes to evidence must create new revision and linked supersession, not rewrite rows. First-pass outcomes remain original. Backups/restore must reconstruct equivalent projections.
