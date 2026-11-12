"""Declared typed register interfaces use source-backed compiler probes.

All candidate C here is deliberate fixture code, not Qwen output. Passing a
layout/signature check is not passing functional, phase or release acceptance.
"""
# ruff: noqa: F811 - shared isolated fixture
import copy
import json
import re

import pytest
from forge_factory import delivery_first as D
from forge_factory.common import sha256_file
from forge_factory.inspection.implementation import check_implementation
from forge_factory.inspection.regmap import check_regmap
from test_delivery_first import GOOD, candidate, prepared  # noqa: F401

API = '''#ifndef FORGE_IDR_API_CONTRACT_H
#define FORGE_IDR_API_CONTRACT_H
#include "forge_crc_device.h"
static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData);
static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx);
#endif
'''
ARCH = '''# CRC fixture architecture
## Requirement allocation
| SWR | Function |
|---|---|
| SWR-001 | LL_CRC_Write_IDR |
| SWR-002 | LL_CRC_Read_IDR |
## Register table
| Register | Offset |
|---|---|
| CRC_IDR | 0x004 |
'''


def save_manifest(ws, man):
    (ws / ".forge-run/manifest.json").write_text(json.dumps(man))


def input_file(ws, man, path, text, role):
    target = ws / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.chmod(0o600)
    target.write_text(text)
    man["inputs"] = [item for item in man["inputs"] if item["path"] != path]
    man["inputs"].append({"path": path, "sha256": sha256_file(target), "role": role, "bytes": target.stat().st_size})


def typed(prepared):
    ws, original = prepared
    man = copy.deepcopy(original)
    input_file(ws, man, "inputs/IDR-API.h", API, "delivery_first_api_contract")
    man["delivery_first"]["register_interface"] = {
        "schema": "forge-c/typed-register-interface/1",
        "device_header": "inputs/forge_crc_device.h",
        "api_contract": "inputs/IDR-API.h",
        "manual": next(i["path"] for i in man["inputs"] if i["role"] == "reference_manual_crc_chapter"),
        "type_name": "CRC_TypeDef",
        "members": [{"register": "CRC_IDR", "member": "IDR", "width_bits": 32}],
    }
    save_manifest(ws, man)
    architecture = ws / "workproducts/SWE.2/software_architecture.md"
    architecture.parent.mkdir(parents=True)
    architecture.write_text(ARCH)
    return ws, man


def test_typed_layout_checks_frozen_manual_offset_width_volatility_and_api(prepared):
    ws, man = typed(prepared)
    header = candidate(ws)
    before = header.read_bytes()
    report = check_regmap(ws)
    assert report["verdict"] == "PASS", report
    assert report["stats"]["members_checked"] == 1
    assert report["stats"]["layout_compile"] == "PASS"
    proof = json.loads((ws / "verification/static/typed_register_layout.json").read_text())
    assert proof["candidate_sha256"]["software/ll/stm32n6xx_ll_crc.h"] == sha256_file(header)
    assert proof["members"][0]["offset"] == 4
    assert proof["manual_sha256"] == sha256_file(ws / man["delivery_first"]["register_interface"]["manual"])
    assert proof["compiler_profile"] == man["delivery_first"]["compiler_profiles"]["target"]
    assert proof["functional_verification"] == "NOT_ESTABLISHED_BY_LAYOUT_CHECK"
    assert header.read_bytes() == before


def test_typed_pointer_implementation_has_no_undeclared_singleton_requirement(prepared):
    ws, _ = typed(prepared)
    candidate(ws)
    result = check_implementation(ws)
    assert result["verdict"] == "PASS", result


