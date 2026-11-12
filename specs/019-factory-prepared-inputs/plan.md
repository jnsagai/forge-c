# Implementation Plan: Factory-prepared run inputs

**Branch**: `feat/019-factory-prepared-inputs` | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/019-factory-prepared-inputs/spec.md`

## Summary

Move the owner's driver ladder (per peripheral LL SWE.1-6, then HAL on it; WWDG, SPI, TIM) into the factory source
next to the owner-lane allowance, derive the line campaign from it at every deploy, and let the line walk it: a new
campaign key `after` makes a lineage wait for another lineage's last phase without building on it; the existing
`depends_on` keeps a HAL on its LL result. A ladder step whose work-order spec is missing is held as `INPUT_GAP`. The
floor shows the ladder from the guardian's per-cycle plan record. The allowance already carries `wwdg-hal` (67092fad);
it gains `spi-hal` and `tim-hal` (specs missing, held as input gaps).

## Technical Context

**Language/Version**: Python 3.13 (factory `uv` project), HTML/JS (floor page)
**Primary Dependencies**: existing modules only - `afo/owner_supervised_development.py` (allowance, LINEAGES),
`afo/line_campaign.py` (campaign schema and validation), `afo/line_orders.py` (Planner walk/decide), floor
`lrtx/owner_lane_panel.py` + `dashboard/static/factory-floor.html`; deployer tooling
`generate-development-inputs.py` (deploy package, untracked)
**Storage**: campaign YAML generated per deploy; guardian cycle audit JSONL (read-only for the floor)
**Testing**: pytest (`uv run --frozen pytest`), node 20 for page script checks (local), `tests/spec/validate_design.py`
**Target Platform**: Omniverse2 owner lane (guardian + deployer timer)
**Project Type**: single project (factory Python package + floor page)
**Performance Goals**: next ladder step placed within one guardian cycle after the previous step passes (SC-002)
**Constraints**: one GPU run at a time; mission E caps/deadline unchanged; CRE gate before deploy; production Line
Conductor (pinned d77709f4) and signed controls untouched; five pinned adapters untouched
**Scale/Scope**: 8 owner-lane lineages (5 LL existing + 3 HAL), ladder of 6 steps

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| I Safety/correctness first | PASS | HAL admission tightened, not loosened: provided_from only an own-LL SWE.6 order; provided_ll keeps the six-gate check (ADR-0009). |
| II Evidence driven | PASS | campaign records its source revision; HAL orders record provided_from; input gaps recorded in the plan view. |
| III Unattended, external release | PASS | removes the last manual step between drivers; no release claims. |
| IV/V SKILLs, MCP | N/A | no new AI role or tool. |
| VI Model-free supervision, bounded healing | PASS | ladder walk is deterministic Planner logic; no model calls. |
| VII Evidence-based knowledge | N/A | |
| VIII Traces | PASS | floor reads codes/ids only from the guardian record. |
| IX Minimal model cost | PASS | no extra model work; held steps place nothing. |
| X OSS, clean interfaces | PASS | one new campaign key with a contract update. |

Gates: no violation. Post-design re-check: unchanged (PASS).

## Project Structure

### Documentation (this feature)

```text
specs/019-factory-prepared-inputs/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/driver-ladder.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
factory/python/forge_factory/afo/
├── owner_supervised_development.py   # LINEAGES += spi-hal, tim-hal; LADDER; derived_campaign()
├── line_campaign.py                  # key `after`, validation, cycle check over depends_on+after
└── line_orders.py                    # decide(): AFTER wait, INPUT_GAP hold
factory/python/forge_factory/lrtx/
└── owner_lane_panel.py               # ladder view from the guardian cycle audit
factory/python/forge_factory/dashboard/static/factory-floor.html   # ladder strip in the owner-lane panel
specs/014-durable-local-autonomy/contracts/line-campaign.schema.json  # `after`
factory/python/tests/test_f019_*.py
# deployer tooling (untracked, owner-autodeploy package): generate-development-inputs.py uses D.derived_campaign()
```

**Structure Decision**: single project; the ladder lives in `owner_supervised_development.py` beside `LINEAGES` so the
allowance and the ladder cannot drift (one source of truth, pinned by tests).

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| One-time edit of the untracked deployer generator | the generator must take the campaign from source | keeping the package template means a hand-edited input (the owner's objection) |
