"""EASA M7: assurance inventory in the existing package (T057/T058), safety-scope gating (T059/AT-062), enhanced
assurance blocking only in ENFORCING (AT-060), read-only dashboard view (T056)."""
import json
import shutil
import zipfile

import pytest
from forge_factory.assurance import package as P
from forge_factory.common import data_root

R102 = data_root() / "archives/WO-0002B-STM32N6-RCC-HAL-r102/forge-c-WO-0002B-STM32N6-RCC-HAL-r102-review.zip"
needs_r102 = pytest.mark.skipif(not R102.is_file(), reason="sealed r102 archive not on this host")


def _stage(tmp_path):
    """A copy of the sealed r102 package contents as a packager staging tree (the archive itself is not touched)."""
    x = tmp_path / "x"
    with zipfile.ZipFile(R102) as z:
        z.extractall(x)
    stage = tmp_path / "stage"
    shutil.copytree(x / "evidence", stage)
    for f in ("assurance",):
        shutil.rmtree(stage / f, ignore_errors=True)
    ws = tmp_path / "WO-0002B-STM32N6-RCC-HAL-r102" / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": "deepseek-flash", "provider": "deepseek",
                                                                  "nodes": []}))
    return ws, stage


def _seal(stage, tmp_path, name):
    from forge_factory.release.finalize import POLICY_V05, _packager

    return _packager().build(stage, tmp_path / name, "WO-T", POLICY_V05)


QM = {"scope": {"scope_id": "SC-QM-1", "work_order_id": "WO-0002B-STM32N6-RCC-HAL-r102", "target_asil": "QM",
                "source_requirements_hash": "a" * 64, "hsi_hash": None, "allocation_review_ref": None,
                "product_asil_source": "approved:owner-decision-2026-10-15"},
      "na": {k: {"rationale": "QM development: no safety allocation for this driver (owner decision)",
                 "approved_by": "j.doe", "approved_at": "2026-10-17"} for k in P.SAFETY_FILES}}


@needs_r102
def test_t057_observe_only_bundle_never_changes_status(tmp_path):
    ws, stage = _stage(tmp_path)
    before = _seal(stage, tmp_path, "a")
    s = P.bundle_into(ws, stage, before["package_status"])
    after = _seal(stage, tmp_path, "b")
    assert s["mode"] == "OBSERVE_ONLY" and s["observations_only"] and s["technical_status"] == "PASS"
    assert (before["package_status"], before["gap_count"]) == (after["package_status"], after["gap_count"]) == ("BLOCKED", 2)
    assert s["safety_scope"]["status"] == "NO_APPROVED_SCOPE"
    for f in ("summary.json", "independence.json", "claims.json", "applicability.json", "fidelity.json", "hashes.json"):
        assert (stage / "assurance" / f).is_file()
    assert json.loads((stage / "assurance/independence.json").read_text())["decision"] == "PARTIAL"   # one model
    assert (stage / "configuration/model-profile.json").is_file()                                       # F-06


@needs_r102
def test_at062_qm_documented_na_vs_asil_b_blocked(tmp_path):
    ws, stage = _stage(tmp_path)
    (ws / P.SCOPE_FILE).write_text(json.dumps(QM))
    s = P.bundle_into(ws, stage, "BLOCKED")
    assert s["safety_scope"]["status"] == "SATISFIED"
    assert "NOT APPLICABLE (QM scope)" in (stage / "safety/software_safety_analysis.md").read_text()
    assert _seal(stage, tmp_path, "qm")["package_status"] == "READY_FOR_OFFLINE_REVIEW"
    ws2, stage2 = _stage(tmp_path / "b")
    asil_b = json.loads(json.dumps(QM))
    asil_b["scope"].update(target_asil="B", hsi_hash="b" * 64, allocation_review_ref="TSR-1")
    (ws2 / P.SCOPE_FILE).write_text(json.dumps(asil_b))
    s2 = P.bundle_into(ws2, stage2, "BLOCKED")
    assert s2["safety_scope"]["status"] == "BLOCKED" and not (stage2 / "safety/software_safety_analysis.md").exists()
    assert _seal(stage2, tmp_path / "b", "b")["package_status"] == "BLOCKED"
    agent = json.loads(json.dumps(QM))
    agent["na"]["software_safety_analysis"]["approved_by"] = "agent-swe1"
    ws3, stage3 = _stage(tmp_path / "c")
    (ws3 / P.SCOPE_FILE).write_text(json.dumps(agent))
    assert P.bundle_into(ws3, stage3, "BLOCKED")["safety_scope"]["status"] == "BLOCKED"


