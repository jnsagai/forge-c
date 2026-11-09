# Data model: Two-phase SWE.1 inspection

All records are JSON under the work order's workspace `.forge-run/lrtx/SWE.1/` (private run state) unless noted.
No record stores prompts, model reasoning or raw answers beyond the structured answer the existing checkpoints keep.

## Requirement under inspection (`RequirementRef`)

| Field | Type | Rule |
|---|---|---|
| `swr` | str | `SWR-NNN` as assembled (display id; may change after set rework) |
| `key` | str | stable requirement key inside its author task answer (identity across renumbering) |
| `task` | str | owning author task (`requirements:<REG>[_n]`, `requirements:CROSS`, budget/performance tasks) |
| `statement_sha256` | str | sha256 of the canonical requirement object (statement, source_page, verification, verified_by, effects) |

Source: `assembly.json` (`swr -> {task, key}`) plus the task checkpoint answer.

## Quality checklist (`quality-checklist`)

Versioned file `config/factory/swe1-requirements-quality.yaml` derived from the pinned guideline:

| Field | Type | Rule |
|---|---|---|
| `schema` | str | `forge-c/swe1-quality-checklist/1` |
| `guideline` | obj | `{path, sha256, version}`; the sha256 must equal the file in `docs/` |
| `individual[]` | list | `{id: IQ-01..IQ-12, property, criterion}` |
| `set[]` | list | `{id: SQ-01..SQ-10, property, criterion}` |
| `severities` | list | `BLOCKING, CORRECTABLE, EDITORIAL, N/A` |
| `phase1.rounds` | int | default 3 (>=1) |

## Finding

| Field | Type | Rule |
|---|---|---|
| `requirement_id` | str | SWR id, or `SET` for a set-level finding |
| `quality_id` | str | `IQ-01..IQ-12` (phase 1) or `SQ-01..SQ-10` / `SWE1-0n` (phase 2) |
| `severity` | enum | `BLOCKING`, `CORRECTABLE`, `EDITORIAL`, `N/A` |
| `evidence` | str | exact quote of the requirement / input reference; <= 400 chars |
| `required_action` | str | what must change; <= 300 chars |
| `input_uncertainty` | bool | true when the defect is a missing/contradictory input (NEEDS_INPUT), not an author defect |

`N/A` requires a non-empty `evidence` reason. A finding needs rework iff severity in {BLOCKING, CORRECTABLE} and
`input_uncertainty` is false.

## Individual verdict (`phase1/verdicts/<key>.jsonl`, one line per round)

| Field | Type | Rule |
|---|---|---|
| `key`, `swr`, `task` | str | from RequirementRef |
| `round` | int | 1..rounds |
| `statement_sha256` | str | the requirement judged |
| `findings` | list[Finding] | phase-1 findings only (IQ ids) |
| `passed` | bool | no finding needs rework |
| `at` | str | UTC |

Checkpoint rule: a verdict for `(key, statement_sha256)` is reused, never re-requested (FR-011, SC-005).

## Requirement rework result (`phase1/rework/<key>.jsonl`)

| Field | Type | Rule |
|---|---|---|
| `key`, `round` | | |
| `before_sha256`, `after_sha256` | str | canonical requirement object before/after |
| `status` | enum | `CHANGED`, `UNCHANGED` (stop: no progress), `REFUSED_OTHER_CHANGED`, `INVALID` |
| `errors` | list[str] | validator findings of the author answer (existing SWE.1 validators) |

Invariant (FR-004): after a `CHANGED` result every other requirement's `statement_sha256` equals its value before the
rework; otherwise `REFUSED_OTHER_CHANGED` and nothing is written to the task checkpoint.

## Phase-1 summary (`phase1/summary.json`)

`{schema, guideline_sha256, checklist_sha256, rounds, requirements: n, passed: n, carried: n, swaps: n,
 carried_findings: [Finding...], ended: "ALL_PASSED"|"ROUNDS_USED"|"NO_PROGRESS"}`; input to phase 2.

## Set verdict (phase 2)

The existing inspection record (`inspections.jsonl`, verdict files per SWE1 item) unchanged, plus one verdict per SQ
criterion with Finding entries (`requirement_id` may be `SET`), recorded beside the checklist verdicts. The gate
decision is computed from SWE1-01..08 only (FR-010).

## State transitions (per requirement in phase 1)

`PENDING -> JUDGED(passed) -> DONE`
`PENDING -> JUDGED(failed) -> REWORKED(CHANGED) -> PENDING (next round)`
`JUDGED(failed) -> REWORK UNCHANGED | REFUSED | INVALID -> CARRIED` (no further rounds for that requirement)
`JUDGED(failed) at last round -> CARRIED`
