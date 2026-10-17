# Claude Implementation Quickstart

1. Checkout `feat/006-enhanced-ai-software-assurance`. Confirm it is stacked on 005 and inspect divergent updates to 004 independently before merge.
2. Read `CLAUDE.md`, `.specify/memory/constitution.md`, `CLAUDE_FEATURE006_START.md`, `spec.md`, `research.md`, `plan.md`, `architecture.md`, `data-model.md`, `tasks.md`, `acceptance-tests.md` and `contracts/*`.
3. Validate **design only**: `python3 specs/006-enhanced-ai-software-assurance/validate_spec.py`; do not present that as runtime verification.
4. Audit current 001–005 implementation with actual version-pinned code and recorded evidence. Run `make factory-test`, `make design-check` where available and record commands/exits/digests.
5. Begin EASA-T001, implement in milestone order, add independent tests and record PASS/FAIL/BLOCKED/NOT_RUN with evidence. Do not overwrite existing Spec Kit source files by regenerating them.
6. Keep policy in OBSERVE_ONLY until owner-authorized pilot; preserve no SUP/MAN extension and don't reclassify QM as ASIL B.
7. For source r101/r102 retrospective, materialize local archive only if present, hash-verify first; missing contents yield honest NOT_VERIFIABLE, not invented findings.
8. End with a draft PR summary, evidence links and the limitations of any unverified ISO method matrix, tool assurance, Renode vs HIL and safety documentation.
