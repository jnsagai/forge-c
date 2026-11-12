# Bounded remote Qwen engineering assistance

One owner-requested, read-only review of the bus-query helpers ran on Omniverse2
through the existing single-inflight gateway/GPU queue. It is external engineering
assistance, not autonomous repair, inspector calibration or role qualification.

The study made one client request and one measured upstream attempt: 1,819 input
and 793 output tokens, 9.4334 seconds request wall time. Total study wall time was
249.612356 seconds including a failed preflight and its harness correction. The
first preflight compared process UIDs across user namespaces incorrectly and made
zero model calls. Continuation retained the same accounting and one-call cap;
this study is now exhausted and must not be redispatched.

The response was schema-valid but failed literal source-reference validation. The
8KiB ceiling complaint did not establish a defect. A nonnumeric-name suggestion
led to an independent check against the primary D-Bus contract and native libdbus,
which reproduced false blocks at `fbd8bc8`. External engineering fixed the parser
at `818ab90`; verification at `7e1abb2` passes supported and malformed reply cases.
The native library overaccepts some degenerate unique names, so normative negative
fixtures remain authoritative. No finding was automatically applied by Qwen.

`packet.json`, the submitted source projections and `context-replay.json` establish
exact serialized-context/hash replay without another inference request. The
7,960-byte request has a conservative 8,088-token UTF-8 bound, not a native
tokenizer measurement. The 1,024-output reserve fits the 16,000 task envelope;
the observed gateway retry limit also retained a conservative 48,000 total token
bound. Meter records retain actual attempts/usage and UNKNOWN fields as observed.
The original failed and resumed queue scripts/status/logs are preserved. The
initial harness was reconstructed byte-for-byte and verified against its original
queued SHA256; it is explicitly named as reconstructed.

Four factual experiences/dispositions use the existing LessonStore APIs: three
DEFERRED_BUDGET and one NO_NEW_LESSON. Zero qualified lessons were added. No repair
incident, product success, measured learning benefit, self-healing success or
operational availability is claimed. Raw model responses and prompts are private;
Git contains a sanitized proposal summary and original-response hash.

See [summary and artifact hashes](summary.json), [before check](independent-before.json),
[after check](independent-after-7e1abb2.json), and the
[primary D-Bus naming contract](https://dbus.freedesktop.org/doc/dbus-specification.html#message-protocol-names-bus).
