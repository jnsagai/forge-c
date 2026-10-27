# Full collection replay through bounded batches

Exact runtime revision: **bf05e59b968f01abc6bc8ba60f8d369237e1c804**.
This advances backlog A2 and prerequisites for DA-T016/017/026/046/049/052.
It closes no formal acceptance case or task checkbox. The ledger remains **30/58**.

The existing collector verifier formerly refused once all capture files together
exceeded 128 MiB. `Collector.verify_batches()` now checks one original sample at a
time, always starting at zero. The five source files remain individually limited
to 16 MiB. The frozen sample allowance and 128 MiB soak-log bound remain enforced.
It verifies the receipt against the hash in the frozen log using the same bytes
for parsing and hashing. It does not accept a caller's cursor or success record.

Partial results remain SOURCE_REPLAY_PARTIAL; only the final checked prefix yields
SOURCE_REPLAY_PASS. Collection can append between batches. The final result binds
the original canonical history hash, and campaign reports refuse a different
window. An interrupted verifier starts from zero next time, preserving all history
and allowances. No durable checkpoint, scheduler, store or authority was added.

| Exact-source lane | Result |
|---|---|
| Local observer/audit/control/collection/AFO integration |393 PASS, 38.290s|
| Release/legacy gates |29 PASS, 11.104s|
| Real local fixture source volume |134,234,326 bytes across 24 source files; all 8 samples verified|
| First broad Omniverse2 lane |TIMEOUT at 180s; incomplete, no JUnit verdict|
| Focused native continuation lane |18 PASS, 40.713s; new cases only|

The source-volume measurement counts each capture file once. It excludes repeated
semantic reads and is not physical I/O or engineering expenditure. Generated spaces
and synthetic fixture facts contain no model prompts or vendor inputs. Each source
file and each batch stays bounded; the measured history crosses the previous
134,217,728-byte aggregate limit without dropping earlier evidence.

New cases cover partial-result refusal, fresh replay rejecting altered earlier
sources, corruption of a later capture, malformed receipt references, an oversized
individual file, collection during verification, log rewrite/truncation/partial
tail, report-window races, empty history and the actual former byte boundary.
The existing crash/allowance/host-cursor cases also pass locally.

The first local exact-source run retains 392 PASS / 1 FAIL because FORGE_FABRO_BIN was
unset. The corrected environment passes 393. The initial release invocation retains
exit 4 / NOT_RUN for incorrect test paths; the corrected 29-case run passes. No failed
run was relabeled. Native waiting was observed as uninterruptible
jbd2_log_wait_commit; this is not a test assertion failure or evidence of model
failure. The wrapper and original pytest process were confirmed terminal before
the separately bounded focused lane was started. The original native timeout stays
in the record regardless of the focused result.

Local affected command, from the exact clean source and existing forge-env:

```sh
python -m pytest -q factory/python/tests/test_da014_collection_continuation.py factory/python/tests/test_da014_operational*.py factory/python/tests/test_da014_audit*.py factory/python/tests/test_da014_fault_observer.py factory/python/tests/test_da014_control*.py factory/python/tests/test_afo_local_autonomy.py factory/python/tests/test_da014_integration.py --basetemp="$FC014_OPS/collection-bf05e59-qualified-tmp" --junitxml="$FC014_OPS/collection-bf05e59-qualified.xml"
python -m pytest -q factory/python/tests/test_m7_governance_release.py tests/test_gates.py tests/test_oss_pipeline.py --basetemp="$FC014_OPS/collection-bf05e59-release-qualified-tmp" --junitxml="$FC014_OPS/collection-bf05e59-release-qualified.xml"
```

The focused native command uses the exact same source:

```sh
python -m pytest -q factory/python/tests/test_da014_collection_continuation.py --basetemp="$Q/collection-bf05e59/focused/pytest-tmp" --junitxml="$Q/collection-bf05e59/focused/native-tests.xml"
```

The focused native fixture verifies 134,233,135 source bytes. Native results do
not qualify the broader timed-out lane.

Set FORGE_REPO_ROOT/PYTHONPATH to the exact checkout, PYTHONDONTWRITEBYTECODE=1,
FABRO_NO_UPGRADE_CHECK=1, and TMPDIR/state/events/basetemp/JUnit/cache paths on
loop10. The local pin is the existing native Fabro executable used for validate;
no Fabro workflow or inference was launched. The native harness, bundle and logs
are retained in the same operations directory. Native source and outputs live
under inspector-014-b309039/collection-bf05e59 on Omniverse2's data volume.

[Regression record](regression.json) and [focused native result](native-focused.json) retain JUnit hashes and
fixture byte accounting. Native pytest is bounded to 180 wall seconds, 120 CPU
seconds and 3 GiB address space, with an outer 210-second wrapper. No native fault,
service command, reboot, mount loss or Qwen request was dispatched.

This verifies collection metadata/source replay. Kernel compound-event replay still
has its independent 128 MiB limit. Full host/control/write/service correlation and
all-channel coverage remain incomplete; interventions are UNKNOWN. The log bound,
retained source availability and actual workload/fault oracles remain prerequisites.
No 24/72/168-hour campaign, role qualification, product success, self-healing or
learning benefit is established. WWDG HSI/access-model and execution-authority
blockers remain separate. Inspector/parked-task decisions remain in force.
