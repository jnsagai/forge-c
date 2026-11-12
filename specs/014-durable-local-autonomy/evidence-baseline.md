# Evidence baseline and unresolved questions

This feature follows the October 25 review. All timestamps are UTC. Facts below describe pinned records, not the current remote host.

| Identity | Value |
|---|---|
| Implementation branch baseline | `fix/013-local-autonomous-recovery` at `f6ff873d5b4f3e9e46956ef26766181aaec2289d` |
| Actual final recovery runtime | `36ed0fc70bd8765f0cc90a45b21bbf02924b0269` |
| Reviewed overnight snapshot | `03a274df14cc00135d4055361d72a4b2c44f1545` |
| Last historical RCC run | `01M5QPG9HT2SZW0PY5ZQSNE78X`, ended 2026-10-24 20:08:41.904251 |
| Historical diagnosis grant | `AUTH-OMNI-Q36-LOCAL-SELFHEAL-V4-20261024`, expiry 2026-10-25 09:00 UTC; four diagnosis calls exhausted |

| Trial | Native run ID | Source | Reported tokens | Observed terminal issue |
|---|---|---|---:|---|
| v1 | `01M5QTF2X5M4WMSFKXPJ6KRHEJ` | `c008ba1` | 15,507 | Invalid submissions, clipped error, no valid recorded compact reply; parent FileNotFoundError |
| v2 | `01M5QVAH97WCR7E9W0VPTSMK8Q` | `a477a6d` | 9,270 | Wrong field types/lengths, prose final; record exit 2; intended schema metadata absent from actual SDK registration |
| v3 | `01M5QVW4QYPRC1JAX1Q413HEA8` | `335a2e0` | 16,856 | Three reads, no plan, reactive cancellation after 856-token overrun; unrelated skills exposed |
| v4 | `01M5QWC6CP1BJKGXKEXWG6HXHM` | `36ed0fc` | 13,071 | Three reads, no plan/valid compact exit; one correct skill exposed; native stopping cause unresolved |

Each reserved 16,000 tokens. Totals: reported 54,704; reserved 64,000; conservative sum(max(reserved,reported)) 64,856. Zero accepted model recovery plans and zero new implementation attempts. There is a validated deterministic RULE/CLOSE_BLOCKED plan in morning progress.

Five unique historical product executions were imported, not rerun. Their 20 attempt rows across four orders must not be counted as 20 executions. Packages are BLOCKED, SWE.1/SWE.2 PASS and SWE.3–SWE.6 REWORK; gap counts 44, 56, 57, 51, 50 are not independent error counts or a convergence metric.

Timeline: 50 valid records from 2026-10-24 20:43:40.588652 to 2026-10-25 06:43:45.067314. All diagnoses terminal by 21:18:03.337692. Final hash appears in 39 snapshots (38 repeats), spanning approximately 9h25m42s unchanged terminal state. Hash-only changes elsewhere include fields not projected into timeline job/order columns and do not prove engineering progress. Snapshot intervals do not measure inference duration.

Morning heartbeat was fresh/healthy and GPU was idle. Download freshness/byte progress was omitted, so the DOWNLOADING label alone does not establish ongoing download. Operator-qualified source fixes and passing CRE gates do not establish autonomous source promotion or product recovery effectiveness.

## Required native investigation

Retrieve exact terminal/finish reason, configured versus actual model requests/tool calls, denied calls, registered tool schemas, prompt/skill digests, recorder exit and final-output metadata. Record per-request input/cache/output usage, context size, timestamps, cancellation request/ack and evidence-read sizes. Do not retain hidden reasoning or raw private inputs.

Retrieve the actual final SWE.3 findings, implicated source/design and reproducible tool diagnostics; classify root causes separately from downstream packaging gaps. If these records cannot be obtained, keep the cause UNKNOWN and proceed with independently reproducible control-plane fixes.

## Pinned sources

- [Trial validation](https://github.com/jnsagai/forge-c/blob/f6ff873d5b4f3e9e46956ef26766181aaec2289d/specs/013-local-autonomous-recovery/validation.md)
- [Runtime snapshot](https://github.com/jnsagai/forge-c/blob/f6ff873d5b4f3e9e46956ef26766181aaec2289d/evidence/013-local-autonomous-recovery/runtime-status-36ed0fc.json)
- [Timeline](https://github.com/jnsagai/forge-c/blob/03a274df14cc00135d4055361d72a4b2c44f1545/evidence/013-local-autonomous-recovery/overnight-20261024/timeline.jsonl)
- [Morning handoff](https://github.com/jnsagai/forge-c/blob/03a274df14cc00135d4055361d72a4b2c44f1545/evidence/013-local-autonomous-recovery/overnight-20261024/HANDOFF.md)
- [Morning progress](https://github.com/jnsagai/forge-c/blob/03a274df14cc00135d4055361d72a4b2c44f1545/evidence/013-local-autonomous-recovery/overnight-20261024/progress.json)
- [Reviewed analysis and plan](https://chatgpt.com/space/page_794127ccee00819192cce472a5cf9f29) — context only; the repository specification and constitution govern implementation.
