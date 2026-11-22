---
name: hi-gates
description: Deterministic forge-c-hi gates for high-integrity V-model work. Use when you need to validate a workproduct, check traceability or requirement quality, check write scope, run a stage's required gates, show V-model status, or seal a READY_FOR_OFFLINE_REVIEW / BLOCKED review package. No AI model is involved; verdicts are PASS, FAIL or NOT_RUN.
license: Apache-2.0
metadata:
  version: 0.1.0
  role: gate
  stage: all
  write_scope: "hi/<stage>/gates/**, hi/trace-matrix.md, hi/packages/**, .hi/**"
---

# hi-gates: deterministic engine

The gates use only the Python ≥3.10 standard library and never call a model. Every result is a JSON record
(`references/schemas/gate-result.schema.json`) under `hi/<stage>/gates/`.

## How to run

The scripts are in this skill's `scripts/` folder. Call them relative to this `SKILL.md`, wherever APM installed it
(`.claude/skills/`, `.agents/skills/`, `.github/skills/` and so on):

```sh
python3 <this-skill>/scripts/hi.py <command> [options]
sh <this-skill>/scripts/locate.sh hi.py <command>   # same, from the project root, for any install location
```

The same functions are also available as MCP tools from the `forge-c-hi` MCP server, when your harness loads it.

| Command | MCP tool | What it does |
|---|---|---|
| `hi init --profile P --level HI-n --class C` | `hi_init` | create `.hi/project.json`, hash inputs |
| `hi doc-index <pdf> --doc-id ID` | `hi_doc_index` | section/page outline of your own reference document (needs poppler, else NOT_RUN) |
| `hi validate <file>` | `hi_validate` | schema and envelope check |
| `hi quality <stage>` | `hi_quality_rules` | deterministic requirement-quality rules |
| `hi trace [--stage S]` | `hi_trace_check` | bidirectional traceability, dangling or suspect links, document sources |
| `hi scope --role R --stage S` | `hi_scope_check` | files changed ⊆ role write scope |
| `hi gate <stage>` | `hi_gate` | every gate the profile requires for this stage and level |
| `hi status` | `hi_status` | V-model position, verdicts, open findings |
| `hi seal` | `hi_seal_package` | sealed review package, READY_FOR_OFFLINE_REVIEW or BLOCKED |

**Exit codes:**

- `0`: PASS or DONE.
- `1`: FAIL or BLOCKED.
- `2`: usage or configuration error.

NOT_RUN is reported in the JSON and counts as a gap, never as a pass. stdout is one compact JSON object of at most 2 KB.

## References

- `references/stages.json`: the neutral V-model stages, counterparts, write scopes and default gates.
- `references/profiles/*.json`: the standard profiles `generic`, `iso26262`, `iec61508` and `aspice40`, plus
  `_template.json` for adding one. They map HI-0..HI-4 to native levels and set the rigor: required gates,
  independence, coverage, rework limit. Clause identifiers only.
- `references/checklists/*.json`: the neutral inspection checklists (IQ/SQ for requirements, plus one per later stage).
- `references/schemas/*.json`: the workproduct, finding, gate, status and manifest contracts.

## Write-scope guard

`scripts/guard.py` is installed as a PreToolUse hook by the package. While `.hi/active-role.json` names a role, writes
outside that role's scope are denied, and `.hi/` is never writable by roles. `hi scope` re-checks the same rule after
the fact for harnesses without hooks.
