"""The factory's side of the model channel (feature 017, FR-002 to FR-006, FR-029; contracts/model-channel.md).

`ModelServiceTransport` wraps the HTTP transport of the factory's existing LLM gateway (`llm_gateway.create_app`
accepts a transport), so the external mode needs no change to the gateway source, whose hash the owner lane's
signed transport proof pins (research R7). For every call to the model service it:

* replaces the caller's credential with the factory tenant's key (resolved from the private secrets file);
* turns thinking off for models whose expected identity is non-thinking (the service may not enforce it);
* pins each model's identity on its first answer (or to the expected fingerprint) and blocks any later answer
  from a different identity with a synthetic 409 `identity_changed`; a swap that brings back the same model is
  not a change (FR-003);
* maps refusals and transport failures to the contract's reasons and writes one metadata-only record per call
  (model, identity prefix, status, reason, queue and swap time) - never content (FR-024);
* when the owner's switch `<state>/model-exchanges/capture.json` says `"gateway": true` (off by default), writes the
  complete request and reply of each call privately for the per-node exchange log (FR-022): hidden reasoning is
  removed and secrets are redacted before anything is written (FR-023, FR-024). This lives in the transport because
  the gateway source is pinned; the exporter attaches each record to its node by model and exact token counts.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx

from .reasons import Reason, classify

ID_HEADER, QUEUE_HEADER, SWAP_HEADER = "x-forge-model-identity", "x-forge-queue-ms", "x-forge-swap-ms"


class CallLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, rec: dict) -> None:
        line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **rec}, sort_keys=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(line + "\n")


class Capture:
    """Private full-call capture behind the owner's switch (FR-022 to FR-024). Never raises into the call."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def on(self) -> bool:
        try:
            return json.loads((self.root / "capture.json").read_text()).get("gateway") is True
        except (OSError, ValueError, AttributeError):
            return False

    def write(self, rec: dict) -> None:
        try:
            from ..lrtx.model_exchanges import _clean

            d = self.root / "gateway" / time.strftime("%Y%m%d", time.gmtime())
            d.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.root / "gateway", 0o700)
            os.chmod(d, 0o700)
            f = d / f"{time.strftime('%H%M%S', time.gmtime())}-{uuid.uuid4().hex[:8]}.json"
            fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as fh:
                json.dump(_clean(rec), fh, ensure_ascii=False)
        except Exception:  # noqa: BLE001, S110 - capture must never fail the call
            pass


def _reply_of(data: dict) -> dict:
    ch = (data.get("choices") or [{}])[0] if isinstance(data, dict) else {}
    msg = ch.get("message") or {}
    return {"text": msg.get("content"), "tool_calls": msg.get("tool_calls"), "finish_reason": ch.get("finish_reason"),
            "usage": data.get("usage") if isinstance(data, dict) else None}


def _reply_of_sse(raw: bytes) -> dict:
    text, calls, usage, finish = [], {}, None, None
    for line in raw.decode(errors="replace").splitlines():
        if not line.startswith("data:") or line[5:].strip() in ("", "[DONE]"):
            continue
        try:
            chunk = json.loads(line[5:])
        except ValueError:
            continue
        usage = chunk.get("usage") or usage
        for c in chunk.get("choices") or []:
            d = c.get("delta") or {}
            finish = c.get("finish_reason") or finish
            if d.get("content"):
                text.append(d["content"])
            for tc in d.get("tool_calls") or []:
                cur = calls.setdefault(tc.get("index", 0), {"id": tc.get("id"), "function": {"name": "", "arguments": ""}})
                fn = tc.get("function") or {}
                cur["function"]["name"] += fn.get("name") or ""
                cur["function"]["arguments"] += fn.get("arguments") or ""
    return {"text": "".join(text) or None, "tool_calls": [calls[i] for i in sorted(calls)] or None, "finish_reason": finish,
            "usage": usage}


class _TeeStream(httpx.AsyncByteStream):
    def __init__(self, inner, done):
        self.inner, self.done, self.buf = inner, done, bytearray()

    async def __aiter__(self):
        async for chunk in self.inner:
            self.buf += chunk
            yield chunk

    async def aclose(self) -> None:
        try:
            await self.inner.aclose()
        finally:
            self.done(bytes(self.buf))


class ModelServiceTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport, *, key: Callable[[], str], expected: dict[str, dict],
                 log: CallLog | None = None, tenant_id: str = "", capture: Capture | None = None):
        self.inner, self.key, self.expected, self.log, self.tenant_id = inner, key, expected, log, tenant_id
        self.capture = capture
        self.pins: dict[str, str] = {m: e["revision_fingerprint"][:16] for m, e in expected.items()
                                     if e.get("revision_fingerprint")}

    def _rewrite(self, request: httpx.Request) -> tuple[httpx.Request, str | None]:
        headers = {k: v for k, v in request.headers.items() if k.lower() not in ("authorization", "content-length")}
        headers["authorization"] = f"Bearer {self.key()}"
        content, model = request.content, None
        if request.method == "POST" and request.url.path.endswith("/chat/completions"):
            try:
                body = json.loads(content or b"{}")
            except ValueError:
                body = None
            if isinstance(body, dict):
                model = body.get("model")
                if (self.expected.get(model) or {}).get("reasoning_mode") == "off":
                    body["chat_template_kwargs"] = {**(body.get("chat_template_kwargs") or {}), "enable_thinking": False}
                    content = json.dumps(body).encode()
        return httpx.Request(request.method, request.url, headers=headers, content=content,
                             extensions=request.extensions), model

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        req, model = self._rewrite(request)
        t0, sent, at = time.monotonic(), False, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            sent = True
            resp = await self.inner.handle_async_request(req)
        except httpx.HTTPError as exc:
            reason = classify(exc=exc, sent=sent and not isinstance(exc, httpx.ConnectError | httpx.ConnectTimeout))
            self._record(model, None, None, reason, t0, {})
            raise
        if model is None:
            return resp
        reason, ident = None, resp.headers.get(ID_HEADER)
        if resp.status_code >= 400:
            forge_reason = None
            try:
                await resp.aread()
                forge_reason = ((json.loads(resp.content or b"{}") or {}).get("error") or {}).get("forge_reason")
            except (ValueError, AttributeError, httpx.HTTPError):
                pass
            reason = classify(status=resp.status_code, forge_reason=forge_reason)
        elif ident:
            pinned = self.pins.setdefault(model, ident)
            if ident != pinned:  # never continue on a silently different model (US1 scenario 2)
                await resp.aclose()
                self._record(model, ident, 409, Reason.IDENTITY_CHANGED, t0, resp.headers)
                return httpx.Response(409, json={"error": {"type": "identity_changed", "forge_reason": "identity_changed",
                                                           "message": f"{model}: pinned {pinned}, served {ident}"}},
                                      request=request)
        self._record(model, ident, resp.status_code, reason, t0, resp.headers)
        if self.capture is not None and resp.status_code < 400 and self.capture.on():
            return await self._captured(req, resp, model, ident, at, t0)
        return resp

    async def _captured(self, req, resp, model, ident, at, t0) -> httpx.Response:
        try:
            body = json.loads(req.content or b"{}")
        except ValueError:
            body = {}
        base = {"kind": "gateway", "at": at, "model": model, "identity_prefix": ident, "tenant_id": self.tenant_id,
                "request": {k: v for k, v in body.items() if k != "forge_execution"}}

        def write(reply: dict) -> None:
            self.capture.write({**base, "reply": {**reply, "wall_ms": round((time.monotonic() - t0) * 1000)}})

        if "text/event-stream" in resp.headers.get("content-type", ""):
            return httpx.Response(resp.status_code, headers=resp.headers, request=req,
                                  stream=_TeeStream(resp.stream, lambda raw: write(_reply_of_sse(raw))),
                                  extensions=resp.extensions)
        raw = await resp.aread()
        try:
            write(_reply_of(json.loads(raw or b"{}")))
        except ValueError:
            pass
        return httpx.Response(resp.status_code, headers=resp.headers, content=raw, request=req,
                              extensions=resp.extensions)

    def _record(self, model, ident, status, reason, t0, headers) -> None:
        if self.log is None:
            return
        self.log.write({"model": model, "identity_prefix": ident, "status": status,
                        "forge_reason": reason.value if reason else None, "tenant_id": self.tenant_id,
                        "queue_ms": _int(headers.get(QUEUE_HEADER)), "swap_ms": _int(headers.get(SWAP_HEADER)),
                        "total_ms": round((time.monotonic() - t0) * 1000), "model_service_mode": "external"})

    async def aclose(self) -> None:
        await self.inner.aclose()


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
