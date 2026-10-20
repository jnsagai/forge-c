# Research: Brownfield Work Orders

Sources: three read-only code surveys (2026-10-20):
- the work order and workflow flow;
- the gates that assume factory-written code;
- ST's stm32n6xx-hal-driver v1.4.0 RCC code.

File references are to `factory/python/forge_factory/` unless stated.

## R1. How the delivered code is kept away from the requirement author (FR-007)

- **Decision**: do not put delivered code in the workspace at prepare time.
  - Store it content-addressed in `state/workorders/<wo>/delivered/` (read-only).
  - A deterministic node `delivery_inject`, placed between the SWE.1 inspection gate (PASS) and the SWE.2 entry,
    re-checks the fingerprints, writes the files read-only into `software/...` and commits them. It records the
    frozen SWE.1 baseline id and hash it followed.
  - As defence in depth, brownfield manifests add a read deny on the delivered paths for SWE.1 roles (author,
    triage). The ACP gate filters grep/glob/list results for denied paths.
- **Rationale**:
  - There are no per-role read scopes today (`policy/authz.py:158-167`).
  - The ACP `grep` walks the whole tree under its root (`acp/gate.py:181-193`), so a path deny alone is bypassable.
  - Code committed at prepare time would also sit in git history.
  - Injecting after SWE.1 is frozen makes the order provable from the gate log.
- **Alternatives**: copying at prepare with a read deny (leaks through tree walks and history); a separate SWE.1
  workspace (duplicates the run machinery).

## R2. Where the work order describes the delivery

- **Decision**: a `delivery` block in the example's `workorder.json`, with:
  - `code_mode`;
  - `origin`, `licence` and `licence_allows_modification`;
  - `source` (directory or archive) and `files` (delivery path → workspace path);
  - `scope.functions` (function or macro names);
  - `dependencies` (fingerprinted vendor headers, with origin and licence);
  - `build` (defines and include order).

  `layer` (LL or HAL) keeps its meaning, so the existing per-layer harnesses (LL array harness, HAL `ll_fake`)
  apply to factory-style deliveries.
- **Rationale**: it reuses the example/work-order format and the `layer` machinery (`layer.py`).
- **Alternatives**: a new layer value `BROWNFIELD` (rejected: brownfield is orthogonal to LL/HAL).

## R3. Protection of delivered files (FR-013, FR-014)

- **Decision**: `Authorizer` reads the manifest's `delivered` paths.
  - **FROZEN**: they are protected for every role (`PROTECTED_PATH_DENIED`).
  - **FIX_ALLOWED**: `swe3-author` may write a delivered path only while a CODE defect is IN_FIX.
  - **Both modes**: `verify_delivery` re-hashes at SWE.3 verify and at packaging. In FIX_ALLOWED mode each changed
    file must map to a FIXED/VERIFIED CODE defect and lie inside the scope's files. The change report records the
    defect, the old and new SHA-256 and a unified diff.
- **Rationale**: the provided-LL precedent is chmod plus an after-the-fact hash check only
  (`inspection/implementation.py:81-83`). Policy-level refusal is stronger and auditable.

## R4. SWE.2/SWE.3 for code that exists

- **Decision**: brownfield SWE.3 chain: `delivery_check` (deterministic) → `swe3_author` (recovered detailed
  design, unit specs, code trace map) → `swe3_verify`. FIX_ALLOWED adds the existing `swe3_fix_author` for CODE
  defects only.
  - Not run: `swe3_regmap` (it would overwrite a delivered LL header, `inspection/regmap.py:109-118`), the LL author
    and the HAL author.
  - SWE.2 prompts ask for the architecture *recovered* from the delivered code. The SWE.1 prompt is unchanged.
- **Rationale**: generators must never touch delivered code. The existing checks on documents (architecture,
  views, register contract) work unchanged.

## R5. Code trace without tags

