# Proposed contracts — Feature 014

Status: **PARTIALLY_IMPLEMENTED / QUALIFICATION_INCOMPLETE**. These authored contracts have runtime consumers; current scoped evidence is tracked in ../validation.md. Passing their validator proves schema/fixture consistency only. It does not run Qwen, Fabro, MCP, recovery code or any production service.

## Interfaces and trust boundary

| File | Producer | Consumer and meaning |
|---|---|---|
| `semantic-proposal.schema.json` | Scoped Qwen role | Broker validates a small engineering decision. No administrative IDs, budgets, authority claims or execution flags are accepted from the model. Case/job identity is supplied by authenticated tool context. |
| `completion-receipt.schema.json` | Deterministic broker/controller | Immutable receipt revision separating storage, admissibility and repair execution. A stored proposal cannot launch work; accepted CLOSE_BLOCKED is not a repair. |
| `execution-lifecycle.schema.json` | Fenced controller/native reconciler | Snapshot separating task outcome, native liveness, cancellation and resource ownership. Terminal task outcomes can still require cancellation/reconciliation. |
| `offline-export-manifest.schema.json` | Offline export command (`forge_factory.offline.export`) | Manifest of an export bundle carried to development (DA-FR-056): records in full from an allowlist, other files by hash, vendor inputs never; stripped prompt/reasoning keys and redactions counted per file. |
| `review-disposition.schema.json` | Owner (signed, namespace `forge-review-disposition`) | One end-of-run review decision on a registered gap or finding (DA-FR-057). Learning set only; never a release approval or a change to a package. |
| `patch-bundle.schema.json` | Development builder, owner signature (namespace `forge-patch-bundle`) | `PATCH.json` of a signed patch bundle (DA-FR-058): base/target revisions, per-file new and base hashes, declared regression, CRE decision hash. Activated only by the local import gate. |
| `examples/manifest.json` | Specification author | Explicit mapping of synthetic positive/negative structural fixtures to schemas and expected validity. |
| `validate_contracts.py` | Read-only specification checker | Checks Draft 2020-12 schemas, the complete fixture inventory and expected structural acceptance/rejection. |

The schema `$id` is a contract identifier, not a network endpoint. Consumers must pin the local version. JSON Schema's `additionalProperties: false` is deliberate. No coercion of wrong types, silent field deletion or automatic decision completion is permitted.

Each proposal addresses one small, coherent repair objective from a controller-selected packet. Array/string maxima are defensive serialization limits, not a request to fill them. The controller enforces a smaller measured per-role output allowance and bounds the total serialized payload. Do not ask one local Qwen invocation to diagnose all 50 historical RCC gaps. Decomposition retains a global obligation/coverage manifest, shared mission limits, provenance and externally stored evidence; a small prompt must not discard required evidence. A bounded search may create distinct proposal identities, but never independent budgets or automatic duplicate implementation attempts. Receipt `reason_codes` can record `CAPABILITY_LIMIT`; that classification must reference measured qualification or observed bounded failure evidence rather than a model's unsupported self-assessment.

Semantic-proposal branches are exclusive:

- PROPOSE_REPAIR carries a hypothesis, target obligations, material change, allowed technique reference, proposed artifact scope and expected independent checks. Model switch/upstream return require their explicit semantic choices.
- NEEDS_EVIDENCE carries scoped missing-evidence requests. It cannot carry repair fields or result in an implementation dispatch. Any allowed follow-up consumes the original mission budget; the default proposal is at most one bounded evidence exchange, configured and enforced by policy.
- CLOSE_BLOCKED supplies evidence-backed blocking reasons. It is independently evaluated; a model refusing every case is not successful autonomy.

`evidence_refs`, `test_ref`, `technique_id`, obligation IDs, profiles and artifact scopes must resolve within the sealed packet and current authority. Their string shape alone is not evidence of existence, correctness or permission. The complete phase-scoped diagnosis packet must expose incompleteness; paging a truncated summary never proves evidence completeness.

