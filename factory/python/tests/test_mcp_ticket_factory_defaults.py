"""Native MCP default expansion must preserve the authorized logical call."""

import asyncio

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import build, evidence
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


@pytest.mark.parametrize("only_evidence_refs_omitted", [False, True])
def test_native_defect_declaration_keeps_ticket_after_empty_lists_are_injected(tmp_path, monkeypatch, only_evidence_refs_omitted):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("FORGE_BINDING_ID", "defect-default-fixture")
    monkeypatch.delenv("FORGE_MCP_TRUST", raising=False)
    seen = []

    def handler(ctx, args):
        seen.append((ctx.role, ctx.phase, args.kind, args.requirement_ids, args.test_files, args.evidence_refs))
        return sdk.result(ctx, "PASS", "Synthetic declaration, no defect or repair incident created")

    server = sdk.build_server("forge-evidence-mcp", [sdk.Operation("report_defect", evidence.DefectIn, handler, "declaration probe")])
    args = {"kind": "TEST", "summary": "Synthetic test setup correction declaration"}
    if only_evidence_refs_omitted:
        args.update(requirement_ids=["USPEC-01"], test_files=["software/tests/target/test_fixture.c"],
                    requirement_quote="Synthetic setup quote, not an observed repair incident")
    sdk.issue_ticket("defect-default-fixture", "mcp__forge_evidence_mcp__report_defect", args,
                     "swe5-author", "swe5_target_author", "SWE.5", str(tmp_path))
    asyncio.run(server.call_tool("report_defect", args))
    expected_ids = ["USPEC-01"] if only_evidence_refs_omitted else []
    expected_files = ["software/tests/target/test_fixture.c"] if only_evidence_refs_omitted else []
    assert seen == [("swe5-author", "SWE.5", "TEST", expected_ids, expected_files, [])]
