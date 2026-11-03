"""Read-only, human-friendly progress of the structured phases (owner 2026-11-01: "this is the kind of information that
i would like to see in the fabro dashboard").

Fabro 0.362 shows nothing while a command node runs, and a command node's output is only a blob reference. This module
derives progress from the files the structured runner already writes - the SWE.1 inventory, the task packets, the visit
state and the gate log - so the runner itself is unchanged and a run already in progress is covered:

    {"work_order", "fabro_run_id", "updated_at",
     "active": {"phase", "step" (author|inspect), "done", "total", "unit", "current", "invalid", "calls",
                "continuations", "elapsed_s", "eta_s", "eta_utc", "text"},
     "gates": [last gate decisions], "phases": {phase: last decision}}

`text` is the one-line summary for a human, e.g.
"SWE.1 author: 47/61 register groups + cross-cutting, now RCC_APB4LRSTR_2, 86 calls, ETA 10:28 UTC".

    python -m forge_factory.lrtx.progress_api --port 32398          # serve GET /progress[?run=<fabro id>|?wo=<id>],
                                                                     # the factory floor page / and /floor.json[?since=],
                                                                     # the supervisor station /supervisor.json
    python -m forge_factory.lrtx.progress_api --once [--wo ID]       # print the JSON once

It never writes, never calls a model, and binds loopback only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import re
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RECENT_S = 24 * 3600  # work orders touched within this window are listed
STALE_S = 40 * 60  # the runner saves the visit state after every call (longest measured call 448 s, time box 1200 s);
# an open visit not updated for this long belongs to a node that was killed or cancelled


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _ts(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _packets(ws: Path, phase: str) -> dict[str, dict]:
    out = {}
    for p in glob.glob(str(ws / ".forge-run/lrtx" / phase / "packets/*.json")):
        c = _load(Path(p))
        if isinstance(c, dict) and c.get("task"):
            out[c["task"]] = c
    return out


def _author_tasks(ws: Path, phase: str) -> tuple[list[str], str]:
    """The ordered task list of a structured author visit, and the unit word for a human."""
    if phase == "SWE.1":
        inv = _load(ws / ".forge-run/lrtx/SWE.1/inventory.json")
        if isinstance(inv, dict):
            try:
                from .swe1 import groups

                return [f"requirements:{g['id']}" for g in groups(inv)] + ["requirements:crosscutting"], \
                    "register groups"
            except Exception:  # noqa: BLE001 - progress is best effort; never fails the caller
                pass
    tasks = sorted(t for t in _packets(ws, phase) if not t.startswith("inspect:"))
    return tasks, "tasks"


def _inspect_items(ws: Path, phase: str) -> list[str]:
    try:
        from ..inspection.engine import Store

        st = Store(ws)
        return [c["id"] for c in st.applicable(st.checklist(phase))["checks"]
                if c.get("required") and not c.get("deterministic_check")]
    except Exception:  # noqa: BLE001
        return []


def _resume_task(ws: Path, visit: str, started: float | None) -> str | None:
    """The task the visit's last time-boxed node execution named as its resume point ("time box used; the next node
    execution resumes at test:UT-008"), from .forge-run/lrtx/<visit>/visits.jsonl of the current visit; else None."""
    p = Path(ws) / ".forge-run/lrtx" / visit / "visits.jsonl"
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return None
    for line in reversed(lines[-5:]):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if started and (_ts(rec.get("at")) or 0) < started:
            return None
        if rec.get("status") != "CONTINUE":
            return None
        for issue in rec.get("issues") or []:
            m = re.search(r"resumes at (\S+)", str(issue))
            if m:
                return m.group(1).rstrip(".,;")
        return None
    return None


def _eta(done: int, total: int | None, elapsed: float | None) -> tuple[float | None, str | None]:
    if not total or not done or not elapsed or done >= total:
        return None, None
    eta = elapsed / done * (total - done)
    return round(eta), time.strftime("%H:%M", time.gmtime(time.time() + eta))


