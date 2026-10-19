# ADR-AFO-001: AFO reuse map, authority and mode envelope

- Status: accepted for implementation (Feature 005, M0)
- Date: 2026-10-19
- Context: Feature 005 adds a 24/7 Conductor. Features 002, 003 and 004 already supply most of the machinery it needs.
  The capability matrix (`docs/afo-capability-matrix.md`) is generated from code checks, so it can't claim code that
  doesn't exist.

## Decision

1. **Reuse, don't duplicate.**
   - **Launch:** `workorder.run`/`prepare`, `fabro.runconfig.fabro_run` and `fabro.client.FabroClient`.
   - **Infrastructure health and repair:** the 002 supervisor, dispatch and `repair.infra`.
   - **Failure handling:** the 004 taxonomy, fingerprints, CAPA, reproducers, promotion gate, `SideEffectJournal`,
     `RetryAdmission`, `Breaker` and `ScopeLeases`.
   - **Measurement and output:** the 003 KPIs and `reliability.metrics` (Wilson); the event ledger
     (`events.emit`); `release.finalize`.
   - **New in AFO:** the durable queue/outbox/leases, launch reconciliation, cross-attempt checkpoint refs,
     recovery plans, dead letters and the mount sentinel.
2. **Separate authority store.** AFO state lives in `$FORGE_STATE_DIR/conductor/conductor.sqlite3` (M2). It links to
   002/004 records by stable id and never mirrors their mutable truth.
3. **Policy and modes** (`afo.policy`):
   - **Fail-closed loading:** a missing, unreadable, schema-invalid or floor-breaking policy is DISABLED.
   - **The floor:** `policy.FLOOR` re-checks every non-weakening invariant in code. A weakened schema alone opens
     nothing.
   - **Authorization:** DISABLED and OBSERVE_ONLY need none. PILOT and ACTIVE need the authorization the policy
     names (`authorization_ref`).
   - **The shipped policy is OBSERVE_ONLY.** Its models follow the owner's rules: DeepSeek, Codex through the forge
     ACP proxy, no local Qwen.
4. **Signed authorization** (`afo.authz`):
   - **Signature:** a detached OpenSSH signature (`ssh-keygen -Y`, namespace `forge-afo-authorization`) by the
     owner's own key. The repo holds only the public key (`config/factory/afo-allowed-signers`).
   - **What is checked:** the schema, the signature, the time window, revocation (field or `revoked.txt`), the
     policy sha256, the mode, the action and the scope.
   - **Agents never hold the owner key.** `authz sign` is an owner CLI.
5. **Authority intersection** (`afo.authority`). Every action needs every owner of that action to agree:
   - **The constitutional floor** (`FORBIDDEN`). Source deploy or merge, factory-code promotion, safety approval,
     release signing, edits to safety/CRE/AFO policy or to holdouts/oracles/archives/baselined evidence, enabling a
     CRE mode and hardware flashing are never AFO actions.
   - **The AFO mode and its authorization.**
   - **CRE, for the actions CRE owns** (service restart/reload, guarded side-effect retries). This needs the CRE
     policy's own mode and pre-authorized action list. AFO never edits CRE configuration or switches CRE mode.
   - **Every decision is recorded** in `<state>/afo/decisions.jsonl` (AFO-FR-006).
6. **Models.** AFO-T066 asks for a "local Qwen" end-to-end run. Under the owner rule of 2026-10-16 it runs with the
   approved DeepSeek/Codex profiles, and the Qwen variant is recorded as deferred by owner decision, not faked.

## Consequences

- Known distinctions to keep from 004:
  - CRE stays OBSERVE_ONLY.
  - CRE readiness has a hardcoded signed-runbook gate.
  - A sealed BLOCKED package is never an accepted delivery (AFO-FR-008).
- Host prerequisites (lingering, the fstab or mount unit, systemd credentials) are operator actions. AFO documents and
  checks them; it never invokes sudo.
- The authorization contract alone is not proof. Only `authz.verify` decides.
