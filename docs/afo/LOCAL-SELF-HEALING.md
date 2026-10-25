# Local autonomous recovery

The production entry point for unattended diagnosis is the AFO Conductor.
`workorder.run` provides bounded author/inspector loops within one attempt. An
external script that only repeats that command does not run AFO's diagnosis or
Factory Maintainer. The former q36c operator controller stopped after a repeated
failure; it did not provide the complete self-healing path.

## Recovery cycle

For an approved order admitted under signed PILOT/ACTIVE authorization:

1. The model-free Conductor reconciles the authoritative terminal Fabro receipt
   and constructs a failure bundle from native gates, inspections and tool evidence.
2. Existing deterministic remediation and validated lessons take precedence.
   Otherwise, when enabled, a separate local Fabro run loads the locked Recovery
   Planner SKILL and reaches only `forge-afo-mcp`.
3. A durable job records the source/runtime identity, frozen case hash, model,
   profile, policy, launch nonce, original order deadline and reserved capacity.
   Inference runs outside the Conductor's health loop. Healthy idle supervision
   makes zero model calls. Restart adopts a matching receipted job; ambiguous
   launches are never blindly repeated.
4. The independent validator checks the proposed plan's failure identity, scope,
   strategy, authorization, budgets and material difference. Accepted plans create
   a new attempt through the existing work-order/resume API. The scoped author
   receives the strategy as untrusted reference data; inspectors do not. A return
   to SWE.1 excludes downstream free text and code details.
5. A verified factory-source defect enters WAITING_EXTERNAL_CHANGE. When enabled,
   the local Maintainer gets its own isolated candidate, restricted MCP tools and
   bounded job. Its submission starts a separate CPU verifier: baseline reproducer,
   CAPA linkage, existing independent CRE gates and the draft-only proposal broker.
   The Conductor does not block on that evaluation.
6. Revocation, exhausted budgets, missing authority, uncertain side effects,
   invalid plans and out-of-scope repairs end explicitly BLOCKED. A local-model
   diagnosis cannot waive a product gate or establish READY.

Local agent admission requires the work order's explicit local profile. The
served model digest, loopback endpoints and namespace isolation are checked by
the existing local-profile validator. No cloud endpoint or ACP fallback is added.
AFO gateway admission uses that profile's gateway port.

`afo_local_agent_jobs` in the existing Conductor SQLite database records model jobs
and independent-review dispatches. Calls reserve the complete role allowance
before launch, including failed/uncertain attempts; usage that is not reported
stays UNKNOWN. These reservations cover diagnosis/maintenance capacity and do
not retroactively qualify historical work-order token measurements. The existing
order, phase and resume-lineage budgets remain separate constraints.

## Owner-controlled activation

The shipped policy remains OBSERVE_ONLY. On the remote host at the time of this
change, both agents were disabled, the Conductor was inactive, and there were no
authorization records or allowed signers. Code availability is not activation.

An operator may keep deployment configuration outside the clean source checkout:

```bash
export FORGE_AFO_POLICY=/path/to/deployment/afo-policy.yaml
export FORGE_AFO_AUTH_DIR=/path/to/deployment/authorizations
export FORGE_AFO_ALLOWED_SIGNERS=/path/to/deployment/allowed-signers
```

The normal schema, constitutional floor, signature, exact policy hash, scope,
expiry and revocation checks still apply. Environment selection grants nothing.
The deployment policy must enable the planner and scoped rework, allow only the
intended local model, and optionally enable the Maintainer. Keep source promotion
and automatic merge disabled.

After reviewing the policy, the owner supplies their public signing key in the
allowed-signers file and signs the prepared authorization record themselves:

```bash
python -m forge_factory.afo.authz sign "$FORGE_AFO_AUTH_DIR/<id>.json" --key <owner-signing-key>
python -m forge_factory.afo.authz verify "$FORGE_AFO_AUTH_DIR/<id>.json" --mode PILOT --action recover_workorder
```

Run the Conductor inside the same local profile namespace and environment as the
work order, with the existing user-service/watchdog setup and persistent data
mount checks. Submit the approved order to the AFO queue; a bare work-order
launch is not enrolled automatically. Never run two competing controllers for
one order. Preserve the original attempt count and deadline during a migration.

