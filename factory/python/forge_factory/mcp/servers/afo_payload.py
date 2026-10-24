"""Paged AFO tool data. `issues` is a 120-character diagnostic field, never a file transport."""
import json

from ...common import sha256_bytes
from ...events.redact import redact_text
from ..sdk import result


def payload(ctx, obj, offset=0, *, refs=(), summary="Untrusted case data", status="PASS"):
    text = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, separators=(",", ":"))
    text = redact_text(text)[0]
    chunk = text[offset:offset + 1000]
    metrics = {"data": chunk, "offset": offset, "total_chars": len(text),
               "next_offset": offset + len(chunk) if offset + len(chunk) < len(text) else None,
               "data_sha256": sha256_bytes(text.encode())}
    out = result(ctx, status, summary, list(refs), [], metrics, "forge-afo", max_bytes=2048,
                 output_bytes=text.encode())
    if out["metrics"].get("data") != chunk:
        return result(ctx, "BLOCKED", "page exceeds tool envelope; no partial data accepted",
                      issues=["AFO_DATA_PAGE_TOO_LARGE"], tool="forge-afo", max_bytes=2048)
    return out
