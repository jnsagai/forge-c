# Claude Code / cloud-development quickstart — Feature 011

**Scope:** implementation through Claude Code (may use cloud inference in the development tool), but Forge-C v2 runtime remains **strictly local-only and offline** on RTX 4070 Laptop 8 GB / 32 GB RAM. No run or product release is authorized by this document.

## Repository and entrypoints

- Forge-C working branch: `feat/011-safec-semantic-first`. Read top-level `CLAUDE_FEATURE011_START.md`, this directory`s `spec.md`, `plan.md`, `research.md`, `data-model.md`, `acceptance-tests.md`, `tasks.md`, `contracts/*.schema.json`, then `.specify/memory/constitution.md`, `docs/adr/ADR-0013*`, `ADR-0014*`, `ADR-0015*` and Feature 010 frozen evidence.
- SafeC Forge is a separate **private** project: obtain explicit authorized read/write access and create **its own branch**. Verify reference SHA `556dca8df4d2fccd9cb59fd8fb0432aafdd05835` against actual remote main before editing. Do not publicly copy its source or raw logs.
- If access to either workspace, host or tool is missing, record BLOCKED and continue with independently testable work; never invent capabilities, tests or completed tasks.

## First commands (run on the appropriate checkout; do not assume they have been executed)

```bash
git status --short
git rev-parse HEAD
git branch --show-current
# Forge-C baseline checks (existing commands)
python3 tests/spec/validate_design.py
bash scripts/lrtx_compat_check.sh
python3 -m pytest factory/python/tests/test_lrtx_profile.py factory/python/tests/test_lrtx_swe1.py
```

Run appropriate remaining tests/versions discovered from the actual repository. For SafeC use its own pinned Cargo lockfile and `cargo test --workspace --locked` on Linux; its existing Windows-specific scripts are **not** a substitute for Linux evidence.

## Safe implementation cadence

1. Record immutable before-state revisions, tree hashes, protected configuration and private/public trust boundary.
2. Implement and test **M0, then M1** bridge wire contract and negative cases, with the SafeC process returning UNSUPPORTED until its semantic core exists.
3. Implement **M2** typed hardware semantics in SafeC private branch with register negative fixtures, independent parser/schema validation and source trace. Do not modify approved Wheel sampled-latch contracts or toolchain versions to suppress errors.
4. Integrate **M3** into the Forge-C v2 **explicit profile** only, with existing gate invariants and local token metrics.
5. Benchmark and qualify **M4** independent inspection on clean/mutant holdouts before attempting any full Fabro workorder or campaign.
6. Proceed to **M5/M6** only when earlier tasks and acceptance tests have honest real evidence. A failed pilot is a reported result, not a reason to weaken gate criteria.

## Cloud versus local boundary

Claude Code may author software, open draft PRs and prepare tests in a networked development environment. The deployed Fabro local profile MUST deny external networking and ACP/cloud providers, including Claude. Do not send private SafeC files to a public Forge-C PR; do not record secrets or model raw reasoning.

## Required completion summary

Per milestone output: `M# F011-T### PASS|FAIL|BLOCKED|NOT_RUN — commit — test/evidence — limitations`. Link both draft PRs when needed. Report baseline compatibility, inspection false positives/misses, remaining mandatory ASIL owner inputs, SafeC unsupported methods and total wall/tokens/Wh per genuine accepted workorder. Never claim a formal proof or release without precise obligation and tool evidence.
