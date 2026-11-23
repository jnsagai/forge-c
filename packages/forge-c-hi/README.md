# forge-c-hi: high-integrity V-model skills for coding agents

**forge-c-hi** is an [APM](https://github.com/microsoft/apm) package that teaches coding agents (Claude Code, Codex,
GitHub Copilot, Cursor, Kiro and others) to develop high-integrity software the way safety standards expect: along the
V-model, from system requirements down to code and back up through verification, with an **independent inspector** for
every author, **deterministic gates** that no model can talk its way past, bidirectional **traceability**, and a sealed
**offline review package** at the end.

It is the portable, assisted-use form of [Forge-C](../../README.md), an open-source software factory for embedded
safety software. The package is not a certification tool: its packages are `READY_FOR_OFFLINE_REVIEW` or `BLOCKED`,
never "certified", "compliant" or "released".

## The problem

Coding agents write requirements, code and tests quickly, but in regulated domains speed is not the bottleneck: every
requirement must be precise and verifiable, trace to its source, be reviewed by someone independent, and be backed by
evidence that the checks actually ran. Left alone, a model invents plausible values ("within 100 ms"), marks its own
work as reviewed, and reports checks as passed that never ran. Teams then spend their review time finding that out.

forge-c-hi turns the standards' expectations into skills and gates the agent cannot skip:

- **Scope first:** before any requirement is written, the author states actors, use cases and what is out of scope;
  a gate checks without a model that every need (or every in-scope section of a reference manual) is placed and that
  every use case ends up realised by a requirement.
- **No invention:** missing facts become open points that block the stage until a human decides.
- **Independence:** the inspector is a different, read-only process, and from level HI-3 a different model family.
- **Evidence decides:** PASS, FAIL or NOT_RUN come from deterministic gates; NOT_RUN is a gap, never a pass.
- **Traceability:** every link is derived and checked both ways; an upstream change makes its links suspect.

## Who it is for

- Embedded and safety software engineers (automotive, industrial, rail, medical, avionics) who use coding agents.
- Quality, safety and process engineers who need reviewable evidence rather than chat logs.
- Teams evaluating agentic engineering under ISO 26262, IEC 61508, ASPICE or a similar standard.

## What it contains

| Kind | Name | Purpose |
|---|---|---|
| Skills (author + inspector per stage) | `hi-sys-req-*`, `hi-sys-arch-*`, `hi-sw-req-*`, `hi-sw-arch-*`, `hi-sw-design-*`, `hi-unit-verif-*`, `hi-sw-integ-verif-*`, `hi-sw-qual-*`, `hi-sys-verif-*` | the ten V-model stages |
| Skills (process) | `hi-intake`, `hi-conductor`, `hi-release`, `hi-gates` | set-up, unattended stage runs, sealing, the deterministic engine |
| Agents | `hi-author`, `hi-inspector`, `hi-release` | role definitions for harnesses with sub-agents |
| Instructions | `hi-core` | eight non-negotiable rules for every role |
| Hook | `hi-write-scope` | a PreToolUse guard that blocks writes outside the active role's scope |
| MCP server | `forge-c-hi` | the gate functions as MCP tools (`hi_gate`, `hi_trace_check`, `hi_seal_package`, ...) |
| References | profiles, checklists, schemas | standard profiles, 9 inspection checklists, JSON contracts |

### The V-model it follows

```
 sys-req  ─────────────────────────────────────────────  sys-qual
   sys-arch  ───────────────────────────────────────  sys-integ
     sw-req  ─────────────────────────────────────  sw-qual
       sw-arch  ───────────────────────────────  sw-integ
         sw-design (detailed design + C code)  ─  unit-verif
```

Two input classes: **natural-language needs** for middleware and applications (entry at `sys-req`), and **reference
documents** (datasheets, reference manuals, reference models) for HAL and low-level drivers (entry at `sw-req`, every
hardware fact cited by document, section and page, never quoted).

### Standards: a neutral core with profiles

| Profile | Levels | Notes |
|---|---|---|
| `generic` (default) | HI-0..HI-4 | requirements quality after ISO/IEC/IEEE 29148 |
| `iso26262` | QM, ASIL A..D | ISO 26262:2018 parts 4, 6 and 8 by clause id |
| `iec61508` | SIL 1..4 | IEC 61508:2010 parts 2 and 3 by clause id |
| `aspice40` | process HI-0..HI-4 | Automotive SPICE 4.0 SYS.2-5, SWE.1-6, SUP |

Switching profile or level changes only `.hi/project.json`; reports then use the standard's own terms. Add DO-178C,
EN 50716 or IEC 62304 from the template (see `hi-gates/references/profiles/README.md`).

## Prerequisites

- Python 3.10 or newer, git, and APM 0.37 or newer (`pip install apm-cli`).
- At least one coding-agent CLI, logged in with your own account: for the reference set-up, Claude Code (`claude`) as
  author and Codex CLI (`codex`) as inspector. **No API key is needed by the package.**
