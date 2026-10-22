"""LRTX-T012: runtime capability probe of the structured-output mode, bound to the served model digest, and its use."""
import json

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import visit as V

DIGEST = "06c1097efce8" + "0" * 52


@pytest.fixture()
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path / "state"


def _fake_call(valid: dict):
    def call(p, *, schema_mode="json_schema", **_kw):
        ok = valid[schema_mode]
        return {"doc": {"answer": "yes", "items": [2, 4, 6]} if ok else None, "errors": [] if ok else ["NOT_JSON"],
                "usage": {"prompt_tokens": 300}, "wall_ms": 5.0, "raw_chars": 10, "finish_reason": "stop",
                "format_note": None}
    return call


def test_probe_selects_the_strongest_honoured_mode_and_records_the_digest(state, monkeypatch):
    monkeypatch.setattr(S, "call", _fake_call({"json_schema": False, "json_object": True, "none": True}))
    out = S.record_capabilities("qwen3-coder:30b", DIGEST)
    assert out["selected_mode"] == "json_object" and out["json_schema"]["valid"] is False
    rec = json.loads(S.capability_path("qwen3-coder:30b").read_text())
    assert rec["digest"] == DIGEST and rec["schema"] == "forge-c/lrtx-capabilities/1"
    assert S.schema_mode_for("qwen3-coder:30b", DIGEST) == ("json_object", f"PROBED {rec['probed_at']}")


def test_unprobed_stale_or_unconstrained_models_keep_the_schema_contract(state, monkeypatch):
    assert S.schema_mode_for("qwen3:8b", DIGEST) == ("json_schema", "UNPROBED (default)")
    monkeypatch.setattr(S, "call", _fake_call({"json_schema": False, "json_object": True, "none": True}))
    S.record_capabilities("qwen3:8b", DIGEST)
    mode, why = S.schema_mode_for("qwen3:8b", "f" * 64)
    assert mode == "json_schema" and why.startswith("PROBE_STALE")
    monkeypatch.setattr(S, "call", _fake_call({"json_schema": False, "json_object": False, "none": True}))
    S.record_capabilities("qwen3:8b", DIGEST)
    mode, why = S.schema_mode_for("qwen3:8b", DIGEST)
    assert mode == "json_schema" and "no constrained mode" in why  # never silently drop to unconstrained output


def test_a_visit_calls_with_the_probed_mode_and_logs_it(state, monkeypatch, tmp_path):
    monkeypatch.setattr(S, "call", _fake_call({"json_schema": False, "json_object": True, "none": True}))
    S.record_capabilities("m", None)
    seen = []

    def call(p, *, schema_mode="json_schema", **_kw):
        seen.append(schema_mode)
        return {"doc": {"answer": "yes", "items": [2, 4, 6]}, "errors": [], "usage": None, "wall_ms": 1.0,
                "raw_chars": 1, "finish_reason": "stop", "format_note": None}

    monkeypatch.setattr(S, "call", call)

    def build(_findings, _previous):
        return S.packet(phase="PROBE", task="t", role="swe1-author", with_skill=False, model="m", instructions="x",
                        sources=[], criteria=[], output_schema=S.PROBE_SCHEMA, output_reserve=64)

    budget = {"calls": 0, "max_calls": 3, "state": None, "deadline": None}
    V.run_task(tmp_path / "ws", "SWE.1", "t", build, lambda _d: [], budget)
    assert seen == ["json_object"] and budget["schema_mode"] == "json_object"
    assert budget["log"][0]["schema_mode"] == "json_object" and budget["log"][0]["schema_mode_basis"].startswith("PROBED")


def test_visit_mode_selection_is_per_visit(state, monkeypatch):
    monkeypatch.setattr(S, "call", _fake_call({"json_schema": False, "json_object": True, "none": True}))
    S.record_capabilities("m", None)
    assert S.schema_mode_for("m")[0] == "json_object"
