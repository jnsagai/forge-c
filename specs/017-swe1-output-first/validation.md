# Validation and controlled experiment protocol

All native results initially: **NATIVE_NOT_RUN**. No task checkbox or acceptance result is satisfied by this document.

## A. Freeze the comparison

Before trials, version a manifest containing task/source hashes, obligations, reviewed expected properties, seeded defects, model/runtime identities, sampling settings, prompts/schema/check versions, budgets and repetitions. Keep source content and private captures in the local evidence store. Avoid adapting prompts against the held-out case.

Use at least 12 small author tasks spanning three behavior families and at least two driver families: configuration/readback, bounded waiting/error paths, and asynchronous completion/buffer or resource ownership. Include a behavior case withheld from tuning. A missing capability in the current intake is an explicit onboarding gap, not permission to manufacture source facts.

Run at least three repetitions per task/configuration with the same supported seeds where possible; record nondeterminism when seeds are unsupported. This is an initial engineering screen, not proof of universal capability. Match concurrency and hardware allocation. Report warm and cold behavior separately, including model loading and cache state, and alternate trial order where practical. Do not insist both models fit in VRAM simultaneously.

## B. Isolate one change at a time

1. Establish a measured current author + current inspector baseline.
2. Change only the author's effective thinking mode. Preserve task content, sampling parameters where compatible, validators, inspector and budgets; record unavoidable differences.
3. If off is unsupported/unverified, test a genuinely supported bounded mode and label it accurately.
4. After contract/render changes, establish a fresh matched baseline on that path; do not attribute simultaneous prompt, schema and inference changes entirely to thinking-off.
5. Evaluate any inspector mode change separately against a fixed defect suite and known-good requirements. Do not use the candidate inspector as the sole judge of its own quality.

## C. Capability proof

Check through the actual application gateway, not just a direct model-server call:

- deployed model digest, quantization and role routing;
- backend/template/gateway identity and effective request mapping;
- JSON schema adherence and nonempty output when obligations are mandatory;
- thinking-off or bounded mode honored, with transient classification/numeric accounting where available;
- independent answer/total-generation limit semantics and context reservation;
- cancellation and timeout propagation to the backend, including no orphan inference;
- graceful handling of unsupported controls, malformed JSON and missing usage.

Do not persist reasoning text to prove this. Inspect template/request paths and numeric counters or transient stream event types. If this cannot establish the effect, label it UNVERIFIED. Do not treat a short displayed answer or absent reasoning field as proof. A generic API parameter name does not establish semantics on every backend/version.

## D. Mandatory deterministic regressions

| Case | Expected result |
|---|---|
| Matching duplicate prefix, e.g. resource `PORT_CFG`, field `PORT_CFG.MODE7` | Canonical `MODE7`; retain the obligation and requirement |
| Mismatching/ambiguous prefix | Representation finding; no guessed rewrite or scope deletion |
| Empty arrays for nonempty mandatory scope | Reject; restore previous usable candidate |
| Stale or unrelated patch | Atomic rejection with prior revision intact |
| Patch drops a supported value, state or instance | Coverage regression finding |
| Distinct calls share token totals | Both counted by call ID |
| Duplicate lifecycle events | Aggregated idempotently |
| Failed/superseded/cancelled call | Retained in history; missing usage labeled unknown |
| Crash after response, before completion event | Recovery reconciles durable evidence or records unknown; no invented success |
| Changed shared precondition/source | Only dependent accepted contracts become STALE; aggregate consistency reruns |
| Same finding across visits/repartition | Does not reset task lineage or phase budgets |
| Unsupported rendering pattern | Structured finding; no model call just for grammar and no semantic rewrite |
| Existing legacy profile selected | Behavior remains unchanged |
| SWE.1-only run finishes | No SWE.2 launch or full release claim |

## E. Semantic and inspector defects

At least 12 independently labeled defective examples plus known-good controls. Include: missing value/state coverage despite named fields; unsupported invalid-input masking; contradictory policies across instances; missing access/write-protection precondition; unexplained timing assumption; source locator that exists but does not support the claim; ungrounded exclusion; false test execution claim; frozen-code discrepancy disguised as a new requirement; vacuous preservation check; asynchronous ownership/completion omission; and inconsistent shared resource assumptions.

Use synthetic sources or license-cleared public fixtures. Expected verdicts must be independently reviewed and frozen before trials. A second model's agreement alone is not the oracle. Where arithmetic or executable consistency checks are useful, apply independent expected properties; do not derive both implementation and expected answer from the same unchecked generated contract. Use contrasting surrounding-bit patterns, including zeros and mixed bits, to expose set/clear corruption that all-nonzero presets can mask.

## F. Measurements

Report per task, behavior family, role and full work order:

- semantic first-pass acceptance and final mandatory-obligation coverage;
- unsupported claims accepted, seeded-defect detection and known-good false positives;
- total reported generated tokens, reasoning/answer split when known, prompt/cache tokens;
- full task median/p95 elapsed time, call/inference time, loading/queue time and repair cost;
- attempts, repeated findings, changed strategies, coverage regressions and resume reuse;
- exact input/profile/tool versions and all NOT_RUN/unknown values.

Use denominator = independently validated accepted contracts/obligations; never reward an empty output, excluded required scope or premature blocker as efficient acceptance. Publish separate completeness and correct-blocking metrics. Estimates such as characters/4 must be labeled and cannot prove reasoning-token counts. Raw historical summaries with inconsistent call counts are not a clean performance baseline.

## G. Promotion and stopping rules

Mandatory: all deterministic regressions pass; no seeded critical defect is accepted; known-good false positives and task semantic acceptance do not regress against the frozen baseline; no accepted unsupported claims; all required coverage is retained. For a full phase claim, all mandatory obligations must be satisfied and all blocking issues resolved under the applicable policy.

Initial performance targets: >=50% reduction in total generated tokens and >=30% reduction in median full task latency versus the matched baseline, including repair cost. These are targets, not forecast results. If quality fails, reject the candidate regardless of speed. If quality passes but performance targets fail, retain the baseline default and report the measured tradeoff. If tokens cannot be measured reliably, the token target is unproven, not passed.

Do not promote on an aggregate average that hides a failed behavior family or held-out case. Record repeated-trial distributions and limitations. Passing this screen supports only the evaluated workload/profile. Runtime promotion still follows the existing deployment authority; this feature handoff does not authorize a production cutover.

## H. Milestone report

For each milestone record commit, exact commands, environment identity, results, hashes/paths of local evidence, unresolved items and next task. Distinguish IMPLEMENTED, REPLAY_PASS, NATIVE_PASS, NATIVE_FAIL and NATIVE_NOT_RUN. Never mark native capability or competence complete based only on mocks.
