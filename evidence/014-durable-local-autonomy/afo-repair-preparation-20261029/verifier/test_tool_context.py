"""Actual child-process context from generated Fabro TOML; no model or service."""

import json
import os
import shlex
import subprocess
import tomllib

import pytest
from forge_factory.fabro.runconfig import render_run_toml


@pytest.mark.parametrize("override", [False, True])
def test_isolated_mcp_and_hook_resolve_the_same_pinned_tool_root(tmp_path, monkeypatch, override):
    root = tmp_path / "factory data"
    selected = tmp_path / "explicit server data" if override else root
    state = selected / "state"
    jar = selected / "toolchains/plantuml/plantuml-asl-1.2026.8.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"location-only fixture; never executed as a renderer")
    monkeypatch.setenv("FORGE_DATA_ROOT", str(root))
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    monkeypatch.setenv("UNRELATED_TEST_CREDENTIAL", "must-not-inherit")
    explicit = {"FORGE_DATA_ROOT": str(selected)} if override else {}
    config = tomllib.loads(render_run_toml(
        "workflow.fabro", "portable tool context", tmp_path / "binding file.json",
        {"forge-evidence-mcp": {"module": "forge_factory.mcp.servers.evidence", "env": explicit}},
        binding_id="context-fixture", hook_env=explicit,
    ))
    server = config["run"]["agent"]["mcps"]["forge_evidence_mcp"]
    code = (
        "import json,os; from forge_factory.common import data_root; "
        "from forge_factory.inspection import swtrace,views; "
        "print(json.dumps({'root':str(data_root()),'units':str(swtrace._plantuml_jar()),"
        "'views':str(views.plantuml_jar()),'ambient':os.environ.get('UNRELATED_TEST_CREDENTIAL')}))"
    )
    # Fabro supplies the TOML environment to isolated MCP children. Exercise that
    # exact map rather than inheriting the test runner's FORGE_DATA_ROOT.
    child = subprocess.run(
        [server["command"][0], "-c", code], env=server["env"], capture_output=True,
        text=True, check=True, timeout=10,
    )
    expected = {"root": str(selected), "units": str(jar), "views": str(jar), "ambient": None}
    assert json.loads(child.stdout) == expected
    assert server["env"]["FORGE_BINDING_ID"] == "context-fixture"
    for hook in config["run"]["hooks"]:
        prefix, _ = hook["script"].split(" -m forge_factory.policy.fabro_hook ", 1)
        observed = subprocess.run(
            ["/bin/sh", "-c", prefix + " -c " + shlex.quote(code)], env={"PATH": os.environ["PATH"]},
            capture_output=True, text=True, check=True, timeout=10,
        )
        assert json.loads(observed.stdout) == expected
