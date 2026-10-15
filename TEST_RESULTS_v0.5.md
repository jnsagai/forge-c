# Forge-C v0.5 — Consolidation verification (2026-10-14)

The following commands were actually executed on the project **during packaging**, using the provided files. A passing design-contract test is **not** evidence that the planned subsystem has been implemented.

| Check | Executed result | Limitations |
|---|---|---|
| `python3 tests/spec/validate_design.py` | PASS — 14 design checks | Schema, registry, consistency, and v0.4 diagram references only; no autonomous runtime |
| `python3 -m unittest discover -s tests -v` | PASS — 16 Python engineering-gate tests | Fixture and gate logic, not certified software |
| `python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py' -v` | PASS — 7 reference-packager tests | Standalone packager, not yet connected to Fabro |
| `./scripts/run_oss_demo.sh` | PASS — Clang host C build + native test + LLVM MC/DC evidence generated | Host-only RCC demonstrator; no real MCU evidence |
| `./scripts/run_oss_clang_analyzer.sh` | PASS — no diagnostics for host demo | Does not establish formal MISRA compliance |
| `./scripts/compare_host_size.sh` | PASS — Clang `-Os` / `-O2` / `-Oz` comparison | Host binary footprint, not target Flash/RAM/stack proof |
| JSON, schema JSON, YAML, TOML, editable draw.io XML parsing | PASS | Syntactic validity only |
| Final checksums + fresh ZIP extraction | PASS upon packaging | See `SHA256SUMS.txt`; command `python3 scripts/verify_bundle.py` |

**Not executed / not implemented:** Fabro+Qwen autonomous workflow, new MCP server adapters, runtime agent SKILL enforcement, model-free supervisor, repair loop, shared lessons runtime, dashboard, live trace filtering, KPI engine, target Arm/Renode/HwSim, full MISRA compliance, hardware-based ASIL B verification and human safety approval.

The carried demo evidence in `evidence/oss-demo/` is explicitly tagged `NOT_ASIL_B_EVIDENCE`. The only permissible production release states remain `READY_FOR_OFFLINE_REVIEW` and `BLOCKED`, subject to offline human review.

## Night-run implementation verification (2026-10-14/15, branch `night-run/2026-10-14`)

Every row below was executed; per-task records (command, exit code, git head, host, log SHA-256) are in
`evidence/v0.4/runs/<task>/latest.json`. Generated summary: `docs/IMPLEMENTATION-STATUS-v0.4.md`.

| Check | Result | Evidence |
|---|---|---|
| Legacy v0.1 gates, v0.3 packager, design validator, OSS demo (LLVM 19 MC/DC), clang analyzer, host size | PASS | `evidence/v0.4/runs/T002-*` |
| Factory suite `make factory-test` (≈200 tests incl. M1–M7, KPI) | PASS (live/opt-in tests run separately) | `evidence/v0.4/runs/T0xx`, `KPI-T0xx` |
| Live Fabro 0.362 probes (skills, MCP stdio, pre_tool_use hook, native-bypass denial) | PASS | `T004`, `T007`, `T018` |
| Supervisor 100 healthy polls → 0 model calls; systemd SIGKILL restart | PASS | `T020`, `T024` |
| Live autonomous repair on qwen3:8b (rollback, then promotion, lesson validated + reused) | PASS | `evidence/v0.4/live/AT-13-14-repair/` |
| Dashboard browser smoke at 390/1280 px (headless Firefox) | PASS | `T038`, `evidence/v0.4/live/dashboard/` |
| Clean bootstrap + demo + fault-injection reproduction | PASS | `T050` |
| STM32N6 RCC work orders (r1–r9) on local qwen3:8b | Ran unattended; packages BLOCKED with explicit gaps | `$FORGE_DATA_ROOT/archives/WO-0002-*` |

Not performed (declared, not hidden): target/MCU verification, Renode/HwSim, CBMC/Frama-C, Unity/CMock, tool
qualification, offline human safety review. No package claims ASIL B approval.
