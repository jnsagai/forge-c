# ADR-0010: Assurance profile is separate from product ASIL; QM scope; release and capability claims

Status: accepted (2026-10-17) · Feature: 006-enhanced-ai-software-assurance · Task: EASA-T005

## Context
Feature 006 adds stronger SWE.1–SWE.6 verification. There's a risk that a higher assurance profile gets read as a
higher safety integrity level, or that a factory PASS gets read as safety approval or a capability rating.

## Decision
1. **Two independent inputs.**
   - `ProductSafetyScope` holds `target_asil` QM/A/B/C/D. It comes from an approved external allocation
     (`product_asil_source`). A source that is a profile, an agent, generated text or an inference is rejected
     (`ASIL_SOURCE_NOT_APPROVED_ALLOCATION`).
   - `AssurancePolicy.profile` (STANDARD/ENHANCED/HIGH_ASSURANCE) selects evidence requirements only.
     `policy.effective()` copies the ASIL from the scope and never changes it.
   - Profiles are cumulative, so a higher profile can't skip a lower-profile requirement.
2. **ASIL scope (A–D).**
   - These are required: HSI, the allocation review, a software safety analysis and a tool assurance assessment.
   - If any is missing, the result is BLOCKED (`SAFETY_EVIDENCE_MISSING:*`).
   - N/A isn't permitted for these items.
3. **QM scope.**
   - The safety documents may be NOT_APPLICABLE only with a written rationale and a human approver.
   - Silent omission blocks (`QM_NA_WITHOUT_RATIONALE`).
   - QM output is never described as ASIL compliant. Generated text claiming an ASIL different from the scope, or
     ISO/ASPICE conformance, is rejected (`ASIL_MISMATCH_TEXT`, `FALSE_COMPLIANCE_TEXT`).
4. **Release semantics are unchanged.**
   - The existing finalizer still decides READY_FOR_OFFLINE_REVIEW or BLOCKED.
   - EASA adds evidence and can add blockers. It never produces ASIL_x_APPROVED, a certification or a safety
     sign-off (`safety_approval` is always null).
5. **No capability claims.**
   - The Automotive SPICE 4.0 SWE baseline is preserved.
   - No CL rating is produced or implied.
   - No SUP/MAN workflow is added. Existing support utilities are reused as libraries.
6. **Normative authority.** The bundled ISO 26262-6:2018 method list is a provisional secondary working index
   (`normative.py`, `catalog.py`). Without a registered licensed copy and per-table reviewer reconciliation, every
   normative or compliance assertion is rejected.

## Consequences
- A work order can run ENHANCED or HIGH_ASSURANCE checks at any ASIL, including QM, without its safety
  classification changing.
- The owner-deferred safety documents keep blocking ASIL-scoped packages. A QM scope needs an explicit, approved N/A.

## Verification
`factory/python/tests/test_easa_m1.py`: AT-010, AT-012, AT-078, AT-079, AT-083.
