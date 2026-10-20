"""CAPA-057 (b006 DEF-002): validate_artifact (hal_guideline | register_map | implementation | swe3_all) answers a
delivery with the v0.4-brownfield checks: delivered-code findings are recorded for the owner, not author failures."""
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import docs as D
from test_brownfield_pilot import _contract, ws  # noqa: F401 - pytest fixture
from test_brownfield_pilot import pytestmark as pilot_mark


def _validate(ws, check):  # noqa: F811
    return D.validate_artifact(sdk.ToolContext("forge-docs-mcp", "validate_artifact", "swe3-author", "SWE.3", ws, "r"),
                               D.ValidateIn(path="workproducts/SWE.3/detailed_design.md", check=check))


@pilot_mark
def test_capa057_st_delivery_swe3_all_passes_with_recorded_findings(ws):  # noqa: F811
    _contract(ws)
    r = _validate(ws, "swe3_all")
    assert r["status"] == "PASS", r
    assert r["metrics"]["blocking"] == 0 and r["metrics"]["recorded_findings"] >= 5
    assert all(i.startswith("DELIVERED_FINDING(recorded for the owner):") for i in r["issues"])
    assert not any("NO_REGISTER_DEFINES" in i or "LL_NOT_STATIC_INLINE" in i for i in r["issues"])
    assert _validate(ws, "register_map")["status"] == "PASS"  # 14 CMSIS probes match RM0486
