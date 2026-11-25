"""Plant Floor operator settings and evidence review for the Omniverse line."""
import json
import os
import sqlite3
from http.client import HTTPConnection, HTTPException
from urllib.parse import urlencode, urlparse

from ..common import state_dir
from ..inspection import partial

PATH = "/partial-inspection.json"
CONTROL = "partial-inspection"
DEFAULT_HOSTS = "localhost,127.0.0.1,::1,master.local,omniverse2.local"


def _send(handler, code, body):
    raw = json.dumps(body, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _accepted_origin(handler):
    host = handler.headers.get("Host", "")
    origin = urlparse(handler.headers.get("Origin", ""))
    allowed = set(os.environ.get("FORGE_PARTIAL_INSPECTION_HOSTS", DEFAULT_HOSTS).split(","))
    return (handler.headers.get("X-Forge-Control") == CONTROL and origin.scheme in {"http", "https"}
            and origin.netloc == host and origin.hostname in allowed
            and not (origin.username or origin.path or origin.params or origin.query or origin.fragment))


def _relay(base, wo, raw):
    url = urlparse(base)
    if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.username:
        raise OSError("Omniverse relay must use the trusted loopback endpoint")
    query = urlencode({"line": "local", "order": wo})
    conn = HTTPConnection(url.hostname, url.port, timeout=10)
    try:
        conn.request("POST" if raw is not None else "GET", PATH + "?" + query, body=raw,
                     headers={"Origin": f"http://{url.netloc}", "X-Forge-Control": CONTROL,
                              "Content-Type": "application/json"})
        response = conn.getresponse()
        return response.status, json.loads(response.read(524289))
    finally:
        conn.close()


def serve(handler, q, lines):
    wo = (q.get("order") or [""])[0]
    line = (q.get("line") or ["local"])[0]
    if line != "local" or not partial.ORDER.fullmatch(wo):
        return _send(handler, 404, {"error": "Select an Omniverse work order."})
    local = next((x for x in lines if x["id"] == "local"), {})
    if lines and not local:
        return _send(handler, 404, {"error": "The Omniverse line is unavailable on this floor."})
    raw = None
    try:
        if handler.command == "POST":
            if not _accepted_origin(handler):
                return _send(handler, 403, {"error": "Use the Plant Floor operator page to change this setting."})
            n = int(handler.headers.get("Content-Length", "0"))
            if handler.headers.get_content_type() != "application/json" or not 0 < n <= 4096:
                return _send(handler, 400, {"error": "A small JSON request is required."})
            raw = handler.rfile.read(n)
        if local.get("url"):
            code, body = _relay(local["url"], wo, raw)
            return _send(handler, code, body)
        ws = state_dir() / "workorders" / wo / "workspace"
        if not ws.is_dir() or ws.resolve() != ws.absolute():
            return _send(handler, 404, {"error": "Work order unavailable."})
        if raw is not None:
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("A JSON object is required.")
            operator = f"plant-floor/{handler.client_address[0]}"
            if request.get("action") == "configure":
                partial.configure(ws, request, operator)
            elif request.get("action") == "approve":
                partial.approve(ws, request.get("evidence_sha256"), operator)
            else:
                raise ValueError("Unknown action.")
        return _send(handler, 200, partial.snapshot(ws))
    except partial.Conflict as exc:
        return _send(handler, 409, {"error": str(exc)})
    except (ValueError, TypeError, UnicodeError) as exc:
        return _send(handler, 400, {"error": str(exc)[:200]})
    except (HTTPException, OSError, sqlite3.Error):
        return _send(handler, 503, {"error": "Omniverse inspection settings are temporarily unavailable."})
