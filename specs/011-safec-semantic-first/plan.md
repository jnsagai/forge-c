# Implementation Plan — Feature 011: SafeC semantic-first local Forge-C

**Branch:** `feat/011-safec-semantic-first` | **Date:** 2026-10-22 | **Status:** PLANNED / not implemented | **Spec:** `spec.md`

## Summary

Reuse the working Feature 010 isolation, admission, structured tasks, checkpoints and instrumentation. Introduce an opt-in `local-rtx-v2` profile that (a) constructs source-anchored register-domain contracts; (b) uses SafeC as a pinned deterministic semantics, contract/test and evidence provider; (c) limits local-model generation to bounded, source-backed decisions; (d) grounds independent inspection in explicit machine-checkable claims; (e) progresses through the unchanged Forge-C SWE gates in stages. Claude Code is the development engineer only, not a cloud runtime requirement.

## Technical context

| Area | Approach |
|---|---|
| Forge-C | Existing Python/Fabro 0.362, `factory/python/forge_factory/lrtx`, profile routing and inspector gates |
| SafeC | Separate private Rust workspace and pinned binary; existing CLI has wheel temporal profile, Frama-C/CBMC/Kind 2/guest/evidence components; extend with `register-io-0.1` only behind new API |
| Source of truth | Baselined RM0486/errata/owner scope for hardware; SafeC validated contract for modeled semantics; Forge-C existing safety and SWE policy for phase decisions |
| Host | Ubuntu/Linux on i9-14900HX, RTX 4070 Laptop 8 GB, 32 GB RAM; actual backends/versions to be probed |
| Local LLM | Keep `qwen3-coder:30b` as measured author comparator; evaluate `gpt-oss:20b` and GLM family for independent inspection and optional smaller task models only after exact local compatibility/quality evidence |
| Execution isolation | Existing `local-rtx-v1` network namespaces, single inflight, model store read-only, isolated profile root/ports; v2 has separate writable root and id |
| Bridge transport | Narrow local CLI invoked by deterministic orchestrator; versioned JSON file/stdio contract, timeout/cancellation, explicit evidence digests and closed exit semantics. A role-approved MCP wrapper is necessary if an AI agent calls a bridge tool |
| Output | Same SWE.1–SWE.6 workproducts and existing `READY_FOR_OFFLINE_REVIEW`/`BLOCKED` semantics; SafeC results are evidence inputs, never an independent release authority |
| Tests | pytest + current workflow graph/gate compatibility tests; SafeC cargo tests + Linux integration; seeded mutation tests and explicit live profile campaign |

## Constitution check (pre-implementation)

1. **Correctness and sources:** Never infer MCU register semantics or modify scope; unsupported information blocks its obligations. No false assurance claim.
2. **Evidence:** Every bridge call captures source/profile/binary hashes, inputs, statuses and audit trail; no stale or off-target result becomes PASS.
3. **Autonomy with external review:** Runtime may run unattended but only packages for offline review; Safety scope / ASIL ownership remains outside the agents.
4. **Separation:** Every author/inspector uses independent role/context; SafeC is a deterministic service, not an inspector-equivalent by itself.
5. **MCP:** An AI-accessed SafeC capability must be a narrow whitelisted MCP tool with explicit permissions; native backend invocation by deterministic gate is allowed under constitution.
6. **Supervisor:** Keep model-free health checking and bounded repairs; no self-modification of constitution, gate or normative rules.
7. **Observability and cost:** Immutable audit retains tool results; no raw chain-of-thought/prompt logging; measure full success cost, not just token count per call.
8. **OSS/license and privacy:** No private SafeC code in public Forge-C; no mandatory proprietary binary/API; pin licenses and check commercial suitability prior to productization.

## Workstreams / dependency graph

| Milestone | Changes | Gate to proceed |
|---|---|---|
| M0 Baseline / feasibility | Record both repo SHAs, frozen default/v1 behavior, dependency/trust boundary, license inventory and probe SafeC on Linux with actual binaries | Compatibility and tool identity PASS; no changes to deployed host |
| M1 Contract bridge | Add `safec_bridge` adapter, subprocess envelope schema, status normalization, bounded execution, no-network/digest tests; SafeC implements compatible CLI endpoint behind private feature branch | All positive/negative/stale/error/timeout cases pass, no release-policy bridge |
| M2 Semantic domain | In SafeC define `register-io-0.1` and strict RM-backed register/field/access/operation grammar plus canonicalization/provenance and proof obligations; dual-branch coordinated PRs | RCC/IWDG semantic goldens including adversarial mutations PASS/FAIL correctly; unsupported fails closed |
| M3 SWE.1 author | Map structured outputs to validated semantic intent, deterministically render effects/EARS/trace while retaining existing `swe1.py` gate and completeness checks | 3 independent IWDG and 3 RCC SWE.1 author freezes and no invalid semantic operations |
| M4 Inspector | Atomic evidence claims and independent inspector model/role qualification on clean and seeded holdouts; fact/rule adjudication and bounded targeted repair | All critical seeded on-target detections, 0 known clean false rejects, no missing safety evidence obscured |
| M5 SWE.2 and downstream | Bind exact interface identifiers/allocations, then contract-driven C/tests/verification through SWE.3–SWE.6 with no unmodeled proof claims | 3 isolated SWE.2 author+inspection passes each; later each phase individually verified |
| M6 Campaign and packaging | Run gated qualification with frozen unseen cases, resource accounting, signed-off human review of deltas and rollback drill | 30-case target measured truthfully, artifact bundle offline review only |
| Separate shared bugfix | Shared `inspection/gate.py` progress-extension issue requires an independent CRE candidate/PR, testing both ACP and local modes; **not** a silent change in M1..M5 | Existing max budget/stuck policy invariant + regression PASS |

