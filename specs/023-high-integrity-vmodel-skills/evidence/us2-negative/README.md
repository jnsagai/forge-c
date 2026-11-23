# T053: US2-AS3 negative cases (driver mode)

`run_us2_negative.sh <package> <work>` writes `us2-negative.txt`. No model is involved.

| Case | Result |
|---|---|
| 1. The reference document does not exist | `hi init` exits 2: `input docs/rm.pdf does not exist`. No project is written. |
| 2. The file exists but is not a PDF | `hi init` exits 2: `not a readable PDF (no PDF header)`. No project and no index. |
| 3. A readable document (generated, no vendor content), cited, but no `hi doc-index` run | `hi gate sw-req` gives `doc-sources` **NOT_RUN** and the stage verdict FAIL. |

In case 3, `governance` fails because this bare project has no governance package, and `scope` is NOT_RUN because
the work folder is not a git repository. Neither is ever counted as a pass.

**Defect found and fixed:** before this task, `hi init` accepted a file that was not a PDF. Only the later `hi
doc-index` refused it (DOC-UNREADABLE), so the stop did not happen at intake as US2-AS3 requires. `hi init` now
checks two things:
- every `.pdf` reference document starts with the PDF header;
- when poppler is installed, `pdfinfo` can read the file.

Without poppler it warns that the source gate will be NOT_RUN. Test:
`test_intake_refuses_a_missing_or_unreadable_reference_document`.
