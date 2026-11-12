# Data model: Factory-prepared run inputs

## Driver ladder (source)
- `LADDER`: ordered tuple of lineage ids. Initial value:
  `wwdg-ll, wwdg-hal, spi-ll, spi-hal, tim-ll, tim-hal`.
- Each id must name an entry of `LINEAGES`; no duplicates; a HAL step's `depends_on` LL must appear earlier.

## Lineage (allowance table entry, `LINEAGES`)
| field | rule |
|---|---|
| id, tag, series, example, driver_class | unique id; (tag, series) unique |
| phases | SWE.1..SWE.6 |
| depends_on | `None` for LL; the LL lineage id for HAL |
New entries: `spi-hal` (SPIH, 20261109-L46, `0011m-spi-hal`, STM32N6_SPI_HAL, depends_on spi-ll), `tim-hal` (TIMH,
20261109-L47, `0013m-tim-hal`, STM32N6_TIM_HAL, depends_on tim-ll).

## Derived campaign (generated per deploy)
`derived_campaign()` -> `forge-c/line-campaign/1` document:
- every `LINEAGES` entry appears; `status` ACTIVE when on the ladder, ON_HOLD otherwise;
- `phases` SWE.1..SWE.6; `factory_revision` `@SOURCE@` (the generator substitutes the deployed commit);
- `priority`: 50 for the first ladder step, descending by 1; off-ladder 30;
- ladder step k>0: HAL -> `depends_on {lineage: <its LL>, phase: SWE.6, verdict: PASS}`; LL ->
  `after {lineage: <step k-1>, phase: SWE.6, verdict: PASS}`;
- `quality`: the pinned ASPICE_ONLY block (digest == `QUALITY_SHA`).

## Plan state (line, per cycle)
Existing `Plan.view()` plus new reasons:
- `AFTER:<lineage>:<phase>:PASS` (state WAITING) - waiting for the previous ladder step;
- `INPUT_GAP:WORKORDER_SPEC:<example>` (state WAITING) - the step's spec is missing in the running revision.
Transitions: WAITING(AFTER) -> WAITING(INPUT_GAP) | QUEUED -> RUNNING -> ... -> DONE (ALL_PHASES_PASSED).

## Floor ladder view
`owner_lane.ladder[]`: `{lineage, state, reason, phase, wo}` in ladder order + `at` (cycle time). Codes and ids only.
