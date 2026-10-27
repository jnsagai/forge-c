# ST3 local Qwen pilot — 2026-10-27

All three frozen ST LL work orders ran on Omniverse2 at clean source
`9a88fbc5b28864e45917cdc77f7e6ab9c9f59825`; **0/3 READY, 3/3 BLOCKED at SWE.1**,
59 package gaps each. GPU queue job 050 completed normally; that is runner completion,
not engineering success. The campaign hash and native run IDs are in [summary.json](summary.json).

Each run stopped after the same deterministic rejection repeated twice, including
missing `workproducts/SWE.1/register_effects.json` and the required traceability output.
These are author/output failures before the unsigned SSA/TAA release prerequisite
could establish the first blocking cause. Signing the safety drafts alone would not
resolve these SWE.1 failures. No signature, gate waiver, retry or inspector change was made.

The existing verifier checked local provider/model/namespace, metric capture and
sealed packages. Its PASS is execution/provenance verification, **not product acceptance**.
The pilot is neither the 30-product benchmark nor an operation-24 qualification.

Collection used read-only SSH access to the completed campaign summary and whitelisted
package/gate/artifact metadata. Public output contains no model prompts, hidden
reasoning, vendor source or credentials. Raw structured collection stays private on
loop10 at `operations/feature014/st3-collection-20261027/`. No historical attempt,
expenditure or uncertainty was reset. Inspector development remains frozen.
