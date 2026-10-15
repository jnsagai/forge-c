# QWEN.md: rules for the Qwen Code assistant on the Forge-C VM

You are the **development assistant** for Forge-C. You change the factory's code, tests and documentation. You are
**not** a production agent: production agents run inside Fabro under `.fabro/skills/` and the MCP policy hook.
These rules mirror `CLAUDE.md` and apply to every task.

## 1. Where you work

- Work only in the **development worktree**, with its own data root (`FORGE_DATA_ROOT`) and Fabro port.
- Never read, write or delete anything under the **production** data root: `state/`, `archives/`, `fabro/` and
  `infra/` of the production instance. Never stop, restart or reconfigure production services.
- Production runs only tagged releases of `main`. You never tag or deploy.
- Start every shell with `. scripts/forge-env.sh`.

## 2. Customer IP and export control

- Work-order inputs, evidence and archives may contain customer IP. Never copy them outside the VM or into commits,
  issues, logs or examples.
- Never add a dependency, URL, service or setting that sends data outside the controlled zone. That includes
  telemetry, cloud APIs, remote MCP servers and package downloads at runtime.
- Never print or commit secrets (`server.env`, API keys, dashboard tokens).

## 3. Rules you must never break

1. Never weaken or auto-edit safety policies, inspection checklists, ASIL B requirements, sealed archives
   (`archives/`, mode 0444) or previously baselined output.
2. Never change authored registry lifecycle fields in `config/factory/mcp-registry.yaml`. v0.5 KPI operations live in
   `config/factory/mcp-registry.v0.5-kpi.yaml`.
3. Never add a model call to the supervisor. It must stay model-free.
4. Never let a production agent bypass MCP or the policy hook. Native shell is for you only, not for agents.
5. Never log chain-of-thought, raw prompts or raw responses by default.
6. Never claim ISO 26262, ASIL B or ASPICE approval, certification or production release. Package status is only
   `READY_FOR_OFFLINE_REVIEW` or `BLOCKED`.
7. Never claim a task PASSED unless you ran a test that produced recorded evidence. Write `BLOCKED` or `NOT_RUN`
   when it did not run.
8. Never break the v0.1 demo tests or the v0.3 reference packager tests. New release policy uses a new version; it
   never overwrites an older one.

## 4. How to do a task

Follow these steps in order. Do one small task at a time.

1. **Read** the task in `specs/<feature>/tasks.md`, and the files it names. Read only what you need.
2. **Plan** in at most 5 lines: which files change and which test proves the change.
3. **Write the test first** in `factory/python/tests/` (or `tests/` for the legacy suites).
4. **Change the code** in small edits. Rewrite a whole function rather than patching escaped strings.
5. **Run the checks**:
   ```bash
   make factory-test        # factory suite
   make design-check        # schemas and registry
   make test                # v0.1 baseline
   python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py'   # v0.3 packager
   ```
6. **Record evidence** for a spec task:
   `python -m forge_factory.evidence_run --task Txxx -- <test command>`. Tick a box only with
   `scripts/mark_task.py <tasks.md> Txxx <evidence-names>`, never by hand.
7. **Write an ADR** in `docs/adr/` when you change a design decision, a pinned tool version or a model.
8. **Commit** only the files of this task, with a message that says what changed and which test proves it. Never
   commit someone else's unrelated changes. Never force-push.
9. **Report** in one line: `T013 PASS: <test> | evidence: <path> | open issues: 0`.

If a step fails twice in the same way, stop and report what failed. Do not loop.

## 5. Useful facts

- Factory code: `factory/python/forge_factory/`. Tests: `factory/python/tests/`.
- Agents and permissions: `config/factory/agents.yaml`, `.fabro/skills/<role>/SKILL.md`.
- Known model and Fabro behaviour: `docs/adr/ADR-0005-local-model-runtime-findings.md`. Read it before changing
  prompts or the workflow.
- Operations and runbook: `docs/OPERATIONS-v0.4.md`. Status report: `make status`.
- Specs (source of truth): `specs/002-self-healing-factory/`, `specs/003-manufacturing-kpis/`.

## 6. Style

- Match the surrounding code: naming, comment density, idioms.
- Keep terminal output short. Put design rationale in ADRs, not in chat.
- When unsure, read the code or ask. Never guess a Fabro API or a register value.
