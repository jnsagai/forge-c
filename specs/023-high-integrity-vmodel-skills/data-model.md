# Data Model: Feature 023

All machine records are JSON (UTF-8, sorted keys when hashed). Schemas live in [contracts/](contracts/). Paths are
relative to the user's project root.

## ProjectConfig: `.hi/project.json`

| Field | Type | Rule |
|---|---|---|
| `schema` | const `forge-c-hi/project@1` | |
| `project_id` | string `^[a-z0-9-]{3,64}$` | |
| `profile` | enum `generic`, `iso26262`, `iec61508`, `aspice40` or a custom profile id | default `generic` (FR-009) |
| `integrity_level` | `HI-0`..`HI-4` | required. Profile-native names are shown via the mapping |
| `input_class` | `natural_language` \| `reference_document` | |
| `entry_stage` | stage id | `sys-req` for natural language. `sw-req` is allowed for reference documents (out-of-context) |
| `stages` | list of stage ids | ordered. Default: the full V from the entry stage |
| `inputs` | list of InputRef | needs files or reference documents, each hashed at intake |
| `links` | list of `{project_path, level}` | e.g. middleware SW-REQ → driver interface requirements (US2-AS2) |
| `roles` | map role → RoleBinding | `author`, `inspector`, `release` (FR-028) |
| `rework_limit` | int ≥0 | the profile's default applies if absent. Exhaustion → BLOCKED |
| `trace_capture` | `{raw_prompts: false, events: "standard"}` | raw prompts OFF by default (Principle VIII) |

**RoleBinding:**

| Field | Meaning |
|---|---|
| `harness` | `claude-code`, `codex`, `copilot`, `kiro`, `manual` or `custom` |
| `command` | the argv template, with `{prompt_file}` and `{skill}` placeholders |
| `model` | a declared model id, or null to use the harness default |
| `model_family` | free text used for the independence check, e.g. `claude`, `gpt` or `qwen` |
| `read_only` | bool |

## StandardProfile: `hi-gates/references/profiles/<id>.json`

| Field | Rule |
|---|---|
| `id`, `title`, `version` | |
| `level_map` | HI-n → native name (e.g. `HI-2: "ASIL B"`, `HI-2: "SIL 2"`). Not every HI level needs a mapping. An unmapped level → the gate refuses the configuration |
| `vocabulary` | stage id → native stage/workproduct name |
| `clause_refs` | stage id → list of clause identifiers. Identifiers only: `maxLength` 40, no sentences |
| `rigor` | HI-n → `{required_gates[], independence, coverage{statement,branch,mcdc}, verification_methods[], rework_limit}` |
| `disclaimer` | fixed non-certification statement (FR-008) |

`independence` is one of:

- `same-session-ok`
- `separate-session`
- `separate-model-family`

## Stage (static, `hi-gates/references/stages.json`)

Each stage has the following fields:

| Field | Meaning |
|---|---|
| `id` | the stage id |
| `side` | `left` or `right` |
| `level` | the V level |
| `counterpart` | the left stage this right stage verifies, or the reverse |
| `author_skill`, `inspector_skill` | the skills that play each role |
| `outputs` | the workproduct paths |
| `checklist` | the checklist id |
| `gates` | the gates run for this stage |

The stage ids and their counterparts:

- **`sys-req`** ↔ `sys-qual`
- **`sys-arch`** ↔ `sys-integ`
- **`sw-req`** ↔ `sw-qual`
- **`sw-arch`** ↔ `sw-integ`
- **`sw-design`** ↔ `unit-verif`

`sys-integ` and `sys-qual` are served by the `hi-sys-verif-*` skills.

## Workproduct (common envelope): `hi/<stage>/<name>.json`

| Field | Rule |
|---|---|
| `schema` | `forge-c-hi/<type>@1` |
| `stage`, `baseline_id`, `status` | status: `draft`, `inspected`, `blocked` |
| `provenance` | `{role, skill, skill_version, harness, model, model_family, input_hashes{}, created_utc, run_id}` (FR-012) |
| `items` | type-specific: RequirementItem, ArchElement, DesignUnit, TestCase or VerificationResult |
| `open_points` | list `{id, text, raised_by, blocks: bool}` |