The existing authoritative `../../005-autonomous-factory-operations/contracts/recovery-plan.schema.json` is neither copied nor changed. Host binding must validate against it and the production recovery validator. Detailed mapping and cross-record invariants are in `../data-model.md`.

## Hashes, receipts and persistence

Proposed canonical JSON encoding is UTF-8 with sorted object keys, compact separators, Unicode retained (`ensure_ascii=False`), and no non-finite numeric values (`allow_nan=False`). Reject duplicate input keys before canonicalization. Strings are preserved exactly; do not normalize semantic text while hashing. This restricted contract contains no floating-point decision fields. Align the implementation's hash helper and cross-language fixtures explicitly before rollout.

Hash canonical schema-valid proposals with SHA-256. A rejected malformed payload may use SHA-256 of the received raw bytes and `proposal_hash_basis=RAW_BYTES`; retaining that hash does not authorize retaining raw private input. A raw malformed payload has no trusted semantic decision (`decision=null`). Synthetic fixture digests are placeholders, not computed provenance.

Hash each immutable receipt revision's canonical bytes externally; its successor's `previous_receipt_sha256` binds that digest. Do not include an unresolvable self-hash in the record. Receipt revisions begin at one with no predecessor; later versions preserve immutable identity and reference the actual predecessor. `admissibility_receipt_ref` must resolve to the exact independent decision, including policy/authorization/evidence versions. `verification_receipt_ref` must resolve to independently produced verification evidence. Schema validity cannot authenticate either reference.

`STORED + PENDING + NOT_REQUESTED` is an expected intermediate state. `ACCEPTED + NOT_REQUESTED` is still not execution. `ACCEPTED + VERIFIED` proves only the independently checked repair scope once its evidence is authenticated; full product acceptance uses the unchanged release gates. A successful native run or compact PASS text cannot synthesize any of these transitions.

The execution schema permits `BLOCKED + LIVE + ACKNOWLEDGED + HELD`: an outcome can be terminal while cancellation is merely acknowledged. An acknowledged cancel does not imply quiescence. `UNKNOWN + RELEASED` is forbidden. Native IDs may be absent after a lost launch receipt; the nonce and durable intent remain mandatory for reconciliation.

## Validation strategy

Run from any working directory:

```sh
python3 specs/014-durable-local-autonomy/contracts/validate_contracts.py
```

Development-only dependency: Python `jsonschema` supporting Draft 2020-12 (validated with 4.23.0). This is a specification-checker dependency, not a newly required production service. The checker also validates RFC 3339 date-time syntax using the standard library so optional format packages cannot silently disable that check.

The checker must report `scope: SPEC_CONTRACTS_ONLY_NOT_RUNTIME`, all three schemas and every positive/negative fixture. A negative fixture passing its schema is a checker failure. Unknown schemas, duplicate manifest entries, orphan fixture files and malformed JSON also fail. No file is rewritten.

Implementation qualification additionally requires the following tests; they are **not implemented or satisfied by these fixtures**:

| Invariant | Required implementation/behavioral test |
|---|---|
| Real wire schema | Compare actual registered MCP schema and constrained-generation schema against this contract; execute valid/invalid payloads through authorization tickets and serialization, not direct Python model construction alone. |
| Authoritative plan compatibility | Bind each decision to the existing plan schema or explicitly no plan for NEEDS_EVIDENCE. Reject wrong types and invalid semantic mappings without invented fields or truncated meaning. |
| Complete evidence | Retrieve a decisive finding beyond the former 1,500-character summary cap; reject stale hashes and nonexistent/cross-case references. |
| Material difference | Reworded/reseeded duplicate technique remains a duplicate; an actually changed permitted technique is distinguishable. Validate against prior strategy history. |
| Receipt integrity | Authenticate references/hashes, reject wrong case/nonce/mission, broken predecessor chains, mutable identity, revision races and fabricated independent-verifier receipts. |
| Single effective dispatch | Crash after acceptance and before/after outbox/native acknowledgement; replay must adopt the same execution, not launch another. |
| Current authority | Revoke or expire admission after stored/accepted proposal and before dispatch. The historical receipt remains evidence but does not allow a new request. |
| Cancellation reconciliation | Cancel returns 500/timeout/202 while still live; revoke before native receipt adoption; restart during cancellation; multiple nonce matches. Retain resources until actual quiescence. |
| Verifier recovery | Kill before/after worker spawn and during verification; adopt or safely repeat verification without duplicated external publication. |
| Accounting lineage | Concurrent admissions, late/missing usage, reservation overrun and continuation order preserve the shared ledger; a new order cannot reset caps. |
| Release independence | Model success, accepted CLOSE_BLOCKED, a stored proposal and scoped verification can never produce a READY package without all unchanged release gates. |

