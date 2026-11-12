# Delivery-First integrated verification — 30 October 2026

**Implementation verified; autonomous DF-M1 still NOT_PROVEN.** The active real
Qwen run and the external qualification below are different execution scopes.
All Qwen inference and first-candidate target qualification occurred on Omniverse.
Local work, caches and copied evidence reside on loop10.

## Source and test record

`d846ec82086e299f2acd88a24e1b2b6e234dc27f` fixes an observed measurement failure
on valid static header functions, binds every declared input and requires the
full declared API set. The valid pre-fix fixture failed three cases; the corrected
exact-source cohort passed85. The earlier exploratory invalid test fixture is
not counted as an implementation counterexample.

`58ef89b7c798b7fdeb05aef08813f1b26a24a6a9` integrates the independent target
oracle into the existing delivery verifier/finalizer; rechecks final bytes;
exports a JSON report and one-page scorecard; and resolves compiler/simulation
selection from frozen work-order adapters. Unsupported targets block explicitly.
Existing strict release behavior remains. The actual AFO role-trial preflight
now builds the selected demonstration graph, fixing a reproduced ambiguous
legacy generator route.

Two additional before-change failures exposed an inherited extra fix author
and out-of-sequence mutation permission. The Delivery-First graph now has only
three implementation visits, and the existing tool policy enforces their order
and completion. Subsequent authors can produce documents/tests but cannot
silently add another driver correction or another driver source file.

Exact-source regression command (pinned loop10 Python/toolchain environment):

```text
python -m pytest factory/python/tests/test_delivery_first.py factory/python/tests/test_simulation_declared_headers.py factory/python/tests/test_simulation_performance_authored.py factory/python/tests/test_pipeline_demonstration.py factory/python/tests/test_demonstration_repair.py factory/python/tests/test_t007_policy.py factory/python/tests/test_da014_product_role_trial.py -q
```

**103 PASS, one explicitly disabled live Fabro test skipped; zero failures/errors.**
The XML and `verification-record.json` retain the actual counts/skip. Cohorts
overlap and must not be added. Ruff and source diff checks passed. Specification
validation passed58mappings,6schemas/38contract fixtures; it is documentation
validation, not runtime qualification.

## Real first candidate: external target qualification

Origin native `01M6788GYKREQSS1YTZHS9N3TV`, source `beb48b49`, launched20:33:15UTC.
The native `write_file` and frozen first-candidate header share SHA256:
`511956a9345ca465b265a60214f16fb43c5d2395b18dfcf7fd4766a980cc29f5`.
The original in-loop check passed630preregistered host assertions and both
compilers. Its candidate and original chronology are in the earlier
[native evidence](../delivery-first-20261030/README.md).

The separate Omniverse verification at clean `d846ec82` copied that immutable
candidate, never edited the active workspace and made **zero model calls**:

| Case | Behavior | Cost | Outcome |
|---|---|---|---|
| Actual first candidate |351target assertions PASS |70write+70read samples; maximum2instructions and20virtual ns per API at100MIPS | PASS |
| Controlled read masked to8bits | FAIL | PASS | Correctly rejected |
| Controlled one-instruction allocation | Actual candidate behavior | FAIL | Correctly rejected |

Object-level flash16B, static RAM0B and maximum frame0B meet4096/64/128.
These are neither linked-firmware footprint nor call-graph stack guarantees.
The target fixture was authored externally **after** the first candidate; this
is post-hoc qualification, not a preregistered autonomous result for that job.
It is now a frozen input for future jobs. The complete measurement metadata,
raw tool logs and selected proof objects are in `omniverse-external/`; private
ELF blobs and authoritative manual contents were excluded from publication.
Transfer hashes were independently checked locally.

## Integrated verifier and packaging on Omniverse

At clean source `58ef89b7`, the separate model-free qualification invoked:

```text
/mnt/data/forge-c/production-local-014/venv/bin/python /mnt/data/forge-c/delivery-first-014-20261030-v1/qualify-delivery-integrated-58ef89b7.py
```

Actual results in [summary](omniverse-integrated/summary.json):

- The same real candidate passed the integrated host, target, simulation,
  performance and resource checks;351target assertions passed.
- Existing finalizer produced an integrity-PASS archive, functional PASS,
  **package BLOCKED**; SHA256
  `dce554349609770e867b25bded70cc0f2cc882747f2e63fee7fb88139a563423`.
- A later controlled wrong-read mutation failed the final-byte recheck;
  correction_count remained0, and the failing package was also integrity-PASS.
- Fixture/copied source did **not** gain native Qwen authorship or DF-M1.
  No inference, code repair or test overwrite was supplied to the active job.

`omniverse-integrated/` contains the actual script, immutable receipts, reports,
scorecards and checked transfer manifest. Its results are external qualification,
not new autonomous product executions or successful repeatability trials.

## Runtime and next execution

The real job retained `beb48b49`/profile2 throughout and finished **SUCCEEDED**
at21:43:09UTC, approximately4194seconds after launch. The product is
**BLOCKED57**, archive integrity **PASS**; SHA256
`f953209eefcf3c06a88281c93f4771653f9e01715e66875c9f6a4213557c93dd`.
Actual author/inspector attempts exist for all six phases; phase file counts
are6/3/3/3/0/6. SWE.5 missing artifacts remain explicit. The original delivery
report remains **INCONCLUSIVE** for complete functional verification.
Actual failures include64K context refusals, normal MCP header-only discovery,
the strict static-inline/register-map guideline and downstream test/artifact
failures. New fixes were **not** hot-patched into that job. Reported native
usage:610015input,209145output and4545363cache-read tokens; missing separately
reported reasoning is UNKNOWN, not proven zero. Gateway observations count246
response records, not a verified physical-generation count. All expenditure
and failure history remain; no fresh continuation may silently reset them.
The new native metadata reader was also exercised against this actual terminal
job: successful exact-content native write confirmed, and154339reported author
output tokens attributed through the protected node-role binding. This is a
subset of the209145total, not an additional token charge.
Production Conductor remains paused111; no expired production grant was renewed.
At21:43:31the physical provider slot was independently observed idle. Terminal
transport alone was not used as evidence of quiescence. Terminal metadata and
phase hashes are in `native-terminal/`; the complete archive is copied privately
to the owner's loop10 inspection directory by the existing collector.

The next source-pinned trial must use the existing AFO admission, mission,
request and native-reconciliation path with real model/provider ownership.
The observed host namespace has external connectivity; it does not satisfy the
profile's `namespace_denied` requirement. The existing LRTX user/net namespace
mechanism is available (actual unshare probe passed); using that mechanism is
required, rather than pretending host execution proves network isolation.
Reconcile native terminality **and** physical provider quiescence before any
new inference ownership handoff. No competing job was started here.

No three-run repeatability, HAL dependency, full RCC, ASPICE acceptance, safety,
production, general-target, learning-benefit or24/7 result is established.
See [the task ledger](../../../specs/014-durable-local-autonomy/DELIVERY-FIRST-IMPLEMENTATION.md).
