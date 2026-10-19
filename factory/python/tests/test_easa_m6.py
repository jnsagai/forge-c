"""EASA M6: environment fidelity (AT-049/054/055), Renode raw outcome validation (AT-052), requirement observation
(AT-053/081), integration categories and fault injection (T048/T049), back-to-back applicability (AT-050)."""
from forge_factory.assurance import target as T

RIG = {"rig_id": "HIL-01", "probe_tool": "openocd", "probe_version": "0.12", "board_serial": "N6-DK-0042",
       "operator": "j.doe"}


def _raw(blocks):
    lines = ["Renode, version 1.17.0"]
    for p, f, ids in blocks:
        lines += [f"0x{T.MAGIC:08X}", f"0x{p:08X}", f"0x{f:08X}", "0x00000001"] + [f"0x{i:08X}" for i in ids] + \
            ["0x00000000"] * (8 - len(ids))
    return "\n".join(lines) + "\n"


def test_at049_at055_renode_declared_hil_rejected_and_logged_renode():
    assert T.environment_of("run_renode") == "RENODE"
    assert T.check_claim("HIL", "run_renode") == ["FIDELITY_ESCALATION:HIL claimed for RENODE evidence (run_renode)"]
    assert T.check_claim("RENODE", "run_renode") == [] and T.check_claim("HOST", "run_renode") == []
    rec = T.fidelity_record("renode-1.17", "RENODE", "STM32N657X0", "Renode v1.17.0", ["raw:abc"], ["behavioural"])
    assert rec["physical_hardware_verified"] is False and rec["schema_issues"] == []


def test_at054_simulator_report_as_physical_needs_rig_provenance():
    assert T.check_claim("PHYSICAL", "run_robot")[0].startswith("FIDELITY_ESCALATION:PHYSICAL")
    assert T.check_claim("PHYSICAL", "run_robot", rig={**RIG, "operator": "agent-swe6"})[0].startswith("FIDELITY")
    # even with a valid rig record, observations produced by the simulator are not rig observations
    assert "rig observations must come from the rig" in T.check_claim("HIL", "run_renode", rig=RIG)[0]
    assert T.fidelity_record("hil-01", "HIL", "STM32N657X0", None, ["rig:obs1"], [], rig=RIG)["physical_hardware_verified"]
    assert not T.fidelity_record("hil-01", "HIL", "STM32N657X0", None, [], [], rig=None)["physical_hardware_verified"]


def test_at052_renode_counts_must_be_derivable_from_raw():
    res = {"status": "PASS", "metrics": {"passed": 46, "failed": 0}}
    raw = _raw([(34, 0, []), (12, 0, [])])
    assert T.validate_renode(res, raw) == ["LIMITATION:PER_CHECK_PASS_IDS_NOT_RECORDED (requirement observation via "
                                           "TCHECK is inferred)"]
    assert T.validate_renode(res, "no mailbox here") == ["RENODE_RAW_HAS_NO_RESULTS"]
    f = T.validate_renode({**res, "metrics": {"passed": 50, "failed": 0}}, raw)
    assert f[0] == "RENODE_COUNTS_NOT_IN_RAW:claimed 50/0 raw 46/0"
    f2 = T.validate_renode({"status": "PASS", "metrics": {"passed": 33, "failed": 1}}, _raw([(33, 1, [7])]))
    assert "RENODE_PASS_CONTRADICTED_BY_RAW" in f2
    assert T.renode_from_raw(_raw([(33, 1, [7])]))[0]["failed_ids"] == [7]


SUITE = """*** Test Cases ***
SWR-001
    [Tags]    SWR-001
    Run Target Scenario    scn_osc.c
    Target Check Should Pass    1

SWR-002
    [Tags]    SWR-002
    Run Target Scenario    scn_osc.c
    Log    looks fine

SWR-003
    [Tags]    SWR-003
    Run Target Scenario    scn_osc.c
    Target Check Should Pass    9

SWR-004
    [Tags]    SWR-004
    Driver Flash Size Should Be At Most    4096
"""
SCN = {"scn_osc.c": "TCHECK(1, (regs[0] & 8U) != 0U);\nTCHECK(2, st == HAL_OK);\n"}


def test_at053_at081_tagged_test_without_observing_assertion_is_unverified():
    rob = {f"SWR-00{i}": {"status": "PASS", "tags": [f"SWR-00{i}"]} for i in range(1, 5)}
    r = T.requirement_observation(["SWR-001", "SWR-002", "SWR-003", "SWR-004", "SWR-005"], SUITE, SCN, rob, set())
    assert r["requirements"] == {"SWR-001": "VERIFIED:INFERRED_FROM_AGGREGATE",
                                 "SWR-002": "UNVERIFIED:no observing assertion",
                                 "SWR-003": "UNVERIFIED:asserted check absent from scenario",
                                 "SWR-004": "VERIFIED:measured resource assertion", "SWR-005": "UNVERIFIED:no test"}
    assert (r["verified"], r["total"]) == (2, 5)      # never 100% from tags or file names
    failed = T.requirement_observation(["SWR-001"], SUITE, SCN, rob, {1})
    assert failed["requirements"]["SWR-001"] == "UNVERIFIED:asserted check failed"


def test_t048_integration_categories_and_vacuous_checks():
    t = {"it.c": "/** @verifies IF-01 */\nst = HAL_RCC_HSI_Enable(HAL_RCC_TIMEOUT_VALUE + 1U);\nCHECK(st == HAL_ERROR);\n"}
    assert T.integration_categories(t, {"measure_elf", "stack_usage"})["missing"] == []
    assert T.integration_categories(t, {"measure_elf"})["missing"] == ["resource"]
    assert T.vacuous_checks({"a.c": "TCHECK(3, 1);\nTCHECK(4, (r & 8U) != 0U);\nTCHECK(5, 1U);\n"}) == [
        "VACUOUS_CHECK:a.c:TCHECK 3", "VACUOUS_CHECK:a.c:TCHECK 5"]


def test_t049_fault_classes_injected_or_not_supported(tmp_path):
    st = T.fault_injection_status(tmp_path, [tmp_path / "test_rcc_target_timeout.c"])
    assert st["ready_flag_never_set (timeout)"] == "INJECTED"
    assert st["interrupt / preemption during read-modify-write"].startswith("NOT_SUPPORTED")
    assert T.fault_injection_status(tmp_path, [])["ready_flag_never_set (timeout)"] == "NOT_RUN"


def test_at050_b2b_documented_inapplicable_without_model(tmp_path):
    from forge_factory.assurance import contracts

    d = T.b2b_applicability(tmp_path, "WO-1")
    assert d["decision"] == "NOT_APPLICABLE_WITH_RATIONALE" and contracts.errors("method-applicability", d) == []
    (tmp_path / "plant.slx").write_bytes(b"x")
    assert T.b2b_applicability(tmp_path, "WO-1")["decision"] == "APPLICABLE"
