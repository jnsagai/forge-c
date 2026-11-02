"""Owner 2026-11-02 ("could be the average, no problem" / "lets just have a local gauge in the cell"): the line speed
KPI stays a Fabro node's average; the cell at work shows the speed of the model at work now, from the gateway's
per-call measurements (output tokens / latency of its latest calls)."""
import json
import time

from forge_factory.lrtx import floor_api as F


def _row(model, out, lat_ms, ago):
    return {"model": model, "tokens_output": out, "latency_ms": lat_ms,
            "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago))}


def test_recent_speed_is_the_latest_model_from_gateway_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    (tmp_path / "llm-gateway").mkdir()
    rows = [_row("ornith", 10828, 73400, 400), _row("ornith", 8449, 56700, 340), {"sample": {"gpu": 1}},
            _row("qwen3.8:27b-q8_0", 3822, 61100, 120), _row("qwen3.8:27b-q8_0", 1039, 24500, 60)]
    (tmp_path / "llm-gateway/usage.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    r = F.recent_speed(time.time())
    assert r["model"] == "qwen3.8:27b-q8_0" and r["calls"] == 2 and r["tok_s"] == round((3822 + 1039) / 85.6)
    assert F.recent_speed(time.time() + 3600) is None  # nothing in the last 10 minutes


def test_no_gateway_meter_no_speed(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    assert F.recent_speed(time.time()) is None
