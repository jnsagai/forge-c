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
