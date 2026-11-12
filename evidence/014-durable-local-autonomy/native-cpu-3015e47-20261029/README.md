# Exact-source CPU qualification while Qwen stays stopped

Runtime candidate **3015e47f93de7bfd1e81c8dd7bf4426d8c13ddc6**, not deployed:
**130distinct tests PASS per host**, across41+89cohorts, zero final failures,
errors or skips. Case-ID sets match and do not overlap. [Summary](qualification.json)
binds the exact revision, XML, durations and scope; native provenance contains
complete commands, clean source before/after, environment and guards.

- 41cohort: [native XML](native-swe6-v4-results/pytest.xml),
  [provenance](native-swe6-v4-results/provenance.json); local41source results remain
  in ../swe6-structured-measurement-20261029/local-pytest.xml.
- 89cohort: [native XML](native-core-v6-results/pytest.xml),
  [provenance](native-core-v6-results/provenance.json), [local XML](core-3015e47-local.xml).
- [Actual failed diagram cases](native-swe6-v4-results/real-render.json): exact frozen
  inputs, actual JAR/root and successful PlantUML SVG invocations through generated
  MCP environment. Existing render_ok uses temporary output; these results do not
  modify the original failed inspection, frozen phase or product verdict.

The earlier core cohort [failed88/89](native-core-v5-results/pytest.xml): the real
Conductor correctly refused an uninitialized qualification-only data root with
DURABLE_DATA_VOLUME_NOT_READY. The only correction was proper isolated-root
initialization using the existing host.init routine on the actual mounted volume;
native V6 records UUID/root/fsync preflight PASS and sentinel hash. No guard was
disabled, no sentinel copied/faked, no production sentinel changed, no failure
erased. This is qualification setup correction, not Qwen self-healing evidence.

## Execution boundary

The owner's immediate stop applies to Qwen. Independent verification uses scripted
semantic responses and CPU tools, with no backend connectivity. Requiring RUNNING
for these checks was unnecessarily restrictive. Executed V4/V6 instead require
stable **STOPPED epoch33/effective_stop**, no pending native/request/resource owner,
and actual provider quiescence. Private PID and network namespaces prevent model
access and retain namespace-descendant cleanup;8CPU affinity/nice10 and600s total/
480s pytest limits bound work. [Namespace probe](native-cpu-namespace-probe.json).
Healthy monitoring and normal cleanup executed; forced stop-race injection during
qualification remains NOT_RUN. Earlier RUNNING-only V3 was not executed.

All native tests run serially. Qualifier workspace/checkouts/artifacts were created
under production-local-014/deployment/qualification-*, with separate state/scratch;
the active checkout, services, policy and grants were not activated or changed.
An initial idempotent shutdown-settlement recheck refreshed its observation proof
without changing the STOPPED epoch. The final [read-only audit](stopped-factory-after-cpu-verification.json)
shows clean active source9b4c390, provider quiet, zero outstanding requests and
QUIESCENT/RELEASED original execution. Entire mission snapshot matches the earlier
audit:4attempts/345requests/596tools/400m conservative charges, aggregate usage
UNKNOWN. No grant renewal or automatic18:00 restart is authorized.

The checks include real compiler/Robot/Renode, source/measurement binding negatives,
the complete scoped IDR scripted-artifact anchor, inherited full IWDG verification,
request-refusal metadata, native/task liveness separation, role/trial and maintainer
fixtures. Semantic answers, independent capability receipts and reviews used by
fixtures remain labelled substitutions. This is software/tool verification,
**not Qwen role qualification, an accepted product, learning benefit or24/7 proof**.

[Primary-reference note](primary-reference-note.json) records that detailed CRC_IDR
section26.4.2 supports the reviewed32-bit scope, offset4 and reset0; the chapter's
high-level feature summary differs at8bits. That source discrepancy is explicit;
no reference, requirement or human review is rewritten, and no silicon claim is made.
Restricted reference contents and raw engineering packages remain private on loop10.

## Remaining execution

Qwen remains **STOPPED** until newer explicit owner intent. Before any new model
run: revalidate current finite authority/time window and resources; bind the exact
candidate/profile/model and complete role admission; use the current cumulative
mission; validate brownfield compatibility or start a properly bounded continuation.
Existing18:05:39UTC expiry is not renewed. Native CPU qualification is not source
activation or a signing grant. Preserve original SWE.3 failures and interrupted
SWE.6 results; a new real run must produce substantive checks/report/inspection
and an independently recomputable package. Demonstration traversal alone cannot
close IE-T008/M1. IE-T009/M2–M5 and formal campaigns remain unrun/unaccepted.