Schema checks cover static snapshot relationships only. Transition legality, external reference resolution, effect idempotency, cancellation, resource fencing, ledger arithmetic and genuine independent verification require tests against the implemented components and finally the qualified native local path.


## Operator time-window amendment (2026-10-29 implementation)

This is an administrative CLI input, not a semantic-proposal branch or model
permission. See afo.mission_deadline.SCHEMA and the exact-field validation there,
plus INCREMENTAL-RUNBOOK.md. The existing independent-decision table stores sealed
receipts; MissionLedger validates a bounded8-record linked chain. Original
allowances/accounting remain intact. This additional runtime interface does not
change the six versioned qualification schemas or their structural fixtures.
No amendment or grant is created by specification validation.

## Explicit operator capacity amendment (2026-10-30 implementation)

`afo mission-amend-capacity FILE --reason TEXT` is an authenticated operator-only
CLI command, never an agent MCP operation. `afo.mission_capacity.SCHEMA` defines
the exact input: mission and complete current snapshot hash, six finite non-time
ceilings, exact signed authorization reference/request, operator intent epoch and
reason. The grant must bind `mission-capacity-amendment-014:` plus the canonical
document hash. Ordinary execution authority cannot amend capacity.

This implements the owner's explicit high-allowance request while preserving the
same immutable initial mission, lineage, expenditure, uncertainty and original
limits. At most eight append-only amendments are stored in the existing independent
decision table. Ceilings must increase monotonically within current policy;
the protocol correction ceiling cannot change. An exhausted non-time allowance
or unbounded historical usage prevents amendment. The old deadline is unchanged:
a separate exact signed time-window decision is still required where expired.

The command checks native quiescence and holds the existing operator intent lock
through its database transaction. A newer pause/stop/epoch fences application.
No order is reopened, job admitted or grant renewed by this operation; historical
receipt replay has no effects or present dispatch authority. Existing admission,
capability, resource and quality gates remain mandatory. Model-free factory
supervision continues when the affected mission remains blocked.


## Optional bounded maintenance feedback

The existing AFO policy schema accepts optional
`maintenance.max_retained_reworks` (integer0..8, default0). Existing signed
policies and their meaning remain unchanged when the key is absent. The case,
sealed receipt/reference and verification-job result extensions are administrative
bindings produced by the existing broker/worker, not semantic model fields or
new capability/deployment grants. See afo.maintenance_rework and the retained
maintenance section of data-model.md. All six qualification schemas and their
structural fixtures remain distinct from native runtime qualification.

## Runtime contracts (`runtime/`)

The six schemas in `runtime/` belong to the process-first lab (`docs/designs/forge-c-process-first-ornith-qwen.md`,
§1, §4, §8 and §9). Unlike the schemas above, the factory loads them at runtime through
`forge_factory.process_lab.contracts`. `validate_contracts.py` checks them and their `process-lab-*` fixtures as well.
The `SPEC_CONTRACTS_ONLY_NOT_RUNTIME` scope of the fixture manifest still describes the validator: it never runs
production code.
