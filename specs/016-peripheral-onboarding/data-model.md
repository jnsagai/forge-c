# Data Model: Peripheral onboarding

All records are JSON files under `$FORGE_STATE_DIR/workorders/<WO>/onboarding/`, except the AFO order states, which
live in the conductor store. The schemas are in [contracts/](contracts/).

## OnboardingPackage (`onboarding/package.json`)

| Field | Type | Rules |
|---|---|---|
| `schema` | const `forge-c/onboarding-package/0.1` | |
| `work_order` | string | The work order this package belongs to |
| `inputs` | list of {path, role, sha256} | Every owner input, including the converted RM sections and their manifests (FR-003). Any hash change invalidates approval (FR-017). |
| `factory_revision` | git sha | The revision that derived the package |
| `driver_style` | `LL` \| `HAL_ON_LL` \| `HAL_STANDALONE` | Itself a Fact (see below); copied here for convenience |
| `facts` | list of Fact | One per fact name, sorted by name |
| `authored` | list of AuthoredItem | Empty when nothing needed authoring |
| `assumptions` | list of TestEnvironmentAssumption | |
| `gaps` | list of Gap | Derived from facts and items. Never edited by hand. |
| `profile` | object | Derived profile, valid against the feature 009 peripheral-profile schema plus `derived_from` |
| `texts` | object | Generated prompt keys (`prompt`, and `prompt_st_hal` for HAL_STANDALONE); each value traces to a template id or an authored item |
| `status` | `READY_FOR_OWNER` \| `BLOCKED` | BLOCKED when a required input is missing (for example no vendor file); otherwise READY_FOR_OWNER, even with gaps |
| `sha256` | hex | Canonical hash: sorted keys, no whitespace, over everything above except `sha256` and timestamps |
| `created_at` | ISO 8601 UTC | Excluded from the hash |

## Fact

| Field | Type | Rules |
|---|---|---|
| `name` | string | From a closed vocabulary. Examples: `instance`, `base_address`, `mm_page`, `register_prefix`, `register_index`, `driver_style`, `function_prefix`, `headers`, `time_base`, `timeout_constants`, `waits`, `undelivered_externals`, `instance_comparisons`, `host_instance`, `file_map`, `framework_modules`. |
| `value` | any JSON | `null` unless status is DERIVED |
| `status` | `DERIVED` \| `NOT_DERIVED` \| `CONFLICT` | FR-005 |
| `method` | string | The derivation rule id (research R3), e.g. `cmsis_base_chain`, `mm_table_row`, `link_undefined` |
| `sources` | list of {kind: `file`\|`doc`\|`log`, ref, line?, page?, value?} | At least one for DERIVED. At least two, with their values, for CONFLICT. |
| `owner_question` | string? | Required when NOT_DERIVED or CONFLICT |

**Validation**
- DERIVED requires at least one source and a non-null value.
- A CONFLICT's sources carry different values.
- Facts are deterministic: the same inputs give the same list, byte for byte.

## AuthoredItem

| Field | Type | Rules |
|---|---|---|
| `id` | string | `model` or `text:<slot>`, for example `text:requirement_example` |
| `role` | string | `onboard-model-author` or `onboard-text-author` |
| `path` | string | The file under `onboarding/` (model `.py`/`.repl`, or `texts.json` entry) |
| `attempts` | int | At most 3 (FR-009) |
| `gate` | {verdict: PASS\|FAIL, findings: [string], tool, version, invocation_id} | Model gate (R5) or text checks (FR-010) |
| `inspection` | {verdict: PASS\|FAIL, findings: [string], inspector_role} | Independent inspector (IV) |
| `limits` | list of string | Behaviour not modelled, or scope of the text |
| `status` | `ACCEPTED` \| `GAP` | ACCEPTED only when the gate and the inspection both pass |
| `reused` | bool | True when an existing model was re-gated rather than authored |

## TestEnvironmentAssumption

