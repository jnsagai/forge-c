"""Installed simulation/render tools must be visible to real production preflight and MCP children."""
from forge_factory.lrtx import stack


def test_optional_installed_tools_are_on_the_stack_path(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path))
    settings = stack.settings("local-rtx-v2-omniverse2-q38-qm-demo-repair-mtp")
    before = stack.envmap(settings)["PATH"].split(":")
    paths = [tmp_path / "toolchains/plantuml", tmp_path / "toolchains/renode/renode_1.17.0-portable"]
    for path in paths:
        assert str(path) not in before
        path.mkdir(parents=True)
    actual = stack.envmap(settings)["PATH"].split(":")
    assert [path for path in actual if path not in before] == [str(path) for path in paths]
    assert actual[:2] == before[:2]  # Pinned Python/LLVM retain precedence.


def test_uninstalled_optional_tools_preserve_the_existing_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path))
    settings = stack.settings("local-rtx-v1")
    env = stack.envmap(settings)
    assert env["PATH"] == ":".join([
        str(tmp_path / "venv/bin"), str(tmp_path / "toolchains/LLVM-19.1.7-Linux-X64/bin"), stack.SYSTEM_PATH,
        str(tmp_path / "toolchains/formal/bin"), str(tmp_path / "toolchains/sysroot/usr/bin")])
