# Ornith Q8 speed study on Omniverse2

Owner request, 31 October 2026: test the downloaded
`hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0` across reasoning configurations.

**36/36 serial trials completed**: three synthetic cases × three seeds × four
settings. [Measured results and limits](SPEED-REPORT.md);
[per-trial CSV](trials.csv). No factory model selection or production activation.

| Setting | Median native decode tok/s | Median request seconds | Full task-contract passes / 9 |
|---|---:|---:|---:|
| Thinking off | 148.9 | 0.45 | 1 |
| 512 thinking tokens | 154.7 | 3.66 | 0 |
| 2048 thinking tokens | 153.9 | 13.71 | 2 |
| Default thinking | 153.3 | 21.25 | 4 |

The 2048-token setting answered all three review cases semantically correctly;
one used a markdown fence contrary to the JSON contract. Its semantic/functional
score is therefore 3/9, while its full-contract score remains 2/9. All other
semantic/functional totals equal the table. [Concrete findings](INTERPRETATION.md).

Default thinking includes **one truncated numeric trial at the common 8192 total
completion-token cap**, retained as a failed/incomplete case. Budgets are
experimental server controls, not trained low/medium/high/xhigh settings. The
actual embedded template has no reasoning_effort variable and those four named
levels render identically; thinking on/off changes the rendered prompt.

The GPU was an RTX 6000 Ada 48 GB, one 262144-context slot, f16 KV, all GPU layers
requested, MTP off, 12 generation/24 batch threads. Actual prompts were 159–539 tokens;
this does not measure full 262K-context throughput. Caching was requested off
and every measured cache_n was 0. Sampling and matched seeds are in the frozen
scope. Order rotates across repetitions, but this is not a fully balanced or
randomized controlled capability comparison; other host activity was not isolated.

The positive C oracle control passed 31878 checks; all three seeded-negative
controls failed as expected (21/223/1 assertions). These controls ran after GPU
measurements. Every timed API decode count/time matches the separate native
numeric log: 37 generations total, including one explicitly excluded warm-up.
55,297 completion tokens are reported across the 36 timed trials. Reasoning text
was discarded; only numeric re-tokenized thought counts and final answers remain.

Full model SHA256:
`de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3`.
The 37.8 GB GGUF was size- and hash-verified before timed trials. Runtime build
0.3.0-dev/0f3a71be1 and binary/library hashes are retained. The exact private
measurement script is bound by source_script_sha256 in benchmark-scope.json;
it was not a future Git revision or a production factory run.

## Artifacts and interpretation

- Native numeric timings, per-request usage, final answers and all generated C
  candidates, compiler/UBSan/oracle logs, positive/negative controls and scripts.
- Raw server.log, native executables and the full third-party chat template are
  excluded from this public text set. The private hash-verified transfer contains
  compiled artifacts for inspection; none was executed locally.
- Native server process ended, endpoint closed and GPU process absent.
  Factory intent remains STOPPED 7; the old mission stays 7 attempts/1470 requests/
  2583 tools/467140608 charged-reserved with uncertainty retained. No old grant was
  renewed or mission budget reset. This new explicit speed request authorized
  a separate measurement, not continuation of the expired factory campaign.
- Pass counts concern these three small standalone prompts only. There was no
  tool-assisted rework loop, native pipeline, general accuracy qualification,
  independently measured learning gain or operational availability campaign.
  Default thinking gave the strongest result here, but 4/9 is insufficient for a
  production-model recommendation. A representative tool-assisted qualification
  remains necessary before deploying Ornith in the factory.

Local full outcomes:
`B/operations/feature014/incremental-m1-followup-20261029/ornith-speed-20261031/`,
where B is the existing loop10 Forge-C data root. The private archive SHA is
bdbff40dda6f64cc9493ce145889abdfa9c2b2d3623fa51cfa86df7f879fb00d;
all205listed file hashes were verified on transfer.

No Feature014DA task is newly closed. The existing2/3tiny CRC cohort, incomplete
fullLL/HAL and stopped-job learning gap retain their previous status.
