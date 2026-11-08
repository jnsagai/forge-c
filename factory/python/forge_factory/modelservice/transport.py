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
  (model, identity prefix, status, reason, queue and swap time) - never content (FR-024).
"""
from __future__ import annotations

import json
import os
import time
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


class ModelServiceTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport, *, key: Callable[[], str], expected: dict[str, dict],
                 log: CallLog | None = None, tenant_id: str = ""):
        self.inner, self.key, self.expected, self.log, self.tenant_id = inner, key, expected, log, tenant_id
        self.pins: dict[str, str] = {m: e["revision_fingerprint"][:16] for m, e in expected.items() if e.get("revision_fingerprint")}

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
        t0, sent = time.monotonic(), False
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
        return resp

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
