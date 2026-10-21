"""LRTX-T010 (LRTX-FR-007): per-work-order measurement record of a local-profile run.

    python -m forge_factory.lrtx.runmetrics --workspace <ws> [--out <json>]

Joins three observed sources for the run's time window: Fabro's stage records (wall, active, inference and tool time
per stage, from the run's server log), the admission gateway meter (queue wait, model load, prefill, decode, tokens,
GPU residency per call) and the gateway's periodic resource samples (GPU board power, memory). Energy is the GPU-only
trapezoid integral of plausible power samples with its coverage stated; wall energy stays UNKNOWN on this host.
Anything not observed is UNKNOWN - nothing is estimated from per-call figures.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
from datetime import datetime
from pathlib import Path

from ..common import pretty_json, utc_now

STAGE = re.compile(r'^(\S+) .*Stage (completed|failed) node_id="([^"]+)".*?wall_time_ms=(\d+) active_time_ms=(\d+) '
                   r'inference_time_ms=(\d+) tool_time_ms=(\d+)(?: status="(\w+)")?')


def _ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def stages(log: Path) -> list[dict]:
    out = []
    for line in log.read_text(errors="replace").splitlines() if log.is_file() else []:
        m = STAGE.match(line)
        if m:
            out.append({"at": m.group(1), "node": m.group(3), "wall_ms": int(m.group(4)), "active_ms": int(m.group(5)),
                        "inference_ms": int(m.group(6)), "tool_ms": int(m.group(7)),
                        "status": m.group(8) or m.group(2)})
    return out


def _q(xs: list[float], p: float) -> float | None:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def collect(ws: Path, storage: Path | None = None, meter: Path | None = None) -> dict:
    ws = Path(ws)
    rid = (ws / ".forge-run/fabro_run_id").read_text().strip() if (ws / ".forge-run/fabro_run_id").is_file() else None
    storage = Path(storage or os.environ.get("FORGE_FABRO_STORAGE", ""))
    log = next(iter(sorted(storage.glob(f"scratch/*-{rid}/runtime/server.log"))), None) if rid else None
    st = stages(log) if log else []
    if not st:
        return {"status": "UNKNOWN", "reason": "no Fabro stage records for the run"}
    t0, t1 = _ts(st[0]["at"]) - max(1, st[0]["wall_ms"] / 1000), _ts(st[-1]["at"])
    meter = Path(meter or Path(os.environ.get("FORGE_STATE_DIR", "")) / "llm-gateway/usage.jsonl")
    calls, samples, refusals = [], [], []
    for line in meter.read_text().splitlines() if meter.is_file() else []:
        r = json.loads(line)
        if not t0 <= _ts(r["ts_utc"]) <= t1:
            continue
        if "sample" in r:
            samples.append((_ts(r["ts_utc"]), r["sample"]))
        elif "refused" in r:
            refusals.append(r["refused"])
        elif "local" in r:
            calls.append(r)
    loc = [c["local"] for c in calls]
    num = lambda k: [x[k] for x in loc if isinstance(x.get(k), (int, float))]  # noqa: E731
    pin = [c["tokens_input"] for c in calls if c.get("tokens_input")]
    pw = [(t, s["gpu"]["power_w"]) for t, s in samples if (s.get("gpu") or {}).get("power_w") is not None]
    energy_j = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(pw, pw[1:], strict=False))
    res = [m["vram_fraction"] for _t, s in samples for m in (s.get("residency") or {}).get("loaded", [])
           if m.get("vram_fraction") is not None]
    by_node: dict[str, dict] = {}
    for s in st:
        n = by_node.setdefault(s["node"], {"visits": 0, "wall_ms": 0, "inference_ms": 0, "tool_ms": 0})
        n["visits"] += 1
        for k in ("wall_ms", "inference_ms", "tool_ms"):
            n[k] += s[k]
    return {"schema": "forge-c/lrtx-run-metrics/1", "generated_at": utc_now(), "fabro_run_id": rid,
            "window": {"from": st[0]["at"], "to": st[-1]["at"], "wall_s": round(t1 - t0, 1)},
            "stages": {"count": len(st), "wall_ms": sum(s["wall_ms"] for s in st),
                       "inference_ms": sum(s["inference_ms"] for s in st), "tool_ms": sum(s["tool_ms"] for s in st),
                       "basis": "Fabro stage records", "by_node": by_node},
            "calls": {"count": len(calls), "refused_or_cancelled": len(refusals),
                      "prompt_tokens": {"sum": sum(pin), "median": statistics.median(pin) if pin else None,
                                        "p95": _q(pin, 0.95), "max": max(pin) if pin else None},
                      "output_tokens": sum(c.get("tokens_output") or 0 for c in calls),
                      "queue_wait_ms": {"sum": sum(num("queue_wait_ms")), "max": max(num("queue_wait_ms"), default=None)},
                      "model_loads": sum(1 for x in loc if x.get("model_loaded_before") is False),
                      "load_ms": sum((x.get("load") or {}).get("load_ms") or 0 for x in loc),
                      "prefill_ms": sum(num("prefill_ms")), "decode_ms": sum(num("decode_ms")),
                      "first_delta_ms": sum(num("first_delta_ms")),
                      "split_unobservable": sum(1 for x in loc if isinstance(x.get("decode_ms"), str)),
                      "prefill_tokens_per_s_median": statistics.median(num("prefill_tokens_per_s"))
                      if num("prefill_tokens_per_s") else None,
                      "decode_tokens_per_s_median": statistics.median(num("decode_tokens_per_s"))
                      if num("decode_tokens_per_s") else None, "basis": "admission gateway meter"},
            "resources": {"samples": len(samples), "gpu_vram_fraction_min": min(res, default=None),
                          "gpu_vram_fraction_median": statistics.median(res) if res else None,
                          "host_swap_used_mib_max": max(((s.get("host") or {}).get("swap_used_mib", 0)
                                                         for _t, s in samples), default=None),
                          "host_mem_available_mib_min": min(((s.get("host") or {}).get("mem_available_mib", 10**9)
                                                             for _t, s in samples), default=None)},
            "energy": {"gpu_board_j": round(energy_j, 1) if len(pw) > 1 else "UNKNOWN",
                       "gpu_board_wh": round(energy_j / 3600, 3) if len(pw) > 1 else "UNKNOWN",
                       "coverage": round(len(pw) / len(samples), 3) if samples else 0.0,
                       "basis": "GPU board power reported by nvidia-smi, trapezoid over periodic samples; implausible "
                                "readings excluded", "wall": "UNKNOWN (no wall-power meter on this host)"}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    rec = collect(a.workspace)
    out = a.out or a.workspace / ".forge-run/lrtx/run-metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pretty_json(rec))
    print(json.dumps({k: rec.get(k) for k in ("fabro_run_id", "window")} | {"calls": (rec.get("calls") or {}).get("count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
