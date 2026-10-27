# Feature 014 qualification inputs

Prepare concrete source cases in a new private data directory before freezing
and signing a campaign. This command requires a real C compiler and creates no
grant, mission, order, runtime job or inference request:

```bash
python -m forge_factory.afo.qualification_inputs \
  --out <new-private-directory> --compiler <pinned-clang> \
  --campaign-id <unique-protocol-campaign> \
  --authorization-ref <planned-owner-authorization-id>
```

Set `FORGE_STATE_DIR` and `FORGE_EVENTS_DIR` to private qualification directories.
On the local workstation all outputs must be on loop10. Native Qwen execution
belongs on Omniverse2. Freeze inputs on their final host: absolute paths are part
of the evidence and cannot be moved after sealing.

The generator materializes the frozen 20-case catalog with five repeats each,
deterministic prospective job identities, case hashes, intake envelopes, complete
evidence packets, requirement coverage and request measurements. The virtual
REG32 fixture is explicitly seeded qualification data, not an STM32 product
failure. A fixed compiled checker tests 260 register inputs and idempotence: the
seeded implementation fails 194 checks and the independent reference passes all
260. This limited oracle establishes the fixture counterexample; it proves no
product, model or operational capability.

Request measurements apply the selected profile's actual gateway transformation
to a copy of the request, including reasoning settings and output extensions.
The adapter sends the original request, so the gateway applies that transformation
once. Provider admission and mission accounting remain independent checks.

The selected Omniverse2 Qwen profile reserves 16,384 extra output tokens for high
reasoning. With the adapter's 2,048 answer tokens this alone exceeds the current
16,000-token diagnosis job reservation. Preparation reports
`COMPLETE_SERIALIZED_CASE_EXCEEDS_JOB_ENVELOPE`; it does not disable reasoning,
raise a reservation, or call the model. Any new qualification allowance must be
explicitly finite and authorized before the job's initial reservation. Existing
mission limits and exhausted history cannot be rebound.

For a distinct owner-approved qualification campaign, the optional
`--qualification-job-tokens <finite-tokens>` records prospective initial
reservations. It does not authorize them. Preparation emits `jobs.json` and
`requested-initial-reservations.json`; pass these to qualification `freeze` with
`--jobs` and `--job-token-reservations`, together with the exact identity and
`--input <directory>/inputs.json`. The owner signature must bind the resulting
manifest hash. Provisioning checks that signature, source/case/mission/model
identity, per-order policy cap and declared context before the first ledger
reservation. Rebinding an existing job's reservation remains forbidden. The
ordinary production path retains the registry allowance. Full campaign readiness
still requires every other prerequisite below.

The optional freeze argument `--mission <json-file>` binds an explicit mission
ID, lineage and finite ledger limits into that same signed manifest. The existing
ledger validates the limits. The protocol scope permits no product attempts,
tools or corrections, and cannot exceed its frozen job/request/token work.
Initial preparation refuses a registered mission whose identity, lineage,
limits or authorization differs. No mission is created by freeze/provision.

`dry-run`, `provision` and `step` accept repeated `--trial <case-id:repeat>` for
scoped protocol work. This checks every frozen source-case hash and retains all
100 expected trials; it evaluates capability/fault prerequisites only for the
selected trials. A missing alternative therefore still blocks its own case
without claiming other cases are unavailable. Full reports remain 100-case
reports; `--trial` cannot shrink their denominator. Scoped completion is labeled
`TRIAL_SUBSET_COMPLETE`, never whole-campaign qualification. Provisioning waits
for an order's existing AFO admission before charging its diagnosis job.

The owner-verified preparer archives its immutable manifest in the existing AFO
artifact tree. Completed role jobs can then be recorded by model-free supervision
after engineering authority expires or is revoked. Publication is recoverable
across the artifact/SQL boundary; the original snapshot remains immutable while
late usage and liveness settle in their existing ledgers.

Purpose-aware queue admission creates a qualification wrapper without a product
`FABRO_LAUNCH` command. Its neutral terminal state is `QUALIFICATION_RECORDED`:
it means a protocol result was recorded, including a failed or unknown result.
It is neither product READY nor product BLOCKED. Ordinary product orders cannot
enter it. Closure requires the original qualification marker, a hash-bound result
and proven native quiescence for every role worker; a held inference lease keeps
the wrapper active. No product native identity or accepted gate is invented.

Native command nodes, role MCP servers and policy hooks receive the same explicit
non-secret data/policy/authorization/intent paths. Credentials are not forwarded
through this context. Qualification usage comes from the gateway request ledger;
Fabro command-node usage is retained separately and cannot replace model usage
with zero. Recoverable protocol cases require an actual request-ledger entry in
addition to the independent audit and accepted plan.

