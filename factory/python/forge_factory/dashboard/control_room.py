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
    from ..controlroom.pareto import History
    from ..controlroom.scorecard import COHORTS, EventCache, scorecard
    from ..controlroom.spc import i_mr, p_chart

    fl = floor or Floor()
    hist = History(root=getattr(fl, "root", None))
    cache = events or EventCache()
    if events is None:  # production: fill the KPI event cache in the background (about a minute at start)
        threading.Thread(target=cache.warm, daemon=True, name="controlroom-warm").start()

    def cfg() -> dict:
        try:
            return C.load()
        except ValueError as exc:  # fail closed and say why
            raise HTTPException(500, str(exc)) from exc

    memo: dict = {}

    def cached(key: str, ttl: float, fn):
        hit = memo.get(key)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        try:
            val = fn()
        except Exception:  # noqa: BLE001 - an unavailable input only removes its alerts; the floor stays live
            val = None
        memo[key] = (time.monotonic(), val)
        return val

    def today_score() -> dict | None:
        if not cache.ready.is_set():
            return None
        return cached("score", 30.0, lambda: scorecard(cache, W.window("today", cfg()), "all"))

    def quality_30d() -> dict | None:
        return cached("quality", 60.0, lambda: cr_quality("viewer", "30d", None))

    def floor_snapshot() -> dict:
        from ..controlroom.alerts import collect, from_scorecard

        c = cfg()
        sc, q = today_score(), quality_30d()
        viol = sum(1 for a in from_scorecard(sc, c) if a["condition"] == "SAFETY_PROCESS_VIOLATION")
        snap = fl.snapshot(c, violations_open=viol)  # an open violation decides the factory status (FR-017)
        snap["alerts"] = collect(snap, c, sc, q)["alerts"]
        return snap

    @app.get("/control-room")
    def control_room_page(request: Request) -> HTMLResponse:
        html = (STATIC / "control-room.html").read_text()
        tok = request.cookies.get("forge_dashboard_session", "")
        who = next((r for r, t in toks.items() if tok and secrets.compare_digest(tok, t)), None)
        if who:  # first paint without waiting for the stream
            init = {"role": who, "floor": floor_snapshot()}
            if cache.ready.is_set():  # first paint with today's scorecard (the page then follows the viewer's choice)
                init["score"] = scorecard(cache, W.window("today", cfg()), "all")
            init["quality"] = cr_quality(who, "30d", None)
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

    @app.get("/api/v1/control-room/quality")
    def cr_quality(r: str = Depends(role), window: str = Query("30d", pattern="^(7d|30d|90d)$"),
                   station: str | None = Query(None, pattern=r"^SWE\.[1-6]$")) -> dict:
        from datetime import UTC, datetime, timedelta

        from ..inspection.engine import PHASES

        c = cfg()
        now = datetime.now(UTC)
        start = (now - timedelta(days=int(window[:-1]))).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        charts = {p: {"first_pass_yield": p_chart(hist.first_pass_groups(start, end, p, c["tz"]), c["spc"]),
                      "time_to_pass_s": i_mr(hist.time_to_pass(start, end, p), c["spc"])}
                  for p in ([station] if station else PHASES)}
        try:
            from ..reliability import dashboard_api as R

            capa = [{k: x.get(k) for k in ("capa_id", "state", "root_cause_status", "root_cause_summary",
                                           "reproducer_id", "created_at", "updated_at")}
                    for x in R.capas().get("items", [])]
            capa_err = None
        except Exception as exc:  # noqa: BLE001 - shown as unavailable, never guessed
            capa, capa_err = [], f"CRE store unavailable: {type(exc).__name__}"
        return {"window": {"kind": window, "start_utc": start, "end_utc": end}, "station": station,
                "charts": charts, "pareto": hist.pareto(start, end, station)[:40],
                "capa": sorted(capa, key=lambda x: str(x.get("updated_at") or ""), reverse=True)[:30],
                "capa_error": capa_err,
                "notes": {"first_pass_yield": "per run: outcome of the first inspection at the station (daily subgroups)",
                          "time_to_pass_s": "per run: from the previous station's pass to this station's pass"}}

    @app.get("/api/v1/control-room/usage")
    def cr_usage(r: str = Depends(role), window: str = Query("7d", pattern="^(shift|today|7d|30d|custom)$"),
                 cohort: str = Query("all"), start: str | None = None, end: str | None = None) -> dict:
        from ..controlroom.usage import window_usage

        if cohort not in COHORTS:
            raise HTTPException(422, f"cohort must be one of {COHORTS}")
        w = window_or_422(window, start, end)
        if not cache.ready.is_set():
            return {"status": "WARMING_UP", "window": w, "cohort": cohort}
        return {"status": "OK", "window": w, "cohort": cohort,
                **window_usage(cache, w["start_utc"], w["end_utc"], cohort, cfg()["prices"])}

    @app.get("/api/v1/control-room/alerts")
    def cr_alerts(r: str = Depends(role)) -> dict:
        snap = floor_snapshot()
        return {"generated_at": snap["generated_at"], "alerts": snap["alerts"],
                "violations_open": snap.get("violations_open", 0),
                "acknowledgement": "per viewer, in the browser only; no factory state changes"}

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
