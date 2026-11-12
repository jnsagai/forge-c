"""Scorecard (CR-T019; research R4): output counts and K01-K20 for a window and its previous window.

K-metrics are the feature-003 engine's values, passed through unchanged (FR-006, SC-003). The Control Room only
adds the presentation status: MEASURED / INSUFFICIENT_SAMPLE show a value; every other engine status
(NOT_APPLICABLE, UNKNOWN, NOT_COMPUTABLE) shows NOT_MEASURED with the engine's status and explanation as the reason.

Cohorts: the 003 production KPIs exclude user-authorized cloud-model runs (kpi.sources.collect_all). Since owner
decisions OD-2026-10-19-06/08 every run uses cloud models, so the Control Room offers `production` (the 003 rule,
unchanged), `cloud` and `all`, always labelled; nothing is mixed silently.

Event cache: KPI source events per workspace are cached in memory. A finished attempt (sealed package) is immutable
and cached for the process lifetime; a running attempt is re-read at most every REFRESH_S. A warm-up thread fills
the cache at start (reading Fabro usage/stage events of ~170 runs takes about a minute); until it finishes the
scorecard answers WARMING_UP instead of partial numbers.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ..common import state_dir

COHORTS = ("all", "cloud", "production")
REFRESH_S = 30.0
QUIET_S = 6 * 3600.0  # an unsealed attempt with no file change for 6 h (the run timeout) is no longer running
SHOWN = ("MEASURED", "INSUFFICIENT_SAMPLE")


def cohort_of(ws: Path) -> str:
    p = ws / ".forge-run/model-profile.json"
    try:
        local = json.loads(p.read_text()).get("local_only", True) if p.is_file() else True
    except (OSError, ValueError):
        local = True
    return "production" if local else "cloud"


def _fabro(ws: Path) -> tuple[dict | None, list[dict] | None]:
    rid = ws / ".forge-run/fabro_run_id"
    if not rid.is_file():
        return None, None
    try:
        from ..fabro.client import client_for_workspace

        c = client_for_workspace(ws, timeout=10)
        r = rid.read_text().strip()
        return c.usage(r), [e for e in c.iter_events(r) if e["event"] in ("stage.started", "stage.completed",
                                                                          "stage.failed")]
    except Exception:  # noqa: BLE001 - unavailable usage stays UNKNOWN in the engine
        return None, None


class EventCache:
    def __init__(self, root: Path | None = None, fabro=_fabro) -> None:
        self.root, self.fabro = root, fabro
        self._c: dict[Path, dict] = {}
        self._lock = threading.Lock()
        self.ready = threading.Event()
        self.error: str | None = None

    def _workspaces(self) -> list[Path]:
        r = self.root or state_dir() / "workorders"
        return sorted(r.glob("*/workspace")) if r.is_dir() else []

    def _key(self, ws: Path) -> tuple:
        out = []
        for p in (".forge-run/package.json", ".forge-run/gates/gate-log.jsonl", ".forge-run/manifest.json"):
            try:
                st = (ws / p).stat()
                out.append((st.st_size, st.st_mtime))
            except OSError:
                out.append(None)
        return tuple(out)

    def refresh(self) -> None:
        from ..kpi.sources import from_workspace

        for ws in self._workspaces():
            key = self._key(ws)
            with self._lock:
                c = self._c.get(ws)
            sealed = (ws / ".forge-run/package.json").is_file()
            # unchanged files: a sealed or long-quiet attempt is final; a recently active one is re-read (Fabro
            # stage/usage events keep arriving while it runs) at most every REFRESH_S
            quiet = all(k is None or time.time() - k[1] > QUIET_S for k in key)
            if c and c["key"] == key and (sealed or quiet or time.monotonic() - c["t"] < REFRESH_S):
                continue
            usage, stages = self.fabro(ws)
            evs = from_workspace(ws, fabro_usage=usage, fabro_stage_events=stages)
            with self._lock:
                self._c[ws] = {"key": key, "t": time.monotonic(), "cohort": cohort_of(ws), "events": evs}

    def warm(self) -> None:
        try:
            self.refresh()
        except Exception as exc:  # noqa: BLE001 - reported, never guessed around
            self.error = f"{type(exc).__name__}: {str(exc)[:200]}"
        finally:
            self.ready.set()

    def events(self, cohort: str) -> list[dict]:
        from ..kpi.sources import dedup_sort, from_incidents, from_supervisor_events

        if cohort not in COHORTS:
            raise ValueError(f"BAD_COHORT:{cohort}")
        self.refresh()
        with self._lock:
            evs = [e for c in self._c.values() if cohort in ("all", c["cohort"]) for e in c["events"]]
        return dedup_sort(evs + from_incidents() + from_supervisor_events())


def present(m: dict) -> dict:
    """Engine value -> displayed value; the engine's own fields are kept unchanged."""
    shown = m["status"] in SHOWN
    return {**m, "display": "VALUE" if shown else "NOT_MEASURED",
            "reason": None if shown else f"{m['status']}: {m.get('explanation') or 'inputs missing'}",
            "low_sample": m["status"] == "INSUFFICIENT_SAMPLE"}