@needs_r102
def test_at060_swe_gates_pass_but_enhanced_assurance_missing_blocks_only_when_enforcing(tmp_path, monkeypatch):
    ws, stage = _stage(tmp_path)
    (ws / P.SCOPE_FILE).write_text(json.dumps(QM))
    pol = P._policy()
    monkeypatch.setattr(P, "_policy", lambda: {**pol, "mode": "ENFORCING"})
    s = P.bundle_into(ws, stage, "READY_FOR_OFFLINE_REVIEW")
    assert s["technical_status"] == "PASS" and s["enforced"]
    assert "EASA:CLM-SWE.4:UNSUPPORTED" in s["blocking_findings"]          # no assurance-gate evidence recorded
    res = _seal(stage, tmp_path, "enf")
    assert res["package_status"] == "BLOCKED"
    with zipfile.ZipFile(res["archive"]) as z:
        gaps = json.loads(z.read("missing_artifacts.json"))["gaps"]
    assert any("EASA:CLM-SWE.4:UNSUPPORTED" in g for g in gaps)


def test_t058_phase_claims_separate_technical_and_assurance_status():
    gates = {p: {"decision": "PASS"} for p in P.PHASES}
    log = [{"phase": "SWE.4", "state": "PASS", "requirements": {}}, {"phase": "SWE.5", "state": "FAIL",
                                                                      "requirements": {"FAULT_INJECTION": "FAIL"}}]
    c = {x["phase"]: x for x in P.phase_claims(gates, log)}
    assert c["SWE.4"]["status"] == "SUPPORTED" and c["SWE.5"]["status"] == "CONTESTED"
    assert c["SWE.6"]["status"] == "UNSUPPORTED" and all(x["safety_conclusion"] is None for x in c.values())


def test_t056_dashboard_assurance_view_read_only(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from forge_factory.events.store import EventStore

    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws = tmp_path / "state/workorders/WO-X-r1/workspace"
    (ws / ".forge-run/assurance").mkdir(parents=True)
    (ws / ".forge-run/assurance/gate-log.jsonl").write_text(json.dumps({"phase": "SWE.4", "state": "BLOCKED"}) + "\n")
    (ws / "workproducts/SWE.4/traceability").mkdir(parents=True)
    (ws / "workproducts/SWE.4/traceability/matrix_4_unittest_to_unitspec.csv").write_text("test,file,uspec,result,status\n")
    (ws / "workproducts/SWE.4/traceability/matrix_4_unittest_to_unitspec.md").write_text("Uncovered items: USPEC-HAL-01-01\n")
    from forge_factory.dashboard.app import create_app, tokens

    c = TestClient(create_app(EventStore(), collect=False))
    t = tokens()
    hdr = {"Authorization": f"Bearer {t['viewer'] if 'viewer' in t else next(iter(t.values()))}"}
    s = c.get("/api/v1/assurance/summary", headers=hdr)
    assert s.status_code == 200 and "no ISO 26262" in s.json()["statement"]
    w = c.get("/api/v1/assurance/workorders", headers=hdr).json()["items"]
    assert w == [{"work_order": "WO-X-r1", "assurance_gates": {"SWE.4": "BLOCKED"}, "matrices": 1}]
    d = c.get("/api/v1/assurance/workorders/WO-X-r1", headers=hdr).json()
    assert d["matrices"][0]["uncovered"] == "USPEC-HAL-01-01" and d["independence"]["decision"] in ("UNKNOWN", "PARTIAL")
    assert c.get("/api/v1/assurance/workorders/..%2Fetc", headers=hdr).status_code in (404, 422)
    assert c.post("/api/v1/assurance/summary", headers=hdr).status_code == 405       # read-only
    assert c.get("/api/v1/assurance/summary").status_code == 401
