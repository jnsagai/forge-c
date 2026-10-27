"""Feature 016 OB-T061: a recovery plan cannot rework a FROZEN delivery's code, answer a gate demand for a
delivered-code output, or rework a phase whose failing tests reproduce escalated delivered-code defects (only the
owner's disposition changes that). Fixtures are the CRC HAL shake-down's real plans and gate records."""
import json

from forge_factory.afo import recovery as R

LL_PLAN = {"strategy": "REWORK_LOCAL", "artifact_scope": ["software/ll", "workproducts/SWE.3"]}
BUNDLE = {"phase": "SWE.3"}


def _ws(tmp_path, mode="FROZEN", gate=None, defects=()):
    ws = tmp_path / "ws"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"delivery": {"build": {}}, "code_mode": mode}))
    if gate:
        (ws / ".forge-run/gates/gate-log.jsonl").write_text(json.dumps(gate) + "\n")
    (ws / ".forge-run/defects").mkdir()
    for d in defects:
        (ws / f".forge-run/defects/{d['id']}.json").write_text(json.dumps(d))
    return ws


def test_rework_of_frozen_code_and_style_outputs_is_refused(tmp_path):
    gate = {"gate": {"decision": "BLOCKED", "phase": "SWE.3", "reason": "STUCK: identical deterministic rejection "
                     "twice (MISSING_REQUIRED_OUTPUT:software/ll/*.h); stopped early"}, "phase": "SWE.3"}
    issues = R.frozen_issues(LL_PLAN, BUNDLE, _ws(tmp_path, gate=gate))
    assert "FROZEN_CODE_SCOPE:software/ll" in issues and "STYLE_OUTPUT:software/ll/*.h" in issues


def test_rework_of_tests_that_reproduce_escalated_frozen_defects_is_refused(tmp_path):
    gate = {"gate": {"decision": "BLOCKED", "phase": "SWE.4", "reason": "STUCK: identical deterministic rejection twice "
                     "(REQUIRED_TOOL_NOT_PASS:run_unit:FAIL, UT:SPEC_NOT_VERIFIED:USPEC-HAL-01-03)"}, "phase": "SWE.4"}
    d = {"id": "DEF-003", "kind": "CODE", "status": "ESCALATED", "detected_phase": "SWE.4",
         "target_kind": "DELIVERED_CODE"}
    plan = {"strategy": "REWORK_LOCAL", "artifact_scope": ["workproducts/SWE.4", "software/tests/unit"]}
    assert R.frozen_issues(plan, {"phase": "SWE.4"}, _ws(tmp_path, gate=gate, defects=[d])) == \
        ["FROZEN_DEFECTS_NEED_OWNER:DEF-003"]


def test_fix_allowed_closing_and_greenfield_are_unaffected(tmp_path):
    gate = {"gate": {"decision": "BLOCKED", "phase": "SWE.3", "reason": "MISSING_REQUIRED_OUTPUT:software/ll/*.h"},
            "phase": "SWE.3"}
    assert R.frozen_issues(LL_PLAN, BUNDLE, _ws(tmp_path / "a", mode="FIX_ALLOWED", gate=gate)) == []
    assert R.frozen_issues({**LL_PLAN, "strategy": "CLOSE_BLOCKED"}, BUNDLE, _ws(tmp_path / "b", gate=gate)) == []
    assert R.frozen_issues(LL_PLAN, BUNDLE, None) == []
