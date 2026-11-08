"""Engines of the model service (feature 017, FR-025 to FR-027, FR-031; research R3b, R3c).

* `ProcessEngine` runs a pinned binary (llama.cpp server for Ornith) with the explicit arguments of the catalog.
  Warm strategy `ram_staged_file`: the model file is staged once into RAM-backed storage and every load starts the
  server on that copy, so a swap is a RAM-to-GPU copy, never a disk read. Unload stops the process group.
* `VllmComposeEngine` runs a Compose service (vLLM). Warm strategy `vllm_sleep`: the engine is started once, then
  put to sleep (weights to pinned host RAM, KV cache dropped); a swap wakes it, so there is no restart, no file read
  and no recompilation. Its sleep/wake endpoints are on the internal engine network only.

When the RAM budget cannot hold a model warm, the engine still works cold (start from disk) and says so; the swap
controller records that as a finding. Engines report what they serve; the identity check is the controller's.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import re
import signal
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

from .catalog import Catalog, Model

Cmd = Callable[[list[str]], Awaitable[tuple[int, str]]]


def stage_name(model: str) -> str:
    """A file-system-safe name for a model id such as `hf.co/org/Model-GGUF:Q8_0`."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", model).strip("._-")[:120] or "model"


async def run_cmd(argv: list[str]) -> tuple[int, str]:
    p = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await p.communicate()
    return p.returncode or 0, out.decode(errors="replace")[-2000:]


async def _wait_healthy(http: httpx.AsyncClient, url: str, timeout_s: float, headers: dict | None = None,
                        proc: asyncio.subprocess.Process | None = None) -> None:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout_s
    while loop.time() < end:
        if proc is not None and proc.returncode is not None:
            raise RuntimeError(f"ENGINE_EXITED:{proc.returncode}")
        with contextlib.suppress(httpx.HTTPError):
            r = await http.get(url + "/health", headers=headers, timeout=5)
            if r.status_code == 200:
                return
        await asyncio.sleep(0.5)
    raise TimeoutError("ENGINE_NOT_HEALTHY")


async def _served(http: httpx.AsyncClient, m: Model, headers: dict | None = None) -> dict:
    """The catalog identity when the engine lists the model with the expected context, else a copy that differs."""
    r = await http.get(m.engine_url + "/v1/models", headers=headers, timeout=10)
    r.raise_for_status()
    entry = next((d for d in r.json().get("data") or [] if d.get("id") == m.name_on_engine), None)
    ident = dict(m.identity)
    if entry is None:
        ident["name"] = "<not served>"
    elif entry.get("max_model_len") not in (None, m.identity["context_limit"]):
        ident["context_limit"] = int(entry["max_model_len"])
    return ident


