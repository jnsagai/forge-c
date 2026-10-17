# Implementation Tasks — Feature 006

**State:** all tasks NOT IMPLEMENTED by this specification; do not mark done without executable code, independent tests and recorded evidence. Task prefixes `EASA-Tnnn`; priority P0/P1.

## M0 — Baseline, normative review and reversible rollout

- [ ] **EASA-T001 [P0]** Audit Features 001–005 and locked references; independently classify code, tests, contracts, toolchain and active approval modes. **Refs:** EASA-FR-001, EASA-FR-010, EASA-FR-066. **Acceptance:** EASA-AT-001, EASA-AT-080. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T002 [P0]** Record exact 2018 standard availability/access, copyright boundaries and reviewer-based normative reconciliation plan. **Refs:** EASA-FR-005, EASA-FR-006, EASA-FR-007, EASA-FR-009. **Acceptance:** EASA-AT-002, EASA-AT-083. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T003 [P0]** Create frozen baseline manifests for LL r101 and HAL r102 and report absent evidence without inventing it. **Refs:** EASA-FR-024, EASA-FR-065, EASA-FR-071. **Acceptance:** EASA-AT-003, EASA-AT-073. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T004 [P0]** Run existing regression/design checks and store actual tool/version/exit/hash evidence. **Refs:** EASA-FR-017, EASA-FR-024, EASA-FR-066. **Acceptance:** EASA-AT-004. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T005 [P0]** Write ADR for profile-versus-ASIL separation, QM safety scope, release and capability claims. **Refs:** EASA-FR-002, EASA-FR-003, EASA-FR-004, EASA-FR-010, EASA-FR-061. **Acceptance:** EASA-AT-005, EASA-AT-078, EASA-AT-079. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T006 [P0]** Create Feature 006 source/packages/test scaffolding and deterministic contract tooling. **Refs:** EASA-FR-001, EASA-FR-066, EASA-FR-072. **Acceptance:** EASA-AT-006. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T007 [P0]** Check existing 002/003/004/005 upgrade/migration compatibility before any gate changes. **Refs:** EASA-FR-011, EASA-FR-063, EASA-FR-066. **Acceptance:** EASA-AT-007, EASA-AT-077. **Done only with:** committed implementation, deterministic tests and checked hashes.

## M1 — Method registry and assurance policy

- [ ] **EASA-T008 [P0]** Implement versioned ISO26262 Part6 method registry and 47-entry ASIL B working-index import. **Refs:** EASA-FR-005, EASA-FR-006, EASA-FR-070. **Acceptance:** EASA-AT-008. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T009 [P0]** Implement controlled reconciliation workflow with per-table review and licensed edition/hash inputs. **Refs:** EASA-FR-006, EASA-FR-007, EASA-FR-009, EASA-FR-011. **Acceptance:** EASA-AT-009. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T010 [P0]** Implement applicability records, alternatives and rationale/approver state machine. **Refs:** EASA-FR-008, EASA-FR-009, EASA-FR-070. **Acceptance:** EASA-AT-010. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T011 [P0]** Implement Standard/Enhanced/High Assurance profile selection independent of product ASIL. **Refs:** EASA-FR-002, EASA-FR-003, EASA-FR-012. **Acceptance:** EASA-AT-011. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T012 [P0]** Implement fail-closed normative authority and explicit QM/ASIL safety-scope handling. **Refs:** EASA-FR-004, EASA-FR-007, EASA-FR-028, EASA-FR-062. **Acceptance:** EASA-AT-012. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T013 [P0]** Implement policy schema, profile hashes, approved version pinning and safe live reload. **Refs:** EASA-FR-011, EASA-FR-024, EASA-FR-066, EASA-FR-072. **Acceptance:** EASA-AT-013. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T014 [P0]** Implement method-to-evidence capability resolver using real MCP adapters only. **Refs:** EASA-FR-017, EASA-FR-018, EASA-FR-022, EASA-FR-068. **Acceptance:** EASA-AT-014, EASA-AT-074. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T015 [P0]** Unit-test all applicability alternatives and unverified catalog safety behavior. **Refs:** EASA-FR-007, EASA-FR-008, EASA-FR-009, EASA-FR-070. **Acceptance:** EASA-AT-015. **Done only with:** committed implementation, deterministic tests and checked hashes.

## M2 — Independent evidence and assurance cases

