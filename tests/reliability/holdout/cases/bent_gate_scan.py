"""Holdout: the author-gate anti-bending scan must flag an undeclared test edited until it passes on unchanged code."""
import json
import os
import sys
from pathlib import Path

ws = Path(sys.argv[1]) / "ws"
os.environ["FORGE_EVENTS_DIR"] = str(Path(sys.argv[1]) / "ev")
from forge_factory.inspection import defects as D  # noqa: E402

f = "software/tests/software/scn.c"
code = D.code_hash(ws)
log = ws / D.INTEGRITY_LOG
log.parent.mkdir(parents=True, exist_ok=True)
with log.open("w") as fh:
    for status, ts, h, failed in (("FAIL", "2026-10-16T01:00:00Z", "h1", [f]), ("PASS", "2026-10-16T01:05:00Z", "h2", [])):
        fh.write(json.dumps({"ts_utc": ts, "phase": "SWE.6", "op": "run_robot", "status": status, "code_sha": code,
                             "files": {f: h}, "assert_failed": failed}) + "\n")
print(json.dumps({"observed": {"flagged": D.bent_tests(ws, "SWE.6")}}))
