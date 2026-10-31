# CAPA-076 regression, loop10, 140 test files (regression-files.txt)
baseline 2d91c2fa (code-identical to d18e454a; later commits are evidence only): 6 failed, 1738 passed, 18 skipped in 3585.85s (0:59:45)
candidate (fix, uncommitted on d18e454a = 51a9138d content): 5 failed, 1739 passed, 18 skipped in 3602.84s (1:00:02)
failures only in candidate: 0; only in baseline: 1 (test_lrtx_drill::test_stop_waits_for_the_namespace_holder_and_forgets_it, timing)
shared pre-existing failures (5): test_afo_paging_limits source_limit, test_da014_provider_recovery retired namespace, test_lrtx_compat x2, test_lrtx_rework_unchanged checkpoint reuse
