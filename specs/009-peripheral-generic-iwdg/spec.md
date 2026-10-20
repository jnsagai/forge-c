# Feature Specification: Peripheral-generic factory (IWDG pilot)

**Feature Branch**: `feat/009-peripheral-generic-iwdg`

**Created**: 2026-10-20

**Status**: Draft

**Input**:
- Owner, 2026-10-20: "if you are done with this mission before the 8h, choose by yourself another driver to implement".
- Pending reuse task T-019 of feature 001: "Port to watchdog/GPIO/other driver -> reuse demonstration, no HSI assumptions leaked".

## Context

So far every Forge-C work order has produced the STM32N6 RCC driver. A survey of the factory (2026-10-20) found RCC
hard-coded in about 35 modules:
- file names and API prefixes (`stm32n6xx_ll_rcc.h`, `LL_RCC_`, `HAL_RCC_`, `ll_rcc_regs`);
- the reference-manual sections handed to SWE.1 (`14.10.1`, `14.10.2`, `14.10.79`, `14.10.64`);
- the simulator model (an RCC peripheral at 0x56028000);
- the register contract (set/clear bits with a ready flag only);
- the prompt examples.

The register-field parser also drops multi-bit fields such as `KEY[15:0]`, which RCC never needed.

The factory is meant to build drivers, not one driver. This feature makes the peripheral a parameter of the work
order and proves it with a second, small peripheral: the **independent watchdog (IWDG)**, RM0486 chapter 59 (pages
2979–2994). It has 7 registers, a single instance at 0x56004800 (secure) and multi-bit fields.

**Why IWDG rather than GPIO:**
- one instance at one base address, so the factory's "one register block per driver" design holds;
- a small chapter;
- it exercises exactly the missing capabilities: multi-bit fields, writing values (keys, prescaler, reload) and a
  status-flag wait.

GPIO has twelve ports, pin-indexed fields and depends on RCC, so it is a later step.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Peripheral identity comes from the work order (Priority: P1)

The owner writes a work order for a peripheral by naming, in the work order:
- the peripheral;
- its register prefix;
- its base address;
- its reference-manual sections.

The factory derives the file names, API prefixes, register-block name, component names and the sections each phase
reads from that description. RCC work orders behave exactly as before.

**Independent Test**: An IWDG work order prepares a workspace whose manifest, file names, prompts and checks name IWDG
everywhere and RCC nowhere. The existing RCC examples produce byte-identical workflows and checks.

### User Story 2 - Register descriptions with multi-bit fields and value writes (Priority: P1)

The register-map generator and its check read multi-bit fields (`Bits 15:0 KEY[15:0]`) from the RM. The register
contract can state "write value V to field F" (for example the IWDG key 0xCCCC), not only set/clear bits. The
independent oracle checks those writes.

**Independent Test**: The IWDG chapter yields all 7 registers with their fields (KEY, PR, RL, WINR, EWCR, SR flags), and
a contract case "write 0xAAAA to IWDG_KR.KEY" is checked by the oracle on a fixture driver.

### User Story 3 - IWDG simulator model (Priority: P2)

Target tests run against a behavioural IWDG model:
- key-protected access;
- reload;
- the update flags in IWDG_SR;
- the counter running down after the start key.

**Independent Test**: A Renode scenario starts the watchdog, refreshes it, and observes the expected flags.

### User Story 4 - A complete IWDG LL work order (Priority: P2)

A greenfield IWDG LL work order runs SWE.1–SWE.6 with Codex authors and Claude inspectors. It ends
READY_FOR_OFFLINE_REVIEW, or BLOCKED with every gap named.

**Independent Test**: The live run and its package.

## Requirements *(mandatory)*

- **FR-001**: The work order MUST name the peripheral, register prefix, base address (secure alias), RM chapter
  sections and API shape. The factory MUST derive every peripheral-specific name from them.
- **FR-002**: RCC work orders (0002a, 0002b, 0008a–c) MUST produce the same workflows, prompts, checks and packages as
  before.
- **FR-003**: The register parser MUST read single- and multi-bit fields. Reserved fields MUST be recorded as reserved.
- **FR-004**: The register contract MUST support a write-value operation, and the oracle MUST check it.
- **FR-005**: The simulator MUST select the peripheral model and base address from the work order.
- **FR-006**: Prompt examples MUST come from a per-peripheral profile, never from RCC text in an IWDG run.
- **FR-007**: No compliance, certification or safety approval may be claimed. An IWDG work order has no owner
  safety scope until the owner records one.

## Success Criteria *(mandatory)*

- **SC-001**: In an IWDG workspace, 0 occurrences of RCC-specific names in prompts, scaffolds or generated code.
- **SC-002**: All existing tests and the reliability benchmark pass unchanged.
- **SC-003**: All 7 IWDG registers and their fields are parsed from the converted chapter.
- **SC-004**: An IWDG LL live run reaches SWE.6, or blocks with named gaps.

## Assumptions

- The RM0486 PDF already on disk is the source. Chapter 59 is converted with the factory's `pdf2md` (verified
  2026-10-20: 7 register sections, fields as above). The memory-map line for IWDG is `0x56004800 - 0x56004BFF` secure.
- The first IWDG work order is LL only. A HAL work order follows the RCC pattern later.
- The datasheet input and guideline are reused.
