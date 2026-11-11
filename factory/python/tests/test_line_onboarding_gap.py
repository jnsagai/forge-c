"""Owner 2026-11-11: the SPI/TIM HAL ladder steps wait as INPUT_GAP:ONBOARDING_NOT_APPROVED until the owner signs."""
import inspect
import json

from forge_factory.afo import line_orders as LO

FHAL = {"layer": "HAL", "onboarding": {"style": "HAL_ON_LL", "ll_example": "0011l-st-cube-spi-swe1-gen"}}


def test_factory_hal_and_onboarding_specs_need_an_approval():
    assert LO.onboarding_spec(FHAL) and LO.onboarding_spec({"delivery": {"onboarding": True}})
    assert not LO.onboarding_spec({"layer": "LL", "delivery": {"source": "x"}})


def test_a_missing_package_or_approval_is_a_gap(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    assert LO.onboarding_gap("0011m-spi-hal") == "ONBOARDING_NOT_APPROVED"
    pkg = tmp_path / "onboarding/0011m-spi-hal/onboarding"
    pkg.mkdir(parents=True)
    (pkg / "package.json").write_text(json.dumps({"status": "READY_FOR_OWNER"}))
    assert LO.onboarding_gap("0011m-spi-hal") == "ONBOARDING_NOT_APPROVED"


def test_input_gaps_checks_the_approval_live():
    src = inspect.getsource(LO.RealLine.input_gaps)
    assert "onboarding_gap(example)" in src and "never cached" in src
