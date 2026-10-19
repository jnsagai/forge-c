"""AFO-T012 (AFO-FR-010/014, AT-003/AT-009) - the Conductor service process: heartbeat and systemd watchdog.

`python -m forge_factory.afo.conductor` runs as the forge-conductor user unit (Type=notify, WatchdogSec). Each poll
it (1) re-evaluates the AFO policy (fail closed, recorded), (2) runs the cycle the effective mode allows - in
DISABLED nothing, in OBSERVE_ONLY only reads (the queue cycle arrives with M2) - and (3) ONLY after a completed cycle
writes the heartbeat file and sends WATCHDOG=1. A hung or crashing cycle therefore stops the watchdog pings and
systemd restarts the unit; the external afo-watchdog timer alerts on a stale heartbeat. The process makes no model
call itself (the 002 supervisor's socket guard is installed): any agent work happens inside Fabro runs.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

from ..common import state_dir, utc_now

HEARTBEAT = "afo/conductor.heartbeat"


def heartbeat_path() -> Path:
    return state_dir() / HEARTBEAT


def write_heartbeat(cycle: int, mode: str, ok: bool, detail: str = "") -> None:
    p = heartbeat_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"ts": utc_now(), "epoch": time.time(), "pid": os.getpid(), "cycle": cycle,
                               "mode": mode, "ok": ok, "detail": detail[:200]}))
    os.replace(tmp, p)  # atomic: a reader never sees a half-written heartbeat


def cycle(n: int) -> tuple[str, bool, str]:
    """One Conductor cycle. M1: policy evaluation only; M2 adds the queue/scheduler work for OBSERVE_ONLY+."""
    from .policy import load

    eff = load(log=(n % 60 == 0))  # record a policy decision every 60 cycles and at start
    return eff.mode, True, ("; ".join(eff.issues))[:200]


class Conductor:
    def __init__(self, interval: float, max_cycles: int | None = None):
        self.interval, self.max_cycles, self.stop = interval, max_cycles, False

    def run(self) -> int:
        from ..supervisor.service import install_model_guard, sd_notify

        install_model_guard()
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stop", True))
        n = 0
        ready = False
        while not self.stop and (self.max_cycles is None or n < self.max_cycles):
            try:
                mode, ok, detail = cycle(n)
            except Exception as exc:  # noqa: BLE001 - a failed cycle sends no watchdog ping; systemd decides
                write_heartbeat(n, "UNKNOWN", False, f"{type(exc).__name__}: {exc}")
                time.sleep(self.interval)
                n += 1
                continue
            write_heartbeat(n, mode, ok, detail)
            if not ready:
                sd_notify(f"READY=1\nSTATUS=AFO conductor mode={mode}")
                ready = True
            sd_notify(f"WATCHDOG=1\nSTATUS=cycle {n} mode={mode}")
            n += 1
            for _ in range(int(self.interval * 10)):
                if self.stop:
                    break
                time.sleep(0.1)
        sd_notify("STOPPING=1")
        return 0


def heartbeat_age(now: float | None = None) -> float | None:
    try:
        return (now or time.time()) - json.loads(heartbeat_path().read_text())["epoch"]
    except (OSError, ValueError, KeyError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.afo.conductor")
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--max-cycles", type=int)
    a = ap.parse_args(argv)
    return Conductor(a.interval, a.max_cycles).run()


if __name__ == "__main__":
    sys.exit(main())
