"""Holdout: a CODE defect without a verbatim requirement quote is refused (ADR-0008 grounding must not regress)."""
import json
import os
import sys
from pathlib import Path

ws = Path(sys.argv[1]) / "ws"
os.environ["FORGE_EVENTS_DIR"] = str(Path(sys.argv[1]) / "ev")
from forge_factory.inspection import defects as D  # noqa: E402

try:
    D.report(ws, detected_phase="SWE.6", reported_by="swe6-author", kind="CODE", summary="driver wrong",
             requirement_ids=["SWR-014"], test_files=["software/tests/software/scn.c"], evidence_refs=[],
             requirement_quote="the driver should probably accept it")
    result = "ACCEPTED"
except D.DefectError as exc:
    result = str(exc).split(":")[0]
print(json.dumps({"observed": {"result": result}}))
