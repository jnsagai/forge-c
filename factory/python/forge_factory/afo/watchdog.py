"""AFO-T013 (AFO-FR-010/014/015, AT-003/AT-009) - external Conductor watchdog (systemd timer, model-free).

Independent of the Conductor process: reads the heartbeat file and, when it is missing, older than --max-age or
reports a failed cycle, appends ONE alert per dedup window to <state>/afo/alerts.jsonl (always-available local
channel; external channels come with M6) and exits 1 so the timer unit shows the failure. It never restarts
anything: restarts are systemd's (Restart=, WatchdogSec=) and bounded by StartLimitBurst.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from ..common import state_dir, utc_now
from .conductor import heartbeat_path

ALERTS = "afo/alerts.jsonl"


def check(max_age: float, now: float | None = None) -> dict:
    now = now or time.time()
    try:
        hb = json.loads(heartbeat_path().read_text())
    except (OSError, ValueError):
        return {"ok": False, "code": "HEARTBEAT_MISSING"}
    age = now - float(hb.get("epoch", 0))
    if age > max_age:
        return {"ok": False, "code": "HEARTBEAT_STALE", "age_s": round(age, 1), "pid": hb.get("pid")}
    if not hb.get("ok", False):
        return {"ok": False, "code": "CYCLE_FAILED", "detail": hb.get("detail", "")[:200], "pid": hb.get("pid")}
    return {"ok": True, "code": "HEALTHY", "age_s": round(age, 1), "mode": hb.get("mode")}


def alert(result: dict, dedup_s: float, now: float | None = None) -> bool:
    """Append the alert unless the same code was alerted within the dedup window. Returns True when written."""
    now = now or time.time()
    p = state_dir() / ALERTS
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        last = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    except OSError:
        last = []
    if any(a.get("code") == result["code"] and now - a.get("epoch", 0) < dedup_s for a in last[-50:]):
        return False
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": utc_now(), "epoch": now, "source": "afo-watchdog", **result}) + "\n")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.afo.watchdog")
    ap.add_argument("--max-age", type=float, default=300)
    ap.add_argument("--dedup", type=float, default=900)
    a = ap.parse_args(argv)
    r = check(a.max_age)
    if not r["ok"]:
        from .operations import configured
        from .host import preflight

        if configured() and not preflight()["ok"]:
            # Surviving independent layer reports via journal/stdout, without data-root fallback writes.
            print(json.dumps({**r, "recovery": "WAITING_FOR_AUTHORITATIVE_VOLUME"}))
            return 1
        r["alerted"] = alert(r, a.dedup)
        from .operations import recover

        r["recovery"] = recover()
    from .operations import configured, recover_profile
    from .host import preflight

    if configured() and preflight()["ok"]:
        from .queue import Store

        try:
            r["profile_recovery"] = recover_profile(Store())
        except (OSError, ValueError, TimeoutError) as exc:
            r["profile_recovery"] = {"action": "WAITING", "code": getattr(exc, "code", type(exc).__name__)}
    print(json.dumps(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
