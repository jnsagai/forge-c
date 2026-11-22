# Research: Feature 023 — High-Integrity V-Model Skills (APM package)

**Date:** 2026-11-22. All evidence was produced on loop10 in the session scratchpad. Omniverse2 was not used, per the owner's instruction.

## R1. APM package format and multi-harness install (verified by spike)

- **Decision:** a single APM package at `packages/forge-c-hi/`.
  - The manifest is `apm.yml`. The primitives live under `.apm/skills/<name>/SKILL.md`, `.apm/agents/<name>.agent.md`,
    `.apm/instructions/<name>.instructions.md` and `.apm/hooks/<name>.json`.
  - MCP servers are declared under `dependencies.mcp` as self-defined stdio servers (`registry: false`).
  - Users install it from a git reference that includes the subdirectory:
    `apm install jnsagai/forge-c/packages/forge-c-hi#<tag>`.
- **Evidence (spike, apm-cli 0.37.0, installed with `uv pip install apm-cli` into a user venv, no sudo):**
  - `apm install <local pkg>` into a consumer created with `--target claude,codex` placed:
    - skills in `.claude/skills/` and `.agents/skills/`;
    - agents in `.claude/agents/*.md` and `.codex/agents/*.toml`;
    - instructions in `.claude/rules/`;
    - hooks in `.claude/settings.json` and `.codex/hooks.json`, with the same `PreToolUse` schema;
    - the MCP server in `.mcp.json` (Claude Code) and the Codex configuration.
  - Skill-bundled `scripts/` files were copied.
  - `apm audit` reported no issues.
- **Finding:** hook commands and MCP commands run from the consumer project root, and APM does not copy a hook's
  scripts. Any script a hook or MCP server calls must therefore ship inside a skill folder. It is then reached through a
  small POSIX-sh locator that checks `.claude/skills/hi-gates`, `.agents/skills/hi-gates`, and the other target roots
  APM uses.
- **Alternatives considered:**
  - A separate repository. The owner asked for a branch in this repo, and APM supports subdirectory installs.
  - A Claude plugin only. That fails the multi-harness requirement.
  - Raw skills without `apm.yml`. The hackathon mandates the APM package structure.
- **Open (owner, external):** the publication route into Capgemini's Agentic AI Artifacts repository is internal. The
  fallback, which is always produced, is a public GitHub tag install link. Only the publish step depends on the answer.

## R2. Harnesses and models for the reference evidence (owner decision 2026-11-22)

- **Decision:** the conductor reads each role's harness command from the project configuration. Reference config:
  - **author:** Claude Code headless, `claude -p` on the owner's Claude account;
  - **inspector:** Codex CLI, `codex exec` on the owner's ChatGPT login (`codex login status` → "Logged in using
    ChatGPT"), run with `--sandbox read-only`.

  Inspectors cannot change files at all. Their verdict comes back on stdout as JSON and the conductor writes it.
- **Local models, same harness:** `codex exec --oss --local-provider ollama -m <model>`, as shown by
  `codex exec --help`, or any OpenAI-compatible local endpoint. No skill changes.
- **Rationale:** the author and inspector come from different model families and run in different harnesses and
  processes. That gives independence by construction (Principle IV, FR-028). Both harnesses are APM targets, so one demo
  also proves portability. No paid API is used.
- **Alternatives:**
  - API SDK bridges: rejected, because account mode is the owner's default and no paid API is allowed.
  - One harness with two sessions: weaker independence, kept only as a configurable option.

## R3. Gate and packager implementation: stdlib Python, JSON workproducts

- **Decision:** Python 3.10+ standard library only for the gates, the conductor, the MCP server and the packager. Machine
  workproducts are JSON. Markdown views are rendered deterministically from them.
- **Rationale:** there is nothing to install for users except Python. The stdlib has no YAML parser, so JSON. Cloud and
  local models both emit JSON reliably. Hashing is reproducible.
- **Reuse:**
  - `tools/trace_gate.py`, whose link-type graph and checks are adapted to neutral V-model levels;
  - `tools/gate_common.py`, for the emit/verdict pattern;
  - `factory/release-manager/scripts/build_review_package.py`, for the manifest, hashing and READY/BLOCKED logic;
  - `factory/checklists/v0.4/SWE.*.yaml`, as checklist content to neutralise.
- **Alternatives:**
  - PyYAML: an extra dependency for users.
  - Importing `forge_factory`: couples the package to the factory and Fabro, violating FR-010 and the spec's Fabro-free
    assumption.

## R4. Requirement quality and two-phase inspection content

- **Decision:** port the owner's SWE.1 quality guideline as a standard-neutral checklist:
  - **IQ-01..12**, judged per requirement: necessary, correct, unambiguous, complete, atomic, verifiable, feasible,
    design-independent, consistent, right abstraction, conforming, identifiable;
  - **SQ-01..10**, judged on the whole set: coverage, behavioural completeness, non-functional and interface
    completeness, structure, consistency, traceability, interdependency, environment, agreement, verification readiness.

  The guideline is `docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md`, fetched from the public GitHub ref
  `origin/publish/omniverse2-campaign-20261111`, not from Omniverse2. The same criteria apply at system level with
  level-specific wording.

  The process follows feature 018 (on the same GitHub ref): judge every item, rework only the flagged ones, each alone,
  re-judge only the reworked ones, carry unresolved findings into the set phase.
