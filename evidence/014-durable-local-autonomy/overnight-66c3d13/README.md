# Eight-hour local Qwen continuation

Owner instruction: "I want a brute force continuation on omniverse, for8 hours".
Source **66c3d13d38b401129023b2a20b3e0239ef844f74**; common window
2026-10-27T22:28:12Z through **2026-10-28T06:28:12Z**. Dedicated controller and
existing mission recorder are active on Omniverse2. RCC is RUNNING with the first
request admitted; IWDG follows serially. This is experimental engineering work,
not proven production readiness, product success, self-healing or24/7 availability.

The existing production grant remains current. An additional qualification grant
binds these exact two orders, source, Qwen model/digest/precision/profile, bounded
role configurations and expiry. Admission rechecks frozen bytes, owner signature,
order/model/source scope, complete serialized context and existing mission/job/
request limits. It never writes a capability-success receipt. Ordinary jobs still
require their independently measured role capabilities. Inspector sampling and
configuration are unchanged. All author/inspection/native release gates remain.

The existing AFO scheduler alone admits/dispatches/reconciles/recovers work.
Finite recorder intake publishes mission identity and lineage before exposing
QUEUED work, and adopts the original deadline on restart. Per-attempt prospective
40k/30k/20k allocations remain inside each120k total; no old charge is reduced or
mission replenished. Each order retains3attempts,4recovery jobs,32requests/tools,
1correction and6h maximum, capped by the common window. Exhaustion may end useful
engineering earlier; the factory remains alive. No claim of continuous GPU duty.

The first prepared trial was never admitted; a queue-publication ordering fix
changed the source pin. Its grant was explicitly revoked and its files retained
before the replacement study began. Historical4BLOCKED orders/20attempts remain
untouched. These two prospective role experiments do not reset their allowances.

Native tests were terminal before Qwen dispatch. No competing GPU test/model was
started. All new local files remain on loop10. Raw prompts, hidden reasoning,
credentials and private ST inputs are excluded from progress commits.

## Verification

Exact source66c3d13 local:127PASS,0fail/skip,18.854s. Command:

```
FORGE_REPO_ROOT=<source> PYTHONPATH=<source>/factory/python PYTHONDONTWRITEBYTECODE=1 \
FORGE_FABRO_BIN=<installed-fabro> <venv>/bin/python -m pytest -q \
 factory/python/tests/test_da014_overnight.py \
 factory/python/tests/test_da014_product_role_trial.py \
 factory/python/tests/test_da014_integration.py \
 factory/python/tests/test_da014_protocol.py \
 factory/python/tests/test_da014_qualification_state.py \
 factory/python/tests/test_afo_local_autonomy.py \
 --basetemp=<loop10>/overnight-66c3d13-tmp --junitxml=<loop10>/overnight-66c3d13-tests.xml
```

Focused Omniverse2:11PASS,0fail/skip,0.693s, the first two files above, isolated
data/state/events,60s hard bound. Broad native lane failed/incomplete: the isolated
continuity fixture had no stable-volume marker, and attempted interruption during
SQLite journal waiting caused a transaction teardown error. SIGINT was intercepted
by a test-installed Conductor handler; later stop checks found the process already
terminal. No affected production process was signaled. Retain the private complete
log and actual outcomes; do not claim the broad lane passed. Earlier local WIP
failures (immutable-fixture tampering setup and absent Fabro environment) remain.

Both RCC and IWDG real workorders were prepared via existing run(intake_only=True)
before launch, with the unchanged pinned profile and private authoritative inputs.
This is preparation, not model qualification. New source passes Ruff on the trial,
recorder and new test modules. Formal ledger30/58 unchanged; no task completed.

## Overnight records and resume

Remote progress Git: `/mnt/data/forge-c/production-local-014/overnight-progress-20261027`.
Published branch:
https://github.com/jnsagai/forge-c/tree/overnight/2026-10-27-local-qwen-8h
Every5minutes records order/attempt state, request count and resource ownership.
Existing same-repository Git configuration was reused after the first publication
failed; no private key was copied/read by the agent. Remote commits remain durable
if later publication fails. Actual artifacts and request accounting remain in the
authoritative runtime store, not inferred from the progress count.

Operator status:
`/mnt/data/forge-c/production-local-014/deployment/forge-c-operator status`.
Controller:`forge-conductor-local-omniverse2.service`;
watchdog:`forge-afo-watchdog-014-omniverse2.timer`;
recorder:`forge-qwen-mission-recorder.service`. Original units/database backup remain
under deployment/rollback. Never replay the one-time cutover/activation scripts.

The owner requested conserving Codex credits while the remote work continues.
Pause the Codex goal after this checkpoint. On resume inspect live/native liveness,
original mission costs, actual phase gates, sealed packages and Git history before
further work. No automatic merge, source promotion, renewed grant or hardware release.
API bridge recovery after backend/host restart remains unverified; no24/72/168-hour
campaign, RCC recovery qualification,30-product benchmark or learning benefit claim.
