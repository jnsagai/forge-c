"""Display-only live view of the answer tokens the gateway relays (owner 2026-11-01: "yes, proceed with answer tokens
only").

With FORGE_GATEWAY_LIVE_TAP set to a socket path (the stack sets it only for a profile with `gateway.live_tap: true`),
the gateway broadcasts each relayed ANSWER piece - message content and tool-call argument text, after the gateway has
stripped every reasoning field - to the viewers connected to that Unix socket, one JSON object per line:

    {"t": "start", "model": ..., "role": ..., "n": <call number>}
    {"t": "d", "n": ..., "c": "<text piece>"}
    {"t": "end", "n": ..., "finish": ..., "out": <completion tokens>}

Nothing is written to disk and nothing is kept: a viewer that is not connected sees nothing, and a viewer that reads too
slowly loses pieces (bounded per-viewer buffer) rather than slowing the model call. Reasoning text never reaches the
tap: callers pass only text taken from stripped chunks. Without the variable every call is a no-op.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

MAX_BUFFER = 256 * 1024  # bytes queued per viewer before pieces are dropped for it


class LiveTap:
    def __init__(self, path: str | os.PathLike | None):
        self.path = Path(path) if path else None
        self.viewers: list[asyncio.StreamWriter] = []
        self.server: asyncio.AbstractServer | None = None
        self.calls = 0
        self.dropped = 0

    @classmethod
    def from_env(cls) -> LiveTap:
        return cls(os.environ.get("FORGE_GATEWAY_LIVE_TAP") or None)

    async def ensure(self) -> None:
        """Start listening (once, in the running event loop). Failure to listen never fails a model call."""
        if self.path is None or self.server is not None:
            return
        try:
            if self.path.is_socket():
                self.path.unlink()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.server = await asyncio.start_unix_server(self._viewer, path=str(self.path))
            os.chmod(self.path, 0o600)
        except OSError as exc:  # e.g. a path over the Unix-socket limit: the gateway log says so, calls go on
            import sys

            print(f"LIVE_TAP_DISABLED:{self.path}:{exc}", file=sys.stderr, flush=True)
            self.path = None

    async def _viewer(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.viewers.append(writer)
        try:
            await reader.read()  # the viewer never sends; EOF = it disconnected
        finally:
            if writer in self.viewers:
                self.viewers.remove(writer)
            writer.close()

    def _emit(self, obj: dict) -> None:
        if not self.viewers:
            return
        line = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        for w in list(self.viewers):
            if w.is_closing():
                self.viewers.remove(w)
                continue
            if w.transport.get_write_buffer_size() > MAX_BUFFER:
                self.dropped += 1
                continue
            w.write(line)  # never awaited: a slow viewer cannot delay the call

    async def begin(self, model: str | None, role: str | None) -> int:
        await self.ensure()
        self.calls += 1
        self._emit({"t": "start", "n": self.calls, "model": model, "role": role})
        return self.calls

    def piece(self, n: int, text: str | None) -> None:
        if text:
            self._emit({"t": "d", "n": n, "c": text})

    def delta(self, n: int, delta: dict) -> None:
        """One stripped stream delta: its content and any tool-call argument text."""
        self.piece(n, delta.get("content"))
        for tc in delta.get("tool_calls") or []:
            self.piece(n, ((tc or {}).get("function") or {}).get("arguments"))

    def end(self, n: int, finish: str | None, usage: dict | None) -> None:
        self._emit({"t": "end", "n": n, "finish": finish, "out": (usage or {}).get("completion_tokens")})