- **Decision**: `workproducts/SWE.3/code_trace_map.json` maps each delivered in-scope function to its file,
  file fingerprint, unit id and unit spec ids. The SWE.3 author fills it, from a deterministic seed listing the
  scope functions and their locations.
  - In brownfield mode `swtrace.check_code` reads the map instead of Doxygen tags. It checks that each function
    exists at the stated file, the fingerprint matches the delivery, every unit spec is covered, and every scope
    function is mapped.
  - Test trace (`@test/@verifies`) and SWR tags in Robot tests are unchanged, because the factory writes the tests.
- **Rationale**: `swtrace` requires tags before every function (`inspection/swtrace.py:416-458`). Frozen code cannot
  have them.

## R6. Conformance findings (FR-008)

- **Decision**: deterministic conformance at the SWE.2 freeze and again after SWE.3:
  - **Requirement → function:** from the SWE.2 allocation (`api_calls.json`/allocation table). A requirement
    allocated to a function absent from the delivery gives `NO_CODE`.
  - **Function → requirement:** a scope function not allocated to any requirement gives `NO_REQUIREMENT`.
  - **Contradiction:** a register access in the delivered function that differs from the requirement's register
    effects (`register_effects.json`, built from the RM index) gives `CONTRADICTION`, citing the RM section and
    page. Failing tests produce CODE defects, which are also contradictions.

  The register access of each delivered function is extracted deterministically:
  - for the factory style: `ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U]` with `|=`/`&= ~`/`=` and masks;
  - for the CMSIS style (pilot): `WRITE_REG/SET_BIT/CLEAR_BIT/MODIFY_REG(RCC->X, M)` and `RCC->X op= M`;
  - in both cases set/clear alias registers are mapped to their base register bit (CSR→CR set, CCR→CR clear,
    AHB1ENSR/ENCR→AHB1ENR, AHB1RSTSR/RSTCR→AHB1RSTR).
- **Seeded mismatch kinds (SC-002)**: wrong mask, missing function, extra function, wrong register, unrelated bit
  overwritten (plain `=` on a shared register). Each maps to exactly one finding kind and is tested on fixture
  copies of the r170 LL header.

## R7. Defects against delivered code

- **Decision**:
  - **FROZEN:** CODE defects (failing tests, auto code defects, conformance contradictions) are filed with
    `target: owner`, status `ESCALATED`, and no rework loop. `gaps()` keeps the package BLOCKED until an owner
    disposition settles the defect. The existing owner-disposition mechanism is extended from INPUT to CODE
    findings.
  - **FIX_ALLOWED:** the existing CODE → SWE.3 loop (`inspection/defects.py:24`).
  - **Both modes:** TEST defects are unchanged.
- **Rationale**: in FROZEN mode the fix author cannot change code, so a rework loop would end in a false REJECT
  (`inspection/defects.py:211`).

## R8. Checklists

- **Decision**: add `factory/checklists/v0.4-brownfield/` (owner-decision commit; protected path), a copy of the
  v0.4 checklists with SWE.3 items remapped:
  - SWE3-07 guideline: applicable only when the delivery declares the factory guideline;
  - SWE3-08 regmap: becomes "register definitions checked against the RM" (check mode only);
  - SWE3-09 implementation: becomes "scope functions exist, fingerprints match";
  - SWE3-10 trace: becomes the trace map check.

  The engine selects the version from the manifest.
- **Rationale**: required items cannot be marked not applicable (`inspection/engine.py:268`). Greenfield
  checklists must stay byte-identical.

## R9. Build and test environment for delivered code

