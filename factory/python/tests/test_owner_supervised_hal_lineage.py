"""Owner 2026-11-09: "implement first the low level driver, then the whole driver for the same model" - the owner
lane carries a HAL lineage that builds only on the SWE.6 order of its own LL lineage (provided_from); LL lineages
still build on nothing."""
# ruff: noqa: F811 - shared pytest fixtures are imported from their home modules
from __future__ import annotations

import pytest
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused
from test_owner_supervised_development import _lineage, _shape, _wo, supervised  # noqa: F401

LL_SWE6 = "WO-F014-SWE6-WWDGL-20261109-L44C"


def _hal(supervised, name, provided_from=LL_SWE6):
    order = _shape(supervised, name, "wwdg-hal")
    return {**order, "provided_from": provided_from}


def test_the_hal_lineage_follows_its_ll_lineage():
    hal = D._LINEAGE["wwdg-hal"]
    assert hal["depends_on"] == "wwdg-ll" and hal["example"] == "0016m-wwdg-hal"
    assert hal["driver_class"] == "STM32N6_WWDG_HAL" and D.ORDER_DRIVERS["WO-F014-SWE1-WWDGH-20261109-L45"] == hal["driver_class"]
    assert all(D._LINEAGE[i]["depends_on"] is None for i in ("gpio-ll", "spi-ll", "usart-ll", "tim-ll", "wwdg-ll"))


@pytest.mark.parametrize("name", ["START", "START_RETRY", "CHAIN", "CHAIN_RETRY", "UPSTREAM", "RECOVERY_SWE1"])
def test_a_hal_order_on_the_ll_swe6_order_is_accepted(supervised, name):
    D.validate_order(_hal(supervised, name))


@pytest.mark.parametrize("source", [None, "WO-F014-SWE5-WWDGL-20261109-L44", "WO-F014-SWE6-SPIL-20261107-L41",
                                    "WO-F014-SWE6-WWDGHAL-20261104-L35E", "WO-F014-SWE6-WWDGH-20261109-L45"])
def test_a_hal_order_on_anything_else_is_refused(supervised, source):
    with pytest.raises(Refused, match=D.ENVELOPE_REFUSED):
        D.validate_order(_hal(supervised, "START", source))


def test_an_ll_order_still_refuses_provided_from(supervised):
    with pytest.raises(Refused, match=D.ENVELOPE_REFUSED):
        D.validate_order({**_shape(supervised, "START", "wwdg-ll"), "provided_from": LL_SWE6})


@pytest.mark.parametrize(("hal", "ll_swe6"), [("spi-hal", "WO-F014-SWE6-SPIL-20261107-L41B"),
                                             ("tim-hal", "WO-F014-SWE6-TIML-20261107-L43")])
def test_every_hal_lineage_builds_only_on_its_own_ll(supervised, hal, ll_swe6):
    D.validate_order({**_shape(supervised, "START", hal), "provided_from": ll_swe6})
    for other in (LL_SWE6, "WO-F014-SWE5-" + ll_swe6.split("-", 3)[3], None):
        with pytest.raises(Refused, match=D.ENVELOPE_REFUSED):
            D.validate_order({**_shape(supervised, "START", hal), "provided_from": other})


def test_the_hal_lineages_name_their_specs_and_drivers():
    assert {i: (D._LINEAGE[i]["example"], D._LINEAGE[i]["driver_class"], D._LINEAGE[i]["depends_on"])
            for i in ("spi-hal", "tim-hal")} == {
        "spi-hal": ("0011m-spi-hal", "STM32N6_SPI_HAL", "spi-ll"),
        "tim-hal": ("0013m-tim-hal", "STM32N6_TIM_HAL", "tim-ll")}
