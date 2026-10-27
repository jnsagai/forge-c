# WWDG unblock: engine capability, then one complete driver

Status: proposed external engineering scope; no SafeC implementation or policy
change is authorized by this document. This is not a safety signature request.

The owner asked whether progress matched the actual autonomy objective. Observer
and comparison increments are published, but 30/58 tasks, 0/3 READY and unproven
operational availability remain. The next useful outcome is one driver through the
unchanged gates, beginning with an independently demonstrated representability limit.

## Measured prerequisite

On Omniverse2, the pinned engine (source cf3b01b; binary hash recorded in evidence)
was called with twelve minimal, source-bound required WWDG operation forms. These
are deterministic external checks against the original frozen domain, not Qwen
suggestions, fabricated repair incidents or a new driver attempt. Nine returned
UNSUPPORTED; three ordinary reads passed both SafeC and Forge-C's independent
Python contract derivation. Total 14.055950 s, zero model requests.

| Required operation | Pinned profile result |
|---|---|
| Activate / query activation | UNSUPPORTED / UNSUPPORTED |
| Update / read counter | UNSUPPORTED / PASS |
| Update / read prescaler | UNSUPPORTED / PASS |
| Update / read window | UNSUPPORTED / PASS |
| Enable / query early-wakeup interrupt | UNSUPPORTED / UNSUPPORTED |
| Clear / query early-wakeup flag | UNSUPPORTED / UNSUPPORTED |

The baselined source has set-only (`rs`) activation/interrupt fields and a
write-zero-to-clear (`rc_w0`) flag. `register-io-0.1` cannot model those access kinds;
ordinary writes sharing a register with an unsupported field also remain unsupported.
This does not establish that every historical model answer was correct. It establishes
that another model answer cannot supply these missing verification semantics while
preserving the stated full driver scope.

Evidence: `evidence/014-durable-local-autonomy/wwdg-required-capability-20261027/`.
No original workorder, source domain, pin, archive, mission or spent inference budget
was changed. The historical three-request diagnosis study remains SPENT.

## Concrete proposed scope

1. Introduce an explicitly versioned SafeC capability for the exact documented
   set-only and write-zero-to-clear forms needed here. Keep the old profile frozen.
   Do not relabel either kind as ordinary read/write or suppress UNSUPPORTED.
2. Define reads, allowed set/clear values, prohibited transitions, reserved bits and
   read-modify-write sibling behavior. Keep unmodeled access kinds, side effects,
   mixed writes and timing/hardware obligations blocked. State register-image/model
   assumptions; this is not proof of arbitrary silicon behavior.
3. Extend the public bridge contract compatibly for the new profile and update
   Forge-C's independently derived contract checks. A profile, pin or schema mismatch
   must still block. Rust remains semantic authority; Python agreement alone grants
   no acceptance.
4. Before more Qwen work, detect required engine-capability limits without inference
   and retain a factual job disposition. This production change intersects the parked
   capability-disposition work; do not reopen DA-T036 without the owner's decision.
5. Qualify independently: positive reads/sets/zero-clears; illegal clear/value and
   out-of-range negatives; reserved-bit preservation; sibling effects; mixed/unknown
   access refusals; stale/tampered contracts; unchanged legacy acceptance/rejection;
   Rust/Python arithmetic diversity and the required actual formal checks. Preserve
   failed counterexamples and uncertainty. No golden evidence auto-acceptance.
6. Only after that qualification, prepare one fresh bounded WWDG workorder under
   current valid execution authority, with the same full scope and all normal gates.
   Preserve Job050 and all old expenditure. Development SSA/TAA deferral remains as
   already decided. A semantic extension does not itself prove driver READY,
   author/inspector qualification, learning benefit or autonomous recovery.

RNG/LPTIM semantic extensions, inspector tuning, production deployment, grant renewal
and automatic merging are outside this narrow proposed change. The 24/72/168-hour operational campaign prerequisites remain independently recorded.

## Approval boundary

The private SafeC checkout's `AGENTS.md` says: "Functional changes require
confirmation." It also requires isolated work, active feature instructions and real
formal checks for semantic changes. Feature014 qualification approval and development
SSA/TAA deferral are already recorded; neither specifically authorized this newly
identified change to SafeC's verification semantics. Confirm the narrow scope above
before modifying that implementation. Preserve its private/public source boundary.
