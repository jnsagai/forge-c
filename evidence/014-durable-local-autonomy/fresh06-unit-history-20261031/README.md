# Fresh06unit repair: regrouped assertions, no driver change

Native01M67ZJWDYS7H33828MPTK6E6D remains a RUNNING fresh trial, not a terminal
delivery result. Producer0e342eef and frozen e52e3763... header are unchanged.
This records actual tools/protected test snapshots, copied/read/hashed locally;
no Qwen C was executed locally and no active job was steered or fixed manually.

At04:06:16UTC unit execution passed its executable, but duplicate UT IDs caused
the metadata resultFAIL. A second run still had duplicateUT-006; at04:08:38the
metadata/executable resultPASSed. The report author repeatedPASS at04:11:02.
LLVM host line/function/region coverage100%, branch/MC/DCnull, targetfalse.
Trace reports11/11draft requirements with5future test links planned; this is
not yet complete target/requirement qualification.

Static CHECK calls changed16 to6, distinct IDs6 to6. Qwen aggregated pattern/
preservation predicates into boolean accumulators and grouped IDs, rather than
only renaming duplicates. Primary register-preservation checks moved after
writing another instance. Checks for the other instance's RESERVED1/INIT/POL
remaining zero were added. The fixture snap comparison was removed. This differs
from prior05's mixed-coverage rewrite; do not copy its specific findings here.

The diff changes execution order and failure localization, so it is not called
an assertion-preserving ID-only fix. Static call counts do not establish dynamic
assertion coverage or total adequacy; no measured learning benefit is claimed.
The separately frozen independent630host/351target oracle remains the functional
authority. No test-adequacy experiments or candidate changes were supplied.

Original protected source hashes are in test-rewrite-observation.json and match
the exact failed/passedC files here. Both failed tool results and their actual
native event hashes are preserved. Native06's complete sealed package/final
recheck and DF-T010 repeatability evidence remain pending. Original expiry
07:57:59UTC and all3cohort members remain fixed.
