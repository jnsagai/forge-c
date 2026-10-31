"""T037–T041 — read-only human supervision dashboard (FastAPI, loopback, OSS; contract: dashboard-api.openapi.yaml).

* Auth: bearer token or `forge_dashboard_session` cookie. Roles: viewer (no security/audit channels) and
  auditor (all channels). Tokens live in $FORGE_STATE_DIR/dashboard/tokens.json (0600). Owner decision
  OD-2026-10-19-09: sign-in can be switched off until deployment (config/factory/dashboard-access.yaml); requests
  from this machine then get the configured anonymous role, and (OD-2026-10-19-10) so do the owner's trusted devices
  over Tailscale. Every other client still needs a token, and the operator token is unchanged.
* All /api/v1 endpoints are GET/read-only projections; no SQL or file paths are exposed to the browser. Single
  exception (AFO-T058): POST /api/v1/afo/operator/{pause,drain,resume}, bearer operator token only, audited.
* Display filters (channels, severity, run, agent, phase, search) never alter capture policy (T039).
* SSE `/api/v1/events/stream` resumes from Last-Event-ID; `/api/v1/events` is the polling fallback (T040).
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from ..common import REPO_ROOT, state_dir
from ..events.store import Collector, EventStore

ALL_CHANNELS = {"human", "workflow", "tools", "ai", "supervisor", "repair", "security", "audit", "metrics", "knowledge"}
ROLE_CHANNELS = {"viewer": ALL_CHANNELS - {"security", "audit"}, "auditor": ALL_CHANNELS}
STATIC = Path(__file__).parent / "static"


def tokens() -> dict[str, str]:
    p = state_dir() / "dashboard" / "tokens.json"
    if not p.is_file():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"viewer": secrets.token_urlsafe(24), "auditor": secrets.token_urlsafe(24)}))
        os.chmod(p, 0o600)
    return json.loads(p.read_text())


def page(items: list, limit: int, cursor: str | None) -> dict:
    start = int(cursor) if cursor and cursor.isdigit() else 0
    chunk = items[start:start + limit]
    return {"items": chunk, "next_cursor": str(start + limit) if start + limit < len(items) else None}


def workspaces() -> list[Path]:
    root = state_dir() / "workorders"
    return sorted(root.glob("*/workspace")) if root.is_dir() else []


def create_app(store: EventStore | None = None, collect: bool = True, fabro_client=None, control_room_floor=None,
               control_room_events=None) -> FastAPI:
    app = FastAPI(title="Forge-C Human Supervisor Dashboard API", version="0.4.0", docs_url=None, redoc_url=None)
    st = store or EventStore()
    col = Collector(st)
    toks = tokens()
    from .access import load as load_access

    access = load_access()

    def peer(request: Request | None) -> tuple[str | None, str | None]:
        """(client address, local listen address) of the connection; the socket peer, never a forwarded header."""
        if request is None:
            return None, None
        server = request.scope.get("server")
        return (request.client.host if request.client else None), (server[0] if server else None)

    def who_of(request: Request) -> str | None:
        """Role of a page request: its session cookie, else the anonymous role when sign-in is disabled."""
        from .access import anonymous_role

        tok = request.cookies.get("forge_dashboard_session", "")
        who = next((r for r, t in toks.items() if tok and secrets.compare_digest(tok, t)), None)
        return who or anonymous_role(access, *peer(request))

    def collector_loop() -> None:
        while True:
            try:
                col.ingest_segment()
                for ws in workspaces():
                    rid = ws / ".forge-run" / "fabro_run_id"
                    if rid.is_file():
                        col.ingest_fabro_run(rid.read_text().strip(), fabro_client)
            except Exception:  # noqa: BLE001,S110 - collector must never take the dashboard down
                pass
            time.sleep(2)

    if collect:
        threading.Thread(target=collector_loop, daemon=True).start()

    def role(authorization: str | None = Header(default=None), request: Request = None) -> str:  # type: ignore[assignment]
        tok = (authorization or "").removeprefix("Bearer ").strip() or request.cookies.get("forge_dashboard_session", "")
        for r, t in toks.items():
            if tok and secrets.compare_digest(tok, t):
                return r
        from .access import anonymous_role

        anon = anonymous_role(access, *peer(request))
        if anon:  # OD-2026-10-19-09/-10: no sign-in until deployment - this machine and the trusted Tailscale devices
            return anon
        raise HTTPException(401, "authentication required")

    @app.get("/api/v1/health/live")
    def live() -> dict:
        return {"live": True}

    @app.get("/login")
    def login(token: str, next: str = "/") -> RedirectResponse:  # noqa: A002 - query parameter name
        if not any(secrets.compare_digest(token, t) for t in toks.values()):
            raise HTTPException(401, "bad token")
        resp = RedirectResponse(next if next in ("/", "/control-room") else "/", status_code=303)
        resp.set_cookie("forge_dashboard_session", token, httponly=True, samesite="strict")
        return resp

    @app.get("/")
    def index(request: Request):
        from fastapi.responses import HTMLResponse

        html = (STATIC / "index.html").read_text()
        who = who_of(request)
        if who:  # server-side initial snapshot (same read-only projections as the API) for an immediate first paint
            init = {"me": me(who), "health": health(who), "runs": runs(who, None, 50, None),
                    "incidents": incidents(who, None, 20, None), "packages": packages(who, 20, None),
                    "mcp": mcp(who, 60, None), "lessons": lessons(who, 20, None), "tokens": tokens_ep(who, None, 20, None),
                    "events": st.query(["human", "workflow", "supervisor"], "INFO", limit=200,
                                       allowed_channels=ROLE_CHANNELS[who])}
            try:
                init["kpis"] = kpis(who, 7, None, None, None)
            except Exception:  # noqa: BLE001,S110 - KPI tiles then load asynchronously instead
                pass
            blob = json.dumps(init, default=str).replace("</", "<\\/")
            html = html.replace("<script>", f"<script>window.__INIT__={blob};</script>\n<script>", 1)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/me")
    def me(r: str = Depends(role)) -> dict:
        return {"role": r, "auth": access["auth"],
                "channels": sorted(ROLE_CHANNELS[r]), "default_view": {"channels": ["human", "workflow",
                                                                                               "supervisor"],
                                                                                  "min_level": "INFO"}}

    @app.get("/api/v1/health")
    def health(r: str = Depends(role)) -> dict:
        p = state_dir() / "supervisor" / "health.json"
        if not p.is_file():
            return {"status": "UNKNOWN", "last_supervisor_poll": None, "components": []}
        h = json.loads(p.read_text())
        comp = [{"id": c["id"], "status": c["status"] if c["status"] in ("HEALTHY", "DEGRADED", "DOWN") else "UNKNOWN",
                 "last_checked": c.get("last_checked")} for c in h.get("components", [])]
        return {"status": h.get("status", "UNKNOWN") if h.get("status") in ("HEALTHY", "DEGRADED", "UNAVAILABLE")
                else "UNKNOWN", "last_supervisor_poll": h.get("last_poll"), "components": comp,
                "model_calls": h.get("model_calls"), "polls": h.get("polls")}

    @app.get("/api/v1/runs")
    def runs(r: str = Depends(role), state: str | None = None, limit: int = Query(50, ge=1, le=200),
             cursor: str | None = None) -> dict:
        items = []
        for ws in workspaces():
            rid_f, pkg_f = ws / ".forge-run/fabro_run_id", ws / ".forge-run/package.json"
            gates = ws / ".forge-run/gates/gate-log.jsonl"
            from ..inspection.engine import PHASES, Store

            s = Store(ws)
            phases = {}
            for p in PHASES:
                nb, ni = len(s.baselines(p)), len(s.inspections(p))
                g = s.gate(p)["decision"]
                started = nb or ni or any(f'"phase": "{p}"' in x for x in (gates.read_text().splitlines()
                                                                           if gates.is_file() else []))
                phases[p] = {"baselines": nb, "inspections": ni, "decision": g if started else "PENDING"}
            pkg = json.loads(pkg_f.read_text()) if pkg_f.is_file() else None
            items.append({"work_order": ws.parent.name, "fabro_run_id": rid_f.read_text().strip() if rid_f.is_file() else None,
                          "phases": phases, "gate_events": len(gates.read_text().splitlines()) if gates.is_file() else 0,
                          "package_status": pkg["package_status"] if pkg else None,
                          "state": "PACKAGED" if pkg else "ACTIVE"})
        if state:
            items = [i for i in items if i["state"] == state]
        return page(items, limit, cursor)

    @app.get("/api/v1/agents")
    def agents(r: str = Depends(role), limit: int = Query(50, ge=1, le=200), cursor: str | None = None) -> dict:
        from ..registry.agents import load_agents

        lock = json.loads((REPO_ROOT / "config/factory/skills.lock.json").read_text())["skills"]
        items = [{"role": a.id, "phase": a.phase, "skill": a.skill, "skill_sha256": lock.get(a.id, {}).get("sha256"),
                  "model": a.model, "readonly": a.readonly, "tools": len(a.allowed_tools),
                  "max_stage_tokens": a.max_stage_tokens} for a in load_agents()[0]]
        return page(items, limit, cursor)

    @app.get("/api/v1/mcp")
    def mcp(r: str = Depends(role), limit: int = Query(50, ge=1, le=200), cursor: str | None = None) -> dict:
        from ..mcp.preflight import op_catalog

        items = [{"op": k, **{x: v[x] for x in ("server", "status", "mandatory", "missing_tools")}}
                 for k, v in sorted(op_catalog().items())]
        return page(items, limit, cursor)

    @app.get("/api/v1/incidents")
    def incidents(r: str = Depends(role), status: str | None = None, limit: int = Query(50, ge=1, le=200),
                  cursor: str | None = None) -> dict:
        from ..supervisor.store import IncidentStore

        s = IncidentStore()
        items = [{**s.to_contract(i), "attempts_detail": [{k: a[k] for k in ("attempt_id", "status")}
                                                          for a in s.attempts(i["incident_id"])]} for i in s.all(500)]
        if status:
            items = [i for i in items if i["state"] == status]
        return page(items, limit, cursor)

    @app.get("/api/v1/lessons")
    def lessons(r: str = Depends(role), limit: int = Query(50, ge=1, le=200), cursor: str | None = None) -> dict:
        from ..knowledge.store import LessonStore

        items = [{k: le.get(k) for k in ("lesson_id", "state", "source_incident_id", "remedy", "expires_at")}
                 for le in LessonStore().list()]
        return page(items, limit, cursor)

    @app.get("/api/v1/packages")
    def packages(r: str = Depends(role), limit: int = Query(50, ge=1, le=200), cursor: str | None = None) -> dict:
        from ..release.finalize import archive_root

        items = []
        for f in sorted(archive_root().glob("*/finalize-result.json")):
            d = json.loads(f.read_text())
            items.append({k: d.get(k) for k in ("run_id", "package_status", "gap_count", "archive_sha256",
                                                 "finalized_at", "scope")})
        return page(items, limit, cursor)

    @app.get("/api/v1/tokens")
    def tokens_ep(r: str = Depends(role), run_id: str | None = None, limit: int = Query(50, ge=1, le=200),
                  cursor: str | None = None) -> dict:
        from ..release.finalize import token_usage

        items = []
        for ws in workspaces():
            rid_f = ws / ".forge-run/fabro_run_id"
            if not rid_f.is_file() or (run_id and rid_f.read_text().strip() != run_id):
                continue
            u = token_usage(rid_f.read_text().strip(), ws)
            tr = ws / "evidence/tool-results.jsonl"
            mcp_bytes = [len(x) for x in tr.read_text().splitlines()] if tr.is_file() else []
            items.append({"work_order": ws.parent.name, "fabro_run_id": rid_f.read_text().strip(), "basis": u["basis"],
                          "total_input": u.get("total_input"), "total_output": u.get("total_output"),
                          "by_stage": u.get("by_stage", []), "mcp_results": len(mcp_bytes),
                          "mcp_result_bytes_max": max(mcp_bytes) if mcp_bytes else 0,
                          "mcp_result_bytes_median": sorted(mcp_bytes)[len(mcp_bytes) // 2] if mcp_bytes else 0})
        meter = state_dir() / "llm-gateway" / "usage.jsonl"
        if meter.is_file() and not run_id:
            rows = [json.loads(x) for x in meter.read_text().splitlines() if x.strip()]
            rows = [x for x in rows if "sample" not in x]  # feature 010 resource samples are not requests
            items.append({"work_order": "llm-gateway-meter", "basis": "reported" if all(x["basis"] == "reported"
                                                                                        for x in rows) else "mixed",
                          "requests": len(rows), "total_input": sum(x["tokens_input"] or 0 for x in rows),
                          "total_output": sum(x["tokens_output"] or 0 for x in rows),
                          "unknown_requests": sum(1 for x in rows if x["basis"] != "reported")})
        return page(items, limit, cursor)

    kpi_cache: dict = {}

    def kpi_events() -> list[dict]:
        from ..kpi.sources import collect_all

        now = time.monotonic()
        if "events" not in kpi_cache or now - kpi_cache["t"] > 30:  # bounded aggregation cost (KPI-T014)
            kpi_cache.update(events=collect_all(), t=now)
        return kpi_cache["events"]

    @app.get("/api/v1/kpis")
    def kpis(r: str = Depends(role), window_days: int = Query(7, ge=1, le=90), order_id: str | None = None,
             target_mcu: str | None = None, metric_id: str | None = Query(None, pattern=r"^K(0[1-9]|1[0-9]|20)$")) -> dict:
        from ..kpi.engine import snapshot
        from ..kpi.service import load_baselines, window

        evs = kpi_events()
        if order_id or target_mcu:  # production-class filter: numerator AND denominator recomputed together
            keep = {e["order_id"] for e in evs if e["type"] == "work_order.admitted"
                    and (not order_id or e["order_id"] == order_id)
                    and (not target_mcu or e["payload"]["class"].get("target_mcu") == target_mcu)}
            evs = [e for e in evs if e["order_id"] in keep or e["order_id"] == "factory"]
        ws_, we_ = window(window_days)
        snap = snapshot(evs, ws_, we_, "IN_PROGRESS", load_baselines())
        if metric_id:
            snap["metric_values"] = [m for m in snap["metric_values"] if m["metric_id"] == metric_id]
        return snap

    @app.get("/api/v1/kpis/{metric_id}/evidence")
    def kpi_evidence(metric_id: str, r: str = Depends(role), window_days: int = Query(7, ge=1, le=90)) -> dict:
        if not (len(metric_id) == 3 and metric_id[0] == "K" and metric_id[1:].isdigit() and 1 <= int(metric_id[1:]) <= 20):
            raise HTTPException(422, "bad metric id")
        snap = kpis(r, window_days, None, None, metric_id)
        by_id = {e["event_id"]: e for e in kpi_events()}
        runs = {}
        for ws in workspaces():
            rid = ws / ".forge-run/fabro_run_id"
            if rid.is_file():
                runs[ws.parent.name] = rid.read_text().strip()
        rows = []
        for m in snap["metric_values"]:
            src = [by_id[x] for x in m["source_event_refs"][:50] if x in by_id]
            rows.append({"metric": m, "source_events": [{k: e.get(k) for k in ("event_id", "type", "ts_utc", "order_id",
                                                                                "attempt_id", "phase", "evidence_refs")}
                                                        for e in src],
                         "trace_runs": sorted({runs[e["attempt_id"]] for e in src if e["attempt_id"] in runs})})
        return {"metric_id": metric_id, "snapshot_id": snap["snapshot_id"], "formula_version": snap["formula_version"],
                "rows": rows}

    # ---- feature 004 CRE: read-only Reliability view (projections over the CRE tables of the 002 incident DB) ----
    @app.get("/api/v1/reliability/summary")
    def rel_summary(r: str = Depends(role)) -> dict:
        from ..reliability import dashboard_api as R
        return R.summary(r)

    @app.get("/api/v1/reliability/failure-modes")
    def rel_modes(r: str = Depends(role), failure_class: str | None = Query(None, pattern=r"^[A-Z_]{3,40}$"),
                  recurring: bool | None = None, limit: int = Query(50, ge=1, le=200),
                  category: str | None = Query(None, pattern=r"^[A-Z_]{3,40}$"),
                  model: str | None = Query(None, pattern=r"^[A-Za-z0-9._:-]{1,60}$"),
                  since: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}[T0-9:.Z]*$"),
                  until: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}[T0-9:.Z]*$"),
                  revision: str | None = Query(None, pattern=r"^[0-9a-f]{4,40}$")) -> dict:
        from ..reliability import dashboard_api as R
        return R.failure_modes(failure_class, recurring, limit, category, model, since, until, revision)

    @app.get("/api/v1/reliability/failure-modes/{fingerprint}")
    def rel_obs(fingerprint: str, r: str = Depends(role)) -> dict:
        from ..reliability import dashboard_api as R
        if not (fingerprint.startswith("cfp1-") and len(fingerprint) == 45):
            raise HTTPException(422, "bad fingerprint")
        return R.observations(fingerprint)

    @app.get("/api/v1/reliability/capa")
    def rel_capa(r: str = Depends(role)) -> dict:
        from ..reliability import dashboard_api as R
        return R.capas()

    @app.get("/api/v1/reliability/metrics")
    def rel_metrics(r: str = Depends(role), metric: str | None = Query(None, pattern=r"^(CRE-R\d{2}[A-Za-z0-9.-]*|K\d{2})$"),
                    cohort: str | None = Query(None, max_length=200)) -> dict:
        from ..reliability import dashboard_api as R
        return R.metrics(metric, cohort)

    @app.get("/api/v1/reliability/promotions")
    def rel_promotions(r: str = Depends(role), candidate: str | None = Query(None, pattern=r"^[0-9a-f]{4,40}$"),
                       decision: str | None = Query(None, pattern=r"^[A-Z_]{3,40}$")) -> dict:
        from ..reliability import dashboard_api as R
        return R.promotions(candidate, decision)

    @app.get("/api/v1/reliability/anomalies")
    def rel_anomalies(r: str = Depends(role)) -> dict:
        from ..reliability import dashboard_api as R
        return R.anomalies()

    # ---- feature 006 EASA: read-only Assurance view (evidence records and workspace files only) ----
    @app.get("/api/v1/assurance/summary")
    def easa_summary(r: str = Depends(role)) -> dict:
        from ..assurance import dashboard_api as A
        return A.summary()

    @app.get("/api/v1/assurance/workorders")
    def easa_workorders(r: str = Depends(role), limit: int = Query(30, ge=1, le=100)) -> dict:
        from ..assurance import dashboard_api as A
        return {"items": A.workorders(limit)}

    @app.get("/api/v1/assurance/workorders/{wo}")
    def easa_workorder(wo: str, r: str = Depends(role)) -> dict:
        from ..assurance import dashboard_api as A
        try:
            return A.workorder(wo)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    # ---- feature 005 AFO: Autonomy view (read-only projections; operator controls need the operator token) ----
    @app.get("/api/v1/afo/summary")
    def afo_summary(r: str = Depends(role)) -> dict:
        from ..afo import dashboard_api as F
        return F.summary()

    @app.get("/api/v1/afo/orders")
    def afo_orders(r: str = Depends(role), state: str | None = Query(None, pattern=r"^[A-Z_]{4,30}$"),
                   limit: int = Query(50, ge=1, le=200), cursor: str | None = None) -> dict:
        from ..afo import dashboard_api as F
        try:
            return page(F.orders(state), limit, cursor)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/v1/afo/orders/{oid}")
    def afo_order(oid: str, r: str = Depends(role)) -> dict:
        from ..afo import dashboard_api as F
        try:
            return F.order(oid, auditor=r == "auditor")
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, "no such order") from exc

    @app.get("/api/v1/afo/dead-letters")
    def afo_dlq(r: str = Depends(role), state: str | None = Query(None, pattern=r"^(OPEN|ACKNOWLEDGED|CLOSED)$"),
                limit: int = Query(50, ge=1, le=200), cursor: str | None = None) -> dict:
        from ..afo import dashboard_api as F
        return page(F.dead_letters(state), limit, cursor)

    @app.get("/api/v1/afo/proposals")
    def afo_proposals(r: str = Depends(role), limit: int = Query(50, ge=1, le=200), cursor: str | None = None) -> dict:
        from ..afo import dashboard_api as F
        return page(F.proposals(), limit, cursor)

    @app.get("/api/v1/afo/operations")
    def afo_operations(r: str = Depends(role)) -> dict:
        from ..afo import dashboard_api as F
        return F.operations(auditor=r == "auditor")

    @app.post("/api/v1/afo/operator/{action}")
    async def afo_operator(action: str, request: Request, authorization: str | None = Header(default=None)) -> dict:
        """AFO-T058: pause/drain/resume. Bearer operator token ONLY (never the session cookie, so a cross-site form
        cannot ride a browser session: CSRF-safe by construction), JSON body with a reason; every denial is audited."""
        from ..afo import dashboard_api as F
        if action not in ("pause", "drain", "resume"):
            raise HTTPException(404, "unknown action")
        authentication = F.operator_authentication(authorization)
        if authentication is None:
            who = "cookie-session" if request.cookies.get("forge_dashboard_session") else (
                "bearer" if authorization else "anonymous")
            F.audit_denied(action, who, "no valid operator bearer token")
            raise HTTPException(403 if authorization else 401, "operator token required")
        try:
            body = await request.json()
        except ValueError:
            body = {}
        try:
            return {"control": F.control(action, "dashboard-operator", str(body.get("reason", ""))[:300],
                                         authentication=authentication)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/v1/events")
    def events(r: str = Depends(role), channel: str | None = None, min_level: str = "INFO", run_id: str | None = None,
               agent_id: str | None = None, phase: str | None = None, q: str | None = Query(None, max_length=200),
               after_id: str | None = None, limit: int = Query(100, ge=1, le=500)) -> dict:
        if min_level not in ("ERROR", "WARN", "INFO", "DEBUG", "TRACE"):
            raise HTTPException(422, "bad min_level")
        chans = [c for c in channel.split(",") if c] if channel else None
        return st.query(chans, min_level, run_id, agent_id, phase, q, int(after_id) if after_id and after_id.isdigit() else 0,
                        limit, ROLE_CHANNELS[r])

    @app.get("/api/v1/events/stream")
    async def stream(request: Request, r: str = Depends(role), last_event_id: str | None = Header(default=None),
                     channel: str | None = None, min_level: str = "INFO", max_seconds: int = Query(25, ge=1, le=300)):
        after = request.query_params.get("after", "0") or "0"
        start = int(last_event_id) if last_event_id and last_event_id.isdigit() else (int(after) if after.isdigit() else 0)
        chans = [c for c in channel.split(",") if c] if channel else None

        async def gen():
            cur, t0 = start, time.monotonic()
            while time.monotonic() - t0 < max_seconds:
                if await request.is_disconnected():
                    return
                page_ = st.query(chans, min_level, after_seq=cur, limit=200, allowed_channels=ROLE_CHANNELS[r])
                for ev in page_["items"]:
                    cur = ev["seq"]
                    yield f"id: {ev['seq']}\nevent: forge\ndata: {json.dumps(ev, sort_keys=True)}\n\n"
                yield ": keepalive\n\n"
                await asyncio.sleep(1.0)
        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    from .control_room import register as register_control_room  # feature 007: manager view, read-only

    register_control_room(app, role, who_of, control_room_floor, control_room_events, access)

    @app.exception_handler(HTTPException)
    async def http_err(_req: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return app


def main() -> int:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", action="append", default=None,
                    help="listen address; repeatable (e.g. 127.0.0.1 plus a Tailscale/LAN address for a phone). "
                         "Other clients need a dashboard token, except trusted devices over Tailscale "
                         "(config/factory/dashboard-access.yaml).")
    a = ap.parse_args()
    import socket

    socks = []
    for h in a.host or ["127.0.0.1"]:
        s = socket.socket(socket.AF_INET6 if ":" in h else socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((h, a.port))
        socks.append(s)
    # no reverse proxy: the client address is the socket peer (sign-in exemptions are by address)
    uvicorn.Server(uvicorn.Config(create_app(), log_level="warning", proxy_headers=False)).run(sockets=socks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