Six response interventions are implemented at the native adapter boundary:
administrative-field forgery, empty content, truncated JSON, an unqualified
model switch, a genuinely distinct foreign case reference and a reworded tried
strategy. Enable only a declared per-trial mapping using qualification
`freeze --protocol-faults <json-file>`. Each entry must exactly match that seeded
case's prospective recipe; the owner signature binds the mapping. Ordinary
product cases cannot enable these controls. For example, `empty-output:0` maps to
`{"boundary":"after-provider-response","recipe":"drop-content"}`.

At execution the adapter rechecks the current signature, order/model scope,
job/case/nonce, policy, deadline and held native execution. The authoritative
evidence table retains original/injected visible-response hashes and the declared
intervention, without response text or hidden reasoning. Changed replays are
refused. Reports require matching exposure evidence as well as an independent
oracle audit. Injected responses do not establish unmodified model competence.
Unmodified empty or invalidly typed content is a protocol incident and cannot
create a semantic completion receipt.

Two pre-evidence interventions atomically replace only the frozen seeded
`software/hal/reg32.c`: a hash-stale file or a symlink to a fixed nonauthoritative
marker outside that fixture workspace. Both persist an immutable intent before
the effect and adopt an identical completed effect on replay. Parent paths,
regular-file type and bounded source size are checked; no external source is
read through the injected symlink. Tests interrupt both sides of replacement.
The original case and packet hashes remain unchanged so actual evidence access
must refuse the altered source. Reports require the matching source-fault fact
and its exact native incident code. A response fault likewise needs the specific
broker rejection code; an unrelated refusal cannot satisfy the case.

`inputs.json` includes prospective fault recipes. They are not executed fault
evidence. Revocation/expiry, lost launch acknowledgement and
cancellation-with-live-request interventions
remain unprovisioned, as does the independently measured authorized local
alternative; unresolved prerequisites block the full campaign. Dirty generator
source also blocks readiness. Pass `inputs.json` and
its exact `jobs` mapping to the existing qualification freeze operation; preflight
checks their readiness and effective model/reasoning identity. A prepared file,
successful compiler check or dry-run never qualifies the 100 native trials.

A durable local launch refusal is distinct from an uncertain native launch.
Preflight and operator-fence failures can release inference capacity only when the
controller proves the Fabro subprocess was never invoked. The existing execution
ledger retains dispatch intent, a hash-bound non-dispatch proof, and the original
job reservation. A timeout or any error after invoking that subprocess remains
possibly live and follows native nonce reconciliation; a terminal job alone never
releases capacity. Non-dispatch proof publication is recoverable after restart.

### Independent operational observation

`python -m forge_factory.afo.fault_observer capture|evaluate` captures evidence
outside the Conductor process and control group. It does not inject faults,
restart services, admit jobs, migrate SQLite, contact a model or renew authority.
Its plan must be an exact hash-bound input of the frozen operation manifest:

```json
{
  "schema": "forge-c/operational-observer-plan/1",
  "unit": "forge-conductor.service",
  "observer_source_sha256": "<sha256 of afo/fault_observer.py>",
  "fact_evaluator_sha256": "<sha256 of afo/operational_facts.py>",
  "data_root": "<absolute isolated factory root>",
  "database": "<data_root>/state/conductor/conductor.sqlite3",
  "heartbeat": "<data_root>/state/afo/conductor.heartbeat",
  "intent": "<operator-provisioned durable intent path>",
  "evidence_root": "<operator-provisioned observer directory outside factory state>",
  "mount_uuid": "<authoritative mount UUID>",
  "max_rows": 10000,
  "health_urls": {
    "fabro": "http://127.0.0.1:<isolated-port>/health",
    "gateway": "http://127.0.0.1:<isolated-port>/health"
  }
}
```

The plan, source hash, paths, ports and mount identity must be frozen before the
campaign is signed; placeholders are not executable configuration. Provision the
observer directory with owner-only access outside product workspaces. For a
mount-loss/reboot campaign, independently provision observation and durable storage
outside the affected fault domain; a directory on the same failed mount is not
continuous external observation.

```bash
python -m forge_factory.afo.fault_observer capture \
  --manifest operation.json --plan-ref plan-reference.json --out <observer-dir>/before.json
# Execute only the separately authorized existing fault recipe/host fixture.
python -m forge_factory.afo.fault_observer capture \
  --manifest operation.json --plan-ref plan-reference.json --out <observer-dir>/after.json
python -m forge_factory.afo.fault_observer evaluate \
  --manifest operation.json --plan-ref plan-reference.json \
  --evidence fault-and-sample-references.json --out <observer-dir>/observation.json
```

