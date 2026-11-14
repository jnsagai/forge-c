"""Feature 020 T028 (research R7) and T029: the UART module pilot lineage and the generic PILOTS option.

`uart-module` (tag UARTM, example 0012u-st-cube-uart-module, driver class STM32N6_UART_MODULE_ST) joins LINEAGES; the
generic `PILOTS = {lineage_id: phases}` makes such a lineage ACTIVE in `derived_campaign()` with its own phases, outside
the driver ladder (no `after`/`depends_on` chaining). The ladder, every other lineage entry and every existing order
name are unchanged: golden `fixtures/f020/derived_campaign_base.json` captured on forge-c-020-base (303b46ea).

T029: in the owner lane (OWNER_SUPERVISED_DEVELOPMENT) a new lineage needs no signed grant entry: the guardian's
record admits exactly `ORDERS` with `ORDER_DRIVERS` (generated from LINEAGES when the record is issued) and the
deployer's unsigned development inputs name the product-role trial orders from the same `ORDERS`; the signed PILOT
grants' `driver_classes` are not consulted in that mode (afo/authority._decide)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from forge_factory.afo import line_campaign as LCMP
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import digest
from forge_factory.common import REPO_ROOT

BASE = json.loads((Path(__file__).parent / "fixtures/f020/derived_campaign_base.json").read_text())
# Owner 2026-11-13 "run SWE.1 on spi module now on local. use this new way of working": the SPI module is the active
# pilot; the UART module pilot (SWE.1 PASS at L50B, D41) stays a registered lineage on hold.
# Owner 2026-11-14 "after finishing SPI, i want omniverse to place TIM to do the same SWE 1 work": the TIM module pilot
# is ACTIVE `after` the SPI module's SWE.1 PASS, so the line places it by itself.
PILOT = "spi-module"
TAG = "SPIM"
EXAMPLE = "0011u-st-cube-spi-module"
DRIVER = "STM32N6_SPI_MODULE_ST"
NEXT = ("tim-module", "TIMM", "0013u-st-cube-tim-module", "STM32N6_TIM_MODULE_ST")
MODULES = ("uart-module", "spi-module", "tim-module")  # the feature 020 lineages (not in the base golden)


def _sub(doc):
    return yaml.safe_load(yaml.safe_dump(doc, sort_keys=False).replace("@SOURCE@", "a" * 40))


def test_the_module_lineages_and_the_pilot_option():
    assert D.PILOTS == {PILOT: ["SWE.1"], NEXT[0]: ["SWE.1"]} and D.PILOT_AFTER == {NEXT[0]: PILOT}
    T = D._LINEAGE[NEXT[0]]
    assert (T["tag"], T["example"], T["driver_class"], T["depends_on"]) == (*NEXT[1:], None)
    assert NEXT[0] not in D.LADDER and (REPO_ROOT / "examples" / NEXT[2] / "workorder.json").is_file()
    L = D._LINEAGE[PILOT]
    assert (L["tag"], L["example"], L["driver_class"], L["depends_on"]) == (TAG, EXAMPLE, DRIVER, None)
    assert PILOT not in D.LADDER and (REPO_ROOT / "examples" / EXAMPLE / "workorder.json").is_file()
    U = D._LINEAGE["uart-module"]
    assert (U["tag"], U["example"]) == ("UARTM", "0012u-st-cube-uart-module")
    by = {x["id"]: x for x in D.derived_campaign()["lineages"]}
    assert by["uart-module"]["status"] == "ON_HOLD"  # its SWE.1 passed (L50B): no new UART order


def test_the_derived_campaign_validates_with_the_pilot_active_on_its_own_phases(tmp_path):
    doc = D.derived_campaign()
    assert LCMP.validate(_sub(doc)) == [] and LCMP.contract_errors(_sub(doc)) in ([], None)
    by = {x["id"]: x for x in doc["lineages"]}
    p = by[PILOT]
    assert (p["status"], p["phases"], p["example"], p["tag"], p["driver_class"]) == (
        "ACTIVE", ["SWE.1"], EXAMPLE, TAG, DRIVER)
    assert not {"after", "depends_on", "provided_from", "start"} & set(p)
    t = by[NEXT[0]]  # the TIM module waits for the SPI module's SWE.1 PASS and builds on nothing
    assert (t["status"], t["phases"], t["example"], t["tag"], t["driver_class"], t["priority"]) == (
        "ACTIVE", ["SWE.1"], NEXT[2], NEXT[1], NEXT[3], p["priority"])
    assert t["after"] == {"lineage": PILOT, "phase": "SWE.1", "verdict": "PASS"}
    assert not {"depends_on", "provided_from", "start"} & set(t)
    ladder = [by[i]["priority"] for i in D.LADDER]
    assert 30 < p["priority"] < min(ladder)  # after every ready ladder step, before the lineages on hold
    f = tmp_path / "c.yaml"
    f.write_text(yaml.safe_dump(_sub(doc), sort_keys=False))
    c = LCMP.parse(f, require_approval=False)
    parsed = {x.id: x for x in c.lineages}
    assert list(parsed[PILOT].phases) == ["SWE.1"] and list(parsed[NEXT[0]].phases) == ["SWE.1"]
    assert parsed[NEXT[0]].after == {"lineage": PILOT, "phase": "SWE.1", "verdict": "PASS"}


def test_the_ladder_and_every_other_lineage_entry_are_unchanged():
    doc = D.derived_campaign()
    by = {x["id"]: x for x in doc["lineages"]}
    assert {i: digest(by[i]) for i in BASE["lineages"]} == BASE["lineages"]
    assert [x["id"] for x in doc["lineages"]][:len(BASE["lineages"])] == [L["id"] for L in D.LINEAGES
                                                                          if L["id"] not in MODULES]
    assert digest({k: v for k, v in doc.items() if k != "lineages"}) == BASE["campaign_without_lineages"]


def test_existing_order_names_are_unchanged_and_the_pilot_adds_its_own():
    old = {wo: s for wo, s in D.ORDER_SCOPE.items() if s[0] not in MODULES}
    assert len(old) == BASE["orders"]["count"]
    assert hashlib.sha256(json.dumps(sorted(old.items())).encode()).hexdigest() == BASE["orders"]["sha256"]
    drivers = {wo: d for wo, d in D.ORDER_DRIVERS.items() if wo in old}
    assert hashlib.sha256(json.dumps(sorted(drivers.items())).encode()).hexdigest() == BASE["order_drivers_sha256"]
    tim = {wo for wo, s in D.ORDER_SCOPE.items() if s[0] == NEXT[0]}
    assert "WO-F014-SWE1-TIMM-20261114-L52" in tim and all("-TIMM-" in wo for wo in tim)
    assert D.ORDER_SCOPE["WO-F014-SWE1-TIMM-20261114-L52"] == (NEXT[0], "SWE.1", NEXT[2])
    new = {wo for wo, s in D.ORDER_SCOPE.items() if s[0] == PILOT}
    assert "WO-F014-SWE1-SPIM-20261113-L51" in new and all("-SPIM-" in wo for wo in new)
    assert D.ORDER_SCOPE["WO-F014-SWE1-SPIM-20261113-L51"] == (PILOT, "SWE.1", EXAMPLE)
    assert D.ORDER_SCOPE["WO-F014-SWE1-UARTM-20261113-L50"] == ("uart-module", "SWE.1", "0012u-st-cube-uart-module")


def test_t029_the_owner_lane_admits_the_pilot_from_generated_data_only():
    """The record fields the guardian generates (order_ids, driver_class, order_drivers) carry the pilot."""
    from forge_factory.afo.queue import order_id_for

    for wo, drv in (("WO-F014-SWE1-SPIM-20261113-L51", DRIVER), ("WO-F014-SWE1-TIMM-20261114-L52", NEXT[3])):
        assert wo in D.ORDERS and D.ORDER_DRIVERS[wo] == drv
        assert drv in sorted(set(D.ORDER_DRIVERS.values()))
        assert order_id_for("line-local", wo) in D.trial_order_ids()
