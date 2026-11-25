# Contract: `hi` CLI and `forge-c-hi` MCP tools

The same functions are available both ways. The CLI is `python3 <skills-root>/hi-gates/scripts/hi.py <cmd>`. The MCP
server is `hi_mcp.py`, a stdlib JSON-RPC 2.0 stdio server implementing `initialize`, `tools/list` and `tools/call`.

All commands:

- print one compact JSON object to stdout (at most 2 KB) and write full results to disk;
- exit `0` on PASS or DONE, `1` on FAIL or BLOCKED, `2` on usage or configuration error;
- report NOT_RUN in the JSON, never as exit `0` with a pass.

| CLI command | MCP tool | Purpose | Writes |
|---|---|---|---|
| `hi init --profile P --level HI-n --class C` | `hi_init` | create `.hi/project.json` and hash the inputs | `.hi/project.json`, `.hi/inputs.lock.json` |
| `hi doc-index <pdf> --doc-id ID` | `hi_doc_index` | section/page outline of a user-supplied reference document; NOT_RUN without poppler | `.hi/docs/<ID>.index.json` (never redistributed) |
| `hi validate <workproduct>` | `hi_validate` | schema and envelope check | gate result |
| `hi quality <stage>` | `hi_quality_rules` | deterministic IQ/SQ subset (R4) | gate result |
| `hi governance <stage> [--before-requirements]` | `hi_governance_check` | governance package coverage of the entry stage (feature 020 port) | gate result (not with `--before-requirements`) |
| `hi trace [--stage S]` | `hi_trace_check` | bidirectional completeness, dangling links, suspect links, document-source resolution | gate result, `hi/trace-matrix.md` |
| `hi scope --role R --stage S` | `hi_scope_check` | changed files ⊆ role write scope (diff or snapshot backstop) | gate result |
| `hi gate <stage>` | `hi_gate` | run all of the profile's required gates for the stage at the configured level | `hi/<stage>/gates/*.json` |
| `hi status` | `hi_status` | V-model position, verdicts, open findings | none |
| `hi answer <stage> <OP-id> --by <who> --text <answer>` | - | A person answers a process question of one stage; held to the wording of the point, kept in `.hi/answers.json` and in the sealed package, never evidence. Product decisions go in the inputs | `.hi/answers.json` |
| `hi seal` | `hi_seal_package` | READY or BLOCKED review package | `hi/packages/<run_id>/…` |
| `hi role set <role> <stage>` | none (conductor/skills) | write `.hi/active-role.json` for the guard hook | `.hi/active-role.json` |

## Conductor

`python3 <skills-root>/hi-conductor/scripts/conduct.py --stage S [--until S2] [--dry-run]`

For each stage it runs these steps, using each role's command template from `.hi/project.json`:

1. author
2. gate
3. item inspection
4. rework of the flagged items, each alone
5. re-judge of the reworked items
6. set inspection
7. gate
8. one of: next stage, BLOCKED, or the rework limit reached

It writes `.hi/runs/<run_id>/events.jsonl` (see the data model). Raw prompts are captured only when
`trace_capture.raw_prompts` is true.

## Guard hook

The `PreToolUse` hook runs `sh -c '<locator> guard.py'`. The guard reads the tool input JSON on stdin and
`.hi/active-role.json`, then:

- exits `0` to allow;
- exits `2` with a reason on stderr to deny a write outside the role's scope.

With no active role, no project files are guarded and the guard allows. The gate backstop then applies.