- **Decision**: for factory-style deliveries (0008a/0008b), the existing build, test and simulator tools work
  unchanged, because the code uses the factory's own conventions. For vendor (CMSIS) deliveries (pilot):
  - **Build inputs:** the manifest supplies the defines (e.g. `STM32N657xx`, `USE_HAL_DRIVER`,
    `CPU_IN_SECURE_STATE`) and the include order, from fingerprinted dependency headers. They are never chosen by
    an agent.
  - **Compiler flags:** a brownfield build profile records compiler warnings as findings instead of failing the
    build (`-Werror` is removed for delivered files only).
  - **Host tests:** a generated host shim that includes the device header, then redefines `RCC` to a RAM
    `RCC_TypeDef`, plus a `HAL_GetTick` stub.
  - **Renode RCC model:** the window is extended to 8 KB, and CSR/CCR and AHB1ENSR/ENCR/RSTSR/RSTCR set/clear
    semantics are added.
  - **Robot policy:** accepts `RCC_<REG>_<FIELD>(_Msk)` tokens.
  - **Register scanner:** CMSIS writes, as in R6.
- **Rationale**: ST code uses CMSIS struct access, `HAL_GetTick` timeouts and set/clear registers (pilot survey
  §1–§4). The current tools assume `ll_rcc_regs` and `LL_RCC_*` macros (gate survey §2–§3).
- **Pilot base address**: secure build (`CPU_IN_SECURE_STATE`) → `RCC_S` = 0x56028000, which matches the RM memory
  map used by the factory and the simulator window.

## R10. Pilot scope (ST v1.4.0)

- **Decision**: FROZEN, LL layer scope of 11 functions:
  - `LL_RCC_HSI_Enable/Disable/IsReady` and `LL_RCC_HSE_Enable/Disable/IsReady` (`stm32n6xx_ll_rcc.h:1781-1842`);
  - `LL_AHB1_GRP1_EnableClock/DisableClock/IsEnabledClock/ForceReset/ReleaseReset` (`stm32n6xx_ll_bus.h:869-942`).

  Applied to the GPDMA1 and ADC12 masks, these cover the same 16 behaviours as the factory's LL scope.
- **Excluded:** every other function in the two headers is listed by name. The HAL `HAL_RCC_OscConfig` is out of
  the first pilot.
- **Dependencies:**
  - `cmsis-device-n6` v1.4.0 (`stm32n6xx.h`, `stm32n657xx.h`, `system_stm32n6xx.h`);
  - CMSIS 6 core (`core_cm55.h`, `cmsis_compiler.h`, `cmsis_gcc.h` and the headers they include);
  - `stm32n6xx_hal_conf.h` from the template, with only the RCC module enabled, plus `stm32_assert.h` from the
    template.

  All are fingerprinted, with their licences recorded. The configuration is a declared, owner-visible input.
- **Known points for independent verification** (from the survey; to be confirmed by the run, not assumed):
  - `__HAL_RCC_AHB1_RELEASE_RESET` writes 0 to a set register;
  - the HSE 2 ms wait has no timeout;
  - the in-use check is partial.

## R11. Safety drafts (US5)

- **Decision**: a brownfield `safety_draft` author node after SWE.6. It runs on the existing inspector-independent
  author model and writes `safety/drafts/software_safety_analysis.md` and `safety/drafts/tool_assurance_assessment.md`.
  - Each draft carries the draft marker, the delivered fingerprints and the scope.
  - A deterministic gate checks the marker, the absence of compliance claims and ASIL consistency
    (`assurance/scope.py claim_text_findings`), and that the drafts are kept apart from the signed paths.
  - The signed document register is unchanged.
- **Rationale**: it reuses the existing signing process (OD-2026-10-19-11). Drafts never enter the signed paths, so
  they can never unblock a package.

## R12. Validation deliveries

- **Decision**:
  - **0008a:** the r170 LL header and compile unit as the delivery (FROZEN; origin: the factory's own work order
    r170 archive; licence: project licence).
  - **0008b:** the r164 HAL `.c/.h` with one seeded defect (the oscillator rollback turns off an already-running
    oscillator) in FIX_ALLOWED mode, on the provided LL.
  - **Seeded mismatch fixtures** for SC-002 live in the test suite, not as examples.
- **Rationale**: the owner asked to test both modes on the factory's own RCC code. Both are already known to pass
  their greenfield gates, so any new failure points at the brownfield machinery.
