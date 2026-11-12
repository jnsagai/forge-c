# Upstream coverage

| Input | Status as stated in the manifest | Affected SWR IDs |
| --- | --- | --- |
| HSI contract | RM0486 Rev 4 ch.26 CRC register interface + memory map p.176 (CRC secure base 0x56024C00); upstream.status: NOT_PROVIDED | SWR-001, SWR-002, SWR-003, SWR-004 |
| Safety allocation | OUT_OF_SCOPE: QM development selected by the owner. No software safety requirements, allocated safety safe state or safety assurance are required. Functional requirements, startup/error behavior, resource constraints, traceability and verification remain required. | SWR-001 through SWR-009: no software safety requirement is allocated |
| Budgets | development targets set by the work-order owner (2026-10-15), reused for the feature 015 benchmark set (2026-10-25); flash_bytes: 4096; static_ram_bytes: 64; stack_bytes: 128; upstream.status: NOT_PROVIDED | SWR-005, SWR-006, SWR-007, SWR-008, SWR-009 |

No allocation is invented: missing approved upstream inputs remain open gaps.

## Upstream to software requirements

| Upstream ID | SWR IDs |
| --- | --- |
| RM0486-26.4 | SWR-001, SWR-002 |
| RM0486-26.3 | SWR-003, SWR-004 |
| WO-BUDGET | SWR-005, SWR-006, SWR-007 |
| WO-SIMULATION-PERFORMANCE | SWR-008, SWR-009 |

## Software requirements to upstream

| SWR ID | Upstream ID |
| --- | --- |
| SWR-001 | RM0486-26.4 |
| SWR-002 | RM0486-26.4 |
| SWR-003 | RM0486-26.3 |
| SWR-004 | RM0486-26.3 |
| SWR-005 | WO-BUDGET |
| SWR-006 | WO-BUDGET |
| SWR-007 | WO-BUDGET |
| SWR-008 | WO-SIMULATION-PERFORMANCE |
| SWR-009 | WO-SIMULATION-PERFORMANCE |
