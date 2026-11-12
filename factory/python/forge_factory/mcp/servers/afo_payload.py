"""Paged AFO tool data. `issues` is a 120-character diagnostic field, never a file transport."""
import json

from ...common import sha256_bytes
from ...events.redact import redact_text
from ..sdk import result

PAGE_CHARS = 32_768
MAX_RESPONSE_BYTES = 65_536


def payload(ctx, obj, offset=0, *, refs=(), summary="Untrusted case data", status="PASS"):
    text = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, separators=(",", ":"))
    text = redact_text(text)[0]
    raw = text.encode()
    text_hash = sha256_bytes(raw)
    artifact_refs = list(refs)

    def page(size):
        chunk = text[offset:offset + size]
        metrics = {"data": chunk, "offset": offset, "total_chars": len(text),
                   "next_offset": offset + len(chunk) if offset + len(chunk) < len(text) else None,
                   "data_sha256": text_hash}
        out = result(ctx, status, summary, artifact_refs, [], metrics, "forge-afo",
                     max_bytes=MAX_RESPONSE_BYTES, output_bytes=raw)
        # The SDK bounds canonical UTF-8; the stdio tool returns JSON text with
        # ASCII escaping. Check that exact serialization too, including metadata.
        fits = (out["metrics"] == metrics
                and len(json.dumps(out, separators=(",", ":")).encode()) <= MAX_RESPONSE_BYTES)
        return out, fits

    maximum = min(PAGE_CHARS, max(0, len(text) - offset))
    out, fits = page(maximum)
    if fits:
        return out
    low, high, best = 1, maximum - 1, None
    while low <= high:
        size = (low + high) // 2
        candidate, fits = page(size)
        if fits:
            best, low = candidate, size + 1
        else:
            high = size - 1
    if best is not None:
        return best
    return result(ctx, "BLOCKED", "page exceeds tool envelope; no partial data accepted",
                  issues=["AFO_DATA_PAGE_TOO_LARGE"], tool="forge-afo", max_bytes=MAX_RESPONSE_BYTES)
