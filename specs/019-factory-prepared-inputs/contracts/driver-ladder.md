# Contracts: driver ladder

## 1. Campaign lineage key `after` (schema `forge-c/line-campaign/1`)

```yaml
after: {lineage: <lineage id in the same campaign>, phase: SWE.1..SWE.6, verdict: PASS}
```
- Optional. Valid with or without `depends_on`. Refused: unknown lineage, self reference, other verdict, a cycle over
  `depends_on` + `after` (`DEPENDENCY_CYCLE:<id>`), malformed (`FIELD_INVALID:after`).
- Meaning: the lineage places nothing until the named lineage's chain has the phase passed. It never sets
  `provided_from`.

## 2. `owner_supervised_development` source API

- `LADDER: tuple[str, ...]` - ordered lineage ids (see data-model).
- `derived_campaign() -> dict` - the campaign document; pure, deterministic (same source -> same bytes after canonical
  dump); validates with `line_campaign.validate` once `@SOURCE@` is substituted.
- `validate_order(order)` - unchanged contract; HAL orders need `provided_from` in `ORDER_SCOPE` with
  `(depends_on lineage, SWE.6)`; LL orders need `provided_from is None`.

## 3. Planner reasons (line feed / guardian audit)

| state | reason | meaning |
|---|---|---|
| WAITING | `AFTER:<id>:<phase>:PASS` | previous ladder step not done |
| WAITING | `DEPENDS_ON:<id>:<phase>:PASS` | (existing) HAL waits for its LL |
| WAITING | `INPUT_GAP:WORKORDER_SPEC:<example>` | the step's work-order spec is missing |

## 4. Deployer generator record

The development-inputs report gains `campaign_source: "DERIVED" | "TEMPLATE"` and
`template_sha256_ignored: <sha256 | null>` (a package template present but not used).
