"""Owner 2026-11-02 (comparison line): a cloud-bridge profile runs no ollama or llama-server, routes its models to the
bridge socket, reports the bridge in its health, and `serve` is a recorded no-op routed to the bridge."""
import json
import threading
from types import SimpleNamespace

import pytest
from forge_factory.lrtx import cloud_bridge as CB
from forge_factory.lrtx import profile as lp
from forge_factory.lrtx import stack

PID = "cloud-bridge-claude-author-codex-inspector"


def test_the_comparison_profile_is_the_ornith_think_profile_with_only_the_models_changed():
    cb, orn = lp.load(PID), lp.load("local-rtx-v2-omniverse2-ornith-think-author-q38-inspector")
    assert cb["structured"]["role_models"] == {"author": "claude-opus-5-5", "inspector": "gpt-6.1-sol"}
    same = ("phases_by_layer", "inspect_phases_by_layer", "visit_time_s", "inspection_max_source_chars", "timeout_s",
            "reinspect_direct", "swe2_named_functions", "swe2_constrained_design", "brownfield_structured_phases",
            "inspector_coverage", "inspector_entries", "inspector_stepwise", "author_max_calls_by_phase")
    assert {k: cb["structured"].get(k) for k in same} == {k: orn["structured"].get(k) for k in same}
    assert stack.cloud_bridge(cb) and stack.cloud_bridge(orn) is None and cb["local_only"] is False
    assert lp.selection_issues(cb, model="claude-opus-5-5", provider="ollama", code_model=None, acp_authors=None,
                               acp_inspectors=None) == []


def test_serve_is_a_recorded_no_op_routed_to_a_healthy_bridge(tmp_path, monkeypatch):
    prof = lp.load(PID)
    s = {"profile": prof, "root": tmp_path, "ports": prof["deployment"]["ports"]}
    with pytest.raises(RuntimeError, match="CLOUD_BRIDGE_UNREACHABLE"):
        stack.serve(s, "claude-opus-5-5")
    sock = stack.bridge_socket(tmp_path, prof)
    srv = CB.serve(sock, CB.Bridge({"claude-opus-5-5": {"backend": "x"}}, {}, tmp_path / "m.jsonl"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert stack.bridge_healthy(sock)
        out = stack.serve(s, "gpt-6.1-sol", workspace=tmp_path / "ws")
        assert out["result"] == "BRIDGE_ROUTED" and out["digest"] == "cloud:openai:gpt-6.1-sol"
        rows = [json.loads(x) for x in (tmp_path / "ws/.forge-run/lrtx/serving/model-swaps.jsonl").read_text().splitlines()]
        assert rows[-1]["result"] == "BRIDGE_ROUTED"
        with pytest.raises(RuntimeError, match="NOT_SERVED"):
            stack.serve(s, "qwen3.8:27b-q8_0")
    finally:
        srv.shutdown()
        srv.server_close()
