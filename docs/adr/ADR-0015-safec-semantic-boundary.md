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

## Addendum 2026-10-22 — owner decisions during implementation

These decisions were recorded by Claude Code. The authored decision above is unchanged.

1. **Adjudicated pass (decision 6, F011-FR-017/018).** Owner, 2026-10-22: "I accept ADJUDICATED_PASS rule". In
   `local-rtx-v2` the SWE.1 inspector returns typed claims, and fixed rules adjudicate them on the frozen baseline
   (`lrtx/review_semantic.py`). The rules decide whether the baseline:
   - states a pass criterion;
   - has exactly one 'shall';
   - has a startup requirement;
   - records the owner's upstream gap;
   - has the requirement in the trace tables;
   - has the budget requirements.

   A FAIL whose claims are all REFUTED gets one selective reinspection with the refutations. If its claims are
   still all refuted, the item is recorded as `ADJUDICATED_PASS`; the original verdict, every claim and every
   refutation are kept in the inspection record and the reply.

   Limits:
   - A claim the rules cannot decide (a judgement) stands and fails the item.
   - A genuinely missing mandatory ASIL input is never refuted.
   - The unchanged `check_inspection` operation and inspect gate judge the recorded verdicts.
   - The rule applies only to `local-rtx-v2`. The default, ACP and `local-rtx-v1` lines keep their inspectors.
2. **New local model families.** Owner, 2026-10-22: "you can download, but do it on loop10". Candidate inspector
   models are pulled only through the standalone loop10 Ollama, into the shared model store on the data volume.
   The v1/v2 stacks see that store read-only. A pulled model is NOT_QUALIFIED until F011-T029 measures it.
3. **Further candidates.** Owner, 2026-10-22: "If no local model qualifies as inspector try another candidate
   model" and "glm4:9b's licence isn't OSI ok no problem". phi4:14b (MIT), mistral-small3.2:24b (Apache-2.0) and
   granite3.3:8b (Apache-2.0) were pulled on loop10 and pinned by digest in `local-rtx-v2` as NOT_QUALIFIED
   candidates (366db72). glm4:9b's licence is accepted for evaluation and use.
4. **Finding: gpt-oss and the gateway's reasoning setting (decided, see 5).** The local gateway forces
   `reasoning_effort="none"` on every request and strips reasoning fields from responses (`llm_gateway.py`).
   gpt-oss:20b cannot switch its reasoning off: with `none` it returns empty content (measured, F011-T028C), so
   every inspection item failed to parse. FR-025 (spec 002) requires that AI trace storage exclude hidden reasoning;
   it does not forbid a model from reasoning. The gateway docstring states the stricter "forbids requesting". A
   per-model exception (send `low` to models that cannot disable reasoning, keep stripping before anything is
   stored) would meet FR-025 as written, but it changes the gateway's design and costs extra tokens. It is left to
   the owner; until then gpt-oss:20b is NOT_QUALIFIED (incompatible with the gateway setting) and was not evaluated
   further.
5. **Per-model reasoning exception (decision).** Owner, 2026-10-22: "I agree with A per-model exception in the
   gateway". A local profile may list models in `gateway.reasoning` with a fixed effort and extra output tokens.
   - The stack passes the policy to the gateway.
   - A listed model reasons at that effort, and the caller cannot raise it. Every other model stays at `none`.
   - The gateway still strips every reasoning field from plain and streamed answers before they reach the caller or
     the meter, so no hidden reasoning is stored (FR-025).
   - local-rtx-v2 and local-rtx-v2-omniverse2 list gpt-oss:20b at `low`, plus 4096 tokens. local-rtx-v1 and the
     default lines have no policy and are unchanged.
   - Implemented in 82c5fe8 (`pd-704dec78b9e1f85b1f92`). Whether reasoning improves inspection is still to be
     measured: the same holdouts, with reasoning on and off.
