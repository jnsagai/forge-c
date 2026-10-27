# Protected audit-source capture and replay

This is executable qualification tooling for DA-AT-052, not campaign evidence or
a new audit/retention authority. It extends the existing frozen observer plan and
qualification evidence tree. No command installs audit policy, starts a service,
changes a grant or makes a model request.

## Prerequisites and frozen inputs

Use an isolated, clean checkout of the exact qualified source on Omniverse2 and
private state/events/evidence directories. Preserve the existing services. Native
kernel auditing, approved rules, protected retained files and read access must
already exist. Missing privilege or visibility stays BLOCKED; these commands do
not grant it. Run `python -m forge_factory.afo.host_audit preflight --out <new-file>`
first. A finite preflight cannot establish continuous host coverage.

An existing `forge-c/host-audit-plan/1` input gains an optional `segments` object:

```json
{
  "reader_sha256": "<SHA-256 of afo/audit_segments.py in the tested checkout>",
  "paths": ["/var/log/audit/audit.log", "/var/log/audit/audit.log.1", "/var/log/audit/audit.log.2"],
  "max_bytes": 8388608
}
```

Freeze this host plan, its observer-plan reference, host/source hashes, keys and
approved rules in the existing operational manifest before execution. Keep the
existing observer/source hash checks. Re-freezing for different tooling is an
explicit new qualification input; it never renews authority or mission budgets.
Do not modify an already signed/frozen manifest. Paths are a bounded consecutive
auditd rotation sequence, beginning with the active file; arbitrary aliases and
missing intermediate numbers are refused. At most 64 paths and 16 MiB per capture
are allowed. Retention remains the host administrator's responsibility.

## Capture, resume and verify

The reference files below contain `{"path":"<absolute-path>","sha256":"<file-hash>"}`;
the manifest is the actual frozen manifest JSON. Every output path must be new
and inside the observer's approved evidence root. Do not store raw private audit
records or credentials in Git. All new local artifacts belong on loop10.

```bash
python -m forge_factory.afo.host_audit capture \
  --manifest "$MANIFEST" --observer-plan-ref "$OBSERVER_REF" \
  --host-plan-ref "$HOST_REF" --out "$EVIDENCE/capture-000.json"

# Hash capture-000.json into a private reference file, then continue:
python -m forge_factory.afo.host_audit capture \
  --manifest "$MANIFEST" --observer-plan-ref "$OBSERVER_REF" \
  --host-plan-ref "$HOST_REF" --previous-ref "$PREVIOUS_CAPTURE_REF" \
  --out "$EVIDENCE/capture-001.json"

# SEGMENT_REFS is a JSON array of successful-capture references, in order.
python -m forge_factory.afo.host_audit verify-segments \
  --manifest "$MANIFEST" --observer-plan-ref "$OBSERVER_REF" \
  --host-plan-ref "$HOST_REF" --segment-refs "$SEGMENT_REFS" \
  --out "$EVIDENCE/segment-replay.json"
```

Capture and verification deliberately return **exit 2 / INCOMPLETE_SOURCE_COVERAGE**
while host/event coverage is incomplete. Inspect the durable receipt; do not treat
this exit as a request to retry a model or reset the mission. Malformed, unbound or
changed inputs are refused before a successful replay receipt is written.

The initial cursor begins at byte zero of the then-active source, not before the
declared campaign or all historical boots. Subsequent captures bind the previous
successful artifact, sequence and cursor. A failed capture retains `resume_ref`;
passing its reference to the next capture resumes the last successful cursor.
Keep failed captures as immutable history. Their intervals remain unobserved even
when later byte coverage succeeds. The replay list contains successful captures
starting at sequence zero, including every intervening successful range.

Replay validates artifact hashes/plan bindings, sequence/parent references, exact
adjacent byte ranges, rolling anchors and retained source contents. It rejects
missing/reordered/duplicated ranges, changed/truncated/deleted history and altered
sealed generations. Total metadata is bounded to 16 MiB, count to 10,000 captures,
and source/terminal-anchor I/O to 128 MiB. Exceeding a bound requires an explicitly
qualified scoped continuation; it never silently drops the beginning of a chain.
The current verifier does not yet provide such a batched continuation.

## Rotation and evidence limits

The reader drains an old inode before switching. Handoff requires two stable
native descriptor censuses of the PID reported by kernel audit status: old inode
closed, new regular source open for append, UID zero, stable process identity.
No caller-supplied `closed=true` flag is accepted. Descriptor path/command strings
are not exported. Replay checks those recorded numeric facts and their bindings;
hashes do not independently authenticate the original observer or its clock.

Old generations must remain readable and at their sealed EOF. Late writes fail
the next capture or replay. Multiple rotations missed between observations are
explicitly blocked; this reader does not skip the intermediate generation. Source
ownership/ancestry protections are checked on open. These checks assume the host
kernel and privileged audit configuration are trusted, not arbitrary root compromise.

Linux exposes descriptor flags in octal in [the proc filesystem interface](https://www.kernel.org/doc/html/latest/filesystems/proc.html).
The append-writer check follows [auditd's native file open](https://github.com/linux-audit/audit-userspace/blob/master/src/auditd-event.c).

`CAPTURED_BYTE_PREFIX_REPLAYED` proves only the supplied captured byte prefix was
replayed. A final source may have an explicitly reported unread tail. Complete
compound-event replay across byte boundaries, boot/loss/time-window reconciliation,
continuous bus/control/actor correlation and all-channel intervention verification
remain separate unfinished work. The global intervention count stays **UNKNOWN**.
Synthetic protection/UID fixtures and deterministic tests are not live root audit
qualification, product success, learning benefit or 24/72/168-hour availability.
