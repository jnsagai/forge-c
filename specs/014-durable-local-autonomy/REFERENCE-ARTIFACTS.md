# Phase references from completed cloud jobs

Owner direction, 2026-10-28: use small verified Codex/Claude examples as Qwen
context. Keep the existing knowledge store, curator and independent qualification
path. A successful source job does not demonstrate that an example transfers or
improves Qwen's result.

`forge_factory.knowledge.references` prepares an ordinary-outcome lesson candidate.
It verifies the source's READY package and archive/member hashes, current phase
gate, frozen artifact and native execution identity. It selects one complete
section of at most 700 characters rather than truncating a document. The full
source archive remains external and hash-bound. Source revision, artifact hash,
selection hash, classification and baseline are retained as factual experience.

The selection must declare a training reference and explicit destination phase,
author, source versions, target and tool versions. Requirements authors and all
inspectors are excluded. Only phase work products on the allowlist are accepted;
inspection verdict files, driver implementations and primary manuals are excluded.
Unknown classification is not treated as permission. Historical holdout reports
and append-only held-out experience override a newer training selection, even when
the original cloud manifest predates the `evaluation_holdout` field.

The CLI does not propose, promote or expose a lesson:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=factory/python \
  FORGE_STATE_DIR=/path/on/loop10/reference-preparation/state \
  python -m forge_factory.knowledge.references \
  --workspace /path/to/completed/cloud/workspace \
  --selection /path/to/explicit-selection.json \
  --out /path/on/loop10/reference-candidate.json
```

The selection contains `phase`, `role`, `artifact`, optional exact Markdown heading
`section`, `execution_id`, `archive_sha256`, `query`, `tool_versions`,
`classification` (`intended_use: TRAINING_REFERENCE`, `evaluation_holdout: false`,
and `record_ref`), and normal lesson `applicability`. Classification cannot be
chosen by a runtime model. Do not amend an existing held-out source to make it fit.

Next, qualify the exact candidate using `knowledge.qualification.record` and
independently produced applicable/adverse receipts bound to its content and source
experience. Only then supply those actual validation receipts and qualification
reference to the existing `LessonStore.propose` and `validate` APIs. Until then,
validation is NOT_RUN and the candidate cannot be retrieved. Legacy promoted
repair validation and separate inspector-lesson governance remain unchanged.

Qualified lessons use existing structured-packet/MCP retrieval, complete request
measurement, whole-block context omission and transactional exposure receipts.
Exposure, verified application and measured benefit remain separate. M2's
requirements author receives no reference answers. Learning comparisons must
exclude training sources and include retrieval, curation and qualification costs.

## Preparation result

The recorded CRC, SPI, USART and GPIO successful benchmark runs occur in historical
inspector holdouts and are excluded. The successful TIM run
`WO-AFO-c2fd276494a54e7f-a1` has no designation in the searched historical reports.
An explicit prospective training selection prepared its 540-character SWE.2
verification-handoff section (607 characters with the reference wrapper), scoped
to the IDR fixture's SWE.2 author and source identity. Its archive hash is
`995f31e322a1feb0370ecec97709424beab02c1d84102c02fae09b50113e4ad6`.

Status: **PENDING_INDEPENDENT_QUALIFICATION; not exposed to Qwen; benefit UNKNOWN**.
The preparation is stored on loop10 under
`operations/feature014/incremental-e2e-20261028/reference-preparation/`.
No production knowledge database, cloud benchmark workspace or remote deployment
was modified. This does not satisfy DA-T042 or M1 product acceptance.
