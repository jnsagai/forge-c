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