- Optional tools, each turning a gate from NOT_RUN into a real check: poppler (`pdfinfo`, `pdftotext`) for reference
  documents; `gcc`, `cppcheck` and `gcovr` for build, static analysis, unit tests and coverage.

## Install

```sh
mkdir my-project && cd my-project && git init
apm install jnsagai/forge-c/packages/forge-c-hi#forge-c-hi-v0.1.0 --target claude,codex
```

APM places the skills in `.claude/skills/` and `.agents/skills/`, the agents in `.claude/agents/` and `.codex/agents/`,
the guard hook in `.claude/settings.json` and `.codex/hooks.json`, and the MCP server in `.mcp.json`. Use other
`--target` values for Copilot, Cursor, Kiro, Gemini or OpenCode. Run `apm audit` to check the installed files.

## Run the demo (Safety Supervisor on an STM32N6)

The example is a supervisor for a small Cortex-M55 controller: task alive, deadline and program-flow monitoring, the
two hardware watchdogs, CRC self-tests, safe state, reset reasons and a diagnostic line. Its 15 stakeholder needs are
deliberately loose, as real ones are.

```sh
HI=".claude/skills/hi-gates/scripts/hi.py"
EX="apm_modules/jnsagai/forge-c/packages/forge-c-hi/examples/safety-supervisor"
cp -r "$EX/needs" .
python3 $HI init --from "$EX/hi-project.example.json"          # generic profile, HI-2, Claude Sonnet author, GPT-6.1 Terra inspector
python3 .claude/skills/hi-conductor/scripts/conduct.py --stage sys-req --until sw-req
python3 $HI status
python3 $HI seal                                                # READY_FOR_OFFLINE_REVIEW or BLOCKED with gaps
```

Or work **assisted**: ask your agent to use the `hi-intake` skill, then `hi-sys-req-author`, run `hi gate sys-req`,
and have the inspector skill run in a separate session or by a different model.

## Inputs, outputs and parameters

| | |
|---|---|
| **Inputs** | needs (`STK-<AREA>-<NNN>` ids) and constraints (`CON-...`) in Markdown; or a reference document you supply (PDF, never redistributed) with `hi doc-index` |
| **Configuration** | `.hi/project.json` via `hi init`: `--profile`, `--level HI-0..HI-4`, `--class natural_language\|reference_document`, `--entry`, `--input PATH:KIND[:DOC_ID]`, `--author/--inspector <preset>`, `--author-model`, `--inspector-model`, `--*-family` |
| **Workproducts** | `hi/<entry stage>/governance.json` (actors, use cases, scope), `hi/<stage>/requirements.json`, `architecture.json`, `design.json` + `src/`, `include/`, `test-spec.json` + `tests/` |
| **Evidence** | `hi/<stage>/gates/*.json`, `hi/<stage>/inspection/*.json`, `hi/trace.json`, `hi/trace-matrix.md`, `.hi/runs/<id>/events.jsonl` |
| **Package** | `hi/packages/<id>/`: `manifest.json` (hashes, gaps, profile, provenance), `gates.md`, `findings.md`, `trace-matrix.md`, `review.tar.gz` |
| **Exit codes** | 0 PASS/DONE, 1 FAIL/BLOCKED/NOT_RUN gap, 2 usage or configuration error; stdout is one JSON object of at most 2 KB |

## Supported models

Any harness and model, chosen per role in `.hi/project.json`; the presets are:

| Preset | Runs | Tested |
|---|---|---|
| `claude-code` | Claude through Claude Code (`claude -p`) with your account | yes, as author (reference: `--model sonnet`) |
| `codex` | GPT through Codex CLI (`codex exec`, read-only sandbox for the inspector) with your ChatGPT login | yes, as inspector (reference: `-m gpt-6.1-terra`) |
| `codex-oss-ollama` | a local model through Codex with Ollama (`--oss --local-provider ollama`) | see the evidence index |
| `manual` | you, in assisted mode | |

Any other CLI can be bound as `custom`: it reads the prompt on stdin, works within the write scope, and prints one JSON
reply.

## Benefits and measured impact

See [the impact report](../../specs/023-high-integrity-vmodel-skills/evidence/impact-report.md): rule violations with
and without the package on the same model and inputs, seeded-defect detection, traceability coverage, and cost. Every
number there links to stored run evidence, and missed targets are reported as missed.

## Limitations

- The gates check form, structure, traceability and evidence; engineering correctness is judged by the inspector model
  and, finally, by the human offline review.
- Model output varies between runs; results come from a small number of runs.
- MC/DC coverage is not measured (levels that require it report NOT_RUN).
- The levels and rigor values in the profiles are Forge-C defaults, not readings of the standards' tables.

**This package does not certify, qualify or approve anything.** It produces engineering input for an offline review by
qualified people. Standards are cited by clause identifier only; no standard or vendor text is included.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
