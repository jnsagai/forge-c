"""Run every EASA verifier on a workspace copy (no report writing) and print {verifier: (status, findings)}."""
import json, sys
from pathlib import Path
from forge_factory.assurance import verifiers as V
ws = Path(sys.argv[1])
out = {}
for fn in dict.fromkeys(V.VERIFIERS.values()):
    name = getattr(fn, "__name__", "?")
    try:
        if fn is V.v_fidelity:
            r = {ph: fn(ws, ph) for ph in ("SWE.5", "SWE.6")}
            r = {"status": {k: v["status"] for k, v in r.items()}, "findings": {k: v["findings"] for k, v in r.items()}}
        else:
            r = fn(ws)
    except Exception as e:  # noqa
        r = {"status": "ERROR", "findings": [f"{type(e).__name__}: {e}"[:300]]}
    out[name if name != "<lambda>" else "not_supported:" + str(r.get("findings"))[:40]] = {"status": r["status"], "findings": r.get("findings")}
print(json.dumps(out, indent=1, sort_keys=True, default=str))
