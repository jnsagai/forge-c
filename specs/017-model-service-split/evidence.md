# Feature 017 evidence (T070)

All runs on Omniverse2, branch feat/017-model-service-split-impl at 158f9990, 2026-11-08.

| Check | Result |
| --- | --- |
| Feature 017 tests (model_tier, modelservice, external gateway, capture, exporter) | 242 tests, all pass |
| ruff on model_tier and forge_factory/modelservice | All checks passed! |
| tests/spec/validate_design.py | PASS: 15 static design tests. This does NOT validate runtime integrations. |
| Full factory suite on this branch | EXIT=1: 738 failures/errors in existing test files (log /mnt/data/forge-c/model-service/fullsuite-017.log) |
| The same 127 existing test files on the base commit 482b824b | 738 failures/errors, **identical set** (0 only on 017, 0 only on base): pre-existing, environment-dependent (loop10 paths, private inputs, toolchains); no regression from feature 017 |
| Owner-lane pinned sources (llm_gateway.py, afo/product_job.py, afo/execution_lifecycle.py, fabro/client.py, lrtx/stack.py) | byte-identical to 482b824b (tested) |
| Window dry run against the live owner lane | REFUSED before any change: LANE_NOT_READY:BLOCKED:DEPLOYER_WINDOW_COMMANDS_MISSING (evidence/017/window-dry-run/) |

Not run (honest status): every [WINDOW] task (T044, T049, T056), host installs T040/T041, T061 stand-in run, T062 VM (BLOCKED), T025 CRE gate (before first host install), T035 catalog.yaml (needs the Qwen3.6 FP8 download).