Old brownfield sources without the versioned resume identity/ledger remain
ineligible for validated resume. An approved factory revision change requires a
new attempt with explicit provenance; no legacy force-resume override exists.
For an enrolled older run, the frozen launch manifest may name
`approved_factory_revision`. A fresh cross-revision attempt is admitted only when
the currently valid owner-signed grant also binds that exact revision through
`signed_runbook_ref: factory-revision:<sha>`. It carries the scoped diagnosis and
source receipt, re-runs intake and every SWE phase, and copies no old phase
evidence or code corrections. The launch-manifest hash is rechecked at dispatch.
The enrolled order's remaining attempts and authorization expiry still apply.

## CPU and RAM use

`FORGE_CPU_JOBS=16` enables bounded parallel execution of independent frozen
prevention reproducers during repair verification. The scheduler caps requested
jobs at 16, leaves eight host CPU cores available, reserves 16 GiB of available
memory and allows 4 GiB per worker. It also observes the current memory cgroup.
The default remains one worker when no capacity is explicitly selected.

Each case retains its original command, oracle, timeout, sandbox and private
scratch directory. Source worktrees are prepared before parallel execution;
results retain deterministic case order and exceptions cannot become PASS.
Dependent phases, author/inspector ordering, numerical precision, model context
and acceptance criteria are unchanged. More RAM is capacity for these isolated
jobs; allocating otherwise idle memory does not speed GPU decoding.

Hosts without subordinate-UID Podman may select
`FORGE_CRE_ISOLATION=bubblewrap`. That backend uses role-specific namespace UIDs,
private PID/network/device namespaces, read-only source/toolchain mounts and only
the current writable scratch directory. Owner HOME/state/agent sockets and GPU
devices are not exposed. Unlike Podman sub-UID isolation, the host UID mapping is
the invoking account; its protection comes from scoped mounts and namespaces.
Kernel confinement checks must pass on the deployment host. A Maintainer with no
available sandbox waits for the dependency instead of executing candidate code
as the production account.

## Authority and validation limits

The existing constitution and AFO-FR-053 prohibit automatic persistent source
deployment. Local diagnosis, scoped product-draft rework and isolated repair
preparation need no human prompt once authorized. Factory-source promotion,
safety decisions and source changes to the recovery authority itself retain
external review. This change does not alter that boundary.

Deterministic tests cover native workflow validation, real MCP authorization and
data pagination, restart/nonce handling, budgets, revocation, strategy propagation,
inspection separation and the independent-review dispatcher. Fabro run outcomes
are fixtures; these tests make no model calls and are not a live Qwen qualification
or an unattended operational soak. See Feature 013 validation evidence for exact
revisions and results.

## Feature 014 durable operation (2026-10-25)

The Feature 013 activation snapshot above is historical. The read-only Feature 014 inventory shows the existing `forge-conductor-local-omniverse2.service` and mission recorder active; the source candidate in PR #42 has not been deployed. Its exact tested revision and separate implementation/model/product/learning/availability results are recorded in `specs/014-durable-local-autonomy/validation.md`.

Use existing AFO authority and a registered durable mission before enabling `FORGE_DURABLE_AUTONOMY=1`. New orders/continuations cannot reset consumed capacity. Unknown native/provider work keeps inference ownership, including after job terminality. Do not use cancel acknowledgements, listing gaps, timeouts or idle GPU as termination proof.

A complete evidence packet, short semantic judgment and deterministic receipt/binding replace fragile model-written administration. The adapter measures the complete serialized request and reserves output. Unfit or unqualified work blocks within its scope; all global requirement/dependency coverage remains recorded. Role capability is measured separately for diagnosis, authoring, inspection and maintenance; same-model agreement is not independent correctness evidence.

Every ordinary success, failure, block, timeout and unknown outcome enters factual experience with a recoverable disposition. Qualified ordinary/negative lessons extend the existing LessonStore, preserve PROMOTED repair validation and separate inspector IL governance, and obey phase/role/target/source/tool/version and context limits. Delivery and retraction share a transactional fence. A captured experience or staged improvement proposal is not evidence of learning benefit. Learning comparisons include all retrieval, curation and validation cost.

