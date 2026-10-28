# Prospective role capacity and first Qwen3.8 native request

Tested and deployed runtime: **2c774b440db65f47f5b78a4702ad974254fa6a96**.
Formal Feature014 completion remains **30/58**; no additional task is ticked.

## Implemented behavior

The owner-selected Qwen3.8 Q8 profile uses xhigh with a32768-token reasoning
increment. Legacy diagnosis16000/maintenance24000 job reservations could not fit
that increment plus complete input and an answer. Profile version2 explicitly
configures finite **65536-token** prospective reservations for these two roles.
Other profiles retain their registry defaults. Profile, policy, grant, mission,
request and independently measured capability remain separate authorities.

The existing local-agent preparation path now:

- Requires the workspace's exact profile version, path and SHA256 before using an
  override; refuses malformed values rather than coercing or clamping them.
- Refuses model/profile/case rebinding of an existing job, including legacy jobs.
- Measures the full first effective diagnosis request before reserving its job,
  including primary evidence, instructions, schema and gateway output extension.
  A request that does not fit blocks without charging or launching that new job.
- Stores counts/hashes, with no raw prompt or hidden reasoning. The measurement
  remains a conservative UTF8 byte bound, not a qualified tokenizer or competence.
- Checks existing policy/mission limits without changing old reservations or
  resetting historical costs. Later requests still pass cumulative gateway
  admission; fitting the first call cannot promise a complete later dialogue.

Qualification preparation uses the same profile default and full frozen binding.
Explicit signed qualification overrides remain bounded independently. Preparation
creates no authority, mission or inference. Maintenance keeps its existing sandbox
gate and per-request native-tool admission; no first-dialogue measurement is invented.

## Deterministic and native fixture evidence

[Results and JUnit hashes](test-results.json),
[exact native invocation](native-invocation.json):

| Revision/scope | Result |
|---|---|
|91011bf with the initial14 new counterexamples|14FAIL,2.069s, expected pre-fix failures|
|Initial implementation cohort|51PASS/3FAIL, missing two-step helper import; corrected|
|Initial139-case regression|138PASS/1FAIL, real Fabro environment variable missing; retained|
|Exact2c774b4 local affected/inherited regression|139PASS,30.694s|
|Exact2c774b4 Omniverse2 native fixtures|75PASS,265.659s|

Native source is clean at invocation start/end. All fixture lanes make zero model
calls. The local and native cohorts are separate commands, not a full-suite claim.
The new tests cover stale bindings, complete oversized evidence, immutable legacy
jobs, sandbox enforcement, finite policy/mission ceilings, request-profile changes,
and preparing every100-case frozen input without creating authority.

Local regression command (all writable directories on loop10):

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH="$REV/factory/python" \
FORGE_DATA_ROOT="$LOOP10_ROOT" FORGE_FABRO_BIN=/home/jefferson/.fabro/bin/fabro \
FABRO_NO_UPGRADE_CHECK=1 FORGE_STATE_DIR="$PRIVATE_STATE" \
FORGE_EVENTS_DIR="$PRIVATE_EVENTS" TMPDIR="$PRIVATE_TMP" \
"$LOOP10_ROOT/venv/bin/python" -m pytest -q \
  factory/python/tests/test_da014_role_envelopes.py \
  factory/python/tests/test_da014_qualification_reservations.py \
  factory/python/tests/test_da014_qualification_state.py \
  factory/python/tests/test_da014_protocol.py \
  factory/python/tests/test_afo_local_autonomy.py \
  factory/python/tests/test_da014_q38_quality_profile.py \
  factory/python/tests/test_da014_maintenance.py \
  factory/python/tests/test_lrtx_profile.py
```

## Deployment and recorder

[Activation](activation.json) records the epoch-fenced engineering deployment:
RUNNING5→PAUSED6→RUNNING7, database backup, exact owned provider retirement,
profile-version change and restored backend/controller/timer. Historical RCC86000
and IWDG116000 conservative mission snapshots remain unchanged. Original production
grant expiry2026-10-29T05:00Z remains unchanged; no grant was renewed by deployment.
This was external engineering work, not autonomous self-healing.

An initial recorder migration retained an incompatible immutable old plan and
failed. [Correction](recorder-migration.json) clones the previous progress history
into a new source-specific working repository, preserving the old Git commits and
original plan. It publishes to the same branch, without forced push, new intake,
generation or deadline extension. [Read-only runtime observation](runtime-before-smoke.json)
confirms healthy Conductor/watchdog/recorder, current heartbeat,33 quiescent old
requests, no held inference, and a successful published progress commit. Earlier
SSH/banner timeouts are observation failures; no worker was restarted because an
observation timed out. Reusing one SSH connection restored observation access.

## First bounded Qwen3.8 request

Using the owner's existing bounded Feature014 qualification approval and approved
SSH-agent signing method, a distinct new seeded protocol cohort was frozen. It is
not a continuation or refill of either failed driver mission. The signed scope
permits **one job, one request,65536 tokens, zero product attempts/tools/corrections**,
with grant/mission end **2026-10-28T14:06:31Z**. All100 frozen source cases remain in
the manifest; only `obligation-counterexample:0` is enrolled and99 remain unrun.

[Intake](smoke-intake.json), [prepared job](smoke-prepared.json) and the recorded
running snapshot bind order **afo-39c86c2270b4cf1a**, job
**afo-agent-14b99411ece11c4e260560b4**, native run
**01M611WAN8544QQKWQE3A1H2MC**. At10:48:42Z Fabro's actual API reports RUNNING;
one request is SENT, inference remains HELD, usage is unknown. Complete request
measurement is9873 conservative input tokens plus34816 output capacity, fitting
the65536-token job. The gateway's reasoning extension is applied once.

This is one explicitly seeded REG32 protocol case with a separately compiled
reference, not an STM32 product failure or a qualified role. No successful outcome
is claimed while it runs. Never infer termination from a timeout, idle GPU, task
label or missing listing. Do not duplicate this request, rename the mission or
renew its allowance. Conductor owns native dispatch and supervision.

After proven native/request quiescence: collect the original row through the
existing qualification bookkeeping, run the independent reference audit, retain
the100-case denominator, and restore the original production policy under the
current operator epoch. A newer operator intent takes precedence. The separate
production grant remains on disk with its original expiry; its policy is backed
up in the private smoke directory. Do not leave qualification authority active
indefinitely or claim self-healing, product/benchmark success, learning benefit,
all-role competence or24/72/168-hour availability from this sample.

Private remote artifacts live under
`/mnt/data/forge-c/production-local-014/deployment/q38-protocol-smoke-20261028/`;
the existing progress branch is `q38/2026-10-28-local-factory`.
Full Feature014 qualification and the owner's frozen/parked-task boundaries remain.
