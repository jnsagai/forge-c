"""Feature 016 OB-T034: the generated prompt texts of the four ST HAL acceptance work orders pass the leftover check
(SC-006), every text records its origin, and the check catches planted leftovers of another layer, another
peripheral or an unknown register field."""
import json

import pytest
from forge_factory import onboarding as OB
from forge_factory.common import REPO_ROOT
from forge_factory.onboarding import leftovers as L
from forge_factory.peripheral import load
from onboarding_util import need_inputs

KEYS = ["0010e-st-cube-gpio-hal-ob", "0011e-st-cube-spi-hal-ob", "0012e-st-cube-usart-hal-ob",
        "0013e-st-cube-tim-hal-ob"]


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    load.cache_clear()
    yield tmp_path
    load.cache_clear()


@pytest.mark.parametrize("key", KEYS)
def test_generated_instructions_have_no_leftover(key, state):
    need_inputs()
    pkg = OB.derive(REPO_ROOT / "examples" / key)
    from forge_factory.onboarding import identity, texts

    stored = OB.facts.read_package(OB.onboarding_dir(key))
    regenerated = texts.generate(identity.context(REPO_ROOT / "examples" / key), stored)
    assert json.loads(json.dumps(regenerated)) == pkg["texts"]
    assert all(v["from"].split(":")[0] in ("template", "owner", "model") for g in pkg["texts"].values()
               for v in g.values())
    assert L.run(key) == []


def _plant(key, edit):
    root = OB.onboarding_dir(key)
    pkg = json.loads((root / "onboarding/package.json").read_text())
    edit(pkg["texts"])
    pkg["sha256"] = OB.facts.canonical_hash(pkg)
    (root / "onboarding/package.json").write_text(json.dumps(pkg))


@pytest.mark.parametrize("key,planted,token", [
    ("0012e-st-cube-usart-hal-ob", "call LL_USART_Enable(USART1) first", "LL_USART_Enable"),
    ("0010e-st-cube-gpio-hal-ob", "check CRC_CR.POLYSIZE", "CRC_CR.POLYSIZE"),
    ("0012e-st-cube-usart-hal-ob", "check USART_CR1.NOSUCHFIELD", "USART_CR1.NOSUCHFIELD"),
    ("0013e-st-cube-tim-hal-ob", "wait for the oscillator", "oscillator")])
def test_planted_leftovers_are_caught(key, planted, token, state):
    need_inputs()
    OB.derive(REPO_ROOT / "examples" / key)
    _plant(key, lambda t: t["prompt_st_hal"]["hal_api"].update(text=t["prompt_st_hal"]["hal_api"]["text"] + " " + planted))
    assert any(x.endswith(":" + token) for x in L.run(key))


def test_hand_onboarded_profiles_keep_their_hand_texts():
    crc = load("crc")
    assert "derived_from" not in crc and crc["prompt_st_hal"]["hal_api"].startswith("Interfaces (the delivered ST HAL")
