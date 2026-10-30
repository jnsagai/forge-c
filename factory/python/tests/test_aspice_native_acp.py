"""Explicit native Codex/Claude comparison uses the same ASPICE scope without weakening local profiles."""
import json

import pytest
from forge_factory import acp
from forge_factory import workorder as W
from forge_factory.acp import claude_home, codex_home
from forge_factory.common import REPO_ROOT
from forge_factory.release import aspice


@pytest.mark.parametrize("authors,inspectors,purpose", [(None, None, "ASPICE_ONLY"), ("codex", None, "ASPICE_ONLY"),
                                                      (None, "claude", "ASPICE_ONLY"), ("codex", "claude", "QM")])
def test_missing_scope_profile_refuses_unless_explicit_dual_acp_aspice(tmp_path, authors, inspectors, purpose):
    with pytest.raises(ValueError, match="ASPICE_SCOPE_PROFILE_MISMATCH"):
        W.run(tmp_path, "WO-NATIVE-SCOPE", purpose=purpose, acp_authors=authors, acp_inspectors=inspectors)


@pytest.mark.parametrize("incomplete", [False, True])
def test_native_aspice_keeps_resolved_scope_and_cannot_fall_back_to_a_run_model(tmp_path, monkeypatch, incomplete):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    for module in (codex_home, claude_home):
        monkeypatch.setattr(module, "ensure", lambda *a, **kw: None)
        monkeypatch.setattr(module, "logged_in", lambda: True)
    monkeypatch.setattr(W, "suspension", lambda _: None)
    monkeypatch.setattr(W, "agent_preflight", lambda _: {"status": "PASS", "issues": []})
    monkeypatch.setattr(W, "mcp_preflight", lambda *a, **kw: {
        "status": "PASS", "issues": [], "disabled_optional_ops": [], "servers": []})
    monkeypatch.setattr(W, "fabro_mcp_config", lambda _: {})
    captured = []

    def write(ws, graph, *a, **kw):
        captured.append((ws, graph))
        return ws / ".forge-run/workflow.toml"

    monkeypatch.setattr(W, "write_run", write)
    if incomplete:
        monkeypatch.setattr(acp, "attach", lambda graph, *a, **kw: (graph, []))

    class BeforeNative(Exception):
        pass

    def stop():
        raise BeforeNative

    expected = pytest.raises(RuntimeError, match="NATIVE_ASPICE_ACP_INCOMPLETE") if incomplete else pytest.raises(BeforeNative)
    with expected:
        W.run(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-NATIVE-ASPICE", purpose="ASPICE_ONLY",
              acp_authors="codex", acp_inspectors="claude", before_native_launch=stop)
    if not incomplete:
        ws, graph = captured[0]
        manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
        assert aspice.selected(manifest) and manifest["purpose"] == "ASPICE_ONLY"
        assert manifest["native_aspice_backends"] == {
            "authors": "codex", "inspectors": "claude", "native_model_agent_nodes": [], "local_inference_requests": 0}
        assert acp.native_agent_nodes(graph) == []
        assert "local_profile" not in manifest and "development_execution" not in manifest
