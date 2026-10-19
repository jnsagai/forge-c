"""CRE-T046 BC-008: end-to-end SWE.1-SWE.6 + packager replay. The frozen, real r87 LL work-order workspace (model
output of a clean run, inputs omitted) is re-evaluated by the factory revision under test: all six phase gates and
the release packager. Model-free: this verifies the deterministic pipeline, not the model."""
import json
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
s = Store(ws)
gates = {p: s.gate(p)["decision"] for p in PHASES}
pkg = finalize(ws, "BENCH-E2E-LL")
print(json.dumps({"observed": {"gates_pass": sum(v == "PASS" for v in gates.values()), "gates": gates,
                               "package_status": pkg["package_status"], "gap_count": pkg["gap_count"],
                               "gaps": pkg["gaps"][:12]}}))