class ProcessEngine:
    def __init__(self, model: Model, ram=None, *, http: httpx.AsyncClient, log_dir: Path, spawn=None):
        if not model.process:
            raise ValueError(f"NOT_A_PROCESS_ENGINE:{model.model}")
        self.m, self.ram, self.http, self.log_dir = model, ram, http, Path(log_dir)
        self.spawn = spawn or asyncio.create_subprocess_exec
        self.staged, self.proc, self.reason = None, None, ""

    async def prepare(self) -> dict:
        p = self.m.process
        if self.m.warm_strategy != "ram_staged_file" or self.ram is None:
            return {"warm": False, "reason": "NO_WARM_STRATEGY"}
        decision, why = self.ram.decide(self.m.ram_gib)
        if decision != "warm":
            self.reason = why
            return {"warm": False, "reason": why}
        self.staged = await asyncio.to_thread(self.ram.stage, stage_name(self.m.model), Path(p["model_path"]),
                                              p.get("model_sha256"))
        return {"warm": True, "reason": ""}

    def _model_path(self) -> tuple[str, bool]:
        if self.staged is not None:
            ok, why = self.ram.check(self.staged)
            if ok:
                return str(self.staged.path), True
            self.reason = why
        return self.m.process["model_path"], False

    async def load(self) -> dict:
        p = self.m.process
        path, warm = self._model_path()
        args = [a.replace("{model_path}", path) for a in p["args"]]
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log = open(self.log_dir / f"{self.m.model}.log", "ab")  # noqa: SIM115 - handed to the child
        try:
            self.proc = await self.spawn(p["binary"], *args, env={**os.environ, **(p.get("env") or {})},
                                         stdout=log, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        finally:
            log.close()
        await _wait_healthy(self.http, self.m.engine_url, self.m.load_timeout_s, proc=self.proc)
        return {"warm": warm, "reason": "" if warm else self.reason}

    async def unload(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None or proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(proc.wait(), timeout=30)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()

    async def identity(self) -> dict:
        return await _served(self.http, self.m)


class VllmComposeEngine:
    def __init__(self, model: Model, compose_file: str, project: str, key: str | None, ram=None, *,
                 http: httpx.AsyncClient, cmd: Cmd = run_cmd):
        if not model.compose_service:
            raise ValueError(f"NOT_A_COMPOSE_ENGINE:{model.model}")
        self.m, self.ram, self.http, self.cmd = model, ram, http, cmd
        self.compose = ["docker", "compose", "-f", compose_file, "-p", project]
        self.h = {"Authorization": f"Bearer {key}"} if key else None
        self.sleeping, self.can_sleep, self.reason = False, False, ""

    async def _compose(self, *args: str) -> None:
        rc, out = await self.cmd([*self.compose, *args])
        if rc != 0:
            raise RuntimeError(f"COMPOSE_FAILED:{args[0]}:{rc}")

    async def _post(self, path: str) -> None:
        r = await self.http.post(self.m.engine_url + path, headers=self.h, timeout=120)
        if r.status_code >= 300:
            raise RuntimeError(f"ENGINE_{path.strip('/').split('?')[0].upper()}_FAILED:{r.status_code}")

    async def prepare(self) -> dict:
        if self.m.warm_strategy != "vllm_sleep" or self.ram is None:
            return {"warm": False, "reason": "NO_WARM_STRATEGY"}
        decision, why = self.ram.decide(self.m.ram_gib)
        if decision != "warm":
            self.reason = why
            return {"warm": False, "reason": why}
        await self._compose("up", "-d", self.m.compose_service)
        await _wait_healthy(self.http, self.m.engine_url, self.m.load_timeout_s, self.h)
        await self._post("/sleep?level=1")
        self.ram.reserve(stage_name(self.m.model), self.m.ram_gib)
        self.sleeping = self.can_sleep = True
        return {"warm": True, "reason": ""}

    async def load(self) -> dict:
        if self.sleeping:
            await self._post("/wake_up")
            await _wait_healthy(self.http, self.m.engine_url, self.m.load_timeout_s, self.h)
            self.sleeping = False
            return {"warm": True, "reason": ""}
        await self._compose("up", "-d", self.m.compose_service)
        await _wait_healthy(self.http, self.m.engine_url, self.m.load_timeout_s, self.h)
        return {"warm": False, "reason": self.reason or "COLD_START"}

    async def unload(self) -> None:
        if self.can_sleep:
            await self._post("/sleep?level=1")
            self.sleeping = True
        else:
            await self._compose("stop", self.m.compose_service)

    async def identity(self) -> dict:
        return await _served(self.http, self.m, self.h)

    async def shutdown(self) -> None:
        await self._compose("stop", self.m.compose_service)


def build(cat: Catalog, *, http: httpx.AsyncClient, ram=None, engine_key: str | None = None, log_dir: Path,
          cmd: Cmd = run_cmd) -> dict:
    engines = {}
    for name, m in cat.models.items():
        if m.launch_kind == "process":
            engines[name] = ProcessEngine(m, ram, http=http, log_dir=log_dir)
        else:
            engines[name] = VllmComposeEngine(m, cat.compose_file, cat.compose_project or "forge-model-tier", engine_key,
                                              ram, http=http, cmd=cmd)
    return engines
