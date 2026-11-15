# Defect mode on the line: first real runs and loop gaps (2026-11-15)

Owner rule (2026-11-14): factory defects are found and fixed by Omniverse - observer, CAPA, maintainer on the model
service, CRE gate, deployer. The engineer works only on that loop and hands a defect in (symptom and location, no fix,
no reproducer) only when the loop did not route it.

## Runs

| When (UTC) | Event | Who |
|---|---|---|
| 12:17 | SPI L51C blocked (rework budget); in-line maintainer returned no receipt; lineage held DURABLE_SOURCE_BLOCKED | line |
| 12:46 | CAPA-263 handed in (FACTORY_DEFECT key, symptom only) | engineer |
| 12:48 | defect mode picked CAPA-263, drained the lane, started the model tier | Omniverse |
| 13:16 | maintainer candidate fec9274c (line_recovery_coordination + its own test), 22 min, unattended | Omniverse |
| 13:16 | pre-gate REJECTED: RPR-131/143/149 CONTROL_CHANGED (stale v1 reproducers in the runner checkout) | loop gap 1 |
| 13:22 | window restored the lane; the restart revision released the held lineage; L51D placed | Omniverse |
| 18:20 | L51D ended (in-run model swap refused LINE_STACK_EXECUTION_CHANGED_BEFORE_SERVE) | line |
| 18:21 | durable recovery retry L51E refused OWNER_DEVELOPMENT_ORIGINAL_ORDER_ENVELOPE_REQUIRED; order WAITING_RECOVERY with no further event | line |
| 18:53 | CAPA-265 handed in (retry_of + resume_from refused by the envelope) | engineer |
| 19:01 | CAPA-266 loop fix 3d24d0c4 gated ELIGIBLE | engineer (loop) |

## Loop gaps and fixes

1. **Runner reproducer manifest** - the maintainer pre-gate read the runner checkout's manifest (179 reproducers,
   RPR-131/143/149 at v1) while the deployer gate reads the host oracle (235, v2 re-frozen 2026-11-11). Host fix: the
   runner's `tests/reliability/reproducers` points at the oracle's; timer `forge-022-maint-follow` keeps the runner on
   the live commit and restores the tracked directory around each checkout.
2. **Stalled recovery holds the maintenance window** (CAPA-266, 3d24d0c4, RPR-266) - `OwnerLane.idle` counted every
   WAITING_RECOVERY order as active; one without a lifecycle event for 30 min is now stalled, not active.
3. **Stalled recovery holds the deployer** (host, same rule) - the deployer's quiet check reports such an order
   WAITING_RECOVERY_STALLED; the quiet wait no longer runs to its 8 h deadline for an order that cannot move.

## Still open (Omniverse's to fix)

- CAPA-263: in-line maintainer without receipt; lineage held DURABLE_SOURCE_BLOCKED without a bound.
- CAPA-265: SWE.1 durable-recovery retry of an order that was itself a line retry is refused by the envelope.
