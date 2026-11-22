# T041 run 5, attempt 1: BLOCKED, the author wrote no work product (conductor gap)

- **Date:** 2026-11-22, 23:54–23:57 UTC. Clean consumer project, final inputs, package at `b93df893`. Claude Sonnet
  author, GPT-6.1 Terra inspector.
- **What happened:** in its one create call (2.9 min) the author wrote a Python generator `hi/sys-req/_gen.py` instead
  of `hi/sys-req/requirements.json`, then tried to run it and to call the `hi_gate` MCP tool. The conductor's author
  binding allows no shell and no gate tool (by design), so both were refused, and the author replied that it could not
  finish. The conductor ended the stage BLOCKED ("the author did not write hi/sys-req/requirements.json").
- **Fix (the commit that adds this file):** the author prompt now says, in conductor mode, to write the work product
  file directly, with no scripts, commands or gate tools; and when an author call leaves no work product the conductor
  gives one corrective retry naming the problem before it blocks. Test:
  `test_author_that_writes_no_workproduct_gets_one_corrective_retry`.
