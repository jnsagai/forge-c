# Research and Decision Record — Feature 005

This document captures design decisions grounded in source inspection of the Forge-C Feature 004 head observed on 2026-10-17, `c03c0da9e771eddfdfb24b02d8ec336dfa847dfa`. Claude must refresh it to its actual target before implementing and log changes as ADRs.

| Decision | Evidence from existing repository | Conclusion |
|---|---|---|
| 005 owns *work order* lifecycle, not supervisor | `supervisor/service.py`, CRE `supervisor_hook.py`, `router.py` already independently poll and repair infrastructure | Single AFO Conductor + **reuse** 002/004 supervisor; distinct responsibility, no second infrastructure router |
| 005 uses existing Fabro | `fabro/client.py` pins observed 0.362 health/runs/events/status/cancel endpoints; `workorder.py` uses CLI `fabro run --detach --auto-approve` | Only use verified endpoints; CLI launch ambiguity needs correlation before retry; do not invent native resume API |
| 005 recovery plans need stage receipts | `workflow/builder.py` has six SWE loops with author/inspector gate and bounded rework; `--resume-from` reuses leading validated phases | Add cross-attempt checkpoints and plan admission; never retry arbitrary internal Fabro nodes as if idempotent |
| 005 cannot indiscriminately broaden infrastructure Repair Agent | `repair/infra.py` allowlist only `runtime/**`,`services/**`; CRE ADR-006 forbids auto source promotion | Distinct source Maintainer worker in candidate worktree with CRE-independent approval and no auto deploy |
| 005 must not simply enable CRE ACTIVE | `config/factory/reliability-policy.yaml` `mode: OBSERVE_ONLY`, `auto_promote_persistent_code: false`; `readiness.py` external signoff gate | Default AFO OBSERVE_ONLY; policy intersection; explicit owner authorization to progress modes; 005 cannot edit 004 policy |
| Tests distinguish packaging vs engineering success | `reliability/e2e.py` may mark verified *BLOCKED* archive as E2E PASS; `evidence/cre/e2e/...` records local Qwen blocked at SWE.1 | Implement separate `valid_terminal_package`, `all_gates_pass`, `ready_yield`, `promptless_recovery` metrics; no inflated green dashboard |
| 24/7 needs host service ownership | `scripts/forge_services.sh` launches components using nohup; only `forge-supervisor.service.in` managed | Systemd user services for stack with linger, mount dependencies and independent watchdogs; boot and logout drills |
| Scheduled intake is separate from CRE | `workorder.py` one-shot CLI; no 005 durable queue/dispatcher in inspected tree | Transactional queue + reconciliation + DLQ, submitted only on owner-approved manifest |
| CLI returns ambiguous result on crash | `workorder.launch_run` stores ID after subprocess returns; CRE wraps `workorder_launch:<wo>` in SideEffectJournal | Treat `PENDING` as uncertain; use unique attempt tag and Fabro listing/receipts to prevent duplicates; migrate keys deliberately |
| Existing evidence stores should not be forked | 002 incident WAL, 003 KPI engine, 004 CRE store/events | AFO DB for queue only; events/metrics plug into existing collector, incident/CAPA/lesson refs cross-linked |
| Automation cannot guarantee perfect engineering | Historical CRE attempt sample has zero confirmed READY packages and no statistically demonstrated reliability growth | Success claims require fixed work orders and homogeneous frozen cohorts, no arbitrary 100% reliability promises |

## Open design decisions for implementation audit

- Confirm how CLI `fabro run` labels appear in `FabroClient.list_runs` and whether list query supports robust attempt nonce. If not, extend side-channel receipt protocol in a safe, tested way or quarantine ambiguities; **do not assume server-native idempotency**.
- Confirm which existing author/inspector SKILLs can be reused for a scoped recovery plan; only add new roles when permission separation requires it.
- Confirm mount device/UUID and the service account/home; write a host-specific deployment report, not hardcoded personal paths.
- Confirm effective local-Qwen maximum context and token/turn limits: note `workorder.model_profile` may call local tokens `unlimited`; AFO must enforce finite cross-attempt limits.
- Confirm TLS/auth/CSRF approach for any human control API; default to loopback read-only endpoints.
- Confirm whether existing 004 promotion runner returns deterministic machine-readable `ELIGIBLE_FOR_OFFLINE_REVIEW` and how to link a draft PR without granting a maintainer agent direct GitHub credentials.

## Methodological references (design rationale, not certification)

- MAPE-K autonomic control: monitor/analysis/plan/execute using a shared audited knowledge base, with a deterministic non-AI control plane.
- Crash consistency and transactional outbox: model external side effects as at-least-once and reconcile receipts; no impossible exactly-once execution claim.
- CRE CAPA / Test–Analyze–and–Fix and SPC: reuse frozen reproducers and independent validation for long-term reliability improvements.
- systemd references for implementers: `systemd.service(5)`, `systemd.unit(5)` (`RequiresMountsFor=`), `systemd.exec(5)` credentials, `loginctl(1)` lingering; validate options against installed systemd rather than assuming availability.
- Existing normative governance: `.specify/memory/constitution.md`; `docs/adr/ADR-CRE-006-autonomous-recovery-scope.md`; approved Automotive SPICE project baseline and ISO 26262 offline review constraints.
