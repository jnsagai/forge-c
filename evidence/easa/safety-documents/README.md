# RCC ASIL B safety documents: change record (OD-2026-10-19-11)

| Step | Commit | Content |
|---|---|---|
| Owner decision | f4b48c0 | AI drafts SSA-RCC-001 and TAA-RCC-001 (`config/factory/safety-documents/SC-RCC-2026-10-18/`), registered **unsigned** under `safety_documents` in `config/factory/safety-scope.yaml`; decision record `evidence/easa/owner-decisions/OD-2026-10-19-11-safety-documents.json` |
| Factory change | 9d5995e | Only owner-signed documents enter RCC work orders (read-only) and packages |

## CRE CHANGE promotion

| Iteration | Baseline | Candidate | Decision | Result |
|---|---|---|---|---|
| 1 | main 8b275fc | 28f6fcf (drafts, register and code in one candidate) | `pd-ba00ad41bfcabb980f1f` | **REJECTED**: `protected_files` FAIL. `config/factory/*safety*` is protected; a factory change must not write it. |
| 2 | 81c55a3 = main 8b275fc + owner decision f4b48c0 | 833d26d = baseline + factory change 9d5995e | `pd-da9d33bff3b882441b02` | **ELIGIBLE_FOR_OFFLINE_REVIEW**: all hard gates PASS |

Cause of iteration 1: the protected safety files (owner content) and the factory code were committed together. The
branch was rebuilt with the owner decision first and the factory change on top; the final tree is identical. The
gate's protected-path rule was not changed.

## Signing status

Both documents are unsigned. RCC packages stay BLOCKED on them until the owner signs (see
`config/factory/safety-documents/README.md`).
