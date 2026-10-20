# Software requirements

Scope: Header-only RCC LL register access for HSI, HSE, GPDMA1 and ADC12. Enable, disable, reset assert and reset release operations return no value. Ready and is-enabled queries return the specified unsigned Boolean value. Waiting, timeouts, parameter validation and error codes belong to the separate HAL work order.

The requirements specify logical register effects. The supplied RM0486 sections document set/clear aliases for the writable fields; host verification models those hardware effects on the register array. A field equal to 1 means that its single bit is set; a field equal to 0 means that its single bit is clear. SWR-003, SWR-006, SWR-009 and SWR-014 describe query return values, not register mutations.

- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.
  - Source: RM0486 p.480
  - Verification: Host register-array test: initialize HSION to both bit values; pass if HSI enable leaves HSION equal to 1.
- **SWR-002** When the HSI disable function is called, the RCC LL driver shall clear RCC_CR.HSION.
  - Source: RM0486 p.480
  - Verification: Host register-array test: initialize HSION to both bit values; pass if HSI disable leaves HSION equal to 0.
- **SWR-003** When the HSI ready query is called, the RCC LL driver shall return 1U when RCC_SR.HSIRDY equals 1 and 0U otherwise.
  - Source: RM0486 p.482
  - Verification: Host register-array test: vary HSIRDY and unrelated RCC_SR bits independently; pass if the return equals 1U for HSIRDY equal to 1 and 0U for HSIRDY equal to 0.
- **SWR-004** When the HSE enable function is called, the RCC LL driver shall set RCC_CR.HSEON.
  - Source: RM0486 p.480
  - Verification: Host register-array test: initialize HSEON to both bit values; pass if HSE enable leaves HSEON equal to 1.
- **SWR-005** When the HSE disable function is called, the RCC LL driver shall clear RCC_CR.HSEON.
  - Source: RM0486 p.480
  - Verification: Host register-array test: initialize HSEON to both bit values; pass if HSE disable leaves HSEON equal to 0.
- **SWR-006** When the HSE ready query is called, the RCC LL driver shall return 1U when RCC_SR.HSERDY equals 1 and 0U otherwise.
  - Source: RM0486 p.482
  - Verification: Host register-array test: vary HSERDY and unrelated RCC_SR bits independently; pass if the return equals 1U for HSERDY equal to 1 and 0U for HSERDY equal to 0.
- **SWR-007** When the GPDMA1 clock enable function is called, the RCC LL driver shall set RCC_AHB1ENR.GPDMA1EN.
  - Source: RM0486 p.575
  - Verification: Host register-array test: initialize GPDMA1EN to both bit values; pass if clock enable leaves GPDMA1EN equal to 1.
- **SWR-008** When the GPDMA1 clock disable function is called, the RCC LL driver shall clear RCC_AHB1ENR.GPDMA1EN.
  - Source: RM0486 p.575
  - Verification: Host register-array test: initialize GPDMA1EN to both bit values; pass if clock disable leaves GPDMA1EN equal to 0.
- **SWR-009** When the GPDMA1 clock is-enabled query is called, the RCC LL driver shall return 1U when RCC_AHB1ENR.GPDMA1EN equals 1 and 0U otherwise.
  - Source: RM0486 p.575
  - Verification: Host register-array test: vary GPDMA1EN and unrelated RCC_AHB1ENR bits independently; pass if the return equals 1U for GPDMA1EN equal to 1 and 0U for GPDMA1EN equal to 0.
- **SWR-010** When the GPDMA1 reset assert function is called, the RCC LL driver shall set RCC_AHB1RSTR.GPDMA1RST.
  - Source: RM0486 p.548
  - Verification: Host register-array test: initialize GPDMA1RST to both bit values; pass if reset assert leaves GPDMA1RST equal to 1.
- **SWR-011** When the GPDMA1 reset release function is called, the RCC LL driver shall clear RCC_AHB1RSTR.GPDMA1RST.
  - Source: RM0486 p.548
  - Verification: Host register-array test: initialize GPDMA1RST to both bit values; pass if reset release leaves GPDMA1RST equal to 0.
