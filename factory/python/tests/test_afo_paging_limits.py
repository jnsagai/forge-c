"""Source-size, escaped-byte and real blocking-hook regressions for AFO limits."""
import hashlib
import json

import pytest
import yaml

from forge_factory.afo import maintainer as M
from forge_factory.common import CONFIG_DIR
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import afo_payload as P
from forge_factory.mcp.servers import maintainer as server
from forge_factory.policy import governor
from forge_factory.policy.authz import Binding
from forge_factory.policy.fabro_hook import handle
from forge_factory.registry import agents


def context(tmp_path):
    return sdk.ToolContext("forge-maintainer-mcp", "read_source", "afo-factory-maintainer", None, tmp_path, "run")


@pytest.mark.parametrize("text", [
    "# line with quotes: \"value\"\\n\n" * 8000,
    "🙂漢\n\x01\\\"" * 12000,
])
def test_complete_pages_fit_actual_serialized_response_and_reconstruct_text(tmp_path, text):
    chunks, offset = [], 0
    while True:
        out = P.payload(context(tmp_path), text, offset, refs=["source:bound"])
        metrics = out["metrics"]
        assert out["status"] == "PASS"
        assert len(json.dumps(out, separators=(",", ":")).encode()) <= 65536
        assert len(metrics["data"]) <= 32768 and metrics["offset"] == offset
        assert metrics["data_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        assert out["artifact_refs"] == ["source:bound"]
        chunks.append(metrics["data"])
        offset = metrics["next_offset"]
        if offset is None:
            break
        assert offset == sum(len(s) for s in chunks)
    assert "".join(chunks) == text
    assert len(chunks) > 1


def test_existing_measured_generated_driver_size_fits_one_response(tmp_path):
    out = P.payload(context(tmp_path), "x" * 7278)
    assert len(out["metrics"]["data"]) == 7278 and out["metrics"]["next_offset"] is None


def candidate(tmp_path, monkeypatch, size):
    rel = "factory/python/forge_factory/example.py"
    source = tmp_path / rel
    source.parent.mkdir(parents=True)
    source.write_bytes(b"#" * size)
    monkeypatch.setattr(server, "_case", lambda: {"src": str(tmp_path)})
    return rel


def test_largest_measured_delivered_driver_can_be_read_without_64k_cutoff(tmp_path, monkeypatch):
    rel = candidate(tmp_path, monkeypatch, 340069)
    chunks, offset = [], 0
    while True:
        out = server.read_source(context(tmp_path), server.PathIn(path=rel, offset=offset))
        chunks.append(out["metrics"]["data"])
        offset = out["metrics"]["next_offset"]
        if offset is None:
            break
    assert len(chunks) == 11 and "".join(chunks) == "#" * 340069


def test_largest_measured_test_header_tail_is_addressable(tmp_path, monkeypatch):
    rel = candidate(tmp_path, monkeypatch, 3599048)
    out = server.read_source(context(tmp_path), server.PathIn(path=rel, offset=3599000))
    assert out["metrics"]["data"] == "#" * 48 and out["metrics"]["next_offset"] is None
    assert out["metrics"]["total_chars"] == 3599048


def test_source_limit_is_bounded_and_does_not_enlarge_write_permissions(tmp_path, monkeypatch):
    rel = candidate(tmp_path, monkeypatch, M.MAX_SOURCE_READ_BYTES + 1)
    with pytest.raises(sdk.ToolDenied, match="SOURCE_TOO_LARGE"):
        server.read_source(context(tmp_path), server.PathIn(path=rel))
    with pytest.raises(M.MaintainerDenied, match="FILE_TOO_LARGE"):
        M.write_source({"src": str(tmp_path)}, rel, "x" * (M.MAX_FILE_BYTES + 1))
    with pytest.raises(M.MaintainerDenied):
        M.read_source({"src": str(tmp_path)}, "evidence/private.json")


def test_new_tool_allowance_reaches_200_then_real_hook_refuses_201(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    binding = Binding("large-maintenance", str(tmp_path), {"agent": {"role": "afo-factory-maintainer"}})
    governor.reset_node(binding.binding_id, "run", "agent")
    call = {"event": "pre_tool_use", "run_id": "run", "node_id": "agent",
            "tool_name": "mcp__forge_maintainer_mcp__read_source", "tool_input": {"path": "factory/python/x.py"}}
    for _ in range(200):
        assert handle(call, binding).allow
    denied = handle(call, binding)
    assert not denied.allow and denied.code == "TURN_BUDGET_EXHAUSTED"
    assert "201>200" in denied.reason
    assert not handle({**call, "tool_name": "shell", "tool_input": {"command": "true"}}, binding).allow


def test_registered_skills_policy_and_formatter_budgets_are_consistent():
    check = agents.preflight(["afo-recovery-planner", "afo-factory-maintainer"], include_afo=True)
    assert check["status"] == "PASS", check["issues"]
    policy = yaml.safe_load((CONFIG_DIR / "token-policy.yaml").read_text())
    assert policy["max_tool_result_bytes"] == 2048
    assert policy["afo_max_tool_result_bytes"] == P.MAX_RESPONSE_BYTES
    roles, _ = agents.load_agents(include_afo=True)
    for role in roles:
        assert role.max_mcp_output_bytes == (65536 if role.id.startswith("afo-") else 2048)


@pytest.mark.parametrize("invalid", [True, 0, -1, "65536", 65537])
def test_malformed_afo_policy_allowance_is_refused(tmp_path, invalid):
    policy = yaml.safe_load((CONFIG_DIR / "token-policy.yaml").read_text())
    policy["afo_max_tool_result_bytes"] = invalid
    path = tmp_path / "token-policy.yaml"
    path.write_text(yaml.safe_dump(policy))
    check = agents.preflight(["afo-factory-maintainer"], include_afo=True, token_policy_path=path)
    assert check["status"] == "BLOCKED" and "AGENT_BUDGET_INVALID" in check["issue_codes"]
