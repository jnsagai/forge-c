---
name: hi-conductor
description: Run forge-c-hi V-model stages unattended - author, deterministic gates, two-phase independent inspection (each item, then the set), bounded rework, final gates - with a configurable harness and model per role (Claude Code, Codex, local Ollama models). Use when the user asks to run, continue or re-run a stage such as system or software requirements end to end, or to see why a stage is BLOCKED.
license: Apache-2.0
metadata:
  version: 0.1.0
  role: conductor
  stage: all
  write_scope: ".hi/runs/**, .hi/state.json, .hi/active-role.json, hi/<stage>/inspection/**, hi/<stage>/gates/**"
---

# Conductor: run V-model stages

The conductor is a deterministic script. It calls the configured author and inspector as separate processes, runs
the gates and records everything. It makes no model call itself and never upgrades a result.

## Before you start

- The project is set up (`hi-intake` skill): `.hi/project.json` exists with roles that have commands.
- The inspector binding must be `read_only: true`. A `manual` binding means assisted mode: run the skills yourself.
- The harness CLIs are installed and logged in (for example `claude` and `codex`). The package needs no API key.

## Run

```sh
sh .claude/skills/hi-gates/scripts/locate.sh ../../hi-conductor/scripts/conduct.py --stage sys-req --until sw-req
# or, with the path of this skill:
python3 <this-skill>/scripts/conduct.py --stage sys-req --until sw-req [--timeout 3600] [--dry-run]
```

`--dry-run` records what would run without calling any harness. A second run on an existing workproduct **updates**
it: the author is called only if inputs changed or upstream links are suspect, and only new, changed, suspect or
still-flagged items are judged again. Earlier judgements are kept only while the stage's checklists and inspector
skill are unchanged. `--fresh` re-authors from scratch.

## What happens per stage

0. **Governance** (entry stage, when the profile requires the `governance` gate, i.e. from HI-1): the author first
   writes `hi/<stage>/governance.json` (actors, use cases, scope, assumptions, open points). Its coverage is checked
   without a model: every stakeholder need, and for a reference document every in-scope section, must be in a use case,
   out of scope or an open point. Gaps go back as `fix-governance` rounds within the rework limit; what remains blocks
   the stage before any requirement is written. On a re-run the package is updated only when inputs changed.
1. **Author** writes the workproduct, with `.hi/active-role.json` naming its write scope (the guard hook enforces
   it) and a file snapshot before and after (any out-of-scope write blocks the stage).
2. **Gates** (`validate`, `quality`, `trace`, `governance`): issues go back to the author as `fix-gates` rounds, at most
   10 issues per call, for `rework_limit` rounds and beyond it (up to `rework_max`) only while their number falls.
3. **Item inspection** of every item by the read-only inspector.
4. **Rework** of each item with a blocking or major finding, **one item at a time**. Changes to other existing items
   are discarded; new items from a split are kept and judged.
5. **Re-judge** only the reworked items; an item the author left exactly as it was is not judged again and keeps its
   findings. Steps 4 and 5 repeat for the profile's `rework_limit` rounds, and beyond it only while the open findings
   keep falling, up to `rework_max` (default 10). Two rounds with the same open findings (same item, criterion and
   cited ids, and nearly the same text) stop the loop at once (`rework-stuck`). What is still open is **carried** into the set phase.
6. **Set inspection** with the carried findings, then set rework under the same rule. Set rework changes every statement of the
   limit, value or rule concerned, in all items, and replaces outdated text.
   A stage that is already `ACCEPTED` is kept without any model call while its files, the inputs, the earlier stages'
   outputs, the project settings, the checklists and the inspector skill are unchanged and every gate passes again.
7. **Final gates** for the profile and level. The stage ends `ACCEPTED`, `ACCEPTED_WITH_GAPS` (a required gate is
   NOT_RUN, or a major finding is still open; both still block the review package) or `BLOCKED` (a gate failed, a
   blocking finding or blocking open point remains, a role wrote outside its scope, or a harness failed).

**Back up the V.** A stage that finds an earlier workproduct wrong or impossible to meet raises a blocking open point
with `returned_to: <earlier stage>`. When the stage then ends BLOCKED, the run goes back to that stage (if it is in the
run, at most `rework_limit` times): its author settles the points, its inspector checks that, and the stages after it
follow. A point is offered once per wording; raised again unchanged, it waits for a person. `returned_to: null` always
waits for a person.

Accepting a stage records the trace baseline, so a later change to an upstream item makes its links **suspect**.

## Harnesses and models per role

`references/harness-presets.json` holds the argv templates:

| Preset | Use |
|---|---|
| `claude-code` | `claude -p` with Read/Grep/Glob/Write/Edit for the author, read-only tools for the inspector; uses the user's Claude Code login |
| `codex` | `codex exec -s workspace-write` (author) or `-s read-only` (inspector); uses the user's Codex login |
| `codex-oss-ollama` | Codex with a local Ollama model (`--oss --local-provider ollama`); state the model family |
| `manual` | assisted mode, no process is started |

The prompt goes on stdin, unless an argument contains `{prompt_file}`. A `{skill}` placeholder is replaced by the
stage skill name. Any other CLI can be used as a `custom` role binding with the same contract: read the prompt, act
within the scope, print one JSON reply.

## Results

- stdout: one compact JSON summary (`status` `DONE`, `DONE_WITH_GAPS`, `BLOCKED`), exit 0 only for `DONE`.
- `.hi/runs/<run_id>/events.jsonl`: every step with role, harness, model family, duration, files changed and gate
  verdicts. Raw prompts and replies are recorded only when `trace_capture.raw_prompts` is true.
- `hi/<stage>/inspection/`: the findings of every round and `findings.json` with each finding's final status.
- `hi/<stage>/gates/`: gate results. `hi status` shows where the project stands.

When a stage is BLOCKED, read `reason` in the summary and the last events, fix the cause (often an open point that a
human must decide), and run the stage again. Then seal a review package with `hi seal`.
