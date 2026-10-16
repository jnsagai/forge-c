"""T020/T024 — model-free supervisor service (separate OS process, independent of Fabro).

* Validated interval (policy 15..300 s, default 60) with jitter; persistent checkpoint (poll count, last poll).
* Socket guard: any connection attempt to a model endpoint port is BLOCKED and counted -> the healthy-poll
  `model_calls` metric is measured, not assumed (FR-008, AT-09).
* Writes health.json + heartbeat each poll; systemd `sd_notify` READY/WATCHDOG when NOTIFY_SOCKET is set.
* On eligible incidents dispatches repair (T023); on terminal Fabro runs without a package, runs the
  external finalizer (T046).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import signal
import socket
import time
from pathlib import Path

import yaml

from ..common import CONFIG_DIR, pretty_json, state_dir, utc_now
from ..events.emit import emit
from .dispatch import dispatch
from .probes import MODEL_PORTS, Probes
from .router import Router, RouterState
from .store import IncidentStore

MODEL_CALLS = {"blocked_attempts": 0}
_real_connect = socket.socket.connect


def _guarded_connect(self, address):  # type: ignore[no-untyped-def]
    try:
        port = address[1] if isinstance(address, tuple) else None
    except (IndexError, TypeError):
        port = None
    if port in MODEL_PORTS:
        MODEL_CALLS["blocked_attempts"] += 1
        raise PermissionError(f"supervisor model-call guard: port {port} blocked")
    return _real_connect(self, address)


def install_model_guard() -> None:
    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]


def sd_notify(msg: str) -> None:
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
        try:
            s.connect(addr)
            s.sendall(msg.encode())
        except OSError:
            pass


def load_policy(path: Path | None = None) -> dict:
    pol = yaml.safe_load((path or CONFIG_DIR / "supervisor-policy.yaml").read_text())
    lo, hi = pol["valid_poll_interval_seconds"]
    if pol["mode"] != "NO_MODEL_IN_HEALTH_POLL":
        raise ValueError("supervisor mode must be NO_MODEL_IN_HEALTH_POLL")
    if not (lo <= int(pol["poll_interval_seconds"]) <= hi):
        raise ValueError(f"poll_interval_seconds must be within {lo}..{hi}")
    return pol


class Supervisor:
    def __init__(self, policy: dict, probes: Probes, store: IncidentStore | None = None, home: Path | None = None,
                 dispatch_enabled: bool = True, dry_run_dispatch: bool = False, finalizer_enabled: bool = True):
        self.p, self.probes = policy, probes
        self.home = home or state_dir() / "supervisor"
        self.home.mkdir(parents=True, exist_ok=True)
        self.store = store or IncidentStore(self.home / "incidents.sqlite3")
        self.state = RouterState.load(self.home / "router-state.json")
        self.router = Router(policy, self.store, self.state)
        self.dispatch_enabled, self.dry = dispatch_enabled, dry_run_dispatch
        self.finalizer_enabled = finalizer_enabled
        self.cre = None  # CRE hook (feature 004), created on first poll
        ck = self.home / "checkpoint.json"
        self.ck: dict = json.loads(ck.read_text()) if ck.is_file() else {"polls": 0, "started": utc_now()}

    def poll_once(self) -> dict:
        t0 = time.monotonic()
        samples = self.probes.all(self.store.path)
        eligible = self.router.observe(samples)
        eligible = self.cre_poll(samples, eligible)
        dispatched = []
        fabro_ok = any(s.check == "fabro_readiness" and s.status == "HEALTHY" for s in samples)
        if self.dispatch_enabled:
            for inc in eligible:
                r = dispatch(inc, self.store, fabro_ok, dry_run=self.dry)
                if r.get("dispatched"):
                    self.router.mark_dispatched(inc)
                    dispatched.append(r)
        if self.finalizer_enabled and fabro_ok:
            self.external_finalizer()
            self.budget_governor()
        self.export_dashboard_queues(fabro_ok)
        worst = "HEALTHY"
        for s in samples:
            if s.status == "DOWN" or (s.status == "DEGRADED" and worst == "HEALTHY"):
                worst = "DOWN" if s.status == "DOWN" else "DEGRADED"
        if all(s.status == "UNKNOWN" for s in samples):
            worst = "UNKNOWN"
        self.ck["polls"] += 1
        self.ck["last_poll"] = utc_now()
        health = {"status": {"DOWN": "DEGRADED"}.get(worst, worst) if worst != "DOWN" else "DEGRADED",
                  "last_poll": self.ck["last_poll"], "polls": self.ck["polls"],
                  "model_calls": MODEL_CALLS["blocked_attempts"], "model_tokens": 0,
                  "poll_ms": round((time.monotonic() - t0) * 1000, 1),
                  "components": [{"id": f"{s.component}:{s.check}", "status": s.status, "last_checked": self.ck["last_poll"],
                                  "fault_type": s.fault_type, "metrics": s.metrics} for s in samples],
                  "active_incidents": [i["incident_id"] for i in self.store.active()], "dispatched": dispatched}
        if any(s.check == "fabro_readiness" and s.status == "DOWN" for s in samples):
            health["status"] = "UNAVAILABLE"
        (self.home / "health.json").write_text(pretty_json(health))
        (self.home / "heartbeat").write_text(self.ck["last_poll"])
        (self.home / "checkpoint.json").write_text(json.dumps(self.ck))
        self.state.save(self.home / "router-state.json")
        emit("supervisor", "INFO" if health["status"] == "HEALTHY" else "WARN",
             f"poll {self.ck['polls']} {health['status']} incidents={len(health['active_incidents'])}")
        emit("metrics", "INFO", f"supervisor poll_ms={health['poll_ms']} model_calls={health['model_calls']}")
        sd_notify("WATCHDOG=1")
        return health

    def cre_poll(self, samples: list, eligible: list[dict]) -> list[dict]:
        """Feature 004 CRE hook (deterministic, zero model calls). Contained: a CRE failure never stops supervision."""
        try:
            if self.cre is None:
                from ..reliability.supervisor_hook import CREHook

                self.cre = CREHook(self.store.path)
            return self.cre.on_poll(samples, self.store, eligible)
        except Exception as exc:  # noqa: BLE001 - containment boundary by design
            emit("supervisor", "WARN", f"cre hook degraded: {type(exc).__name__}: {str(exc)[:100]}")
            return eligible

    def export_dashboard_queues(self, fabro_ok: bool) -> None:
        """Queue records for the external fabro_dashboard monitor (file export only; never affects supervision)."""
        try:
            from ..dashboard.fabro_monitor_export import export_all
            from ..fabro.client import FabroClient, load_token, run_status

            client = FabroClient(token=load_token(), timeout=5) if fabro_ok else None
            export_all((lambda rid: run_status(client.get_run(rid))) if client else None)
        except Exception as exc:  # noqa: BLE001
            emit("supervisor", "DEBUG", f"dashboard queue export failed: {type(exc).__name__}")

    def budget_governor(self) -> None:
        """T042: model-free token governor over active work-order runs (reported usage only)."""
        from ..policy.governor import check_run

        root = state_dir() / "workorders"
        for ws in sorted(root.glob("*/workspace")) if root.is_dir() else []:
            rid_f, bind_f = ws / ".forge-run/fabro_run_id", ws / ".forge-run/binding.json"
            if not rid_f.is_file() or not bind_f.is_file() or (ws / ".forge-run/package.json").is_file():
                continue
            try:
                nodes = json.loads(bind_f.read_text())["nodes"]
                check_run(rid_f.read_text().strip(), nodes, ws)
            except Exception as exc:  # noqa: BLE001
                emit("supervisor", "DEBUG", f"governor check failed: {type(exc).__name__}")

    def external_finalizer(self) -> None:
        """T046: any terminal Fabro work-order run without a package gets a deterministic BLOCKED/READY package."""
        root = state_dir() / "workorders"
        for ws in sorted(root.glob("*/workspace")) if root.is_dir() else []:
            rid_f, pkg = ws / ".forge-run/fabro_run_id", ws / ".forge-run/package.json"
            if not rid_f.is_file() or pkg.is_file():
                continue
            try:
                from ..fabro.client import client_for_workspace, run_status

                st = run_status(client_for_workspace(ws).get_run(rid_f.read_text().strip()))
            except Exception as exc:  # noqa: BLE001
                emit("supervisor", "DEBUG", f"finalizer status probe failed: {type(exc).__name__}")
                continue
            if st in ("SUCCEEDED", "FAILED", "CANCELLED", "CANCELED", "DEAD"):
                from ..release.finalize import finalize

                wo = ws.parent.name
                out = finalize(ws, wo, rid_f.read_text().strip())
                emit("supervisor", "WARN", f"external finalizer packaged {wo} {out['package_status']} (run {st})",
                     correlation_id=wo)

    def run_forever(self, max_polls: int | None = None) -> None:
        stop = {"flag": False}
        signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
        sd_notify("READY=1")
        interval = int(self.p["poll_interval_seconds"])
        n = 0
        while not stop["flag"] and (max_polls is None or n < max_polls):
            try:
                self.poll_once()
            except Exception as exc:  # noqa: BLE001 - never die on a probe bug; record it
                emit("supervisor", "ERROR", f"poll error {type(exc).__name__}: {str(exc)[:80]}")
            n += 1
            jitter = random.uniform(-0.1, 0.1) * interval  # noqa: S311 - scheduling jitter only
            end = time.monotonic() + max(1.0, interval + jitter)
            while time.monotonic() < end and not stop["flag"]:
                time.sleep(0.5)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-polls", type=int)
    ap.add_argument("--interval", type=int, help="override (still validated against policy range)")
    ap.add_argument("--no-dispatch", action="store_true")
    a = ap.parse_args(argv)
    install_model_guard()
    pol = load_policy()
    if a.interval:
        lo, hi = pol["valid_poll_interval_seconds"]
        if not lo <= a.interval <= hi:
            raise SystemExit(f"--interval must be within {lo}..{hi}")
        pol["poll_interval_seconds"] = a.interval
    from ..fabro.client import load_token
    from ..mcp.sdk import SERVER_MODULES

    probes = Probes(pol, os.environ.get("FORGE_FABRO_URL", "http://127.0.0.1:32290"), load_token(),
                    os.environ.get("FORGE_DASHBOARD_URL"), sorted(SERVER_MODULES))
    Supervisor(pol, probes, dispatch_enabled=not a.no_dispatch).run_forever(a.max_polls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
