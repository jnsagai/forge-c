"""Native ACP tools inherit the pinned launch environment, not the older Fabro server's PATH."""
import shlex

from forge_factory import acp
from forge_factory.acp import proxy


def test_acp_command_preserves_exact_root_state_and_toolchain_path_with_safe_quoting(tmp_path, monkeypatch):
    data = tmp_path / "data with spaces"
    state = data / "state"
    path = str(data / "LLVM19/bin") + ":/usr/bin:/bin"
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data))
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    monkeypatch.setenv("PATH", path)
    workspace = state / "workorders/WO-CONTROL/workspace"
    command = shlex.split(acp.acp_command(workspace, "swe1_inspector", "claude"))
    assert command[0] == "env"
    assert "PATH=" + path in command and "FORGE_DATA_ROOT=" + str(data) in command
    assert "FORGE_STATE_DIR=" + str(state) in command
    assert command[command.index("--binding") + 1] == str(workspace / ".forge-run/binding.json")
    assert command[-2:] == ["--agent", "claude"]


def test_every_gate_server_receives_the_same_root_and_pinned_path(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("PATH", "/pinned-LLVM19/bin:/usr/bin:/bin")
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/workflow.toml").write_text('[run.agent.mcps.forge_build_mcp]\ntype="stdio"\n')
    servers = proxy.gate_servers(tmp_path / ".forge-run/binding.json", "swe3_author", tmp_path)
    assert set(servers) == {"forge_fs", "forge_build_mcp"}
    assert all(s["env"]["PATH"] == "/pinned-LLVM19/bin:/usr/bin:/bin" for s in servers.values())
    assert all(s["env"]["FORGE_DATA_ROOT"] == str(tmp_path / "data") for s in servers.values())
