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
| Window dry run against the live owner lane | REFUSED before any change: LANE_NOT_READY:BLOCKED:DEPLOYER_WINDOW_COMMANDS_MISSING (specs/017-model-service-split/evidence/window-dry-run/) |

Not run (honest status): every [WINDOW] task (T044, T049, T056), host installs T040/T041, T061 stand-in run, T062 VM (BLOCKED), T025 CRE gate (before first host install), T035 catalog.yaml (needs the Qwen3.6 FP8 download).


## Quickstart steps (T071, offline part) — 2026-11-08 on Omniverse2, commit 45bd569f

| Step | Result | Evidence |
| --- | --- | --- |
| 1. Offline checks: all feature-017 tests, design check, lint | PASS: 250 tests collected, 0 failed; validate_design 15 PASS; ruff clean | run on Omniverse2, uv Python 3.13 |
| 2a. `recipe plan --site omniverse2` | PASS: 30 parameters, secrets shown by name only; 5 production-facing values unconfirmed (channel_url, channel_ca_bundle, auth_method, engine_key, identity_extension) | recipe CLI output |
| 2b. `recipe plan --site production` | PASS: 24 parameters; 7 unconfirmed with the platform team (model_catalog, reference_sequences, channel_url, channel_ca_bundle, auth_method, identity_extension, factory_share_concurrency) | recipe CLI output |
| 2c. `recipe verify --site omniverse2` (full sha256) | PASS: no problems, 492 s | /mnt/data/forge-c/model-service/verify-017.log |
| 3. Factory machine isolation | PASS 4/4 in the container stand-in (T061) and in the KVM VM (T062); channel was a stand-in (model tier only runs in a GPU window) | evidence/isolation/ |
| 4. First window (smoke) | NOT_RUN: needs T073 (first real lane stop/restart) | — |
| 5. Qualification windows | NOT_RUN: needs the smoke window | — |
| 6. Rebuild drill | NOT_RUN: needs a window | — |
