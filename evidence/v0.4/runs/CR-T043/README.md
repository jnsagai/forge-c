# CR-T043: CRE CHANGE promotion, feature 007

Recorded 2026-10-19.

Promotion candidates must not change `evidence/**`. Each candidate was therefore built on main (a2dd3fa) from
`git diff a2dd3fa..<branch head> -- . ':!evidence'`. Each candidate tree equals the branch head's tree outside
`evidence/`.

| Iteration | Branch head | Candidate | Decision | Result |
|---|---|---|---|---|
| 1 | c9f836a | 10f033e | `pd-8751bf7a491efacc018e` | **REJECTED**: prevention FAIL, RESOLVED_FAILURE_REAPPEARED (RPR-049: ERROR) |
| 2 | 99fafa2 | 7e7066d | `pd-b6f44c10ef98b46db5b3` | **ELIGIBLE_FOR_OFFLINE_REVIEW**: all hard gates PASS (the reproducer gate does not apply to a CHANGE) |

**Cause of iteration 1:**
- The new ACP-proxy usage recording read `self.prompts`, which only `Proxy.__init__` sets.
- The frozen CAPA-045 reproducer (RPR-049) builds a bare `Proxy` without `__init__`, so it raised an error.
- **Fix in 99fafa2:** class-level defaults (`kind`, `prompts`), so the proxy copes with a bare instance. Frozen
  reproducers are never changed.
- After the fix, RPR-045, RPR-049 and RPR-053 report SYMPTOM_ABSENT.

Both decision records are in `evidence/cre/decisions/`.
