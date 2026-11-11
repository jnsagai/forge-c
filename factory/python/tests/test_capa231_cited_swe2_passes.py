"""CAPA-231 (owner SWE.2 review 2026-11-11): the inspector's flat verdict string recorded only the baseline record as
evidence, so a PASS that examined nothing looked like one that read everything (WWDG HAL L35 passed with 0 findings
and flawed views). At SWE.2 every PASS of an item no tool decides cites the baseline file(s), with the section, the
inspector examined: ID=PASS[<file>#<section>, ...]. A PASS without such a citation, or citing a file outside the
baseline, is not recorded and the inspector resubmits; FAIL and tool-decided items are unchanged."""
from __future__ import annotations

import json

import pytest
from forge_factory.inspection.engine import Store
from forge_factory.inspection import gate
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import evidence as E
from forge_factory.workflow import prompts

ITEMS = [f"SWE2-{i:02d}" for i in range(1, 10)]
DET = {"SWE2-07", "SWE2-08", "SWE2-09"}
ARCH = "workproducts/SWE.2/software_architecture.md"


@pytest.fixture()
def st(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-T-231", "layer": "HAL", "scope": [],
                                                             "created_at": "2026-11-11T00:00:00Z", "target": {},
                                                             "budgets": {}}))
    for rel, text in {"workproducts/SWE.1/software_requirements.md": "- **SWR-001** x\n", ARCH: "# a\n"}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    monkeypatch.setattr(Store, "deterministic_items", lambda self, phase, checklist: {
        i: {"verdict": "PASS", "evidence_refs": ["d.json"], "findings": [], "source": "deterministic"} for i in DET})
    s = Store(ws)
    for ph in ("SWE.1", "SWE.2"):
        bl = s.freeze(ph, f"swe{ph[-1]}-author")
    gate._state(ws, "SWE.2", {"step": "author", "result": "FROZEN", "baseline_id": bl["baseline_id"]})
    return s


def _submit(st, text):
    ctx = sdk.ToolContext("forge-evidence-mcp", "check_inspection", "swe2-inspector", "SWE.2", st.workspace, "r")
    return E.check_inspection(ctx, E.InspectIn(phase="SWE.2", baseline_id=st.latest_baseline("SWE.2")["baseline_id"],
                                               verdicts=text))


def test_cited_passes_parse_into_evidence_refs():
    v = E.parse_verdict_string(f"SWE2-01=PASS[{ARCH}#Interfaces, {ARCH}#Components]; SWE2-02=FAIL:no RMW section")
    assert v["SWE2-01"] == {"verdict": "PASS", "evidence_refs": [f"{ARCH}#Interfaces", f"{ARCH}#Components"],
                            "findings": []}
    assert v["SWE2-02"]["verdict"] == "FAIL" and v["SWE2-02"]["findings"] == ["no RMW section"]


def test_an_uncited_swe2_pass_is_not_recorded(st):
    out = _submit(st, "; ".join(f"{i}=PASS" for i in ITEMS))
    assert out["status"] == "FAIL" and "UNCITED_PASS:SWE2-01" in out["issues"]
    assert not list((st.workspace / "inspection/SWE.2").glob("INS-*.json"))


def test_a_pass_citing_a_file_outside_the_baseline_is_not_recorded(st):
    text = "; ".join(f"{i}=PASS[workproducts/SWE.2/other.md#X]" for i in ITEMS)
    assert "UNCITED_PASS:SWE2-03" in _submit(st, text)["issues"]


def test_cited_passes_and_fails_are_recorded(st):
    text = "; ".join(f"{i}=FAIL:no concurrency section" if i == "SWE2-03" else f"{i}=PASS[{ARCH}#Interfaces]"
                     for i in ITEMS)
    out = _submit(st, text)
    rec = json.loads(next((st.workspace / "inspection/SWE.2").glob("INS-*.json")).read_text())
    assert rec["items"]["SWE2-01"]["evidence_refs"] == [f"{ARCH}#Interfaces"] and out["status"] == "FAIL"
    assert rec["items"]["SWE2-03"]["verdict"] == "FAIL"


def test_the_swe2_inspector_is_told_to_cite():
    text = prompts.inspector_prompt("SWE.2")
    assert "=PASS[workproducts/SWE.2/software_architecture.md#" in text and "is not recorded" in text
    assert "=PASS[" not in prompts.inspector_prompt("SWE.3")
