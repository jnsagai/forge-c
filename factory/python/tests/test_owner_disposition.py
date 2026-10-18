"""Owner disposition OD-2026-10-18-01 (r136 DEF-005): an INPUT issue the owner already decided is recorded as
DISPOSITIONED (not escalated again, not a package gap); only a human-approved disposition reaches a work order and
its limitation is stated in the package."""
import json

from forge_factory.inspection import defects

REQS = ("- **SWR-015** While no oscillator enable has been requested after reset, the RCC driver shall leave "
        "RCC_CR.HSION at its reset value 1.\n- **SWR-003** When the HSE enable is requested, the RCC driver shall set "
        "RCC_CR.HSEON.\n")
OD = [{"id": "OD-1", "requirement_text_regex": r"RCC_CR\.HSION\b.*\breset value\b",
       "disposition": "VERIFIED_AGAINST_DOCUMENTED_RESET_VALUE_ONLY", "limitation": "documented reset value only",
       "approved_by": "Jefferson Nascimento", "approved_at": "2026-10-18"}]


def _ws(tmp_path, ods=OD):
    ws = tmp_path / "WO" / "workspace"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
    (ws / ".forge-run").mkdir(parents=True)
    if ods is not None:
        (ws / defects.DISPOSITIONS).write_text(json.dumps(ods))
    return ws


def _input(ws, rid):
    return defects.report(ws, detected_phase="SWE.6", reported_by="swe6-author", kind="INPUT",
                          summary="the Renode model does not show the reset value", requirement_ids=[rid],
                          test_files=[], evidence_refs=[])


def test_settled_input_issue_is_dispositioned_not_a_gap(tmp_path):
    ws = _ws(tmp_path)
    d = _input(ws, "SWR-015")
    assert d["status"] == "DISPOSITIONED" and d["history"][-1]["disposition"] == "OD-1"
    assert defects.gaps(ws) == []


def test_other_input_issues_still_escalate(tmp_path):
    ws = _ws(tmp_path)
    assert _input(ws, "SWR-003")["status"] == "ESCALATED"
    assert defects.gaps(ws) == ["escalated_defect:DEF-001:INPUT"]
    ws2 = _ws(tmp_path / "b", ods=None)
    assert _input(ws2, "SWR-015")["status"] == "ESCALATED"           # no disposition recorded: escalate


def test_only_human_approved_dispositions_reach_a_work_order(tmp_path):
    import pytest
    from forge_factory.common import REPO_ROOT
    from forge_factory.workorder import owner_dispositions_for

    assert [d["id"] for d in owner_dispositions_for("0002b-arm_55_rcc_hal")] == ["OD-2026-10-18-01"]
    assert owner_dispositions_for("0002-arm_55_rcc_st") == []
    cfg = tmp_path / "config/factory"
    cfg.mkdir(parents=True)
    (cfg / "verification-dispositions.yaml").write_text(
        "dispositions:\n  - id: OD-X\n    examples: [0002a-arm_55_rcc_ll]\n    requirement_text_regex: x\n"
        "    disposition: D\n    limitation: L\n    approved_by: 'agent:swe6-author'\n    approved_at: '2026-10-18'\n")
    with pytest.raises(ValueError, match="OWNER_DISPOSITION_NOT_HUMAN_APPROVED"):
        owner_dispositions_for("0002a-arm_55_rcc_ll", repo=tmp_path)
    assert REPO_ROOT.is_dir()


def test_package_states_the_disposition_as_a_limitation(tmp_path):
    import pytest
    from test_easa_m7 import R102, _stage

    if not R102.is_file():
        pytest.skip("sealed r102 archive not on this host")
    from forge_factory.assurance import package as P

    ws, stage = _stage(tmp_path)
    (ws / defects.DISPOSITIONS).write_text(json.dumps(OD))
    P.bundle_into(ws, stage, "BLOCKED")
    lim = json.loads((stage / "assurance/fidelity.json").read_text())["limitations"]
    assert any(x.startswith("OWNER_DISPOSITION OD-1 (Jefferson Nascimento, 2026-10-18): documented reset value only")
               and x.endswith("[not invoked in this run]") for x in lim)
    assert "OWNER_DISPOSITION OD-1" in (stage / "assurance/ASSURANCE-CASE.md").read_text()