## RequirementItem

| Field | Rule |
|---|---|
| `id` | unique per project. Pattern `^(STK|SYS|SWR|DRV)-[A-Z0-9_]+-[0-9]{3}$` |
| `level` | `stakeholder`, `system`, `software` or `driver_interface` |
| `text` | contains exactly one "shall" (deterministic IQ-05/IQ-11) |
| `rationale` | required for derived requirements |
| `sources` | list of `{kind: upstream, id}` or `{kind: document, doc_id, section, page}`. At least one (IQ-12) |
| `derived` | bool. True → `rationale` required and flagged to the set inspection |
| `verification_method` | `test`, `analysis`, `inspection` or `demonstration` (IQ-06) |
| `attributes` | `{safety_relevant: bool, integrity_level?, priority?}` |
| `status` | `proposed`, `accepted-by-inspection`, `open` or `rejected` |

## TraceLink: `hi/trace.json`

`{from, to, type, status}`, where:

- `type` is one of `derives`, `allocates`, `realises`, `implements`, `verifies` or `interfaces`;
- `status` is `valid` or `suspect`.

When an upstream item's content hash changes, every link that touches it becomes `suspect` (FR-022).

## Finding: `hi/<stage>/inspection/*.json`

| Field | Meaning |
|---|---|
| `id` | the finding id |
| `phase` | `item` or `set` |
| `checklist_item` | e.g. `IQ-05` or `SQ-06` |
| `target_id` | the item it is about |
| `severity` | `blocking`, `major` or `minor` |
| `description` | what is wrong |
| `requested_change` | what the author should change |
| `round` | the inspection round that raised it |
| `status` | see below |
| `raised_by` | the inspector's provenance |

The status lifecycle: `open` → `resolved`, `carried` or `rejected-with-rationale`. Findings that are still open after
item-phase rounds become `carried` into the set phase (FR-016).

## GateResult: `hi/<stage>/gates/<gate>.json`

| Field | Meaning |
|---|---|
| `gate` | the gate id |
| `verdict` | `PASS`, `FAIL` or `NOT_RUN` |
| `tool` | the tool's name and version |
| `exit_code` | the tool's exit code |
| `evidence` | a list of paths and hashes |
| `issues` | a list of `{code, target_id, message}` |
| `profile` | the profile in force |
| `integrity_level` | the level in force |

A required gate with NOT_RUN counts as a gap (FR-019, SC-009).

## AgentStatus (the compact reply contract)

`{role, stage, status: DONE|NEEDS_REWORK|BLOCKED|ERROR, outputs[], issues[{code,target_id}], open_points: int}`

At most 2 KB. Detail goes in the workproducts (FR-021, Principle IX).

## ReviewPackage: `hi/packages/<run_id>/`

| Content | Meaning |
|---|---|
| `manifest.json` | `{status: READY_FOR_OFFLINE_REVIEW|BLOCKED, gaps[], files[{path, sha256}], profile, integrity_level, provenance_summary, disclaimer, tool_versions}` |
| workproducts | copied from the stages |
| `trace-matrix.md` | the rendered trace matrix |
| `findings.md` | the rendered findings |
| `gates.md` | the rendered gate results |
| `review.tar.gz` | the sealed archive |

READY requires every required gate to PASS, no blocking open point or finding, no suspect link, and the independence
rule satisfied.

## EvaluationRun: `specs/023-…/evidence/eval/<run_id>.json`

| Field | Meaning |
|---|---|
| `arm` | `with_package` or `baseline` |
| `author_model` | the author model used |
| `inspector_model` | the inspector model used |
| `inputs_hash` | the hash of the inputs |
| `metrics` | see below |
| `artefacts` | paths |

The metrics are:

- trace coverage;
- rule violations per 100 requirements;
- `seeded_detected` / `seeded_total`;
- gate verdicts;
- wall time in seconds;
- turns;
- tokens (where the harness reports them).