- **SWR-012** When the ADC12 clock enable function is called, the RCC LL driver shall set RCC_AHB1ENR.ADC12EN.
  - Source: RM0486 p.575
  - Verification: Host register-array test: initialize ADC12EN to both bit values; pass if clock enable leaves ADC12EN equal to 1.
- **SWR-013** When the ADC12 clock disable function is called, the RCC LL driver shall clear RCC_AHB1ENR.ADC12EN.
  - Source: RM0486 p.575
  - Verification: Host register-array test: initialize ADC12EN to both bit values; pass if clock disable leaves ADC12EN equal to 0.
- **SWR-014** When the ADC12 clock is-enabled query is called, the RCC LL driver shall return 1U when RCC_AHB1ENR.ADC12EN equals 1 and 0U otherwise.
  - Source: RM0486 p.575
  - Verification: Host register-array test: vary ADC12EN and unrelated RCC_AHB1ENR bits independently; pass if the return equals 1U for ADC12EN equal to 1 and 0U for ADC12EN equal to 0.
- **SWR-015** When the ADC12 reset assert function is called, the RCC LL driver shall set RCC_AHB1RSTR.ADC12RST.
  - Source: RM0486 p.548
  - Verification: Host register-array test: initialize ADC12RST to both bit values; pass if reset assert leaves ADC12RST equal to 1.
- **SWR-016** When the ADC12 reset release function is called, the RCC LL driver shall clear RCC_AHB1RSTR.ADC12RST.
  - Source: RM0486 p.548
  - Verification: Host register-array test: initialize ADC12RST to both bit values; pass if reset release leaves ADC12RST equal to 0.
- **SWR-017** When an HSI or HSE enable or disable function or a GPDMA1 or ADC12 clock enable or disable function or a GPDMA1 or ADC12 reset assert or release function is called, the RCC LL driver shall change only the named bit specified for that function in SWR-001, SWR-002, SWR-004, SWR-005, SWR-007, SWR-008, SWR-010, SWR-011, SWR-012, SWR-013, SWR-015 or SWR-016 and preserve every other bit of that register.
  - Source: RM0486 p.480; RM0486 p.575; RM0486 p.548
  - Verification: Host register-array test: for each write function and both initial values of its named bit, seed unrelated bits with zero, all ones and alternating patterns; pass if the resulting register equals the original value with only the specified field assigned its required bit value.
- **SWR-018** While no LL function has been called after reset, the RCC LL driver shall not write any RCC register.
  - Source: RM0486 p.479; RM0486 p.481; RM0486 p.575; RM0486 p.548
  - Verification: Host startup test: initialize the register array to reset values and run startup without invoking an LL function; pass if the complete array remains unchanged.
- **SWR-019** The RCC LL driver shall contribute at most 4096 bytes of flash to a target executable exercising all scoped functions.
  - Source: work-order budget (owner development target)
  - Verification: Target size-tool test: compare matched executables with and without the scoped driver exercise; pass if the additional flash is at most 4096 bytes.
- **SWR-020** The RCC LL driver shall allocate 0 bytes of static RAM for persistent driver state within the 64-byte static RAM budget.
  - Source: work-order budget (owner development target)
  - Verification: Target size-tool and symbol-map test: pass if driver-owned .data and .bss total 0 bytes, excluding the test register array, CMSIS hardware mapping and test harness.
- **SWR-021** The RCC LL driver shall require at most 128 bytes of stack for any scoped function call.
  - Source: work-order budget (owner development target)
  - Verification: Target stack-tool test: analyze stack usage of wrappers exercising every scoped function; pass if the maximum driver call stack requirement is at most 128 bytes.
- **SWR-022** When an HSI or HSE ready query or a GPDMA1 or ADC12 clock is-enabled query is called, the RCC LL driver shall leave every RCC register unchanged.
  - Source: RM0486 p.482; RM0486 p.575
  - Verification: Host register-array test: snapshot the entire array before each query with its flag equal to both bit values; pass if all register values are unchanged afterward.

## Open points

- Software safety allocation for ASIL B scope SC-RCC-2026-10-18 is pending owner allocation review; no software safety requirement is allocated yet.
- Target silicon revision is UNSPECIFIED in the manifest.
- The upstream package status is NOT_PROVIDED; its recorded issues identify an unapproved draft template and placeholders. No placeholder constitutes an approved allocation.