def progress(ws: Path) -> dict:
    ws = Path(ws)
    man = _load(ws / ".forge-run/manifest.json") or {}
    rid = (ws / ".forge-run/fabro_run_id")
    log = ws / ".forge-run/gates/gate-log.jsonl"
    gates = []
    if log.is_file():
        for x in log.read_text().splitlines()[-200:]:
            try:
                e = json.loads(x)
            except ValueError:
                continue
            if e.get("step") in ("reinspect_direct",):
                continue
            g = e.get("gate") or {}
            gates.append({"ts": e.get("ts"), "phase": e.get("phase"), "step": e.get("step"),
                          "result": e.get("result") or g.get("decision"),
                          "reason": str(g.get("reason") or e.get("reason") or "")[:160]})
    phases = {}
    for g in gates:
        if g["step"] in ("author", "inspect", "route"):
            phases[g["phase"]] = f"{g['step']} {g['result']}"
    # the open visit with the newest state file is the node at work now
    visits = []
    for vs in glob.glob(str(ws / ".forge-run/lrtx/*/visit-state.json")):
        st = _load(Path(vs))
        if isinstance(st, dict) and st.get("open"):
            visits.append((os.path.getmtime(vs), Path(vs).parent.name, st))
    active = None
    stopped = None
    if visits and time.time() - max(v[0] for v in visits) > STALE_S:
        stopped = max(visits, key=lambda v: v[0])[1]
        visits = []
    if visits:
        _m, name, st = max(visits, key=lambda v: v[0])
        inspect = name.endswith("-inspect")
        phase = name.removesuffix("-inspect")
        started = _ts(st.get("started_at"))
        elapsed = round(time.time() - started) if started else None
        packs = _packets(ws, phase)
        if inspect:
            items = _inspect_items(ws, phase)
            mine = {t.rsplit(":", 1)[-1]: c for t, c in packs.items() if t.startswith("inspect:")
                    and (_ts(c.get("at")) or 0) >= (started or 0)}
            done = sum(1 for i in items if (mine.get(i) or {}).get("status") == "VALID")
            total, unit = len(items), "checklist items"
            current = next((i for i in items if (mine.get(i) or {}).get("status") != "VALID"), None)
            invalid = [i for i in items if (mine.get(i) or {}).get("status") in ("INVALID", "FAILED")]
        else:
            tasks, unit = _author_tasks(ws, phase)
            done = sum(1 for t in tasks if (packs.get(t) or {}).get("status") == "VALID")
            total = len(tasks) or None
            current = next((t for t in tasks if (packs.get(t) or {}).get("status") != "VALID"), None)
            invalid = [t for t in tasks if (packs.get(t) or {}).get("status") in ("INVALID", "FAILED")]
            if unit == "register groups":  # "61 register groups + cross-cutting" reads better than 62
                cross = (packs.get("requirements:crosscutting") or {}).get("status") == "VALID"
                done, total = done - cross, (total or 1) - 1
                unit = "register groups" + (" + cross-cutting done" if cross else "")
        # owner 2026-11-02 ("the author cell [says] running tool checks, but the tool station is saying no SWE.4 tool
        # run yet"): a phase's task list is known only from its packets, so "every known task valid" is not the end of
        # the visit. The visit's own last record says where the next node execution resumes; while that task is not
        # done the author is between time boxes, not at its tool checks.
        resume = None if inspect else _resume_task(ws, name, started)
        if resume and (packs.get(resume) or {}).get("status") != "VALID":
            current = resume
            if resume not in tasks:
                total = None  # more tasks than packets so far
        eta_s, eta_utc = _eta(done, total, elapsed)
        cur = (current or "").split(":")[-1] or None
        step = "inspect" if inspect else "author"
        text = f"{phase} {step}: {done}/{total} {unit}"
        checking = bool(total) and done >= total and not invalid and not current
        if cur:
            text += f", now {cur}"
        elif checking:  # every task of the visit is valid; the node runs its deterministic tool checks or assembly
            text += ", all valid, running the tool checks (build, static analysis)"
        text += f", {st.get('calls', 0)} calls"
        if st.get("continuations"):
            text += f", {st['continuations']} continuations"
        if invalid:
            text += f", {len(invalid)} invalid"
        if eta_utc:
            text += f", ETA {eta_utc} UTC"
        active = {"phase": phase, "step": step, "done": done, "total": total, "unit": unit, "current": cur,
                  "invalid": [x.split(":")[-1] for x in invalid], "calls": st.get("calls", 0),
                  "continuations": st.get("continuations", 0), "elapsed_s": elapsed, "eta_s": eta_s,
                  "eta_utc": eta_utc, "checking": checking, "text": text}
    return {"work_order": man.get("work_order") or ws.parent.name,
            "fabro_run_id": rid.read_text().strip() if rid.is_file() else None,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "active": active, "stopped_visit": stopped, "phases": phases, "gates": gates[-8:]}


def state_root() -> Path:
    return Path(os.environ.get("FORGE_STATE_DIR") or "state")


