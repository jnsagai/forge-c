# Data model: USART benchmark pilot - SWE.1 the benchmark way

All entities are module-agnostic; UART-specific values live only in the UART work order's data.

## SWE.1 level setting (work order → manifest)

| Field | Where | Rule |
|---|---|---|
| `swe1.level` | work order | `functional` or `register`; absent = register (today) |
| `swe1.template` | work order | template version id, e.g. `swe1-functional-v1` (config/factory/swe1-functional-template.yaml) |
| `swe1_level` | manifest | stamped **only when** the work order sets `swe1.level: functional`; absent otherwise (existing manifests byte-identical) |

Effects of `swe1_level == functional`: no `register_contract` stamp; SWE.1 structured with the functional author;
governance node + coverage check before the author; SWE.2+ refused (`SWE1_FUNCTIONAL_LATER_PHASES_NOT_YET`).

## Module scope rule (work order, data)

| Field | Meaning |
|---|---|
| `module.name` | module name (e.g. `UART`) |
| `module.components[]` | `{id, layer (LL/HAL), files[] (delivery paths), uses[] (other component ids, may be empty)}` |
| `scope.in[]` | groups `{group, functions[] (exact names or `prefix*` patterns), rm_features[] (RM section ids)}` |
| `scope.out[]` | groups delivered but out of benchmark scope, same shape |
| `scope.not_delivered[]` | `{capability, note}` - capabilities the reference process has and the delivery lacks (generic wording) |
| `use_cases_owner[]` | optional owner-provided use cases (same shape as Use case, `origin: owner`) |

Validation (prepare, INPUT_GAP on failure): every delivered public function matches exactly one of `scope.in` /
`scope.out`; no pattern matches nothing; components cover every delivered file.

## Input register entry (governance inventory)

| Field | Meaning |
|---|---|
| `input_id` | stable id (`IN-NN`), derived from the order's input list order |
| `name`, `revision` | document name and revision (from the inputs manifest) |
| `sha256`, `bytes` | content fingerprint (as `manifest.inputs`) |
| `role` | `requirement_source` or `implementation_under_analysis` (delivered code, always the latter) |
| `sections[]` | for RM inputs: section ids and page ranges (from the existing section split) |

## Delivered API inventory entry

| Field | Meaning |
|---|---|
| `function` | public function name |
| `component` | component id |
| `file` | delivery path |
| `scope_class` | `in`, `out` |
| `scope_group` | group name from the scope rule |

## Governance package (output of the governance step)

| Field | Meaning |
|---|---|
| `package_version` | sha256 of the canonical package |
| `inventory_sha256` | the inventory it was generated from |
| `actors[]` | `{actor_id, name, description}` |
| `use_cases[]` | `{use_case_id, title, actor_id, goal, functions[] (in-scope names), rm_features[], origin (generated/owner)}` |
| `assumptions[]` | `{assumption_id, text}` |
| `open_points[]` | `{open_point_id, text, concerns[] (functions/features/input ids)}` |
| `coverage` | `{uncovered_functions[], uncovered_features[], unused_use_cases[]}` - computed deterministically |

State: `GENERATED` → `COVERAGE_PASS` (SWE.1 may start) or `COVERAGE_FAIL` (SWE.1 stops, items named).

## Functional software requirement

| Field | Set by | Rule |
|---|---|---|
| `id` | assembly | `SWR-NNN` (existing format) |
| `key` | author | stable key within its task |
| `title` | author | short title |
| `statement` | author | EARS; level rule: no register, field, address, reset value |
| `type` | author | functional, design_constraint, architectural |
| `precondition` | author | text or `none` |
| `origin_group` | author | use_case, out_of_context, hal_design_constraint, state_behaviour, awaiting_traceability |
| `links[]` | author | `{kind: trace/derive, input_id, locator, rationale}`; rationale required for derive; empty only for awaiting_traceability |
| `use_cases[]` | author | use-case ids it serves (may be empty for constraints) |
| `verification_method` | author | test, analysis, inspection, demonstration; design_constraint ⇒ inspection |
| `test_level` | author | unit, component, integration, qualification, not_testable |
| `status` | assembly | `draft` |
| `asil`, `cal` | assembly | `QM`, `0` (lane) |
| `allocated_interface`, `allocated_operation` | assembly | `not applicable until SWE.2` |

Validation errors carry the requirement id and the failed rule (gate rejection text).

## Benchmark metrics (private file, outside the repository)

| Field | Meaning |
|---|---|
| `requirement_count` | integer |
| `by_type` | category → count |
| `attribute_completeness` | attribute → share present |
| `by_origin_group` | generic category → count |
| `link_kinds` | traced/derived/awaiting → count |
| `verification_methods`, `test_levels` | category → count |

Only numbers and generic category names; no text, identifiers or names from the benchmark.

## Decision log entry

| Field | Meaning |
|---|---|
| `date` | ISO date |
| `rule` | the rule decided |
| `decided_by` | owner / factory |
| `rationale` | why |
| `evidence` | refs (commit, run, metric) or `pending` |
| `status` | adopted / rejected / open |
