"""T022 — incident routing: thresholds, fingerprint dedup, lease, backoff/cooldown, attempt caps, breaker.

Model-free. Decides *whether* an eligible incident gets a repair dispatch; the dispatcher (T023) decides
*how* (Fabro child run when Fabro is healthy, external local worker when it is down).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..events.emit import emit
from .probes import Sample
from .store import IncidentStore

SEVERITY = {"READINESS_FAILURE": "CRITICAL", "STAGE_STALL": "HIGH", "MCP_HANDSHAKE_FAILURE": "HIGH",
            "STORE_NOT_WRITABLE": "CRITICAL", "DB_NOT_WRITABLE": "CRITICAL", "DISK_PRESSURE": "HIGH",
            "QUEUE_STALL": "MEDIUM", "RAM_PRESSURE": "MEDIUM", "DASHBOARD_DOWN": "LOW"}
# Faults outside automatic repair scope go straight to offline attention (never auto-edited).
NOT_REPAIRABLE = {"DISK_PRESSURE", "RAM_PRESSURE"}


@dataclass
class RouterState:
    consecutive: dict[str, int] = field(default_factory=dict)
    healthy_streak: dict[str, int] = field(default_factory=dict)
    last_dispatch: dict[str, float] = field(default_factory=dict)

    def save(self, p: Path) -> None:
        p.write_text(json.dumps(self.__dict__))

    @classmethod
    def load(cls, p: Path) -> RouterState:
        try:
            return cls(**json.loads(p.read_text()))
        except (OSError, ValueError, TypeError):
            return cls()


class Router:
    def __init__(self, policy: dict, store: IncidentStore, state: RouterState, version: str = "0.4"):
        self.p, self.store, self.st, self.version = policy, store, state, version

    def fingerprint(self, s: Sample) -> str:
        return f"{s.component}:{s.fault_type}:{s.run_id or '-'}:{self.version}"

    def threshold(self, s: Sample) -> int:
        return int(self.p["thresholds"]["fabro_consecutive_failed_polls"]) if s.component == "fabro" else 1

    def observe(self, samples: list[Sample]) -> list[dict]:
        """Update incidents from one poll; return incidents eligible for repair dispatch now."""
        failing = {self.fingerprint(s): s for s in samples if s.fault_type and s.status in ("DOWN", "DEGRADED")}
        for fp, s in failing.items():
            self.st.consecutive[fp] = self.st.consecutive.get(fp, 0) + 1
            self.st.healthy_streak.pop(fp, None)
            if self.st.consecutive[fp] >= self.threshold(s):
                inc, created = self.store.open_or_dedup(fp, s.component, s.fault_type or "UNKNOWN",
                                                        SEVERITY.get(s.fault_type or "", "MEDIUM"), s.run_id,
                                                        f"{s.check} {s.status} {s.detail}"[:160],
                                                        s.fault_type not in NOT_REPAIRABLE)
                if created:
                    emit("supervisor", "WARN", f"incident {inc['incident_id']} {s.component} {s.fault_type}",
                         correlation_id=inc["correlation_id"], incident_id=inc["incident_id"], run_id=s.run_id)
                    if s.fault_type in NOT_REPAIRABLE:
                        self.store.transition(inc["incident_id"], "REQUIRES_OFFLINE_ATTENTION",
                                              "outside automatic repair scope")
                    else:
                        self.store.transition(inc["incident_id"], "TRIAGED", "deterministic triage")
        stable = int(self.p["thresholds"]["stable_polls_for_recovery"])
        for inc in self.store.active():
            fp = inc["fingerprint"]
            if fp not in failing:
                self.st.consecutive.pop(fp, None)
                self.st.healthy_streak[fp] = self.st.healthy_streak.get(fp, 0) + 1
                if inc["state"] in ("DETECTED", "TRIAGED") and self.st.healthy_streak[fp] >= stable:
                    self.store.transition(inc["incident_id"], "RESOLVED", f"health restored {stable} stable polls")
                    emit("supervisor", "INFO", f"incident {inc['incident_id']} self-recovered",
                         incident_id=inc["incident_id"], correlation_id=inc["correlation_id"])
        return self.eligible()

    def eligible(self) -> list[dict]:
        rep = self.p["repair"]
        if not rep.get("request_ai_agent_on_eligible_incident"):
            return []
        now = time.time()
        hour_count = self.store.attempts_since(now - 3600)
        in_repair = [i for i in self.store.active() if i["state"] in ("REPAIRING", "VERIFYING")]
        out: list[dict] = []
        for inc in self.store.active():
            if inc["state"] not in ("TRIAGED",) or not inc["recoverable"]:
                continue
            if inc["attempts"] >= int(rep["max_attempts_per_incident"]):
                self.store.transition(inc["incident_id"], "REQUIRES_OFFLINE_ATTENTION", "attempt budget exhausted")
                emit("supervisor", "ERROR", f"breaker: {inc['incident_id']} requires offline attention",
                     incident_id=inc["incident_id"], correlation_id=inc["correlation_id"])
                continue
            last = self.st.last_dispatch.get(inc["fingerprint"], 0)
            backoff = float(rep["cooldown_seconds"]) * (2 ** max(0, inc["attempts"] - 1)) if inc["attempts"] else 0
            if now - last < backoff:
                continue
            if hour_count + len(out) >= int(rep["max_attempts_per_hour"]):
                emit("supervisor", "WARN", "factory-wide repair quota reached; deferring", incident_id=inc["incident_id"])
                break
            if len(in_repair) + len(out) >= int(rep["max_concurrent"]):
                break
            out.append(inc)
        return out

    def mark_dispatched(self, inc: dict) -> None:
        self.st.last_dispatch[inc["fingerprint"]] = time.time()
