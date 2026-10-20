# Proposal for owner decision: brownfield SWE.3 checklist (feature 008, research R8, task BF-T019)

**Status:** proposal only. `factory/checklists/**` is a protected path, so a new checklist version is added only by
an owner-decision commit. Nothing below is in effect.

## Why

Three required SWE.3 checklist items (v0.4) are decided by deterministic checks written for the factory's **own**
code style:
- the `ll_rcc_regs` register array;
- the `LL_RCC_<REG>_OFFSET/_MSK` defines;
- the Cube2 HAL guideline.

On a factory-style delivery (0008a, 0008b) they apply unchanged and pass. On a vendor delivery (the ST pilot 0008c,
CMSIS style) they fail by construction:

| Item | v0.4 criterion (short) | On ST STM32CubeN6 code |
|---|---|---|
| SWE3-07 | Generated HAL/LL code conforms to the ST Cube2 HAL SAD v1.2 rule subset | Classic Cube code follows a different convention (`HAL_StatusTypeDef`, `RCC_OscInitTypeDef`, `__HAL_` macros). Fails by design. |
| SWE3-08 | Every `LL_RCC_` register offset/bit/mask define matches RM0486 | ST has no such defines. Offsets come from `RCC_TypeDef` and masks from `RCC_<REG>_<FIELD>_Msk` in the vendor device header. |
| SWE3-09 | Every allocated `HAL_RCC_`/LL function is implemented (factory LL rules: static inline, `(void)`, register-block declaration) | The ST functions exist, but the factory LL rules (`ll_rcc_regs`, void signatures) do not hold. |

In FROZEN mode the SWE.3 author cannot change the code. A failed required item therefore loops through rework
until the budget is spent, and the work order blocks at SWE.3 without ever reaching the requirement-based tests
(SWE.4–SWE.6).

## Proposed change (new version `factory/checklists/v0.4-brownfield/`, v0.4 untouched)

1. **SWE3-07 (brownfield):**
   - The delivered code is checked against the guideline the work order declares for it. Forge-style deliveries
     still use the Cube2 subset.
   - For a vendor delivery with no factory guideline, every rule hit is recorded as a delivered-code finding
     (package gap, owner disposition). The item then judges whether the SWE.3 work products report those findings
     completely.
2. **SWE3-08 (brownfield):** the register definitions **the delivered code uses** are checked against the RM0486
   section files:
   - for forge style, the `LL_RCC_` defines (as today);
   - for CMSIS style, the `RCC_TypeDef` member offsets and the `RCC_<REG>_<FIELD>_Msk` masks of the vendor header,
     compiled as `_Static_assert(offsetof(...))` probes.

   A mismatch is a finding against the vendor input.
3. **SWE3-09 (brownfield):** every function the SWE.2 allocation names exists in the delivered code (any style), and
   the delivered fingerprints are unchanged, or changed only by a linked fix (FIX_ALLOWED).
4. SWE3-10 is unchanged (the trace map already replaces code tags).

The engine would select `v0.4-brownfield` only for manifests with a `delivery` block. Greenfield keeps v0.4.

## Also needed for the ST pilot to reach SWE.4–SWE.6

These are factory changes, not owner decisions, but they depend on the above being accepted:
- a host device shim (CMSIS `RCC` mapped to RAM, a `HAL_GetTick` stub) for unit and integration tests;
- Renode: a full 8 KB RCC window and CSR/CCR plus ENSR/ENCR/RSTSR/RSTCR set/clear semantics;
- Robot observation policy accepting `RCC_<REG>_<FIELD>` tokens.

## Decision requested

- Accept, change or reject items 1–3.
- If accepted: an owner-decision commit adds `v0.4-brownfield`, and the factory change (engine selection, CMSIS
  checks) goes through the CRE promotion gate as usual.
