"""CRE-T015 — CRE inside the existing 002 supervisor poll (no second daemon). Deterministic, zero model calls.

Per poll: (1) dependency breakers follow probe health (no write while healthy: closure); (2) every 002 incident gets a
CRE observation + a recovery scope `incident:<id>` whose FSM mirrors the 002 state (observe-only); (3) in PILOT/ACTIVE,
incidents of a dependency whose breaker is OPEN are withheld from repair dispatch (no repair storm). OBSERVE_ONLY
never changes routing. Any CRE error is contained by the caller: supervision never depends on CRE.
"""
from __future__ import annotations

from pathlib import Path

from .observe import from_incidents
from .policy import PolicyHolder
from .recovery import Breaker, RecoveryController
from .store import CREStore
from .taxonomy import classify

TERMINAL_002 = {"RESOLVED": "RECOVERED", "REQUIRES_OFFLINE_ATTENTION": "REQUIRES_OFFLINE_ATTENTION"}


class CREHook:
    def __init__(self, incident_db: Path, policy_holder: PolicyHolder | None = None):
        self.store = CREStore(incident_db)
        self.policy = policy_holder or PolicyHolder()
        self.db = incident_db

    def on_poll(self, samples: list, incident_store, eligible: list[dict]) -> list[dict]:
        pol = self.policy.current()
        br, ctl = Breaker(self.store, pol), RecoveryController(self.store, pol)
        status: dict[str, str] = {}
        for s in samples:  # one breaker per component; any failing check of the poll counts as one failure
            failing = s.status in ("DOWN", "DEGRADED") and bool(s.fault_type)
            prev = status.get(s.component, "HEALTHY")
            status[s.component] = "FAIL" if failing or prev == "FAIL" else (
                "HEALTHY" if s.status == "HEALTHY" and prev == "HEALTHY" else "UNKNOWN")
        for dep, st in sorted(status.items()):
            if st == "FAIL":
                br.record_failure(dep)
            elif st == "HEALTHY":
                br.record_success(dep)
        incidents = incident_store.all()
        if incidents:
            obs = {o["incident_id"]: o for o in from_incidents(self.db)}
            for inc in incidents:
                scope = f"incident:{inc['incident_id']}"
                o = obs.get(inc["incident_id"])
                if o is not None and self.store.insert_observation(o):
                    pass  # recorded once (content-addressed); the event is written by ingest/import paths
                if ctl.get(scope) is None:
                    ctl.open(scope, classify(inc["fault_type"]).failure_class, o["fingerprint"] if o else None)
                    ctl.step(scope, "fault")
                if inc["state"] in TERMINAL_002:
                    ctl.drive_to(scope, TERMINAL_002[inc["state"]], f"002 incident {inc['state']}")
        if pol.mode == "OBSERVE_ONLY":
            return eligible
        return [i for i in eligible if br.allow(i["component"])]  # OPEN: none; after cooldown: bounded probes
