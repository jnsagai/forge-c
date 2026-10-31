# Bounded kernel-event replay and crash-safe scratch

Exact runtime: **b321a8766947fa5f5174bbb4f61f5d05720b22d6**.
This advances A2 and the prerequisites for DA-T016/017/026/046/049/052.
No formal checkbox is closed; Feature 014 remains **30/58**.

The existing host-audit command now has an explicitly frozen opt-in path for
replaying long retained byte/event histories. It rechecks every original capture
from zero, preserves interleaved and late event records, and checks duplicates
across the whole prefix. The existing EventReplay rules reconstruct each event.
Selected records are grouped in bounded disposable scratch, with process-local
integrity checks rejecting altered, missing or duplicated rows. This adds no
runtime knowledge store, checkpoint authority, scheduler or model permission.

| Exact-source lane | Result |
|---|---|
| Local observer/audit/control/collection/AFO integration |521 PASS, 39.908s|
| Release/legacy gates |29 PASS, 10.150s|
| Omniverse2 new kernel-continuation cases |81 PASS, 28.073s|
| Actual local generated source |134,224,064 bytes, 17 ranges|
| Actual native generated source |134,224,080 bytes, 17 ranges|
| Read-only native host preflight |BLOCKED; kernel visibility, continuous bus coverage and authenticated-control correlation|

Both long-source cases retain one compound event across all ranges, five unique
records and 2,095 duplicate records. They finish with no pending event/line and no
uncaptured final source bytes. The legacy reader still refuses this source at its
unchanged 128 MiB bound. These are generated native-format fixtures with real file,
descriptor, range, hash and process behavior; protected-root ownership is simulated.
They do not qualify an actual complete kernel audit window.

The new cases also cover UTF8 at byte boundaries, 11,000 distinct groups, completion
and rejection of late PATH records after 10,000 other groups, input/source/hash/boot
bindings, malformed references, output-page chains, privacy, finite resource limits
and original serialized metadata accounting. Raw audit command/argv/path fields
and unselected rule keys do not enter scratch or exported facts.

Crash tests hard-kill only owned fixture processes during initialization and active
sorting. They verify restart from empty scratch, actual spilled storage with zero
links, and preservation of live/unowned/symlinked/hard-linked/exposed files. One
existing-style lock and a small slot-ownership marker remain; the working B-tree
is unlinked after initialization and its storage is released by descriptor closure.
An initializer crash leaves only one reclaimable owned slot. No Conductor/service,
reboot or mount fault was injected, and this is not RCC/self-healing qualification.

Historical results remain separate. The initial c4b601c implementation passed
513 local /29 release /73 native cases before the crash-storage refinement.
An uncommitted descriptor-path prototype then failed its hard-kill test: SQLite
created a named alias rather than using the anonymous inode. The corrected slot
implementation initially hit 26 outdated cleanup assertions, which expected no
control files at all. Final tests explicitly allow only the two bounded control
files and reject named aliases; all81 new cases pass. Original logs/XML/fixtures
remain under the operations directory, with hashes and scope in regression.json.
Earlier collection-native timeout evidence is also retained in its own checkpoint;
these81 passes do not qualify that older broader lane.

Exact local affected command, from forge-env and the clean runtime checkout:

```sh
python -m pytest -q factory/python/tests/test_da014_kernel_continuation.py factory/python/tests/test_da014_collection_continuation.py factory/python/tests/test_da014_operational*.py factory/python/tests/test_da014_audit*.py factory/python/tests/test_da014_host_audit.py factory/python/tests/test_da014_fault_observer.py factory/python/tests/test_da014_control*.py factory/python/tests/test_afo_local_autonomy.py factory/python/tests/test_da014_integration.py --basetemp="$FC014_OPS/kernel-b321a87-exact-tmp" --junitxml="$FC014_OPS/kernel-b321a87-exact.xml"
python -m pytest -q factory/python/tests/test_m7_governance_release.py tests/test_gates.py tests/test_oss_pipeline.py --basetemp="$FC014_OPS/kernel-b321a87-release-tmp" --junitxml="$FC014_OPS/kernel-b321a87-release.xml"
```

Native qualification uses the exact clean SDK and:

```sh
python -m pytest -q factory/python/tests/test_da014_kernel_continuation.py --basetemp="$Q/kernel-b321a87/pytest-tmp" --junitxml="$Q/kernel-b321a87/native-tests.xml"
```

Use exact FORGE_REPO_ROOT/PYTHONPATH, PYTHONDONTWRITEBYTECODE=1 and isolated
TMPDIR/state/events/basetemp/JUnit/cache paths. All local mutable files remain on
loop10. Native source/harness/attempt/summary/artifacts remain under
inspector-014-b309039/kernel-b321a87 on Omniverse2's data volume. The harness caps
pytest at180 wall seconds,120 CPU seconds and3GiB address space, with an outer210s
wrapper. Its terminal result is confirmed. Source bindings, limits and the CLI
are documented in [kernel-event-replay](../../../specs/014-durable-local-autonomy/kernel-event-replay.md).

[Regression record](regression.json), [native summary](native-summary.json) and
[read-only preflight](native-preflight.json) retain the measurements. Static
spec/contract/design/handoff validation is documentation evidence, not runtime
qualification. No full inherited-suite or full native host-audit qualification claim.

Next A2 work is native full-record/loss/window qualification and authenticated
actor/control/write/service correlation across all channels. Boot changes remain
blocked in this parser until their independent continuity evidence exists.
Interventions remain UNKNOWN. Product bindings, actual fault/work campaigns and
valid execution authority remain required. Driver/model-role success, learning
benefit, self-healing and 24/72/168-hour availability remain unproven. All model
requests/product attempts in this increment are0; no qualified lesson was invented.
No grant renewal, allowance reset, deployment, promotion or automatic merge.