- [ ] **EASA-T016 [P0]** Implement versioned independent oracle provenance and immutable holdout access controls. **Refs:** EASA-FR-013, EASA-FR-015, EASA-FR-016, EASA-FR-046. **Acceptance:** EASA-AT-016, EASA-AT-076, EASA-AT-082. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T017 [P0]** Implement evidence reference validator with digest, tool identity, exit status and frozen baseline. **Refs:** EASA-FR-017, EASA-FR-019, EASA-FR-024. **Acceptance:** EASA-AT-017. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T018 [P0]** Implement agent/inspection/verifier trust-domain collision checks, including same-prompt oracle contamination. **Refs:** EASA-FR-013, EASA-FR-014, EASA-FR-015, EASA-FR-019. **Acceptance:** EASA-AT-018. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T019 [P0]** Implement CAE claim graph, node types, support/counterevidence and residual limits. **Refs:** EASA-FR-023, EASA-FR-057, EASA-FR-058. **Acceptance:** EASA-AT-019. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T020 [P0]** Implement assurance gate aggregation with explicit UNKNOWN/NOT_RUN/BLOCKED state. **Refs:** EASA-FR-014, EASA-FR-018, EASA-FR-020, EASA-FR-059. **Acceptance:** EASA-AT-020. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T021 [P0]** Implement change-impact invalidation of affected claims and prior inspections. **Refs:** EASA-FR-021, EASA-FR-063, EASA-FR-064. **Acceptance:** EASA-AT-021. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T022 [P0]** Add independent inspector summary and separate deterministic gate authority integration. **Refs:** EASA-FR-013, EASA-FR-014, EASA-FR-064. **Acceptance:** EASA-AT-022. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T023 [P0]** Test malicious forged PASS, stale digest, reused oracle and prompt-injected evidence. **Refs:** EASA-FR-019, EASA-FR-046, EASA-FR-069, EASA-FR-072. **Acceptance:** EASA-AT-023. **Done only with:** committed implementation, deterministic tests and checked hashes.

## M3 — SWE.1 and SWE.2 stronger validation

- [ ] **EASA-T024 [P1]** Implement upstream-source anchored requirement semantic validation and discrepancies. **Refs:** EASA-FR-025, EASA-FR-027. **Acceptance:** EASA-AT-024. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T025 [P1]** Implement requirement quality and completeness checks including modes/timeouts and testability. **Refs:** EASA-FR-025, EASA-FR-028. **Acceptance:** EASA-AT-025. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T026 [P1]** Implement trace edges system/HSI -> requirements -> tests with round-trip completeness. **Refs:** EASA-FR-026, EASA-FR-028. **Acceptance:** EASA-AT-026. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T027 [P1]** Add requirements owner-freeze gate with source citations and no silent assumption filling. **Refs:** EASA-FR-027, EASA-FR-028. **Acceptance:** EASA-AT-027. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T028 [P1]** Implement architecture structural graph invariants and allocation/interface checks. **Refs:** EASA-FR-029, EASA-FR-030. **Acceptance:** EASA-AT-028. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T029 [P1]** Add optional sched/shared-resource/control/data-flow analyzers with honest limitations. **Refs:** EASA-FR-029, EASA-FR-031. **Acceptance:** EASA-AT-029. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T030 [P1]** Integrate independent architectural review, PlantUML semantic model and evidence gate. **Refs:** EASA-FR-030, EASA-FR-032. **Acceptance:** EASA-AT-030. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T031 [P1]** Run negative fixtures: contradictory requirement, invented register, architectural cycle/race. **Refs:** EASA-FR-025, EASA-FR-027, EASA-FR-029, EASA-FR-031. **Acceptance:** EASA-AT-031. **Done only with:** committed implementation, deterministic tests and checked hashes.

## M4 — SWE.3 defensive code and hardware assurance

- [ ] **EASA-T032 [P0]** Build C static coding policy for table1/table6 working-index methods without falsely labeling full MISRA. **Refs:** EASA-FR-033, EASA-FR-037. **Acceptance:** EASA-AT-032. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T033 [P0]** Implement authoritative register/access/errata semantic contract and compare generated code. **Refs:** EASA-FR-034, EASA-FR-035. **Acceptance:** EASA-AT-033, EASA-AT-084. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T034 [P0]** Validate type/pointer/initialization/hidden-control-flow/complexity findings with real analyzers. **Refs:** EASA-FR-033, EASA-FR-037. **Acceptance:** EASA-AT-034. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T035 [P1]** Add concurrency/IRQ/reentrancy/timeout invariants and trace requirement coverage. **Refs:** EASA-FR-036, EASA-FR-039. **Acceptance:** EASA-AT-035. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T036 [P0]** Implement static/MISRA rule family inventory, unsupported coverage and deviation control. **Refs:** EASA-FR-037, EASA-FR-022. **Acceptance:** EASA-AT-036. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T037 [P0]** Implement resource evidence with measured-vs-estimated environment tags and configurable budgets. **Refs:** EASA-FR-038, EASA-FR-049. **Acceptance:** EASA-AT-037. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T038 [P0]** Integrate optional bounded CBMC/formal proof and record completeness assumptions. **Refs:** EASA-FR-039, EASA-FR-068. **Acceptance:** EASA-AT-038. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T039 [P0]** Test RO-register write, fabricated API, stale test edit, uninitialized pointer, IRQ race. **Refs:** EASA-FR-035, EASA-FR-040, EASA-FR-069. **Acceptance:** EASA-AT-039. **Done only with:** committed implementation, deterministic tests and checked hashes.

