"""LRTX-T023: per-task model comparison on copies of one frozen start workspace (scripted models)."""
import json

from forge_factory.lrtx import modelcmp
from forge_factory.lrtx import structured as S
from test_lrtx_swe1 import ANSWERS, pytestmark, ws  # noqa: F401 - shared fixture, skip marker and scripted answers


def _by_model(calls):
    broken = {"requirements": [{"key": "x"}], "not_covered": [], "open_points": []}  # schema-invalid every time

    def call(p, **_k):
        calls.append((p["model"], p["task"]))
        doc = broken if p["model"] == "small" and p["task"] == "requirements:IWDG_KR" else ANSWERS[p["task"]]
        return {"doc": json.loads(json.dumps(doc)), "errors": S.validate(doc, p["output_schema"]),
                "usage": {"prompt_tokens": 1000 if p["model"] == "large" else 900, "completion_tokens": 100},
                "wall_ms": 50.0 if p["model"] == "large" else 10.0, "finish_reason": "stop"}
    return call


def test_attempts_never_write_the_start_workspace_and_compare_per_task(ws, monkeypatch, tmp_path):  # noqa: F811
    before = sorted(str(p.relative_to(ws)) for p in ws.rglob("*"))
    calls = []
    monkeypatch.setattr(S, "call", _by_model(calls))
    rows = [modelcmp.attempt(ws, tmp_path / "cmp", m, 1, tmp_path / "no-meter.jsonl", 35) for m in ("small", "large")]
    assert sorted(str(p.relative_to(ws)) for p in ws.rglob("*")) == before  # the start workspace is untouched
    small, large = rows
    assert large["visit"] == "PASS" and str(large["gate"]).startswith("FROZEN")
    assert small["visit"] == "FAILED" and small["gate"].startswith("NOT_RUN")
    assert small["tasks"]["requirements:IWDG_KR"]["status"] == "INVALID"
    assert small["tasks"]["requirements:IWDG_KR"]["calls"] > 1  # retries are counted
    assert small["tasks"]["requirements:IWDG_PR"]["first_call_valid"] is True
    by = modelcmp.summarise(rows)
    assert by["large"]["gate_frozen"] == 1 and by["small"]["visit_pass"] == 0
    assert by["small"]["load_ms_median"].startswith("UNKNOWN")
    est = modelcmp.mixed_estimate(by, "small", "large")
    assert est["basis"].startswith("DERIVED") and est["plan"]["requirements:IWDG_KR"] == "large"
    assert est["plan"]["requirements:IWDG_PR"] == "small" and est["switch_cost_ms"] == "UNKNOWN"
