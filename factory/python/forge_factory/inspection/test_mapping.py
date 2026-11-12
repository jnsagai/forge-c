"""CAPA-059 (b006): SWE.1 maps every requirement to a test level. A reset/startup invariant ("While no ... after reset,
the driver shall not write ...") cannot be observed by a host unit test - the harness itself starts after reset, so
such a test is tautological (b006 UT-018: SWE4-02/SWE4-06 FAILs until the SWE.4 rework budget ran out). It belongs to
the SWE.6 Robot suite (a target image observes the registers before the first driver call)."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .ears import RESET_AFTER

STARTUP = re.compile(r"\bWhile\b[^.\n]*" + RESET_AFTER, re.I)
TRACE = "traceability/requirements_to_tests.csv"


def startup_on_host(ws: Path) -> list[str]:
    from ..layer import profile
    from .swtrace import swr_texts

    ws = Path(ws)
    p = ws / TRACE
    if not p.is_file():
        return []
    robot = f"software/tests/software/test_{profile(ws)['id']}_requirements.robot"
    startup = {r for r, t in swr_texts(ws).items() if STARTUP.search(t)}
    out = []
    for row in csv.DictReader(p.read_text(errors="replace").splitlines()):
        rid, tf = (row.get("requirement_id") or "").strip(), (row.get("test_file") or "").strip()
        if rid in startup and tf.startswith("software/tests/unit/"):
            out.append(f"SWE1:STARTUP_INVARIANT_ON_HOST_TEST:{rid} (a host unit test starts after reset and cannot "
                       f"observe it: map it to the Robot suite - test_id {rid}, test_file {robot})")
    return out
