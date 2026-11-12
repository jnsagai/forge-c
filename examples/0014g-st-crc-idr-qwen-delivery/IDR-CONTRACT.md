# CRC independent-data-register candidate contract

This is a new QM development candidate, not the frozen ST driver or a narrower
replacement for any historical RCC/CRC job. Qwen must create
software/ll/stm32n6xx_ll_crc.h from an initially absent candidate.

Implement exactly these header-only public C functions:

- void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)
- uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)

Use forge_crc_device.h, available in the immutable inputs directory, for the
source-backed CRC_TypeDef register layout. Do not redeclare the type or add
singleton register objects. The caller supplies a valid accessible instance.
Compile/test tools use the declared include directories. Host tests define
FORGE_HOST_DEVICE_IMPLEMENTATION before the first device include in exactly one
translation unit; CRC maps to a RAM fixture there. The generated SWE.4 harness
already provides this infrastructure, reset helper and insertion markers.
Write all32 supplied bits to its IDR. Read returns the independently stored
32-bit IDR value. Preserve every other register and other peripheral instances.
No startup accesses, status polling, allocation or setup occur in this scope.
Invalid pointers/inaccessible hardware and CRC polynomial/calculation/configuration
are outside this invocation domain.

Authority: RM0486 Rev4 section26.4.2 (CRC_IDR), p.1172; the declared CRC manual
and memory-map inputs. Device-layout fixture derives from pinned ST
cmsis-device-n6 v1.4.0 stm32n657xx.h, CRC_TypeDef. The original nine externally
reviewed requirements are supplied as a reference with their original review
metadata unchanged; that review is not a new review of this candidate or scope.

The independent predeclared host oracle checks boundary, alternating and every
walking bit pattern, independent reads, preservation and instance isolation.
The target probe checks both signatures compile for Cortex-M55. These checks
do not prove target execution, no-polling WCET or the reviewed simulation-only
64-instruction/100us-at100MIPS requirement. Those remain explicit unqualified
requirements until actual independently verified simulation evidence exists.
Host fixture success alone cannot establish the complete functional milestone.

Later SWE.1–6 documentation describes the actual chronology: implementation
precedes newly generated documentation. Do not invent prior approvals. Process
inspections remain real and advisory for traversal; strict release stays blocked.

