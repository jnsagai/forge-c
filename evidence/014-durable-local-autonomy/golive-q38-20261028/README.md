# Omniverse2 engineering recovery and official Qwen3.8 switch

Runtime tested and deployed: **a7490b45e25a399c87e274f60c3f2fcaba1080c2**.
Feature014 remains **30/58** tasks; no task is newly closed by this checkpoint.
These are engineering interventions and bounded trials, not successful autonomous
self-healing, product qualification, learning benefit or a 24/7 availability claim.

## Running configuration

Owner selected **Qwen3.8-27B Q8_0 for all local roles**, prioritizing quality over
speed, and requested `xhigh`. The new dedicated profile
`local-rtx-v2-omniverse2-q38-quality` permits only `qwen3.8:27b-q8_0` with one
admitted inference request. Context is65536tokens, additional reasoning output
allowance32768tokens, Fabro output ceiling49152tokens. Old profiles retain their
previous settings. Roles still require separate qualification; a selected model
is not a capability receipt.

[Activation](activation.json), [model integrity](model-integrity.json), and
[native render proof](xhigh-native-render-proof.json) bind the change. All five
installed model blobs were freshly SHA256-verified (29,978,242,050bytes).
Installed Ollama0.34.0 rendered the explicit xhigh instruction; medium did not.
Both calls used native render-only mode with zero prompt/completion tokens.
No Qwen3.8 generation or engineering request has yet qualified a role.

The owner-approved SSH-agent signing method signed the scoped model-switch grant
`AUTH-014-OMNIVERSE2-Q38-GOLIVE-20261028-V2`. Expiry remains
**2026-10-29T05:00:00Z**. LL/manual-order scope, one concurrent order,120k tokens,
three attempts and six-hour limits remain. No private key was read/copied, no
historical allowance was replenished, and no deployment/release gate was waived.
Operator intent advanced through an epoch-fenced maintenance pause to RUNNING5;
a newer authenticated operator instruction always takes precedence.

## Actual trial results

The original eight-hour RCC run at66c3d13 ended BLOCKED, not recovered. Its
continuation failed locally at `git commit` with no tracked changes, before native
launch. The unknown dispatch held inference capacity overnight. Original source,
single-dispatch trace and prepared workspace were reviewed before explicit
engineering reconciliation. [Reconciliation proof](operator-reconciliation.json)
records its hash and retained **86000** conservative mission charge. Idle GPU or
an absent native listing was not treated as sufficient quiescence proof.

A fresh, prospectively scoped Qwen3.6 IWDG trial at97936d7 used **31 real model
requests**, with **83631 reported tokens** and **116000 conservative mission
charge**. It created a SWE.1 baseline, but did not pass inspection. Thirteen
required packets remained INVALID because the job token envelope was exhausted;
39 semantic retries could not change those deterministic refusals. Diagnosis
failed before a model call because a reason-only gate produced an empty objective.
The second product attempt also exhausted its smaller envelope. Both product
packages are BLOCKED/INCOMPLETE; the diagnostic is FAILED_PROTOCOL. All three
native leases are physically released; semantic failure remains independently
recorded. See [recorded outcomes](iwdg-recorded-outcomes.json).

[Feasibility](iwdg-feasibility.json) proves at least13 new requests are required
for already known unanswered packets, against only1 remaining. Additional
uncreated checks are excluded from that lower bound. Do not replay this mission,
give it a new alias/allowance, or interpret this as a model-accuracy conclusion.

## Implemented corrections

Reviewable commits on the existing feature branch:

- af509b4: preserve local prelaunch failure evidence, skip empty resume commits,
  stabilize case identity across poll limits, and reconcile expired waiting orders.
- 2fbb33e: settled request-usage accounting reuses only proven unspent per-request
  capacity after quiescence. Legacy charges and job/mission reservation floors stay.
- 4fc584b: retain owned API relay metadata during health refresh.
- 97936d7: expected-epoch operator transitions fence delayed maintenance resumes.
- 9663fa5: hash-bound reason-only gate findings and no semantic repair retries for
  fixed administrative refusals; busy/transient retries remain bounded.
- ddd6b4d: retain failed product semantics after physical lease release without
  inventing RECOVERED from a READY label or releasing a live provider.
- 24f5d00: factual phase-gate outcomes enter the existing learning/disposition
  path even without an inspection record; no invented defect or promoted lesson.
- 1252589/a7490b4: dedicated Qwen3.8 Q8 quality profile, validated provider bounds,
  explicit xhigh support and old-profile compatibility.

Changes are general to workorders and phases, with no IWDG/RCC-specific scheduler,
memory store, correctness exception or driver-specific bypass.

## Verification

[Test results](test-results.json) retain exact revisions, counts, native commands,
JUnit hashes and original nonpassing outcomes. These cohorts are not one aggregate
green full-suite invocation:

| Revision | Host and scope | Result |
|---|---|---|
|24f5d00|loop10 affected/AFO/learning/inherited regression|241PASS,110.203s|
|24f5d00|Omniverse2 native fixtures|52PASS,122.768s|
|a7490b4|Omniverse2 profile/gateway/product/gate fixtures|32PASS,25.297s|
|a7490b4|loop10 inherited governance/release|13PASS,9.658s|

Native fixtures use real filesystem/process/protocol mechanisms with isolated
state; they do not generate model output. All actual Qwen tests remain remote.
Original counterexample failures, environment mistakes and the120s incomplete
native lane remain recorded. Static specification/schema/design/handoff checks
are documentation checks, never runtime qualification.

Native command at exact a7490b4 (environment/state are isolated from production):

```sh
python -m pytest -q \
  factory/python/tests/test_da014_q38_quality_profile.py \
  factory/python/tests/test_llm_gateway.py \
  factory/python/tests/test_da014_product_outcomes.py \
  factory/python/tests/test_da014_gate_incidents.py
```

Release command at exact a7490b4 uses the installed real Fabro pin:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH="$REV/factory/python" \
FORGE_DATA_ROOT="$LOOP10_ROOT" FORGE_FABRO_BIN=/home/jefferson/.fabro/bin/fabro \
FABRO_NO_UPGRADE_CHECK=1 FORGE_STATE_DIR="$PRIVATE_STATE" \
FORGE_EVENTS_DIR="$PRIVATE_EVENTS" TMPDIR="$PRIVATE_TMP" \
"$LOOP10_ROOT/venv/bin/python" -m pytest -q \
  factory/python/tests/test_m7_governance_release.py
```

## Resume and remaining work

Read [runtime snapshot](runtime-status.json) and actual current intent/services
before acting. The controller and recovery timer supervise independently of the
finite recorder. New progress branch is
`q38/2026-10-28-local-factory`; it observes already terminal historical Qwen3.6
orders through the existing recorder and performs no new intake or generation.
Its original six-hour milestone ends **2026-10-28T14:06:31Z**, without globally
shutting down the factory. Previous progress branches remain historical.

Next address prospective role-envelope feasibility: legacy diagnosis allocations
must fit the complete serialized input plus xhigh reasoning and answer allowances.
The32768 reasoning increment alone exceeds a legacy16000-token job. Do not simply
retry it or change old mission ceilings. Use existing role qualification and finite
admission paths for newly authorized scoped cases; qualify diagnosis, authoring,
inspection and maintenance separately before a new large product run. Preserve the
frozen inspector and require independent correctness evidence.

Full native recovery/RCC qualification, independent host/control fault observation,
product benchmark, comparable learning benefit and24/72/168-hour campaigns remain
unrun/unproven. Existing private-input/model-compatibility blockers remain. No
automatic merge or production-release claim is authorized by these test results.
