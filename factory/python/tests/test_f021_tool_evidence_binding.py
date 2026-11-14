"""Feature 021 T014 (FR-007): tool evidence is bound to the code it ran on. A verification tool's record carries the
SWE.3 content hash; a PASS older than the current code baseline still counts when that hash equals the baseline's
(the code is unchanged, e.g. a re-freeze after a document-only rework), and is stale otherwise. Records without the
hash keep the timestamp rule (ADR-0008)."""
import json

from forge_factory.inspection.engine import Store
from test_loopbacks import tool, ws  # noqa: F401 - workspace fixture and tool-record helper
from test_lrtx_tool_accounting import mission  # noqa: F401 - unit-test mission workspace


def _baseline(s, h):
    s.base.joinpath("SWE.3").mkdir(parents=True, exist_ok=True)
    s.base.joinpath("SWE.3/BL-SWE.3-001.json").write_text(json.dumps(
        {"baseline_id": "BL-SWE.3-001", "phase": "SWE.3", "baseline_hash": h, "files": [], "upstream": {},
         "frozen_at": "2026-10-15T09:00:00Z", "author_role": "swe3-author"}))


def _bound(ws, code_sha, **extra):  # noqa: F811
    p = ws / "evidence/tool-results.jsonl"
    with p.open("a") as f:
        f.write(json.dumps({"ts_utc": "2000-01-01T00:00:00Z", "phase": "SWE.4", "op": "run_unit",
                            "server": "forge-tests-mcp", "code_sha": code_sha, **extra,
                            "result": {"status": "PASS", "issues": [], "summary": "run_unit"}}) + "\n")


def test_an_older_pass_on_the_frozen_code_stays_current(ws):  # noqa: F811
    s = Store(ws)
    _baseline(s, s.current_hash("SWE.3"))
    (ws / "evidence").mkdir(exist_ok=True)
    _bound(ws, s.current_hash("SWE.3"))
    assert not [m for m in s.missing_outputs("SWE.4") if "run_unit" in m]


def test_an_older_pass_on_other_code_or_without_a_hash_is_stale(ws):  # noqa: F811
    s = Store(ws)
    _baseline(s, s.current_hash("SWE.3"))
    (ws / "evidence").mkdir(exist_ok=True)
    _bound(ws, "0" * 64)
    assert "REQUIRED_TOOL_STALE:run_unit:before BL-SWE.3-001" in s.missing_outputs("SWE.4")
    tool(ws, "SWE.4", "run_unit", "PASS", ts="2000-01-01T00:00:00Z")  # legacy record: no code hash
    assert "REQUIRED_TOOL_STALE:run_unit:before BL-SWE.3-001" in s.missing_outputs("SWE.4")


def test_the_sdk_records_the_code_hash_of_a_verification_tool(mission, monkeypatch):  # noqa: F811
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import tests as operations

    monkeypatch.setenv("FORGE_MCP_TRUST", "env")  # SDK test authorization fixture, never a production profile
    monkeypatch.setenv("FORGE_ROLE", "swe4-author")
    monkeypatch.setenv("FORGE_PHASE", "SWE.4")
    monkeypatch.setenv("FORGE_WORKSPACE", str(mission.ws))
    op = next(o for o in operations.OPERATIONS if o.name == "run_unit")
    sdk.invoke("forge-tests-mcp", op, {})
    rec = json.loads((mission.ws / "evidence/tool-results.jsonl").read_text().splitlines()[-1])
    assert rec["op"] == "run_unit" and rec["code_sha"] == Store(mission.ws).current_hash("SWE.3")
    from forge_factory.inspection.engine import tool_image
    assert rec["tool_image"] == tool_image()


def test_a_pass_on_the_frozen_code_but_another_tool_image_is_stale(ws):  # noqa: F811
    from forge_factory.inspection.engine import tool_image

    s = Store(ws)
    _baseline(s, s.current_hash("SWE.3"))
    (ws / "evidence").mkdir(exist_ok=True)
    _bound(ws, s.current_hash("SWE.3"), tool_image="0" * 64)
    assert "REQUIRED_TOOL_STALE:run_unit:before BL-SWE.3-001" in s.missing_outputs("SWE.4")
    _bound(ws, s.current_hash("SWE.3"), tool_image=tool_image())
    assert not [m for m in s.missing_outputs("SWE.4") if "run_unit" in m]
