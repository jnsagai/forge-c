"""The factory's LLM gateway in external model service mode (feature 017, FR-001, FR-002, FR-004).

It is the unchanged `llm_gateway` application (its source stays byte-identical, research R7) with one difference:
its upstream transport is `ModelServiceTransport`, pointed at the model channel only. The gateway's admission is
set from the factory tenant's share. Nothing here starts, stops or swaps a model server or touches the GPU.

    python -m forge_factory.modelservice.gateway_external --port P --model-service model-service.yaml \
        --secrets FILE --meter usage.jsonl --calls calls.jsonl
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import httpx

from .client import load_profile
from .secrets import resolve
from .transport import CallLog, Capture, ModelServiceTransport


def upstream_of(profile: dict, inner: httpx.AsyncBaseTransport | None = None) -> tuple[str, httpx.AsyncBaseTransport]:
    """'unix:/path' reaches a service socket on the shared filesystem (a lane in its own network namespace);
    anything else is the service URL itself."""
    base = profile["base_url"]
    # llm_gateway posts to "/v1/chat/completions" relative to its upstream: give it the service ROOT (qualification
    # window 1, 2026-11-12: a ".../v1" upstream made every call "/v1/v1/chat/completions" -> HTTP 404)
    if base.startswith("unix:"):
        return "http://model-service", inner or httpx.AsyncHTTPTransport(uds=base[len("unix:"):])
    return base.rstrip("/").removesuffix("/v1"), inner or httpx.AsyncHTTPTransport()


def build_app(profile: dict, *, secrets: Path, meter: Path, calls: Path, inner: httpx.AsyncBaseTransport | None = None,
              capture_root: Path | None = None):
    from .. import llm_gateway

    if profile["mode"] != "external":
        raise ValueError("NOT_EXTERNAL_MODE")
    os.environ["FORGE_GATEWAY_MAX_INFLIGHT"] = str(int(profile["share"]["concurrency"]))  # the tenant's share (FR-004)
    upstream, transport = upstream_of(profile, inner)
    t = ModelServiceTransport(transport, key=lambda: resolve(profile["credential_ref"], secrets).reveal(),
                              expected=profile["expected_identity"], log=CallLog(calls), tenant_id=profile["credential_ref"],
                              capture=Capture(capture_root) if capture_root else None)
    return llm_gateway.create_app(upstream=upstream, meter_path=meter, transport=t)


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    ap = argparse.ArgumentParser(prog="gateway_external")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--model-service", type=Path, required=True)
    ap.add_argument("--secrets", type=Path, required=True)
    ap.add_argument("--meter", type=Path, required=True)
    ap.add_argument("--calls", type=Path, required=True)
    ap.add_argument("--capture-root", type=Path, help="<state>/model-exchanges (capture only when its switch is on)")
    a = ap.parse_args(argv)
    app = build_app(load_profile(a.model_service), secrets=a.secrets, meter=a.meter, calls=a.calls, capture_root=a.capture_root)
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
