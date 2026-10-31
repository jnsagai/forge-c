# Shared fixes and diagnostic controls — 30 October 2026

**Update at18:33UTC:** cloud r4 is terminal BLOCKED atSWE.3/30gaps after
SWE.1/SWE.2 PASS, native transportSUCCEEDED. Qwen451038c4 remains RUNNING,
62valid author packets/637requirements plus four valid PASS inspection packets;
no complete phase/product verdict yet. The native QM Qwen graph atc221b65e has
31focused local passes but has NOT_STARTED. Earlier live snapshots below are
historical. Read the [three-day review](../../../specs/014-durable-local-autonomy/ASTRA-REVIEW-20261028-30.md)
and its dated snapshots for the reconciled cutoff and remaining issues.

The native Codex/Claude control exposed shared factory defects more quickly while Qwen continued on Omniverse. The same raw source inputs, product scope and blocking functional criteria were checked, but the native ACP workflow and Qwen structured-task workflow have different decomposition, prompts and call accounting. **This is a diagnostic control, not a model-only benchmark.** No complete LL/HAL success, learning benefit or 24/7 availability is claimed.

## Changes and exact evidence

| Revision | Change | Evidence |
|---|---|---|
| 9769911c | All-phase profile call capacity and ordinals above99 | Original failure retained: native517PASS/1FAIL; current-header cache compilation defect |
| 9029f939 | Correct current-header C revalidation and explicit hash-bound fresh author-task reuse | Local192PASS; native575PASS/one optional Doxygen skip |
| e50f3d16 | Explicit Codex-author/Claude-inspector ASPICE control without local-profile fallback | Local44PASS |
| 344b7051 | Preserve pinned LLVM/data-root/Python paths through native MCP gates | Local23PASS |
| 30ab4b02 | Complete owner scope in prospective native ASPICE prompts | Local38PASS |
| c1244ecd | Owner-selected simulation-only RCC allocations | Local106PASS; native638PASS/1FAIL/one Doxygen skip; preflight inventory regression retained |
| 451038c4 | Share actual section map with role preflight and resolve the legacy RCC default correctly | Local62PASS; native640PASS/one optional Doxygen skip |
| 76d79b46 | Explicit native author budget4096 and one counter start per ACP visit | Local56PASS |
| f5e07c9e | Developer-level compact Codex worker replies; strict parser remains | Local33PASS |
| 1089742d | Correct query instructions and select the declared manual instead of RM0486 | Local49PASS, including a synthetic different-manual positive/negative control |
| c221b65e | Native QM Qwen six-phase graph/profile, whole owner scope and query guidance | Focused31PASS; original broader six-failure development run retained; live trial NOT_STARTED |

Cohorts overlap; do not add their counts. Exact commands, versions, outcomes and source hashes are in the JUnit and native provenance files. Native qualification runs were CPU-only (4cores/8GiB/no swap), isolated with no network, GPU or owner/SSH credentials and zero model requests. The single native skip is test_at089_real_doxygen_run_and_undocumented_warning: Doxygen is not installed. It is not a passing Doxygen qualification.

The native c1244ecd failure is not suppressed: role preflight built its role graph with an empty section map and reported WORKFLOW_SCOPE_SECTION_MISSING ahead of the actual pending input-review finding. The corrected caller shares the prepared primary-source map with launch. Its positive and missing-section negative tests passed, followed by the full native641-case cohort.

The original 9769911c failure likewise remains available. The cached-code validator compiled a candidate alongside its already assembled definition, causing a duplicate-definition error. The correction replaces that one definition in a temporary copy of the current header. Real compiler checks cover unchanged reuse, a broken replacement, changed current defines and the inherited complete SWE.3 assembly/gate.

## Live Qwen and preserved history

Omniverse runs source451038c4776db8e52c248148848d0f734af8b70b under signed scope dd75c75a29f30aee6fd810ed15cb3603a0e23bad507280dcc2c47805c905c283. Profile local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector-capacity retains Qwen3.8-27B Q8/f16/MTP3/context262144, medium authors and xhigh inspectors, one admitted inference request and blocking ASPICE gates. Model role quality remains experimental.

