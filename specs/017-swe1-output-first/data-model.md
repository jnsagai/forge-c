# SWE.1 data model

These are design contracts for implementation, not claims that runtime schemas already exist. Implement versioned schemas and tests in the repository's existing schema mechanism. Keep the model's output projection smaller than the stored envelope.

## 1. Evidence and decisions

`EvidenceRef`: stable source ID, source hash/version, section/span locator, fact IDs and provenance kind (`normative_source`, `interface_contract`, `implementation_observation`, `engineering_decision`). A reference must resolve within the input manifest. Citation existence alone does not prove the claim follows from it; semantic review checks that relationship.

`Decision`: ID, subject, alternatives/selected policy in concise structured form, evidence refs, authority/status and dependency hash. An author proposal is not automatically an accepted owner or engineering decision. A frozen implementation observation is not automatically a normative requirement.

## 2. Coverage obligation

Factory-managed envelope:

- `id`, `revision`, `scope_hash` and evidence refs;
- `behavior_id`, capability category and applicable domain/state/value combinations;
- explicit exclusions/exceptions with evidence and dispositions;
- `status`: `UNRESOLVED`, `REQUIRED`, `COVERED`, `EXCLUDED_JUSTIFIED`;
- satisfying contract IDs and review record.

Do not blindly materialize a Cartesian product. Use symbolic domains and explicit expansion only where useful; verify supported combinations and exceptions. Empty domains or an exclusion chosen merely to pass validation are findings. Mandatory unresolved obligations block phase acceptance. Exclusions require the work-order policy's disposition authority.

## 3. Requirement contract

Factory-managed fields: `schema_version`, `id`, `revision`, `behavior_id`, obligation IDs, source/scope/policy hashes, status, review/validation references, creation/update events. IDs are assigned by the factory and survive rewording. A semantic split or merge records lineage.

Model-authored semantic fields:

| Field | Meaning |
|---|---|
| `applicability` | Explicit supported instances/configurations and exceptions |
| `inputs` | Names, types where known, supported domains and combinations |
| `preconditions` | Caller/environment obligations, each traceable |
| `trigger` | Call, event, interrupt or condition |
| `response` | Observable result and state/effect changes |
| `preservation` | Resources or properties required to remain unchanged |
| `constraints` | Applicable timing, ordering, concurrency and resource constraints |
| `failure_behavior` | Supported error/exception paths, domains and observations |
| `verification_criteria` | Initial conditions, stimulus, expected observation and pass/fail criteria |
| `evidence_refs` | Claim-to-evidence/decision mappings |
| `open_issues` | Unresolved decisions/conflicts with affected obligations |

Fields already known from the source adapter are supplied, not regenerated. Task-specific schemas expose only fields the model must decide. Optional concerns use `applicable`, `not_applicable` with justification/evidence, or `unresolved`; omission does not imply not applicable. A generic response may describe buffers, callbacks, messages or state, not necessarily registers.

Use structured EARS components (`pattern`, `condition`, `trigger`, `subject_ref`, `response`) for rendering. The renderer adds grammar, IDs and punctuation, not new engineering meaning. Unsupported or ambiguous compositions return a structured finding. Required atomicity is checked semantically; splitting clauses must preserve conjunctions, conditions and provenance.

For a source-supported register capability, typed effects may contain resource/field IDs, operation and logical value. Bit positions/masks come from a validated source adapter, not free text. A redundant field prefix is canonicalized only when it matches its resource and resolves uniquely. Other capabilities use their own typed effect extensions behind the same core.

## 4. Findings and patches

`Finding`: `id`, stable `code`, severity, target contract/obligation ID, field path, concise defect, evidence refs and expected correction. Classification distinguishes `REPRESENTATION_ERROR`, `MISSING_COVERAGE`, `SOURCE_GAP`, `SOURCE_CONFLICT`, `CONTRACT_CONFLICT`, `IMPLEMENTATION_MISMATCH`, `REPAIR_REGRESSION`, `VERIFICATION_GAP`, `INFRASTRUCTURE_ERROR`, `RESOURCE_EXHAUSTED` and `NO_PROGRESS`.

`Patch`: base contract revision/hash, target finding IDs, permitted field paths and replacement/addition operations. Reapply all affected validators and aggregate obligations before atomic commit. Reject stale bases, deletion of mandatory coverage, unrelated changes and introduced contradictions. Deterministic normalization also records a patch event.

Progress compares newly satisfied reviewed obligations, resolved substantive findings and preserved accepted contracts. More text, fewer array entries or an empty finding list alone are not progress. Fingerprint findings by semantic target/code; a newly generated wording cannot reset retry limits.

## 5. State and acceptance

Contract states: `DRAFT`, `STRUCTURALLY_VALID`, `SEMANTICALLY_REVIEWED`, `ACCEPTED`, `BLOCKED`, `STALE`. ACCEPTED means accepted within this work-order engineering policy, not externally approved or certified. A failed repair preserves the previous version but records that the open finding still blocks the affected acceptance.

Phase states: `RUNNING`, `BLOCKED`, `PHASE_ACCEPTED`, `CANCELLED`. Phase acceptance requires complete required coverage, no blocking open issues, aggregate consistency, valid reviews and artifact integrity. Externally reported package status remains governed by the existing phase-scoped finalizer.

Dependencies include source/scope hashes, shared decisions, capability schema, renderer/validator versions and inspection policy. Invalidation propagates only along affected edges, then aggregate checks rerun. Cancellation does not imply successful inspection or acceptance.

## 6. Capability record and call ledger

Capability key: model digest + quantization + backend version + chat template hash + gateway revision + effective profile hash + role. Record requested control, translated request fields, observed behavior and evidence method. Result: `SUPPORTED_VERIFIED`, `UNSUPPORTED`, `UNVERIFIED` or `NATIVE_NOT_RUN`. A numeric zero reported by a parser is insufficient proof if the parser might be dropping reasoning.

Ledger events: `CALL_STARTED`, `RESPONSE_RECEIVED`, `CALL_FINISHED`, `CALL_FAILED`, `CALL_CANCEL_REQUESTED`, `CALL_CANCEL_CONFIRMED`, `CALL_INTERRUPTED_UNKNOWN`. Each has event ID, call ID, attempt/parent/task/run IDs, timestamps, profile/model identity and relevant outcome. Recovery reconciles unfinished calls without inventing usage or rerunning blindly. Durable append and idempotent aggregation must survive duplicate events and interrupted writes.

Usage fields: prompt tokens, cache-read tokens, total completion tokens, reasoning tokens, answer tokens, measurement basis and nullable values. Keep reported counters distinct from estimates and counter semantics. Do not add reasoning tokens twice when already included in completion tokens. Aggregate call duration separately from elapsed campaign duration, loading, queue and retries. No chain-of-thought contents are stored.

## 7. SWE.1 outputs

Adapt accepted contracts into existing software requirements and traceability formats, plus coverage, issues and inspection reports. Verification links may identify planned obligations or methods; they must not assert a test passed or that a SWE.6 artifact exists. Preserve upstream requirement relationships and source provenance. Reports label unknown measurements and unexecuted work explicitly.
