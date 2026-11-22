# M0 evidence summary (T001–T022)

- **Package tests:** `m0-pytest.txt`, 105 passed and 1 xfailed (plus `tests/test_checklists.py`, 11 passed, added after that log for T013/T014), on Python 3.10.12 with apm-cli 0.37.0. The xfail is
  `test_mcp_server_declared`, which is strict and waits on T033 (US1).
- **Install smoke (T003/T022):** a real `apm install` of a git copy of the package into a consumer with targets claude
  and codex places:
  - `hi-gates` in `.claude/skills` and `.agents/skills`;
  - hooks in `.claude/settings.json` and `.codex/hooks.json`;
  - agents in `.claude/agents` and `.codex/agents`.

  `apm audit` is clean.
- **Guard (T008/T018):** it fails closed while a role is active, for Claude Write/Edit/MultiEdit/NotebookEdit and Codex
  `apply_patch` inputs. The hook command was tested from both installed roots.
- **Regression:** `python3 tests/spec/validate_design.py` gives PASS (14 static design tests).
- **NOT_RUN:**
  - A live Codex PreToolUse hook honouring exit code 2. Mitigations: the inspector runs with `--sandbox read-only`, and
    the scope gate is the backstop. To be exercised in T041.
  - A live Claude Code hook inside a real session. To be exercised in T041.