Order afo-f2a638a42fadd518, native01M66YFFN0CJSFWVEMX0C89RHY, job afo-product-540644845473ac5b1f983d02 uses the same RCC mission and all historical expenditure/unknown usage. Owned PAUSED109→RUNNING110; deadline remains19:40UTC. No allowance was reset or time grant silently renewed. Business BLOCKED status did not release inference; old provider lifetime and native termination were reconciled first.

The first source upgrade reused40 VALID packets/428requirements. The simulation-contract continuation reused49 VALID packets/527requirements under complete input hashes and current schema/task validators, retaining original record hashes and usage. No inspector verdict or phase PASS was imported. See the two live-author-reuse-proof.json records.

**Progress correction:** the previous workspace had62 saved packet files, not62 successful outputs.49were VALID and13recorded CALL_FAILED after the external maintenance stop. These are not13 demonstrated Qwen content/diagnosis failures.

The two previous Qwen packages are sealed BLOCKED55/integrityPASS, with SHA256 c38f88ba8f88473a21b3b11327d629c22166ea99c9cc3dd22bdf58b112ebdba3 and ac66eef5928b28afd3000836a667c7347aab1443400b985a994f7fcc987d2e05. Both are copied and inventory-verified privately on loop10. This external source correction is not autonomous Qwen self-healing.

The explicit development allocation is64 executed target instructions and100microseconds virtual time per measured API call at100MIPS. It applies to declared instrumented simulation scenarios; unmeasured timeout paths and physical hardware WCET are not established. Independent measurement must cover every scoped function and fails for missing/incomplete/over-budget evidence. Functional timeout checks remain separate.

## Native controls

The first completed control, WO-F014-CC-20261030-LL-r2/native01M66VM7XZCBHSC10KDRZQF0A4, is product BLOCKED at SWE.1 despite native SUCCEEDED. Its two Claude inspections found missing target CPU/timing allocation; the final author visit also failed contract ownership validation. The original product archive has48gaps, SHA256 8b7cebd76a14169c85d1c5e1adb9efef49fe277a6114ca8ec9ffa0a8e7c02e0d.

The next control, r3/native01M66XB1DBHKBKW2MDJZTKHPD0, has its terminal proof in control-ll-r3-terminal-proof.json. It is BLOCKED49gaps, SHA256 53f99786b4a17d4f31dcdfba632d439e07642edc420a700973b38abe8d8195f1. Missing query no_write cases, prose replies and the inherited35-call limit are preserved as separate failures.

Current control WO-F014-CC-20261030-LL-r4/native01M66YMZK9JTMZCF2PNV4JRGCY runs frozen sourcef5e07c9e844b9ee09c391f50f74b2d30e4888246 through the existing local Fabro cloud instance. Codex gpt-6.1-sol/high authors and Claude claude-opus-5-5 inspectors use no Omniverse GPU. SWE.1 passed after one query-contract rework, and SWE.2 passed independent inspection. SWE.3 is in progress. That proves these gates for this control, not a complete product or Qwen capability.

Each HAL remains dependent on its own newly verified LL. The remote one-shot HAL tool additionally checks native success, released resources, sealed READY package/inventory, literal global section coverage and generated LL provenance. The local coordinator waits native termination and observed scoped-worker quiescence. No HAL was admitted from either failed LL.

## Traceability and limits

Formal Feature014 remains30/58; no additional DA task is closed by these increments. Specification, six schemas/38fixtures and14design checks pass **as static checks only**. Complete LL/HAL qualification, RCC recovery,30-product benchmark, learning benefit and24/72/168-hour campaigns remain unproven or unrun.

[Generic embedded C boundary](../../../specs/014-durable-local-autonomy/GENERIC-EMBEDDED-C.md) records the owner's scope and the remaining LL/HAL/target assumptions. Synthetic MANUAL42 tests are not another-device qualification.

The Codex reply setting uses the documented developer_instructions configuration key: [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). The strict output parser still rejects prose and invalid/routing fields; developer instructions are not correctness evidence.
