# Source separation validation — 2026-10-21

Scope: initial feature-010 specification and source-reference delivery. This record is not a local RTX benchmark
or a live regression of the Codex/Claude service.

| Check | Result | Evidence |
|---|---|---|
| Starting source | PASS | main SHA `86f1f40c030bc721e7e5125a572d69647c4ac041`, tree `aedbf050d1fee9a9fedf1544cfb7996877298dcf` |
| Preserved reference | PASS | GitHub branches read-back resolves `baseline/codex-claude-2026-10-21` to the starting SHA |
| Local branch ancestry | PASS | `feat/010-local-rtx-optimization` created from the same SHA; initial read-back confirmed it |
| Existing tracked files | PASS | `git diff --exit-code 86f1f40c030bc721e7e5125a572d69647c4ac041 -- .` exited 0 before committing the new files |
| Representative source fingerprints | PASS | All 19 SHA-256 values in `baseline.json` recomputed from the original Git objects and checked against the checkout |
| Documentation references | PASS | Authored relative Markdown links resolved to existing files |
| Existing design contracts | PASS | `tests/spec/validate_design.py`: 14 tests, exit 0; static design only |
| Runtime code or service change | NONE | Only new specification, decision, baseline and entry-point documentation files added |
| Host snapshot / external archive verification | NOT_RUN | RTX host and its data volume not accessible from this checkout |
| New optimized local inference / quality | NOT_RUN | Runtime implementation is pending |
| Live Codex/Claude regression | NOT_RUN | Existing evidence was read; no new provider calls or deployed service actions performed |

Static validation command executed from the repository checkout:

```bash
PYTHONPATH=/workspace/scratch/f34f6de2be86/design-check-deps:factory/python python3 tests/spec/validate_design.py
```

Environment: Python 3.12.14, PyYAML 6.0.3, jsonschema 4.26.0 (installed in a separate temporary dependency directory).
This is a static-check environment, not a replacement for the factory's pinned deployment environment.

To recheck source fingerprints:

```bash
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

manifest = json.loads(Path('specs/010-local-rtx-optimization/baseline.json').read_text())
for item in manifest['representative_source_sha256']:
    actual = hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()
    assert actual == item['sha256'], item['path']
print('PASS: initial separation preserves the recorded source fingerprints')
PY
```

Later runtime development can intentionally change source files in the experimental branch. At that point these
fingerprints still identify the preserved reference; executable compatibility tests must establish that existing
behavior is retained. Do not rewrite historical fingerprints to hide changes or mark pending tasks complete.

## Implementation validation — 2026-10-21 (owner host, loop10)

| Check | Result | Evidence |
|---|---|---|
| Host preservation (T003) | PASS | `evidence/v0.4/runs/LRTX-T003/` (deployment checkout 86f1f40 clean; 208 archives copied and verified; rc4 restore re-hashed 238/238) |
| Compatibility of the existing line (T004) | PASS | `evidence/v0.4/runs/LRTX-T004/` (21 frozen workflow/provider fixtures, ACP/provider tests, v0.1, v0.3 packager, design check) |
| Explicit profile, isolation, provenance, network denial (T005-T008) | PASS | `LRTX-T005..T008`; baseline run `LRTX-TRIAL/lrtx1` verified on 8 checks |
| Admission, queue, cancellation (T009) | PASS | `LRTX-T009` (tests) and live queue/cancel probe |
| Structured SWE.1/SWE.2 authors and inspectors (T011, T013-T015, T017-T020) | PASS with scripted models | `LRTX-T011..T020`; the unchanged gates freeze the assembled work products |
| Replay triage of the QWEN-TRIAL rejections (T016, first part) | PASS (14 codes, none untriaged) | `LRTX-T016-REPLAY/replay.json` |
| Promotion (CRE) | ELIGIBLE | pd-72f598aa1dc971b146cb (P0+P1), pd-b6853328caf1e2190ecf (P2+P3); pd-7f4521cc52c2676c4638 REJECTED by host memory exhaustion (local model loaded), not by the change |
| Measurement split, residency, memory pressure, GPU energy (T010) | PASS | `LRTX-T010` (tests); `LRTX-TRIAL/lrtx6|lrtx7/metrics.json` (live) |
| Structured-output capability probe (T012) | PASS | `LRTX-T012` (tests) and the live probe record of qwen3-coder:30b |
| Structured SWE.3-SWE.6 for LL (T022) | PASS with scripted models | `LRTX-T022`; the real tools, Renode, Robot and the unchanged gates |
| Existing deployment preserved (T025, host check part) | PASS (re-run 2026-10-21 22:01 UTC) | `LRTX-T025-HOSTCHECK` (checkout unchanged, configs, 208 archives, no profile work order or archive in the deployment, services, network DENIED_VERIFIED, dry-run rollback of the profile root and all 16 profile run worktrees without conflicts) |
| Promotion (CRE), later candidates | ELIGIBLE | pd-5bfcdeab..., pd-118fefed..., pd-7cc602f1..., pd-82e141b7..., pd-4d89b29d..., pd-0d218f28..., pd-2213d82c..., pd-e853a842..., pd-9a54ade5..., pd-602dbedc..., pd-5a91e536..., pd-414b3233... |
| Local model quality (structured SWE.1 on qwen3-coder:30b) | BLOCKED (lrtx1-lrtx7) | `LRTX-TRIAL/README.md`; lrtx7 froze SWE.1 on its first visit, then factory inspection defects blocked it (fixed) |
| Model routing per task (T023) | PASS (measured; no routing proposed) | `LRTX-T023` (qwen3:8b 0/3 SWE.1 visits pass, cross-cutting task never valid; qwen3-coder:30b 3/3 frozen; derived mixed routing 575 s vs 541 s for 30B alone) |
| Local model quality, lrtx8-lrtx10 and QM lrtxq1/lrtxq2 (T016) | BLOCKED by the structured Qwen inspector | `LRTX-TRIAL/README.md`; the author froze SWE.1 on the first visit in lrtx7-lrtxq2; the inspector rewords refuted findings and changes verdicts between visits (NOT_QUALIFIED); under QM 7/8 items pass at the first inspection |
| Fresh local SWE.2 author trials (T016) | PASS (measured; 1/3 frozen) | `LRTX-T016-SWE2` (on a frozen READY rc1 SWE.1 baseline; trial 1 0/3, actionable-finding fix pd-5a91e536, trial 2 1/3 frozen by the unchanged SWE.2 author gate) |
| Seeded defects on independent holdouts (T021) | PASS (measured; local inspector NOT_QUALIFIED) | `LRTX-T021` (2 READY rc1 LL holdouts, 9 seeded cases: 2 deterministic, 1 inspection on target, 4 off target, 2 missed; both clean holdouts falsely rejected; holdouts unchanged) |
| 30-case campaign | NOT_RUN (owner hold 2026-10-21) | T024 |
