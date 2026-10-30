"""Model-free native context measurement on an already pinned llama.cpp route.

The complete canonical request is tokenized as well as its native chat template.
Non-message controls/schemas are counted separately: the conservative bound is
max(serialized request, rendered prompt + controls) plus a framing margin. No
generation, raw prompt persistence, model self-assessment or budget reconciliation
occurs here. A native transport/protocol failure refuses before admission.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx

from ..afo.durable import Refused, canonical

METHOD = "native_template_plus_serialized"
MAX_REQUEST_BYTES = 8 * 1024 * 1024


def policy(prof: dict) -> dict:
    configured = (prof.get("gateway") or {}).get("request_measurement", {})
    allowed = (prof.get("models") or {}).get("allowed", {})
    if not isinstance(configured, dict) or any(m not in allowed or value != METHOD for m, value in configured.items()):
        raise ValueError("PROFILE_REQUEST_MEASUREMENT_INVALID")
    if configured and not (prof.get("runtime") or {}).get("llama_server"):
        raise ValueError("PROFILE_REQUEST_MEASUREMENT_REQUIRES_NATIVE_ROUTE")
    return dict(configured)


def required_at_gateway(ws: Path | None, model: str) -> bool:
    """Only a durably bound, explicitly selected profile can defer the byte estimate.

    This is not an admission or a fit result. The gateway must measure its full
    transformed body and apply the usual context/capability/mission gates before
    reserving or sending inference. An older gateway still rejects by byte bound.
    """
    if ws is None or not (ws / ".forge-run/durable-binding.json").is_file():
        return False
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    selected = (manifest.get("local_profile") or {}).get("id")
    if not selected:
        return False
    from .profile import load

    return model in policy(load(selected))


async def measure(client: httpx.AsyncClient, body: dict) -> dict:
    started = time.monotonic()
    raw = canonical(body)
    if len(raw) > MAX_REQUEST_BYTES:
        raise Refused("NATIVE_MEASUREMENT_REQUEST_TOO_LARGE")

    async def post(path, value):
        try:
            response = await client.post(path, json=value, timeout=httpx.Timeout(30, connect=5))
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise Refused("NATIVE_MEASUREMENT_UNAVAILABLE") from exc

    rendered = await post("/apply-template", body)
    prompt = rendered.get("prompt") if isinstance(rendered, dict) else None
    if not isinstance(prompt, str) or not prompt or len(prompt.encode()) > MAX_REQUEST_BYTES:
        raise Refused("NATIVE_MEASUREMENT_TEMPLATE_INVALID")
    controls = canonical({k: v for k, v in body.items() if k != "messages"})
    counts = {}
    for name, text in (("serialized_request", raw.decode()), ("chat_template", prompt),
                       ("non_message_controls", controls.decode())):
        result = await post("/tokenize", {"content": text, "add_special": True})
        tokens = result.get("tokens") if isinstance(result, dict) else None
        if (not isinstance(tokens, list) or not tokens or len(tokens) > MAX_REQUEST_BYTES
                or any(type(token) is not int or token < 0 for token in tokens)):
            raise Refused("NATIVE_MEASUREMENT_TOKENS_INVALID")
        counts[name] = len(tokens)
    return {
        "sha256": hashlib.sha256(raw).hexdigest(), "serialized_bytes": len(raw),
        "input_tokens": max(counts["serialized_request"], counts["chat_template"] + counts["non_message_controls"]) + 128,
        "method": METHOD, "native_measured": True, "counts": counts, "framing_reserve_tokens": 128,
        "chat_template_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "wall_ms": round((time.monotonic() - started) * 1000, 3),
    }
