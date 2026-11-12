# Complete archive inventory verification

Exact independent auditor source **319e215417b8f7e0d329fb3ce71b595f0367f8ef**.
This is external package verification preparation for M1, not deployment or acceptance.

A concrete counterexample on25a93b6 removed a member still listed by SHA256SUMS.txt.
The old checker returned integrity PASS because it visited only surviving ZIP members.
The new regression therefore failed before the fix; raw output is under counterexample/.
The existing verifier now checks both sides of the inventory, rejects duplicate ZIP or
checksum entries and malformed/empty indexes, reports unreadable input as FAIL, and
streams member hashes. Existing external checksums and the integrity/readiness distinction
are retained. Unlisted or changed members still fail. No checksum authenticates its own
source; independently trusted archive hashes remain necessary for source identity.

The existing real package-builder regression also drops its required final-gates.json
while retaining its checksum entry; verification must FAIL. Other controls cover a
complete archive with/without a sidecar, absent or extra members, ambiguous duplicates,
bad index encoding/format, empty inventory and malformed/mismatching sidecars.

## Commands and results

Same focused archive and inherited governance/release cohort: **24PASS per host**,
zero failures/errors/skips and zero model calls. Local13.477s; isolated Omniverse250.327s.
Native checkout is clean before/after. See XML/logs and actual native provenance.

On the workstation, use loop10 for all data/state/output/TMPDIR. Point these variables
to the existing data root and Fabro installation; this suite makes no model request.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 FORGE_FABRO_LIVE=0 \
FORGE_FABRO_BIN="$FC014_FABRO" FORGE_FABRO_HOME="$FC014_FABRO_HOME" \
FABRO_NO_UPGRADE_CHECK=1 PYTHONPATH=factory/python \
FORGE_DATA_ROOT="$FC014_DATA" TMPDIR="$FC014_TMP" \
  python -m pytest -q factory/python/tests/test_archive_inventory.py \
  factory/python/tests/test_m7_governance_release.py --junitxml="$FC014_OUTPUT/pytest.xml"
```

Initial setup failures are preserved, not counted as passes: local23PASS/1FAIL because
Fabro was absent from the executable lookup; native21PASS/3FAIL because the isolated
data root lacked the existing pinned PlantUML mapping. Correcting those prerequisites
required no source, verdict or test-expectation change. The final native script binds
that toolchain and PATH; both native producer scripts are included under scripts/.

Spec/contracts58mappings/sixschemas/38fixtures,14static design checks and selected Ruff
pass separately. They are not runtime or model qualification.

## Actual private archive recheck

On Omniverse2, the new exact auditor recomputed the existing f206 trial archive's
external checksum and complete internal inventory: **integrity PASS**, issues empty.
SHA2561a406bbd48e75c163a57207268ccfe774072d36164e77fda5bdbef43f14ab257.
The archive remains private and unchanged; no restricted primary-reference content,
credentials, hidden reasoning or raw prompts are published. Product acceptance remains
**BLOCKED at SWE.1**, downstream NOT_RUN, as in the prior terminal evidence. A complete
BLOCKED evidence packet is different from a correct or accepted delivered product.

## Current execution boundary

This fix is committed for independent audit, **not activated on production**. Production
is stillf206e3a. The separately qualified, prepared QM runtime remains5b398d2 and its
pending signing/activation scopef068de41…b642d is unchanged. This follow-up must not
silently substitute a newer source into that reviewed packet. The unsigned packet is
staged at deployment/idr-m1-qm-5b398d2-20261029 on Omniverse2; no signature was created.

Current M1 is unaccepted:0/2functions accepted through the real six-phase workflow.
IE-T001–007 completion and formal30/58 remain unchanged; IE-T008 unaccepted,
IE-T009/M2–M5 NOT_RUN. No model capability, learning benefit or availability claim.
