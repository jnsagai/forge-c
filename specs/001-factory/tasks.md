# Backlog and task list — SPEC-001

Work item format: `TASK-ID [Owner role] (Depends on) Description -> acceptance`.

- [ ] `T-001` [Safety/Owner] Select device variant + board + silicon revision -> approved inventory
- [ ] `T-002` [Safety/Owner] Obtain TSC/TSR/SYS/SW safety allocations and operating safe-state -> traceable approved references
- [X] `T-003` [Architecture] HSI/RM/errata semantic model & source provenance -> verified register contract ✅ Evidence: `evidence/v0.4/runs/001-T-003/latest.json` (sealed package WO-0002B-STM32N6-RCC-HAL-r154, checked read-only by forge_factory.backlog001)
- [x] `T-004` [Factory] Project charter, constitution, SWE and ASIL evidence mapping -> reviewable documents
- [x] `T-005` [Factory] Scaffold profile/footprint/trace/checks gates -> executable negative tests
- [X] `T-006` [Factory] Pin Fabro version, providers/models and sandbox -> verified model/proxy config ✅ Evidence: `evidence/v0.4/runs/001-T-006/latest.json`
- [X] `T-007` [Factory] Validate end-to-end Fabro DOT workflow syntax & path semantics -> smoke run ✅ Evidence: `evidence/v0.4/runs/001-T-007/latest.json`
- [X] `T-008` [Build] C11 target and native build scripts with CMake/compilers -> reproducible target + test build ✅ Evidence: `evidence/v0.4/runs/001-T-008/latest.json`
- [ ] `T-009` [SWE.1] Approved SWE requirements for RCC including RAM/ROM/timing -> reviewed requirements baseline
- [ ] `T-010` [SWE.2] Software architecture and safety interaction analysis -> signed design review
- [X] `T-011` [SWE.3] Detailed design/API and code implementation -> reviewed C/H + map/ELF ✅ Evidence: `evidence/v0.4/runs/001-T-011/latest.json` (sealed package WO-0002B-STM32N6-RCC-HAL-r154, checked read-only by forge_factory.backlog001)
- [X] `T-012` [SWE.4] Unit tests + static/MISRA analysis -> raw test/violation evidence ✅ Evidence: `evidence/v0.4/runs/001-T-012/latest.json` (sealed package WO-0002B-STM32N6-RCC-HAL-r154, checked read-only by forge_factory.backlog001)
- [ ] `T-013` [SWE.5] Component/integration test adapters for RCC/clock/interrupt -> recorded integration results
- [ ] `T-014` [SWE.6] Software requirements verification on representative target -> full software report
- [ ] `T-015` [Optimization] Add map/stack/cycle metric collectors and rigorous baseline comparator -> measured Pareto report
- [ ] `T-016` [Safety] Review tool confidence and any missing qualification/coverage evidence -> decision register
- [X] `T-017` [Process] Export trace graph, work products and raw evidence -> audit package with gaps reported ✅ Evidence: `evidence/v0.4/runs/001-T-017/latest.json` (sealed package WO-0002B-STM32N6-RCC-HAL-r154, checked read-only by forge_factory.backlog001)
- [ ] `T-018` [Release] Independent review and controlled sign-off -> authenticated release record
- [ ] `T-019` [Reuse] Port to watchdog/GPIO/other driver -> reuse demonstration, no HSI assumptions leaked
