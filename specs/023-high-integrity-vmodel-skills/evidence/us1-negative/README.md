# T042: quickstart V3 negative cases

`APM=<apm> sh run_negative.sh <ready-project> <work>` writes `negative-cases.txt`. The base is the sealed, READY run 6
project. Each case runs on a fresh copy with the current package installed and a clean commit. No model is involved.

| Case | Expected | Result |
|---|---|---|
| 0. Unchanged copy | READY | `hi seal` READY_FOR_OFFLINE_REVIEW, 81 files, 0 gaps |
| 1. Delete one trace link (`SWR-TIM-001` no longer cites `SYS-SUP-002`, which only it refined) | trace FAIL, seal BLOCKED naming the item | `hi trace` FAIL: TR-UNCOVERED `SYS-SUP-002`, TR-SUSPECT `SWR-TIM-001`. `hi seal` BLOCKED: CHANGED-AFTER-INSPECTION, TRACE-SUSPECT, GATE-FAIL trace |
| 2a. A required gate that cannot run: a document is declared and cited, but no index exists | NOT_RUN, then BLOCKED, never PASS | `hi gate sw-req`: doc-sources **NOT_RUN**. `hi seal` BLOCKED with GATE-NOT-RUN `sw-req/doc-sources` |
| 2b. Building the index without poppler | NOT_RUN | `hi doc-index` NOT_RUN: "poppler (pdfinfo, pdftotext) is not installed" |
| 3. A write outside the author's scope | the hook denies it; when bypassed, the scope gate fails | guard exit 2 for `src/supervisor.c` and exit 0 for `hi/sys-req/notes.md`. A direct write gives `hi scope` FAIL, SCOPE-OUTSIDE `src/supervisor.c` |

Deviation from the quickstart: it names a switch `HI_FORCE_NOT_RUN=doc-index`, which was never implemented. Case 2
produces NOT_RUN the way a user meets it instead: a missing index (2a) and missing poppler (2b).

**Defect found and fixed** (4279db11): `hi` run inside a consumer project left `__pycache__` in the installed
skills, and the git-mode scope gate then reported those files as writes outside every role's scope. The entry
scripts no longer write bytecode.

**Notes on the script:**
- APM refuses to redeploy into a copied project. Its receipts in the user's `~/.apm` bind the original project.
- So each copy gets its own APM home, and its deployed skills are removed before `apm install`.
