"""Read-only: one line per 30 s with the inspector checkpoint count and the latest verdict status. No model text."""
import json, os, time
from datetime import datetime, timezone
D = "/mnt/data/forge-c/operations/swe1-ornith-20261031"; LOG = D + "/progress.log"
PK = D + "/inspect-ws/.forge-run/lrtx/SWE.1/packets"; STOP = D + "/inspect-work/monitor.stop"
while not os.path.exists(STOP):
    try:
        fs = [os.path.join(PK, f) for f in os.listdir(PK) if f.startswith("inspect") and f.endswith(".json")]
        s = f"STEP2 CHECKPOINTS: {len(fs)} inspector item checkpoints"
        if fs:
            lf = max(fs, key=os.path.getmtime); c = json.load(open(lf)); d = c.get("doc") or {}
            s += (f"; latest {c.get('task','').split(':')[-1]} {c.get('status')} verdict {d.get('verdict')} "
                  f"findings {len(d.get('findings') or [])} ({len(c.get('attempts') or [])} calls)")
        if os.path.getsize(LOG) < 190_000:
            with open(LOG, "a") as f:
                f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + s + "\n")
    except Exception:
        pass
    for _ in range(30):
        if os.path.exists(STOP):
            break
        time.sleep(1)
