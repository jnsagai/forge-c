"""Native MCP default expansion must preserve the authorized logical call."""

import asyncio

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import build
from pydantic import Field


@pytest.mark.parametrize("profile", ["host-clang", "target-cm55-gcc"])
def test_native_mcp_expanded_default_list_keeps_exact_one_time_ticket(tmp_path, monkeypatch, profile):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("FORGE_BINDING_ID", "factory-default-fixture")
    monkeypatch.delenv("FORGE_MCP_TRUST", raising=False)
    seen = []

    def handler(ctx, args):
        seen.append((ctx.role, ctx.phase, args.profile, args.defines))
        return sdk.result(ctx, "PASS", "Synthetic handler, no compiler or model invoked")

    server = sdk.build_server("forge-build-mcp", [sdk.Operation("compile", build.CompileIn, handler, "default expansion probe")])
    tool = "mcp__forge_build_mcp__compile"
    sdk.issue_ticket("factory-default-fixture", tool, {"profile": profile}, "swe3-author", "df_author_0", "SWE.3", str(tmp_path))
    # Real MCP registration/call injects defines=[] before sdk.invoke.
    asyncio.run(server.call_tool("compile", {"profile": profile}))
    assert seen == [("swe3-author", "SWE.3", profile, [])]
    asyncio.run(server.call_tool("compile", {"profile": profile}))
    assert len(seen) == 1  # The normalized ticket remains single-use.
    sdk.issue_ticket("factory-default-fixture", tool, {"profile": profile}, "swe3-author", "df_author_0", "SWE.3", str(tmp_path))
    asyncio.run(server.call_tool("compile", {"profile": profile, "defines": ["DIFFERENT=1"]}))
    assert len(seen) == 1  # A nondefault argument never inherits an empty-list ticket.
    asyncio.run(server.call_tool("compile", {"profile": profile, "defines": []}))
    assert len(seen) == 2


@pytest.mark.parametrize("tool,omitted,expanded", [
    ("mcp__forge_build_mcp__compile", {"profile": "host-clang"}, {"profile": "host-clang", "defines": []}),
    ("mcp__forge_knowledge_mcp__propose_lesson", {}, {"tool_versions": {}}),
])
def test_builtin_factory_defaults_hash_identically_but_nondefaults_stay_bound(tool, omitted, expanded):
    assert sdk.args_digest(tool, omitted) == sdk.args_digest(tool, expanded)
    key = "defines" if "defines" in expanded else "tool_versions"
    changed = {**expanded, key: ["DIFFERENT=1"] if key == "defines" else {"compiler": "different"}}
    assert sdk.args_digest(tool, omitted) != sdk.args_digest(tool, changed)


def test_ticket_hashing_never_executes_custom_default_factories(monkeypatch):
    def forbidden_factory():
        raise AssertionError("Argument authentication must not execute custom factories")

    class CustomInput(sdk.ToolInput):
        labels: list[str] = Field(default_factory=forbidden_factory)

    monkeypatch.setattr(sdk, "_op_model", lambda name: CustomInput)
    assert sdk.normalize_args("custom", {"labels": []}) == {"labels": []}
    assert sdk.normalize_args("custom", {}) == {}
