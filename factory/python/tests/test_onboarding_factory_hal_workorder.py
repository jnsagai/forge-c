"""Feature 016 OB-T070 (owner decisions 2026-11-11): a factory-HAL (HAL_ON_LL) work order is prepared only from its
owner-approved package - generated scope, owner-confirmed budgets, the package's peripheral and LL lineage header -
and a HAL work order stopping at SWE.1/SWE.2 may build on an LL work order verified up to that phase (FR-027); SWE.3+
keeps the six-gate rule. A throwaway test key signs; the factory never signs an owner approval."""
import json
import os
import shutil
import subprocess

import pytest
from forge_factory import onboarding as OB
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT
from forge_factory.inspection import engine
from forge_factory.onboarding import approval as A
from forge_factory.onboarding import factory_hal as FH
from forge_factory.peripheral import load
from forge_factory.workflow import prompts
from onboarding_util import factory_hal_example, need_inputs

SPI_LL = "$FORGE_DATA_ROOT/inputs/st/stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_spi.h"


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    load.cache_clear()
    yield tmp_path
    load.cache_clear()
    prompts.LAYER["layer"] = "LL+HAL"


def ll_order(state, wo="WO-LL-SPI", peripheral="spi", header: bytes | None = None, layer="LL"):
    src = state / "state/workorders" / wo / "workspace"
    (src / "software/ll").mkdir(parents=True)
    (src / "software/ll/stm32n6xx_ll_spi.h").write_bytes(header if header is not None else b"/* LL */\n")
    (src / ".forge-run").mkdir(parents=True)
    (src / ".forge-run/manifest.json").write_text(json.dumps({"layer": layer, "peripheral": peripheral,
                                                              "work_order": wo}))
    return src


def gates(monkeypatch, passed):
    monkeypatch.setattr(engine.Store, "gate", lambda self, ph: {"decision": "PASS" if ph in passed else "REWORK"})


def test_an_swe1_stage_hal_order_may_build_on_an_ll_order_verified_up_to_swe1(state, monkeypatch):
    ll_order(state)
    gates(monkeypatch, {"SWE.1"})
    data, rec = WO.provided_ll("WO-LL-SPI", "spi", upto="SWE.1")
    assert data == b"/* LL */\n" and rec["basis_phase"] == "SWE.1" and rec["verified_phases"] == ["SWE.1"]
    assert "FR-027" in rec["basis_rule"]
    with pytest.raises(ValueError, match="PROVIDED_LL_NOT_VERIFIED:WO-LL-SPI:SWE.2"):
        WO.provided_ll("WO-LL-SPI", "spi", upto="SWE.2")                    # an SWE.2 order needs SWE.1..SWE.2
    for upto in (None, "SWE.3", "SWE.6"):                                     # code phases: the six-gate rule stays
        with pytest.raises(ValueError, match="PROVIDED_LL_NOT_VERIFIED:WO-LL-SPI:SWE.2,SWE.3,SWE.4,SWE.5,SWE.6"):
            WO.provided_ll("WO-LL-SPI", "spi", upto=upto)


def test_the_six_gate_record_is_unchanged_and_other_refusals_hold(state, monkeypatch):
    ll_order(state)
    gates(monkeypatch, {"SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"})
    _d, rec = WO.provided_ll("WO-LL-SPI", "spi")
    assert not {"basis_phase", "verified_phases", "basis_rule"} & set(rec)  # ADR-0009 record, byte-identical keys
    with pytest.raises(ValueError, match="PROVIDED_LL_OTHER_PERIPHERAL:WO-LL-SPI:spi"):
        WO.provided_ll("WO-LL-SPI", "tim", upto="SWE.1")                    # wrong peripheral refused
    ll_order(state, "WO-LLHAL", layer="LL+HAL")
    with pytest.raises(ValueError, match="PROVIDED_LL_NOT_FROM_LL_WORK_ORDER"):
        WO.provided_ll("WO-LLHAL", "spi", upto="SWE.1")


