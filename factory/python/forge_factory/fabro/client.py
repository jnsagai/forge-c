"""Thin adapter over the *verified* Fabro 0.362 run API (see ADR-0002 and pinned openapi.json).

Only endpoints observed on the installed server are used:
  GET /health, GET /api/v1/system/info, GET /api/v1/runs, GET /api/v1/runs/{id},
  GET /api/v1/runs/{id}/events?since_seq&limit (ordered, seq-numbered),
  GET /api/v1/runs/{id}/usage, POST /api/v1/runs/{id}/cancel.
No undocumented DB access, no UI scraping.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

DEFAULT_URL = "http://127.0.0.1:32290"


class FabroUnavailable(RuntimeError):
    pass


def load_token(storage_dir: str | None = None) -> str | None:
    tok = os.environ.get("FORGE_FABRO_TOKEN")
    if tok:
        return tok
    storage = storage_dir or os.environ.get("FORGE_FABRO_STORAGE")
    if storage:
        env = Path(storage) / "server.env"
        try:
            for line in env.read_text().splitlines():
                if line.startswith("FABRO_DEV_TOKEN="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            return None
    return None


class FabroClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ):
        url = (base_url or os.environ.get("FORGE_FABRO_URL") or DEFAULT_URL).rstrip("/")
        if url.endswith("/api/v1"):
            url = url[: -len("/api/v1")]
        try:
            namespace = os.readlink("/proc/self/ns/net")
            boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        except OSError:
            namespace, boot = "UNKNOWN", "UNKNOWN"
        # A loopback port can name different servers in different namespaces.
        # This is a probe-cache subject, never native termination evidence.
        self.observation_identity = hashlib.sha256(json.dumps(
            {"url": url, "netns": namespace, "boot": boot}, sort_keys=True,
        ).encode()).hexdigest()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = httpx.Client(base_url=url, headers=headers, timeout=timeout, transport=transport)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _get(self, path: str, **params: Any) -> Any:
        try:
            r = self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        except httpx.HTTPError as exc:
            raise FabroUnavailable(f"{type(exc).__name__}") from exc
        if r.status_code >= 500:
            raise FabroUnavailable(f"http_{r.status_code}")
        r.raise_for_status()
        return r.json()

    def health(self) -> bool:
        try:
            return self._get("/health").get("status") == "ok"
        except (FabroUnavailable, httpx.HTTPStatusError, ValueError):
            return False

    def system_info(self) -> dict:
        return self._get("/api/v1/system/info")

    def list_runs(self, limit: int = 50, status: str | None = None) -> list[dict]:
        return self._get("/api/v1/runs", **{"page[limit]": limit, "status": status}).get("data", [])

    def get_run(self, run_id: str) -> dict:
        return self._get(f"/api/v1/runs/{run_id}")

    def usage(self, run_id: str) -> dict:
        return self._get(f"/api/v1/runs/{run_id}/usage")

    def events(self, run_id: str, since_seq: int = 0, limit: int = 200) -> list[dict]:
        data = self._get(f"/api/v1/runs/{run_id}/events", since_seq=since_seq, limit=limit).get("data", [])
        return [e for e in data if int(e.get("seq", 0)) > since_seq]

    def iter_events(self, run_id: str, since_seq: int = 0, page: int = 200) -> Iterator[dict]:
        seq = since_seq
        while True:  # the server may cap page size below `page`: only an empty batch ends the stream
            batch = self.events(run_id, seq, page)
            if not batch:
                return
            last = seq
            for e in batch:
                seq = max(seq, int(e["seq"]))
                yield e
            if seq == last:
                return

    def cancel(self, run_id: str) -> int:
        try:
            return self._http.post(f"/api/v1/runs/{run_id}/cancel").status_code
        except httpx.HTTPError as exc:
            raise FabroUnavailable(type(exc).__name__) from exc


def client_for_workspace(ws: Path, timeout: float = 5.0) -> FabroClient:
    """Client for the Fabro server that holds this work order's run (.forge-run/fabro_server.json, written at launch;
    the local server when absent). r56: cloud-benchmark runs live on another server and 404 on the local one."""
    url = storage = None
    srv = Path(ws) / ".forge-run/fabro_server.json"
    if srv.is_file():
        meta = json.loads(srv.read_text())
        url, storage = meta.get("url") or None, meta.get("storage") or None
    return FabroClient(base_url=url, token=load_token(storage), timeout=timeout)


def run_status(run: dict) -> str:
    """Map Fabro lifecycle to a coarse status; unknown shapes stay UNKNOWN (never PASS)."""
    st = ((run.get("lifecycle") or {}).get("status") or {}).get("kind")
    return str(st).upper() if st else "UNKNOWN"
