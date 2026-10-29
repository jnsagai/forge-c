# Larger AFO limits sized from recorded Codex driver files

Owner requested substantially larger paging/tool allowances, then asked to size
them against drivers from the Codex workflow. Runtime revision
**979dcb406353b5c779cd7b61964e3e5f39add454** is **active on Omniverse2**.
Conductor is active, operator RUNNING epoch38; Qwen/gateway/Fabro remain healthy.
The same provider instance was retained. No new order, model request, grant,
mission refill or deadline extension was made. Self-healing remains unproven.

| AFO setting | Previous | Active |
| --- | ---: | ---: |
| Target page, characters | 1000 | **32768** |
| Serialized tool-response text, bytes | 2048 | **65536** |
| Maintenance tool calls per visit | 20 | **200** |
| Diagnosis tool calls per visit | 8 | **200** |
| Source-read ceiling, bytes | 65536 | **4194304** |

Pages shrink when necessary to fit the actual JSON serialization, including
Unicode/ASCII escaping and all metadata. Every page retains complete hash, total,
offset and next-offset fields; no truncated page is accepted. The reader performs
bounded file IO and can address the tail of a3.6MB source file. Write, path,
credential, isolation and review permissions are preserved. This changes explicit
AFO role budgets through the existing token policy; base SWE-role defaults remain
2048bytes. The agent registry and versioned SKILLs/hash lock agree on200calls and
65536bytes. Skills explain the bound cumulative job allowance and exact compact
next_action enum. Individual model-request context admission remains131072 on
the active profile; a larger source-read ceiling is not a larger model context.

## Actual Codex-workflow source-size census

[Complete metadata](driver-source-sizes.json) and [summary](driver-size-summary.json)
come from **92local workspaces** with an explicit recorded Codex author adapter:
882C/C++/header/assembly observations, including192driver-file observations
(96distinct contents). Inputs/vendor and vendor/build/third_party trees, symlinks
and non-source files were excluded. No source content was published or modified.

| Observed category | Largest file | Bytes | 32768-character pages for this ASCII file |
| --- | --- | ---: | ---: |
| Workflow output outside declared ST delivery files | stm32n6xx_hal_rcc.c | **7278** | **1** |
| Declared delivered driver | stm32n6xx_ll_rcc.h | **340069** | **11** |
| Device header present in test scaffolding | stm32n657xx.h | **3599048** | **110** |

Other large delivered drivers include LL TIM283668bytes and HAL TIM264233bytes.
Delivered ST source is distinct from newly authored code. Recorded author
configuration does not prove authorship of every byte, independent review,
passing gates or an accepted product. These are observed workspace bytes at the
recorded time, not a benchmark score or an exhaustive maximum across other hosts.
The metadata includes hashes, model provenance and origin classification.

The read-only reproducer is
`factory/qualification/014/measure_codex_driver_files.py --state-root <workorders> --out <new-json>`.
It checks file size/mtime stability during each read and records warnings; this
census has zero read-instability/non-UTF8 warnings. All local outputs use loop10.

## Qualification of exact runtime979dcb4

- **13focused boundary tests PASS**: complete escaped JSON responses, Unicode and
  control characters, hash-bound reconstruction,7278-byte single-page source,
 340069-byte/11-page source, addressable3599048-byte tail, bounded4MiB rejection,
  preserved write/protected-path limits, actual blocking hook allows200calls then
  refuses201, native filesystem tools remain denied, skill/policy consistency
  and malformed allowance refusal. These are included in the larger cohort.
- Local reconciled cohort: **153PASS/1SKIP**,154distinct cases. The initial cohort
  had152PASS/1FAIL/1SKIP because FORGE_FABRO_BIN was absent from the test environment.
  With the actual installed Fabro0.362binary supplied, that exact failed graph/
  skill/MCP-preflight case passed. No runtime source change was needed. Original
  failed XML/log and corrected single-case XML/log are preserved.
- Final native cohort: **152PASS/2SKIP**,154matching case IDs, zero failures/errors,
 302.052seconds. Skips are explicit: rootless-Podman-specific verification is not
  available on this host, and live model-driven Fabro testing was disabled.
- The first native cohort had151PASS/1FAIL/2SKIP: the reused root-mapped CPU runner
  exposed namespace UID0 with effective DAC capabilities. Its read-only-file
  permission test failed correctly. A synthetic [permission probe](native-initial/permission-probe.json)
  demonstrates UID0/write-access versus actual UID1000/no effective capabilities/
  no write-access. The corrected runner maps the current user, retains private
  PID/network namespaces and reruns the entire cohort; no test was relaxed.
- The transport checksum guard also rejected an incomplete staging copy before
  clone/tests. The completed source bundle was verified and copied again. Its
  failed guard and hash recheck are retained. None of these setup corrections
  changed production or generated a model request.
- Native runs use finite deadlines,8CPU affinity/nice10, mounted-volume init and
  continuous guards requiring unchanged RUNNING epoch36/provider instance and no
  inference/request/verifier owner. Qualification cannot contact the model.
  Static specification/contracts/design and Ruff pass separately; they are not
  native model-role qualification. Full commands and XML are in the evidence.

## Activation and remaining work

[Activation scope/receipt](activation/activation.json) records the explicit owner
instructions, exact qualified source, source-size basis and preserved histories.
Fenced PAUSED37 allowed the source fast-forward and fresh-process role preflight;
RUNNING38 restarted only Conductor. The provider stayed loaded, with no instance
replacement. [Installed limits](activation/installed-limits.json) and
[post-activation audit](after-activation.json) confirm active source/health, zero
pending requests and unchanged mission:4product attempts/2maintenance jobs/
371requests/401131072conservative charged tokens, historical aggregate UNKNOWN.
The existing22:25:58UTC execution expiry remains unchanged.

The previous two failed model trials and their reservations were not refilled or
reclassified. No new Qwen repair trial was launched. Another trial needs its
normal fresh source-bound role/intake records and factual evidence; it must keep
the original mission and finite current window. Source inventory/navigation work
and real independent candidate verification remain distinct from these size and
budget changes. No task acceptance, model capability, product success, learning
benefit or long-duration availability proof is newly claimed.

Initial local failure XML/log strip trailing whitespace for publication only;
[original/published hashes](publication.json) bind that normalization. Original
raw files remain in the private loop10 operations directory.