- **Rationale:** the criteria rest on ISO/IEC/IEEE 29148 quality attributes, which are standard-neutral, and feature 018
  already showed native evidence (L44F WWDG SWE.1, 20/20 judged).
- **Deterministic subset (gate, no model):** ID uniqueness and format, the mandatory "shall", a banned-ambiguity
  word list (IQ-03), a heuristic for multiple obligations (IQ-05: several "shall", or "and"/"or" joining verbs), a
  verification method present (IQ-06), source references present and resolvable (IQ-12, SQ-06), units present on
  numeric values. Semantic items stay with the inspector.

## R5. Standard profiles

- **Decision:** profiles are JSON data in `hi-gates/references/profiles/`: `generic`, `iso26262`, `iec61508` and
  `aspice40`, plus `_template`. Each profile declares:
  - its integrity scale, mapped onto the neutral levels HI-0..HI-4;
  - stage names and workproduct names in the standard's vocabulary;
  - clause identifiers per stage (identifiers only);
  - rigor per level: required gates, inspector independence (`same-model-ok`, `separate-session` or
    `separate-model-family`), structural-coverage targets, required verification methods, and a rework limit.
- **Rationale:** FR-005 to FR-009 and constitution v0.5.0 Principle II. The level mappings follow each standard's
  published scale names (ASIL QM/A–D, SIL 1–4, ASPICE process-only). The rigor values are engineering defaults that
  profile owners may tune. They are marked as Forge-C defaults, not quotes from a standard.
- **Alternatives:** per-standard skill variants. Rejected because they duplicate skills and fail SC-007.

## R6. Driver input class: section and page evidence without shipping the document

- **Decision:** at intake, the user's own PDF is hashed and outlined into `doc-index.json` (section numbers, titles,
  page ranges) using `pdftotext`/`pdfinfo` (poppler, open source) when present. Each driver requirement's `source` holds
  `{doc_id, section, page}`. The gate resolves it against the index.
  - No PDF tools: the source-resolution check is **NOT_RUN** and becomes a gap. This never counts as a pass.
  - The index stays in the user's project and is excluded from the review package's redistributable part. Only the
    identifiers travel.
- **Demo:** an IWDG driver that cites a public STM32 reference manual by identifier. The user downloads it from the
  vendor. The package ships no vendor text.

## R7. Write-scope guardrail and independence in assisted mode

- **Decision:**
  - **Hook:** a `PreToolUse` hook on `Write|Edit|MultiEdit|apply_patch` calls `hi-gates/scripts/guard.py`. The guard
    reads `.hi/active-role.json`, written by the conductor or the stage skill, and denies writes outside the role's
    output paths.
  - **Gate backstop:** the gate runs `git diff --name-only` (or a hash snapshot when there is no git) against the
    role's write scope. Any out-of-scope change fails the gate (FR-020).
  - **Inspector:** read-only sandbox (R2).
  - **Same-model check:** if the provenance records the same model family where the profile requires separation, an
    "independence not demonstrated" gap is recorded.

## R8. MCP exposure (Principle V in assisted mode)

- **Decision:** `hi-gates/scripts/hi_mcp.py` is a stdlib JSON-RPC MCP server (stdio). Its tools:
  - `hi_validate`
  - `hi_trace_check`
  - `hi_quality_rules`
  - `hi_gate`
  - `hi_status`
  - `hi_seal_package`

  It is declared in `apm.yml` with the POSIX-sh locator (R1). The same functions are available as the `hi.py` CLI for
  harnesses without MCP. The stdlib implementation removes the SDK dependency.

## R9. Measuring impact (FR-026, SC-005, SC-006)

- **Decision:** `evaluation/` in the feature folder holds:
  - a seeded-defect corpus of at least 20 requirement defects across the IQ/SQ classes, with a hidden answer key;
  - an A/B runner: the same author model and inputs, with the package (skills plus gates plus inspector) and without
    it (a plain prompt with the same needs).

  The metrics are:
  - trace coverage;
  - deterministic quality-rule violations per 100 requirements;
  - seeded-defect detection rate;
  - gate outcomes;
  - wall time and model usage (turns, plus tokens where the harness reports them).

  Results go to `evidence/` with run IDs. Targets are fixed before measuring, and results are reported whatever they are.

## R10. Local-model run location (risk, needs owner)

- loop10 local model runs were frozen by the owner on 2026-10-22, and Omniverse2 is excluded for this feature.
- **Resolved (owner 2026-11-22):** run it locally on loop10, as the last task (T080). This lifts the 2026-10-22 freeze
  for this run only.

## Installed tool versions (loop10, 2026-11-22)

| Tool | Version | Licence |
|---|---|---|
| apm-cli | 0.37.0 | MIT |
| Python | 3.13.13 (target ≥3.10) | PSF |
| Claude Code | 2.1.330 | proprietary client, owner account |
| Codex CLI | 0.171.0 | Apache-2.0 |
| uv | present in ~/.local/bin | MIT/Apache-2.0 |
