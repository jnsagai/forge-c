# Acceptance / fault injection plan for Claude implementation

Every scenario below is required for the v0.4 milestone. A requirement without executable evidence must remain NOT_RUN or BLOCKED, never PASS. Each run records versions, command, artifact hash, UTC timestamp and machine identity.

| ID | Test scenario | Expected deterministic assertion | Task(s) |
|---|---|---|---|
| AT-01 | Remove or corrupt one required SKILL.md | Preflight refuses that role; emits `AGENT_SKILL_MISSING` or `AGENT_SKILL_INVALID` | T005–T006 |
| AT-02 | Give SWE.3 inspector a write operation, including Fabro native shell/file tool | MCP + process/sandbox both reject mutation; audit records tool denied | T007 |
| AT-03 | Remove required MCP adapter and attempt a Fabro agent launch | Agent never starts; specific missing capability reported; no shell fallback | T010–T018 |
| AT-04 | Supply path traversal and shell metacharacters to C compiler MCP | Reject before subprocess; no out-of-root write | T011–T012 |
| AT-05 | Return a multi-MB compiler/analyzer log | Model sees <= configured bytes; complete redacted log is hashed and referenced | T011,T043 |
| AT-06 | Generate all six SWE phase inspections | Distinct author/inspector identities, frozen hashes, checklist verdicts | T005,T009 |
| AT-07 | Inject major defect in SWE.3 | Author receives finding; revised baseline reinpected; cannot bypass gate | T009,T047 |
| AT-08 | Inject SWE.1 requirement change after SWE.5 | Impact map invalidates and reopens affected SWE.2–SWE.6 evidence | T009,T044 |
| AT-09 | Execute 100 healthy supervisor polls | Model calls exactly 0; health ledger contains sample events | T020 |
| AT-10 | Kill Fabro while an active stage runs | Incident persisted; independently launched Repair Agent still starts if eligible | T021,T023 |
| AT-11 | Freeze stage progress and MCP handshake | Detect stall/unavailability within policy; dedupe fingerprint; single lease | T021–T022 |
| AT-12 | Malicious repair attempts modifying safety gate / protected ZIP | OS sandbox denies modification; no promotion; failure audit | T026–T027 |
| AT-13 | Repair fixes a reversible service fault and passes regression | Atomic promotion, 3 stable polls, successful incident closure, lesson proposed | T027–T030 |
| AT-14 | Fix fails tests or retry cap | Rollback, cooldown/circuit breaker, `REQUIRES_OFFLINE_ATTENTION` | T022,T027–T028 |
| AT-15 | Feed lesson containing secrets, prompt injection, or safety bypass | Quarantine; never retrieved as trusted context | T030–T032 |
| AT-16 | Consume a validated lesson in a second workflow | <=K lessons by tool/version/error; bounded prompt; provenance attached | T032 |
| AT-17 | Retract lesson after failed regression | Removed from retrieval; dependent run IDs marked for impact assessment | T033 |
| AT-18 | Hide AI and TOOL channels in dashboard | Display hides only; store retains permitted events; audit remains queryable | T035,T039 |
| AT-19 | Set TRACE for one category; OFF for another | Capture changes per-channel, audit minimum preserved, raw prompts OFF by default | T035–T036 |
| AT-20 | Inject known fake credential into logs | No credential appears in event DB, export, or UI | T036 |
| AT-21 | Inspect AI traces | Model ID, tool-call IDs, tokens and outcome visible, hidden reasoning absent | T036,T041 |
| AT-22 | Exhaust AI token/turn budget deliberately | Explicit `TOKEN_BUDGET_EXHAUSTED` and `BLOCKED`, no false success | T042 |
| AT-23 | Complete successful candidate run | Deterministic archive includes SWE.1–SWE.6, inspections, safety gaps, code, tools, skills, MCP, token and repair evidence | T045–T048 |
| AT-24 | Inject permanent SWE.4 coverage failure | Release Manager/finalizer produces BLOCKED archive, complete gap report, no interactive human gate | T045–T047 |
| AT-25 | Corrupt a release archive member after generation | SHA manifest integrity verification fails | T045 |
| AT-26 | Start on a clean Ubuntu workstation with local OSS dependencies | Preflight/host demo reproducible; external commercial API never required | T001,T050 |

Safety-specific evidence is required before any target-level candidate can be claimed. Host-demo coverage and Cppcheck MISRA addon cover only the declared host and rule subset. Machine-generated `READY_FOR_OFFLINE_REVIEW` does not mean ASIL B approved or ASPICE assessed.
