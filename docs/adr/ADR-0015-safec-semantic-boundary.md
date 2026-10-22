# ADR-0015 — SafeC semantic boundary for local Forge-C v2

- **Date:** 2026-10-22
- **Status:** proposed for implementation under Feature 011; not a safety authorization or product-release decision.
- **Inputs:** merged Feature 010/PR #34 evidence; independently maintained private SafeC Forge Rust kernel at discovery revision `556dca8df4d2fccd9cb59fd8fb0432aafdd05835`.

## Decision

1. Keep **two independent products and repositories**. Forge-C owns ASPICE SWE workflow policy, local orchestration, inspection independence, bounded rework, finalizer and offline-review packaging. SafeC is a pinned **deterministic semantic and formal-evidence provider** only for source/profiles it can actually validate.
2. Keep the old Codex/Claude baseline and `local-rtx-v1` unchanged. Introduce opt-in `local-rtx-v2` with dedicated writable roots/ports and conservative version matching; not the default.
3. Supply a versioned JSON CLI bridge and, where called by an AI agent, a narrow permission-controlled MCP wrapper. Every result binds binary/tool/schema/model/source/workorder/policy identity, independent review claims, limits and raw evidence hashes. No shell access through agent MCP.
4. Extend SafeC with `register-io-0.1` without silently changing the current sampled-latch/CSRI semantics. Source-verified finite intents may include reads, sets/clears, exact field writes and modeled key sequences; unmodeled silicon behavior remains unsupported.
5. An LLM may propose source-fact-linked functional intent, never trustworthy bit positions, offsets, encodings, test expected values or approval state. Deterministic Rust produces those where supported; existing Forge-C produces final SWE-format artifacts.
6. Maintain author/inspector role and context independence. An inspector finding names exact source-backed evidence and a testable target; its dispute is recorded by an evidence-based deterministic process. No automatic weakening of checklist or scope to obtain READY.
7. `PASS` from a SafeC subcheck does not mean complete workorder PASS. `FAIL`, `INCONCLUSIVE`, `UNSUPPORTED`, `STALE`, `ERROR` or incomplete mandatory evidence continue to BLOCKED under unchanged Forge-C gates. `policy_satisfied` does not assert ISO/MISRA/ASIL approval.
8. Cloud/Claude is a **development workflow only**. The factory runtime is offline and operates without cloud APIs. New local model families require host and semantic-quality measurements before deployment.
9. No SafeC private source, implementation logs, licensed manuals, customer scope, access tokens or binary are mirrored in public Forge-C. Public schemas/interfaces are intentionally minimal and must be reviewed for disclosure.
10. The shared progress-extension defect in `inspection/gate.py` is handled in a separate controlled change through CRE/regression review; feature 011 cannot silently alter common safety gates.

## Trade-offs

| Alternative | Decision | Rationale |
|---|---|---|
| Use larger local model alone for author/inspector | Rejected as the primary fix | PR #34 shows both deterministic field misuse and systematic independent inspector failure; a bigger model has no correctness guarantee |
| Let SafeC accept workorders | Rejected | SafeC checks narrower semantics, and owner/ASPICE gates and offline approval remain in Forge-C |
| Merge repositories/vendor SafeC code | Rejected | Privacy, governance, independent versioning and reuse; public Forge-C/private SafeC separation |
| Convert old `.sreq` grammar into generic MCU semantics | Rejected | Changes validated sampled-latch meaning and risks silent migration |
| Pinned CLI with JSON envelopes | Selected first | Narrow testable authority boundary; MCP wrapper for actual production AI tools when needed |
| Full 30-case campaign immediately | Rejected | Prior attempt used 8.41 h with 0 READY; isolate and qualify semantics/inspection first |

## Consequences and checks

- More interfaces and source/evidence hashing; requires explicit Rust/Linux compatibility work.
- Real model and formal backend limitations remain visible; simulated/wheel coverage cannot count for IWDG/RCC.
- No backward-compatible workflow change without fixture comparison; protected policy changes need explicit owner and CRE review.
- Owner-facing metric is cost/quality per accepted package including failures, not a cheap individual token.
- Cross-reference: `specs/011-safec-semantic-first/{spec,plan,acceptance-tests,tasks}.md` and `specs/010-local-rtx-optimization/validation.md`.
