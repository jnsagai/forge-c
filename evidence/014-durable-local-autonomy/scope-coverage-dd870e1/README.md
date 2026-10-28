# Preserve explicitly requested fields during structured authoring

Implementation revision **dd870e1fe826fbf90a9ecd514a06ee693389a127**.
Status: **LOCAL_REGRESSION_PASS; NATIVE_QUALIFICATION_NOT_RUN; NOT_DEPLOYED**.
Formal Feature014 ledger remains30/58. No task is newly marked complete.

The liveCRC run remains pinnedd7fa97e41f6e265e55737478379052db8d6bd859;
this change must not be applied inside its active workspace or mutate its grant,
mission, checkpoints, requirements, native handles or costs.

## Observed problem

[Read-only partial packet metadata](observed-live-packet-metadata.json) records an
actual live SWE.1 packet accepted asVALID despite having zero intents and excluding
CRC_CR.REV_OUT, CRC_CR.RTYPE_OUT and CRC_CR.RTYPE_IN. The tracked work order explicitly
requests these fields. Earlier SafeC findings rejected proposed read-modify-write
operations due to the unmodeledRESET write effect. The revised packet removed the
requested fields instead of supplying their verification. A localVALID label did
not prove repair, complete requirements, phasePASS or product correctness.

The original run/failed proposals are preserved. Whole SWE.1 inspection had not
passed in this snapshot. The experiment remains a useful negative observation;
it is not independently correct learning or successful autonomous self-healing.
No existing promoted lesson, inspector configuration or qualification denominator
was changed to make this sample pass.

## General correction

The existing structured SWE.1 validators now reject not_covered entries for exact
REGISTER.FIELD identifiers explicitly named by the work order's in-scope text.
The same shared check covers semantic-intent and legacy structured-requirement
authors. It normalizes bare field names against the current task's register and
uses exact field boundaries, preventing substring matches. There is no CRC name,
peripheral-specific branch, new scheduler or alternate authority store.

Explicit out-of-scope declarations remain available. Unmentioned fields do not
acquire new requirements. The rule does not infer operations or complete behavioral
coverage from prose; independent inspection, traceability and subsequent code/test
gates remain required. Source/contract ambiguities and unsupported verification
must remain visible gaps, rather than silently reducing requested coverage.

Both author packet builders state the rule, so it is part of the complete serialized
context and existing input-hash/checkpoint identity. No inspector prompt, sampling,
source authority, safety scope, release criterion or hardware semantics was edited.
The current live run is not retroactively requalified by this new validator.

## Evidence

[Test results and JUnit hashes](test-results.json):

| Lane | Result |
|---|---|
|Prior7908a11 with10new counterexamples|4PASS/6FAIL,0.250s|
|Candidate focused+inherited structured author tests|31PASS,4.608s|
|Candidate semantic/required-preflight/inherited engine checks|44PASS,326.579s|
|Exactdd870e1 new scope regressions|10PASS,0.158s|

All lanes have0skips. Inherited semantic checks use the actual pinned local SafeC
engine and scripted model answers, including native tools/target oracle where
applicable; they make0model calls. They are deterministic runtime regressions,
not Qwen tests or local-model qualification. All actual Qwen execution stays on
Omniverse2. Local source/test Ruff and diff checksPASS.

The tests reproduce the real trackedCRC scope through both author paths, qualified
and bare field exclusions, another peripheral's required field, allowed owner
exclusions, and exact-identity boundaries. Original failures are retained. No new
inference, remote test cohort or worker restart was launched by this correction.

Commands use a private state/events/TMPDIR onloop10 and the existing venv:

~~~sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH="$REV/factory/python" \
FORGE_DATA_ROOT="$LOOP10_ROOT" FORGE_FABRO_BIN=/home/jefferson/.fabro/bin/fabro \
FABRO_NO_UPGRADE_CHECK=1 FORGE_STATE_DIR="$PRIVATE_STATE" \
FORGE_EVENTS_DIR="$PRIVATE_EVENTS" TMPDIR="$PRIVATE_TMP" \
"$LOOP10_ROOT/venv/bin/python" -m pytest -q \
  factory/python/tests/test_da014_required_scope_coverage.py \
  factory/python/tests/test_lrtx_swe1.py
~~~

The44-case command instead selects test_lrtx_v2_swe1.py,
test_da014_required_preflight.py and test_da014_required_scope_coverage.py.
The exact10-case command selects only test_da014_required_scope_coverage.py.

## Native next execution

Native qualification is NOT_RUN while the owner's currentCRC→RNG inference mission
occupies Omniverse2 and source must remain pinnedd7fa97e. Once verified quiescence
and applicable authority permit, qualify exactdd870e1 in an isolated checkout using
the existing native fixture runner/pytest path, starting with the10standalone scope
cases. Do not run concurrent GPU tests, reset an old mission, or treat source/spec
checks as live Qwen qualification. Any later engine/profile capability alternative
also needs exact pins, independent qualification and preserved historical allowance.

The active factory continues using the existing controller/watchdog/intake, Q38Q8
xhigh and one inference/one verification worker, until the unchanged16:29:12Z window
cutoff. Collect the actual original run and independent quality findings, then verify
scheduled old-policy restoration. Do not infer whole-goal completion from this fix.
