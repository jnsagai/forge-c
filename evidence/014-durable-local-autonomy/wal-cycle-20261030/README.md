# Conductor journal I/O correction — prospective, NOT_DEPLOYED

Exact source **a7804054744ce3d471d6e15c60a205610755503a**.
Live reasoning comparison stays frozen on12e601e4. No source, model request,
cadence, case, oracle, budget or active experiment tool was changed remotely.

Reasoning-off model requests took approximately3–4seconds, but completed trials
took70–165seconds. A [40-second read-only native sample](native-readonly-controller-sample.json)
of the same live Conductor process observed93/200 journal-commit waits,98/200
uninterruptible sleep samples and0.75% of one CPU core. It attributed about21MiB
writes/cancelled writes to that process. This does not attribute every wait to one
database, prove whole-host utilization, or qualify a runtime speed improvement.

The existing Store opens/closes a SQLite connection for each transaction. The last
connection closing repeatedly checkpoints/unlinks WAL. An [isolated local test](local-storage-comparison.json)
of32 independent transactions using the actual Store measured0.142→0.079seconds,
1.80x in this single serial sample, with write bytes1572864→266240. Both retained
FULL synchronization and passed reopen row/hash/integrity checks. This is a local
storage observation, not an Omniverse2 or full-pipeline performance claim.

`Store.wal_session()` holds one idle connection only for an existing Conductor
cycle. It holds no transaction or writer lock and exposes no connection to its
caller. Each existing transaction still creates its own connection, validates the
data device and commits independently with synchronous=FULL. Existing WAL automatic
checkpoint behavior and the end-of-cycle close remain. Success/failure closes the
session; no idle connection survives between cycles. Durable profiles opt in via
the existing durable-autonomy mode; legacy cycle behavior and DISABLED/no-database
behavior are preserved. No new store, scheduler or authority; no fsync reduction,
long transaction, new inference slot, verifier, budget, governor or quality change.

Tests and boundaries:

- [Affected27PASS](affected-27-junit.xml), no failure/error/skip, overlapping broader
  coverage: independent reader/writer visibility, no open keeper transaction,
  FULL pragma, keeper closure, rollback retaining prior commits, real child process
  abrupt exit before keeper close, recovered16 committed receipts/integrity,
  Conductor success/exception cycle boundaries, absent database and legacy mode.
- [Broad group](broad-196-failure-redacted.xml):195PASS/1 child-namespace import
  failure from the invocation's relative PYTHONPATH. The exact failed case
  [reranPASS](corrected-namespace-junit.xml) with the absolute source path. The
  original failure is retained; this is not a fabricated green196-case run.
  [Exact source and private/redacted hashes](test-provenance.json).
- Ruff/diff checks pass. Process-crash recovery is tested, not physical power-loss
  durability or native24/72/168h operation.

Local commands use the existing loop10 B/A3 roots and B/venv/bin/python:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH="$W/factory/python" FORGE_DATA_ROOT="$B" FORGE_FABRO_LIVE=0 TMPDIR="$A3" \
"$B/venv/bin/python" -m pytest -q -p no:cacheprovider \
 factory/python/tests/test_da014_wal_session.py \
 factory/python/tests/test_afo_m2_queue.py \
 factory/python/tests/test_afo_m1_services.py \
 factory/python/tests/test_afo_m6_operations.py \
 factory/python/tests/test_da014_integration.py \
 factory/python/tests/test_da014_provider_recovery.py \
 factory/python/tests/test_da014_operational_facts.py \
 factory/python/tests/test_da014_kernel_continuation.py
```

The broad run used relative PYTHONPATH=factory/python; the corrected isolated case
used the absolute value above. This distinction is retained in the receipts.

[Exact native qualifier](qualify-native.py), [maintenance window](qualify-window.py),
[after-comparison waiter](qualify-after-comparison.py), [collector](collect-qualification.py)
are staged. Only completion of all none/medium/xhigh cohorts, actual execution/
request/verifier quiescence and unchanged RUNNING94 permit PAUSED95 CPU checks,
four CPUs/8GiB/no swap/no network/GPU/owner/SSH. Resume only the owned unchanged
pause96. No source activation or extra inference. A real check-only probe refused
RUNNING94 (expected PAUSED95), no tests/intent/deployment effects. Newer intent is
preserved. Native source qualification and native performance benefit are NOT_RUN.

The actual runtime remains12e601e4 afterward. A later deployment/performance test
requires its concrete bounded source scope. Formal Feature014 remains30/58; no
new task IDs closed, LL/HAL/role/learning/availability acceptance remains unproven.
# Native qualification update — original failure retained

Exact source `a7804054744ce3d471d6e15c60a205610755503a`: native306tests,
305PASS/1FAIL, zero errors/skips. The failure is
`test_afo_m1_services.py::test_rendered_units_are_complete_bounded_and_preflighted`;
`services.verify` returned false in the isolated verifier. [Original JUnit and
provenance](native-original/qualification-wal-session-a7804054-epoch95-v1/).
The candidate was NOT_DEPLOYED, runtime remained12e601e4. Its owned PAUSED95 was
resumed only after verifier quiescence, to RUNNING96; model requests0.

Retained diagnostics distinguish fixture errors: v1 used an absent Fabro path;
v2 showed missing private XDG runtime directory; v3 confirmed the isolation helper
deliberately strips inherited XDG_RUNTIME_DIR. v4 created a private runtime directory
inside the verifier and read-only exposed the actual Ollama executable for unit
ExecStart validation; `services.verify` then returned ok=true. No GPU/model weights,
network, credentials, live DB mutation or service installation/start were involved.
This diagnoses qualification prerequisites; it does not turn the original306run
green or establish native performance benefit. Corrected qualification uses a short
private `/tmp/forge-runtime` path and preserves the identity/network/filesystem boundary.

The later product-binding candidate includes this WAL change; its separate native
results belong to its exact revision. Earlier NOT_RUN/queued checkpoints below are history.