def test_hand_text_peripheral_and_style_mismatches_are_refused():
    pkg = {"driver_style": "HAL_ON_LL", "facts": [{"name": "register_prefix", "value": "SPI", "status": "DERIVED",
                                                    "method": "m", "sources": []}],
           "texts": {"work_order": {"scope": {"text": ["generated"], "from": "template:factory_hal.scope"}}},
           "assumptions": []}
    for extra, code in (({"scope": ["hand prose"]}, "ONBOARDING_HAND_TEXT_REFUSED:scope"),
                        ({"prompt": {}}, "ONBOARDING_HAND_TEXT_REFUSED:prompt"),
                        ({"peripheral": "tim"}, "ONBOARDING_PERIPHERAL_MISMATCH:tim")):
        with pytest.raises(FH.FactoryHalError, match=code):
            FH.apply({"layer": "HAL", **extra}, pkg, {})
    with pytest.raises(FH.FactoryHalError, match="ONBOARDING_STYLE_MISMATCH"):
        FH.apply({"layer": "HAL"}, {**pkg, "driver_style": "LL"}, {})


@pytest.fixture
def signer(tmp_path, monkeypatch):
    if not shutil.which("ssh-keygen"):
        pytest.skip("ssh-keygen not installed")
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    allowed = tmp_path / "allowed"
    allowed.write_text(f"tester {key.with_suffix('.pub').read_text()}")
    monkeypatch.setattr(A, "ALLOWED_SIGNERS", allowed)
    return key


def approve(root, key, flash=8192):
    A.summary(root)
    a = json.loads((root / A.TEMPLATE).read_text())
    a.update(approval_id="OA-2026-11-11-07", decided_by="tester", decided_on="2026-11-11")
    for c in a["assumption_confirmations"]:
        if c["id"] == "ASM-BUDGET-FLASH":
            c["value"] = flash
    (root / A.APPROVAL).write_text(json.dumps(a))
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", A.NAMESPACE, str(root / A.APPROVAL)],
                   check=True)


def test_a_factory_hal_order_is_prepared_only_from_its_approved_package(state, signer, monkeypatch):
    need_inputs()
    ex = factory_hal_example(state, "spi")
    with pytest.raises(OB.OnboardingNotApproved, match="ONBOARDING_NOT_APPROVED:APPROVAL_MISSING"):
        WO.prepare(ex, "WO-SPI-HAL-0", "WO-LL-SPI", ll_basis="SWE.1")       # unapproved package refused
    approve(OB.onboarding_dir(ex.name), signer)
    real = open(os.path.expandvars(SPI_LL), "rb").read()
    ll_order(state, header=real)
    gates(monkeypatch, {"SWE.1"})
    with pytest.raises(ValueError, match="PROVIDED_LL_NOT_VERIFIED:WO-LL-SPI:SWE.2"):
        WO.prepare(ex, "WO-SPI-HAL-1", "WO-LL-SPI")                          # a full HAL order: six gates
    ws, man = WO.prepare(ex, "WO-SPI-HAL-2", "WO-LL-SPI", ll_basis="SWE.1")
    assert man["provided"][0]["basis_phase"] == "SWE.1" and man["provided"][0]["source_work_order"] == "WO-LL-SPI"
    assert man["peripheral"] == f"onboarded:{ex.name}" and man["onboarding"]["driver_style"] == "HAL_ON_LL"
    assert man["onboarding"]["ll_lineage"]["example"] == "0011l-st-cube-spi-swe1-gen"
    assert man["scope"][0].startswith("HAL: hal_status_t API with HAL_SPI_ prefix")    # generated, not hand-written
    assert man["budgets"]["flash_bytes"] == 8192 and "OA-2026-11-11-07" in man["budgets"]["status"]  # owner value
    assert man["simulation_performance"]["performance_mips"] == 100
    assert man["semantic_required_operations"] and man["layer"] == "HAL"
    assert load(man["peripheral"])["hal"]["host_instance"] == "SPI1"
    other = ll_order(state, "WO-LL-OTHER", header=b"/* another LL */\n")
    assert other.is_dir()
    with pytest.raises(ValueError, match="PROVIDED_LL_NOT_THE_PACKAGE_LINEAGE:WO-LL-OTHER"):
        WO.prepare(ex, "WO-SPI-HAL-3", "WO-LL-OTHER", ll_basis="SWE.1")
