"""A bridge using the isolated ACP home must request its own envelope, without changing that home."""
import json
from pathlib import Path
from types import SimpleNamespace

from forge_factory.lrtx.cloud_bridge import CodexBackend


def test_native_tool_envelope_overrides_inherited_status_only_instructions(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('developer_instructions = "Return only status, artifacts, issues and next_action"\n')
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-account-worker")
    seen = []

    def run(argv, **kw):
        seen.append(argv)
        overrides = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg == "-c"]
        scoped = next((s for s in overrides if s.startswith("developer_instructions=")), "")
        assert "caller's separate workspace under its own permissions" in scoped
        assert "Preserve all caller role, path and quality restrictions" in scoped
        assert argv[argv.index("--sandbox") + 1] == "read-only"
        answer = {"action": "tool_calls", "tool_calls": [{"name": "echo", "arguments": {"text": "hello"}}],
                  "content": ""} if "stateless model backend" in scoped else {
                      "status": "BLOCKED", "artifacts": [], "issues": ["no MCP tools"], "next_action": "halt"}
        Path(argv[argv.index("-o") + 1]).write_text(json.dumps(answer))
        assert "OPENAI_API_KEY" not in kw["env"]
        assert kw["env"]["CODEX_HOME"] == str(tmp_path)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    body = {"model": "gpt-6.1-terra", "messages": [{"role": "user", "content": "Call echo with text hello"}],
            "tool_choice": "required", "tools": [{"type": "function", "function": {"name": "echo",
            "parameters": {"type": "object", "additionalProperties": False, "required": ["text"],
                           "properties": {"text": {"type": "string"}}}}}]}
    result = CodexBackend(str(tmp_path), run=run).answer(body, {"model": "gpt-6.1-terra"})
    assert result["finish"] == "tool_calls" and result["tool_calls"][0]["function"]["name"] == "echo"
    assert len(seen) == 1
    assert config.read_text() == 'developer_instructions = "Return only status, artifacts, issues and next_action"\n'
