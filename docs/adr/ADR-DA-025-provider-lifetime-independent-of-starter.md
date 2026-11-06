# ADR DA-025 — Provider lifetime is independent of its starting process

Status: implementation candidate; runtime and product acceptance remain separate.

L90D, the last mission attempt, failed on source 9e0eee4b before native submission.
`stack start` reported all four services healthy, then the serving holder, ollama,
gateway and llama-server were gone. Fabro and the network holder survived, and 118
status polls saw only Fabro healthy until the launch gave up.

`owner_development_view.prepare` launched the provider sandbox with
`bwrap --die-with-parent`. The line launcher runs `stack start` as a short-lived
subprocess, so the sandbox died when it exited. Guardian bootstrap masked this by
calling the same start in-process from a long-lived guardian, and no earlier attempt
had reached the launcher's start. An external reproducer drives the real `prepare`
and `provider.capture` from a short-lived parent.

The flag is removed. The ordinary non-owner provider path never tied the provider to
its starter, and the view has no reason to differ.

Consequence: a provider now outlives a crashed guardian instead of dying with it. It
stays inert for guarded work. The launch guard reads guardian liveness through the
kernel, and `require_compatible_provider` binds a provider to the exact guardian
record, so another guardian refuses it with `KNOWN_PROVIDER_REPLACEMENT_REQUIRED`.
It keeps holding GPU memory until the exact recorded instance is retired, which the
stop path already does by pidfd. Unbounded automatic reaping is not added here.

Process lesson: offline qualification and host proofs covered components, and each of
four spent attempts died at a stage no earlier attempt had reached. The launcher path
under owner-development authority needs a private end-to-end rehearsal before another
real attempt is spent.

## Findings from the private launch rehearsal

The first rehearsal stalled the guardian: `_publish_heartbeat` runs synchronously inside
the serve loop, and an fsync over two seconds spent the caller's attestation timeout.
`guard()` then refused during bootstrap. Only the first challenge needs the heartbeat
published before the acknowledgement, because the host guard reads it after `current()`.
Later publications now run on one background thread at a time. A failed publication
leaves the heartbeat stale, which the guard still refuses.

The rehearsal then reached the workorder CLI and refused every durable product at native
admission with `SOURCE_WORKSPACE_MISMATCH`. `product_job.prepare` took its path from the
attempt, which stays `pending:<id>` until after launch, so every job recorded
`workorders/pending:<id>/workspace`, including L90, L90B and L90C. `job["binding"]` pointed
into the same missing path. `dispatch` already knows the launch name, so it now passes it
and the job binds the real work-order workspace. A pending attempt without a safe name
refuses rather than binding the placeholder, and a launched attempt cannot be rebound.
Historic job records are left as they are. Admission refusals keep the binding reason
instead of the bare exception class.

Merging storage identity exposed a soak fixture that relied on a durable recovery cycle
creating its queue. That refusal is the storage fix working, so the fixture now creates
its authority first.

`L/archives` is group-writable on Omniverse2, and the controller export correctly refuses a
group-writable anchor. As with `lrtx/run`, the host needs a one-time `g-w` hardening before
reports can publish. The check is not weakened.

The next rehearsal stage refused with `SOURCE_REVISION_UNRESOLVED`. `line_recovery.bind` looked
up the factory commit in the campaign's repository, which assumed the campaign lived in the
factory repository. The real campaign lives in its own data repository, so this could never
resolve. It now resolves against the running source. An unknown or malformed revision still
refuses, and the manifest provenance check that follows is unchanged.

The rehearsal then failed in role-context capture with `JSONDecodeError`. Generated workflow
prompts carry real line breaks, which strict `json.loads` refuses, so `_attrs` could not read
any real graph. Control characters are now accepted inside graph strings. All 86 statements of
the generated SWE.6 workflow parse. Duplicate attributes and unterminated values still refuse.
