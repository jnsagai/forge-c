# Quickstart / validation guide: Feature 023

Proves the feature end to end. Contracts: [contracts/](contracts/). Entities: [data-model.md](data-model.md).

## Prerequisites

- Python ≥3.10 and git.
- apm-cli ≥0.37 in a user venv:

  ```sh
  uv venv ~/.venvs/apm && VIRTUAL_ENV=~/.venvs/apm uv pip install apm-cli
  ```

- Reference harnesses:
  - Claude Code logged in to an account (author);
  - Codex CLI logged in with ChatGPT (inspector, `codex login status`).
- Optional: poppler (`pdftotext`, `pdfinfo`) for driver mode. gcc and cppcheck for the code-stage gates.

## V1: Install into a clean project (SC-002)

```sh
mkdir demo && cd demo && git init
apm init -y --target claude,codex
apm install jnsagai/forge-c/packages/forge-c-hi#<tag>    # during development: apm install <repo>/packages/forge-c-hi
```

**Expected:**

- `.claude/skills/hi-*` and `.agents/skills/hi-*` are present;
- `.claude/agents/hi-*.md` and `.codex/agents/hi-*.toml` are present;
- the hooks are in `.claude/settings.json` and `.codex/hooks.json`;
- `.mcp.json` lists `forge-c-hi`;
- `apm audit` reports no issues.

## V2: P1 demo, natural-language needs → SYS-REQ → SW-REQ (US1, SC-001, SC-004)

```sh
# copy examples/watchdog-manager/needs/ from the installed package (its apm_modules path is in the README) to ./needs
python3 .claude/skills/hi-gates/scripts/hi.py init --profile generic --level HI-2 --class natural_language
python3 .claude/skills/hi-conductor/scripts/conduct.py --stage sys-req --until sw-req
python3 .claude/skills/hi-gates/scripts/hi.py seal
```

**Expected:**

- `hi/sys-req/requirements.json` and `hi/sw-req/requirements.json` validate;
- `hi/trace-matrix.md` shows 100% of items traced both ways;
- `.hi/runs/<id>/events.jsonl` records the claude author and the gpt inspector;
- the package manifest status is READY_FOR_OFFLINE_REVIEW, or BLOCKED with the gaps listed. Both are valid outcomes;
  the evidence records which one happened.

## V3: Negative cases (US1-AS4, US5-AS2, SC-009)

- Delete one trace link → `hi trace` FAIL → `hi seal` BLOCKED with a gap naming the item.
- Uninstall poppler, or set `HI_FORCE_NOT_RUN=doc-index` → the source-resolution gate is NOT_RUN → BLOCKED, never PASS.
- Write a file outside the author's scope while the author role is active → the hook denies it. Bypass the hook → the
  `hi scope` gate fails.

## V4: Driver mode (US2)

`hi init --class reference_document --entry-stage sw-req`, then `hi doc-index <your RM pdf> --doc-id RM-IWDG`. Run the
conductor on `sw-req`. **Expected:** every DRV requirement has `{doc_id, section, page}` resolving in the index. Link
the middleware project → the middleware SW-REQ traces to the DRV interface items.

## V5: Profile switch (US3, SC-007)

Re-run `hi gate sw-req` under `--profile iso26262 --level HI-2` and under `iec61508 HI-2`. **Expected:**

- `git diff --stat .claude/skills .agents/skills` is empty;
- the reports show "ASIL B" or "SIL 2" respectively, with that profile's required gates.

## V6: Package tests and regression

```sh
cd packages/forge-c-hi && python3 -m pytest -q
cd ../.. && python3 tests/spec/validate_design.py
python3 packages/forge-c-hi/tools/publish_check.py packages/forge-c-hi   # SC-008: 0 violations
```

## V7: Impact evaluation (US7, SC-005, SC-006)

Follow `evaluation/PROTOCOL.md`: run the baseline arm and the with-package arm on the same inputs and author model.
Results go to `evidence/eval/`, and the report links each number to its run file.
