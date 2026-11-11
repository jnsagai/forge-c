"""CAPA-228 (owner SWE.2 review 2026-11-11: the SPI/TIM HAL keep their LL SWE.1 basis through SWE.2): a HAL order
that continues a HAL SWE.1 order into SWE.2 keeps the LL basis that order recorded (F016 FR-027 basis_phase). Before,
the basis was recomputed from --stop-after, so the SWE.2 continuation of SPI HAL L46 (built on SPI LL L41P, verified
SWE.1) required the LL SWE.2 gate and was refused with PROVIDED_LL_NOT_VERIFIED. Code phases keep the six-gate rule."""
import json

import pytest
from forge_factory import workorder as WO

SRC = {"provided": [{"role": "provided_ll_driver", "path": "software/ll/x.h", "sha256": "0" * 64,
                     "source_work_order": "WO-LL", "basis_phase": "SWE.1", "verified_phases": ["SWE.1"]}]}


def test_a_continuation_keeps_the_recorded_ll_basis():
    assert WO.ll_basis_for("SWE.2", SRC) == "SWE.1"
    assert WO.ll_basis_for("SWE.1", SRC) == "SWE.1"


def test_a_fresh_order_and_a_six_gate_source_use_the_stop_phase():
    assert WO.ll_basis_for("SWE.2", None) == "SWE.2"
    six = {"provided": [{"role": "provided_ll_driver", "path": "p", "sha256": "0" * 64, "source_work_order": "WO-LL"}]}
    assert WO.ll_basis_for("SWE.2", six) == "SWE.2"
    assert WO.ll_basis_for("SWE.1", {"provided": []}) == "SWE.1"


def test_code_phases_keep_the_six_gate_rule():
    for stop in (None, "SWE.3", "SWE.6"):
        assert WO.ll_basis_for(stop, SRC) is None


def test_run_passes_the_recorded_basis_to_prepare(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    src = tmp_path / "state/workorders/WO-HAL-SWE1/workspace/.forge-run"
    src.mkdir(parents=True)
    (src / "manifest.json").write_text(json.dumps({"work_order": "WO-HAL-SWE1", **SRC}))
    ex = tmp_path / "ex"
    ex.mkdir()
    (ex / "workorder.json").write_text("{}")
    seen = {}

    class Stop(Exception):
        pass

    def prepare(example, wo, provided_from=None, **kw):
        seen.update(kw, provided_from=provided_from)
        raise Stop

    monkeypatch.setattr(WO, "prepare", prepare)
    with pytest.raises(Stop):
        WO.run(ex, "WO-HAL-SWE2", resume="WO-HAL-SWE1", provided_from="WO-LL", stop_after="SWE.2")
    assert seen["ll_basis"] == "SWE.1" and seen["provided_from"] == "WO-LL"
