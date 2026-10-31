# Assertion identity repair without regrouping predicates

Implementation revision: `6a4721ecbef8c85326dfd101811c232f6258174e`.
Parent: `dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf`.

The fresh06/fresh07 native records already show Qwen responding to duplicate
CHECK IDs by grouping predicates. That changed evaluation order and diagnostic
localization; it was not an assertion-preserving metadata repair. Historical
sources, findings and qualifications remain unchanged. See the protected
[fresh06](../fresh06-unit-history-20261031/README.md) and
[fresh07](../fresh07-unit-history-20261031/README.md) histories.

A separate deterministic factory defect is reproduced here: two static
`CHECK("UT-001-RESULT", ...)` call sites previously passed the duplicate-ID
check, which recognized numeric-only IDs. The updated lexical scan counts the
complete literal ID, including suffixes and forms such as UT-001a, across test
files. Comments and string/character literals are not extra assertions. Distinct
UT-001 and UT-001-RESULT remain valid. This does not prove runtime coverage,
expand macros or qualify the preprocessor's active branches.

The existing unit/integration MCP runner retains actual compiler/executable
results, protected test history and undeclared-change checks. Failed predicates
still fail with unique IDs. The shared native LL/HAL unit-author prompt and
metadata diagnostics now request unique suffixes, existing trace links and
ID-only correction when only metadata fails. They explicitly forbid combining
or removing assertions to fix IDs. No automatic source/test rewrite is added.
Qwen following this guidance, and its live benefit, are NOT_RUN.

## Verification

- Initial seven-case regression: **3 PASS / 4 FAIL**, including a real MCP host
  run that incorrectly returned PASS for duplicated suffixed IDs. Two failures
  establish absent LL/HAL prompt guidance; one establishes the missing scanner
  helper. This initial test version predates the final fixture expansion.
- Final exact revision: **90 PASS / 1 SKIP / 0 failures / 0 errors**, 91 unique
  cases, 34.320 s. The single inherited skip is live Fabro disabled. Three
  synthetic Robot target executions were deselected by `-k 'not real_robot'`;
  they are not claimed as tested here. All compiled C is deliberately authored
  fixture code, never Qwen output or product qualification.
- Ruff for the two changed source files and new test: PASS.
- Static spec mapping (58), contracts (6 schemas / 38 fixtures), design (14):
  PASS. These are static consistency checks, not runtime qualification.
- Existing RCC graph-golden mismatch and scheduler import-order findings were
  not addressed or rerun in this cohort. No entire-repository green claim.

Exact command/environment, immutable JUnit receipts, source/test hashes and
static output are in `verification.json` and the attached files. Counts overlap
prior cohorts and must not be added to them. Trace: supports DF-FR-008/012/016,
DF-T007 traversal and DA-T029 compatibility work; no original DA task is newly
closed.

## Runtime and next execution

This change is inactive on Omniverse2. The ten-hour grant ended; no inference,
provider restart, deployment or grant renewal was performed for this fix.
The historical cohort remains 2/3 scoped functional qualifications, strict
release blocked, full LL/HAL and autonomous self-healing unproven. Before a new
live retry, retain cumulative mission accounting, establish a valid new bounded
execution window and activate the tested fixes through the existing path.
Do not replace the old third trial or rewrite its stop outcome.
