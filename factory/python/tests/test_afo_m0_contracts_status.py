"""AFO-T005 (AFO-FR-007, AT-066): runtime contract validation of every record type, and an FR->task->evidence status
that only executed evidence (with a matching log hash) or the blocker register can move off NOT_RUN."""
import hashlib
import json

import pytest
from forge_factory.afo import contracts, status
from forge_factory.common import REPO_ROOT, load_yaml

EX = contracts.CONTRACTS / "examples"
MAP = {"readiness": "operational-readiness"}


@pytest.mark.parametrize("p", sorted(EX.glob("*.example.json")), ids=lambda p: p.name)
def test_every_example_record_validates_and_a_broken_one_does_not(p):
    name = MAP.get(p.name.split(".")[0], p.name.split(".")[0])
    rec = json.loads(p.read_text())
    assert contracts.errors(name, rec) == []
    bad = {**rec, "unexpected_field": 1}
    assert contracts.errors(name, bad), name                       # unknown top-level fields are rejected
    with pytest.raises(contracts.ContractError):
        contracts.require(name, bad)


def test_shipped_policy_and_state_machine():
    assert contracts.errors("afo-policy", load_yaml(REPO_ROOT / "config/factory/afo-policy.yaml")) == []
    f = contracts.fsm()
    assert set(f["order_terminal"]) == {"REJECTED_INTAKE", "READY_FOR_OFFLINE_REVIEW", "BLOCKED"}
    assert "no_ready_without_six_independent_gates" in f["invariants"]
    with pytest.raises(contracts.ContractError):
        contracts.errors("not-a-contract", {})


def test_status_moves_only_on_verified_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(status, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(status, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(status, "BLOCKERS", tmp_path / "blockers.json")
    (tmp_path / "blockers.json").write_text(json.dumps({"AFO-T015": {"status": "BLOCKED", "reason": "reboot drill not authorized"}}))
    for tid, good in (("AFO-T004", True), ("AFO-T006", False)):
        d = tmp_path / "runs" / tid
        d.mkdir(parents=True)
        (d / "x.log").write_text("ok\n")
        h = hashlib.sha256(b"ok\n").hexdigest() if good else "0" * 64
        (d / "latest.json").write_text(json.dumps({"status": "PASS", "exit_code": 0, "log": f"runs/{tid}/x.log",
                                                    "log_sha256": h}))
    rep = status.report()
    t = rep["tasks"]
    assert t["AFO-T004"]["status"] == "PASS" and t["AFO-T006"]["status"] == "FAIL"     # log tampered
    assert t["AFO-T015"]["status"] == "BLOCKED" and t["AFO-T001"]["status"] == "NOT_RUN"
    fr = {r["id"]: r for r in rep["requirements"]}
    assert fr["AFO-FR-003"]["coverage"] == "PARTIAL"                 # T004 PASS, T006 FAIL
    assert len(rep["requirements"]) == 72 and len(t) == 75
