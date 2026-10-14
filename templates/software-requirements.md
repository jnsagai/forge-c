# SWE.1 — Software Requirements Specification

Document ID: SRS-<driver>-<revision>  
Status: DRAFT / REVIEWED / APPROVED  
Upstream system requirement baseline: <ID + digest>  
Safety allocation: <ASIL or QM, rationale>  
HSI/manual/errata: <exact revision + hash>  
Owner / approver: <identity and date>

For each requirement:
- ID, requirement text (atomic, verifiable, unambiguous), type (functional/quality/safety), ASIL, source and safety goal/TSR link.
- Trigger/mode, preconditions, guaranteed response, error handling, timing/memory bound, verification method, acceptance criteria.
- Constraint or assumption with provenance, owner and resolution status.

Add: requirements impact analysis, interactions/operating context, open questions, bidirectional consistency summary and communication/review record.

## Requirement syntax — EARS (mandatory, checklist SWE1-07)

Write each requirement as one EARS statement with exactly one `shall`, naming the specified system:

| Pattern | Template |
|---|---|
| Ubiquitous | `The <system> shall <response>.` |
| State-driven | `While <state>, the <system> shall <response>.` |
| Event-driven | `When <trigger>, the <system> shall <response>.` |
| Optional feature | `Where <feature is included>, the <system> shall <response>.` |
| Unwanted behaviour | `If <condition>, then the <system> shall <response>.` |
| Complex | `[Where …,] [While …,] When …, / If …, then the <system> shall <response>.` |

Machine-readable form (one per line): `- **SWR-001** When the PLL lock flag is not set within 100 us, the RCC driver shall return FORGE_RCC_TIMEOUT.`
Avoid weak modals (should/may/will/must) and vague terms (fast, efficient, as appropriate, TBD).
