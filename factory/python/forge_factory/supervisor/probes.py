"""T021 — deterministic health probes (no model, no LLM endpoint is ever contacted).

Each probe returns HealthSample {component, check, status HEALTHY|DEGRADED|DOWN|UNKNOWN, latency_ms, metrics,
fault_type?, run_id?, detail}. Unobservable metrics are UNKNOWN, never HEALTHY.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..common import state_dir

MODEL_PORTS = {11434, 11435, 11436}  # supervisor must never touch these (FR-008)


@dataclass
class Sample:
    component: str
    check: str
    status: str
    latency_ms: float = 0.0
    fault_type: str | None = None
    run_id: str | None = None
    detail: str = ""
    metrics: dict = field(default_factory=dict)

    def dict(self) -> dict:
        return asdict(self)


def _http_json(url: str, timeout: float = 3.0, headers: dict | None = None):
    port = int(url.split("://", 1)[1].split("/", 1)[0].rsplit(":", 1)[1]) if url.count(":") >= 2 else 80
    if port in MODEL_PORTS:
        raise PermissionError("supervisor may not contact model endpoints")
    req = urllib.request.Request(url, headers=headers or {})  # noqa: S310 - loopback config URLs only
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - loopback URLs from config only
        import json

        return json.load(r)


class Probes:
    def __init__(self, policy: dict, fabro_url: str, token: str | None, dashboard_url: str | None = None,
                 mcp_servers: list[str] | None = None, data_root: Path | None = None):
        self.policy = policy
        self.fabro = fabro_url.rstrip("/").removesuffix("/api/v1")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.dashboard = dashboard_url
        self.mcp_servers = mcp_servers or []
        self._rr = 0
        self.data_root = data_root or state_dir().parent

    # --- Fabro ------------------------------------------------------------------------------------
    def fabro_readiness(self) -> Sample:
        t0 = time.monotonic()
        try:
            ok = _http_json(f"{self.fabro}/health").get("status") == "ok"
            info = _http_json(f"{self.fabro}/api/v1/system/info", headers=self.headers)
            return Sample("fabro", "fabro_readiness", "HEALTHY" if ok else "DEGRADED", (time.monotonic() - t0) * 1000,
                          None if ok else "READINESS_FAILURE", metrics={"version": info.get("version"),
                                                                       "active_runs": info.get("runs", {}).get("active")})
        except Exception as exc:  # noqa: BLE001
            return Sample("fabro", "fabro_readiness", "DOWN", (time.monotonic() - t0) * 1000, "READINESS_FAILURE",
                          detail=f"{type(exc).__name__}")

    def fabro_run_progress(self) -> list[Sample]:
        mult = float(self.policy["thresholds"]["stage_stall_multiplier"])
        stall_s = float(self.policy.get("stage_stall_seconds", 1800)) * mult / 2.0
        qmax = float(self.policy["thresholds"]["queue_max_age_seconds"])
        out: list[Sample] = []
        try:
            runs = _http_json(f"{self.fabro}/api/v1/runs?page%5Blimit%5D=20", headers=self.headers).get("data", [])
        except Exception as exc:  # noqa: BLE001
            return [Sample("fabro", "fabro_run_progress", "UNKNOWN", detail=type(exc).__name__)]
        now = datetime.now(UTC)
        for r in runs:
            kind = ((r.get("lifecycle") or {}).get("status") or {}).get("kind", "")
            rid = r["id"]
            if kind in ("running",):
                try:
                    evs = _http_json(f"{self.fabro}/api/v1/runs/{rid}/events?order=desc&limit=1",
                                     headers=self.headers).get("data", [])
                    last = datetime.fromisoformat(evs[0]["ts"].replace("Z", "+00:00")) if evs else None
                except Exception:  # noqa: BLE001
                    last = None
                if last is None:
                    out.append(Sample("fabro-run", "fabro_run_progress", "UNKNOWN", run_id=rid))
                    continue
                age = (now - last).total_seconds()
                out.append(Sample("fabro-run", "fabro_run_progress", "DEGRADED" if age > stall_s else "HEALTHY",
                                  fault_type="STAGE_STALL" if age > stall_s else None, run_id=rid,
                                  metrics={"seconds_since_last_event": round(age, 1), "stall_threshold_s": stall_s}))
            elif kind in ("submitted", "queued", "runnable"):
                created = r.get("created_at") or r.get("lifecycle", {}).get("created_at")
                qage: float | None = ((now - datetime.fromisoformat(created.replace("Z", "+00:00"))).total_seconds()
                                      if created else None)
                bad = qage is not None and qage > qmax
                out.append(Sample("fabro-queue", "queued_run_age", "DEGRADED" if bad else ("HEALTHY" if qage is not None
                                  else "UNKNOWN"), fault_type="QUEUE_STALL" if bad else None, run_id=rid,
                                  metrics={"queued_seconds": qage}))
        return out or [Sample("fabro-run", "fabro_run_progress", "HEALTHY", metrics={"active": 0})]

    # --- MCP (round-robin one server per poll; full handshake) -------------------------------------
    def mcp_handshake(self) -> Sample:
        if not self.mcp_servers:
            return Sample("mcp", "mcp_handshake", "UNKNOWN", detail="no servers configured")
        from ..mcp.preflight import handshake

        s = self.mcp_servers[self._rr % len(self.mcp_servers)]
        self._rr += 1
        t0 = time.monotonic()
        h = handshake(s)
        ok = "error" not in h and h["tools"]
        return Sample(f"mcp:{s}", "mcp_handshake", "HEALTHY" if ok else "DOWN", (time.monotonic() - t0) * 1000,
                      None if ok else "MCP_HANDSHAKE_FAILURE", detail=h.get("error", "")[:120],
                      metrics={"tools": len(h["tools"])})

    # --- storage / host -------------------------------------------------------------------------------
    def storage(self) -> list[Sample]:
        out = []
        min_mb = float(self.policy["thresholds"]["storage_free_min_mb"])
        for name, d in (("evidence_store", state_dir()), ("archive_store", self.data_root / "archives")):
            d.mkdir(parents=True, exist_ok=True)
            try:
                p = d / f".probe-{os.getpid()}"
                p.write_bytes(b"x")
                p.unlink()
                free = shutil.disk_usage(d).free / 2**20
                st = "HEALTHY" if free >= min_mb else "DEGRADED"
                out.append(Sample(name, "evidence_store_writable", st, fault_type=None if st == "HEALTHY" else
                                  "DISK_PRESSURE", metrics={"free_mb": round(free)}))
            except OSError as exc:
                out.append(Sample(name, "evidence_store_writable", "DOWN", fault_type="STORE_NOT_WRITABLE",
                                  detail=type(exc).__name__))
        return out

    def db_writable(self, db: Path) -> Sample:
        try:
            c = sqlite3.connect(db, timeout=5)
            c.execute("CREATE TABLE IF NOT EXISTS _probe(x)")
            c.execute("INSERT INTO _probe VALUES(1)")
            c.execute("DELETE FROM _probe")
            c.commit()
            c.close()
            return Sample("incident_db", "db_writable", "HEALTHY")
        except sqlite3.Error as exc:
            return Sample("incident_db", "db_writable", "DOWN", fault_type="DB_NOT_WRITABLE", detail=str(exc)[:80])

    def ram(self) -> Sample:
        try:
            mi = {ln.split(":")[0]: int(ln.split()[1]) for ln in Path("/proc/meminfo").read_text().splitlines()}
            avail = mi["MemAvailable"] / mi["MemTotal"]
            return Sample("host", "ram_pressure", "HEALTHY" if avail > 0.05 else "DEGRADED",
                          fault_type=None if avail > 0.05 else "RAM_PRESSURE", metrics={"available_ratio": round(avail, 3)})
        except (OSError, KeyError, ValueError):
            return Sample("host", "ram_pressure", "UNKNOWN")

    def gpu(self) -> Sample:
        if not shutil.which("nvidia-smi"):
            return Sample("gpu", "gpu_memory_pressure_when_available", "UNKNOWN", detail="nvidia-smi unavailable")
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=10, check=True).stdout.split(",")
            used, total = float(out[0]), float(out[1])
            return Sample("gpu", "gpu_memory_pressure_when_available", "HEALTHY" if used / total < 0.98 else "DEGRADED",
                          metrics={"used_mb": used, "total_mb": total})
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            return Sample("gpu", "gpu_memory_pressure_when_available", "UNKNOWN")

    def dashboard_health(self) -> Sample:
        if not self.dashboard:
            return Sample("dashboard", "dashboard_health", "UNKNOWN", detail="not configured")
        try:
            ok = _http_json(f"{self.dashboard.rstrip('/')}/api/v1/health/live").get("live") is True
            return Sample("dashboard", "dashboard_health", "HEALTHY" if ok else "DEGRADED")
        except Exception as exc:  # noqa: BLE001
            return Sample("dashboard", "dashboard_health", "DOWN", fault_type="DASHBOARD_DOWN", detail=type(exc).__name__)

    def all(self, db: Path) -> list[Sample]:
        out = [self.fabro_readiness()]
        if out[0].status == "HEALTHY":
            out += self.fabro_run_progress()
        out.append(self.mcp_handshake())
        out += self.storage()
        out += [self.db_writable(db), self.ram(), self.gpu(), self.dashboard_health()]
        return out
