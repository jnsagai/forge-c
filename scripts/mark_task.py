#!/usr/bin/env python3
"""Check a Spec Kit task box ONLY if its recorded evidence run(s) PASSED (CLAUDE.md rule).

Usage: scripts/mark_task.py <tasks.md> <TASK-ID> <evidence-task-name> [more evidence names...]
"""
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tasks, tid, names = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
refs = []
for n in names:
    rec = json.loads((root / "evidence/v0.4/runs" / n / "latest.json").read_text())
    if rec["status"] != "PASS" or rec["exit_code"] != 0:
        sys.exit(f"{tid} NOT MARKED — evidence {n} status {rec['status']}")
    refs.append(f"evidence/v0.4/runs/{n}/latest.json")
text = tasks.read_text()
# 002 '**T001**', 001 '`T-006`' and 010 bare 'LRTX-T003' forms
pat = re.compile(rf"^- \[ \] ((?:\*\*|`)?{re.escape(tid)}\b.*)$", re.M)
m = pat.search(text)
if not m:
    sys.exit(f"{tid} not found unchecked")
line = m.group(1) + f" ✅ Evidence: {', '.join('`'+r+'`' for r in refs)}"
text = text[: m.start()] + "- [X] " + line + text[m.end():]
tasks.write_text(text)
print(f"{tid} MARKED — {', '.join(refs)}")
