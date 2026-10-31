# Why functional delivery still has25strict release gaps

05:35UTC follow-up: [actual normal compile denials and inactive generic SDK fix](../mcp-default-tickets-50a4813d/README.md)
identify a factory argument-default ticket mismatch. Native03/05/06 each have
3normal compile callsBLOCKED/NO_AUTHORIZATION_TICKET; actual07hash reproduction
and failed-before MCP integration regressions bind the diagnosis. This helps
explain absent normal objects/stack outputs, without changing historical gaps,
claiming driver compile errors or retroactively supplying missing evidence.
Fix50a4813d is not activated during the frozen cohort.

Read-only triage of the retained native05 work products, gate failures and
source checks. No Qwen artifact validator or candidate C was rerun locally, and
no active cohort input/code/source was changed. Original findings stay intact.
This is diagnosis for later work, not a release waiver or new task completion.

The findings have different causes and should not be described as25independent
driver defects. Multiple release labels refer to the same underlying gate.

| Evidence | Supported classification | Consequence |
|---|---|---|
| SWE.2 STARTUP_NO_WRITE allocation failure | Author/schema mismatch: the architecture row says “all LL functions” without explicit function names, while api_calls names LL_CRC_Read_IDR. `oracle_gen.allocation` extracts explicit names per row. | Correcting an explicit allocation entry could address this metadata finding; it does not prove startup behavior or justify changing the gate toPASS. |
| REGMAP:NO_REGISTER_DEFINES / IMPL:LL_REG_BLOCK_DECLARATION_MISSING | Checker/declared-layout mismatch: legacy greenfield rules require generated offset defines and an extern volatile register array. The selected input contract instead requires the provided CRC_TypeDef pointer API and forbids singleton register objects. | A future declared target/API adapter must qualify the applicable structural checks. Adding fabricated array objects to this driver would contradict its contract. Existing failures remainGAPS. |
| CODE:UNDOCUMENTED_FUNCTION / SPEC_NOT_IMPLEMENTED | Actual missing strict unit/spec annotations in the frozen candidate, plus sequence friction: implementation is deliberately written before retrospective unit design. | A later quality pass needs stable predeclared unit IDs or an explicitly governed annotation update with preserved provenance/revalidation. The current source freeze is not bypassed. |
| UT:SPEC_NOT_VERIFIED:USPEC-LL-01-08..12 | Fine-grained unit-spec trace entries are absent, even though authored unit execution and the independent full-scope oracle passed. | Executable results do not supply missing trace links. Preserve the test rewrite and its mixed coverage; do not invent verification metadata. |
| IT:INTERFACE_NOT_VERIFIED:IF-03 | Authored target file declares @verifiesIF-01/IF-02, while the architecture also names IF-03. Register assertions exist, but the expected interface trace marker is missing. | Keep traceabilityGAPS separate from actual simulator results. No assertion that all interface trace evidence passed. |
| Missing normal software/src, software/build ELF/map patterns and resource check | Normal release-package evidence gap for this header-only slice. The separately archived independent target snapshot actually passed object/frame checks (16flash bytes/0static RAM/0max frame). | Do not call this an observed resource overflow; equally, do not use the independent object result to fabricate missing normal release artifacts or whole-program budgets. |
| run_not_completed:INCOMPLETE / QM_PIPELINE_DEMONSTRATION_ONLY | Existing strict release semantics and deliberate development-mode restriction. Native execution/all-six traversal and scoped function verification are separate. | Keep releaseBLOCKED regardless of functional M1. |

Source anchors: `inspection/implementation.py` retains the CAPA-019 array check;
`inspection/regmap.py` fails if no generated defines are found;
`inspection/gate.py` combines guideline, register-map and implementation verdicts.
The native message reported0guideline violations but the combined check failed
on the other two components. It should not be summarized as a measured C-style
violation count or as evidence of SafeC execution.

The missing explicit allocation names are an actual machine-readable artifact
issue, not evidence that the parser should infer an unbounded “all functions”
set. The incompatible array checks are a distinct adapter issue. Neither needs
another scheduler, model switch, memory store or global rule bypass.

Current decision: let the source-pinned three-run comparison finish unchanged.
The already prepared target-prompt correctiond0090099 also remains inactive.
Only after the required repeatability evidence should a later scoped change
measure these quality improvements with before/after controls. Full LL/HAL,
assessed ASPICE, production and24/7qualification remain open.
