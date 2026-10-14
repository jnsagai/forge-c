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
