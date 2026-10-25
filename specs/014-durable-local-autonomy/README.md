# Feature 014 — Durable local autonomy and recovery

Spec Kit package for **Codex implementation**, following the October 24–25 Omniverse2 recovery failures and the owner's explicit requirement to design for local Qwen limitations.

**Branch:** `feat/014-durable-local-autonomy`  
**Base:** PR [#41](https://github.com/jnsagai/forge-c/pull/41), `fix/013-local-autonomous-recovery` at `f6ff873d5b4f3e9e46956ef26766181aaec2289d`. This is a stacked feature; `main` does not yet contain its required recovery implementation.  
**Status:** specification and contract fixtures only. Runtime implementation, local Qwen qualification, RCC success and operational soak are **NOT_RUN**.

Start with [codex-prompt.md](codex-prompt.md), then follow [quickstart.md](quickstart.md).

| Document | Purpose |
|---|---|
| [spec.md](spec.md) | Prioritized stories, 36 requirements, boundaries and success criteria |
| [local-model-design.md](local-model-design.md) | Role capability, task decomposition, context/memory, correlated errors and capability fallback |
| [plan.md](plan.md) | Existing modules, implementation order, persistence and compatibility |
| [tasks.md](tasks.md) | Unchecked implementation and qualification tasks |
| [acceptance-tests.md](acceptance-tests.md) | Deterministic/native/live acceptance scenarios and required evidence |
| [traceability.csv](traceability.csv) | Requirement → task → test links; planned status |
| [data-model.md](data-model.md) | Durable records, identities and invariants |
| [contracts/README.md](contracts/README.md) | Versioned proposed contracts and synthetic positive/negative fixtures |
| [research.md](research.md) | Decisions, alternatives and primary sources |
| [evidence-baseline.md](evidence-baseline.md) | Pinned history and unresolved native questions |
| [future-worker-promotion.md](future-worker-promotion.md) | Proposal only; no runtime permission or enabling bypass |
| [validation.md](validation.md) | Actual spec checks and explicitly unrun runtime milestones |

The first engineering milestone is complete evidence → bounded semantic proposal → durable receipt → one effective verified repair. A passing protocol, healthy service or blocked package does not independently prove product success.
