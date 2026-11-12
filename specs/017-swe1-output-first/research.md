# Evidence and integration notes

## Repository observations

The specification was prepared against remote main `f6d6e526b7cdde1f9766409362918c552cec0c88`. Feature 016 is already allocated on remote branches, so this proposal uses 017. The active runtime revision referenced by the operator's private diagnostic bundle was not retrievable through the connected repository at preparation time. The exact runtime profile was also unavailable there. This is a deployment/source synchronization question for M0, not proof that the runtime is missing or broken.

Existing main already contains structured SWE.1 calls, context accounting, capability probes, source hashing, a semantic-first SWE.1 implementation, deterministic rendering, review tools and model comparison helpers. Reuse and reconcile these before adding code. The existing semantic-first implementation is register-oriented and imports a SafeC bridge; reuse its separation of concerns without making that engine mandatory for this ASPICE-only feature.

The public `local-rtx-v2-omniverse2.yaml` on the inspected main is historical and names older candidates. It is not sufficient evidence of current author/inspector deployment. The operator's selected model pair and actual endpoint must be discovered locally.

## Motivation, generalized from private diagnostics

Observed failure categories motivating synthetic regressions: duplicated resource qualification misclassified as out-of-scope behavior; repair instructions deleting needed content; expensive full regeneration for grammatical corrections; empty outputs; repeated domain-policy findings across equivalent instances; incomplete task histories; apparently valid packets with missing behavior cases or unsupported contracts; and generation costs poorly controlled by the recorded request limit.

Do not publish the private archive, its vendor excerpts, full prompts, responses or identifiers as repository evidence. Build minimal synthetic fixtures that exercise these categories. Exact timings and token counts must be remeasured on the current stack for candidate comparisons; older summary totals were not reliable enough to serve as a promotion baseline.

## Public model-control references checked 2026-11-08

- Ornith template: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B/blob/main/chat_template.jinja — contains an `enable_thinking is false` generation branch. This is template-level support, not proof that the installed GGUF/backend honors it or retains SWE.1 quality.
- Qwen model documentation: https://huggingface.co/Qwen/Qwen3.8-27B — describes per-request thinking control. Discover whether this is actually the deployed inspector and pin the installed artifact.
- Ollama thinking: https://docs.ollama.com/capabilities/thinking — controls depend on model support and installed version.
- Ollama compatibility: https://docs.ollama.com/api/openai-compatibility — compatibility mappings are backend-specific; a generic API control is not a universal hard budget.
- llama.cpp server: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md — consult the installed revision's reasoning and generation controls rather than assuming current-main flags exist locally.

Pin model/template/runtime identities in native evidence; these web links can change. Hiding reasoning is not equivalent to suppressing its generation. A non-thinking switch does not remove all computation needed to answer; it aims to avoid an extended generated thinking sequence.

## Decisions

1. Local-only runtime; retain the deployed model pair initially.
2. First prove controls and author performance; hold the inspector fixed, then assess it separately.
3. Compact semantic output plus deterministic rendering/validation; no reasoning narratives in the deliverable or stored telemetry.
4. Generic operation/behavior contracts, with source-backed capability extensions rather than driver-name branching.
5. Stage-specific statuses and independent semantic review; schema success is not requirement acceptance.
6. Coverage planning, targeted atomic patches and bounded changed-strategy recovery.
7. Preserve frozen-code policy, source authority and existing release boundaries.
8. M0–M1 is the first implementation slice; later milestones are specified so the direction stays coherent without requiring a large rewrite upfront.