@pytest.mark.parametrize("fault", ["offset", "width", "volatile", "signature", "member", "register", "syntax"])
def test_real_target_compiler_or_manual_rejects_incompatible_interfaces(prepared, fault):
    ws, man = typed(prepared)
    text = GOOD
    cfg = man["delivery_first"]["register_interface"]
    if fault in ("offset", "width", "volatile"):
        source = (ws / cfg["device_header"]).read_text()
        if fault == "offset":
            source = source.replace("volatile uint32_t DR;\n    volatile uint32_t IDR;",
                                    "volatile uint32_t IDR;\n    volatile uint32_t DR;")
            source = source.replace("offsetof(CRC_TypeDef, IDR) == 4U", "offsetof(CRC_TypeDef, IDR) == 0U")
        elif fault == "width":
            source = source.replace("volatile uint32_t IDR;", "volatile uint16_t IDR;")
        else:
            source = source.replace("volatile uint32_t IDR;", "uint32_t IDR;")
        input_file(ws, man, cfg["device_header"], source, "synthetic_negative_control")
    elif fault == "signature":
        text = text.replace("LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)", "LL_CRC_Read_IDR(CRC_TypeDef *CRCx)")
    elif fault == "member":
        cfg["members"][0]["member"] = "NOT_A_MEMBER"
    elif fault == "register":
        cfg["members"][0]["register"] = "CRC_UNKNOWN"
    else:
        text = "this is not C"
    save_manifest(ws, man)
    candidate(ws, text)
    report = check_regmap(ws)
    assert report["verdict"] == "FAIL", report
    assert report["major_findings"], report


@pytest.mark.parametrize("fault", ["schema", "undeclared_header", "undeclared_manual", "undeclared_api",
                                   "type_injection", "member_injection", "duplicate", "unknown_key", "width"])
def test_adapter_contract_refuses_unsupported_or_undeclared_inputs(prepared, fault):
    _, man = typed(prepared)
    cfg = man["delivery_first"]["register_interface"]
    if fault == "schema":
        cfg["schema"] = "unqualified-adapter"
    elif fault.startswith("undeclared"):
        key = {"undeclared_header": "device_header", "undeclared_manual": "manual", "undeclared_api": "api_contract"}[fault]
        cfg[key] = "inputs/unlisted.h"
    elif fault == "type_injection":
        cfg["type_name"] = "CRC_TypeDef); int malicious; /*"
    elif fault == "member_injection":
        cfg["members"][0]["member"] = "IDR); int malicious; /*"
    elif fault == "duplicate":
        cfg["members"].append(dict(cfg["members"][0]))
    elif fault == "unknown_key":
        cfg["skip_checks"] = True
    else:
        cfg["members"][0]["width_bits"] = True
    with pytest.raises(ValueError, match="TYPED_REGISTER_INTERFACE"):
        D.contract(man)


def test_changed_primary_input_fails_instead_of_reusing_a_layout_pass(prepared):
    ws, man = typed(prepared)
    candidate(ws)
    assert check_regmap(ws)["verdict"] == "PASS"
    header = ws / man["delivery_first"]["register_interface"]["device_header"]
    header.chmod(0o600)
    header.write_text(header.read_text() + "\n/* changed immutable input */\n")
    assert check_regmap(ws)["verdict"] == "FAIL"


def test_untrusted_derived_slice_cannot_override_frozen_primary_manual(prepared):
    ws, _ = typed(prepared)
    candidate(ws)
    sections = list((ws / "inputs/sections/RM0486").glob("*CRC_IDR*"))
    assert len(sections) == 1
    sections[0].chmod(0o600)
    old = sections[0].read_text()
    changed = re.sub(r"(Address offset:\s*)0x[0-9A-Fa-f]+", r"\g<1>0x0FC", old)
    assert changed != old
    sections[0].write_text(changed)
    result = check_regmap(ws)
    assert result["verdict"] == "PASS", result
    assert json.loads((ws / "verification/static/typed_register_layout.json").read_text())["members"][0]["offset"] == 4


def test_wrong_behavior_can_pass_layout_but_still_fails_independent_oracle(prepared):
    ws, _ = typed(prepared)
    D.preflight(ws)
    candidate(ws, GOOD.replace("return CRCx->IDR;", "return CRCx->IDR & 0xFFU;"))
    assert check_regmap(ws)["verdict"] == "PASS"
    assert D.verify(ws, 0)["status"] == "FAIL"


def test_unselected_legacy_manifest_retains_existing_register_array_checks(prepared):
    ws, man = typed(prepared)
    del man["delivery_first"]["register_interface"]
    save_manifest(ws, man)
    candidate(ws)
    assert "REGMAP:NO_REGISTER_DEFINES" in check_regmap(ws)["major_findings"]
    assert "IMPL:LL_REG_BLOCK_DECLARATION_MISSING" in check_implementation(ws)["major_findings"]


