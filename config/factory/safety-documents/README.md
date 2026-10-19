# Owner-signed safety documents

Owner decision OD-2026-10-19-11. An ASIL work order needs a software safety analysis and a tool assurance
assessment. They are written for the **product** (one safety scope in `config/factory/safety-scope.yaml`), not for
each run, and a competent human is responsible for them. An AI may draft them; only the owner's signature makes
them count.

## Layout

`<scope_id>/software_safety_analysis.md` and `<scope_id>/tool_assurance_assessment.md`, registered under
`safety_documents` in the scope decision.

## How a document counts

A new work order receives a document (read-only, at `safety/<name>.md`) only when all of these hold:

1. The register entry has `approved_by` (a human, never an agent), `approved_at` and `sha256`.
2. The file still has that SHA-256: any edit after signing un-signs it.
3. The entry's `basis` equals the work order's source requirements hash. A change to the work order inputs
   un-signs it until it is re-reviewed.
4. The file no longer carries the draft marker (`DRAFT … not approved` on the status line).

Anything else is recorded in the work order manifest (`owner_safety_document_issues`) and in the package's
`safety/known_limitations.md`, and the package stays BLOCKED on the missing document. The packager also removes
any other file at those paths, so only the signed version can be packaged.

## Signing

1. Review the draft. Correct it where needed, answer its open questions, fill in the review and signature section,
   and replace the draft status line with the decision (for example "Approved with open findings").
2. The owner records the decision. On the owner's instruction the register entry is completed with the reviewer's
   name, the date, the file's SHA-256 and the decision id, in an "Owner decision" commit.
3. The change goes through the CRE promotion gate like any factory change. The next RCC work order picks the
   document up.

A signed document records the reviewer's engineering judgement. It is not a safety approval, a release decision or
a certification.
