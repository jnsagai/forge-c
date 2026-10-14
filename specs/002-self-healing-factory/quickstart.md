# Quickstart for Claude Code — Spec Kit feature 002

The Spec Kit feature specification, plan, tasks and contracts are already authored. **Do not regenerate/overwrite them.** Everything beneath `specs/002-self-healing-factory/` defines the desired implementation, not accomplished work.

## 1. Establish a clean project baseline

```bash
cd /path/to/forge-c-darkfactory-v0.4
python3 tests/spec/validate_design.py
python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py' -v
```

Install or update GitHub Spec Kit separately if needed. After committing/backing up the existing repo, select Claude integration using the syntax supported by the installed Specify CLI:

```bash
specify init --here --force --integration claude --non-interactive
```

`--force` must only be used after confirming exactly which files initialization will overwrite. Inspect `specify --help` and `specify check` on the local installation. Source: [GitHub Spec Kit](https://github.com/github/spec-kit/blob/main/docs/installation.md).

## 2. Start Claude Code

Open the project root in Claude Code and paste `CLAUDE_START.md`. Claude reads constitution, specs, contracts and draw.io; implements T001 through T051 milestone by milestone; and writes only concise task status in dialogue. Detailed technical evidence remains in versioned artifacts.

Suggested first implementation request:

> Implement M0/T001–T004 in `specs/002-self-healing-factory/tasks.md`. Do not implement speculative Fabro APIs. Verify `SKILL.md` discovery and MCP agent config against installed Fabro; create ADRs and baseline tests. Output only task status, measured tool versions, evidence paths and blockers.

## 3. Acceptance checks (design is not runtime)

Check [spec.md](spec.md), [plan.md](plan.md), [tasks.md](tasks.md), [acceptance-tests.md](acceptance-tests.md). Both static and executable acceptance tests are required; schema validation proves only consistency of the specification. Do not mark any runtime acceptance criterion PASS until actual adapter, supervisor, repair, knowledge, dashboard, Fabro and packager execution has produced evidence.

For the first proof-of-concept, use the **generic RCC host driver**, not the STM32N6 hardware safety target. Once the pilot passes, move to target compilation, STM32N6 model and hardware verification with approved manuals and HSI.
