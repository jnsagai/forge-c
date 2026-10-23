"""F011-T028 (F011-FR-021): host measurement of a local model candidate, one model at a time.

    python -m forge_factory.lrtx.modelprobe --model gpt-oss:20b --model qwen3-coder:30b --out <report.json>

Runs inside the profile namespace against the profile's own Ollama (FORGE_OLLAMA_URL). For each model it records:
- presence and digest in the local store;
- family, parameter size, quantization and context length (`/api/show`);
- cold load time, after unloading every model first;
- memory once loaded (`/api/ps`: size in VRAM and in total);
- prefill and decode rate on one fixed prompt;
- failures as they happen.

A model that is not in the local store is MISSING. Downloading a model is an owner decision and never happens here.
Nothing is qualified by this probe: role qualification needs the seeded and holdout catalogue (F011-T029).
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..common import pretty_json, utc_now

PROMPT = ("List the three bit fields of a 32-bit register whose bits 0-3 hold PR, bits 4-15 are reserved and bit 16 "
          "holds EN, as JSON with keys name, lsb, msb.")


def _api(path: str, body: dict | None = None, timeout: float = 600.0) -> dict:
    url = os.environ.get("FORGE_OLLAMA_URL", "http://127.0.0.1:11455") + path
    if not url.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise ValueError(f"PROBE_NOT_LOOPBACK:{url}")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},  # noqa: S310
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - loopback Ollama of the profile only
        return json.loads(r.read())


def _unload_all() -> None:
    for m in _api("/api/ps").get("models", []):
        _api("/api/generate", {"model": m["name"], "keep_alive": 0})


def probe(model: str) -> dict:
    tags = {m["name"]: m for m in _api("/api/tags").get("models", [])}
    if model not in tags:
        return {"model": model, "status": "MISSING", "note": "not in the local model store; downloading a model is an "
                                                             "owner decision"}
    rec = {"model": model, "digest": tags[model]["digest"], "size_bytes": tags[model].get("size"), "status": "MEASURED"}
    try:
        show = _api("/api/show", {"model": model})
        det = show.get("details") or {}
        info = show.get("model_info") or {}
        rec.update({"family": det.get("family"), "parameter_size": det.get("parameter_size"),
                    "quantization": det.get("quantization_level"),
                    "context_length": next((v for k, v in info.items() if k.endswith(".context_length")), None)})
        _unload_all()
        t0 = time.monotonic()
        _api("/api/generate", {"model": model, "prompt": "", "keep_alive": "5m"})
        rec["cold_load_s"] = round(time.monotonic() - t0, 2)
        ps = next((m for m in _api("/api/ps").get("models", []) if m["name"] == model), {})
        rec.update({"loaded_size_bytes": ps.get("size"), "loaded_vram_bytes": ps.get("size_vram")})
        out = _api("/api/generate", {"model": model, "prompt": PROMPT, "stream": False, "keep_alive": "5m",
                                     "options": {"temperature": 0, "num_predict": 256}})
        ns = 1e9
        rec.update({"prompt_tokens": out.get("prompt_eval_count"), "output_tokens": out.get("eval_count"),
                    "prefill_tok_s": round(out["prompt_eval_count"] / (out["prompt_eval_duration"] / ns), 1)
                    if out.get("prompt_eval_duration") else None,
                    "decode_tok_s": round(out["eval_count"] / (out["eval_duration"] / ns), 1)
                    if out.get("eval_duration") else None,
                    "total_s": round(out.get("total_duration", 0) / ns, 2)})
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        rec.update({"status": "FAILED", "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
    finally:
        try:
            _api("/api/generate", {"model": model, "keep_alive": 0})
        except (urllib.error.URLError, TimeoutError):
            pass
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rows = [probe(m) for m in a.model]  # one model at a time, each from a cold start
    rep = {"schema": "forge-c/lrtx-modelprobe/1", "generated_at": utc_now(), "ollama": os.environ.get("FORGE_OLLAMA_URL"),
           "rows": rows, "note": "Host measurement only; no role qualification (F011-T029 decides that)."}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(rep))
    print(json.dumps([{k: r.get(k) for k in ("model", "status", "cold_load_s", "loaded_vram_bytes", "decode_tok_s")}
                      for r in rows]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
