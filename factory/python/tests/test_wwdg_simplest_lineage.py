"""Owner 2026-11-09: SWE.1 ladder - the simplest driver (WWDG LL) first, then SPI (intermediate), then TIM (complex)."""
import json

from forge_factory.afo import owner_supervised_development as D
from forge_factory.common import REPO_ROOT


def test_the_wwdg_lineage_names_its_orders_and_uses_the_st_cube_wwdg_example():
    L = D._LINEAGE["wwdg-ll"]
    assert (L["tag"], L["series"], L["example"], L["driver_class"]) == (
        "WWDGL", "20261109-L44", "0016c-st-cube-wwdg", "STM32N6_WWDG_LL_ST")
    assert "WO-F014-SWE1-WWDGL-20261109-L44" in D.ORDER_SCOPE
    assert D.ORDER_SCOPE["WO-F014-SWE1-WWDGL-20261109-L44"] == ("wwdg-ll", "SWE.1", "0016c-st-cube-wwdg")
    assert D.ORDER_DRIVERS["WO-F014-SWE1-WWDGL-20261109-L44"] == "STM32N6_WWDG_LL_ST"


def test_the_wwdg_example_has_the_swe1_generation_form_of_the_other_campaign_examples():
    wwdg = json.loads((REPO_ROOT / "examples/0016c-st-cube-wwdg/workorder.json").read_text())
    spi = json.loads((REPO_ROOT / "examples/0011l-st-cube-spi-swe1-gen/workorder.json").read_text())
    for key in ("layer", "generate_obligations", "development_execution_policy", "guideline", "schema"):
        assert wwdg[key] == spi[key], key
    assert wwdg["peripheral"] == "wwdg"


def test_the_existing_lineages_and_their_order_names_are_unchanged():
    assert [L["id"] for L in D.LINEAGES][:5] == ["gpio-ll", "spi-ll", "usart-ll", "tim-ll", "wwdg-ll"]
    assert D.ORDERS[0] == "WO-F014-SWE1-GPIOL-20261107-L40"
