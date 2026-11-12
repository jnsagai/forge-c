# Explicit typed-register interface in the existing SWE.3 verifier

Exact tested implementation: `b8ecd2695b832c4905c5f538fda5b2c2193f8650`.
Owner requested that this increment be finished and work stopped; see
[Claude handoff](../../../specs/014-durable-local-autonomy/HANDOVER-CLAUDE-20261031.md).

The historical native CRC outputs use the declared typed pointer API, whereas
the legacy SWE.3 checks require a singleton register array/numeric definitions.
The explicitly selected `delivery_first.register_interface` now describes the
frozen primary manual, device header, declaration-only API header, C type and
register members. The existing verifier compiles offset/width/volatility/API
assertions with the selected target compiler and stores hash-bound proof in
the existing artifact store. Selected invalid contracts fail. Unselected
manifests retain legacy checks. No new scheduler, authority or memory store.

The manual is reconstructed from frozen primary input, not mutable derived
sections. The generic module contains no CRC/STM32 facts. A synthetic PORT
16-bit interface with differently named manual, member, API and header also
passes. Incorrect offsets, widths, missing volatility, signatures, members,
register identities and C syntax fail. Changed frozen input fails. The real
MCP aggregate uses the same checks. A behaviorally wrong candidate passes layout
but fails the independent oracle, showing why layout is not a correctness claim.

## Measured checks

- Focused final test version: **24 passed**, zero skips/failures/errors.
- Exact-revision ten-file cohort: **141 passed, 3 skipped**, zero failures/errors,
  72.174 seconds, 144 collected. See `exact.xml` and `exact.stdout`.
- Three skips require unavailable local copyrighted GPIO/TIM primary manuals
  (names/reasons in JUnit); no fabricated inputs or waived failure.
- Ruff on changed Python: PASS.
- Static design: 14 PASS. Specification: 58 requirement/task/acceptance entries.
  Contract fixtures: 16 positive/22 negative PASS. These are **static checks,
  not runtime qualification**.
- Exact commands, environment and static outputs: `verification.json`.
  Relevant source/test/validator hashes: `source-files.sha256`.
- `before-initial-22.xml.gz`: original 14 FAIL/8 PASS draft receipt.
  `after-initial-22.xml.gz`: initial implementation 22 PASS. These are earlier
  test versions. Final adds two cases and fixes a formerly ineffective derived
  slice mutation, now asserted nonempty. Do not present the old and final
  counts as an identical-suite comparison. Original decompressed hashes are
  retained in `verification.json`.
- `precommit-regression.xml`: 141 PASS/3 SKIP, 72.700 seconds on identical
  implementation files. Exact source was rerun after commit, not inferred.

Run `bash evidence/014-durable-local-autonomy/typed-register-interface-b8ecd269/reproduce.sh`
from a checkout with these source hashes, existing loop10 toolchains and inputs.
It runs local synthetic fixtures only; live Fabro is disabled.

## Limits and retained failures

This extends only the existing explicit Delivery-First QM path. It does not
qualify an arbitrary target, infer access permissions beyond the compiled
declared type, prove functional correctness from signatures, or make a release,
ASPICE/certification, self-healing or availability claim. Existing quality gates
and old failed runs remain intact. No original DA task is newly completed.

The example now adds a fifteenth frozen input `IDR-API.h` to express its existing
contract. Future native work needs a new frozen intake/cohort and correctly
bound current execution scope. The old 14-input cohort remains 2/3; DF-T010
remains NOT_COMPLETE. Historical packages/grants were not modified.

No native model run, generated-model C execution, live deployment, grant renewal
or signing occurs here. Actual Qwen/native protocol effectiveness is NOT_RUN.
The factory remains at its last observed STOPPED7; old grants expired.
Known inherited RCC graph-golden/scheduler import-order lint findings remain
outside this increment; the entire repository suite was not rerun. Full LL/HAL,
learning benefit and 24/72/168-hour campaigns remain unproven.
