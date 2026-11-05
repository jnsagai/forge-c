# Manual offline improvement

Omniverse uses its provisioned local models, Python environment and tools. Export
finished work for external analysis, then carry an explicitly reviewed update back.
These commands do not fetch packages, contact a model provider or change networking.

## Export a report and its evidence

Use the installed Forge-C Python environment from its trusted checkout:

```sh
python -m forge_factory.offline.export \
  --run /path/to/finished-workorder/workspace \
  --out /path/to/outgoing/report.zip
python -m forge_factory.offline.export --verify /path/to/outgoing/report.zip
```

Transfer `report.md`, `report.zip` and `report.zip.sha256`. The Markdown contains run
identities, all sanitized structured decisions, findings, attempts and usage records,
and the complete evidence inventory. It is also `REPORT.md` inside the hash-listed
ZIP. Exporting unchanged runs again produces the same bytes. Verification checks that
a supplied report agrees with the bundled evidence. Older v1 bundles remain readable.

The factory identity identifies the exporter revision. Historical run identities and
profiles are retained in their own records; exporting does not rerun an old workflow
or establish its success. Missing/unparseable records confer no PASS. Unparseable
record portions are counted and omitted from the human report. Vendor inputs and
other excluded files travel only as hashes; raw prompts/reasoning keys are stripped
and secrets redacted according to the existing export policy.

## Prepare a reviewed return package in development

Reproduce the finding from the evidence and unchanged frozen inputs. Implement and
test the correction through the existing CRE process. A qualifying decision must
identify exactly the installed base and proposed target, including both complete
tree digests. Then build:

```sh
python -m forge_factory.offline.patch build \
  --repo /path/to/development-checkout --base BASE_COMMIT --target TARGET_COMMIT \
  --regression factory/python/tests/test_da014_offline_export.py \
  --regression factory/python/tests/test_da014_offline_patch.py \
  --regression factory/python/tests/test_da014_offline_disposition.py \
  --cre-decision /path/to/qualified-decision.json --approver OWNER_PRINCIPAL \
  --out /path/to/return/update.zip --runner-out /path/to/return/apply-update.py
```

The owner signs the canonical manifest through the existing owner-only signing
command. Transfer the bundle, detached `update.zip.sig`, and the reviewed runner.
The build receipt prints the runner hash. The runner is part of the trusted tooling
and must be reviewed/pinned separately; the bundle signature authenticates the patch
manifest and its referenced contents, not an arbitrary companion script.

## Apply locally and retain rollback

This importer expects an install-root containing clean code-only archives at
`releases/<commit>/` and a `current` symlink. A development checkout is not this
install layout. Models, dependencies, licensed inputs, keys, mutable state and test
outputs remain outside releases. Provision everything needed before isolation.
There is no automatic adoption or live-service restart in these commands.

Run the transferred script with the already installed Forge-C Python environment:

```sh
python /path/to/return/apply-update.py apply \
  --install-root /path/to/install --bundle /path/to/return/update.zip \
  --allowed-signers /path/to/local-public-allowed-signers \
  --preflight-cmd 'python tests/spec/validate_design.py'
python /path/to/return/apply-update.py rollback --install-root /path/to/install
```

By default the runner invokes the trusted verifier in `current`; `--runtime-root`
selects a different already trusted local verifier explicitly. The verifier validates
the signature, CRE decision, base/target identities, all files and deployed protected
paths. It runs the explicitly configured preflight and declared regression in the
staged release, confirms that checks left its tree unchanged, and switches `current`
atomically. `imports/log.jsonl` retains rejection, activation and rollback receipts.
Checks requiring checkout-local ignored inputs need explicit external-input routing;
their absence is a failure, never permission to fetch them or conceal local drift.

## Verification scope

The CPU integration fixture performs real subprocess execution, export, development
replay, TEST signing, transfer, import and rollback inside a separate kernel network
namespace. It checks no-route failure and seven rejection paths. Synthetic fixture
CRE metadata does not replace the separate normal CRE qualification of the actual
source. Actual Omniverse model competence, live work, offline cold-start/time handling
and the authored endurance campaigns require their own acceptance evidence.

## Turn the owner's review into preventive learning

Record each reviewed gap/finding using the existing
`specs/014-durable-local-autonomy/contracts/review-disposition.schema.json`.
The owner signs it in the separate `forge-review-disposition` namespace. Route
the signed records against the exact export:

```sh
python -m forge_factory.offline.disposition route /path/to/signed-reviews \
  --bundle /path/to/report.zip --out /path/to/learning-intake.jsonl \
  --allowed-signers /path/to/local-public-review-signers
```

Confirmed defects and confirmed false findings open evidence-linked corrective
CAPAs with an UNKNOWN root cause. Missing-input and out-of-scope decisions remain
review facts. The command archives the verified review, public signature/signers
and exact export, deduplicates repeated subjects, refuses changed content under
an existing review ID, and can recover an interrupted JSONL projection from CRE.
Raw rationale never becomes a root-cause finding or lesson automatically.

Set membership replays protected registrations and their exact source hashes.
The nine spent F011 subset baselines and the spent F015 GPIOA/CRC pair already
have explicit post-calibration learning registrations; the remaining thirteen
F011 cases stay excluded. Missing/inconsistent registration or incomplete
calibration evidence refuses intake. Historical packages, test sets and rates
remain unchanged; these transitions confer no new held-out measurement result
or permission to distill an ordinary positive example from evaluation evidence.

After the existing independent CRE process actually reproduces and tests a fix:

```sh
python -m forge_factory.offline.disposition qualify-capa \
  --capa CAPA-HR-ID --decision pd-QUALIFIED --reproducer RPR-ID
python -m forge_factory.offline.disposition publish-lesson \
  --capa CAPA-HR-ID --workspace /path/to/prepared-future-training-workspace \
  --role swe1-author
```

Qualification consumes an existing eligible FIX decision, all seven hard gates,
its exact baseline/candidate/prevention runner records and hash-matching raw logs.
The normal guarded CAPA lifecycle verifies the cause and registers prevention.
This command fabricates no run or approval and applies no patch. For a newly
staged maintainer reproducer, provide `--staged-manifest` and
`--lesson-description` (a JSON object containing the curated `root_cause`,
`remedy`, `operations` and `error_codes`). Its script must equal the committed
candidate source; the immutable descriptor is retained for later validation.
Qualified staged tests are registered for subsequent CRE prevention gates, in
addition to every protected global oracle. A missing or changed registered
descriptor/script refuses qualification rather than dropping the test.

Publication uses the qualified frozen remedy through the existing deterministic
lesson curator. It requires explicit phase/role/target, unchanged input hashes
and tool identities; new work orders record their factory revision as a tool
identity. Missing identities or a held-out destination refuse publication.
Unsafe explanations are quarantined. Matching future author/recovery/maintainer
contexts retrieve bounded reference data through the existing knowledge MCP;
the independent inspector path remains separately governed. New versions/scopes
require explicit revalidation, rather than silent transfer of old memory.

The existing generic and local-line learning cycles reconcile reviewed CAPAs
against completed packages and recorded source/operation exposures. A recurrence
on a revision containing the fix reopens the CAPA and retracts its lessons. The
clean effectiveness window is distinct from source qualification and from any
claim of measured learning benefit. Reconciliation is bounded, rotates through
CAPAs, uses existing stores, and makes zero model calls.
