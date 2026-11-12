"""A verifier refusal cannot authorize dropping explicitly requested register fields."""
import json

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import swe1
from forge_factory.lrtx import swe1_semantic as semantic


def workspace(tmp_path, scope=None, peripheral="crc"):
    spec = json.loads((REPO_ROOT / "examples/0014c-st-cube-crc/workorder.json").read_text())
    ws = tmp_path / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({
        "peripheral": peripheral, "layer": "LL", "scope": spec["scope"] if scope is None else scope,
    }))
    return ws


def group(register="CRC_CR", fields=("REV_OUT", "RTYPE_OUT", "RTYPE_IN")):
    return {"id": register, "register": register, "fields": dict.fromkeys(fields, {}), "pages": []}


def excluded_doc(g, qualified=True):
    return {"intents": [], "requirements": [], "open_points": [],
            "not_covered": [{"field": f"{g['register']}.{f}" if qualified else f,
                             "reason": "verifier does not model the other field's write effect"}
                            for f in g["fields"]]}


def findings(lane, ws, doc, g):
    if lane == "semantic":
        return semantic.local_checks(ws, doc, g)
    return swe1.validate_group(ws, doc, g, "CRC LL driver", {})


@pytest.mark.parametrize("lane", ["semantic", "legacy"])
@pytest.mark.parametrize("qualified", [True, False])
def test_real_crc_scope_cannot_be_shrunk_after_tool_refusal(tmp_path, lane, qualified):
    ws = workspace(tmp_path)
    g = group()
    errors = findings(lane, ws, excluded_doc(g, qualified), g)
    for field in ["CRC_CR.REV_OUT", "CRC_CR.RTYPE_OUT", "CRC_CR.RTYPE_IN"]:
        assert any("REQUIRED_SCOPE_FIELD_EXCLUDED:" + field in e for e in errors), errors


@pytest.mark.parametrize("lane", ["semantic", "legacy"])
def test_explicit_owner_exclusion_remains_available(tmp_path, lane):
    ws = workspace(tmp_path, ["Query CRC_DR.DR.", "Out of scope: CRC_CR.REV_OUT."])
    g = group(fields=("REV_OUT",))
    assert findings(lane, ws, excluded_doc(g), g) == []


@pytest.mark.parametrize("lane", ["semantic", "legacy"])
def test_rule_uses_the_existing_peripheral_and_exact_field_identity(tmp_path, lane):
    ws = workspace(tmp_path, ["Set IWDG_PR.PR as requested.", "Out of scope: IWDG_WINR.WIN."], "iwdg")
    g = group("IWDG_PR", ("PR",))
    assert any("REQUIRED_SCOPE_FIELD_EXCLUDED:IWDG_PR.PR" in e for e in findings(lane, ws, excluded_doc(g), g))


@pytest.mark.parametrize("lane", ["semantic", "legacy"])
def test_unmentioned_field_is_not_invented_as_a_new_requirement(tmp_path, lane):
    ws = workspace(tmp_path, ["Set CRC_CR.REV_OUT_EXTRA in the caller's separate contract."])
    g = group(fields=("REV_OUT",))
    assert findings(lane, ws, excluded_doc(g), g) == []
