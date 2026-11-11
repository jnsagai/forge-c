"""Feature 016 OB-T007: the delivery contract accepts an onboarding work order with owner inputs only, keeps
requiring the hand-written file map otherwise, and every existing example still validates."""
import json

import pytest

from forge_factory.brownfield import delivery as BD
from forge_factory.common import REPO_ROOT

EXAMPLES = sorted(p for p in (REPO_ROOT / "examples").glob("*/workorder.json")
                  if "delivery" in json.loads(p.read_text()))
OWNER_ONLY = {"code_mode": "FROZEN", "origin": "STMicroelectronics stm32n6xx-hal-driver v1.4.0", "licence": "BSD-3-Clause",
              "licence_allows_modification": True, "source": "$FORGE_DATA_ROOT/inputs/st/hal", "onboarding": True,
              "packages": [{"source": "$FORGE_DATA_ROOT/inputs/st/cmsis-device", "origin": "ST cmsis-device-n6 v1.4.0",
                            "licence": "Apache-2.0"}],
              "scope": {"functions": ["HAL_UART_Init"]}, "build": {"style": "cmsis", "defines": ["STM32N657xx"],
                                                                    "secure": True}, "provided_ll": False}


@pytest.mark.parametrize("wo", EXAMPLES, ids=lambda p: p.parent.name)
def test_existing_examples_still_validate(wo):
    assert BD.validate(json.loads(wo.read_text())["delivery"]) == []


def test_owner_inputs_only_onboarding_delivery_validates():
    assert BD.validate(OWNER_ONLY) == []
    hand = {k: v for k, v in OWNER_ONLY.items() if k not in ("onboarding", "packages")}
    assert any("files" in e for e in BD.validate(hand))                       # no onboarding: the map is required


def test_intake_refuses_an_onboarding_delivery_without_its_derived_map(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    with pytest.raises(BD.DeliveryBlocked, match="DELIVERY_FILES_NOT_DERIVED"):
        BD.intake({"delivery": OWNER_ONLY}, tmp_path, "WO-OB-X")
