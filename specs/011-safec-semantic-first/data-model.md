# Data model — Feature 011

**Status:** proposed wire types, not implemented. Authoritative boundary is the pinned Rust SafeC binary; Forge-C parses and verifies the complete JSON envelope, then applies its unchanged SWE gates.

## Trust hierarchy

1. Baselined MCU RM/errata, owner work order, approved safety allocation/policy: authoritative **inputs**. The source must be locally present, complete, hashed and explicitly in scope.
2. Source snapshot and its deterministic parser: trusted only after its own independent parsing, validation and golden/mutation tests. A text extractor can return UNKNOWN rather than invent a field property.
3. Model-proposed `SemanticIntent`: **untrusted hypothesis** referencing facts by exact IDs; it never supplies trusted bit positions, register access or masks.
4. SafeC `ValidatedRegisterContract`: deterministic result after schema, source binding and semantic checks. Trust is bounded by modeled operations, environment and tool evidence.
5. Forge-C `Workproduct`: EARS requirement/effect/trace, generated C, tests and evidence assembled from frozen contracts; acceptance remains with existing gates/independent inspection.

## Entities and invariants

### `SourceSnapshot`

Fields: `source_id`, `kind` (`reference_manual|erratum|workorder|owner_decision|safety_input`), `file_sha256`, `section`, `source_span`, `source_authority`, `effective_scope`, `snapshot_digest`. For parsed RM facts, retain exact section/text provenance and parser version. A source not present in the profile root is an error; a hash mismatch yields STALE; missing human authority does not become machine-approved.

### `RegisterDomain`

Fields: `peripheral_id`, `register_id`, `base_address`, `offset`, `field_id`, `lsb`, `msb`, `access_mode`, `reset_information`, `side_effects`, `support_level`, `source_fact_ids`, `domain_digest`. Width is `msb-lsb+1` with explicit range checks. Reject overlapping field definitions, ambiguous aliases, reserved field writes, unknown access modes, noncanonical numbers and unsafe truncation. No blanket read-modify-write for W1C or special registers.

### `SemanticIntent`

Fields: `intent_id`, `requirement_source_ids`, `target_register`, `target_field`, `action` (`read_field|set_field|clear_field|write_field|write_key_sequence`), `logical_value` (optional exact numeric literal), `preconditions` (source-linked), `open_points`. No candidate masks or encoded offset numbers are trusted from the LLM. Any unlinked claim is denied, not silently normalized.

### `ValidatedRegisterContract`

Fields: `contract_id`, `schema_version`, `domain_sha256`, `source_snapshot_sha256`, `policy_sha256`, `intents`, `validated_operations`, `assumptions`, `unresolved_obligations`, `semantic_digest`. Example: an **illustrative**, already verified 1-bit field at bit 5 with logical value 1 has bit mask 0x20 and encoded register value 0x20, **not** field logical value 0x20. The actual target bit position is obtained only from the validated RM facts. An unsupported side effect prevents relevant PASS.

### `InspectionClaim`

Fields: `claim_id`, `check_id`, `workproduct_baseline_sha256`, `target_id`, `assertion`, `expected_fact_ids`, `observed_evidence_refs`, `severity`, `remediation`, `decision`, `contestation`. Allowed independent decision statuses: `PASS|FAIL|INCONCLUSIVE|UNSUPPORTED`. No finding without exact baseline, criterion and source evidence can enter rework. `PASS` requires complete required check coverage, not merely no findings.

### `SafeCBridgeRequest` and `SafeCBridgeResult`

Wire schemas: `contracts/bridge-request.schema.json`, `contracts/bridge-result.schema.json`. Both are versioned. The request binds expected engine version, binary digest, source snapshot, work order and policy. The result binds to an exact canonical input digest and echoes the engine identity. All identity checks must precede interpretation of any reported result.

`SafeCBridgeResult.status` is one of `PASS|FAIL|INCONCLUSIVE|UNSUPPORTED|STALE|ERROR`. This is a **check** result, never the phase/release status. All non-PASS mandatory responses map to a Forge-C blocking obligation, with provenance retained. `PASS` is admissible evidence **only for the exact supported property set**. `EMPTY`/missing output is ERROR, not PASS.

### `QualificationRecord`

Fields: `host`, `model_name`, `model_digest`, `quantization`, `role`, `catalogue_digest`, `clean_holdouts`, `mutant_results_on_target`, `false_rejections`, `misses`, `inconclusive`, `load_ms`, `tokens`, `wall_s`, `gpu_energy_wh`, `decision` (`NOT_QUALIFIED|CANDIDATE|MEASURED_ELIGIBLE`). An eligible measurement does not self-approve safety authority or waive checks.

## Hash and invalidation map

| Changed element | Mandatory revalidation |
|---|---|
| RM/errata bytes or parser version | SourceSnapshot -> RegisterDomain -> ValidatedContract -> SWE.1..SWE.6 impacted artifacts |
| Owner scope/ASIL/HSI/safety input | Contract applicability -> SWE.1/2 -> impacted inspections/tests -> package |
| SafeC source commit/binary/schema/backend/tool flags | Every dependent bridge result and associated downstream claims |
| Model digest/role/prompt | Authored proposals and related inspector records; **not** original authoritative source facts |
| SWE.1 contract or allocation | SWE.2 interfaces, C/ACSL obligations, independent oracles, regressions, package |
| Candidate C file | Candidate compilation/analysis/tests; independent test oracle input remains frozen |
| Inspection criterion or policy | Re-run affected inspections and gate evaluation; no reuse of cached verdicts |

## Deterministic wire mapping and scope rules

- The Python adapter may serialize requests; SafeC Rust core alone owns validation, canonicalization and semantic lowering for the new profile. Return exact source fact IDs and supported limitations in result artifacts.
- The Forge-C author may propose one or several intents **within a verified finite inventory**. The bridge ignores any model-supplied extra fields, masks, raw address, source digest overrides or claims of approval.
- Cross-cutting startup/reset/timeout/owner safety requirements remain explicit requirements. They cannot be inferred from a register operation or omitted from global completeness checks.
- Existing Fabro role-bound writes, checkpoint freezes, canonical SWE artifacts, inspector records and finalizer stay the source of truth for progress and packaging.
