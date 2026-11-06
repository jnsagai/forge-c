"""Thin adapter over the *verified* Fabro 0.362 run API (see ADR-0002 and pinned openapi.json).

Only endpoints observed on the installed server are used:
  GET /health, GET /api/v1/system/info, GET /api/v1/runs, GET /api/v1/runs/{id},
  GET /api/v1/runs/{id}/events?since_seq&limit (ordered, seq-numbered),
  GET /api/v1/runs/{id}/usage, POST /api/v1/runs/{id}/cancel.
No undocumented DB access, no UI scraping.
"""

from __future__ import annotations

import hashlib
import errno
import json
import os
import time
from dataclasses import dataclass
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

DEFAULT_URL = "http://127.0.0.1:32290"


class FabroUnavailable(RuntimeError):
    pass


class FabroConnectionUnavailable(FabroUnavailable):
    """No connection was established; distinct from a partial/invalid catalog."""



@dataclass(frozen=True)
class RunInventory:
    """A bounded complete observation, not an admission or termination authority."""

    rows: tuple[dict, ...]
    complete: bool
    observation_identity: str
    statuses: tuple[str, ...] | None
    observed_monotonic: float
    pages: int
    observed_boottime: float
    boot_identity: str

    def fresh(self, max_age_s: float = 1.0) -> bool:
        try:
            boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            age = time.monotonic() - self.observed_monotonic
            boot_age = time.clock_gettime(time.CLOCK_BOOTTIME) - self.observed_boottime
            return self.complete and boot == self.boot_identity and 0 <= max(age, boot_age) <= max_age_s
        except (OSError, TypeError, ValueError):
            return False


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

    def run_inventory(self, *, statuses: tuple[str, ...] | None = None, include_archived: bool = True,
                      page_size: int = 100, max_pages: int = 64, max_runs: int = 6400,
                      timeout_s: float = 5.0, max_bytes: int = 16 * 1024 * 1024) -> RunInventory:
        """Two agreeing complete passes over the pinned 0.362 pagination API.

        `total` is optional in that API; `has_more` is mandatory. A bound,
        malformed response, unstable catalog or transport failure is UNKNOWN,
        never an empty catalog. This is not a transactional server snapshot:
        the caller must retain its normal one-placer/lease/effect fences.
        """
        columns = {"pending", "runnable", "initializing", "running", "blocked", "succeeded", "failed",
                   "archived", "removing"}
        if (type(page_size) is not int or not 1 <= page_size <= 100 or type(max_pages) is not int
                or not 1 <= max_pages <= 64 or type(max_runs) is not int or not 1 <= max_runs <= 6400
                or type(timeout_s) not in (int, float) or not 0 < timeout_s <= 10
                or type(max_bytes) is not int or not 1024 <= max_bytes <= 16 * 1024 * 1024
                or type(include_archived) is not bool or statuses is not None and
                (not isinstance(statuses, tuple) or not statuses
                 or any(type(s) is not str or s not in columns for s in statuses)
                 or len(set(statuses)) != len(statuses))):
            raise FabroUnavailable("RUN_INVENTORY_BOUNDS_INVALID")
        start = time.monotonic()
        boot_start = time.clock_gettime(time.CLOCK_BOOTTIME)
        boot_identity = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        retained_bytes = 0

        def remaining():
            value = timeout_s - max(time.monotonic() - start,
                                    time.clock_gettime(time.CLOCK_BOOTTIME) - boot_start)
            if value <= 0:
                raise FabroUnavailable("RUN_INVENTORY_TIMEOUT")
            return value

        def page(offset):
            nonlocal retained_bytes
            params = {"page[limit]": page_size, "page[offset]": offset, "sort": "created_at", "direction": "asc",
                      "include_archived": str(include_archived).lower()}
            if statuses is not None:
                params["status"] = list(statuses)  # OpenAPI form/explode=true: repeated query keys.
            try:
                with self._http.stream("GET", "/api/v1/runs", params=params, timeout=remaining()) as response:
                    if response.status_code >= 500:
                        raise FabroUnavailable(f"http_{response.status_code}")
                    response.raise_for_status()
                    raw = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        remaining()
                        if len(raw) + len(chunk) > 4 * 1024 * 1024 or retained_bytes + len(chunk) > max_bytes:
                            raise FabroUnavailable("RUN_INVENTORY_PAGE_BYTES_EXCEEDED")
                        raw.extend(chunk)
                        retained_bytes += len(chunk)
                    remaining()
                    value = json.loads(raw, parse_constant=lambda _s: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
            except httpx.ConnectError as exc:
                # Preserve the old absent-server path only for a kernel-proven
                # refusal before any response, never timeout/DNS/partial data.
                causes, pending, seen = [], [exc], set()
                while pending and len(seen) < 16:
                    cause = pending.pop()
                    if id(cause) in seen:
                        continue
                    seen.add(id(cause)); causes.append(cause)
                    pending.extend(x for x in (cause.__cause__, cause.__context__) if x is not None)
                if any(isinstance(cause, OSError) and cause.errno == errno.ECONNREFUSED for cause in causes):
                    raise FabroConnectionUnavailable("CONNECTION_REFUSED") from exc
                raise FabroUnavailable("RUN_INVENTORY_CONNECTION_UNKNOWN") from exc
            except (httpx.HTTPError, ValueError, UnicodeError, RecursionError) as exc:
                raise FabroUnavailable("RUN_INVENTORY_PAGE_UNAVAILABLE:" + type(exc).__name__) from exc
            if not isinstance(value, dict) or not isinstance(value.get("data"), list) or not isinstance(value.get("meta"), dict):
                raise FabroUnavailable("RUN_INVENTORY_PAGE_INVALID")
            return value

        def identity(row):
            if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or not 0 < len(row["id"]) <= 256
                    or not isinstance(row.get("lifecycle"), dict)
                    or not isinstance(row["lifecycle"].get("status"), dict)
                    or not isinstance(row["lifecycle"]["status"].get("kind"), str)
                    or not row["lifecycle"]["status"]["kind"]):
                raise FabroUnavailable("RUN_INVENTORY_RUN_INVALID")
            return json.dumps({"id": row["id"], "source_directory": row.get("source_directory"),
                               "labels": row.get("labels"), "status": row["lifecycle"]["status"]},
                              sort_keys=True, separators=(",", ":"), allow_nan=False)

        def collect(*, keep_rows):
            rows, identities, total, pages = [], {}, None, 0
            for _ in range(max_pages):
                remaining()
                value = page(len(identities)); pages += 1
                part, meta = value["data"], value["meta"]
                if type(meta.get("has_more")) is not bool or len(part) > page_size:
                    raise FabroUnavailable("RUN_INVENTORY_METADATA_INVALID")
                reported = meta.get("total")
                if reported is not None:
                    if type(reported) is not int or reported < 0 or total is not None and reported != total:
                        raise FabroUnavailable("RUN_INVENTORY_TOTAL_CHANGED")
                    total = reported
                for row in part:
                    signature = identity(row)
                    if row["id"] in identities:
                        raise FabroUnavailable("RUN_INVENTORY_DUPLICATE_ID")
                    identities[row["id"]] = signature
                    if keep_rows:
                        rows.append(row)
                    remaining()
                    if len(identities) > max_runs:
                        raise FabroUnavailable("RUN_INVENTORY_RUN_BOUND")
                if total is not None and (len(identities) > total or not meta["has_more"] and len(identities) != total):
                    raise FabroUnavailable("RUN_INVENTORY_COUNT_MISMATCH")
                if not meta["has_more"]:
                    remaining()
                    return rows, identities, pages, total
                if not part or total is not None and len(identities) >= total:
                    raise FabroUnavailable("RUN_INVENTORY_NO_PROGRESS")
            raise FabroUnavailable("RUN_INVENTORY_PAGE_BOUND")

        _, first_identity, first_pages, first_total = collect(keep_rows=False)
        second, second_identity, second_pages, second_total = collect(keep_rows=True)
        if first_identity != second_identity or first_total != second_total:
            raise FabroUnavailable("RUN_INVENTORY_CHANGED")
        if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != boot_identity:
            raise FabroUnavailable("RUN_INVENTORY_BOOT_CHANGED")
        result = RunInventory(tuple(second), True, self.observation_identity, statuses, time.monotonic(),
                              first_pages + second_pages, time.clock_gettime(time.CLOCK_BOOTTIME), boot_identity)
        remaining()
        return result

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
