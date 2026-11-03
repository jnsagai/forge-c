"""CAPA-129 (WO-F014-SWE3-CRCHAL-20261103-L27): the SWE.3 author used `SWU-CRC_HAL` / `USPEC-HAL-CRC-001`; the strict
unit parser found no unit and the rejection said only UNIT:NO_UNITS, so the author repeated the ids and SWE.3 went
STUCK. The rejection now names every malformed id with the required form; the parser stays strict."""
import json

from forge_factory.inspection import swtrace

MD = """# Software unit specifications

## {u}: CRC HAL calculation unit

- SWC: SWC_HAL
- Functions: HAL_CRC_Init
- Design: workproducts/SWE.3/detailed_design/{u}.puml
- **{s}** The unit HAL_CRC_Init shall write the configured polynomial to CRC_POL.POL. Traces: SWR-001
"""
CODE = "/**\n * @brief Init.\n * @unit {cu}\n * @spec {cs}\n */\nint HAL_CRC_Init(void)\n{{\n    return 0;\n}}\n"


def _ws(tmp_path, u, s, cu=None, cs=None, layer="HAL"):
    ws = tmp_path / f"ws-{u}-{layer}"
    for rel, text in {".forge-run/manifest.json": json.dumps({"layer": layer}), swtrace.UNITS_MD: MD.format(u=u, s=s),
                      "software/hal/stm32n6xx_hal_crc.c": CODE.format(cu=cu or u, cs=cs or s),
                      swtrace.REQS: "- **SWR-001** When x, the CRC driver shall write CRC_POL.POL.\n",
                      swtrace.ARCH: "@startuml\nnote right of SWC_HAL\nAllocated: SWR-001\nend note\n@enduml\n"}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    return ws


def test_l27_ids_are_named_with_the_required_form_and_stay_rejected(tmp_path):
    r = swtrace.check_units(_ws(tmp_path, "SWU-CRC_HAL", "USPEC-HAL-CRC-001"), render=False, export=False)
    f = r["major_findings"]
    assert r["units"] == [] and "UNIT:NO_UNITS" in f  # strict: the wrong form is not a unit
    assert f[0].startswith("UNIT:MALFORMED_UNIT_ID:SWU-CRC_HAL (a unit id must be SWU-HAL-nn (e.g. SWU-HAL-01)")
    assert f[1].startswith("UNIT:MALFORMED_SPEC_ID:USPEC-HAL-CRC-001 (a spec item id must be USPEC-HAL-<unit nn>-nn "
                           "(e.g. USPEC-HAL-01-01")
    assert sum("MALFORMED" in x for x in f) == 2  # the same id in the md and the code tags is reported once


def test_code_tags_alone_and_layer_specific_forms(tmp_path):
    f = swtrace.check_units(_ws(tmp_path, "SWU-HAL-01", "USPEC-HAL-01-01", cu="SWU_HAL_1", cs="USPEC-HAL-01-1"),
                            render=False, export=False)["major_findings"]
    assert [x.split(" (")[0] for x in f if "MALFORMED" in x] == ["UNIT:MALFORMED_SPEC_ID:USPEC-HAL-01-1"]
    f = swtrace.check_units(_ws(tmp_path, "SWU-X", "USPEC-HAL-01-01", layer="LL"), render=False, export=False)
    assert "SWU-LL-nn (e.g. SWU-LL-01)" in f["major_findings"][0] and "SWU-HAL" not in f["major_findings"][0]
    f = swtrace.check_units(_ws(tmp_path, "SWU-X", "USPEC-HAL-01-01", layer="LL+HAL"), render=False, export=False)
    assert "SWU-LL-nn (e.g. SWU-LL-01) or SWU-HAL-nn (e.g. SWU-HAL-01)" in f["major_findings"][0]


def test_well_formed_ids_get_no_malformed_finding(tmp_path):
    r = swtrace.check_units(_ws(tmp_path, "SWU-HAL-01", "USPEC-HAL-01-01"), render=False, export=False)
    assert len(r["units"]) == 1 and not any("MALFORMED" in x or x == "UNIT:NO_UNITS" for x in r["major_findings"])