### Continuous service and approved recovery

The explicitly configured `FORGE_OPERATIONS_INTENT` file is OS-owned/private and outside the application mount in a deployment. Provision it through the existing authenticated operator path; absence/corruption is UNKNOWN, never automatic RUNNING. Its RUNNING/PAUSED/DRAINING/STOPPED epochs fence every bounded native/service start. Pause stops new admission; drain allows admitted work to settle. STOPPED stays unresolved until pending contrary service-manager work and possibly live workers settle. Intentional OS stop, disable and mask remain respected.

The continuous renderer uses the actual selected namespace profile and Conductor unit, `Restart=always`, bounded bursts, an independent watchdog, a false boot condition for stopped/unknown intent and `RestartPreventExitStatus=77` for completed operator shutdown. Namespace entry forwards the selected policy, authority paths, operations intent and bounded CPU-job setting; it does not forward unrelated provider/server credentials. Rendering is not installation or activation.

| Existing operational lane | Preconditions and bound |
|---|---|
| Conductor failed/start-limit recovery | Exact approved enabled unit, eligible failed result, current intent epoch and CRE-preauthorized `restart_conductor`; durable 600-second slow cooldown, no runtime `reset-failed`. |
| Local profile dependency restoration | Existing LRTX stack start recipe, pinned PID/boot/start ownership, RUNNING intent and CRE-preauthorized `restart_local_stack`; refuse uncertain inference ownership and unsupported live legacy PIDs. No process-name killing. |
| Native cancellation/reconciliation | Original job/mission/nonce, bounded persistent probes; cancel ACK does not release capacity, transport uncertainty stays visible. |
| Independent verifier recovery | One CPU worker, stable verification identity/epoch, heartbeat/deadline and exact boot/PID-start/process-group ownership; bounded reclaim and publication reconciliation. |
| Housekeeping/storage | Marked disposable scratch only, bounded files/bytes, preserve pins/archives/ledger/evidence. Missing/full/read-only storage closes affected admission without ephemeral fallback or destructive reset. |

These catalogue entries do not enable themselves. Existing CRE policy must explicitly preauthorize an operational action; engineering grant expiry does not renew or cancel separately authorized host supervision. Protected source fixes, policy changes, release decisions and persistent worker promotion still require external review. No automatic source deployment is implemented.

Keep the Conductor lifetime indefinite: no production `--max-cycles`, global exit on a failed/capability-limited job, empty queue, exhausted engineering allowance or campaign completion. Model-free health, dependency/backoff checks, native reconciliation and unrelated eligible work continue. Current authority and all remaining-capacity/resource checks must pass again before engineering work resumes.

### Qualification entry points

All live Qwen tests run on Omniverse2. Store local development/evidence/scratch on loop10. Existing valid authorization is used as-is; an exhausted or expired grant is not a retry allowance. See Feature 014 validation for exact blockers and executable commands.

- `forge_factory.afo.history_qualification`: replay a hash-pinned private dump into a NEW offline copy, preserve every legacy row, deduplicate historical native identities and prove no fresh capacity appears.
- `forge_factory.afo.qualification`: freeze/dry-run/provision/step/report for the 20x5 native protocol, RCC and fixed 30-product denominator; current signed campaign authority and independent oracle audits are mandatory for live results.
- `forge_factory.afo.systemd_qualification`: uniquely named transient local CPU-only service semantics; does not deploy or qualify the remote profile.
- `forge_factory.afo.operational_campaign` via the existing soak lane: 24/72/168-hour observation, bounded authorized faults, real work, gross outage/UNKNOWN accounting and later separately authorized intake. Ending the campaign does not stop continuous service.

Runtime implementation, local-model capability, sealed product outcomes, measured learning benefit and operational availability remain distinct. Short fixture/controller/systemd passes do not demonstrate RCC repair, benchmark success, a 168-hour soak or the rolling 30-day SLO. Future worker promotion stays proposal-only under the separate policy review.
