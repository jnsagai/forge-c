# Valid native compile calls denied by mismatched default arguments

Exact inactive fix **50a4813d8d66d6af31e61f78e7eb0678e2eb3e5d**.
Actual comparison runtime remains0e; this is not a new model qualification or
measured improvement. No running job/source/profile/inputs/tickets changed.

Native07 df_author_0 requested host-clang and target-cm55-gcc compile with only
profile arguments. Hook audit recorded ALLOW_MCP/swe3-author, but both tools
returned BLOCKED/NO_AUTHORIZATION_TICKET. Actual runtime read-only reproduction
shows sdk.args_digest differs after MCP injects defines=[], because old
normalize_args compares FieldInfo.default (Undefined) instead of builtin
container factory defaults. Source0e, unchanged candidate70d55587..., native
calls, policy events and differing argument hashes are bound in diagnosisSHA
`057222ec6fb3967e46e41daece3f0642dc5093328149550785ea28cb119c68cc`.
No compile/model request, ticket issuance/consumption or workspace write was
performed by this diagnosis; it wrote only external observation metadata.

Separate captured native03/05/06 normal compile outcomes each contain3BLOCKED
calls, all NO_AUTHORIZATION_TICKET; original observationSHA
`bf9504075367e07a2fbaaf917dd4549d2babf75d249c726f1ecb0d27c2abeb0a`.
This is a generic factory wrapper defect, not an observed driver syntax error
or proof that Qwen cannot write these functions. Their independently invoked
functional checks and authored unit/target test tools are separate. Missing
normal objects/stack files are consistent with denied compilation, not a
measured resource overflow. Existing gaps/gates/archive results stay unchanged.

Fix: existing argument normalization treats builtin list/dict factory defaults
like constant defaults on both hook/server sides. Nondefault arguments remain
hash-bound and tickets remain one-time; arbitrary/context factories are not
executed while authenticating arguments. No authority bypass, new ticket store
or replacement protocol. This belongs in the next quiescent deployment only;
do not hotpatch frozen trials or reuse outstanding tickets across versions.

Four meaningful tests failed before: actual MCP registration/call injects the
empty list and blocks an authorized synthetic handler, plus list/map hash
counterexamples. Fixed focused4PASS. Exact committed source: **77PASS/2SKIP,
zero failures/errors,24.346s** across79cases; skips are inherited live Fabro
tests explicitly disabled. Actual SDK/MCP calls use a synthetic handler and
no compiler/model; inherited build tests use supplied fixtures on loop10.
Additional exact case proves custom default factories never run in hashing.
Changed source/new test Ruff PASS. Precommit76PASS/2SKIP overlaps exact cohort;
do not add counts or call disabled native tests qualified.

Original deadline07:57:59UTC and cumulative charges/uncertainty remain binding.
Scoped M1 and fresh1/3 result remain separate from full LL/HAL, release,
unattended self-healing, learning benefit and24/7availability, still unproven.
Raw receipts are deterministic gzip; representations.json binds decompressed
original bytes and readable views. Commands/results and failures are retained.
