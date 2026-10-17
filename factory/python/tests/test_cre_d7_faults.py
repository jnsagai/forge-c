"""CRE-T039 (AT-036): the fault-injection campaign passes every scenario, bounded and model-free, and leaves the
protected inputs byte-identical."""
from forge_factory.reliability import faults as FI


def test_fault_injection_campaign_terminates_safely_in_every_scenario():
    rep = FI.run_campaign()
    failed = [(r["id"], r["detail"]) for r in rep["scenarios"] if r["result"] != "PASS"]
    assert failed == [] and rep["total"] == len(FI.SCENARIOS) >= 18
    assert rep["protected_inputs_sha256"]["unchanged"]
    assert all(r["model_tokens"] == 0 and r["terminal_state"] is not None for r in rep["scenarios"])
    assert {r["id"] for r in rep["scenarios"]} >= {f"F{i:02d}" for i in range(1, 19)}
