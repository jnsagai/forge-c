"""Read-only progress monitor: attempt start/finish lines (from report.json rows) and one checkpoint line per 30 s.
Writes only plain status lines to progress.log: counts, task names, statuses, numbers. Never model text."""
import json, os, sys, time
from datetime import datetime, timezone
D = "/mnt/data/forge-c/operations/swe1-ornith-20261031"
LOG, REP, WSR = D + "/progress.log", D + "/report.json", D + "/report-workspaces"
stop = D + "/work/monitor.stop"
def p(s):
    if os.path.getsize(LOG) > 190_000:
        return
    with open(LOG, "a") as f:
        f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + s + "\n")
seen_ws, seen_rows, last_ck = set(), 0, 0.0
while not os.path.exists(stop):
    try:
        cur = sorted(os.listdir(WSR)) if os.path.isdir(WSR) else []
        for a in cur:
            if a not in seen_ws:
                seen_ws.add(a); p(f"ATTEMPT STARTED {a}")
        if os.path.isfile(REP):
            rows = json.load(open(REP)).get("rows") or []
            for r in rows[seen_rows:]:
                p(f"ATTEMPT FINISHED {r['model']}-{r['n']:02d}: visit {r['visit']}, gate {r['gate']}, calls {r['calls']}, wall {r['wall_s']} s")
            seen_rows = len(rows)
        if time.time() - last_ck >= 30 and cur:
            last_ck = time.time()
            pk = os.path.join(WSR, cur[-1], "workspace/.forge-run/lrtx/SWE.1/packets")
            fs = [os.path.join(pk, f) for f in os.listdir(pk) if f.endswith(".json")] if os.path.isdir(pk) else []
            if fs:
                lf = max(fs, key=os.path.getmtime); c = json.load(open(lf))
                p(f"CHECKPOINTS {cur[-1]}: {len(fs)} task checkpoints; latest {c.get('task')} {c.get('status')} ({len(c.get('attempts') or [])} calls)")
            else:
                p(f"CHECKPOINTS {cur[-1]}: 0 task checkpoints")
    except Exception as e:  # a half-written file: retry next tick
        pass
    time.sleep(5)
