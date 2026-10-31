# Export historical test sources through the existing finalizer

**Real native test metadata correction succeeded; factory self-healing and the
full delivery milestone are not established by this episode.**

Native01M67ETTPXS1Q73QPMQ98DNJX0/sourcea34fdd85 first ran its host unit
executable at23:40:08UTC. Its30checks reused only five IDs, so the deterministic
tool rejected the metadata despite no runtime assertion failure. Qwen edited
the test and reran at23:42:27: PASS, with30distinct valid IDs for the same30checks.
Protected content-addressed snapshots show code unchanged after ignoring only
comments, whitespace and UT identifier literals; preprocessor lines and product
code hash are unchanged. The independent CRC implementation remains SHA
855f53a6b3f90d83e60e03aacba50e953e9e3a2827c3730d6ae6746fff46b173,
with zero implementation corrections. No operator code/source/model steering
was supplied. This is bounded job-local test correction, not an invented repair
incident, promoted lesson, independent model correctness proof or CRE recovery.

LLVM subsequently reported100%line/function/region coverage on the host slice;
branch/MC/DC metrics were null. These are host measurements, not target or
physical-hardware coverage. Later test-author/report-author versions and their
results remain separate; the two exported snapshots bind the first FAIL→PASS.
The remote protected hashes and local copies match. See
[native receipts and snapshot audit](native-unit-episode.json),
[first failed test source](failed-test.c), and [first passed version](passed-test.c).

This exposed an actual export omission: the existing finalizer copied current
tests and raw tool logs, but omitted `evidence/test-integrity.jsonl` and the
historical `.forge-run/test-snapshots` sources. Offline reviewers could not
reconstruct the failed version from the review archive alone.

The finalizer now exports the existing raw log, every referenced hash-verified
snapshot and an explicit integrity index under `verification/test-history/`.
Missing, corrupt, symlinked or invalid references and malformed history remain
visible and produce an existing major finding/BLOCKED package. Valid historical
FAIL→PASS records do not block an otherwise qualified package. Jobs with no
history retain their existing behavior. No new scheduler, memory store, lesson
authority or release waiver is added; sealed old archives remain write-once.

Six synthetic package regressions failed before the change: missing history
in an otherwise READY archive, plus five integrity faults incorrectly yielding
READY. Afterwards6PASS; inherited finalizer/delivery/product-outcome cohort53PASS,
zero failures/errors/skips. The unchanged v0.3 packager's seven regressions also
PASS. Cohorts overlap; do not add the focused count. The source-specific exact
post-commit receipt is recorded separately. Failed raw JUnit is retained as gzip
with a whitespace-normalized readable view and explicit representation hashes.

```text
python -m pytest factory/python/tests/test_release_test_history.py -q
python -m pytest factory/python/tests/test_release_test_history.py factory/python/tests/test_m7_governance_release.py factory/python/tests/test_pipeline_demonstration.py factory/python/tests/test_delivery_first.py factory/python/tests/test_da014_product_outcomes.py -q
python -m pytest factory/release-manager/tests/test_packager.py -q
```

All synthetic framework tests ran on loop10, not as Qwen trials. The real model
episode and tests ran only on Omniverse2. This export fix is **NOT_DEPLOYED**;
the active sourcea34fdd85 and current package generation remain unchanged.
DF-M1, three fresh comparable trials, full LL/HAL success, release eligibility,
learning benefit and 24/7 availability remain separate open qualifications.

Traceability: this increment supports DF-T008 and the sealed-package regression
parts of DA-T021/DA-T029. It does not close their remaining qualification or
change any original Feature014 task checkbox.
