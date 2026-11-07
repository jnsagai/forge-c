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

Before L90F, a comparison with real history showed that a real SWE.6 run makes 48 to 218
model calls. Each call is one mission request, and the mission and policy allowed 32, so
L90F could not have finished. No earlier attempt had made a request, so this limit was
never reached. The owner chose to raise the limits unsigned, in this lane only.

A third mission, `line-local-role-trial-20261106b`, takes the last attempt, order L90F:
1 attempt, 2 jobs, 256 requests, 512 tools, 16,777,216 tokens. A product job reserves its
whole budget of 8,388,608, so the mission total also covers one recovery job. The policy
copy changes only `max_model_tokens_per_order` and `max_inference_requests_per_order`, and
the pin moves with it. Both earlier missions stay closed and are pinned on every authority
check, and the signed grant the policy names is not changed.

L90F made 41 real model calls, but most tool calls were denied. The tool hook lacked the
queue scope, so accounting opened a different store that held no mission. Recovery could
not launch either, because its authorization asked for a signed grant file this lane
does not have. Stub rehearsals made no tool calls, so neither showed. Both are fixed.

The owner then asked for as many attempts as required. The ledger only accepts finite
limits, so a fourth mission, `line-local-role-trial-20261106c`, allows 32 attempts with
one attempt's budget multiplied through, orders L90G onward and the same deadline. A
blocked order whose run really ended now leads to the Planner's own retry from the
original seed. An order closed without a run still stops the line: those add no strike,
so retrying them would spend every order name in minutes. A failure before native launch
also stops and waits, spending nothing. The rule that stops a lineage on a repeated issue
is unchanged, and the seed stays the only resume point.

Recovery launches, but the planner role is not in the approved role list, so the gateway
refuses it. Retries run without a diagnosis. Adding that role would widen the approved
scope and is left to the owner.

L90G proved the path with real tools, then `run_robot` failed 21 times before any test ran.
Contained tools recheck the guardian through the operations Intent, and the tool server's
environment did not carry its path. Run by hand with the path added, the same call ran
Renode and passed 13 of 24 tests. The tool environment now carries it, and the mission and
its limits are unchanged.

L90T to L90W each ended the same way. The gateway refused the author with
`CAPABILITY_LIMIT`, and the same-issue rule stopped the line after four runs. The refusal
records show `utf8_byte_upper_bound`: this profile had no `request_measurement` entry, so
serialized bytes were counted as tokens, about three times the real prompt. Refusals came
at about 38,000 real tokens of a 262,144 limit. The Ornith route is now measured natively, and a
measuring failure refuses the request. No limit changes, including the 131,072 reasoning
allowance, and the Qwen route stays on the byte bound because it was never refused. A
durable `CAPABILITY_LIMIT` now returns 400, since repeating the same body cannot help.

The route is named in `request_measurement.py`, not in the profile file. That checksum is
bound into issued guardian records and `services.json`, and a review showed a changed file
would refuse the next guardian after the old stack had stopped. So the file does not fully
describe this profile's gateway behaviour until a migration moves the entry into it. The
mission is unchanged.

L90X was not refused, and it scored 0 of 24. Each stage has 35 tool calls, and the agents
spent nearly all of them searching, so the test bodies were never written. A retry also
started empty, which threw away L90V's 15 of 24. A retry in this series now copies the test
files of the earlier attempt that passed the most. They stay a draft: uncommitted, retested
and reinspected, and no earlier verdict carries over. The seed stays L34G for every
upstream phase. Stopped lineages and low disk now raise a real GitHub issue in this lane,
once per cause and with no mention. The repository is public, so those issues hold only
order names and failure codes. The 35-call limit, the same-issue rule and the policy files
are unchanged.

L90Z started from L90V's tests at 15 of 24 and reached 24 of 24 tests and 22 of 24
requirements, then broke the build trying the last two and ended at 18 of 24. Choosing by an
attempt's last result would have carried that broken state. A retry now restores the files of
the single best robot run of any earlier attempt, most tests then most requirements, from the
SHA-256 snapshots each run already records, and refuses a run whose bytes do not match.

Owner, 2026-11-07: raise every limit that can stop autonomous operation. Each author stage
had 35 tool calls, set on 2026-10-15 for qwen3:8b, and L90X lost a whole attempt to it. Authors
now have 4,096 calls per visit (the structured-visit ceiling) and every other role 200; inspectors still keep their last 4
calls for the verdict. The skill text also told agents to stop near a 32,000 or 16,000 token
stage budget, which only the v0.4 supervisor enforces; it is now 50,000,000 for authors and
5,000,000 otherwise. Stage timeouts, the per-order token envelope and the mission limits still
bound every visit. The AFO planner and maintainer skills are left as committed: regenerating
them would also rewrite unrelated text.
