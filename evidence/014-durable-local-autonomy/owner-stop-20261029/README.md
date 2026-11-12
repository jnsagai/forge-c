# Explicit owner stop

The owner requested immediate Qwen stop on 2026-10-29. The existing authenticated
operations shutdown path persisted STOPPED epoch33 before retiring the exact
managed provider, cancelling native execution and confirming quiescence. Initial
settlements correctly retained the inference lease while cancellation was pending.
At16:27:20UTC settlement completed; at16:27:48UTC independent native/ledger read
confirmed FAILED, QUIESCENT, RELEASED. No GPU compute process remained.

See [actual observations](stop-proof.json). The parent order still reported
RUNNING; no completed archive or complete SWE.6 delivery is asserted. Phase1/2/4/5
inspection passes and the actual phase3 failures remain unchanged. Last observed
Robot result is7/9; this interrupted demonstration is not strict M1 acceptance.

Do not resume at18:00 automatically: the subsequent explicit stop is authoritative.
No grant renewal, source deployment, qualification run or new model order occurred.
Prepared epoch32 qualification remains NOT_RUN and must refuse epoch33. Continue
independent local implementation; resume requires a newer authenticated owner
instruction and a valid finite scope. Current source9b4c390; fix9f9a93f undeployed.
