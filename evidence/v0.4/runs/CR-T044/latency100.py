"""SC-001: 100 recorded station changes -> time until the Control Room stream shows each one (real loopback server)."""
import json, os, sys, tempfile, threading, time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="cr-lat-", dir=sys.argv[1]))
os.environ["FORGE_STATE_DIR"] = str(tmp / "state")
import httpx  # noqa: E402
from controlroom_fixtures import CFG, FakeProbe, append, workspace  # noqa: E402
from forge_factory.controlroom import config as C  # noqa: E402
from forge_factory.controlroom.floor import Floor  # noqa: E402
from forge_factory.dashboard.app import create_app, tokens  # noqa: E402
from test_controlroom_api import _serve  # noqa: E402

C.load = lambda path=None: dict(CFG)
root = tmp / "wo"; root.mkdir()
app = create_app(collect=False, control_room_floor=Floor(root=root, probe=FakeProbe()))
srv, port = _serve(app)
ws = workspace(root, "WO-LAT-r1", [])
tok = tokens()["viewer"]
seen, lat = [], []

def writer():
    time.sleep(1.5)
    for i in range(100):
        t0 = time.monotonic()
        append(ws, {"phase": "SWE.1", "step": "route", "gate": {"decision": "REWORK", "reason": f"R{i}"}, "ts": "2026-10-19T10:00:00Z"})
        while len(seen) <= i and time.monotonic() - t0 < 10:
            time.sleep(0.02)
        lat.append(round(time.monotonic() - t0, 3))

th = threading.Thread(target=writer); th.start()
with httpx.stream("GET", f"http://127.0.0.1:{port}/api/v1/control-room/stream?max_seconds=300",
                  headers={"Authorization": f"Bearer {tok}"}, timeout=30) as r:
    ev = None
    for line in r.iter_lines():
        if line.startswith("event: "):
            ev = line[7:]
        elif line.startswith("data: ") and ev == "floor":
            rs = [s["reason"] for s in json.loads(line[6:])["stations"] if s["reason"]]
            if rs and (not seen or seen[-1] != rs[0]):
                seen.append(rs[0])
        if len(lat) >= 100:
            break
th.join(30); srv.should_exit = True
within = sum(x <= 5 for x in lat)
s = sorted(lat)
res = {"events": len(lat), "within_5s": within, "share_within_5s": within / len(lat), "p50_s": s[len(s) // 2],
       "p95_s": s[int(len(s) * 0.95) - 1], "max_s": s[-1], "pass": within / len(lat) >= 0.95}
print(json.dumps(res))
json.dump({**res, "latencies_s": lat}, open(sys.argv[2], "w"), indent=1)
