# Feature 005 — Production Operations and Readiness Protocol

Status: proposed measurable plan. Neither prior CRE fault injections nor the creation of Feature 005 documents demonstrates a 24/7 SLO.

## Operating modes and authority

| AFO mode | Queue | SWE replan | Service actions | Factory-source proposals | Approval |
|---|---|---|---|---|---|
| DISABLED | paused; no admissions | none | existing 002 only | none | safe default |
| OBSERVE_ONLY | simulate scheduling and counters | observe recommendations only | existing 002/004 unchanged | none | safe onboarding |
| PILOT | authorized test manifests, capacity 1 | approved bounded scoped workproduct repair | 004 policy intersection, no blanket action | candidate + review only if separately authorized | signed pilot envelope |
| ACTIVE | authorized approved production-class work orders | bounded scoped repair/strategy variation | only explicitly authorized reversible actions, governed by CRE | staged PR review, no deploy | separately signed active envelope + operator readiness |

**Control-mode is not evidence status.** An authorized ACTIVE setting may still have `SLO_NOT_DEMONSTRATED`. Conversely, completed soak evidence cannot authorize a change of mode without an external signature.

## Measured KPIs (names provisional; no collision with existing K01–K20 / CRE-Rxx)

| ID | Name | Numerator / denominator or interpretation |
|---|---|---|
| AFO-K01 | Control-plane availability | seconds all mandatory admitted-work controls healthy / scheduled service seconds; exclusions separately disclosed |
| AFO-K02 | Eligible autonomous recovery | incidents recovered without new human prompt / incidents eligible for automatic recovery; censored and non-eligible separate |
| AFO-K03 | Accepted package yield | unique orders with genuine READY package / unique admitted orders with completed observation window |
| AFO-K04 | Terminal package ratio | unique orders with sealed READY **or BLOCKED** / admitted unique orders; not engineering success |
| AFO-K05 | First-pass phase yield | initial frozen inspection passes / initial inspections (SWE.1..SWE.6), reused 003 definitions |
| AFO-K06 | Human interventions per order | new manual prompts and operator repair acts / eligible unique admitted orders (approvals separately classified) |
| AFO-K07 | p95 transient recovery time | empirical p95 of eligible recovered incidents; missing/low n qualified |
| AFO-K08 | Duplicate logical side effects | dedup failures per identified operation; **zero-tolerance hard gate**, not average SLO |
| AFO-K09 | Replan effectiveness | materially changed plans followed by accepted gate / eligible executed plans, per phase/model/version |
| AFO-K10 | Model and compute per READY package | actual/estimated tokens, CPU/GPU seconds, cost including failed attempts; N/A if no READY |
| AFO-K11 | Unreconciled command horizon | oldest outbox UNKNOWN without verified receipt; alert when policy deadline exceeded |
| AFO-K12 | Idle healthy service time | healthy, no approved pending work; count as availability but not throughput/product success |

Each percentage must publish numerator, denominator, cohort key, observation window, source event references and a 95% CI when assumptions apply. Unknown costs and missing denominators are NULL/UNKNOWN, never zero. One work order with many attempts counts as *one order* in accepted yield. Multiple versions/models and full/resumed modes are separate until an explicitly justified comparable cohort is frozen.

## Provisional target thresholds (not demonstrated)

- Control-plane availability: >=99% of configured 30-day scheduled window with unplanned downtime included.
- Eligible-recovery-without-prompt: >=95% for predeclared eligible reversible fault classes, minimum statistically meaningful homogeneous sample; do not falsely claim 100% on tiny sets.
- First genuine READY: >=1 offline-approved pilot work order with all required gates, followed by intentionally BLOCKED negative case before any positive engineering-success claim.
- Zero invariant breaches: no skipped SWE inspector; no unsafe flash; no protection-policy change; no false READY; no repeat of uncertain non-replayable action; no unauthorized cloud model invocation.
- Soak: real 24h smoke, 72h authorized pilot, 168h continuous unattended service (idle allowed but workload exercise required). AFO 24/7 claim stays NOT_DEMONSTRATED until completion plus sustained subsequent monitoring.

## Soak phases and fault campaigns

1. **Simulation/isolated CI:** fake-clock scheduler, outbox crash matrix, blocked/READY discrimination, malicious prompt/MCP/maintainer path. Can be accelerated, but is not uptime evidence.
2. **Host smoke (~24h):** trusted read-only service probes, queue empty then 1 approved test order, maintenance-window SIGTERM/SIGKILL of noncritical service, DB and mount backups; human need not prompt or babysit.
3. **Pilot (~72h):** work-order retries, product and transient failures, outbox unknown, Model/Ollama failure, Fabro recovery, queued second order, pause/drain. Machine restart only if separately owner-authorized.
4. **168h soak:** systemd restart counters, host boot count, power/disk/cpu/gpu periods, actual UTC uptime windows, package READY/BLOCKED, AFO queue reconciliation, split between idle/no work and exercised workloads, metrics and alerts. Any interruption cannot be hidden by resetting start timestamp.
5. **Postsoak decision:** independent evaluation by deterministic test runner produces `ACTIVE_ELIGIBLE` or `NOT_DEMONSTRATED` and explicit remaining risk; external operator separately decides whether to enable ACTIVE.

## Host hardening checklist

- Use stable mount UUID/mount unit; unit `RequiresMountsFor` and verify marker with known volume UUID; fail closed if absent.
- `systemd --user` run after logout only if linger enabled by privileged human operator; no agent sudo.
- Secret storage outside repo, protected service credentials; never export full personal user environment to untrusted repair subprocess.
- Loopback-only APIs by default, separate read-only dashboard and signed operator write controls, OS-enforced candidate verification isolation.
- CPU, VRAM, disk quota, storage pressure and model concurrency cap; fair scheduling only when admitted work is approved.
- Release packages and logs protected against tampering and rotation; backup/restore and scrubbing tested; retention and privacy policies observed.
- Separate freeze windows: AFO code upgrade not deployed in-place during an in-flight work-order run; drain, snapshot, test, switch, rollback ability.

## Honest disposition codes

`IMPLEMENTED`, `PARTIAL`, `BLOCKED`, `NOT_RUN`, `PILOT_ELIGIBLE`, `ACTIVE_ELIGIBLE`, `SLO_NOT_DEMONSTRATED`, `SLO_DEMONSTRATED`. A `PASS` of E2E packaging asserts packaging validity only unless all independent SWE gates and READY state are separately verified. No AFO code or operational metric may assert ISO 26262 or ASPICE approval.
