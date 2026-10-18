# ISO 26262-6:2018 normative reconciliation plan (EASA-T002)

## Availability

| Item | 2026-10-17 | 2026-10-18 |
|---|---|---|
| Copy of ISO 26262-6:2018 | NOT AVAILABLE | Registered by the owner by path outside the repository (`FORGE_ISO26262_6_2018_PATH`), sha256 `5faf4306eaed584c614e0751ba28318099aeb1943bf2bbc14fe4653527f2ca40`. OCR text conversion; licence status asserted by the owner, not verified by the factory. |
| Reviewer worksheet | - | `evidence/easa/normative/worksheet-5faf4306eaed584c.json`: 15/15 tables identical to the catalog (row ids and rating symbols only; footnotes, alternatives and combinations left to the reviewer) |
| Reconciliation | BLOCKED | All 15 tables signed by Jefferson Nascimento (Safety Authority; ISO 26262 personal qualification as stated by the reviewer, 2026-10-18) through `catalog.reconcile()`; decisions in `evidence/easa/normative/reconciliation-decisions-2026-10-18.json`, derived versions `catalog-v01..v15.json` |
| Catalog status | SECONDARY_WORKING_INDEX | CONTROLLED_RECONCILED (47/47 entries normatively checked) |

## Copyright boundary
- The repository stores only table and row identifiers plus short original paraphrases. No clause text, table text
  or footnotes are stored.
- A licensed copy may be registered only by path, outside the repository. `normative.standard_access()` refuses a
  path inside the repository (`REJECTED_IN_REPOSITORY`) and records only its sha256.

## Reconciliation procedure
1. The owner registers the licensed copy (`FORGE_ISO26262_6_2018_PATH`) on the reviewer's host and records its
   sha256.
2. A competent safety reviewer reconciles one whole table at a time:
   - row identity;
   - A/B/C/D recommendations;
   - alternatives and combinations;
   - footnotes and applicability notes.

   The reviewer must be a named human with a competence reference; an agent id is refused.
3. The reconciliation is submitted through `catalog.reconcile()` with the licensed-copy sha256. Partial tables, an
   unregistered or mismatched source, an agent reviewer or an invalid rating are rejected and recorded.
4. Each accepted table produces a new derived catalog version. The authored spec file is never edited, and the
   decision is stored append-only with before/after digests. The catalog becomes `CONTROLLED_RECONCILED` only when
   all 15 tables are reconciled.
5. Applicability decisions, claims and gates bound to the old catalog digest are invalidated through the impact
   graph and re-evaluated.

## What reconciliation does not do
It doesn't authorize any ISO 26262 compliance, ASIL approval or certification statement by the factory.
`assert_normative_claim()` always rejects compliance assertions. The published result is bounded engineering
evidence for offline human review (EASA-FR-071).
