"""CAPA-236 (owner 2026-11-11, "Narrow guard"): the SWE.2 continuation of WWDG LL L44F (ST delivered code, SWE.1 passed on
2026-11-09) was refused RESUME_CONTRACT_OR_RUNTIME_CHANGED: its resume identity pins the whole factory code, checklists,
config, skills and host tools of the SWE.1 run, and the factory (and the host JDK) changed since; the factory revision
check refuses every deploy too. A continuation that carries only SWE.1/SWE.2 now accepts a runtime/revision change when
the contract, limits, inputs and configuration are unchanged and the new revision is clean; the change is recorded.
Carrying SWE.3+ keeps the strict rule."""
import pytest
from forge_factory.brownfield import resume as R

RT_A = {"factory_assets_sha256": "a" * 64, "tools": {"java": {"path": "/j", "sha256": "1" * 64}, "gcc": "ABSENT"},
        "python": "3.13", "packages": {"x": "1"}, "build_environment": {"CC": None}}
RT_B = {**RT_A, "factory_assets_sha256": "b" * 64, "tools": {"java": {"path": "/j", "sha256": "2" * 64}, "gcc": "ABSENT"}}
ID = {"schema": "s", "contract_sha256": "c" * 64, "limits": {"max_attempts": 3}, "runtime": RT_A}
OLD, NEW = {"commit": "1" * 40, "dirty": False}, {"commit": "2" * 40, "dirty": False}


def test_an_unchanged_runtime_and_revision_is_no_change():
    assert R.runtime_change(ID, dict(ID), OLD, dict(OLD)) is None


def test_a_runtime_and_revision_change_is_recorded():
    ch = R.runtime_change(ID, {**ID, "runtime": RT_B}, OLD, NEW)
    assert ch["from_revision"] == OLD["commit"] and ch["to_revision"] == NEW["commit"]
    assert ch["factory_assets_sha256"] == ["a" * 64, "b" * 64] and list(ch["tools_changed"]) == ["java"]
    assert ch["runtime_changed"] is True and "CAPA-236" in ch["rule"]
    assert R.runtime_change(ID, dict(ID), OLD, NEW)["runtime_changed"] is False  # a deploy with the same runtime


def test_a_contract_limit_or_dirty_change_is_still_refused():
    with pytest.raises(R.ResumeRefused, match="RESUME_CONTRACT_OR_RUNTIME_CHANGED"):
        R.runtime_change(ID, {**ID, "runtime": RT_B, "limits": {"max_attempts": 4}}, OLD, NEW)
    with pytest.raises(R.ResumeRefused, match="RESUME_CONTRACT_OR_RUNTIME_CHANGED"):
        R.runtime_change(ID, {**ID, "contract_sha256": "d" * 64}, OLD, NEW)
    for rev in ({"commit": "2" * 40, "dirty": True}, {"commit": "UNKNOWN", "dirty": False}, {}):
        with pytest.raises(R.ResumeRefused, match="RESUME_FACTORY_REVISION_CHANGED_OR_DIRTY"):
            R.runtime_change(ID, {**ID, "runtime": RT_B}, OLD, rev)


def test_only_requirement_and_architecture_phases_may_be_carried_across_a_change():
    ch = R.runtime_change(ID, {**ID, "runtime": RT_B}, OLD, NEW)
    R.carry_across_change(ch, ["SWE.1"])
    R.carry_across_change(ch, ["SWE.1", "SWE.2"])
    R.carry_across_change(ch, [])
    R.carry_across_change(None, ["SWE.1", "SWE.2", "SWE.3"])          # no change: nothing to check
    with pytest.raises(R.ResumeRefused, match="RESUME_CONTRACT_OR_RUNTIME_CHANGED"):
        R.carry_across_change(ch, ["SWE.1", "SWE.2", "SWE.3"])
    with pytest.raises(R.ResumeRefused, match="RESUME_FACTORY_REVISION_CHANGED_OR_DIRTY"):
        R.carry_across_change(R.runtime_change(ID, dict(ID), OLD, NEW), ["SWE.1", "SWE.2", "SWE.3"])
