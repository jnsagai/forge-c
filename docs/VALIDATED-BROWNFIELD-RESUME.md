# Resuming an existing-code work order

Brownfield runs can reuse accepted SWE phases in a new work order. This works
through `forge_factory.workorder.run`, the CLI and AFO recovery. All use the same
validator, delivery injection and native gates.

```bash
. scripts/forge-env.sh
python -m forge_factory.workorder \
  --example examples/0008a-rcc-ll-delivered --wo WO-RCC-next \
  --resume-from WO-RCC-previous --detach
```

For local profiles, run that command inside the profile's existing `lrtx.stack exec`
environment with the same `--profile` and an approved `--model`. AFO launch manifests
can specify `profile`, `resume_from` and `resume_upto`; its existing authorization,
material-difference and queue budgets still apply.

The source must be terminal and reachable through its recorded Fabro server. The
destination ID must be new. Forge-C checks the versioned input/runtime identity,
then reuses the leading intact PASS phases. For example, accepted SWE.1 and SWE.2
with an unfinished SWE.3 restart at SWE.3. To intentionally return earlier, use
`--resume-upto SWE.2`; an earlier invalid phase always wins.

The new work order runs its own intake. Delivery enters its workspace only after
the inherited SWE.1 gate passes there. Original baselines and inspections are copied
byte-identical, then the gates are rechecked. FROZEN code stays unchanged.
FIX_ALLOWED code corrections require accepted SWE.3, preserved CODE defects and a
fresh scoped delivery check. Open defects and upstream-loop counts are preserved.

Set the initial lineage's limits with `--resume-max-attempts` and
`--resume-max-wall-seconds` (defaults: six total attempts and 24 elapsed hours).
Resumes inherit those limits. A SQLite ledger at
`$FORGE_STATE_DIR/resume/lineages.sqlite3` prevents sibling attempts or process
restarts from resetting the budget. Copy failures still consume a reservation;
inspect the partial destination and choose a new ID rather than replaying it.
Native stage/tool hooks and structured calls refuse work after the inherited
deadline. Existing token/turn/AFO budgets remain in force; unreported tokens remain
UNKNOWN. Back up the lineage database with the work-order state.
The original budget is registered before model execution; losing that registry
refuses resume instead of giving an old source a fresh budget.

Version 1 requires an identical clean factory commit and runtime identity. A changed
input, tool, build configuration, delivery or profile is refused. Older work orders
without `resume_identity` must start fresh. There is no force-resume flag.

Review `.forge-run/resume/validation.json` for the exact hashes, accepted phases,
source run and restart reason. Offline packages contain
`configuration/resume-validation.json` and `configuration/resume-lineage.json`.
The source manifest is included as `configuration/resume-source-manifest.json`.
Inherited independence findings remain in the assurance assessment even when the
new attempt uses a different model pair.
Supporting evidence from unaccepted phases is never an accepted checkpoint; only
accepted-phase tool records are carried into the new authoritative tool ledger.
Assurance observations are retained only for accepted phases and only from their
latest inspections onward; validation records the hashes of both filtered ledgers.