## M5 — SWE.4 independent test and mutation assurance

- [ ] **EASA-T040 [P0]** Implement test-oracle derivation from frozen requirements/HSI independent of implementation. **Refs:** EASA-FR-015, EASA-FR-041. **Acceptance:** EASA-AT-040. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T041 [P0]** Implement semantic source-and-call provenance to prove each test executes allocated API. **Refs:** EASA-FR-041, EASA-FR-042. **Acceptance:** EASA-AT-041. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T042 [P0]** Implement statement/branch structural coverage ingestion and gap rationale. **Refs:** EASA-FR-043, EASA-FR-068. **Acceptance:** EASA-AT-042. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T043 [P1]** Implement deterministic mutation harness, classification and evidence, not percentage-only reporting. **Refs:** EASA-FR-044. **Acceptance:** EASA-AT-043, EASA-AT-075. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T044 [P1]** Add selected MC/DC support where toolchain provides genuine condition-decision evidence. **Refs:** EASA-FR-045. **Acceptance:** EASA-AT-044. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T045 [P0]** Integrate negative/boundary/interface tests plus check that mocks cannot fake production calls. **Refs:** EASA-FR-041, EASA-FR-042, EASA-FR-046. **Acceptance:** EASA-AT-045. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T046 [P0]** Protect test oracle and holdout files using OS/MCP/role controls with tamper tests. **Refs:** EASA-FR-016, EASA-FR-046, EASA-FR-069. **Acceptance:** EASA-AT-046. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T047 [P0]** Inject survivor mutant and prove gate blocks unsupported claims; keep killed-mutant provenance. **Refs:** EASA-FR-044, EASA-FR-059. **Acceptance:** EASA-AT-047. **Done only with:** committed implementation, deterministic tests and checked hashes.

## M6 — SWE.5 and SWE.6 target verification

- [ ] **EASA-T048 [P0]** Implement integration requirement/interface/boundary/resource verification artifacts. **Refs:** EASA-FR-047, EASA-FR-052. **Acceptance:** EASA-AT-048. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T049 [P0]** Implement injected clock/interrupt/timeout/peripheral-model faults and oracles. **Refs:** EASA-FR-048, EASA-FR-049. **Acceptance:** EASA-AT-049. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T050 [P0]** Add source-backed target fidelity classifier HOST/SIMULATOR/RENODE/HIL/PHYSICAL with limitations. **Refs:** EASA-FR-049, EASA-FR-054, EASA-FR-055. **Acceptance:** EASA-AT-050. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T051 [P1]** Add back-to-back model/code comparison where applicable, or documented inapplicability. **Refs:** EASA-FR-050. **Acceptance:** EASA-AT-051. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T052 [P0]** Strengthen Renode and integration test outcome validation against observed target behavior. **Refs:** EASA-FR-051, EASA-FR-052. **Acceptance:** EASA-AT-052. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T053 [P0]** Implement SWE.6 operational scenarios, fail-path and degraded-mode coverage. **Refs:** EASA-FR-053, EASA-FR-055. **Acceptance:** EASA-AT-053, EASA-AT-081. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T054 [P0]** Implement requirements-based measured execution trace and actual coverage of observations. **Refs:** EASA-FR-053, EASA-FR-056. **Acceptance:** EASA-AT-054. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T055 [P0]** Block HIL claim for Renode-only environment and target evidence not observed. **Refs:** EASA-FR-054, EASA-FR-055, EASA-FR-068. **Acceptance:** EASA-AT-055. **Done only with:** committed implementation, deterministic tests and checked hashes.

## M7 — Release, UI, documentation and backward compatibility

