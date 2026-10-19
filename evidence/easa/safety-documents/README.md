# RCC ASIL B safety documents: change record (OD-2026-10-19-11)

| Step | Commit | Content |
|---|---|---|
| Owner decision | f4b48c0 | AI drafts SSA-RCC-001 and TAA-RCC-001 (`config/factory/safety-documents/SC-RCC-2026-10-18/`), registered **unsigned** under `safety_documents` in `config/factory/safety-scope.yaml`; decision record `evidence/easa/owner-decisions/OD-2026-10-19-11-safety-documents.json` |
| Factory change | 9d5995e | Only owner-signed documents enter RCC work orders (read-only) and packages |
| Factory change | ed6903c | Tests independent of the committed signing state; the package limitation line names the signature decision |
| Owner decision | 7bb5878 | OD-2026-10-19-12: the owner signs both documents v1.0, approved with open findings ("I approve and sign all") |

## CRE CHANGE promotion

| Iteration | Baseline | Candidate | Decision | Result |
|---|---|---|---|---|
| 1 | main 8b275fc | 28f6fcf (drafts, register and code in one candidate) | `pd-ba00ad41bfcabb980f1f` | **REJECTED**: `protected_files` FAIL. `config/factory/*safety*` is protected; a factory change must not write it. |
| 2 | 81c55a3 = main 8b275fc + owner decision f4b48c0 | 833d26d = baseline + factory change 9d5995e | `pd-da9d33bff3b882441b02` | **ELIGIBLE_FOR_OFFLINE_REVIEW**: all hard gates PASS |
| 3 | a18716e = main 8b275fc + owner decisions f4b48c0 and 7bb5878 (signed documents) | 8242dd6 = baseline + factory changes 9d5995e and ed6903c (final tree) | `pd-b5c615c93aeb3bd2bd79` | **ELIGIBLE_FOR_OFFLINE_REVIEW**: all hard gates PASS |

Cause of iteration 1: the protected safety files (owner content) and the factory code were committed together. The
branch was rebuilt with the owner decision first and the factory change on top; the final tree is identical. The
gate's protected-path rule was not changed.

## Signing status

Both documents are signed by Jefferson Nascimento on 2026-10-19 (OD-2026-10-19-12), version 1.0, approved with open
findings:

| Document | SHA-256 |
|---|---|
| SSA-RCC-001 `software_safety_analysis.md` | `1795badc064854e0cd56ba8cc1dd0e8694c19e4d60cfc9edf38d982510c5407a` |
| TAA-RCC-001 `tool_assurance_assessment.md` | `38b778bd62aa1b3a1b247ea1f8784c285c6ade9512206f8167791a3fe965671c` |

Any edit to either file, or a change to the RCC work order inputs, un-signs it. The HSI and the allocation review
remain open ASIL B gaps in the observe-only assurance check.
