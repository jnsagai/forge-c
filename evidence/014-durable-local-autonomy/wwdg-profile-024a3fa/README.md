# Explicit WWDG profile and frozen semantic context

Runtime source: **024a3fa55fe6b4cce85c61155382cf35aabf76cd**.
This extends the previously measured [engine capability increment](../wwdg-v02-a74baa9/README.md).
No model, driver-product, learning-benefit or continuous-availability claim.

New experimental profile:
`config/factory/profiles/local-rtx-v2-omniverse2-wwdg-v02.yaml`.
It changes only profile identity/status/description and the qualified engine pin
relative to the existing reasoning-off Omniverse2 profile. Model digests, reasoning,
runtime, inspector behavior, admission, endpoints, isolation and gates stay identical.
It neither starts/reconfigures services nor grants execution authority.

The actual workorder intake freezes the selected semantic profile alongside its
configuration identity/version/hash. New-profile semantic contexts reject missing,
changed or downgraded bindings before building domain/model packets. They parse and
hash one profile-byte snapshot. A concurrent edit cannot substitute a hash for
different parsed configuration data. Manifest changes during context construction
or before engine dispatch also refuse, without incrementing the engine-call count.
Legacy profile selection records retain their prior shape; frozen compatibility
fixtures are reproduced from actual source on both hosts.

## Measured checks

| Exact-source lane | Result |
|---|---|
| Local targeted semantic/profile/intake/resume/bridge/compatibility | 232 PASS, 112.601 s |
| Release/legacy quality/OSS gates | 29 PASS, 8.872 s |
| Omniverse2 native client/profile/preflight/compatibility | 72 PASS, 2 initial missing-input SKIP, 4.098 s |
| Same two skipped cases after restoring existing owner inputs | 2 PASS, 2.033 s |
| AFO/local-autonomy integration | 75 PASS, 10.413 s |
| Actual namespace-isolated intake + semantic context + independent preflight | PASS, 12 engine requests, 0 model calls, 10.945230 s |

The targeted lane excludes two unchanged Frama-C/target-oracle tests already
measured at a74baa9; this is not the full inherited suite. Native owner inputs
were copied only from the preserved existing checkout, verified unchanged and
kept git-ignored. No vendor contents or private Rust implementation are published.
The two missing-input skips remain in their original result, with the later
passing run recorded separately.

New candidate **WWDG-LL-v02-002** was prepared via the actual
`workorder.run(..., intake_only=True, profile=...)` path inside the existing
private network namespace. Actual model identity and loopback/provider/isolation
checks passed; the ST target-compiler intake is ACCEPTED. Actual Context loads
the frozen profile; all12 mandatory operations also pass independent contract
materialization. The profile hash is
`3a446c7d17694ab7504a69ff0bb2e0478990a88641c62125695162d43e116315`.
The shared configuration/services records have identical before/after hashes.
Only sample telemetry was appended in the bounded metering window; no inference
record appeared. No Fabro product job was launched. No deployment was activated.

Factual PASS experience was retained with **NO_NEW_LESSON**, zero model tokens,
zero qualified lessons and no measured benefit. The intake wall measurement
excludes subsequent experience consolidation; no comparable cost/benefit claim.

Known unbound admission prerequisites:

- Current signed product execution authority. Available protocol grants do not
  cover the new product continuation; an existing reference was requested.
- Cumulative mission continuation retaining all historical executions, expenditure
  and uncertainty. Known observed minimum is **16 requests,49,697 input +7,757 output
  tokens =57,454 tokens**, from Job050 WWDG and its recorded diagnostic response.
  This is a lower bound, not an independently established usage ceiling or a fresh
  allowance. Neither grant renewal nor mission registration/reset occurred.

The profile-selection preparation prerequisite is now satisfied, while the
candidate remains **NOT_ADMITTED**. All previous candidates/archives and spent
diagnosis studies remain intact. Full driver correctness, role capability and
self-healing require separately authorized bounded execution and unchanged gates.
Private whole-workspace regression still needs16 missing original evidence inputs.
Formal Feature014 completion remains30/58; no full DA-T036 acceptance is claimed.

## Commands and evidence

From the exact checkout, with loop10 state/events/TMPDIR/basetemp/JUnit paths,
source `scripts/forge-env.sh` then restore `PYTHONPATH=$FORGE_REPO_ROOT/factory/python`.
Set separate complete old and new pin documents through
`FORGE_SAFEC_ENGINE_PIN`/`FORGE_SAFEC_V02_ENGINE_PIN`.

```sh
python -m pytest -q factory/python/tests/test_da014_v02_profile.py factory/python/tests/test_da014_required_preflight.py factory/python/tests/test_lrtx_profile.py factory/python/tests/test_lrtx_v2_profile.py factory/python/tests/test_lrtx_compat.py factory/python/tests/test_lrtx_v2_swe1.py factory/python/tests/test_brownfield_resume.py factory/python/tests/test_safec_bridge*.py -k 'not wp_proves_each_register_effect and not target_oracle_on_the_iwdg'
python -m pytest -q factory/python/tests/test_m7_governance_release.py tests/test_gates.py tests/test_oss_pipeline.py
```

Native pytest selects new profile/preflight/client tests plus v2 profile and
compatibility tests. The restored-input run uses
`pytest factory/python/tests/test_lrtx_compat.py -k current_tree_reproduces`.
The native private executable harness and exact source are retained at
`/mnt/data/forge-c/inspector-014-b309039/wwdg-024a3fa/{native-intake.py,repo/}`.
Its existing output/order refuses overwrite. It is intake-only, with a120-second
outer deadline and existing60-second mandatory preflight budget, never an
autonomous scheduler, admission bypass or product-run command.

[Native intake and bindings](intake-result.json), [regression scope/results/hashes](regression.json),
[factual learning disposition](learning-capture.json), [owner input-copy metadata](compat-inputs.json).


The next source gap was found while tracing later phases: assurance.safec_oracle,
register_wp and mutation still rebuild the legacy default domain, and reconstructed
validation objects discard profile metadata. New-profile artifacts therefore cannot
yet reach all downstream gates. This requires compatible version propagation and
independent positive/tamper verification before model dispatch; the intake-only
measurement does not claim these later consumers passed.