def counts(events: list[dict], start: str, end: str) -> dict:
    from ..kpi.sources import dedup_sort

    inw = [e for e in dedup_sort(events) if start <= e["ts_utc"] <= end]  # replayed events never count twice
    started = sorted({e["order_id"] for e in inw if e["type"] == "work_order.admitted"})
    attempts = sorted({e["attempt_id"] for e in inw if e["type"] == "work_order.admitted"})
    closed = [e for e in inw if e["type"] == "work_order.closed"]
    ready = [e for e in closed if e["payload"].get("outcome") in ("READY_FOR_OFFLINE_REVIEW", "READY")]
    blocked = [e for e in closed if e["payload"].get("outcome") == "BLOCKED"]

    def c(items, refs):
        return {"value": len(items), "n": len(items), "evidence": refs[:50]}
    return {"started_orders": c(started, started), "started_attempts": c(attempts, attempts),
            "packages_ready": c(ready, [e["attempt_id"] for e in ready]),
            "packages_blocked": c(blocked, [e["attempt_id"] for e in blocked])}


def scorecard(cache: EventCache, win: dict, cohort: str = "all") -> dict:
    from ..kpi.engine import catalog, snapshot, learning_metrics
    from ..kpi.service import load_baselines

    if not cache.ready.is_set():
        return {"status": "WARMING_UP", "window": win, "cohort": cohort,
                "reason": "reading run records for the first time (about a minute after start)"}
    evs = cache.events(cohort)
    base = load_baselines()
    cur = snapshot(evs, win["start_utc"], win["end_utc"], "IN_PROGRESS", base)
    prev = snapshot(evs, win["previous"]["start_utc"], win["previous"]["end_utc"], "IN_PROGRESS", base)
    k20 = next((m for m in cur["metric_values"] if m["metric_id"] == "K20"), None)
    return {"status": "OK", "window": win, "cohort": cohort,
            'learning':learning_metrics() if cohort == 'all' else {'status':'UNKNOWN','reason':'cohort-specific learning comparison not recorded'},
            "cohort_note": {"all": "includes cloud-model runs (owner decisions OD-2026-10-19-06/08)",
                            "cloud": "cloud-model runs only",
                            "production": "feature-003 production KPIs: local-model runs only"}[cohort],
            "counts": counts(evs, win["start_utc"], win["end_utc"]),
            "previous_counts": counts(evs, win["previous"]["start_utc"], win["previous"]["end_utc"]),
            "names": {m["metric_id"] if "metric_id" in m else m.get("id"): m.get("name") or m.get("title")
                      for m in (catalog().get("metrics") or [])},
            "kpis": [present(m) for m in cur["metric_values"]],
            "previous_kpis": [present(m) for m in prev["metric_values"]],
            "snapshot_ids": {"current": cur["snapshot_id"], "previous": prev["snapshot_id"]},
            "formula_version": cur["formula_version"], "event_set_digest": cur["event_set_digest"],
            "violations_open": int((k20 or {}).get("value") or 0) if (k20 or {}).get("status") == "MEASURED" else 0,
            "error": cache.error}
