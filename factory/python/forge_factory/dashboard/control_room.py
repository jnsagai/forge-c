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


def register(app: FastAPI, role, toks: dict[str, str], floor=None) -> None:
    from ..controlroom import config as C
    from ..controlroom.floor import Floor

    fl = floor or Floor()

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
            blob = json.dumps({"role": who, "floor": floor_snapshot()}, default=str).replace("</", "<\\/")
            html = html.replace("<script>", f"<script>window.__INIT__={blob};</script>\n<script>", 1)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/control-room/floor")
    def cr_floor(r: str = Depends(role)) -> dict:
        return floor_snapshot()

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
