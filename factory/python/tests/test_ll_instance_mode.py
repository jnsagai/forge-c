"""Instance mode (operation_scope.instance, forge-c/ll-instance/1): a work order whose scope declares a caller-supplied
peripheral instance gets LL functions that take the instance pointer. The C below is deliberate fixture code (Forge-C
wording), not model output; nothing here is run or release evidence."""
from __future__ import annotations

import copy
import json

import pytest
from forge_factory import operation_scope as OS
from forge_factory import workorder as W
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.layer import ll_instance

INSTANCE = REPO_ROOT / "examples/0014i-st-crc-idr-swe1-aspice-high"
LEGACY = REPO_ROOT / "examples/0014h-st-crc-idr-swe1-aspice"  # the same work order without the declaration
DS = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/DS14791-rev9-stm32n6x5-x7-datasheet.md"
pytestmark = pytest.mark.skipif(not DS.is_file(), reason="owner datasheet input (git-ignored) not present")


def _env(tmp_path, monkeypatch):
    for name in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + name + "_DIR", str(tmp_path / name))
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)


@pytest.fixture
def inst_ws(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    ws, _ = W.prepare(INSTANCE, "WO-T-INSTANCE", purpose="ASPICE_ONLY")
    return ws


@pytest.fixture
def legacy_ws(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    ws, _ = W.prepare(LEGACY, "WO-T-LEGACY", purpose="ASPICE_ONLY")
    return ws


def _manifest(ws):
    return json.loads((ws / ".forge-run/manifest.json").read_text())


def _scope():
    return copy.deepcopy(json.loads((INSTANCE / "workorder.json").read_text())["operation_scope"])


# ---- stage 1: declaration and detection ------------------------------------------------------------------------------
def test_instance_declaration_is_detected_with_api_contract_signatures(inst_ws):
    inst = ll_instance(inst_ws)
    assert inst["parameter"] == "CRCx" and inst["macro"] == "CRC" and inst["host_object"] == "forge_host_crc"
    assert inst["type_name"] == "CRC_TypeDef" and inst["device_header"] == "forge_crc_device.h"
    assert inst["members"] == {"CRC_IDR": "IDR"}
    assert inst["signatures"] == {
        "LL_CRC_Write_IDR": {"returns": "void", "params": [{"name": "CRCx", "type": "CRC_TypeDef *"},
                                                           {"name": "InData", "type": "uint32_t"}]},
        "LL_CRC_Read_IDR": {"returns": "uint32_t", "params": [{"name": "CRCx", "type": "const CRC_TypeDef *"}]}}
    assert list(inst["signatures"]) == _manifest(inst_ws)["operation_scope"]["functions"]


def test_typed_register_checks_select_the_declared_interface_in_instance_mode(inst_ws):
    from forge_factory.inspection import typed_registers as T

    cfg = T.instance_config(inst_ws)
    assert cfg["candidate_files"] == ["software/ll/stm32n6xx_ll_crc.h"]
    assert cfg["include_dirs"] == ["software/ll", "inputs"]
    assert T.selected(inst_ws) == _manifest(inst_ws)["operation_scope"]["instance"]["register_interface"]


def test_work_order_without_declaration_keeps_the_legacy_path(legacy_ws):
    from forge_factory.inspection import typed_registers as T

    assert ll_instance(legacy_ws) is None
    assert T.instance_config(legacy_ws) is None and T.selected(legacy_ws) is None
    assert T.check_selected(legacy_ws) is None
    assert "instance" not in _manifest(legacy_ws)["operation_scope"]


@pytest.mark.parametrize("fault", ["schema", "unknown_key", "missing_key", "bad_parameter", "same_names",
                                   "interface_schema", "unmapped_register"])
def test_instance_declaration_is_validated_strictly(fault):
    scope = _scope()
    inst = scope["instance"]
    if fault == "schema":
        inst["schema"] = "forge-c/ll-instance/0"
    elif fault == "unknown_key":
        inst["skip_checks"] = True
    elif fault == "missing_key":
        del inst["host_object"]
    elif fault == "bad_parameter":
        inst["parameter"] = "CRCx); int x; /*"
    elif fault == "same_names":
        inst["macro"] = inst["parameter"]
    elif fault == "interface_schema":
        inst["register_interface"]["schema"] = "other"
    else:
        scope["register_fields"].append("CRC_DR.DR")
    with pytest.raises(ValueError, match="OPERATION_SCOPE_INSTANCE"):
        OS.validate(scope)


def test_instance_interface_must_name_declared_inputs():
    scope = _scope()
    inputs = [{"path": "inputs/RM0486-rev4-ch26-crc.md", "role": "reference_manual_crc_chapter"},
              {"path": "inputs/forge_crc_device.h", "role": "fixture"}]  # IDR-API.h not declared
    with pytest.raises(ValueError, match="TYPED_REGISTER_INTERFACE_INPUT_NOT_DECLARED:api_contract"):
        OS.validate_instance_inputs(scope["instance"], inputs)


@pytest.mark.parametrize("fault", ["api_changed", "api_mismatch", "first_parameter", "device_mismatch", "layer"])
def test_declared_but_broken_instance_contract_raises_instead_of_falling_back(inst_ws, fault):
    man = _manifest(inst_ws)
    api = inst_ws / "inputs/IDR-API.h"
    text = api.read_text()
    if fault == "layer":
        man["layer"] = "HAL"
    elif fault == "device_mismatch":
        man["operation_scope"]["instance"]["host_object"] = "forge_other_crc"
    else:
        if fault == "api_mismatch":
            text = text.replace("static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx);\n", "")
        elif fault == "first_parameter":
            text = text.replace("LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)", "LL_CRC_Read_IDR(const CRC_TypeDef *p)")
        else:
            text += "\n"
        api.chmod(0o644)
        api.write_text(text)
        if fault != "api_changed":  # a re-declared input: the hash matches, the content does not fit the scope
            entry = next(i for i in man["inputs"] if i["path"] == "inputs/IDR-API.h")
            entry["sha256"] = sha256_file(api)
    (inst_ws / ".forge-run/manifest.json").write_text(json.dumps(man))
    with pytest.raises(ValueError, match="OPERATION_SCOPE_INSTANCE"):
        ll_instance(inst_ws)
    from forge_factory.inspection import typed_registers as T

    report = T.check_selected(inst_ws)  # the verifier reports the broken contract as a FAIL, never the legacy path
    assert report["verdict"] == "FAIL" and report["major_findings"][0].startswith("TYPED_REGMAP:OPERATION_SCOPE_INSTANCE")


@pytest.mark.parametrize("change", ["layer", "delivery_first"])
def test_preparation_refuses_instance_mode_outside_a_greenfield_ll_work_order(tmp_path, monkeypatch, change):
    _env(tmp_path, monkeypatch)

    class _Spec:  # the 0014i spec as read by prepare, with one field changed (no example file is written)
        def __getattr__(self, name):
            return getattr(json, name)

        @staticmethod
        def loads(text, *a, **k):
            d = json.loads(text, *a, **k)
            if isinstance(d, dict) and d.get("schema") == "forge-c/work-order-spec/0.4":
                d.update({"layer": "LL+HAL"} if change == "layer" else {"delivery_first": {}})
            return d

    monkeypatch.setattr(W, "json", _Spec())
    with pytest.raises(ValueError, match="OPERATION_SCOPE_INSTANCE_REQUIRES_GREENFIELD_LL"):
        W.prepare(INSTANCE, "WO-T-INSTANCE-REFUSED", purpose="ASPICE_ONLY")


# ---- stage 2: include flags --------------------------------------------------------------------------------------------
FIXTURE_LL = """#ifndef FIXTURE_LL_CRC_H
#define FIXTURE_LL_CRC_H
#include <stdint.h>
#include "forge_crc_device.h"
static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)
{
    CRCx->IDR = InData;
}
static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)
{
    return CRCx->IDR;
}
#endif
"""


def _write_ll(ws, text=FIXTURE_LL):
    (ws / "software/ll").mkdir(parents=True, exist_ok=True)
    (ws / "software/src").mkdir(parents=True, exist_ok=True)
    (ws / "software/ll/stm32n6xx_ll_crc.h").write_text(text)
    (ws / "software/src/stm32n6xx_ll_crc.c").write_text('#include "stm32n6xx_ll_crc.h"\n')


def _invoke(ws, monkeypatch, server, op, args, role="swe3-author", phase="SWE.3"):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import analysis, build, tests

    module = {"forge-build-mcp": build, "forge-analysis-mcp": analysis, "forge-tests-mcp": tests}[server]
    for key, value in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_ROLE": role,
                       "FORGE_PHASE": phase}.items():
        monkeypatch.setenv(key, value)
    return sdk.invoke(server, next(o for o in module.OPERATIONS if o.name == op), args)


def test_instance_flags_only_in_instance_mode(inst_ws, legacy_ws):
    from forge_factory.layer import instance_flags

    inputs = str(inst_ws.resolve() / "inputs")
    assert instance_flags(inst_ws, host=False) == ["-isystem", inputs]
    assert instance_flags(inst_ws, host=True) == ["-isystem", inputs, "-DFORGE_HOST_BUILD=1"]
    assert instance_flags(legacy_ws, host=False) == [] and instance_flags(legacy_ws, host=True) == []


def test_tool_include_lists_are_unchanged_without_the_declaration(inst_ws, legacy_ws):
    from forge_factory.brownfield.cmsis import host_flags, target_flags
    from forge_factory.delivery_first import include_flags
    from forge_factory.mcp.sdk import ToolContext
    from forge_factory.mcp.servers import analysis, build

    for ws in (inst_ws, legacy_ws):
        _write_ll(ws)
    ctx = ToolContext("t", "t", "swe3-author", "SWE.3", legacy_ws.resolve(), "t")
    dirs = [f"-I{legacy_ws.resolve() / d}" for d in build.INCLUDE_DIRS if (legacy_ws / d).is_dir()]
    for prof in ("target-cm55-gcc", "host-clang"):
        vendor = target_flags(legacy_ws) if prof.startswith("target") else host_flags(legacy_ws)
        assert build.includes(ctx, prof) == vendor + include_flags(legacy_ws) + dirs
    assert analysis.incs(ctx) == analysis.incs(ctx, cppcheck=True) == host_flags(legacy_ws) + dirs
    ictx = ToolContext("t", "t", "swe3-author", "SWE.3", inst_ws.resolve(), "t")
    inputs = str(inst_ws.resolve() / "inputs")
    assert build.includes(ictx, "target-cm55-gcc")[:2] == ["-isystem", inputs]
    assert analysis.incs(ictx)[:2] == ["-isystem", inputs]
    assert analysis.incs(ictx, cppcheck=True)[:3] == ["-I", inputs, f"--suppress=*:{inputs}/*"]


def test_instance_header_compiles_and_analyses_on_the_pinned_device_header(inst_ws, legacy_ws, monkeypatch):
    import shutil

    if not all(shutil.which(t) for t in ("arm-none-eabi-gcc", "clang", "cppcheck")):
        pytest.skip("toolchain not installed")
    _write_ll(inst_ws)
    for prof in ("target-cm55-gcc", "host-clang"):
        r = _invoke(inst_ws, monkeypatch, "forge-build-mcp", "compile", {"profile": prof})
        assert r["status"] == "PASS", r
    cpp = _invoke(inst_ws, monkeypatch, "forge-analysis-mcp", "cppcheck", {})
    assert cpp["status"] in ("PASS", "FAIL") and cpp["metrics"], cpp
    assert not [i for i in cpp["issues"] if "forge_crc_device.h" in i or "IDR-API.h" in i], cpp
    _write_ll(legacy_ws)  # the same header without the declaration: the pinned input is not on any include path
    r = _invoke(legacy_ws, monkeypatch, "forge-build-mcp", "compile", {"profile": "target-cm55-gcc"})
    assert r["status"] == "FAIL", r


# ---- stage 3: SWE.2 ------------------------------------------------------------------------------------------------
REQS = """# Software requirements

## Functional

- **SWR-001** When the caller requests an IDR write with a valid accessible CRC instance, the CRC LL driver shall write the supplied 32-bit value to CRC_IDR.IDR.
- **SWR-002** When the caller requests an IDR read with a valid accessible CRC instance, the CRC LL driver shall return the current 32-bit value of CRC_IDR.IDR.
- **SWR-003** While no LL function has been called after reset, the CRC LL driver shall not write any CRC register.
"""
EFFECTS = {"schema": "forge-c/register-effects/1", "effects": [
    {"case": "WRITE_IDR", "swr": "SWR-001", "register": "CRC_IDR", "field": "IDR", "op": "write", "value": "0x12345678"},
    {"case": "READ_IDR", "swr": "SWR-002", "register": "CRC_IDR", "field": "IDR", "op": "no_write"}]}
IFACE = {"functions": [
    {"name": "LL_CRC_Write_IDR", "operation": "writes the 32-bit value to CRC_IDR", "fields": ["CRC_IDR.IDR"]},
    {"name": "LL_CRC_Read_IDR", "operation": "returns the 32-bit value of CRC_IDR", "fields": ["CRC_IDR.IDR"]}],
    "allocation": [{"swr": "SWR-001", "functions": ["LL_CRC_Write_IDR"], "responsibility": "IDR write"},
                   {"swr": "SWR-002", "functions": ["LL_CRC_Read_IDR"], "responsibility": "IDR read"}],
    "calls": [{"case": "WRITE_IDR", "function": "LL_CRC_Write_IDR", "args": ["CRC", "0x12345678U"]},
              {"case": "READ_IDR", "function": "LL_CRC_Read_IDR", "args": ["CRC"]}]}
DESIGN = {"components": "The single developed component SWC_LL owns two stateless IDR register operations; the caller "
                        "owns the CRC instance, its clock, power, security and access setup.",
          "register_access": "Volatile typed accesses through the caller's CRC_TypeDef instance; CRC_IDR takes "
                             "whole-register writes and plain reads; clocks and reset belong to the integration.",
          "timing_and_error_handling": "No waiting and no error codes at LL level; every function is one register "
                                       "operation and invalid instances are outside the supported domain.",
          "memory_and_stack": "Flash at most 4096 B, static RAM 64 B budget with 0 B used (no state), stack at most "
                              "128 B per call: only automatic temporaries.",
          "concurrency_and_reentrancy": "The LL is reentrant (no state); callers serialise access to one instance and "
                                        "do not share it with an ISR without their own protection.",
          "safety_and_dependencies": "The LL provides no safety mechanism or degraded state of its own; it depends on "
                                     "the caller for a valid accessible instance.",
          "decisions": ["Header-only static inline LL on the caller's typed instance."],
          "sequences": [{"title": "Write and read IDR", "steps": [
              {"function": "LL_CRC_Write_IDR", "repeat_until": "", "note": ""},
              {"function": "LL_CRC_Read_IDR", "repeat_until": "", "note": ""}]}]}


def _swe1(ws):
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
    (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps(EFFECTS))
    return ws


def _idx(ws):
    from forge_factory.assurance.hardware import index

    return index(ws / "inputs/sections/RM0486")


def test_swe2_schema_takes_signatures_from_the_api_contract_only_in_instance_mode(inst_ws, legacy_ws):
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe2

    schema = swe2.interfaces_schema(_swe1(inst_ws))
    item = schema["properties"]["functions"]["items"]
    assert set(item["required"]) == {"name", "operation", "fields"} and "params" not in item["properties"]
    assert item["properties"]["name"]["enum"] == ["LL_CRC_Write_IDR", "LL_CRC_Read_IDR"]
    assert S.validate(IFACE, schema) == []
    with_sig = copy.deepcopy(IFACE)
    with_sig["functions"][0]["params"] = [{"name": "value", "type": "uint32_t"}]
    assert S.validate(with_sig, schema)  # the model cannot restate (or change) a signature
    assert swe2.interfaces_schema(_swe1(legacy_ws)) is swe2.INTERFACES_SCHEMA
    doc = swe2.normalize_interfaces(inst_ws, IFACE)
    assert doc["functions"][0]["params"] == [{"name": "CRCx", "type": "CRC_TypeDef *"},
                                             {"name": "InData", "type": "uint32_t"}]
    assert doc["functions"][1]["returns"] == "uint32_t"
    assert swe2.normalize_interfaces(legacy_ws, IFACE) is IFACE
    assert swe2._sig(doc["functions"][1]) == "static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)"


def test_swe2_call_contract_checks_the_instance_argument_and_the_value(inst_ws):
    from forge_factory.lrtx import swe2

    ws = _swe1(inst_ws)
    good = swe2.normalize_interfaces(ws, IFACE)
    assert swe2.validate_interfaces(ws, good, _idx(ws)) == []
    bad = copy.deepcopy(IFACE)
    bad["calls"][0]["args"] = ["0x12345678U", "CRC"]
    bad["calls"][1]["args"] = ["CRCx"]
    out = swe2.validate_interfaces(ws, swe2.normalize_interfaces(ws, bad), _idx(ws))
    assert "case WRITE_IDR: the first argument must be the instance macro CRC" in out
    assert "case READ_IDR: the first argument must be the instance macro CRC" in out
    assert "case WRITE_IDR: the argument must be the case value 0x12345678" in out
    missing = copy.deepcopy(IFACE)
    missing["functions"][1]["name"] = "LL_CRC_ReadData32"
    missing["allocation"][1]["functions"] = ["LL_CRC_ReadData32"]
    missing["calls"][1]["function"] = "LL_CRC_ReadData32"
    out = swe2.validate_interfaces(ws, swe2.normalize_interfaces(ws, missing), _idx(ws))
    assert any(f.startswith("function LL_CRC_ReadData32 is not declared by the API contract IDR-API.h") for f in out)
    assert "function LL_CRC_Read_IDR of the API contract IDR-API.h is not defined" in out


def test_swe2_renders_the_instance_architecture_and_the_call_contract_compiles(inst_ws):
    import shutil

    from forge_factory.assurance import register_contract as RC
    from forge_factory.lrtx import swe2

    ws = _swe1(inst_ws)
    files = swe2.render(ws, swe2.normalize_interfaces(ws, IFACE), DESIGN)
    md = files[swe2.ARCH]
    assert "| static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData) |" in md
    assert "| static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx) |" in md
    assert "ll_crc_regs" not in md and "register-array" not in md
    assert "CRCx->IDR" in md and "forge_host_crc" in md and "| CRC_IDR | 0x04 |" in md
    assert "Caller -> LL : LL_CRC_Write_IDR(CRCx, InData)" in files[swe2.DYNAMIC]
    assert json.loads(files[swe2.CALLS])["calls"]["WRITE_IDR"]["args"] == ["CRC", "0x12345678U"]
    for rel, text in files.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    assert RC.check_calls(ws) == []
    if not shutil.which("gcc"):
        pytest.skip("gcc not installed")
    assert RC.check_compiles(ws, [], "IDR-API.h") == []
    assert swe2.self_check(ws) == []  # the unchanged SWE.2 gates accept the instance architecture
    calls = json.loads((ws / swe2.CALLS).read_text())
    calls["calls"]["READ_IDR"]["args"] = ["CRC", "1U"]  # one argument too many for the declared signature
    (ws / swe2.CALLS).write_text(json.dumps(calls))
    assert RC.check_compiles(ws, [], "IDR-API.h")[0].startswith("CONTRACT_CALL_DOES_NOT_COMPILE")


def test_swe2_gate_compiles_the_instance_call_contract(inst_ws, legacy_ws, monkeypatch):
    from forge_factory.assurance import register_contract as RC
    from forge_factory.inspection import gate
    from forge_factory.inspection.engine import Store

    seen = []
    monkeypatch.setattr(RC, "check_calls", lambda ws: [])
    monkeypatch.setattr(RC, "check_compiles", lambda ws, inc, hdr: seen.append((ws, hdr)) or ["CONTRACT_CALL_X"])
    reply = json.dumps({"status": "PASS", "artifacts": [], "issues": [], "next_action": "next"})
    for ws in (inst_ws, legacy_ws):
        _swe1(ws)
        gate.step_author(Store(ws), "SWE.2", reply)
    assert seen == [(inst_ws, "IDR-API.h")]  # greenfield without the declaration: no SWE.2 compile, as before


def _scripted(answers, calls):
    from forge_factory.lrtx import structured as S

    def call(p, **_k):
        calls.append(p)
        doc = answers[p["task"]]
        doc = doc(p) if callable(doc) else doc
        return {"doc": json.loads(json.dumps(doc)), "errors": S.validate(doc, p["output_schema"]),
                "usage": {"prompt_tokens": 1000, "completion_tokens": 200}, "wall_ms": 1.0, "finish_reason": "stop"}
    return call


def test_structured_swe2_interface_task_in_instance_mode(inst_ws, monkeypatch):
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe2

    calls = []
    monkeypatch.setattr(S, "call", _scripted({"interfaces": IFACE, "design": DESIGN}, calls))
    rep = swe2.visit(_swe1(inst_ws), "m")
    packet = calls[0]
    assert packet["task"] == "interfaces" and "IDR-API.h, whose signatures are fixed" in packet["instructions"]
    assert "first the instance macro CRC" in packet["instructions"]
    assert "extern volatile uint32_t" not in packet["instructions"]
    iface = json.loads((inst_ws / ".forge-run/lrtx/SWE.2/packets/interfaces.json").read_text())
    assert iface["status"] == "VALID"
    assert [p["task"] for p in calls][:2] == ["interfaces", "design"]
    # SEPARATE DEFECT (not changed here, reported): validate_design asks for a caller-bounded polling loop whenever a
    # function returns uint32_t, so the value read LL_CRC_Read_IDR draws an invented polling step.
    assert rep["status"] == "FAILED" and any("polling loop" in i for i in rep["issues"]), rep
