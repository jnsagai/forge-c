# Preserve context admission diagnostics without storing request bodies

Exact candidate **a1c6ae5049bf2477fd5198dcbdbdbc80596b4bb0**. This is a local,
undeployed follow-up to the actual CAPABILITY_LIMIT failure, not a claim that the
current model or product is qualified. Current Omniverse production remains
**9b4c390e1605d11c4865bdeea382df74a0078692**; its active Qwen run is uninterrupted.

## Reproduced defect and correction

The gateway returned a typed code when role/context admission refused a request,
but only accepted requests retained their complete serialized measurement. Native
role detection was used to admit requests, yet the accepted evidence wrote the
unresolved binding/job role (often null). This obscured whether a real later-phase
failure came from context pressure or an unqualified role.

The existing Conductor execution-evidence table now retains REQUEST_REFUSAL
metadata after the live job/nonce checks: body hash, complete byte-bound measurement,
effective output cap, resolved role, model/policy identity and bounded typed cause.
Context overflows include actual input/output/allowed dimensions. Evidence keys
include requestID plus body hash, preserving distinct rejected bodies for one ID.
Rejected requests add no request reservation/charge and call no provider;
the original refusal propagates. Accepted metadata records the actual resolved role.
No request body, prompt, tool-result text or reasoning is retained by this change.
No new store, scheduler, authority, admission bypass or capability promotion exists.

Three focused controls explicitly loaded both old modules from453dde2 and **all
three failed**: accepted role metadata null, oversized refusal evidence missing,
unidentified-role refusal evidence missing. With the correction all three pass.
The tests execute actual role detection/serialization/context admission, using an
explicit fixture only for the independent capability receipt. They also check
unchanged accounting/no request reservation on refusal, private-body exclusion,
and retention of an earlier rejection after a changed body reuses its requestID.

## Qualification and next execution

At exact clean candidate a1c6ae5, the four-module local cohort is **89PASS**,
0failures/errors/skips,30.989seconds, zero model/GPU requests:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 FORGE_FABRO_LIVE=0 \
PYTHONPATH=factory/python FORGE_DATA_ROOT="$FC014_DATA" TMPDIR="$FC014_TMP" \
python -m pytest -q factory/python/tests/test_da014_integration.py \
  factory/python/tests/test_da014_maintenance.py \
  factory/python/tests/test_da014_role_envelopes.py \
  factory/python/tests/test_da014_product_role_trial.py \
  --junitxml="$FC014_OUTPUT/pytest.xml"
```

Raw old-source counterexample and corrected exact-source JUnit/logs are retained.
Selected Ruff E9/F/B checks PASS. Full lint has the same16inherited diagnostics
as453dde2 and no new diagnostics; lint.json records the exact comparison. No broad
lint-clean claim is made.

**Native qualification NOT_RUN** while the owner's current Qwen mission has remote
priority. Before any later deployment, qualify this exact candidate on Omniverse,
preserve operator intent/actual quiescence and bind any new trial to this source.
Do not restart or replace the running9b4c390 to install telemetry.

## Live mission evidence, separately from candidate tests

At14:17:44UTC actual current262k SWE.1 inspection **PASS**, no findings.
At14:18:52UTC native **01M63ZTJ5QM1R96484Y2KN97H6 RUNNING** had begun SWE.2
author tool execution,13provider requests in the current run, identityCONFIRMED
and leaseHELD. Substantive SWE.2 artifacts were not yet observed; tool execution
is not phase completion. The attached live observation is read-only.
The actual serving provider separately reports262144context/one slot at14:14:38UTC;
its observation generated no additional inference.

Strict M1/IE-T008 remains unaccepted. Formal30/58 and completed IE-T001–007 remain
unchanged. IE-T009/M2–M5, measured learning benefit and24–168hour availability remain
unrun/unproven. The current rough QM demonstration retains actual findings and
explicit unaccepted release; its final output is still pending.

Published failure transcripts normalize trailing whitespace only; private original logs/XML remain unchanged.
