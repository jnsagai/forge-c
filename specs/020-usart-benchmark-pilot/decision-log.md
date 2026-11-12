# Decision log: USART benchmark pilot (FR-028)

Append-only. Every rule of the new way of working, who decided it, why, and the evidence that confirmed or
contradicted it. The way-of-working proposal cites these entries.

| # | Date | Rule | Decided by | Rationale | Evidence | Status |
|---|---|---|---|---|---|---|
| D1 | 2026-11-12 | Mimic the reference process for a module, starting with SWE.1; its content never enters the repository | owner | use an industrial ASPICE SWE.1-3 example as a process benchmark | spec FR-025 | adopted |
| D2 | 2026-11-12 | Brownfield: delivered vendor code stays frozen; the factory generates the ASPICE artefacts around it | owner | mission of the factory for vendor drivers | spec decision 1 | adopted |
| D3 | 2026-11-12 | One module per peripheral driver (HAL + LL components) under one requirement set, not one lineage per layer | owner (on recommendation) | layering is an architecture (SWE.2) decision; one set avoids cross-lineage basis machinery | spec FR-007 | adopted (pilot) |
| D4 | 2026-11-12 | When the delivered HAL does not use the delivered LL, the LL is a second public API and gets its own functional requirements | factory, confirmed by owner question | delivered HAL accesses registers directly (0 LL calls) | spec FR-008/FR-008a | adopted |
| D5 | 2026-11-12 | SWE.1 at functional/API level; register-level detail and concrete negative paths move to SWE.3 | owner (on recommendation) | requirement level of the reference process; resolves the IQ-08 tension | spec FR-017/FR-018 | pilot |
| D6 | 2026-11-12 | The level is a per-order setting; the driver ladder keeps register-level SWE.1 | owner (on recommendation) | avoid invalidating passed ladder baselines; compare before adopting | spec FR-013, plan R2 | adopted |
| D7 | 2026-11-12 | The factory generates the governance package (inputs, actors, use cases, open points) and checks its coverage; no owner sign-off; owner may add use cases | owner (on recommendation) | no customer requirements exist; owner revoked sign-offs | spec FR-001..FR-006 | adopted |
| D8 | 2026-11-12 | Scope: full delivered public API limited to the functionality comparable with the reference; the rest recorded | owner | comparable benchmark, honest coverage | spec FR-009..FR-012 | adopted |
| D9 | 2026-11-12 | Requirement quality keeps the two-phase IQ-01..12 / SQ-01..10 criteria unchanged | owner | one quality bar | spec FR-022 | adopted |
| D10 | 2026-11-12 | Every mechanism is module-agnostic; module facts are data; a second module needs zero code change | owner ("what we will do with UART will shape the new way of working") | the pilot defines the new Forge-C workflow | spec FR-027, SC-009 | adopted |
| D11 | 2026-11-12 | The governance inventory and scope classification are deterministic in prepare; actors/use cases come from a model step with a deterministic coverage check | factory (plan) | prepare stays model-free; judgement only where needed | research R3 | pilot |
| D12 | 2026-11-12 | Functional orders do not stamp the register contract and refuse SWE.2+ until those phases are defined | factory (plan) | register effects belong to SWE.3 now; honest stop instead of misleading later phases | research R2 | pilot |
| D13 | 2026-11-12 | The pilot is built on the deployed owner-lane commit 303b46ea (branch feat/020-usart-benchmark-pilot-r); the held ladder SWE.3 work (578df4d8, 751dc57f) is not part of it | factory (owner "stop swe.3") | the new way of working must not carry held changes | git: 578df4d8 not an ancestor of the branch | adopted |
