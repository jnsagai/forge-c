# ADR-DA-018: Operating authorization until owner stop

Owner instruction, 2026-11-21: “remove any authorization expiration, it should run forever”.

The deployed development guardian previously ended on 2026-11-19 at 03:07:06 UTC.
Its mission and qualification checks shared that cutoff. Removing one timer would
leave the factory unable to dispatch. A far-future timestamp or automatic signing
would misrepresent the owner's requested lifetime.

An external OS-owner administration command now issues an append-only standing
operating receipt for the existing campaign E mission. The receipt references a
content-addressed file in the private operations directory, inaccessible to runtime
agent writes. It binds the original mission record, current accounting snapshot,
host owner context and exact owner directive. Installation requires quiescent
native execution. It performs no dispatch or budget refill. No production MCP
operation exposes issuance.

Effective mission time becomes `deadline: null` with the explicit
`authorization_lifetime: UNTIL_OWNER_STOP` marker. Historical mission records,
finite signed grants, qualifications, source/policy bindings and usage counters
are preserved. Runtime issuance and each subsequent request still require the
live kernel-bound guardian and current RUNNING operations Intent. Pause, stop,
changed Intent epoch, lost guardian, changed source or changed receipt refuse
new work. A reboot requires a newly issued live guardian, without a calendar
renewal or signing key.

Finite jobs, verifier deadlines, request caps, retry limits, cumulative budgets,
repair protected paths, inspection, release review and recovery storm controls
remain enforced. Infinity is used only as a comparison bound in Python; it is
never stored as a JSON deadline or used to create an unbounded job. Resource
exhaustion remains visible and cannot be concealed by this time-only change.

`test_mission_lifetime.py` verifies conserved history, post-cutoff reservation,
budget refusal, external-owner-only issuance, snapshot freshness, tampering,
quiescence and finite job/verifier deadlines. The owner guardian integration test
advances a century beyond the old cutoff, checks qualification scope and verifies
that owner stop fences both normal admission and the final launch guard. Existing
finite-mode expiry tests remain required. Test and deployment receipts are stored
separately; this decision is not evidence that a deployed campaign has passed.
