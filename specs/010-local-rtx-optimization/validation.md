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
