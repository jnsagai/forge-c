"""CAPA-089 (runs WO-F014-SWE2-CRCK-20261101-01 -> WO-F014-SWE3-CRCK-20261101-01): a brownfield SWE.2 call contract is
compiled against the delivered header at the SWE.2 freeze; at SWE.3 a compile finding on that carried SWE.2 file tells
the author to report an ARCHITECTURE defect instead of editing it."""
from __future__ import annotations

import json

from forge_factory.assurance import register_contract as RC
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.layer import REGISTER_CONTRACT

REPLY = json.dumps({"status": "PASS", "artifacts": [], "issues": [], "next_action": "next"})


def _ws(tmp_path, monkeypatch, delivery: bool):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws = tmp_path / "WO-T/workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    m = {"work_order": "WO-T", "layer": "LL", "peripheral": "crc", "register_contract": REGISTER_CONTRACT}
    if delivery:
        m |= {"delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis"}},
              "delivered": [{"path": "software/ll/stm32n6xx_ll_crc.h", "role": "delivered_code"}]}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    return ws


def _issues(ws, phase):
    log = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    return [e for e in log if e.get("step") == "author" and e.get("phase") == phase][-1]["issues"]


def test_swe2_compiles_the_call_contract_only_when_the_delivered_code_exists(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(RC, "check_calls", lambda ws: [])
    monkeypatch.setattr(RC, "check_compiles", lambda ws, inc, hdr: seen.append(hdr) or
                        ["CONTRACT_CALL_DOES_NOT_COMPILE:workproducts/SWE.2/api_calls.json:'CRC_Instance' undeclared"])
    ws = _ws(tmp_path, monkeypatch, delivery=True)
    gate.step_author(Store(ws), "SWE.2", REPLY)
    assert any(i.startswith("CONTRACT_CALL_DOES_NOT_COMPILE") for i in _issues(ws, "SWE.2")) and seen
    seen.clear()
    green = _ws(tmp_path / "g", monkeypatch, delivery=False)  # greenfield: no header before SWE.3, check stays there
    gate.step_author(Store(green), "SWE.2", REPLY)
    assert seen == [] and not any(i.startswith("CONTRACT_CALL") for i in _issues(green, "SWE.2"))


def test_swe3_tells_the_author_to_report_the_upstream_contract_instead_of_editing_it(tmp_path, monkeypatch):
    monkeypatch.setattr(RC, "check_compiles", lambda ws, inc, hdr:
                        ["CONTRACT_CALL_DOES_NOT_COMPILE:workproducts/SWE.2/api_calls.json:'CRC_Instance' undeclared"])
    ws = _ws(tmp_path, monkeypatch, delivery=True)
    gate.step_author(Store(ws), "SWE.3", REPLY)
    hit = [i for i in _issues(ws, "SWE.3") if i.startswith("CONTRACT_CALL_DOES_NOT_COMPILE")]
    assert hit and "report_defect kind ARCHITECTURE" in hit[0] and "instead of editing it" in hit[0]
