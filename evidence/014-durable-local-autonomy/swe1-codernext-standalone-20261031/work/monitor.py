"""Read-only progress monitor. Plain status lines only (counts, task names, statuses, numbers), never model text.
Arg 1: 'author' or 'inspect'; arg 2 (inspect): the inspect copy, arg 3: run tag."""
import json, os, sys, time
from datetime import datetime, timezone

MODE = sys.argv[1]
D = "/mnt/data/forge-c/operations/swe1-codernext-20261031"
LOG, W = D + "/progress.log", D + "/work"
TAG = sys.argv[3] if len(sys.argv) > 3 else MODE
STOP = f"{W}/monitor-{TAG}.stop"


def p(s):
    if os.path.getsize(LOG) > 190_000:
        return
    with open(LOG, "a") as f:
        f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + s + "\n")


def calls(path, seen, prefix):
    if not os.path.isfile(path):
        return seen
    lines = open(path).read().splitlines()
    for ln in lines[seen:]:
        try:
            d = json.loads(ln)
        except ValueError:
            return seen  # half-written line: retry
        if "lrtx_progress" in d:
            p(f"{prefix}CALL {d['lrtx_progress']} attempt {d.get('attempt')} errors {d.get('errors')} wall {d.get('wall_ms')} ms")
        seen += 1
    return seen


seen_ws, seen_rows, seen_out, last_ck, seen_files = set(), 0, 0, 0.0, {}
REP, WSR = D + "/report.json", D + "/report-workspaces"
PK = (sys.argv[2] if len(sys.argv) > 2 else D + "/inspect-ws") + "/.forge-run/lrtx/SWE.1/packets"
while not os.path.exists(STOP):
    try:
        if MODE == "author":
            cur = sorted(os.listdir(WSR)) if os.path.isdir(WSR) else []
            for a in cur:
                if a not in seen_ws:
                    seen_ws.add(a); p(f"ATTEMPT STARTED {a}")
            seen_out = calls(W + "/modelcmp.stdout", seen_out, "")
            if os.path.isfile(REP):
                rows = json.load(open(REP)).get("rows") or []
                for r in rows[seen_rows:]:
                    p(f"ATTEMPT FINISHED {r['model']}-{r['n']:02d}: visit {r['visit']}, gate {r['gate']}, calls {r['calls']}, wall {r['wall_s']} s")
                seen_rows = len(rows)
            if time.time() - last_ck >= 30:
                last_ck = time.time()
                if not cur:
                    p("CHECKPOINTS: no attempt workspace yet")
                else:
                    pk = os.path.join(WSR, cur[-1], "workspace/.forge-run/lrtx/SWE.1/packets")
                    fs = [os.path.join(pk, f) for f in os.listdir(pk) if f.endswith(".json")] if os.path.isdir(pk) else []
                    if fs:
                        lf = max(fs, key=os.path.getmtime); c = json.load(open(lf))
                        p(f"CHECKPOINTS {cur[-1]}: {len(fs)} task checkpoints; latest {c.get('task')} {c.get('status')} ({len(c.get('attempts') or [])} calls)")
                    else:
                        p(f"CHECKPOINTS {cur[-1]}: 0 task checkpoints")
        else:
            outs = sorted(f for f in os.listdir(W) if f.startswith(f"runner-{TAG}-pass") and f.endswith(".stdout"))
            for o in outs:
                seen_files[o] = calls(os.path.join(W, o), seen_files.get(o, 0), f"[{TAG}] INSPECT ")
            if time.time() - last_ck >= 30:
                last_ck = time.time()
                fs = [os.path.join(PK, f) for f in os.listdir(PK) if f.startswith("inspect") and f.endswith(".json")] if os.path.isdir(PK) else []
                s = f"[{TAG}] INSPECT CHECKPOINTS: {len(fs)} inspector item checkpoints"
                if fs:
                    lf = max(fs, key=os.path.getmtime); c = json.load(open(lf)); d = c.get("doc") or {}
                    s += (f"; latest {c.get('task','').split(':')[-1]} {c.get('status')} verdict {d.get('verdict')} "
                          f"findings {len(d.get('findings') or [])} ({len(c.get('attempts') or [])} calls)")
                p(s)
    except Exception:  # a half-written file: retry next tick
        pass
    time.sleep(2)
