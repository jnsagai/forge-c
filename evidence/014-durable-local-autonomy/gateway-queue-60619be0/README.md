# Stage timeout must not cascade into avoidable busy failures

Exact inactive source **60619be076d36d50f42aef0c1b467aa2c2c14e76**.
Actual native07 timeline binds the problem, original observationSHA256
`976eeb14cca7dcd02ff76b0ccce01cd79720a6cab9cb132c5fb1b56c709df009`:

- SWE.5inspector timed out after900000ms at06:48:29.810817remoteUTC.
- Its prior gateway request was still generating. Six new requests returned
  INFERENCE_REQUEST_BUSY/upstream_called=false at06:48:41.715..48.667.
- SWE.6test-author and author stages failed429after their rapid retries.
- Prior response completed06:48:48.707, finish_reason=tool_calls,11569output
  tokens/175tool calls. Its request ID binds to the same product job in the
  durable ledger and is nowQUIESCENT. Capacity was correctly retained while
  the earlier native stage was already terminal; no overlapping inference.

This explains the two missing SWE.6author deliveries in07, not an observed
failure of the model to implement Robot tests after an admitted request.
The later inspector ran and reported missing verification/report. The sealed
archive retains those gaps; none are retroactively repaired or reclassifiedPASS.

Fix: use the gateway's **existing bounded Admission queue before durable request
reservation/measurement**. A draining request can finish, then the next caller
rechecks authoritative ledger, role/policy/operator/provider conditions before
generation. No replay of prior generation, capacity release on stage terminal,
new queue/scheduler/authority, enlarged limits or hidden budget reset. If the
prior outcome remainsUNKNOWN, the durable ledger still blocks new generation
even after an in-process admission ticket is free. Stop/revocation during wait
still prevents a new provider call. Queue timeout/full/backpressure stays bounded.

Five new actual ASGI/HTTP/ledger fixture scenarios failed-before (next request
failed instead of entering the existing queue), then focused5PASS. They cover
completed drain, operatorSTOPPED, revoked execution, unknown provider outcome
and bounded wait timeout; peak upstream concurrency1, retained execution lease,
no historical expenditure reset. Fixtures use a synthetic provider and existing
protocol authority, not Qwen or real native timeout qualification.

Exact source regression **79PASS/zero failures/errors/skips,10.227s** across
gateway/admission/mission/integration/native-adapter fixtures. Separate inherited
gateway/full-request-measurement **22PASS/zero failures/errors/skips,1.685s**.
Focused5 is included in79; counts must not be added to overlapping earlier
cohorts. Changed gateway/new-test RuffPASS; initial new-test import order fixed.
Commands and raw failed/passing JUnit receipts are retained with gzip hashes.

No deployment during frozen comparison (producer0e/profile3/auditor303).
Native effectiveness of this fix is NOT_RUN; a future source-pinned authorized
qualification must measure it. Fresh scoped yield2/3 remains separate from full
LL/HAL, clean phase delivery, production, independent learning benefit and24/7.
Original owner expiry07:57:59UTC unchanged; no new DA task completed30/58.
