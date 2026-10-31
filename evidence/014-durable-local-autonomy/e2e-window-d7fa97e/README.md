# Live five-hour Qwen end-to-end window

Exact deployed runtime: **d7fa97e41f6e265e55737478379052db8d6bd859**.
Window cutoff: **2026-10-28T16:29:12Z**. This is the later owner five-hour goal,
not a renewal of earlier mission/grant deadlines. Feature014 remains30/58;
no additional formal task is marked complete.

## Actual work in progress

[Live snapshot](running-snapshot.json): at12:48:38Z CRC order
**afo-99cc4f39103951e7**, native **01M618R74R8KQFQR9AJ4VQXZ5Q**, is RUNNING.
First real request sent12:46:24Z is QUIESCENT with4544 accounted tokens; second
request was SENT12:48:00Z. This is transport/accounting progress, not semantic
correctness or a phase PASS. Inference lease remains HELD by the live product job.
RNG **afo-8298dbdf8767eb9c** is not submitted until CRC becomes terminal.

[Model residency](model-residency.json) reports Qwen3.8-27B Q8 with context65536,
size32140983008bytes and equal size_vram; the complete model is resident in GPU
memory according to Ollama. Snapshot GPU32733MiB/99%. Actual shared-resource state
is recorded; the owner accepted shared resources. No unrelated workload is stopped.

