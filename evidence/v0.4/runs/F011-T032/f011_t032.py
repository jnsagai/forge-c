"""F011-T032 / F011-AT-026: three fresh SWE.2 author + inspection visits per pilot on a genuinely accepted SWE.1.

Start workspaces: the READY rc1 work orders (their SWE.1 was accepted by the production inspector), never written.
Each attempt is modelcmp.attempt (fresh copy without SWE.2, the real structured SWE.2 author, freeze through the
unchanged author gate), then the inspector the runner selects for SWE.2 on the frozen baseline. Only an inspection
record added by that visit counts. The local inspector is NOT_QUALIFIED (F011-T029): its verdicts are measurements,
not acceptance.

    python f011_t032.py <report.json> <scratch dir> <gateway usage.jsonl> [author model] [inspector model]

The start work orders are read from $FORGE_T032_WORKORDERS when set (a sha256-checked copy on another host),
else from the loop10 state.
"""
import json
import os
import sys
from importlib import import_module
from pathlib import Path

from forge_factory.common import pretty_json, utc_now
from forge_factory.lrtx import modelcmp
from forge_factory.lrtx.runner import inspector_module

S = Path(os.environ.get("FORGE_T032_WORKORDERS")
         or "/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/state/workorders")
STARTS = {"IWDG-LL": S / "WO-0009A-STM32N6-IWDG-LL-rc1/workspace", "RCC-LL": S / "WO-0002A-STM32N6-RCC-LL-rc1/workspace"}
out, scratch, meter = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
model = sys.argv[4] if len(sys.argv) > 4 else "qwen3-coder:30b"
inspector = sys.argv[5] if len(sys.argv) > 5 else model
rows = []
for pilot, start in STARTS.items():
    for n in (1, 2, 3):
        r = modelcmp.attempt(start, scratch / pilot, model, n, meter, 35, "SWE.2")
        r["pilot"], r["inspection"] = pilot, {"status": "NOT_RUN (not frozen)"}
        if str(r["gate"]).startswith("FROZEN"):
            ws = Path(r["workspace"])
            earlier = {q.name for q in (ws / "inspection/SWE.2").glob("INS-*.json")}
            mod = import_module(f"forge_factory.lrtx.{inspector_module(ws, 'SWE.2')}")
            rep = mod.visit(ws, "SWE.2", inspector)
            new = sorted(q for q in (ws / "inspection/SWE.2").glob("INS-*.json") if q.name not in earlier)
            ins = json.loads(new[-1].read_text()) if new else None
            r["inspection"] = {"module": inspector_module(ws, "SWE.2"), "model": inspector, "reply": rep["status"],
                               "verdict": (ins or {}).get("verdict", "NO_INSPECTION"),
                               "findings": [f"{f.get('id')}: {str(f.get('detail', ''))[:200]}"
                                            for f in (ins or {}).get("findings") or []][:12]}
        rows.append(r)
        out.write_text(pretty_json({"schema": "forge-c/f011-t032/1", "at": utc_now(), "model": model, "inspector": inspector, "rows": rows,
                                    "note": "Inspector NOT_QUALIFIED (F011-T029): verdicts are measurements only."}))
        print(json.dumps({"pilot": pilot, "n": n, "visit": r["visit"], "gate": r["gate"], "calls": r["calls"],
                          "wall_s": r["wall_s"], "inspection": r["inspection"].get("verdict",
                                                                                   r["inspection"].get("status"))}))
