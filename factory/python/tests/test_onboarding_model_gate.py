"""Feature 016 OB-T040: the simulation-model gate (RM reset values, access types, delivered-code smoke) on the
existing feature 015 models, and the failures it must catch: a wrong reset value, and a model that Renode's
IronPython 2.7 cannot load (the feature 015 USART lesson)."""
import json

import pytest

from forge_factory import onboarding as OB
from forge_factory.common import REPO_ROOT
from forge_factory.mcp.servers.sim import renode_bin
from forge_factory.onboarding import model_gate as G
from forge_factory.peripheral import load
from onboarding_util import need_inputs


@pytest.fixture
def state(tmp_path, monkeypatch):
    need_inputs()
    if not renode_bin():
        pytest.skip("Renode not installed")
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    load.cache_clear()
    yield tmp_path
    load.cache_clear()


@pytest.mark.parametrize("key", ["0010e-st-cube-gpio-hal-ob", "0011e-st-cube-spi-hal-ob", "0012e-st-cube-usart-hal-ob",
                                 "0013e-st-cube-tim-hal-ob"])
def test_existing_models_pass_the_gate_and_are_reused(key, state):
    pkg = OB.derive(REPO_ROOT / "examples" / key)
    m = next(a for a in pkg["authored"] if a["id"] == "model")
    assert m["reused"] and m["status"] == "ACCEPTED" and m["gate"]["verdict"] == "PASS", m["gate"]
    assert m["inspection"]["verdict"] == "NOT_RUN" and m["limits"]


def _pkg(state, key):
    return OB.derive(REPO_ROOT / "examples" / key, gate_model=False)


def _tim_model(state, extra=""):
    model = state / "tim_model.py"
    src = (G.SIM_DIR / "tim_model.py").read_text()
    line = next(ln for ln in src.splitlines() if "0x2C:" in ln and "0xFFFFFFFF" in ln)   # TIM_ARR reset value
    model.write_text(src.replace(line, line.replace("0xFFFFFFFF", "0x0000FFFF"), 1) + extra)
    return model


def test_a_wrong_reset_value_is_caught(state):
    pkg = _pkg(state, "0013e-st-cube-tim-hal-ob")
    f, _, _ = G.registers_check(pkg, _tim_model(state), G.SIM_DIR / "stm32n6_tim.repl", renode_bin())
    assert any(x.startswith("MODEL_RESET:TIM_ARR") for x in f), f


def test_a_model_renode_cannot_load_fails_at_load(state):
    pkg = _pkg(state, "0014d-st-cube-crc-hal")
    model = state / "crc_model.py"
    model.write_text((G.SIM_DIR / "crc_model.py").read_text() + '\nX = f"{1}"\n')   # Python 3 only
    f, _, _ = G.registers_check(pkg, model, G.SIM_DIR / "stm32n6_crc.repl", renode_bin())
    assert f and f[0].startswith("MODEL_LOAD")


def test_declared_model_limits_turn_findings_into_limits(state):
    pkg = _pkg(state, "0013e-st-cube-tim-hal-ob")
    model = _tim_model(state, '\nMODEL_LIMITS = ["TIM_ARR"]\n')
    f, limits, _ = G.registers_check(pkg, model, G.SIM_DIR / "stm32n6_tim.repl", renode_bin())
    assert not f and any("TIM_ARR" in x for x in limits)


def test_assurance_states_the_gate_instead_of_not_comparable(state, tmp_path):
    from forge_factory.assurance.target import limitations

    pkg = OB.derive(REPO_ROOT / "examples/0011e-st-cube-spi-hal-ob")
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(
        {"onboarding": {"key": "0011e-st-cube-spi-hal-ob", "sha256": pkg["sha256"]}}))
    out = limitations(ws, "")
    assert any(x.startswith("SIMULATOR_MODEL_GATE:PASS") for x in out)
    assert "SIMULATOR_MODEL_NOT_COMPARABLE" not in out and any(x.startswith("SIMULATOR_LIMIT:") for x in out)
