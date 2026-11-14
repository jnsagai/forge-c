# T016 design (for owner review): item-level impact instead of whole-phase staleness

Status: PROPOSED 2026-11-14, not implemented. Owner review is required because it changes when an inspection PASS
still holds.

## Today

`inspection/engine.Store.stale_reason(phase, baseline)` makes a phase's frozen baseline (and with it its inspection
PASS) stale when ANY file of the phase or ANY upstream baseline hash changed (`BASELINE_CHANGED_AFTER_FREEZE`,
`UPSTREAM_CHANGED:<phase>`). Users: `inspection/gate.py:229` (reuse of a passed phase), `gate.py:741` (defect route
intact check), `development_demonstration.py:195`, `engine.py:305/428`. One changed SWR therefore re-inspects every
later phase in full.

## Proposal

1. **Item graph per baseline.** At freeze, record in the baseline an `items` map: item id -> {digest, depends_on}.
   Items: SWE.1 requirement (SWR id -> statement+attributes sha), SWE.2 interface function / allocation entry,
   SWE.3 unit (`code:<SWU>` record sha), SWE.4 unit test, SWE.5 integration test, SWE.6 scenario; `depends_on` from the
   existing trace links (allocation, @spec/@unit tags, test traces). Built with `assurance/impact.ImpactGraph`.
2. **Impact walk.** `stale_reason` stays the authority. A new `impacted_items(phase, baseline)` returns the items whose
   own digest or any dependency digest changed (ImpactGraph.affected over the changed upstream items).
3. **Where it is used - carry orders only.** Only a rerun of the same order series (feature 021 carry) may use the walk:
   the phase is re-inspected on the impacted items plus every set-level check; unaffected items keep their earlier
   item verdicts, listed in the carry manifest as CARRIED (source order, record sha) - never as a direct PASS of the
   new run. The phase verdict of the new run is still decided by its own inspection gate.
4. **Never weaker.** Any item without a dependency record, any changed checklist/criteria, any changed tool image or
   upstream baseline without an item map -> whole-phase staleness exactly as today.

## Risks and what the owner decides

- Item-level reuse makes a phase verdict depend on earlier item verdicts. The rule "never label an earlier revision's
  result as a new direct PASS" holds only if the carry manifest and the inspection record keep CARRIED and DIRECT
  apart - the inspector would judge set-level items on the whole new set every time.
- Decision needed: (a) accept item-level reuse for carry orders as above, (b) only for SWE.4-SWE.6 tool evidence
  (already hash-bound by T014), or (c) keep whole-phase staleness.

Tests to write first: a changed SWR re-inspects only its traced items; an item without a dependency record forces the
whole phase; the carry manifest lists the carried item verdicts; set-level checks always run.
