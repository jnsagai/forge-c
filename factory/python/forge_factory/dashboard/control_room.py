"""Feature 007 Control Room routes (contract: specs/007-kpi-control-room/contracts/control-room-api.openapi.yaml).

Read-only GET projections plus one SSE stream, registered on the existing dashboard app so its loopback binding,
token roles and cookie are reused. No route here writes factory state or calls a model (FR-020, FR-026).
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse

STATIC = Path(__file__).parent / "static"


def register(app: FastAPI, role, toks: dict[str, str], floor=None, events=None) -> None:
    import threading

    from ..controlroom import config as C
    from ..controlroom import windows as W
    from ..controlroom.floor import Floor
    from ..controlroom.scorecard import COHORTS, EventCache, scorecard

    fl = floor or Floor()
    cache = events or EventCache()
    if events is None:  # production: fill the KPI event cache in the background (about a minute at start)
        threading.Thread(target=cache.warm, daemon=True, name="controlroom-warm").start()

    def cfg() -> dict:
        try:
            return C.load()
        except ValueError as exc:  # fail closed and say why
            raise HTTPException(500, str(exc)) from exc

    def floor_snapshot() -> dict:
        return fl.snapshot(cfg())

    @app.get("/control-room")
    def control_room_page(request: Request) -> HTMLResponse:
        html = (STATIC / "control-room.html").read_text()
        tok = request.cookies.get("forge_dashboard_session", "")
        who = next((r for r, t in toks.items() if tok and secrets.compare_digest(tok, t)), None)
        if who:  # first paint without waiting for the stream
            init = {"role": who, "floor": floor_snapshot()}
            if cache.ready.is_set():  # first paint with today's scorecard (the page then follows the viewer's choice)
                init["score"] = scorecard(cache, W.window("today", cfg()), "all")
            blob = json.dumps(init, default=str).replace("</", "<\\/")
            html = html.replace("<script>", f"<script>window.__INIT__={blob};</script>\n<script>", 1)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/control-room/floor")
    def cr_floor(r: str = Depends(role)) -> dict:
        return floor_snapshot()

    def window_or_422(window: str, start: str | None, end: str | None) -> dict:
        try:
            return W.window(window, cfg(), start=start, end=end)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/v1/control-room/scorecard")
    def cr_scorecard(r: str = Depends(role), window: str = Query("today", pattern="^(shift|today|7d|30d|custom)$"),
                     cohort: str = Query("all"), start: str | None = None, end: str | None = None) -> dict:
        if cohort not in COHORTS:
            raise HTTPException(422, f"cohort must be one of {COHORTS}")
        return scorecard(cache, window_or_422(window, start, end), cohort)

    @app.get("/api/v1/control-room/stream")
    async def cr_stream(request: Request, r: str = Depends(role), max_seconds: int = Query(60, ge=1, le=300)):
        async def gen():
            last, t0 = None, time.monotonic()
            while time.monotonic() - t0 < max_seconds:
                if await request.is_disconnected():
                    return
                snap = await asyncio.to_thread(floor_snapshot)
                if snap["content_hash"] != last:
                    last = snap["content_hash"]
                    yield f"event: floor\ndata: {json.dumps(snap, sort_keys=True)}\n\n"
                else:
                    hb = {k: snap[k] for k in ("generated_at", "data_age_s", "stale", "factory_status")}
                    yield f"event: heartbeat\ndata: {json.dumps(hb)}\n\n"
                await asyncio.sleep(1.0)
        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})
