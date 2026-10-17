"""CRE-T046 BC-009: the BC-008 replay with the SWE.4 inspection evidence removed; the pipeline must not reproduce the
clean result (SWE.4 gate not PASS, the package gains gaps). Proves the BC-008 oracle is sensitive."""
import json
import shutil
import sys
import tarfile
from pathlib import Path

from forge_factory.inspection.engine import PHASES, Store
from forge_factory.release.finalize import finalize

scratch = Path(sys.argv[1])
ws = scratch / "e2e"
ws.mkdir()
with tarfile.open(scratch / "ws" / "e2e_ll_r87.tar.gz") as t:
    t.extractall(ws, filter="data")
shutil.rmtree(ws / "inspection" / "SWE.4")
s = Store(ws)
gates = {p: s.gate(p)["decision"] for p in PHASES}
pkg = finalize(ws, "BENCH-E2E-LL-TAMPERED")
print(json.dumps({"observed": {"gates_pass": sum(v == "PASS" for v in gates.values()), "swe4": gates["SWE.4"],
                               "package_status": pkg["package_status"], "gap_count": pkg["gap_count"]}}))