The existing recorder publishes every5minutes to
[e2e/2026-10-28-q38-five-hour-window](https://github.com/jnsagai/forge-c/tree/e2e/2026-10-28-q38-five-hour-window).
It submits the two finite pre-approved orders serially; existing Conductor owns all
execution/recovery. There is no competing job scheduler or new authority store.
A live handle must be re-polled; a stale observation is never proof of termination.

## Last blocking implementation correction

A zero-model preflight built the real six-phase workflow, checked actual network
isolation and pinned model identity, validated all roles, and handshook every needed
MCP server. It found the unsigned experiment omitted the existing final read-only
inventory role, release-manager. Product experiment validation also excluded that
role. The fix permits an explicitly signed configuration for this existing role;
its MCP/read-only permissions, ordinary capability guard and deterministic package
readiness gates are unchanged. An experiment is still qualified:false.

The regression derives roles from the existing workflow builder and exercises all
of them. Missing final-role configuration still refuses; ordinary release-manager
work still requires an independently measured capability. Attempts to insert
operator, safety-authority or afo-conductor roles remain refused.

[Local regression](local-tests.json): baseline14PASS/1FAIL; candidate101PASS20.172s,
including protocol/gateway/inherited release checks. An initial command named two
nonexistent test files and collected no tests; it is retained privately and is not
passing evidence. [Native results and exact commands](native-tests.json): clean
exactd7fa97e original38-case lane34PASS/4FAIL25.307s due omitted isolated fixture
PlantUML/Fabro/tool paths. Corrected inherited release cohort13PASS44.272s after
attaching real read-only tools and selecting installed binaries. No code/gate
change for this correction; original failed lane retained. All fixtures make0
model calls. Separate cohorts are not a full-suite or live capability claim.

[Deployment](runtime-deployment.json) records RUNNING11→PAUSED12→RUNNING13,
backups, unchanged provider instance and historical missions,0provider signals and
0new requests. Source remains pinnedd7fa97e during this live job; documentation
commits do not change its runtime. Previous fa90128 gateway/holdout/tool-path fixes
and [first failed Q38 audit](../workflow-runtime-fa90128/README.md) remain applicable.

## Explicit authorization basis and finite accounting

The implementation engineer initially asked for an additional larger-cap approval.
Re-reading the owner's existing bounded Feature014 live-qualification approval and
the explicit SSH-agent signing rule established that a second approval was not
required for this prospective experiment. **No new reply was received or inferred.**
[Authorization basis](authorization-basis.json) records the actual earlier owner
requests, scope, reasoning and this correction transparently. No safety document,
review disposition or patch bundle was signed. No private key was read/copied.

[Exact scope](scope.json), SHA256
570a031c15ff4bc668cfa58ab9d3602ac70e1f7e935352b57398b6641258d35d,
binds the new CRC/RNG orders, exact source/profile and existing historical mission
snapshot. These are fresh factory-acceptance experiments around unchanged frozen
ST deliveries,10 and17functions respectively; they do not implement new ST source,
continue an exhausted engineering mission, or reset any old cost/uncertainty.
Earlier unsigned proposals remain preserved and were not activated.

Two SSH-agent-signed qualification grants V3 were cryptographically verified before
[activation](activation.json) at12:46:05Z. Each new order has finite2million local
tokens,512 requests,1024 tools,3 product attempts,4 recovery jobs and1 correction,
common cutoff16:29:12Z; aggregate new-order cap4million tokens. First product job
reserves1.4million, later product attempts150k each, prospective diagnosis jobs65536
each, all within the shared2million ceiling. The conservative1.4million mission
charge is the allocated job floor with ongoing uncertainty, not a claim that
1.4million tokens have actually been reported by Qwen. Finite per-stage quality,
context, MCP, role, historical and native gates remain. One admitted inference and
one verification worker remain; all Qwen execution is on Omniverse2.

[Native launch prerequisites](launch-prerequisites.json) PASS for both deliveries:
network DENIED_VERIFIED, pinned Q38 MATCH, agent/MCP preflightPASS,0missing workflow
roles,0model calls during preflight. Native delivered-code build/intakePASS is not
SWE.1–SWE.6 success or a model competence receipt.

The active policy is temporary and restricted by the two experimental grants.
Original production grant AUTH-014-OMNIVERSE2-Q38-GOLIVE-20261028-V2 remains on disk
with unchanged29Oct05:00Z expiry; all historical RCC/IWDG/smoke accounting remains.
[One-shot expiry cleanup](expiry-cleanup-installed.json) schedules restoration of
that exact previously signed policy at16:29:15Z. It refuses newer operator intent
or a changed policy; it does not start/stop workers, release inference, change any
mission allowance or resume a stop. Existing Conductor/watchdog reconcile expired
jobs independently. Cleanup execution is future/unproven until its receipt exists.
Factory supervision continues after the recorder/window ends.

## Status boundaries and next execution

Runtime fixes are deployed; the product experiment is LIVE. Role qualification,
product correctness/READY, autonomous self-healing, learning benefit,30-product
benchmark and24/72/168h availability remain **unproven**. Same-model review is not
independent evidence. Existing engineering/release gates and offline review remain.
No formal ledger tick or completion claim follows from this running snapshot.

Re-poll the original native/request handles and independently inspect phase gates,
produced artifacts and packages. Let Conductor own bounded diagnosis/recovery;
RNG follows CRC only after terminal reconciliation. Preserve actual failures,
charged allocations and unknown usage. At cutoff, collect outcomes and verify
expiry-policy restoration without stopping global supervision. Respect any newer
operator pause/drain/shutdown. Use the private read-only observer
production-local-014/deployment/observe-e2e-window-v3.py, not a duplicate dispatcher.

Private local artifacts/scripts: loop10 operations/feature014/overnight-audit-20261028.
Remote state: /mnt/data/forge-c/production-local-014/deployment/e2e-window-20261028-v3.


## Owner dashboard connection — 13:05Z

The existing Fabro Monitor now includes source **forge-c-omniverse2-production**,
labelled **Forge-C · Omniverse production · Qwen3.8 Q8 xhigh**, under Forge-C Fabric.
Open http://localhost:8787 (or the existing master.local:8787 LAN address), select
Forge-C Fabric and click the CRC row WO-AFO-99cc4f39103951e7-a1. RNG appears after
it starts; no native RNG row is fabricated while its serial intake is pending.

[Connection](dashboard-connection.json) preserves all10 previous sources and uses
an inbound-only SSH tunnel127.0.0.1:32395→remote127.0.0.1:32491. New tunnel unit,
configuration, credential file and byte-identical old-config backup live onloop10.
The existing canonical config path now symlinks to that loop10 copy, so other
terminals still use the same path. The first cross-device rename failed before
config mutation; same-directory atomic symlink replacement completed installation.
Only the local monitor was restarted;0remote worker restarts/0model calls.

[Live verification](dashboard-verification.json) proves connected:true,7production
native runs listed, currentCRC RUNNING, SWE.1 author stage running and a68343-character
workflow SVG with no graph error. Run detail and graph endpoints return successfully.
Browser visual inspection was NOT_RUN because browser tooling is unavailable;
backend/graph checks are not a browser-rendering claim. No credentials, private
inputs, raw model output or hidden reasoning are published in these evidence files.
Historical Fabro SUCCEEDED is transport/workflow status, not product acceptance.


### Dashboard timeout correction —13:25Z

The owner observed a timeout. Independent native observation still reportedRUNNING;
first SWE.1 author and first continuation had endedSUCCEEDED, and the next checkpoint
continuation was active. The actual graph uses14400s author-node timeouts, not the
20-minute local task time box. Mission cutoff remains16:29:12Z. No native deadline
was extended and no worker was restarted. Re-reading checkpoints also shows that
Qwen revised the initially rejected CRC_CR_1 packet until its local checks returned
VALID; this is not a whole-phase inspection or independent product-success claim.

The read-only monitor's fixed8s HTTP timeout did reproduce502/TimeoutError while
native execution continued. [Minimal client patch](dashboard-remote-timeout.patch)
adds an optional finite per-source request_timeout_seconds, bounded0.1–60s, default8
unchanged. Only the production source now uses30s. Explicit stream deadlines remain.
The viewing SSH tunnel enables compression; previous10source configurations remain.
Only the local tunnel/monitor were restarted. Original dirty monitor changes were
preserved and backed up onloop10; no monitor repository reset or blanket commit.

[Regression evidence](dashboard-timeout-tests.json):2 real delayed-response/invalid-cap
checksPASS,15 inherited monitor testsPASS. [Reproducible local check](verify_dashboard_timeout.py)
imports the installed monitor; set TMPDIR toloop10 and run with Python-B. These are
local monitor tests, not concurrent Qwen or GPU tests. [Live verification](dashboard-timeout-verification.json)
then loaded detail in16.167s and the real68343-character graph in15.476s, with native
RUNNING and checkpoint continuation visible. The longer display deadline permits
responses that exceeded the previous8s bound. Browser visual inspection remainsNOT_RUN.
Six real Qwen requests wereQUIESCENT and seventhSENT at13:24:11Z; do not treat either
a display timeout or a completed continuation node as job termination.
