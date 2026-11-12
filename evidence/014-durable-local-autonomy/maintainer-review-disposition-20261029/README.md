# Preserve the actual Maintainer review disposition

Exact source **f9e7f54b1838be2560d00117c1725f8d1d74d4c8** fixes a controller
contract mismatch exposed by the actual V6 Qwen submission. Maintainer.process
returns a versioned proposal record containing outcome. Its existing Store
projection separately contains status. The review worker previously accessed
result[status] and raised KeyError even after a valid recorded rejection or
eligibility decision, masking the independent result as BLOCKED.

The worker now obtains status from the durable projection, verifies the projection
contains the exact returned record, and preserves the record schema. It retains
post-evaluation current-policy/authorization/deadline checks and the verification
publication fence. Publishing still uses the existing branch/draft-only broker;
no deployment authority is granted. Rejected candidates remain quarantined.

Four integration counterexamples exercise real Maintainer process/record/triage,
existing SQLite projection, real isolated Git branch broker and original baseline
reproducer on synthetic calc fixtures. Independent evaluator eligibility is a
controlled fixture, not a product/CRE qualification claim. All four FAIL on the
unchanged code with KeyError; all four PASS after the fix. They cover rejection,
eligibility publication, lost verification fence and newer owner policy.

Exact affected local cohort **89PASS**; exact clean Omniverse2 sandbox cohort
**13PASS**, zero errors/failures/skips. Native verifier: one CPU,1GiB address-space,
45CPU/60wall seconds, no network/GPU/model. Commands and XML/provenance included.
Ruff PASS. The fix was externally authored, qualified, then activated for V7 at
RUNNING epoch48 with the loaded provider unchanged. It is not a Qwen repair or
proof of self-healing; it does not alter V6's historical rejection/verification.