`plan-reference.json` is `{ "path": "<plan>", "sha256": "<hash>" }` and must occur
in manifest inputs. The evaluation input contains `injection_ref` and chronologically
ordered `sample_refs`, each with path and SHA256. Capture enough samples for the
frozen probe/detection bounds; two examples are not a 24-hour campaign.

The observer correlates the three existing signal receipts with actual unit/PID,
health and intent observations. External exposure fixtures cover the other thirteen
classes below. It preserves missing/corrupt/truncated accounting as UNKNOWN and
detects lost/decreased mission accounting or duplicate native identity observations. HTTP probes are loopback-only, ignore proxy variables and refuse
redirects. Campaign reporting recomputes observer records from their source refs;
legacy handwritten booleans cannot pass the independent recovery gate.

This remains **partial qualification tooling**. Host-level intervention audit
is still required; authenticated AFO actions alone do not prove no manual host
intervention. READY packages require the independent package oracle. Unsupported
live fault exposures (including reboot and mount loss) remain missing, and unknown
fields cannot pass campaign reporting. No service, model, campaign or deployment is
activated by these commands. Full DA-T026/046/049/050/052 remain unqualified until
actual authorized host fixtures, complete observation and wall-clock campaigns exist.

### External exposure fixtures and fault-class predicates

An external fixture is a hash-bound input of the operation manifest, authored and
frozen before signing. It describes what an authorized host/queue fixture intends
to exercise; it never grants permission, executes an action, or supplies success flags.
For example:

```json
{
  "schema": "forge-c/operational-exposure-fixture/1",
  "fault": "resource-pressure",
  "unit": "forge-conductor.service",
  "observer_plan_ref": {"path": "<plan>", "sha256": "<plan hash>"},
  "parameters": {"minimum_free_bytes": 1073741824}
}
```

A runtime exposure receipt has schema `forge-c/operational-exposure/1`, the exact
`manifest_sha256`, `fault`, `unit`, target `host`, factual start `at` (UTC epoch
seconds), and `fixture_ref` (the exact path/hash input above). `evaluate` checks its
bindings and derives exposure/restoration from the captured timeline. A receipt
without the corresponding measured change cannot count. All values/IDs must be
frozen for the actual isolated installation; the example threshold is not policy.

| Fault class | Frozen parameters | Required observed facts |
|---|---|---|
| last-job-success/failure/block | `order_id` | The sole active order reaches the specified outcome, with its latest native attempt; control stays healthy across another declared cycle window. Historical failed attempts cannot substitute. |
| empty-queue | none | No queued/active work and healthy continued control across the cycle window. |
| drained-queue | none | DRAINING intent/control, no active/native-held work, continued healthy control. |
| dependency-outage | `dependency` (`fabro`, `gateway`, `data_volume`) | Actual failed dependency probe followed by healthy restoration. |
| reboot | none | Changed boot identity and restored control; unknown boot identity cannot establish exposure. |
| restart-limit | none | A failed unit with actual `start-limit-hit`, then a new restored process/boot. |
| poison-head | `order_id`, `eligible_order_id` | Older malformed queued item becomes BLOCKED while the separate eligible item progresses under recorded authority within its bound. |
| resource-pressure | `minimum_free_bytes` | Free space crosses the frozen threshold and is restored. This checks disk pressure, not an unmeasured CPU/RAM load. |
| operator-stop-resume | none | Newer STOPPED intent, bounded settlement before effective stop, no new request/execution identity while stopped, quiescence and inactive unit before authorized newer resume. |
| post-campaign-continuity | none | Full stage duration before the event, healthy post-campaign interval through the declared bound. The no-outage event has zero restoration latency and a separately retained observation duration. |
| later-authorized-intake | `order_id` | A newly observed order is admitted and has a native attempt, within its scheduling bound. |

The union of these thirteen classes and the three existing signal recipes must
match the actual `qualification.FAULTS` catalogue. This is tested as a coverage
invariant; additional classes cannot silently default to success. The inspector,
author/gate rules and controller's admission authority remain unchanged.

Collection now reads bounded bytes once for both digest and JSON parsing, caps
cumulative SQLite projection at 16 MiB and loaded traces at 128 MiB, and retains
scope/path restrictions. Capture never follows a FIFO or creates a missing database.
Unit/PID and fresh completed-cycle heartbeat facts are correlated; a legitimately
stopped PID-0/empty-cgroup unit is known downtime, not missing independence.

Predicate tests use synthetic timelines and real private SQLite/HTTP fixtures. They
are not live fault exposure or elapsed-time qualification. Host intervention audit,
independent READY verification, complete live workload/fault coverage and a genuine
reboot/mount window remain required. No observer command activates a service or
performs any of the external actions above.
