# Bounded local inference contention retry

Tested source **d2e083e322aeb3286e6d94bd0d51e532f7d66fb7**, **NOT ACTIVATED**.
Current native cohort remains producer0e/profile3/auditor303, same frozen scope.

Observed problem: fresh06 physically settled while07/08 inherited3600s waiting
on normal singleton inference contention. Healthy Conductor remained running,
but eligibility delayed ordinary dispatch. The disclosed administrative retry
is in [actual terminal/handoff evidence](../fresh06-terminal-20261031/README.md).

Existing scheduler now requests a constant15s Store.defer interval only when
the complete preflight issue list is exactly NATIVE_INFERENCE_CAPACITY_HELD.
Mixed/external faults retain exponential60..3600s cooldown. Existing eligibility,
authority, mission, storage, dependency and inference-lease checks still run.
No new scheduler/store, forced capacity release, history clear or budget reset.
The bound is eligibility retry, not a guaranteed15s wall-time dispatch SLA;
Conductor cycle/other eligible orders add latency. Old already-persisted waits
are not rewritten by this change. Deployment is deferred until this cohort ends.

New regression exercises actual Store/scheduler/preflight/MissionLedger and
Executions using synthetic authority and a deliberately terminal-but-unsettled
execution. It retains7prior deferrals; while ownership is held, repeated cycles
stay QUEUED with15s eligibility and unchanged expenditure. Only a synthetic
local never-launched proof permits release; the next eligible ordinary cycle
admits. A mixed Fabro failure still receives3600s. There is no native/provider
or model invocation, no real quiescence/availability qualification.

First test setup omitted a required ledger execution reservation:2fixtureFAIL.
After correcting the fixture, old source gives **1FAIL/1PASS**, exact3600vs15s
counterexample. Fixed focused **2PASS**. Broader precommit **117PASS**, followed
by exact committed-source **117PASS/zero failures/errors/skips,14.112s**.
Cohorts overlap; do not add their counts. Exact paths/environment/arguments are
in exact-source-summary.json. Failed and passing raw XMLs are deterministic
gzip; representations.json binds decompressed original bytes.

Static specification PASS58requirements/tasks/acceptance mappings; contracts
PASS6schemas/38fixtures,14design checksPASS. These are not runtime proof.
Ruff reports **two inherited import-order failures** at scheduler.py74/185;
not silently waived or described as a passing lint check. No diagnostic on
new retry lines. The known inherited RCC graph golden failure also remains.

No DA/DF task additionally closed. Current scoped M1 and fresh1/3 yield stay
separate from full LL/HAL, unattended handoff, production, learning benefit and
24/7 claims, all still unproven. Owner deadline unchanged07:57:59UTC.
