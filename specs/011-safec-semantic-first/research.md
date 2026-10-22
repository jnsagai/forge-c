# Research and existing-evidence ledger — Feature 011

**Date:** 2026-10-22. This document records repository evidence reviewed for the design; it is not a fresh live benchmark.

## Source revisions

- Forge-C `main` after PR #34: `2f4b9cf44fd9cc56648fa26b6da6c2e29248338d`.
- Feature 010 evidence: `evidence/v0.4/runs/LRTX-T024/README.md`, `LRTX-T021/README.md`, `LRTX-T023/README.md`, `LRTX-T016-SWE2/README.md`, `LRTX-TRIAL/README.md` and `specs/010-local-rtx-optimization/validation.md`.
- SafeC Forge private `main` observed: `556dca8df4d2fccd9cb59fd8fb0432aafdd05835` (record for discovery only; pinned executable identity must be verified at actual build). Public Forge-C must not mirror its source or private artifacts.
- Relevant Forge-C modules: `factory/python/forge_factory/lrtx/swe1.py`, `structured.py`, `runner.py`; `factory/python/forge_factory/inspection/gate.py`; `config/factory/profiles/local-rtx-v1.yaml`; ADR-0013 and ADR-0014.

## Measured limitations

| Observation | Evidence | Architectural implication |
|---|---|---|
| LRTX-T024 stopped at 13/30, 0 READY; 8.41 h, 640 calls, 3.19M input tokens, 204 Wh GPU-board energy | T024 README | Never run full campaign until individual semantic and inspector gates pass |
| All 10 IWDG-LL workorders reach author freeze but independent local inspector blocks; false clean holdouts 2/2 | T024, T021 | Replace blanket inspection with source-grounded, targeted checks and qualified inspector |
| 3 RCC-LL workorders repeat mask-as-field-value and unknown symbol | T024 | Move field encoding, exact symbol lookup and mask generation to trusted typed semantics |
| Qwen3 8B 0/3 and coder 30B 3/3 SWE.1 author freezes, 8B needs more repairs | T023 | No blanket routing to smaller local model |
| On frozen SWE.1 baseline Qwen SWE.2 freezes 1/3 after an actionable finding fix | T016-SWE2 | Contract-driven interface ID binding and separate SWE.2 pilot |
| INS rephrases refuted findings, occasionally changes same-baseline verdict between visits | LRTX-TRIAL | Evidence-based claim identity/adjudication and measurable inspector qualification |
| `step_route` computes progress extension after `store.gate` decision | gate.py, LRTX-TRIAL | Independent shared-route fix/CRE review, never loosen gates as a v2 side effect |

## SafeC Forge existing abilities and scope boundary

- Rust core gives strict source/domain parsing, canonical trace/provenance and a validated CSRI **for a sampled-latch wheel-speed profile**, not a universal language for MCU peripherals.
- Existing Kind 2 property analysis and generated Lustre are limited to supported sampled temporal requirements. They must not be invoked as general RCC/IWDG proof without new formalization.
- Existing `safec-contracts` emits C11/ACSL obligations for a concrete Wheel interface; extensions for arbitrary HAL/LL register operations need separate semantics/ABI assumptions.
- Existing candidate verification provides compiler/Frama-C/CBMC/test/coverage adapters, disposable QEMU guest and evidence integrity, but exact Linux toolchain, licensing, and safe isolation must be reprobed.
- Existing `safec-testgen` derives 26 test goals for sampled-latch profile without reading candidate implementation. Reuse the architecture, **not its numeric/temporal oracle** for register operations.
- SafeC MVP retained Wheel result: 25 histories, 28/28 statements, 22/22 branches on the prepared environment; seven intentional candidate defects fail. This is not an RCC/IWDG or generic code correctness result.
- SafeC partial 20-rule Safe C profile currently exercises five rules; 15 remain unsupported. No full MISRA, tool qualification, silicon timing or product acceptance claim.

## Open technical risks to resolve with experiments

1. **Linux portability and trust boundary:** Rust core likely portable but specific Frama-C/CBMC/Kind 2, QEMU images and tooling have environment constraints. Require reproducible Linux smoke and adversarial tests, do not reuse Windows conclusions.
2. **Source provenance:** RM0486 converted text and errata need authoritative section/page/digest mapping; parser ambiguity may hide hardware semantics and must be explicit UNSUPPORTED.
3. **Completeness:** a correct register intent contract is not evidence that all system/safety requirements were elicited. Keep full scope inventory, independent checklists, upstream allocation and owner authority.
4. **Inspector quality:** a different family does not prove independence; systematic common-cause errors remain. Blind holdout tests are mandatory.
5. **Private/public boundary:** the SafeC repository is private and Forge-C is public. Contracts and anonymized/approved metrics may cross; do not copy proprietary sources, internal logs, secrets or private excerpts.
6. **Licenses/tool confidence:** re-check open-source/commercial licenses including Alt-Ergo when installing local formal tools. Tool output cannot self-qualify.
7. **Host resource pressure:** measure one model resident on 8 GB VRAM plus 32 GB RAM, cold load and switch time. No assumed extra memory or guaranteed performance.

## Design choices vs alternatives

- Chosen: Rust SafeC is a separately pinned deterministic helper; Forge-C is workflow gate authority. Rejected: merge repositories or let SafeC result alone authorize READY.
- Chosen: new `register-io-0.1` semantic profile; rejected: retrofit peripheral concepts silently into the current sampled-latch `0.1.0` CSRI.
- Chosen: closed statuses with evidence-backed hard failure; rejected: treating unsupported formal proof or missing owner decision as a nominal PASS.
- Chosen: staged offline trial; rejected: repeat T024 before independent semantic/inspection qualification.
- Chosen: Claude Code for feature implementation, local models for deployment; rejected: cloud runtime fallback under the local profile.
