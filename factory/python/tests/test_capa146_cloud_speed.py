import json
import time

from forge_factory.lrtx import floor_api as F


def test_account_meter_supplies_speed_before_a_fabro_node_finishes(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    now = time.time()
    meter = tmp_path / "cloud-bridge/calls.jsonl"
    meter.parent.mkdir()
    rows = [{"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - age)),
             "model": "gpt-6.1-terra", "wall_ms": 10000, "ok": True,
             "usage": {"completion_tokens": tokens, "billing": "account"}}
            for age, tokens in ((900, 90000), (50, 100), (30, 200))]
    meter.write_text("".join(json.dumps(r) + "\n" for r in rows))
    speed = F.recent_speed(now)
    assert speed["tok_s"] == 15 and speed["calls"] == 2
    assert speed["model"] == "gpt-6.1-terra" and "cloud bridge" in speed["basis"]
    assert F.recent_speed(now + 3600) is None


def test_gateway_measurement_is_preferred_without_double_counting(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    now = time.time()
    for name, row in [("cloud-bridge/calls.jsonl", {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 50)),
                       "model": "terra", "wall_ms": 10000, "usage": {"completion_tokens": 100}}),
                      ("llm-gateway/usage.jsonl", {"ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 20)),
                       "model": "terra", "latency_ms": 5000, "tokens_output": 100})]:
        p = tmp_path / name
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(row) + "\n")
    speed = F.recent_speed(now)
    assert speed["tok_s"] == 20 and speed["calls"] == 1 and "gateway" in speed["basis"]