- [ ] **EASA-T056 [P0]** Extend existing 002/003/004 dashboard with assurance profile, claims, independence and gap drilldown. **Refs:** EASA-FR-018, EASA-FR-023, EASA-FR-058. **Acceptance:** EASA-AT-056. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T057 [P0]** Extend release/finalize.py package inventory with method applicability, CAE and attestation hashes. **Refs:** EASA-FR-057, EASA-FR-060. **Acceptance:** EASA-AT-057. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T058 [P0]** Preserve READY_FOR_OFFLINE_REVIEW/BLOCKED and separate technical success from packaging success. **Refs:** EASA-FR-059, EASA-FR-060, EASA-FR-061. **Acceptance:** EASA-AT-058. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T059 [P0]** Gate missing safety analysis/tool confidence on ASIL scope; allow documented QM N/A. **Refs:** EASA-FR-004, EASA-FR-022, EASA-FR-062. **Acceptance:** EASA-AT-059. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T060 [P0]** Verify all invalidated downstream artefacts must re-run upon changes. **Refs:** EASA-FR-021, EASA-FR-063, EASA-FR-064. **Acceptance:** EASA-AT-060. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T061 [P0]** Regress Features 001–005 with no modified audit, safety policy or archived evidence. **Refs:** EASA-FR-066, EASA-FR-072. **Acceptance:** EASA-AT-061. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T062 [P0]** Document feature operations, standard license reconciliation, oracle independence and rollout. **Refs:** EASA-FR-006, EASA-FR-007, EASA-FR-067, EASA-FR-071. **Acceptance:** EASA-AT-062. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T063 [P0]** Write reviewer-readable assurance case summary with remaining claims and missing evidence. **Refs:** EASA-FR-057, EASA-FR-058, EASA-FR-060. **Acceptance:** EASA-AT-063. **Done only with:** committed implementation, deterministic tests and checked hashes.

## M8 — Adversarial validation and staged operation

- [ ] **EASA-T064 [P0]** Run immutable LL r101 and HAL r102 shadow audit; list new defects and unverifiable claims. **Refs:** EASA-FR-065, EASA-FR-071. **Acceptance:** EASA-AT-064. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T065 [P0]** Run full negative campaign: poisoned oracle, forged logs, stale evidence, hardware-fidelity mismatch. **Refs:** EASA-FR-018, EASA-FR-019, EASA-FR-054, EASA-FR-069. **Acceptance:** EASA-AT-065. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T066 [P0]** Run positive and negative case sets on independent verifier with real tools when available. **Refs:** EASA-FR-013, EASA-FR-017, EASA-FR-059. **Acceptance:** EASA-AT-066. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T067 [P0]** Perform coverage and mutation calibration on frozen comparable test subjects. **Refs:** EASA-FR-043, EASA-FR-044, EASA-FR-045. **Acceptance:** EASA-AT-067. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T068 [P0]** Carry out OBSERVE_ONLY dry run and measure false positives, false negatives, additional runtime and gaps. **Refs:** EASA-FR-066, EASA-FR-067. **Acceptance:** EASA-AT-068. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T069 [P0]** Perform owner-authorized PILOT on real end-to-end driver without claiming ready if safety evidence missing. **Refs:** EASA-FR-062, EASA-FR-067, EASA-FR-068. **Acceptance:** EASA-AT-069. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T070 [P0]** Run ENFORCING readiness decision based on real evidence/authorization, not task completion alone. **Refs:** EASA-FR-067, EASA-FR-071. **Acceptance:** EASA-AT-070. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T071 [P0]** Regenerate FR -> task -> acceptance -> evidence matrix and report PASS/FAIL/BLOCKED/NOT_RUN. **Refs:** EASA-FR-001, EASA-FR-065, EASA-FR-070. **Acceptance:** EASA-AT-071. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T072 [P0]** Prepare review PR without auto-merging, no claim of ISO conformance or 100% assurance. **Refs:** EASA-FR-061, EASA-FR-071, EASA-FR-072. **Acceptance:** EASA-AT-072. **Done only with:** committed implementation, deterministic tests and checked hashes.

## Dependency and signoff rules

1. M0 must establish actual baseline before altering inspection gates. M1/M2 are prerequisites for enabling any stronger profile; M3–M6 may proceed in parallel only when independent source/evidence baselines exist. M7/M8 validate completed features.
2. Existing CRE/Feature 005 sources and policy remain the sole authority for recovery/Conductor; do not create a duplicate supervisor or enable unreconciled feature branches.
3. Task priority P0 does NOT mean a test passed or production-ready; 006 is only a specification at commit creation.
4. All new AI agents require SKILL.md, bounded tokens and scoped MCP access; deterministic services do not masquerade as agents.
5. Never relax test oracles, benchmark thresholds, policy permission, sample equivalence or safety scope to make a task PASS.
6. BLOCKED/NOT_RUN explicitly recorded if licensed standard, archives, HIL, independent tool or host privileges unavailable. Continue independent tasks.
7. Do not autonomously merge or approve safety release. Submit a draft PR showing objective evidence and residual risk.
