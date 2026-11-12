# WWDG opt-in semantics: measured capability unblock

Owner approval: **“I - Approve the scoped SafeC/Forge-C extension”**, 2026-10-27.
Exact Forge-C runtime: `a74baa91f15383012b997461c551b1e1c066e279`.
Private semantic engine source: `c241a9a7ca7f04270b8de182719ec64555f04207`.
Only interface versions, counts and hashes are public; private Rust source,
vendor domains and implementation logs remain private.

The historical profile supported three of twelve mandatory WWDG forms. The opt-in
`register-io-0.2` / domain 3 supports **12/12** against those frozen source facts.
All **36** validation, oracle-derivation and obligation-derivation operations passed
independent Forge-C materialization. Early mandatory-operation preflight passed.
Illegal RS clear, illegal RC_W0 value, out-of-range counter and an actually
engine-evaluated legacy-domain mismatch were rejected. An additional client
domain-binding refusal is retained.

The original summary's `engine_calls` field counted client bridge calls.
Use [reconciliation.json](reconciliation.json) for final accounting:
**53 bridge requests, 52 engine run requests, one client refusal, zero model calls**.
The initial engine phase took 48.794926 seconds. Native client tests separately
passed 35/35. These are not Qwen trials or driver product attempts.

| Check at exact source | Result |
|---|---|
| Forge-C affected/inherited semantic/peripheral/brownfield tests | 256 PASS, 1 SKIP, 433.012 s |
| Release and legacy quality/OSS gate tests | 29 PASS, 9.822 s |
| Omniverse2 new native client/preflight/WWDG tests | 35 PASS, 1.830 s |
| Private register core | 31 PASS; formal test explicitly run separately |
| Private bridge, legacy and opt-in feature separately | 33 PASS each |
| Actual CBMC 6.11.0 | 5 correct programs proved; 10 semantic/frame mutants rejected |
| Affected private fmt/Clippy | PASS, warnings denied |
| Whole private workspace checks | FAIL: retained-evidence replay (16 original inputs missing); Linux lint fixed |

Formal scope is one-call 32-bit register images, with stated reserved-reset
assumptions and no concurrent hardware transitions. Timing, interrupts, silicon
behavior and driver correctness remain separate obligations. The original CLI failure source matched the base; nonfunctional cleanup3256cb6
subsequently passes whole-workspace fmt/Clippy. Exact3256cb6 workspace results:
264 PASS/1 FAIL;16 retained original inputs are missing, not regenerated or waived.
No passing baseline replay is claimed. Raw failed runs remain retained.

The initial learning harness refused an unsupported outcome label after the checks
completed. A separate reconciliation captured factual PASS / **NO_NEW_LESSON**;
no qualification requests were replayed. Zero qualified lessons, no measured benefit.
Earlier pin/environment/glob mistakes are recorded in [regression.json](regression.json).

The new profile is explicit, separately versioned and opt-in. Default profile/pins,
historical workorders, expenditure and quality gates are preserved. New WWDG orders
freeze twelve mandatory operations; actual engine preflight runs before author
packets or model calls. Missing capability blocks only that engineering job.
Changed/removed mandatory scope is refused. Legacy schemas remain unchanged.
This reopens only the relevant preflight portion of parked DA-T036; its full
acceptance case is still unmet and the Feature014 ledger stays **30/58**.

Candidate `WWDG-LL-v02-001` is **PREPARED_NOT_ADMITTED** on Omniverse2.
Its freshly prepared domain independently passed all12 mandatory forms in7.460138s
(12 additional engine requests,0 model calls), with its own factual NO_NEW_LESSON
disposition. Thus extension studies total65 bridge requests/64 engine run requests,
in addition to the separately counted35-test native regression lane.
The original ST header and dependencies passed target-compiler intake after PATH
was corrected; the initial BUILD_NOT_RUN is retained. See [preparation.json](preparation.json).
No available signed qualification grant names this product order. Its cumulative
mission continuation and explicit isolated engine-profile selection also need
binding. Job050's WWDG floor is 15 requests / 43,438 input / 6,700 output tokens,
plus all later diagnosis expenditure and uncertainty. Do not reset that history
or silently renew protocol grants. [Available grant scope assessment](available-grant-scopes.json).

## Repeatable commands and retained native tooling

Run Python tests from exact runtime source on loop10, sourcing `scripts/forge-env.sh`
then restoring `PYTHONPATH=$FORGE_REPO_ROOT/factory/python`. Keep TMPDIR, pytest
basetemp and JUnit paths on loop10. Set `FORGE_SAFEC_ENGINE_PIN` to a complete old
pin document (including its schema); set `FORGE_SAFEC_V02_ENGINE_PIN` to the separately
hash-verified new pin. No implicit fallback or pin replacement.

```sh
python -m pytest -q factory/python/tests/test_safec_bridge*.py \
  factory/python/tests/test_da014_required_preflight.py \
  factory/python/tests/test_peripheral*.py \
  factory/python/tests/test_brownfield_resume.py \
  factory/python/tests/test_lrtx_v2_swe1.py
python -m pytest -q factory/python/tests/test_m7_governance_release.py \
  tests/test_gates.py tests/test_oss_pipeline.py
```

On Omniverse2 the exact cloned source is
`/mnt/data/forge-c/inspector-014-b309039/wwdg-a74baa9/repo`; native pin,
`native-qualification.py`, `reconcile.py`, `prepare-only.py`, XML and logs
are in its parent. The original qualification output refuses overwriting/re-dispatch.
The immutable study is `runs/wwdg-v02-native-a74baa9` beneath the same isolated root.
Do not rerun reconciliation into existing control/output paths.

Native test command (new pin env above, isolated state/events/TMPDIR):
```sh
python -m pytest -q factory/python/tests/test_safec_bridge_v02.py \
  factory/python/tests/test_da014_required_preflight.py \
  factory/python/tests/test_peripheral_wwdg.py
```

Next execution: reconcile the product continuation's accumulated allowance and current
authority, bind the explicit candidate engine/profile, then run one bounded WWDG job
through unchanged gates. Broader private regression failures remain open. No driver
READY, local-role qualification, self-healing, learning benefit or 24/7 availability
is inferred from this capability result.

