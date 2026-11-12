# Claude implementation handoff — Feature 017

## First implementation request

Implement **M0–M1 only** from `specs/017-swe1-output-first/tasks.md`: establish trustworthy SWE.1 telemetry, fix deterministic destructive-repair defects, verify the models actually deployed on Omniverse, and compare author thinking-off (or genuinely supported bounded thinking) against the current baseline. The requested product is requirements and concise findings, not reasoning narratives.

Read repository instructions and `.specify/memory/constitution.md`, then this feature's README, spec, plan, data model, validation protocol, tasks and research notes. The old root CLAUDE.md references historical implementation tasks; this explicit feature request selects feature 017 while retaining its applicable guardrails. Do not regenerate these authored documents with generic templates.

## Working instructions

1. Inspect the current checkout and runtime before editing. This documentation branch is based on older remote main; it is not an instruction to downgrade or reset the active Omniverse implementation. Use an isolated worktree of the correct integration base and bring over this feature directory when needed. Record the source revision and existing functionality reused.
2. Treat current author and inspector names, digests, quantization, template, backend, gateway and routing as discovery results. Historical mentions of Ornith and Qwen are not proof of installed controls. Model support is not workload qualification.
3. Keep runtime local-only, SWE.1-only and ASPICE-only for this experiment. Preserve baseline profiles and existing production services. Do not enable SafeC or safety-assurance scope implicitly. Do not modify frozen delivered code.
4. Implement ledger/replay safeguards before using performance numbers for decisions. Fix unambiguous identifier normalization and reject repair coverage regressions. Retain every attempt and unknown measurement honestly.
5. Probe thinking and token controls through the real gateway. Never substitute hiding reasoning for disabling generation. Do not persist chain-of-thought. Use effective settings, hashes, numeric usage and transient event classification for evidence.
6. Keep inspector behavior unchanged during the first author experiment. Use fixed tasks, frozen expected properties, repetitions and a held-out case. Count retries and loading/queue costs. Do not claim success from JSON validity alone.
7. Follow the repository's versioned skills, production MCP boundaries, protected policies and evidence rules. Factory implementation shell use does not authorize production agents to bypass MCP.
8. Run focused tests and required design/legacy checks. Check off tasks only with evidence. Without host access, implement and test the harness/replays, report NATIVE_NOT_RUN, and leave native tasks incomplete. Never invent a successful Omniverse run.
9. Stop after the M0–M1 report. State the tested model identities, whether controls were honored, semantic results, token/time changes, retained or candidate settings and next milestone. Do not enable both roles' thinking-off mode, promote a production profile, launch an unattended long campaign, or implement later SWE phases as part of this slice.

## Completion report format

- Commit/branch and implementation base.
- Tasks completed with command/evidence references.
- Deployed identities and verified/unsupported/unverified controls.
- Baseline versus candidate correctness, coverage, generated tokens and full task time.
- Regressions fixed; unresolved/NOT_RUN work.
- Recommended next action: retain baseline, continue capability investigation, or implement M2.

## Subsequent implementation request

After M0–M1 evidence is reviewed, continue with M2, then M3 and M4 in order. The target is the generic output-first architecture described here, not a GPIO-specific patch collection. Extend existing contracts/renderers before creating parallel mechanisms. No additional feature scope is implied by completing a milestone.
