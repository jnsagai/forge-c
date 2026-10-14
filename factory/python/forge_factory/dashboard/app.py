"""T037–T041 — read-only human supervision dashboard (FastAPI, loopback, OSS; contract: dashboard-api.openapi.yaml).

* Auth: bearer token or `forge_dashboard_session` cookie. Roles: viewer (no security/audit channels) and
  auditor (all channels). Tokens live in $FORGE_STATE_DIR/dashboard/tokens.json (0600).
* All /api/v1 endpoints are GET/read-only projections; no SQL or file paths are exposed to the browser.
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


def create_app(store: EventStore | None = None, collect: bool = True, fabro_client=None) -> FastAPI:
    app = FastAPI(title="Forge-C Human Supervisor Dashboard API", version="0.4.0", docs_url=None, redoc_url=None)
    st = store or EventStore()
    col = Collector(st)
    toks = tokens()

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
        raise HTTPException(401, "authentication required")

    @app.get("/api/v1/health/live")
    def live() -> dict:
        return {"live": True}

    @app.get("/login")
    def login(token: str) -> RedirectResponse:
        if not any(secrets.compare_digest(token, t) for t in toks.values()):
            raise HTTPException(401, "bad token")
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("forge_dashboard_session", token, httponly=True, samesite="strict")
        return resp

    @app.get("/")
    def index(request: Request):
        from fastapi.responses import HTMLResponse

        html = (STATIC / "index.html").read_text()
        tok = request.cookies.get("forge_dashboard_session", "")
        who = next((r for r, t in toks.items() if tok and secrets.compare_digest(tok, t)), None)
        if who:  # server-side initial snapshot (same read-only projections as the API) for an immediate first paint
            init = {"me": me(who), "health": health(who), "runs": runs(who, None, 50, None),
                    "incidents": incidents(who, None, 20, None), "packages": packages(who, 20, None),
                    "mcp": mcp(who, 60, None), "lessons": lessons(who, 20, None), "tokens": tokens_ep(who, None, 20, None),
                    "events": st.query(["human", "workflow", "supervisor"], "INFO", limit=200,
                                       allowed_channels=ROLE_CHANNELS[who])}
            blob = json.dumps(init, default=str).replace("</", "<\\/")
            html = html.replace("<script>", f"<script>window.__INIT__={blob};</script>\n<script>", 1)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/me")
    def me(r: str = Depends(role)) -> dict:
        return {"role": r, "channels": sorted(ROLE_CHANNELS[r]), "default_view": {"channels": ["human", "workflow",
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
            u = token_usage(rid_f.read_text().strip())
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
            items.append({"work_order": "llm-gateway-meter", "basis": "reported" if all(x["basis"] == "reported"
                                                                                        for x in rows) else "mixed",
                          "requests": len(rows), "total_input": sum(x["tokens_input"] or 0 for x in rows),
                          "total_output": sum(x["tokens_output"] or 0 for x in rows),
                          "unknown_requests": sum(1 for x in rows if x["basis"] != "reported")})
        return page(items, limit, cursor)

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

    @app.exception_handler(HTTPException)
    async def http_err(_req: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return app


def main() -> int:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    uvicorn.run(create_app(), host="127.0.0.1", port=a.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
