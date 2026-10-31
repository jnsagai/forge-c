# CAPA-077 regression, loop10, 141 test files (regression-files.txt)
baseline 15218323: 6 failed, 1738 passed, 18 skipped in 3495.84s (0:58:15)
candidate (220bb9d8 content, uncommitted at run start): 5 failed, 1747 passed, 18 skipped in 3514.43s (0:58:34)
failures only in candidate: 0; only in baseline: 1 (test_lrtx_drill::test_stop_waits_for_the_namespace_holder_and_forgets_it, timing; also baseline-only in the CAPA-076 regression)
candidate +9 passed: the 8 new test_owner_obligation_coverage tests and the drill test
