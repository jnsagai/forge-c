# Downstream semantic verification and native model incompatibility

Exact runtime SDK: **466d87bef4688af6209937433ef056baa4a5d51f**.
Consumer integration passes; the frozen ST driver still has an independently
measured verification-model incompatibility. No Qwen call or product attempt ran.

The oracle, Frama-C obligation reader and mutation generator previously rebuilt
register-io-0.1 even for new-profile artifacts. Reconstructed contract objects also
discarded profile metadata. Three real-engine positive tests reproduced these
failures before the fix. The consumers now use the existing profile authority,
check frozen profile/engine bindings, rebuild the selected domain family, preserve
its version through independent checks and refuse stale/mixed/rehashed artifacts.
Legacy recorded artifacts also pass both oracle and obligation-reader replay.

| Exact-source verification lane | Result |
|---|---|
| Local affected semantic/consumer/bridge/AFO integration | 219 PASS, 45.525 s |
| Release/legacy quality/OSS gates | 29 PASS, 11.061 s |
| Omniverse2 native new-profile/consumer/client tests | 42 PASS, 33.253 s |
| Real WWDG joint set, all12 forms in one request per operation | PASS for validation, oracle and obligation derivation |
| Production oracle/obligation consumers on that source | PASS |
| Source-derived mutation operators | 7 generated |
| Compiled frozen ST functions versus44 register-image cases | 40 match,4 mismatch; qualification exit2 |

The affected test command excludes the two unchanged expensive Frama-C/target-oracle
cases previously measured at a74baa9. The changed legacy readers were separately
replayed against actual old-engine artifacts without rerunning unchanged solvers.
These results are not a full inherited-suite or whole-private-product qualification.

## What the native source comparison proves

The existing CMSIS host adapter compiled fingerprinted, unchanged ST code. Expected
values came from the reference-manual domain through the pinned Rust engine and
independent Python checks. This is an external verification fixture, with no fake
requirements inspection, phase PASS, release candidate or actual product job.

| Function | Native observation in the plain-memory adapter | Current oracle |
|---|---|---|
| LL_WWDG_GetPrescaler | Returns14336 for each of two nonzero field-image cases | Returns7 |
| LL_WWDG_ClearFlag_EWKUP | Host register word becomes0xfffffffe for each of two cases | Host register word becomes0 |

All other words remain unchanged in these cases. The first disagreement concerns
API value representation; the second concerns the abstract register image versus
the clear operation's written word. These measurements do not establish silicon
behavior or a hardware defect in ST code. The44 cases do not exhaust parameter
domains or hardware obligations.

The current logical-field/plain-memory model therefore cannot qualify the unchanged
full frozen-driver scope yet. Before a full Qwen retry, baseline and independently
qualify the relevant API representation and hardware-access model, or obtain an
explicit scoped alternative. Do not normalize away mismatches, weaken gates,
change the frozen driver, manufacture a repair or infer Qwen failure: **zero model
calls were made**. Product authority and cumulative mission bindings remain separate
unbound prerequisites.

Three assessments retain the same40/44 versus4/44 result: the initial private
native harness, the first committed reproducer, and the final bounded reproducer.
Each uses3 engine requests for the joint12-operation set,0 model requests and0
product attempts; unit-test engine calls are counted in their own test lanes.
All earlier results remain. Factual BLOCKED experience/dispositions are durable:
DEFERRED_BUDGET with0 inference tokens, no qualified lesson or measured benefit.
No repair incident or inspector lesson was invented.

## Executable frozen reproducer

[Reproducer source](../../../factory/qualification/014/reproduce_wwdg_verification_model.py)
is committed for review. It runs only on Omniverse2, requires the preserved frozen
candidate/engine/vendor inputs and imports the exact clean466d87b SDK. It refuses
an existing destination. The overwrite control returned1 with an unchanged existing
summary. Final source SHA256:
`ff68416dda948acac080352512f274ad3c384412bea392b94da60b38ab366b25`.

With the source file available on Omniverse2:

```sh
Q=/mnt/data/forge-c/inspector-014-b309039
export FORGE_REPO_ROOT="$Q/consumers-466d87b/repo"
export PYTHONPATH="$FORGE_REPO_ROOT/factory/python" PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=5s 120s "$Q/lrtx/venv/bin/python" /path/to/reproduce_wwdg_verification_model.py --destination "$Q/repro-wwdg-UNIQUE"
```

Expected measured result for this frozen dataset: ABSTRACT_MODEL_MISMATCH, exit2.
The final measured run is `repro-wwdg-model-002`; its source fingerprint matches the
committed file. Its engine calls are capped at20 CPU/wall seconds each. Host
observations have a5-second CPU/10-second wall/256MiB address-space bound.
Compiler identity is retained. Compilation is bounded to30 seconds; no service,
grant, mission, default pin or production artifact is mutated. The tool is a
finite qualification case, with no scheduling or inference authority.

The exact local test command is:

```sh
python -m pytest -q factory/python/tests/test_da014_v02_consumers.py factory/python/tests/test_da014_v02_profile.py factory/python/tests/test_lrtx_v2_swe1.py factory/python/tests/test_safec_bridge*.py factory/python/tests/test_afo_local_autonomy.py factory/python/tests/test_da014_integration.py -k 'not wp_proves_each_register_effect and not target_oracle_on_the_iwdg'
```

Use loop10 basetemp/JUnit/state/events/TMPDIR paths and explicit old/new pin documents.
The native test lane uses new-profile consumer, profile and bridge-v02 test files.
Full commands, output XML and private raw observations remain under the recorded
operations directory and isolated remote roots. [Regression and fingerprints](regression.json),
[final bounded assessment](summary.json), [original assessment](initial-summary.json),
[legacy replay](legacy-reader.json), [factual disposition](learning-capture.json).

Formal Feature014 completion remains30/58. Driver READY, model-role qualification,
self-healing, learning benefit and operational availability remain unproven. The
private whole-workspace replay also still needs16 missing original inputs.

