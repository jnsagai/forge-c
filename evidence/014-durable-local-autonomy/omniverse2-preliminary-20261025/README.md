# Feature 014 — preliminary live protocol trials on Omniverse2 (2026-10-25)

Scope: owner-approved ("I do, I approve all") bounded protocol-qualification **trial subsets**, one isolated
qualification runtime per exact source revision, model `qwen3.6:35b-a3b` (digest `a7eb95c5…`, Q4_K_M, gateway
reasoning effort high), single-coherent-obligation diagnosis role. Each revision had its own frozen 100-trial manifest,
finite protocol-only mission (100 jobs / 100 requests / 3,276,800 tokens / 0 product attempts, deadline
2026-10-27T19:00Z) and owner-signed grant (`AUTH-OMNI-Q014-QUAL-<REV>-20261025`, signed with the existing `jefferson`
key through the SSH agent). **No campaign is complete; every report keeps the 100-trial denominator. Observed ==
expected below is not a qualified protocol result** (the hash-bound independent audit row is not produced here).

Machine-readable rows: `summary.json` (sanitized: decisions, reason codes, value-free diagnostics, bounded stored
proposal fields, exposure facts, token/request counts, row hashes; no reasoning, raw prompts or vendor content).

## Runtime path findings (each fixed, tested and committed before the next run)

| Revision run | Finding | Fix |
|---|---|---|
| 836ae49 | Enrollment + scheduler admission worked; provisioning refused `PACKET_REFERENCE_INVALID`: sealed packets lived in the preparer's private state dir | cc2b39c: inputs carry hash-bound packet copies, intake imports them; deterministic role refusal closes only its wrapper |
| cc2b39c | Gateway 429 `AUTH_NOT_REFERENCED` (stack services get the AFO policy/grant only with an operations intent); integer HTTP status crashed failure recording | 20f6b02: typed bounded incident codes; live preflight requires a RUNNING operations intent |
| 20f6b02 | Model answers `CONTRACT_INVALID`, cause unknown (receipt kept only the code) | 2dfd32f: value-free rejection diagnostics |
| 20f6b02→ | Managed stack stop: `os.pidfd_open` missing in Omniverse2's uv CPython 3.13.13 | c6850ac: raw pidfd syscall fallback |
| loaded-host regression | `/proc/<pid>/status` vanishing between reads reported as observation error | 8e1aee5 |
| c6850ac | Diagnostics: every answer was `{"decision": ...}` only (34 bytes) — the authoritative oneOf schema did not constrain local decoding | e35ed0a: grammar-friendly closed-branch wire schema (authority unchanged) |
| c6850ac→ | Managed stop refused the API bridge (no recorded identity) | 7f197d2 |
| e35ed0a | 6/6 schema-valid; all NEEDS_EVIDENCE; SKILL text told the no-tool node to read via a tool | 677d45a: explicit single-response contract |
| 677d45a | No change; 3/6 rejected for mangled 64-hex references | b759094: short case-local evidence aliases |
| b759094 | 6/6 admitted, 0 citation errors; still NEEDS_EVIDENCE for evident repairs | dddf00e: stated the contract's decision rule |
| dddf00e | No change (5/6 NEEDS_EVIDENCE, 1 duplicate-item schema failure) | tuning stopped — measured capability limit |

## Fault controls exercised live

- revoked-before-dispatch (20f6b02, cc2b39c): REVOKED, execution NOT_STARTED, no native contact, common grant/mission unaffected.
- expired-mission (20f6b02, cc2b39c): EXHAUSTED through the dispatch-time mission-deadline check, NOT_STARTED; registered mission unchanged.
- lost-launch-ack (20f6b02): real launch receipt dropped; run adopted once by nonce listing (same run id). Model answer then invalid.
- cancel-ack-still-live (c6850ac): cancel acknowledged while a gateway request was SENT; inference lease stayed HELD → BLOCKED_LIVE_HELD.
  (20f6b02: exposure not achieved — the generation finished between 10 s polls; driver polls live jobs every 2 s since.)

## Diagnosis-role capability (preliminary)

Across 5 positive cases × 4 prompt/interface variants after constrained decoding was fixed, Qwen3.6-35B-A3B chose
NEEDS_EVIDENCE for evident conformance repairs, while its own text correctly identified the defect (mask
`UINT32_C(2)` vs required `UINT32_C(1)`). It answered the NEEDS_EVIDENCE case correctly (b759094, dddf00e) and never
chose CLOSE_BLOCKED for the empty-technique case. Structured validity reached 23/24 answers in the last four batches.
This is a role-capability failure for this model/configuration, not evidence about other models, product recovery,
learning benefit or availability (all NOT_RUN).