def test_generic_named_manual_and_16bit_device_are_explicit_inputs(prepared, monkeypatch):
    from forge_factory.layer import profile

    ws, man = typed(prepared)
    custom = copy.deepcopy(profile(ws))
    custom["register_prefix"] = "PORT"
    custom["ll"].update(header="port_access.h", function_prefix="LL_PORT_", void_signatures=True)
    monkeypatch.setattr("forge_factory.peripheral.of_ws", lambda _: custom)
    header = '#include <stdint.h>\ntypedef struct { uint32_t pad[3]; volatile uint16_t DATA; } PortRegs;\n'
    api = ('#include "port_device.h"\nstatic inline void LL_PORT_Write(PortRegs *, uint16_t);\n'
           'static inline uint16_t LL_PORT_Read(const PortRegs *);\n')
    # Include guards matter because the immutable API and candidate share the device header.
    input_file(ws, man, "inputs/port_device.h", "#ifndef PORT_DEVICE_H\n#define PORT_DEVICE_H\n" + header + "#endif\n",
               "synthetic_device")
    input_file(ws, man, "inputs/port_api.h", api, "synthetic_api")
    input_file(ws, man, "inputs/MANUAL42.md",
               "#### 7.1.2 Data register (PORT_DATA)\nAddress offset: 0x0C\nBits 15:0 DATA[15:0]: storage\n",
               "reference_manual_synthetic")
    cfg = man["delivery_first"]
    cfg["candidate_files"] = ["software/ll/port_access.h"]
    cfg["required_functions"] = ["LL_PORT_Write", "LL_PORT_Read"]
    man["operation_scope"].update(functions=cfg["required_functions"], register_fields=["PORT_DATA.DATA"])
    cfg["register_interface"] = {"schema": "forge-c/typed-register-interface/1", "manual": "inputs/MANUAL42.md",
        "device_header": "inputs/port_device.h", "api_contract": "inputs/port_api.h", "type_name": "PortRegs",
        "members": [{"register": "PORT_DATA", "member": "DATA", "width_bits": 16}]}
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        ARCH.replace("LL_CRC_Write_IDR", "LL_PORT_Write").replace("LL_CRC_Read_IDR", "LL_PORT_Read")
        .replace("CRC_IDR", "PORT_DATA").replace("0x004", "0x00C"))
    save_manifest(ws, man)
    target = ws / cfg["candidate_files"][0]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('#ifndef PORT_ACCESS_H\n#define PORT_ACCESS_H\n#include "port_device.h"\n'
                      'static inline void LL_PORT_Write(PortRegs *p, uint16_t v) { p->DATA = v; }\n'
                      'static inline uint16_t LL_PORT_Read(const PortRegs *p) { return p->DATA; }\n#endif\n')
    assert check_regmap(ws)["verdict"] == "PASS"
    assert check_implementation(ws)["verdict"] == "PASS"
    proof = json.loads((ws / "verification/static/typed_register_layout.json").read_text())
    assert proof["members"][0]["offset"] == 12 and proof["members"][0]["width_bits"] == 16
    assert "MANUAL42" in proof["members"][0]["primary_section"]


def test_registered_mcp_aggregate_uses_the_typed_checks(prepared, monkeypatch):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import docs

    ws, _ = typed(prepared)
    candidate(ws)
    for key, value in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws),
                       "FORGE_ROLE": "swe3-author", "FORGE_PHASE": "SWE.3"}.items():
        monkeypatch.setenv(key, value)
    operation = next(op for op in docs.OPERATIONS if op.name == "validate_artifact")
    aggregate = sdk.invoke("forge-docs-mcp", operation, {"check": "swe3_all"})
    assert aggregate["metrics"]["register_map_findings"] == 0, aggregate
    assert aggregate["metrics"]["implementation_findings"] == 0, aggregate
    assert aggregate["artifact_refs"]
    candidate(ws, GOOD.replace("LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)", "LL_CRC_Read_IDR(CRC_TypeDef *CRCx)"))
    negative = sdk.invoke("forge-docs-mcp", operation, {"check": "register_map"})
    assert negative["status"] == "FAIL", negative
