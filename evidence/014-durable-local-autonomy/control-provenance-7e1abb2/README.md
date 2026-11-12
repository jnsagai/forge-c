# Control provenance and bus parsing verification

Exact source: `7e1abb2849dfc6272a00c8b56f6be7a8ea0588d1`.

The initial 899-case core invocation exited 1: 846 PASS, 11 SKIP and 42 setup
errors, all caused by missing ignored ST documents in its worktree. It had zero
source assertion failures. All 22 reference document hashes were then verified;
the complete brownfield file rerun passed 45 tests. Two skipped permission cases
passed separately with an explicit private 0600 canary. The reconciliation script
checks artifact hashes, exact source revisions and individual JUnit identities:
**890 PASS / 9 SKIP / zero unresolved failures/errors across 899 unique cases**.
This is a reconciled cohort, not a single green full invocation. Original exit 1,
errors, skips, commands and rerun receipts remain in Git.

```bash
python evidence/014-durable-local-autonomy/control-provenance-7e1abb2/reconcile-cases.py
```

Release: 13 PASS. Actual Omniverse2 isolated tests: 62 PASS, plus finite user-bus
visibility PASS. Local history replay and seven isolated systemd cases PASS.
Independent CRE remains REJECTED/PROTECTED_PATH_CHANGE. Static spec/contracts,
14 design checks, handoff reconciliation and changed-source/test Ruff PASS
separately. Full inherited 1,840-test suite was not rerun on this revision.

The old synchronize function's reproduced ordering defect left database controls
running after newer STOPPED intent; existing admission still honored the intent.
The fix serializes a complete database transaction with the intent lock and emits
source/provenance receipts through the existing action/lifecycle ledger. Tests
cover concurrent resume/stop, SQL rollback, retained stop fencing, unavailable
process facts, bearer/OS authentication, credential privacy and legacy calls.
Native bus names are checked against normative grammar and representative native
library examples; unexpected names do not become intervention success flags.

Application provenance is not independent host verification. Observer ingestion,
native actor/control correlation, continuous/rotation-safe sources and complete
all-channel replay remain incomplete. Kernel/system-bus prerequisites and the
approved external fault window remain unavailable. No campaign, product success,
learning benefit, 24/7 availability, deployment, promotion or merge is claimed.
Formal task count stays 30/58; no new checkbox.
