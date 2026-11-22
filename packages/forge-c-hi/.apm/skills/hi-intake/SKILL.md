---
name: hi-intake
description: Start a forge-c-hi high-integrity project - choose the standard profile and integrity level, the input class (natural-language needs or a reference document), the entry stage and the author/inspector harnesses, give the inputs stable ids, and run `hi init` to record and hash them. Use when setting up a new V-model project, a safety or high-integrity requirements effort, or before running the conductor for the first time.
license: Apache-2.0
metadata:
  version: 0.1.0
  role: intake
  stage: sys-req
  write_scope: ".hi/project.json, .hi/inputs.lock.json (through hi init only)"
---

# Intake: set up a forge-c-hi project

Run this once per project, together with the user. The result is `.hi/project.json` and `.hi/inputs.lock.json`,
written only by `hi init` (see the `hi-gates` skill for how to call `hi`).

## 1. Ask, do not assume

| Decision | Options | Default |
|---|---|---|
| Standard profile | `generic`, `iso26262`, `iec61508`, `aspice40`, or a custom profile | `generic` |
| Integrity level | `HI-0` (no integrity claim) to `HI-4` (highest); the profile shows its own name, e.g. HI-2 = ASIL B under `iso26262` | none: the user must choose |
| Input class | `natural_language` (needs for middleware or application) or `reference_document` (datasheet, reference manual or reference model for HAL or low-level drivers) | `natural_language` |
| Entry stage | `sys-req` for needs; `sw-req` for a driver from a reference document | from the class |
| Author and inspector | harness presets `claude-code`, `codex`, `codex-oss-ollama` (local models), `manual`; a model and model family per role | Claude Code author, Codex inspector |

Explain the consequence of the level: higher levels require more gates (quality, scope, independence, build, tests,
coverage) and, from HI-3, an inspector from a different model family than the author. Never pick the level yourself:
it comes from the user's own hazard or risk analysis, which this package does not perform.

## 2. Prepare the inputs

- **Needs** go in a Markdown file. Each need gets a stable id `STK-<AREA>-<NNN>` at the start of its line, e.g.
  `- **STK-SUP-001** The supervisor must notice when a supervised task stops running.` The trace gate reads these ids.
- **Constraints** (given platform facts) get ids `CON-<AREA>-<NNN>`.
- **Reference documents** stay the user's own copy and are never redistributed. Register them with a document id, e.g.
  `--input docs/rm.pdf:reference_document:RM0486`.
- Check the inputs for personal data and secrets; `hi init` warns about e-mail addresses and keys, and the user must
  remove them.

If the user's needs have no ids, propose ids and let the user accept them before writing; the needs file belongs to
the user.

## 3. Run `hi init`

```sh
hi init --level HI-2 --profile generic --class natural_language \
  --input needs/stakeholder-needs.md:needs --input needs/constraints.md:constraints \
  --author claude-code --inspector codex
```

Local models: `--inspector codex-oss-ollama --inspector-model <model> --inspector-family <family>`.
To start from the package example: `hi init --from <package>/examples/safety-supervisor/hi-project.example.json`.

Exit 0 prints the profile's name for the level and any warnings; exit 2 explains what is wrong (an unknown profile, a
level the profile does not define, a missing input).

## 4. Next

- Unattended: run the conductor (`hi-conductor` skill) from the entry stage.
- Assisted: invoke the stage's author skill yourself, run `hi gate <stage>`, then have the inspector skill run in a
  separate session or by a different model.

Never edit `.hi/` by hand afterwards; rerun `hi init --force` to change the configuration.
