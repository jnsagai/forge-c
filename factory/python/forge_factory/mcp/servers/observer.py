"""T017/KPI-T012 — forge-observer-mcp: read-only, bounded status/incident/event (and KPI) access for agents.

No SQL, no write paths, no unbounded dumps: every response is a small envelope with artifact refs.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import Field

from ...events.emit import CHANNELS, read_segment
from ...supervisor.store import IncidentStore
from ..sdk import Operation, ToolContext, ToolInput, build_server, result

MAX_EVENTS = 20


class StatusIn(ToolInput):
    pass


class IncidentIn(ToolInput):
    incident_id: str = Field(pattern=r"^inc-[0-9a-f]{12}$")


class EventsIn(ToolInput):
    channel: Literal["human", "workflow", "tools", "ai", "supervisor", "repair", "security", "audit", "metrics",
                     "knowledge"] = "workflow"
    run_id: str = Field(default="", max_length=100, pattern=r"^[A-Za-z0-9_.:-]*$")
    limit: int = Field(default=10, ge=1, le=MAX_EVENTS)


class KpiIn(ToolInput):
    kpi_id: str = Field(default="", pattern=r"^(K[0-9]{2})?$")


def get_status(ctx: ToolContext, a: StatusIn) -> dict:
    from ...common import state_dir

    hp = state_dir() / "supervisor" / "health.json"
    health = json.loads(hp.read_text()) if hp.is_file() else {"status": "UNKNOWN"}
    inc = IncidentStore().active()
    return result(ctx, "PASS", f"factory {health.get('status', 'UNKNOWN')}; active incidents {len(inc)}", [],
                  [f"INCIDENT:{i['incident_id']}:{i['state']}" for i in inc[:10]],
                  {"health": health.get("status", "UNKNOWN"), "active_incidents": len(inc),
                   "last_poll": health.get("last_poll")}, "forge-observer", input_obj=a.model_dump())


def get_incident(ctx: ToolContext, a: IncidentIn) -> dict:
    st = IncidentStore()
    inc = st.get(a.incident_id)
    if inc is None:
        return result(ctx, "BLOCKED", "unknown incident", issues=["INCIDENT_NOT_FOUND"], tool="forge-observer")
    bundle = {"incident": st.to_contract(inc), "history": st.history(a.incident_id)[-10:],
              "attempts": [{k: x[k] for k in ("attempt_id", "status", "tests")} for x in st.attempts(a.incident_id)][-3:]}
    data = json.dumps(bundle, sort_keys=True).encode()
    return result(ctx, "PASS", f"{a.incident_id} {inc['state']} {inc['component']}/{inc['fault_type']}",
                  [ctx.store(data, "json")], [inc.get("last_error") or "-"],
                  {"attempts": inc["attempts"], "state": inc["state"], "component": inc["component"],
                   "fault_type": inc["fault_type"], "recoverable": inc["recoverable"]}, "forge-observer",
                  input_obj=a.model_dump())


def query_events(ctx: ToolContext, a: EventsIn) -> dict:
    assert a.channel in CHANNELS
    evs = [e for e in read_segment() if e["channel"] == a.channel and (not a.run_id or e.get("run_id") == a.run_id)]
    tail = evs[-a.limit:]
    return result(ctx, "PASS", f"{len(tail)}/{len(evs)} {a.channel} events", [ctx.store(json.dumps(tail).encode(), "json")],
                  [f"{e['level']}:{e['message']}"[:120] for e in tail[-8:]], {"matched": len(evs)}, "forge-observer",
                  input_obj=a.model_dump())


def get_kpis(ctx: ToolContext, a: KpiIn) -> dict:
    from ...kpi.service import latest_snapshot

    snap = latest_snapshot()
    if snap is None:
        return result(ctx, "BLOCKED", "no KPI snapshot computed yet", issues=["KPI_SNAPSHOT_MISSING"], tool="forge-kpi")
    vals = [m for m in snap["metric_values"] if not a.kpi_id or m["metric_id"] == a.kpi_id]
    issues = [f"{m['metric_id']}{json.dumps(m['filters'], sort_keys=True)[:40]}:{m['status']}:{m['value']}"[:120]
              for m in vals][:20]
    return result(ctx, "PASS", f"KPI snapshot {snap['snapshot_id']} ({len(vals)} KPIs)",
                  [f"kpi-snapshot:{snap['snapshot_id']}"], issues, {"kpis": len(vals)}, "forge-kpi",
                  input_obj=a.model_dump())


def get_kpi_evidence(ctx: ToolContext, a: KpiIn) -> dict:
    from ...kpi.service import latest_snapshot

    snap = latest_snapshot()
    if snap is None or not a.kpi_id:
        return result(ctx, "BLOCKED", "kpi_id and snapshot required", issues=["KPI_EVIDENCE_UNAVAILABLE"],
                      tool="forge-kpi")
    rows = [x for x in snap["metric_values"] if x["metric_id"] == a.kpi_id]
    if not rows:
        return result(ctx, "BLOCKED", "unknown KPI", issues=["KPI_NOT_FOUND"], tool="forge-kpi")
    data = json.dumps(rows, sort_keys=True).encode()
    k = rows[0]
    return result(ctx, "PASS", f"{a.kpi_id} {k['status']} n={k.get('numerator')} d={k.get('denominator')} rows={len(rows)}",
                  [ctx.store(data, "json"), f"kpi-snapshot:{snap['snapshot_id']}"], [],
                  {"event_refs": sum(len(r["source_event_refs"]) for r in rows), "snapshot": snap["snapshot_id"]},
                  "forge-kpi", input_obj=a.model_dump())


OPERATIONS = [
    Operation("get_status", StatusIn, get_status, "Read-only factory health + active incidents."),
    Operation("get_incident", IncidentIn, get_incident, "Bounded incident bundle (state, history, attempts)."),
    Operation("query_events", EventsIn, query_events, "Last <=20 events of one channel (read-only)."),
    Operation("get_kpis", KpiIn, get_kpis, "Read-only KPI values from the latest snapshot."),
    Operation("get_kpi_evidence", KpiIn, get_kpi_evidence, "Numerator/denominator/event refs for one KPI."),
]

if __name__ == "__main__":
    build_server("forge-observer-mcp", OPERATIONS).run("stdio")
