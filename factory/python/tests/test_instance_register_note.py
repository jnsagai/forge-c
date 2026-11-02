"""CAPA-111 (run WO-F014-CMP-SWE2-OBL-20261102-06): the SWE.2/SWE.3 inspectors of an instance-mode work order were told
the extern register-block array is mandatory (ADR-0009 note), so a correct caller-instance architecture failed three
times. In instance mode they get the declared instance; every other LL work order keeps the ADR-0009 note."""
import json

import pytest
from forge_factory import workorder as W
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import review
from forge_factory.workflow import prompts

INSTANCE = REPO_ROOT / "examples/0014i-st-crc-idr-swe1-aspice-high"
LEGACY = REPO_ROOT / "examples/0014h-st-crc-idr-swe1-aspice"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))


@pytest.mark.parametrize("phase", ["SWE.2", "SWE.3"])
def test_instance_mode_inspector_gets_the_declared_instance(env, phase):
    ws, _ = W.prepare(INSTANCE, "WO-T-NOTE-I", purpose="ASPICE_ONLY")
    notes = " ".join(review._notes(ws, phase, "SWE2-02"))
    assert "CRC_TypeDef *CRCx" in notes and "forge_crc_device.h" in notes and "instance macro CRC" in notes
    assert "extern volatile uint32_t" not in notes and "ADR-0009" not in notes


def test_legacy_work_order_keeps_the_register_block_note(env):
    ws, _ = W.prepare(LEGACY, "WO-T-NOTE-L", purpose="ASPICE_ONLY")
    notes = " ".join(review._notes(ws, "SWE.2", "SWE2-02"))
    assert "extern volatile uint32_t ll_crc_regs" in notes and "ADR-0009" in notes
    assert prompts.register_note(None) is prompts.REGISTER_BLOCK_NOTE
