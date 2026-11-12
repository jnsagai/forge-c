# Research: Factory-prepared run inputs

Sources: tip `7f43f967` (branch feat/019, on 67092fad), live owner lane 2026-11-09 (guardian ecec42e9, cycle 70).

## R1 Where the ladder lives
- **Decision**: in `afo/owner_supervised_development.py` as `LADDER` (ordered lineage ids) next to `LINEAGES`, with a
  pure function `derived_campaign()` that returns the campaign document.
- **Rationale**: the allowance already enumerates the lineages it authorizes; deriving the campaign from the same table
  means a lineage can never be in the campaign without being authorized (FR-007/FR-008). Tests pin both.
- **Alternatives**: a YAML under `config/factory/campaigns/` (second source of truth that can drift from the
  allowance); keeping the package template (manual input).

## R2 How the deploy uses it
- **Decision**: the deployer generator calls `D.derived_campaign()` when the source has it, else falls back to the
  package template (rollback to an older source). It records `campaign_source: DERIVED|TEMPLATE` and, when a template
  exists and differs, its sha256 (FR-002 "difference recorded").
- **Rationale**: the generator already imports `D` from the source being deployed and already drops unknown lineages.
- **Alternatives**: moving the whole generator into the repo (larger change to reviewed deployer tooling).

## R3 Sequencing without building on (`after`)
- **Decision**: campaign key `after: {lineage, phase, verdict: PASS}`; `Planner.decide` sets `WAITING` /
  `AFTER:<lineage>:<phase>:PASS` until that lineage's chain has the phase; it never sets `provided_from`.
- **Rationale**: `depends_on` already implements the wait but also sets `provided_from`, which an LL order must not
  carry (allowance refuses). Same walk data (`dep.chain`), no new state.
- **Alternatives**: priorities only (a waiting step would let a lower one start: not one-at-a-time); ON_HOLD toggling
  (manual).

## R4 Phase list growth (L44F)
- **Finding**: `Planner.walk` finds attempts by order name per phase and chains on the newest passed attempt; it does not
  filter by lineage sha256 (only strikes do). Extending `wwdg-ll` to six phases after L44F passed SWE.1 makes the walk
  stop at SWE.2 with `prev = L44F`, and `decide` places CHAIN SWE.2 `resume_from` L44F (FR-005). The deployer quiesces
  (waits for no active order) before switching, so L44F is never interrupted.

## R5 Input gap
- **Decision**: in `decide`, after dependencies are satisfied and before the first order of a lineage is placed, if
  `examples/<example>/workorder.json` is missing in the running revision: `WAITING`,
  `INPUT_GAP:WORKORDER_SPEC:<example>`. Later steps wait on it through `after`.
- **Rationale**: `line_campaign.validate` checks only the example name pattern, so a missing spec today fails at launch
  (an issue, retries). Holding it before placement is cheaper and names the missing input.
- **Names**: SPI HAL `0011m-spi-hal`, TIM HAL `0013m-tim-hal` (the `0014m`/`0016m` HAL convention).

## R6 Floor ladder view
- **Finding**: the guardian writes one row per cycle to
  `~/.config/forge-c/line-local/owner-supervised-development/<record>.audit.jsonl` with
  `placement.lineages[] = Plan.view()` (lineage, state, reason, phase, wo, provided_from, next). The production feed's
  `placement` is null (the production conductor observes).
- **Decision**: `owner_lane_panel` reads the last row of the newest audit file (bounded tail read) and returns
  `ladder[]` ordered by the ladder (priority); the page draws a step strip with done/running/waiting/input-gap.

## R7 One step at a time
- **Decision**: every ladder step after the first carries `after` (LL steps) or `depends_on` (HAL steps) on the previous
  step's last phase; priorities descend along the ladder. Only one step is ever eligible.

## R8 Contract
- **Decision**: add `after` to `specs/014-durable-local-autonomy/contracts/line-campaign.schema.json` (not a protected
  path) and to `LINEAGE_KEYS`; the cycle check walks `depends_on` and `after`.
