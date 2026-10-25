# Feature 014 — preliminary live protocol trials on Omniverse2 (2026-10-25)

Scope: owner-approved ("I do, I approve all") bounded protocol-qualification **trial subsets**, one isolated
qualification runtime per exact source revision, model `qwen3.6:35b-a3b` (digest `a7eb95c5…`, Q4_K_M, gateway
reasoning effort high unless noted; `qwen3.8:27b-q8_0` in bcb8cae), single-coherent-obligation diagnosis role. Each revision had its own frozen 100-trial manifest,
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
| 3de1a44 | Owner-chosen controlled factor: profile `local-rtx-v2-omniverse2-q36-noreason` (gateway reasoning off, otherwise identical, same digest). Same pattern: 6/6 NEEDS_EVIDENCE (missing-primary correct; 4 accepted wrong decision; 1 rejected for citing SWR-001 as an obligation); tokens fell to ~1.3–2.2k per trial from ~3.2–8.9k | reasoning effort is not the cause |
| bcb8cae | Owner-chosen model comparison: `qwen3.8:27b-q8_0` (digest 8f5fb6b7…, Q8_0, 27.3B, first run; profile `local-rtx-v2-omniverse2-q38`, reasoning none, same cases). Same pattern: 6/6 NEEDS_EVIDENCE, all admitted (no citation errors); only missing-primary correct; ~1.3–2.2k tokens per trial | a second, denser Qwen generation shows the same over-caution |
| bdba4c1 | Owner decision: split the decision (signed task class `two-step-diagnosis`, qwen3.6 reasoning off). Q1 conflict=YES everywhere; Q2 answers opened with `explanation`, which forced NONE although the text named repair-implementation | 1017e88: technique choice first |
| 1017e88 | Still NONE as first token | 0ce4618: three flat questions (conflict; technique enum; repair fields), no repair branch inside anyOf |
| 0ce4618 | First repair proposals (exact fix in reg32.c); rejected for invented test refs and missing conditional owner_phase | ec0c8f9: declared tests as enums; owner_phase follows strategy |
| ec0c8f9 | **First broker-ACCEPTED local repair with bound plan** (obligation-counterexample); others phase/scope-inconsistent | a206c54: contract-legal phase/scope/verdict choices (incomplete packet → only UNKNOWN, disclosed) |
| a206c54 | **6/6 observed == expected, all admitted**: 4 accepted repairs with bound plans, NEEDS_EVIDENCE (restricted verdict), CLOSE_BLOCKED | full remaining matrix launched (89 trials) |

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
With gateway reasoning off (3de1a44, one changed configuration factor; the source revision also differs only by the
variant profile file and a `--profile` preparation option) the decisions did not change, so the reasoning effort does
not explain the over-caution. `qwen3.8:27b-q8_0` (bcb8cae, reasoning none) behaved the same on all six trials. This is a
role-capability failure for both measured Qwen models and configurations, not evidence about other models, product recovery,
learning benefit or availability (all NOT_RUN).

## Stepwise diagnosis (owner: "we have no other option than work with those models")

The local decoder handled small closed questions but never produced a large repair branch inside a JSON-schema
`anyOf`. Splitting diagnosis into three small grammar-constrained questions — (1) conflict YES/NO/UNKNOWN with the
rationale first and evidence restricted to case aliases; (2) technique as one enum of the case catalogue or NONE;
(3) repair fields restricted to contract-legal phases, the case's artifact paths and declared tests — with deterministic
assembly and the unchanged broker made qwen3.6:35b-a3b (reasoning off) answer all six diagnosis trials as expected
(a206c54). Contract-derived restriction disclosed: an incomplete packet is offered only UNKNOWN, so those trials
measure the missing-evidence answer, not the verdict. Up to three metered requests per job (~2.6–5.1k tokens total).

### Remaining matrix on a206c54 (89 further trials, sequential, 22:20–23:09 UTC)

95 of 100 frozen trials ran (the 5 `qualified-local-alternative` trials stay blocked by their missing measured-alternative
prerequisite). **93/95 observed == expected, and every declared fault exposure matched**:
20/20 accepted repairs for obligation-counterexample, unicode-contract, late-finding and lost-launch-ack; upstream-owner 4/5
(repeat 4: an SWE.2 upstream return scoped to an SWE.3 file, rejected REPAIR_SCOPE_DENIED); missing-primary 5/5;
missing-dependency 4/5 (repeat 2: duplicate missing_evidence item failed uniqueItems); no-allowed-strategy 5/5; all response,
evidence, empty-output and dispatch/liveness fault cases 5/5 each.

The official `protocol_report` remains **FAIL (correct_outcomes 0)**: it requires a hash-bound independent audit row
(false success / duplicate effects / authority escapes) for every trial, and no independent auditor exists yet; plus
the 2 misses and 5 blocked trials. Usage is unknown for 23 rows (non-inference trials without gateway requests).
