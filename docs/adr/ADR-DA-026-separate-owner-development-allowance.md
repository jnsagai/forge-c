# ADR DA-026 — A separate finite owner-development allowance

Status: implementation candidate; runtime and product acceptance remain separate.

The original mission ended at 4 of 4 attempts with no model request ever made. After
private rehearsal reached a native run, the owner said "propose something and go" in
answer to how many new attempts to grant. The proposal was two.

`mission_capacity.amend` is the existing way to add capacity. It needs an owner-signed
grant, which an agent can never produce, and the pinned policy caps it below the
current limits. The owner-development lane also pinned the exact original mission.
Refilling that mission would rewrite the record of what happened to it.

The lane moves to one separate mission, `line-local-role-trial-20261106`, with its own
lineage and orders L90E and L90F. It allows 2 attempts and 2 jobs, and keeps the
original request, token, tool and correction caps and fixed deadline. Every cap is at
or below the original. Runtime policy, line policy, profile, quality, role envelopes
and the ASPICE-only envelope are unchanged.

`owner_development_allowance.open_allowance` is the only writer. It runs outside any
agent or issued context, requires the owner's exact words, and adds one row. Replay
returns the same row. Different limits are refused by the ledger, so it cannot refill.
It does not admit work.

The spent mission is read, never written. `prior_conserved` pins its registration
digest, its counters and its unknown usage on every authority check, so a change to it
stops the lane. Spent orders L90B to L90D no longer authorize anything.

Reconciled bootstrap history stays valid. Issuers of the closed mission are compared
with how that mission ended, in `PRIOR_SCOPE`, and not with the allowance. Without this
a new guardian would refuse real reconciled rows as a scope change. Rehearsal removes
those rows from its private copy, so this is proven read-only on the real rows instead.

The mission records `OWNER-DEVELOPMENT-ALLOWANCE-20261106-NOT-A-GRANT`, not the policy's
signed grant reference. `mission_authority` keeps that distinction at the two places
that compare a mission with its control, because the pinned policy still names the
original grant.

Consequence: this allowance is unsigned, under the owner's standing "for now go on
without needing signatures" directive for this lane. It stays OWNER_SUPERVISED_DEVELOPMENT,
UNACCEPTED and qualification-only, and signed production rules are unchanged. An
exhausted allowance needs a new owner decision and a new source; nothing renews it.

L90E, the first allowance attempt, reached a native run and failed before any model
answered. The retained `fabro/settings.toml` came from an older profile and did not list
the run model, so Fabro sent no output limit and the gateway refused every call. Private
rehearsal runs a fresh `stack init`, which hid this. The owner lane now refuses to start
on any mismatch with `fabro_config`, and the transition regenerates the file.

Recovery then planned a continuation from L90E. The order envelope refused it, which is
correct, but the refusal was uncaught and ended the guardian. That refusal now stays an
outcome. Authority failures still stop the guardian. The envelope itself did not change,
so the only resume point stays L34G.

A new source means a new control, and recovery would have left L90E waiting under the old
one for good. `close_for_source_fix` closes it once, keeping its attempt, charge and plan,
and the Planner's normal retry places L90F. Rehearsal now starts from the real retained
settings and a copy of the real store after L90E.
