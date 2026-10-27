# Independent observation collector

This increments backlog A2; it does not complete DA-T016/017/026/046/049/052.
`afo.operational_collection` uses the existing `soak.run` cadence. It has no model
client, dispatch path, recovery authority or service control. No campaign is started
by installing this code. The Conductor continues when an observer invocation ends.

An opt-in frozen observer plan adds `collection` with `source_sha256`,
`soak_source_sha256`, `campaign_source_sha256`, `interval_seconds` (5..600),
`max_samples` (1..50000 cumulative over this soak), and `minimum_free_bytes`
(at least 64 MiB). `source_hashes()` supplies the three exact implementation hashes.
Changing any source/configuration requires a new explicit frozen campaign; it does
not reset a mission or renew authority. Host plans are independently frozen inputs
referencing that observer plan; they must use the existing segmented audit reader.
Do not nest a host-plan reference inside the observer plan (a circular digest).

```sh
python -m forge_factory.afo.operational_campaign start --manifest MANIFEST \
  --soak-id soak-operation-example --authorization-ref CURRENT_REF \
  --observer-plan OBSERVER_PLAN --host-plan HOST_PLAN
python -m forge_factory.afo.operational_campaign collect --manifest MANIFEST \
  --soak-id soak-operation-example --observer-plan OBSERVER_PLAN \
  --host-plan HOST_PLAN --max-samples 100
python -m forge_factory.afo.operational_campaign report --manifest MANIFEST \
  --soak-id soak-operation-example --observer-plan OBSERVER_PLAN \
  --host-plan HOST_PLAN --evidence VERIFIED_FAULT_WORK_CONTINUITY_REFS
```

These are templates, not authority or a runnable signed campaign. Starting requires
existing preflight authority. Model-free sampling can continue after engineering
allowances expire. The sidecar soak lock serializes legacy and collector writers.
The collector refuses mixed/unbound histories, partial tails and clock reversal.
It neither truncates nor repairs evidence automatically. Disk reserve and finite
sample exhaustion stop only that collector invocation, with explicit refusal codes.

Each sequence publishes host and independent operational captures, bounded attempt
records, then an immutable chained receipt, then fsyncs the existing soak JSONL.
A crash before log append replays the original receipt/capture and measured clocks.
A crash after capture reuses that artifact. Failures retain typed errors; a missing
host source retains the existing host reader's last successful cursor through its
failed capture. Reports recompute observations from original source artifacts and
reject altered health claims. Incomplete captures produce unknown telemetry.

`unexpected_interventions` remains null: byte preservation and healthy HTTP probes
are not independent proof of authenticated host-wide intervention coverage. Current
all-channel correlation, genuine product oracles, native boot/reboot/mount windows
and actual campaigns remain separate unfinished qualification. Full replay is
bounded to 128 MiB; longer campaigns need a bounded continuation verifier before
that limit, never a silently truncated successful report.

Qwen job 081 authored a pure configuration-validator candidate on Omniverse2. The
candidate accepted integer subclasses; independent review corrected strict integer
checks and explicitly checked source-value strings. All source/gate decisions remain
deterministic. This assistance is not author-role qualification or measured learning
benefit. Prior spent studies remain spent. No candidate code was automatically applied.
