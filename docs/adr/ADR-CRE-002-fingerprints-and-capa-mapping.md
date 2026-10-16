# ADR-CRE-002: Failure taxonomy, fingerprint v1, collision handling and CAPA mapping

Status: accepted (2026-10-16) · Tasks: CRE-T007, CRE-T008, CRE-T009, CRE-T017

## Classes and categories
`failure_class` (spec CRE-FR-003, five values) is the routing key; `category` keeps the finer engineering view the
owner asked for. A class is assigned by deterministic rules on issue codes, never from a symptom alone:

| failure_class | categories | route |
|---|---|---|
| INFRASTRUCTURE | INFRASTRUCTURE, WORKFLOW_ORCHESTRATION, MCP_TOOL (server down/handshake), RESOURCE_BUDGET | repair-eligible (002 supervisor) when repairable, else offline attention |
| TRANSIENT_DEPENDENCY | TRANSIENT_ENVIRONMENT (timeout, 429, dropped upstream answer) | bounded retry (idempotent operations only) |
| PRODUCT_QUALITY | PRODUCT_ENGINEERING (build/test/analysis), REQUIREMENTS_SPEC, AGENT_OUTPUT (format, turn budget, bent test) | SWE author/inspector rework — never infrastructure repair (AT-004) |
| POLICY_SECURITY | POLICY_SECURITY (denied tool, protected path, Robot policy) | fail closed, offline attention |
| UNKNOWN | UNKNOWN | no automatic action, offline attention |

## Fingerprint v1
`cfp1-` + SHA-256 of the canonical JSON of
`{algorithm: "cfp-v1", failure_class, source_component, error_code, normalized_operation, tool_major_version,
contract_schema_version, environment_family}`.
Normalization removes timestamps, run/work-order IDs, defect IDs, hashes, digits in counters, absolute and
workspace paths (file *names* kept), and free log text. `error_code` is the issue code up to its first variable part
(e.g. `REQUIRED_TOOL_NOT_PASS:run_unit`, `TEST_CHANGED_AFTER_FAIL`, `TURN_BUDGET_EXHAUSTED`).
Root-cause hypotheses never enter the fingerprint.

## Collisions, splits and merges
Never automatic. `cre_fingerprint_aliases` records an audited mapping (`from`, `to`, `kind` MERGE|SPLIT, reason,
actor, time); original fingerprints stay on every observation. Distinct error codes or components are distinct
fingerprints (AT-005).

## CAPA mapping
A CAPA links 1..n fingerprints (and their incidents/work orders). Opening policy (deterministic): a fingerprint
observed in ≥ 2 distinct work orders, or in ≥ 1 BLOCKED outcome, is *significant*; CAPA records are opened for
significant fingerprints in OBSERVE_ONLY as records only (no action).
