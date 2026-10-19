# CR-T042: full regression on 99fafa2 (feature 007 head, recorded 2026-10-19)

`run.sh` checks out 99fafa2 in a frozen worktree with a hard HEAD guard, then runs:

- `tests/spec/validate_design.py`;
- the 005 and 006 spec validators;
- `ruff check factory/python/forge_factory`;
- `forge_factory.assurance.regress --full`.

Result: all PASS (design-006, design-006 negatives x2, design-check-002, legacy-v0.1, factory-test, i.e. the full factory pytest suite). The KPI pilot snapshot the suite rewrites was restored afterwards.
