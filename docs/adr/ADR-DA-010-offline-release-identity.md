# ADR-DA-010: Bind offline patch activation to the complete reviewed release

Date: 2026-11-05. Status: source candidate; qualification is recorded separately.

The offline importer previously checked only paths listed in a signed patch and
then copied the entire installed release. An unrelated local edit could therefore
survive under the reviewed target revision, even when the declared tests passed.

Use the existing signed CRE decision's `baseline_sha256` and `candidate_sha256`.
These identify the complete Git tree listing, including blob identities, executable
bits and symlink text. Reconstruct that listing from installed files without a Git
database or network access. Refuse decisions lacking either content identity.

Verify the complete baseline before reading its protection policy. Verify the staged
target before and after the configured local preflight and declared regression.
Recheck the baseline and current pointer before activation. A process lock serializes
the public import and rollback commands; the current pointer must resolve to the
corresponding release directory. Existing signature, per-file, CRE, protected-path,
atomic activation, previous-release and durable import-record checks remain required.

Releases are clean code-only archives. No ambient ignore rule hides extra files.
Dependencies, models, owner-provided references, keys, mutable state and test outputs
must be provisioned outside releases. Checks must leave the reviewed tree unchanged;
Python bytecode generation is disabled for the normal local subprocess checks.
Existing Forge-C tests requiring ignored inputs inside the checkout need explicit
external-input routing before being usable as this importer's local test scope.
Missing local dependencies are a qualification blocker, never an online fetch.

Unchanged symlinks retain their Git identity. This bundle version cannot represent
changed symlinks or Git submodules; an exact target mismatch refuses them. Git
metadata and filesystem special files are not valid installed release artifacts.

This change qualifies source behavior only. It does not activate a live patch,
change a grant, alter clock checks or establish the complete offline round trip.
