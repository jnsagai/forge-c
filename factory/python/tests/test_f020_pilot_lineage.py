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
PILOT = "uart-module"
EXAMPLE = "0012u-st-cube-uart-module"
DRIVER = "STM32N6_UART_MODULE_ST"


def _sub(doc):
    return yaml.safe_load(yaml.safe_dump(doc, sort_keys=False).replace("@SOURCE@", "a" * 40))


def test_the_uart_module_lineage_and_the_pilot_option():
    assert D.PILOTS == {PILOT: ["SWE.1"]}
    L = D._LINEAGE[PILOT]
    assert (L["tag"], L["example"], L["driver_class"], L["depends_on"]) == ("UARTM", EXAMPLE, DRIVER, None)
    assert PILOT not in D.LADDER and (REPO_ROOT / "examples" / EXAMPLE / "workorder.json").is_file()


def test_the_derived_campaign_validates_with_the_pilot_active_on_its_own_phases(tmp_path):
    doc = D.derived_campaign()
    assert LCMP.validate(_sub(doc)) == [] and LCMP.contract_errors(_sub(doc)) in ([], None)
    by = {x["id"]: x for x in doc["lineages"]}
    p = by[PILOT]
    assert (p["status"], p["phases"], p["example"], p["tag"], p["driver_class"]) == (
        "ACTIVE", ["SWE.1"], EXAMPLE, "UARTM", DRIVER)
    assert not {"after", "depends_on", "provided_from", "start"} & set(p)
    ladder = [by[i]["priority"] for i in D.LADDER]
    assert 30 < p["priority"] < min(ladder)  # after every ready ladder step, before the lineages on hold
    f = tmp_path / "c.yaml"
    f.write_text(yaml.safe_dump(_sub(doc), sort_keys=False))
    c = LCMP.parse(f, require_approval=False)
    assert list({x.id: x.phases for x in c.lineages}[PILOT]) == ["SWE.1"]


def test_the_ladder_and_every_other_lineage_entry_are_unchanged():
    doc = D.derived_campaign()
    by = {x["id"]: x for x in doc["lineages"]}
    assert {i: digest(by[i]) for i in BASE["lineages"]} == BASE["lineages"]
    assert [x["id"] for x in doc["lineages"]][:len(BASE["lineages"])] == [L["id"] for L in D.LINEAGES if L["id"] != PILOT]
    assert digest({k: v for k, v in doc.items() if k != "lineages"}) == BASE["campaign_without_lineages"]


def test_existing_order_names_are_unchanged_and_the_pilot_adds_its_own():
    old = {wo: s for wo, s in D.ORDER_SCOPE.items() if s[0] != PILOT}
    assert len(old) == BASE["orders"]["count"]
    assert hashlib.sha256(json.dumps(sorted(old.items())).encode()).hexdigest() == BASE["orders"]["sha256"]
    drivers = {wo: d for wo, d in D.ORDER_DRIVERS.items() if wo in old}
    assert hashlib.sha256(json.dumps(sorted(drivers.items())).encode()).hexdigest() == BASE["order_drivers_sha256"]
    new = {wo for wo, s in D.ORDER_SCOPE.items() if s[0] == PILOT}
    assert "WO-F014-SWE1-UARTM-20261112-L49" in new and all("-UARTM-" in wo for wo in new)
    assert D.ORDER_SCOPE["WO-F014-SWE1-UARTM-20261112-L49"] == (PILOT, "SWE.1", EXAMPLE)


def test_t029_the_owner_lane_admits_the_pilot_from_generated_data_only():
    """The record fields the guardian generates (order_ids, driver_class, order_drivers) carry the pilot."""
    wo = "WO-F014-SWE1-UARTM-20261112-L49"
    assert wo in D.ORDERS and D.ORDER_DRIVERS[wo] == DRIVER
    assert DRIVER in sorted(set(D.ORDER_DRIVERS.values()))
    from forge_factory.afo.queue import order_id_for

    assert order_id_for("line-local", wo) in D.trial_order_ids()
