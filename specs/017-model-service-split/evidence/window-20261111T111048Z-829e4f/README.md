# 017 smoke window 20261111T111048Z-829e4f (T044 partial; NOT accepted)

Window run on Omniverse2 2026-11-11 11:10Z-12:20Z (`window run --plan smoke --max-minutes 120 --execute`),
model tier from feat/017-model-service-split-impl f1e07b5d (CAPA-234), owner lane live 892404d2.
Outcome **COMPLETED**: lane drained, released, GPU verified free, tier started, plan ran, tier stopped,
GPU free again, lane restarted and resumed (window record: `window-record.json`).

| T044 item | Result in this window |
|---|---|
| window record | collected |
| identity | both models answer with their pinned, attested identity; 0 wrong-model answers |
| swap times both directions, p95 vs SC-011 | Ornith->qwen3.8 median 5.49 s, p95 6.27 s (n=10); qwen3.8->Ornith median 6.60 s, p95 6.70 s (n=9); sc011_pass true |
| SC-009 | sc009_pass true |
| SC-003 (0 factory call failures under neighbour load) | sc003_pass true; the neighbour tenant itself completed 0 of 4 requests (3 errors at the 600 s timeout, 1 HTTP 429): open finding |
| KV capacity | NOT_RUN in this plan |
| outcome-log metadata | in tier-state/outcomes.jsonl (not copied: host state) |
| per-tenant latency | NOT_RUN in this plan |
| SC-001 audit (0 factory server/GPU-lock actions) | NOT_RUN in this plan |
| SC-002 (100% of calls fingerprinted) | NOT_RUN in this plan |
| SC-010 | NOT_RUN in this plan |

Findings: REASONING_CONTENT_WITH_THINKING_OFF (qwen3.8, recorded by the tier).
Earlier windows the same day: 20261111T093853Z-23268f COMPLETED but every Ornith load failed
(FileNotFoundError, fixed by CAPA-234); 20261111T093137Z-e88182 release refused untouched (CAPA-232, CAPA-233).
T044 stays open until the missing items are measured.
