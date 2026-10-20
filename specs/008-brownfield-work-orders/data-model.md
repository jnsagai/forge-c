# Data Model: Brownfield Work Orders

## Delivery spec (`examples/<name>/workorder.json` → `delivery`)

| Field | Type | Rule |
|---|---|---|
| `code_mode` | `FROZEN` \| `FIX_ALLOWED` | required; defaults to FROZEN only when omitted by an older template (it is never inferred) |
| `origin` | string (URL or supplier) | required, non-empty (FR-005) |
| `licence` | SPDX id or text | required, non-empty (FR-005) |
| `licence_allows_modification` | bool | required; FIX_ALLOWED with `false` is refused at intake |
| `source` | path (directory or `.tar.gz`/`.zip`) | absolute, or relative to the repo or `$FORGE_DATA_ROOT`; read-only |
| `files` | list of `{from, to}` | `from` is relative to `source`; `to` lies under `software/ll/`, `software/hal/` or `software/src/` |
| `scope.functions` | list of names | each must resolve to a definition in `files` (FR-003) |
| `scope.note` | string | free text shown to the owner |
| `dependencies` | list of `{from, to, origin, licence}` | vendor headers copied to `inputs/vendor/include/` (fingerprinted, read-only) |
| `build.defines` | list of `NAME` or `NAME=VALUE` | used verbatim by the build, test and simulator tools; never by agents |
| `build.style` | `forge` \| `cmsis` | selects the register-access scanner and test harness |
| `provenance` | path | optional provenance record (e.g. `$FORGE_DATA_ROOT/inputs/st/.../provenance.json`) |

## Manifest additions (`.forge-run/manifest.json`)

- `delivery`: the validated spec, minus the local source path, plus `intake_ref`.
- `code_mode`: `FROZEN` \| `FIX_ALLOWED`.
- `delivered`: list of `{path, sha256, bytes, role: "delivered_code" | "delivered_dependency", origin, licence}`.
- `scope_resolution`: `{functions: [{name, file, line, kind: function|macro|static_inline}], excluded_count, excluded_ref}`.

The excluded list is in `.forge-run/delivery/scope.json`, not in the manifest.

## Delivery records (`.forge-run/delivery/`, written by deterministic nodes only)

| File | Written by | Content |
|---|---|---|
| `intake.json` | `prepare` | Status `ACCEPTED` \| `BLOCKED`; one issue code per failure; build check result (command, exit code, log hash); file fingerprints |
| `scope.json` | `prepare` | Resolved and excluded functions |
| `injection.json` | `delivery_inject` | SWE.1 baseline id and hash at injection; injected files and fingerprints; UTC time |
| `verification-<step>.json` | `verify_delivery` | Per file: expected and actual fingerprint, status `UNCHANGED` \| `CHANGED_BY_FIX` \| `MISMATCH` |
| `change_report.json` | `verify_delivery` (FIX_ALLOWED) | Per changed file: defect ids, original and corrected SHA-256, unified diff, re-verification ref |
| `conformance.json` | conformance check | Conformance findings (below) |

**State transitions** (delivery):

```
INTAKE ─ok→ STORED ─SWE.1 PASS→ INJECTED ─verify→ VERIFIED(UNCHANGED | CHANGED_BY_FIX) ─package→ PACKAGED
   └─fail→ BLOCKED                       └─mismatch→ BLOCKED
```

## Code trace map (`workproducts/SWE.3/code_trace_map.json`)

Rows: `{function, file, sha256, unit, uspecs[]}`. There is one row per scope function, or an explicit
`{function, out_of_scope: true, reason}`.

**Rules:**
- the function exists in the file;
- the sha256 equals the delivered fingerprint (FROZEN) or the post-fix fingerprint (FIX_ALLOWED);
- every unit spec in `unit_specifications.md` appears in at least one row;
- every scope function appears exactly once.

## Conformance finding

| Field | Rule |
|---|---|
| `id` | `CF-NNN`, stable within the work order |
| `kind` | `NO_REQUIREMENT` \| `NO_CODE` \| `CONTRADICTION` |
| `function` | delivered function name (empty for `NO_CODE` when the function does not exist) |
| `requirement` | SWR id (empty for `NO_REQUIREMENT`) |
| `reference` | RM section and page for `CONTRADICTION` |
| `evidence` | expected vs observed register effect, or the allocation row |
| `status` | `OPEN` \| `DISPOSITIONED` (owner) |

An `OPEN` finding is a package gap (FR-009).

## Defects against delivered code

The existing defect record gets `target_kind: DELIVERED_CODE` when the CODE defect is against a delivered file.

- **FROZEN:** status `ESCALATED`, no target author.
- **FIX_ALLOWED:** the normal `IN_FIX → FIXED → VERIFIED` cycle, with the change report entry linked.

## Safety drafts

`safety/drafts/software_safety_analysis.md` and `safety/drafts/tool_assurance_assessment.md`: the draft marker,
the scope, the delivered fingerprints, no compliance claims. They never count as signed documents.
