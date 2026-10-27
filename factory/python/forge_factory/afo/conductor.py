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
    tmp.write_text(
        json.dumps(
            {
                "ts": utc_now(),
                "epoch": time.time(),
                "pid": os.getpid(),
                "cycle": cycle,
                "mode": mode,
                "ok": ok,
                "detail": detail[:200],
            }
        )
    )
    os.replace(tmp, p)  # atomic: a reader never sees a half-written heartbeat


def cycle(n: int) -> tuple[str, bool, str]:
    """One Conductor cycle: policy evaluation (fail closed), then the scheduler cycle the mode allows (M2)."""
    from . import scheduler
    from .policy import load
    from .queue import Store

    eff = load(log=(n % 60 == 0))  # record a policy decision every 60 cycles and at start
    if eff.mode == "DISABLED":
        from . import local_agent
        from .queue import default_path

        if default_path().is_file():
            from . import dispatch

            store = Store()
            local_agent.supervise(store, eff)
            from . import product_job
            from ..fabro.client import FabroClient, load_token

            with FabroClient(token=load_token(), timeout=5) as client:
                product_job.reconcile(store, eff, client)
            dispatch.enforce_deadlines(store, eff)
            if os.environ.get("FORGE_DURABLE_AUTONOMY") == "1":
                learning_cycle(store)
        return eff.mode, True, ("; ".join(eff.issues))[:200]
    store = Store()
    from . import local_agent

    local_agent.supervise(store, eff)
    from . import product_job
    from ..fabro.client import FabroClient, load_token

    with FabroClient(token=load_token(), timeout=5) as client:
        product_job.reconcile(store, eff, client)
    from . import dispatch

    dispatch.enforce_deadlines(store, eff)
    r = scheduler.cycle(store, f"conductor-{os.getpid()}", eff=eff)
    if eff.mode in ("PILOT", "ACTIVE"):  # M3: launch, reconcile, validate; OBSERVE_ONLY never touches Fabro
        from . import checkpoints, dispatch, runtime

        dispatch.dispatch_pending(store, runtime.launcher)
        dispatch.reconcile_inflight(store, runtime.fabro_view)
        from . import recovery

        planner = None
        if eff.get("engineering.enable_recovery_planner"):  # owner-signed policy, as in both features
            from . import planner as afo_planner
            from . import planner_run

            local, fabro = local_agent.make_planner(store, eff), afo_planner.make(planner_run.invoke)

            def planner(bundle, budget, workspace=None):
                # the order's own engine diagnoses it: a local-profile work order (Feature 014) uses the local agent,
                # any other (the codex-claude production line, Feature 015) the Fabro planner run on the Claude login
                return (local if local_agent.local_order(workspace) else fabro)(bundle, budget, workspace)

        recover = recovery.make_recover(store, eff, f"conductor-{os.getpid()}", runtime.workspace_of, planner=planner)
        dispatch.reconcile_running(store, runtime.fabro_view, recover=recover)
        recovery.poll_waiting(store, recover)
        for o in store.orders(("RUNNING", "VALIDATING")):
            try:
                att = store.attempts(o["order_id"])[-1]
                ws = runtime.workspace_of(att)
                if ws.is_dir():
                    checkpoints.capture(store, o["order_id"], att["attempt_id"], ws)
            except (KeyError, ValueError, TypeError, FileNotFoundError) as exc:
                dispatch.item_failure(store, o["order_id"], exc, "checkpoint")
        dispatch.validate(store, runtime.workspace_of)
        from . import maintainer

        maintainer.open_cases(store, eff)  # AFO M5: no-op unless maintenance.enable_factory_maintainer
        local_agent.sweep_maintenance(store, eff)
        from . import alerts, deadletter

        window = float(eff.get("notifications.dedupe_window_seconds", 900))
        deadletter.sweep(store, runtime.workspace_of, window_s=window)  # AFO M6: one case + one alert per BLOCKED
        alerts.deliver(store)  # local fallback always; adapters optional
        store.forward_events()
        from .housekeeping import clean
        from ..common import state_dir

        scratch = state_dir() / "afo/tmp"
        if n % 60 == 0 and (scratch / ".forge-disposable").is_file():
            clean(scratch, max_files=32, max_bytes=10 * 1024 * 1024)
            connection = store.connect()
            try:
                connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            finally:
                connection.close()
        learning_cycle(store)
    return eff.mode, True, f"{r.get('action')} {r.get('order_id', '')}".strip()


def learning_cycle(store):
    from ..knowledge.store import LessonStore
    from ..knowledge.experience import capture_afo, capture_workorders, consolidate
    from ..knowledge.improvement import route
    from .runtime import workspace_of
    from ..fabro.client import FabroClient, load_token

    lessons = LessonStore()
    capture_afo(store, lessons, workspace_of, limit=32)
    with FabroClient(token=load_token(), timeout=3) as client:
        capture_workorders(store, lessons, client=client, limit=8)
    consolidate(lessons, limit=32)
    from ..reliability.capa import CapaRegistry
    from ..reliability.store import CREStore
    from ..reliability.policy import load as cre_policy

    route(lessons, capa_registry=CapaRegistry(CREStore(), cre_policy(), lessons=lessons), limit=32)


class Conductor:
    def __init__(self, interval: float, max_cycles: int | None = None):
        self.interval, self.max_cycles, self.stop = interval, max_cycles, False

    def run(self) -> int:
        from ..supervisor.service import install_model_guard, sd_notify

        from .operations import configured, Intent

        if configured() and self.max_cycles is not None:
            raise ValueError("CONTINUOUS_SERVICE_CANNOT_HAVE_FINITE_CYCLE_LIMIT")
        install_model_guard()
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stop", True))
        n = 0
        ready = False
        operator_stop = False
        while not self.stop and (self.max_cycles is None or n < self.max_cycles):
            try:
                if configured() and Intent().read()["mode"] == "STOPPED":
                    from .operations import settle_shutdown
                    from .queue import Store

                    settled = settle_shutdown(Store())
                    if settled["settled"]:
                        operator_stop = True
                        break
                    write_heartbeat(n, "OPERATOR_STOP_PENDING", True, "native cancellation unresolved")
                    time.sleep(min(self.interval, 15))
                    n += 1
                    continue
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
        return 77 if operator_stop else 0


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
