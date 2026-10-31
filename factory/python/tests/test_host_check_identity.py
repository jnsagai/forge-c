"""Assertion IDs remain distinct without regrouping or dropping predicates.

All compiled C below is a deliberately authored synthetic test fixture, never
Qwen output or product qualification evidence.
"""
import json

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import tests as host
from forge_factory.workflow.builder import build


@pytest.mark.parametrize("ids,condition,expected", [
    (("UT-001", "UT-001"), "8U - 3U == 5U", "FAIL"),
    (("UT-001-RESULT", "UT-001-RESULT"), "8U - 3U == 5U", "FAIL"),
    (("UT-001", "UT-001-RESULT"), "8U - 3U == 5U", "PASS"),
    (("UT-001-RESULT", "UT-001-PRESERVED"), "8U - 3U == 5U", "PASS"),
    (("UT-001a", "UT-001a"), "8U - 3U == 5U", "FAIL"),
    (("UT-001", "UT-001a"), "8U - 3U == 5U", "PASS"),
    (("UT-001", "UT-001-RESULT"), "8U - 3U == 0U", "FAIL"),
])
def test_real_host_runner_checks_complete_assertion_ids(tmp_path, monkeypatch, ids, condition, expected):
    ws = tmp_path / "workspace"
    source = ws / "software/tests/unit/test_assertions.c"
    source.parent.mkdir(parents=True)
    # Both independent predicates execute. Only their metadata varies.
    source.write_text(
        '#include <stdio.h>\n'
        '#define CHECK(id, cond) do { if (!(cond)) return 1; puts(id " PASS"); } while (0)\n'
        'int main(void) {\n'
        f' CHECK("{ids[0]}", 3U + 4U == 7U);\n'
        f' CHECK("{ids[1]}", {condition});\n'
        ' return 0;\n}\n')
    for key, value in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws),
                       "FORGE_ROLE": "swe4-author", "FORGE_PHASE": "SWE.4",
                       "FORGE_STATE_DIR": str(tmp_path / "state"),
                       "FORGE_EVENTS_DIR": str(tmp_path / "events")}.items():
        monkeypatch.setenv(key, value)
    operation = next(op for op in host.OPERATIONS if op.name == "run_unit")
    result = sdk.invoke("forge-tests-mcp", operation, {"coverage": False})
    assert result["status"] == expected, result
    if ids[0] == ids[1]:
        assert any(i.startswith("DUPLICATE_TEST_ID:" + ids[0] + ":") for i in result["issues"]), result
    elif expected == "FAIL":
        assert any(i.startswith("TEST_FAIL:") for i in result["issues"]), result
        assert not any(i.startswith("DUPLICATE_TEST_ID:") for i in result["issues"]), result
    else:
        assert not result["issues"], result
    assert json.loads((ws / "build/tests-unit/results.json").read_text())["passed"] == (0 if condition.endswith("0U") else 1)


def test_id_scan_ignores_comments_and_literals_but_retains_cross_file_duplicates(tmp_path):
    first, second = tmp_path / "test_a.c", tmp_path / "test_b.c"
    first.write_text('/* CHECK("UT-001-RESULT", false); */\n'
                     '// CHECK("UT-001-RESULT", false);\n'
                     'const char *s = "CHECK(\\\"UT-001-RESULT\\\", false);";\n'
                     'CHECK("UT-001-RESULT", a == 1U);\n')
    second.write_text('CHECK("UT-001-RESULT", b == 2U);\n'
                      'CHECK("UT-001-PRESERVED", c == 3U);\n')
    assert host.check_ids([first]) == {"UT-001-RESULT": 1}
    assert host.check_ids([first, second]) == {"UT-001-RESULT": 2, "UT-001-PRESERVED": 1}


@pytest.mark.parametrize("layer", ["LL", "HAL"])
def test_native_unit_author_receives_assertion_preserving_metadata_repair_contract(layer):
    graph, _ = build("WO-ASSERTION-IDENTITY-FIXTURE", layer=layer)
    assert "UT-007-RESULT" in graph
    assert "Preserve every existing predicate and its evaluation order" in graph
    assert "do not combine checks" in graph
    assert "same @test" in graph
