# Approved standing delegation: larger-context demonstration

Source **9b4c390e1605d11c4865bdeea382df74a0078692**; profile **local-rtx-v2-omniverse2-q38-qm-demo-mtp**, context **262144**, batch1024/microbatch512.
28PASS per host;0failures/errors/skips/inference. Prior untouched six-phase fixture
was qualified at15b0fa5. The new changes concern backend batches/context only.
Native complete graph validation PASS;14nodes/56 captures,
max complete conservative reservation77488/262144.
Actual zero-generation allocation PASS, Q8 weights/f16 cache/MTP3/xhigh unchanged,
1966MiB VRAM free. Model reports trained context262144.

The previous demonstration traversed all phases but native roles failed with
CAPABILITY_LIMIT before producing later artifacts. An admitted request already
used130842/131072 conservative context units; this raises input/tool headroom
from81920to212992. This is a material capacity change, not an identical retry.

Owner explicitly requested “increase any limiti to very higher values now” and
standing execution signing/activation approval: “always approve it for now on automatically”.
No further confirmation is required. Sign exactly:
- AUTH-014-IDR-QMDEMO-CTX262-9B4C390-20261029-V1
- AUTH-014-IDR-QMDEMO-CTX262-ROLES-9B4C390-20261029-V1

Activate this exact source/profile and dispatch one same-mission order **afo-774900b297bdde37**.
Continuation_of afo-d9ddb6d7a1c4e025; preserve3attempts,69requests,193tools,
300million conservative tokens and UNKNOWN historical aggregate usage.
Expiry remains **2026-10-29T18:05:39Z**, no reset/refill/window renewal.
Quality is still observational in the owner-selected full-pipeline demonstration;
final product remains explicitly unaccepted. Keep one inference and operator fencing.

ScopeSHA256 **71b48d33283655a68d9fc33dd65b750a6e1be1aa9bd81188a232d3e1a6ac5759**.
[Scope](scope.json), [plan](plan.json), [allocation binding](trial.json).
Private loop10 collector continues downloading complete real outcomes automatically.