| Field | Type | Rules |
|---|---|---|
| `id` | string | e.g. `ASM-CLOCK-USART1` |
| `symbol` | string | The undelivered function or parameter, e.g. `HAL_RCCEx_GetPeriphCLKFreq` |
| `reason` | string | Why it cannot be derived |
| `affects` | list of string | Registers or results that depend on it, e.g. `USART_BRR` |
| `proposed_value` | any? | Only when an input states one, with its source |
| `confirmed_value` | any? | Set only from a verified owner approval |

## Gap

| Field | Type | Rules |
|---|---|---|
| `id` | string | `GAP-OB-nnn` |
| `kind` | `NOT_DERIVED` \| `CONFLICT` \| `AUTHORED_ITEM_FAILED` \| `MISSING_INPUT` \| `ASSUMPTION_UNCONFIRMED` | |
| `ref` | string | Fact name, item id or input path |
| `effect` | string | The later phase or evidence it blocks or limits, e.g. `SWE.5/SWE.6 target evidence BLOCKED` |
| `blocks_approval` | bool | True for CONFLICT, ASSUMPTION_UNCONFIRMED and MISSING_INPUT. Other gaps can be approved as stated. |

## OnboardingApproval (`onboarding/approval.json` + `.sig`)

| Field | Type | Rules |
|---|---|---|
| `schema` | const `forge-c/onboarding-approval/0.1` | |
| `approval_id` | string | `OA-YYYY-MM-DD-nn` |
| `work_order` | string | Must match the package |
| `package_sha256` | hex | Must equal the current package hash (FR-017) |
| `decision` | `APPROVED` \| `REJECTED` | |
| `reason` | string | Required for REJECTED |
| `conflict_resolutions` | list of {fact, chosen_value, reason} | One per CONFLICT fact; required for APPROVED |
| `assumption_confirmations` | list of {id, value} | One per assumption; required for APPROVED |
| `accepted_gaps` | list of gap ids | Every non-blocking gap must be listed (explicit acceptance) |
| `decided_by` / `decided_on` | string / date | |

**Verification.** `ssh-keygen -Y verify -n forge-onboarding-approval` with the owner's allowed-signers entry (the
same file as the AFO authorization). After verification, the factory writes the confirmed values into the derived
profile. Changing the profile changes nothing in the hash subject: the approval binds the pre-approval package hash,
and the post-approval profile records `approval_id`.

## Work-order additions (feature 008 brownfield contract)

- `target.instance` (string): the owner names the instance.
- `delivery.files`, `delivery.dependencies` and `delivery.dependencies[].configure`: optional when
  `onboarding: true`. When present, they are cross-checked against the derived values (CONFLICT on difference).
- `inputs[]`: may carry `{path: <pdf>, role: reference_manual, chapter, memory_map_pages}`.
- `onboarding` (bool): opt-in to the package-driven path. Absent or false keeps today's behaviour (FR-019).

## Manifest addition (`.forge-run/manifest.json`)

`onboarding: {package: "onboarding/package.json", sha256, approval_id}`. Present only on approved package-driven
work orders. Every phase gate copies `sha256` into its evidence record (FR-018).

## AFO integration (amended 2026-10-27: no new queue states)

The owner approves a package **before** its work order is submitted; the feature 005 queue state machine is
unchanged.

- Packages are keyed by the onboarding work order's example name: `$FORGE_STATE_DIR/onboarding/<key>/onboarding/`.
  Every request and attempt of that work order uses the same approved package.
- AFO intake (`queue.submit`) refuses an onboarding work order without a verified approval:
  `INTAKE_ONBOARDING_NOT_APPROVED:<code>:<key>`.
- `workorder.prepare` re-derives the package at every launch. A changed input changes the package hash, which voids
  the approval (moved to `onboarding/void/` with the reason), and the launch is refused `ONBOARDING_NOT_APPROVED`.
- The factory revision is recorded in the package but is not part of the approval subject: a factory update that
  derives the same facts keeps the approval; one that derives different facts voids it.
