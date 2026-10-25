# Feature 014 qualification inputs

Prepare concrete source cases in a new private data directory before freezing
and signing a campaign. This command requires a real C compiler and creates no
grant, mission, order, runtime job or inference request:

```bash
python -m forge_factory.afo.qualification_inputs \
  --out <new-private-directory> --compiler <pinned-clang> \
  --campaign-id <unique-protocol-campaign> \
  --authorization-ref <planned-owner-authorization-id>
```

Set `FORGE_STATE_DIR` and `FORGE_EVENTS_DIR` to private qualification directories.
On the local workstation all outputs must be on loop10. Native Qwen execution
belongs on Omniverse2. Freeze inputs on their final host: absolute paths are part
of the evidence and cannot be moved after sealing.

The generator materializes the frozen 20-case catalog with five repeats each,
deterministic prospective job identities, case hashes, intake envelopes, complete
evidence packets, requirement coverage and request measurements. The virtual
REG32 fixture is explicitly seeded qualification data, not an STM32 product
failure. A fixed compiled checker tests 260 register inputs and idempotence: the
seeded implementation fails 194 checks and the independent reference passes all
260. This limited oracle establishes the fixture counterexample; it proves no
product, model or operational capability.

Request measurements apply the selected profile's actual gateway transformation
to a copy of the request, including reasoning settings and output extensions.
The adapter sends the original request, so the gateway applies that transformation
once. Provider admission and mission accounting remain independent checks.

The selected Omniverse2 Qwen profile reserves 16,384 extra output tokens for high
reasoning. With the adapter's 2,048 answer tokens this alone exceeds the current
16,000-token diagnosis job reservation. Preparation reports
`COMPLETE_SERIALIZED_CASE_EXCEEDS_JOB_ENVELOPE`; it does not disable reasoning,
raise a reservation, or call the model. Any new qualification allowance must be
explicitly finite and authorized before the job's initial reservation. Existing
mission limits and exhausted history cannot be rebound.

For a distinct owner-approved qualification campaign, the optional
`--qualification-job-tokens <finite-tokens>` records prospective initial
reservations. It does not authorize them. Preparation emits `jobs.json` and
`requested-initial-reservations.json`; pass these to qualification `freeze` with
`--jobs` and `--job-token-reservations`, together with the exact identity and
`--input <directory>/inputs.json`. The owner signature must bind the resulting
manifest hash. Provisioning checks that signature, source/case/mission/model
identity, per-order policy cap and declared context before the first ledger
reservation. Rebinding an existing job's reservation remains forbidden. The
ordinary production path retains the registry allowance. Full campaign readiness
still requires every other prerequisite below.

Six response interventions are implemented at the native adapter boundary:
administrative-field forgery, empty content, truncated JSON, an unqualified
model switch, a genuinely distinct foreign case reference and a reworded tried
strategy. Enable only a declared per-trial mapping using qualification
`freeze --protocol-faults <json-file>`. Each entry must exactly match that seeded
case's prospective recipe; the owner signature binds the mapping. Ordinary
product cases cannot enable these controls. For example, `empty-output:0` maps to
`{"boundary":"after-provider-response","recipe":"drop-content"}`.

At execution the adapter rechecks the current signature, order/model scope,
job/case/nonce, policy, deadline and held native execution. The authoritative
evidence table retains original/injected visible-response hashes and the declared
intervention, without response text or hidden reasoning. Changed replays are
refused. Reports require matching exposure evidence as well as an independent
oracle audit. Injected responses do not establish unmodified model competence.
Unmodified empty or invalidly typed content is a protocol incident and cannot
create a semantic completion receipt.

Two pre-evidence interventions atomically replace only the frozen seeded
`software/hal/reg32.c`: a hash-stale file or a symlink to a fixed nonauthoritative
marker outside that fixture workspace. Both persist an immutable intent before
the effect and adopt an identical completed effect on replay. Parent paths,
regular-file type and bounded source size are checked; no external source is
read through the injected symlink. Tests interrupt both sides of replacement.
The original case and packet hashes remain unchanged so actual evidence access
must refuse the altered source. Reports require the matching source-fault fact
and its exact native incident code. A response fault likewise needs the specific
broker rejection code; an unrelated refusal cannot satisfy the case.

`inputs.json` includes prospective fault recipes. They are not executed fault
evidence. Revocation/expiry, lost launch acknowledgement and
cancellation-with-live-request interventions
remain unprovisioned, as does the independently measured authorized local
alternative; unresolved prerequisites block the full campaign. Dirty generator
source also blocks readiness. Pass `inputs.json` and
its exact `jobs` mapping to the existing qualification freeze operation; preflight
checks their readiness and effective model/reasoning identity. A prepared file,
successful compiler check or dry-run never qualifies the 100 native trials.
