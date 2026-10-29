"""The schema actually served by MCP must carry the constraints the broker enforces."""
import asyncio
from typing import Literal

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import maintainer
from pydantic import Field


def schemas(server):
    return {t.name: t.input_schema for t in asyncio.run(server.list_tools())}


def test_actual_maintenance_schema_exposes_submission_and_page_limits():
    tools = schemas(sdk.build_server("forge-maintainer-mcp", maintainer.OPERATIONS))
    fields = tools["submit_candidate"]["properties"]
    for name, bounds in {"summary": (10, 300), "reproducer": (10, 200), "symptom_signature": (8, 160)}.items():
        assert (fields[name].get("minLength"), fields[name].get("maxLength")) == bounds
    offset = tools["read_source"]["properties"]["offset"]
    assert offset["minimum"] == 0 and offset["maximum"] == 4 * 1024 * 1024 and offset["default"] == 0
    assert tools["run_candidate_tests"]["properties"]["tests"]["maxItems"] == 5


def test_native_call_rejects_overlong_summary_before_broker_without_clipping(monkeypatch):
    calls = []
    monkeypatch.setattr(sdk, "invoke", lambda server, op, args: calls.append(args) or {"status": "PASS"})
    server = sdk.build_server("forge-maintainer-mcp", maintainer.OPERATIONS)
    args = {"summary": "x" * 301, "reproducer": "factory/python/tests/afo_candidate/repro.py", "symptom_signature": "reproduction"}
    with pytest.raises(Exception, match="300|string_too_long"):
        asyncio.run(server.call_tool("submit_candidate", args))
    assert calls == []
    args["summary"] = "x" * 300
    asyncio.run(server.call_tool("submit_candidate", args))
    assert calls == [args]


class Item(sdk.ToolInput):
    name: str = Field(min_length=2, pattern="^[a-z]+$", description="Lowercase item name")


class RichInput(sdk.ToolInput):
    items: list[Item] = Field(min_length=1, max_length=3)
    mode: Literal["one", "two"] = "one"
    note: str | None = Field(default=None, max_length=5, description="Optional short note")
    labels: list[str] = Field(default_factory=list, max_length=4)


def test_nested_constraints_descriptions_optional_values_and_factories_survive_registration(monkeypatch):
    calls = []
    monkeypatch.setattr(sdk, "invoke", lambda server, op, args: calls.append(args) or {"status": "PASS"})
    server = sdk.build_server("test-schema", [sdk.Operation("rich", RichInput, lambda *a: {}, "metadata probe")])
    schema = schemas(server)["rich"]
    assert schema["properties"]["items"]["maxItems"] == 3
    assert schema["$defs"]["Item"]["properties"]["name"]["pattern"] == "^[a-z]+$"
    assert schema["$defs"]["Item"]["properties"]["name"]["description"] == "Lowercase item name"
    assert schema["properties"]["note"]["description"] == "Optional short note"
    assert schema["properties"]["mode"]["enum"] == ["one", "two"]
    for _ in range(2):
        asyncio.run(server.call_tool("rich", {"items": [{"name": "ok"}]}))
    assert calls[0]["labels"] == calls[1]["labels"] == []
    assert calls[0]["labels"] is not calls[1]["labels"]
