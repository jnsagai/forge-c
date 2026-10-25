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

`inputs.json` includes prospective fault recipes. They are not executed fault
evidence. Native boundary injection and the independently measured authorized
local alternative remain prerequisites; unresolved prerequisites block the full
campaign. Dirty generator source also blocks readiness. Pass `inputs.json` and
its exact `jobs` mapping to the existing qualification freeze operation; preflight
checks their readiness and effective model/reasoning identity. A prepared file,
successful compiler check or dry-run never qualifies the 100 native trials.
