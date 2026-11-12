# Structured SWE.6 measurement routing

Exact runtime candidate **3015e47f93de7bfd1e81c8dd7bf4426d8c13ddc6**, undeployed.
The structured SWE.1 generator assigns task `budgets` to simulation CPU/timing
allocations. SWE.6 previously recognized only byte budgets, then indexed a
colon-separated task name and crashed. All three [old-runtime cases](baseline-pytest.xml)
reproduce the IndexError: positive measured budget, changed statement and absent
bound budget. The new tests were applied to runtime91ce790 before the code change.

Only exact allocation statements from the existing work-order-bound generator
now use `Run Target Scenario` on the declared instrumented test followed by
`Simulation Performance Should Meet Budget`. Unknown/unbound/changed timing
requirements retain ordinary engineering obligations; no task label or timing
phrase exempts them. Every requirement remains represented. The implementation
is driver-independent; existing measurement checks and resource byte budgets
remain authoritative. This separate structured-path crash did not cause the
interrupted native run's7/9 Robot outcome; b1536d7 addresses that contract visibility.

[Exact qualification and commands](qualification.json): **41PASS**,0failures,
errors or skips,197.299s; [XML](local-pytest.xml), [log](local-pytest.log).
This includes actual compiler/Robot/Renode use of the generated measurement route,
copied/stale/missing/failed measurement rejection, the full scoped IDR six-phase
fixture and inherited full IWDG structured SWE.6 with its unchanged gate. Semantic
model responses/review inputs in those fixtures are explicitly scripted/synthetic;
zero Qwen requests, no owner review invention, no live product/capability claim.
Ruff E9/F/B and static spec/contracts pass separately. Formal tasks30/58 and
IE-T001–007 remain unchanged; IE-T008/M1 unaccepted, IE-T009/M2–M5 unrun.

## Prepared native execution — NOT RUN

[Preparation manifest](native-prepared/preparation.json) binds exact source,
bundle hash/ref/prerequisite, scripts and the two actual frozen failed diagrams.
The full private directory is local loop10 under
operations/feature014/incremental-m1-followup-20261029/native-swe6-route-3015e47.
The source bundle verifies against9b4c390; it is not committed to Git. No files
were uploaded and no remote tests/services/orders/grants were changed.

After a newer explicit owner resume and an eligible resource window, copy that
directory's contents to the manifest's future remote directory. **Do not use old
epoch32 tooling or automatically resume at18:00.** This entry point requires an
explicit current RUNNING epoch, no native/request/resource/verification owner,
and host omniverse2 before touching production state. It does not resume the
operator, deploy code, sign/extend authority or launch inference.

```sh
/mnt/data/forge-c/production-local-014/venv/bin/python \
  /mnt/data/forge-c/production-local-014/deployment/qualification-swe6-route-3015e47/bootstrap-v3.py \
  --expected-operator-epoch "${APPROVED_RUNNING_EPOCH:?new authenticated RUNNING epoch required}"
```

It clones an isolated checkout, verifies the exact source bundle, prepares private
tool/input/scratch context, then runs the41-check cohort and renders the two actual
failed diagrams through generated MCP environment. The guard continuously checks
operator/resource state,600s total/480s tests/90s renderer bounds. Each child uses
an unprivileged private PID namespace with unshare kill-child so terminating the
qualification session also ends its namespace descendants. Unsupported namespace
prerequisites fail qualification; do not fall back to an unguarded shared process.
Only local AST/CLI/wrong-host refusal were checked; **native guard, namespace and
tool execution remain NOT_RUN**, as does combined-source role preflight and any
later Qwen continuation. Existing18:05:39UTC grant expiry is not renewed.

Before promotion, collect actual XML/provenance/real-render results, verify exact
source/host/identities and run complete role admission for the candidate. Preserve
history/cumulative costs and validate any brownfield reuse through the existing
resume path. A new continuation needs current operator intent and finite valid
execution scope. The original failed/interrupted records are never relabelled.