def collect(run: str | None = None, wo: str | None = None) -> list[dict]:
    out = []
    now = time.time()
    for w in glob.glob(str(state_root() / "workorders/*/workspace")):
        ws = Path(w)
        if wo and ws.parent.name != wo:
            continue
        rid = ws / ".forge-run/fabro_run_id"
        if run and not (rid.is_file() and rid.read_text().strip() == run):
            continue
        marks = [ws / ".forge-run/gates/gate-log.jsonl", *map(Path, glob.glob(str(ws / ".forge-run/lrtx/*/visit-state.json")))]
        newest = max((os.path.getmtime(p) for p in marks if p.is_file()), default=0)
        if not (run or wo) and now - newest > RECENT_S:
            continue
        try:
            out.append(progress(ws))
        except Exception as exc:  # noqa: BLE001 - one unreadable workspace never hides the others
            out.append({"work_order": ws.parent.name, "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
    return sorted(out, key=lambda r: r.get("updated_at") or "", reverse=True)


FLOOR_PAGE = Path(__file__).resolve().parents[1] / "dashboard/static/factory-floor.html"


def floor_lines() -> list[dict]:
    """Owner 2026-11-02 ("why not in the very same port?"): one floor page for several production lines.
    FORGE_FLOOR_LINES = [{"id", "label", "sub", "url"?}]: a line with `url` is another floor server (its floor.json is
    passed through, read-only); a line without `url` is this process's own state. Unset: one line, unchanged."""
    raw = os.environ.get("FORGE_FLOOR_LINES")
    if not raw:
        return []
    lines = json.loads(raw)
    if not isinstance(lines, list) or not all(isinstance(x, dict) and re.fullmatch(r"[a-z0-9-]{1,32}", str(x.get("id")))
                                              for x in lines):
        raise ValueError("FORGE_FLOOR_LINES_INVALID")
    return lines


def _line_floor(line: dict, query: dict, path: str = "/floor.json") -> bytes:
    import urllib.parse
    import urllib.request

    qs = urllib.parse.urlencode({k: v[0] for k, v in query.items() if k != "line" and v})
    url = line["url"].rstrip("/") + path + ("?" + qs if qs else "")
    with urllib.request.urlopen(url, timeout=15) as r:  # noqa: S310 - operator-configured loopback floor server
        data = r.read()
    json.loads(data)  # only a JSON floor is passed on
    return data


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/floor"):  # the factory floor page (feature 007 addendum), read-only
            return self._send(FLOOR_PAGE.read_bytes(), "text/html; charset=utf-8")
        if u.path == "/lines.json":
            body = {"lines": [{k: x.get(k) for k in ("id", "label", "sub")} for x in floor_lines()]}
            return self._send(json.dumps(body, ensure_ascii=False).encode(), "application/json")
        if u.path in ("/floor.json", "/supervisor.json") and (q.get("line") or [None])[0]:
            line = next((x for x in floor_lines() if x["id"] == q["line"][0]), None)
            if line is None:
                self.send_error(404)
                return
            if line.get("url"):
                try:
                    return self._send(_line_floor(line, q, u.path), "application/json")
                except (OSError, ValueError):
                    self.send_error(502, "line floor unavailable")
                    return
        if u.path == "/floor.json":
            from .floor_api import floor

            since = (q.get("since") or [None])[0]
            body = floor(since=_ts(since) if since else None, focus=(q.get("order") or [None])[0])
        elif u.path == "/supervisor.json":  # autonomous line M1: the supervisor station alone (read-only, GET only)
            from .floor_api import supervisor_station

            body = supervisor_station()
        elif u.path == "/progress":
            body = {"schema": "forge-c/lrtx-progress/1",
                    "work_orders": collect((q.get("run") or [None])[0], (q.get("wo") or [None])[0])}
        elif u.path == "/health":
            body = {"status": "ok"}
        else:
            self.send_error(404)
            return
        self._send(json.dumps(body, ensure_ascii=False).encode(), "application/json")

    def do_POST(self):  # noqa: N802 - http.server API
        """The floor's only control (owner 2026-11-02): the cloud line's Claude mode, `api` or `account`. A JSON body,
        the control header and (when the browser sends one) a same-host Origin; nothing else is writable."""
        u = urlparse(self.path)
        target = {"/claude-mode": "claude", "/inspector-mode": "inspector"}.get(u.path)
        if target is None:
            self.send_error(404)
            return
        from .floor_api import log_claude_mode_attempt, set_claude_mode

        def refuse(code: int, why: str) -> None:
            log_claude_mode_attempt(code, why, self.client_address[0], self.headers.get("Origin"), self.headers.get("Host"),
                                    target)
            self.send_error(code, why)

        # the custom header makes a cross-site request need a CORS preflight, which this server never grants
        if self.headers.get("X-Forge-Control") != u.path.lstrip("/"):
            return refuse(403, "control header missing")
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= 200 or "application/json" not in (self.headers.get("Content-Type") or ""):
            return refuse(400, "JSON body required")
        try:
            body = set_claude_mode(str(json.loads(self.rfile.read(n)).get("mode")), self.client_address[0], target)
        except (ValueError, AttributeError):
            return refuse(400, "mode must be api or account")
        except FileNotFoundError:
            return refuse(409, "no cloud line on this floor")
        self._send(json.dumps(body).encode(), "application/json")

    def _send(self, data: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_a):  # quiet
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=32398)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--wo")
    a = ap.parse_args(argv)
    if a.once:
        print(json.dumps(collect(wo=a.wo), indent=1, ensure_ascii=False))
        return 0
    if a.host not in ("127.0.0.1", "::1", "localhost"):
        raise SystemExit("progress_api binds loopback only")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
