"""Read-only: per-call lines from the runner stdout and one line per 30 s with the inspector checkpoint count and the
latest verdict status. No model text. Arg 1: run name (medium|xhigh)."""
import json, os, sys, time
from datetime import datetime, timezone

RUN = sys.argv[1]
D = "/mnt/data/forge-c/operations/swe1-omission-20261031"
LOG, W = D + "/progress.log", f"{D}/work-{RUN}"
PK, STOP = f"{D}/inspect-{RUN}/.forge-run/lrtx/SWE.1/packets", W + "/monitor.stop"


def p(s):
    if os.path.getsize(LOG) < 190_000:
        with open(LOG, "a") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + f" [{RUN}] " + s + "\n")


seen, last = {}, 0.0
while not os.path.exists(STOP):
    try:
        for o in sorted(f for f in os.listdir(W) if f.startswith("runner-pass") and f.endswith(".stdout")):
            lines = open(os.path.join(W, o)).read().splitlines()
            for ln in lines[seen.get(o, 0):]:
                try:
                    d = json.loads(ln)
                except ValueError:
                    break
                if "lrtx_progress" in d:
                    p(f"INSPECT CALL {d['lrtx_progress']} attempt {d.get('attempt')} errors {d.get('errors')} wall {d.get('wall_ms')} ms")
                seen[o] = seen.get(o, 0) + 1
        if time.time() - last >= 30:
            last = time.time()
            fs = [os.path.join(PK, f) for f in os.listdir(PK) if f.startswith("inspect")] if os.path.isdir(PK) else []
            s = f"INSPECT CHECKPOINTS: {len(fs)} inspector item checkpoints"
            if fs:
                c = json.load(open(max(fs, key=os.path.getmtime))); d = c.get("doc") or {}
                s += (f"; latest {c.get('task', '').split(':')[-1]} {c.get('status')} verdict {d.get('verdict')} "
                      f"findings {len(d.get('findings') or [])} ({len(c.get('attempts') or [])} calls)")
            p(s)
    except Exception:
        pass
    time.sleep(2)