## Architecture boundary

```text
  Workorder / owner scope / hashed RM + errata
                    |
       Forge-C source inventory + selector
                    | validated limited intent (local LLM)
     Forge-C typed SafeCBridgeRequest ───────────────┐
                    |                                |
       pinned offline SafeC binary (Rust)      tool/model manifest
          register-io-0.1 semantics                   |
                    | validated contract+evidence    |
          Forge-C deterministic assembler <──────────┘
                    |
    unchanged SWE.n author gate -> independent evidence-backed inspector
                    |
          unchanged rework routing / finalizer
                    |
     READY_FOR_OFFLINE_REVIEW or BLOCKED package
```

SafeC is the authority only for the **precise modeled semantic contracts**. Forge-C remains the authority for workflow progress, applicability, mandatory inputs, phase evidence and offline packaging. Identity bindings ensure that two engines never quietly disagree on the same obligation: explicit mismatch is `BLOCKED` with both decisions preserved.

## Source/project changes (proposed; not yet present)

```text
Forge-C (public):
  specs/011-safec-semantic-first/{spec,plan,research,data-model,quickstart,tasks,validation}.md
  specs/011-safec-semantic-first/contracts/{bridge-request,bridge-result}.schema.json
  factory/python/forge_factory/safec_bridge/{client,contracts,adapter,provenance}.py
  factory/python/forge_factory/lrtx/{swe1,swe2,runner,profile,structured}.py  [localized changes]
  config/factory/profiles/local-rtx-v2.yaml [new; explicit selection]
  factory/python/tests/test_safec_bridge*.py
  factory/python/tests/test_lrtx_v2*.py
  docs/adr/ADR-0015-safec-semantic-boundary.md

SafeC Forge (private, separate feature branch/PR):
  crates/safec-register-io/{src,tests}/... [new crate or equivalent reviewed module]
  crates/safec-cli/src/main.rs [new explicit command/interface]
  schemas/register-io-0.1.schema.json [new only]
  crates/safec-contracts/... [new lowering only when semantics are established]
  crates/safec-testgen/... [new oracle profile only after an independent reference model exists]
```

The proposed path in SafeC is a design target, not a claim it already exists. Do not modify wheel sample-domain logic or its backward-compatible schema in place. Validate the exact repo structure when implementing.

## Cross-repository change protocol

1. Treat the SafeC private repo as a separate product. Create its own feature branch from pinned main; never import private files, test data, build logs with secrets, or full evidence into the public Forge-C PR.
2. Deliver compatible **schema fixtures first**, with version negotiation and explicit `UNSUPPORTED` handling. CI may use local stubs for publicly testable adapter behavior; real integration requires approved private binary and a verified digest, not mocked semantic claims.
3. Pin an exact SafeC commit and binary sha256, platform/toolchain manifest, profile/schema version and source digest for each real run. Refuse upgrades automatically until replay fixtures have passed.
4. Preserve verified raw SafeC evidence under the local profile root; Forge-C records a minimally sufficient public-safe summary and cross-hashes without publishing confidential contents.
5. Only promote the coordinated Forge-C and SafeC changes after each repository passes its own full regression, plus the cross-repo compatibility suite.

## Model/inspection experiments

- Reuse fixed LRTX-T021 clean and mutant corpus as diagnostic baseline, not a training set. Freeze additional **unseen** cases and hashes before the model comparison, with author outputs and inspector judgements isolated.
- Candidate inspector families: start with a distinct local family to test independence, measure actual Q4/other permitted quantization, VRAM/RAM use, cold load, swapping, context window, token decoding speed, cost to inspect correctly; never presume fit/quality based on parameter count alone.
- Reject an inspector if it produces vague ungrounded claims, rephrased disproven allegations, misses injected critical defects or falsely rejects clean baselines. No auto-switch on failure; preserve evidence, remain BLOCKED.
- Avoid per-token/per-call optimization until the complete cost per **accepted workorder** is measured. Keep the existing `max_inflight=1`, profile isolation and full prompts criteria initially.

## Staged validation, rollback and constraints

- Before any live workorder: exact source/binary/hash check, `scripts/lrtx_compat_check.sh`, existing pytest/design fixtures, SafeC Rust unit tests (on its own branch), JSON-schema conformance, synthetic negative cases and network-denial check.
- After each milestone preserve ALL failed and corrected attempts; record reproducible commands, digest, analyzer versions, device energy scope and uncovered proof obligations.
- Never change `config/factory/safety-scope.yaml`, inspection checklist thresholds, approved policy, generated source manuals, tests/oracles or historical receipts just to achieve READY. No unreviewed shared gate change.
- Rollback: explicit profile deselection. Stop v2 services only; leave v1 and Claude/Codex untouched. Remove only v2 owned writable paths after verifying archives are backed up; SafeC separate checkout/repository remains recoverable by commit.
- Runtime may stay BLOCKED for missing HSI/safety allocation or unsupported formal backend. That is correct behavior, not feature failure to be papered over.
