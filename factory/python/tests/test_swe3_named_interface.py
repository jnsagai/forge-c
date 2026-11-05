"""CAPA-091 (run WO-F014-SWE3-OBL-20261101-L1): structured SWE.3 reads a named-function SWE.2 interface."""
from __future__ import annotations

import json

from forge_factory.lrtx import swe3


def _ws(tmp_path, doc):
    p = tmp_path / ".forge-run/lrtx/SWE.2/packets/interfaces.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"task": "interfaces", "status": "VALID", "doc": doc}))
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-T", "layer": "LL", "peripheral": "crc"}))
    return tmp_path


def test_named_and_other_functions_become_units_in_order(tmp_path):
    doc = {"named_functions": {"LL_CRC_Write_IDR": {"fields": [], "operation": "w", "params": [], "returns": "void"}},
           "other_functions": [{"name": "LL_CRC_Helper", "fields": [], "operation": "h", "params": [], "returns": "void"}],
           "allocation": [{"swr": "SWR-001", "functions": ["LL_CRC_Write_IDR", "LL_CRC_Helper"]}], "calls": []}
    us = swe3.units(_ws(tmp_path, doc))
    assert [u["function"]["name"] for u in us] == ["LL_CRC_Write_IDR", "LL_CRC_Helper"] and us[0]["swrs"] == ["SWR-001"]


def test_the_plain_functions_shape_is_unchanged(tmp_path):
    doc = {"functions": [{"name": "LL_IWDG_Enable", "fields": [], "operation": "e", "params": [], "returns": "void"}],
           "allocation": [{"swr": "SWR-001", "functions": ["LL_IWDG_Enable"]}], "calls": []}
    assert [u["id"] for u in swe3.units(_ws(tmp_path, doc))] == ["SWU-LL-01"]
