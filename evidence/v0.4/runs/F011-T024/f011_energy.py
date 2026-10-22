"""Energy of an evidence-run window from the v2 admission gateway meter (same trapezoid as lrtx.runmetrics)."""
import json, sys
from datetime import datetime, timedelta

meter, rec = sys.argv[1], json.load(open(sys.argv[2]))
start = datetime.fromisoformat(rec["ts_utc"].replace("Z", "+00:00"))  # evidence_run: ts_utc is the start
end = start + timedelta(seconds=rec["duration_s"])
pw = []
for line in open(meter):
    r = json.loads(line)
    if "sample" not in r:
        continue
    t = datetime.fromisoformat(r["ts_utc"].replace("Z", "+00:00"))
    p = ((r["sample"].get("gpu") or {}).get("power_w"))
    if start <= t <= end and p is not None:
        pw.append((t.timestamp(), p))
j = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(pw, pw[1:]))
print(json.dumps({"task": rec["task"], "window_start": start.isoformat(), "window_end": end.isoformat(),
                  "duration_s": rec["duration_s"], "samples": len(pw), "gpu_board_wh": round(j / 3600, 3)}))
