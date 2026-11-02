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
    from forge_factory.workflow.builder import binding_for, build

    _g, nodes = build("WO-T-INSTANCE", layer="LL", trace=True, peripheral="crc")  # the gate's node binding, as SWE.2 tests
    binding_for("WO-T-INSTANCE", str(inst_ws), nodes).dump(inst_ws / ".forge-run/binding.json")
    rep = swe2.visit(_swe1(inst_ws), "m")
    packet = calls[0]
    assert packet["task"] == "interfaces" and "IDR-API.h, whose signatures are fixed" in packet["instructions"]
    assert "first the instance macro CRC" in packet["instructions"]
    assert "extern volatile uint32_t" not in packet["instructions"]
    iface = json.loads((inst_ws / ".forge-run/lrtx/SWE.2/packets/interfaces.json").read_text())
    assert iface["status"] == "VALID"
    assert [p["task"] for p in calls][:2] == ["interfaces", "design"]
    # owner 2026-11-02 ("Status queries only"): the value read LL_CRC_Read_IDR (CRC_IDR.IDR, 32 bits) asks for no
    # invented polling step
    assert rep["status"] == "PASS" and not any("polling loop" in i for i in rep.get("issues") or []), rep
    assert not swe2._status_query(inst_ws, {"returns": "uint32_t", "fields": ["CRC_IDR.IDR"]})
    assert swe2._status_query(inst_ws, {"returns": "uint32_t", "fields": ["CRC_IDR.NOPE"]})  # unknown field: as before
    assert not swe2._status_query(inst_ws, {"returns": "void", "fields": ["CRC_IDR.IDR"]})


# ---- stage 4: register map and SWE.3 -------------------------------------------------------------------------------
WRITE_UNIT = """/**
 * @brief Writes the caller value to the independent data register.
 * @unit SWU-LL-01
 * @spec USPEC-LL-01-01
 */
static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)
{
    CRCx->IDR = InData;
}"""
READ_UNIT = """/**
 * @brief Returns the independent data register.
 * @unit SWU-LL-02
 * @spec USPEC-LL-02-01
 */
static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)
{
    uint32_t value = CRCx->IDR;
    return value;
}"""


def _swe2(ws):
    """SWE.1 fixture + the rendered SWE.2 products and the VALID structured interface checkpoint SWE.3 reads."""
    from forge_factory.lrtx import swe2

    _swe1(ws)
    for rel, text in swe2.render(ws, swe2.normalize_interfaces(ws, IFACE), DESIGN).items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    ck = ws / ".forge-run/lrtx/SWE.2/packets/interfaces.json"
    ck.parent.mkdir(parents=True, exist_ok=True)
    ck.write_text(json.dumps({"status": "VALID", "doc": IFACE}))
    return ws


def _code(ws, units=(WRITE_UNIT, READ_UNIT)):
    """The generated header with the fixture units at the generator's marker (as assemble_code places them)."""
    from forge_factory.inspection import regmap

    assert regmap.generate(ws)["status"] == "PASS"
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"
    text = hdr.read_text()
    marker = regmap.functions_marker(ws)
    hdr.write_text(text.replace(marker, "\n\n".join(units) + "\n\n" + marker, 1))
    return hdr


def test_generated_header_uses_the_pinned_device_header_only_in_instance_mode(inst_ws, legacy_ws):
    from forge_factory.inspection import regmap

    regs = [{"name": "CRC_IDR", "source": "inputs/sections/RM0486/26.4.2_x.md", "offset": 4, "fields": {"IDR": (31, 0)}}]
    inst, legacy = regmap.render(regs, inst_ws), regmap.render(regs, legacy_ws)
    assert '#include "forge_crc_device.h"' in inst and "ll_crc_regs" not in inst and "REG_COUNT" not in inst
    assert "extern volatile uint32_t ll_crc_regs[LL_CRC_REG_COUNT];" in legacy and "forge_crc_device.h" not in legacy
    assert "#define LL_CRC_REG_COUNT 256U" in legacy
    assert "#define LL_CRC_IDR_IDR_MSK 0xFFFFFFFFU" in inst and "#define LL_CRC_IDR_IDR_MSK 0xFFFFFFFFU" in legacy


def test_swe3_unit_task_validates_and_compiles_the_instance_signature(inst_ws, monkeypatch):
    from forge_factory.lrtx import swe3

    ws = _swe2(inst_ws)
    _code(ws, units=())
    us = swe3.units(ws)
    assert swe3._sig(us[0]["function"]) == "static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)"
    doc = {"code": WRITE_UNIT, "spec_items": [{"id": "USPEC-LL-01-01", "behaviour": "writes the caller value to IDR",
                                               "traces": ["SWR-001"]}]}
    assert swe3.validate_code(ws, doc, us[0]) == []
    wrong = {**doc, "code": WRITE_UNIT.replace("CRCx->IDR = InData;", "CRCx->DATA = InData;")}
    assert any(f.startswith("compile:") for f in swe3.validate_code(ws, wrong, us[0]))
    legacy_sig = {**doc, "code": WRITE_UNIT.replace("CRC_TypeDef *CRCx, uint32_t InData", "uint32_t InData")}
    assert "signature must be exactly: static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)" in \
        swe3.validate_code(ws, legacy_sig, us[0])
    seen = []
    real = swe3.S.packet
    monkeypatch.setattr(swe3.S, "packet", lambda **k: seen.append(k["instructions"]) or real(**k))
    swe3.code_packet(ws, us[0], "m")
    assert "CRC_IDR as CRCx->IDR" in seen[0] and "register-block array ll_crc_regs indexed" not in seen[0]


def test_swe3_checks_accept_the_instance_header_and_keep_the_guideline(inst_ws):
    from forge_factory.inspection.guideline import check_workspace
    from forge_factory.inspection.implementation import check_implementation
    from forge_factory.inspection.regmap import check_regmap

    ws = _swe2(inst_ws)
    _code(ws)
    reg = check_regmap(ws)
    assert reg["verdict"] == "PASS" and reg["stats"]["layout_compile"] == "PASS", reg
    assert reg["stats"]["defines_checked"] > 0
    impl = check_implementation(ws)
    assert impl["verdict"] == "PASS", impl
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"
    hdr.write_text(hdr.read_text().replace("LL_CRC_IDR_IDR_POS 0U", "LL_CRC_IDR_IDR_POS 1U"))
    assert check_regmap(ws)["verdict"] == "FAIL"  # the RM-checked defines stay checked in instance mode
    # owner disposition 2026-11-02 ("Exempt declared API"): the API contract's own names CRCx/InData are recorded as
    # dispositions, not GL-ARG-01 violations; an undeclared mixed-case parameter is still a major finding
    g = check_workspace(ws)
    assert not [v for v in g["violations"] if v["severity"] == "major"], g["violations"]
    assert {d["detail"].split("parameter ")[1].split()[0] for d in g["dispositions"]} >= {"CRCx", "InData"}
    assert all(d["disposition"] == "OWNER_ACCEPTED_DECLARED_API_CONTRACT" for d in g["dispositions"])
    hdr.write_text(hdr.read_text().replace("LL_CRC_IDR_IDR_POS 1U", "LL_CRC_IDR_IDR_POS 0U") +
                   "\n__STATIC_INLINE uint32_t LL_CRC_Extra(uint32_t BadName) { return BadName; }\n")
    g = check_workspace(ws)
    assert [v["detail"] for v in g["violations"] if v["rule"] == "GL-ARG-01"] == ["LL_CRC_Extra: parameter BadName not lower case"]


def test_swe3_header_from_the_legacy_path_is_unchanged(legacy_ws):
    from forge_factory.inspection import regmap

    _swe1(legacy_ws)
    from forge_factory.lrtx import swe2

    legacy_iface = {**IFACE, "functions": [{**f, "returns": r, "params": p} for f, r, p in zip(IFACE["functions"], (
        "void", "uint32_t"), ([{"name": "value", "type": "uint32_t"}], []), strict=True)], "calls": [
        {"case": "WRITE_IDR", "function": "LL_CRC_Write_IDR", "args": ["0x12345678U"]},
        {"case": "READ_IDR", "function": "LL_CRC_Read_IDR", "args": []}]}
    for rel, text in swe2.render(legacy_ws, legacy_iface, DESIGN).items():
        (legacy_ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (legacy_ws / rel).write_text(text)
    assert regmap.generate(legacy_ws)["status"] == "PASS"
    text = (legacy_ws / "software/ll/stm32n6xx_ll_crc.h").read_text()
    assert "extern volatile uint32_t ll_crc_regs[LL_CRC_REG_COUNT];" in text and "forge_crc_device" not in text
    md = (legacy_ws / swe2.ARCH).read_text()
    assert "Register block: `extern volatile uint32_t ll_crc_regs[];`" in md and "register-array access" in md


# ---- stage 5: SWE.4 host harness ---------------------------------------------------------------------------------
UT_WRITE = """/** @test UT-001 @verifies USPEC-LL-01-01 */
static void ut_ut_001(void)
{
    uint32_t zero;
    uint32_t ones;
    ut_reset_regs();
    LL_CRC_Write_IDR(CRC, 0x12345678U);
    zero = CRC->IDR;
    LL_CRC_Write_IDR(CRC, 0U);
    ones = CRC->IDR;
    LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU);
    CHECK("UT-001", (zero == 0x12345678U) && (ones == 0U) && (CRC->IDR == 0xFFFFFFFFU) && (CRC->DR == 0U));
}"""


def _swe3(ws):
    """SWE.2 fixture + the generated header with the fixture units + their VALID SWE.3 code checkpoints."""
    from forge_factory.lrtx import visit as V

    _swe2(ws)
    _code(ws)
    for n, (uid, swr) in enumerate((("SWU-LL-01", "SWR-001"), ("SWU-LL-02", "SWR-002")), 1):
        ck = V._ckpt(ws, "SWE.3", f"code:{uid}")
        ck.parent.mkdir(parents=True, exist_ok=True)
        ck.write_text(json.dumps({"status": "VALID", "doc": {"code": "", "spec_items": [
            {"id": f"USPEC-LL-{n:02d}-01", "behaviour": "the unit's IDR behaviour", "traces": [swr]}]}}))
    return ws


def _case(ws, n=0):
    from forge_factory.lrtx import swe3

    u = swe3.units(ws)[n]
    swr = u["swrs"][0]
    return {"ut": f"UT-00{n + 1}", "swr": swr, "statement": "", "unit": u,
            "effects": [e for e in EFFECTS["effects"] if e["swr"] == swr]}


def test_swe4_harness_is_the_ram_instance_only_in_instance_mode(inst_ws, legacy_ws):
    from forge_factory.workflow import scaffold

    rep = scaffold.scaffold(inst_ws)
    text = (inst_ws / rep["file"]).read_text()
    assert rep["instance"] == "forge_host_crc" and "ll_crc_regs" not in text and "REG_COUNT" not in text
    assert "#define FORGE_HOST_DEVICE_IMPLEMENTATION" in text and '#include "stm32n6xx_ll_crc.h"' in text
    assert "(void)memset((void *)&forge_host_crc, 0, sizeof(forge_host_crc));" in text
    assert scaffold.TEST_CASES_MARKER in text and scaffold.TEST_CALLS_MARKER in text
    legacy = scaffold.scaffold(legacy_ws)
    assert "instance" not in legacy
    assert (legacy_ws / legacy["file"]).read_text() == scaffold._for_peripheral(scaffold.HARNESS.replace(
        '#include "stm32n6xx_hal_rcc.h"', '#include "stm32n6xx_ll_rcc.h"'), legacy_ws)


def test_swe4_test_task_validates_and_compiles_on_the_instance(inst_ws, monkeypatch):
    import shutil

    from forge_factory.lrtx import swe4
    from forge_factory.workflow import scaffold

    if not shutil.which("clang"):
        pytest.skip("clang not installed")
    ws = _swe3(inst_ws)
    scaffold.scaffold(ws)
    c = _case(ws)
    seen = []
    real = swe4.S.packet
    monkeypatch.setattr(swe4.S, "packet", lambda **k: seen.append(k["instructions"]) or real(**k))
    swe4.test_packet(ws, c, "m")
    assert "through the instance macro CRC (CRC->IDR for CRC_IDR" in seen[0] and "ll_crc_regs[" not in seen[0]
    doc = {"code": UT_WRITE, "kinds": ["positive", "boundary", "negative"]}
    assert swe4.validate_test(ws, doc, c) == []
    legacy = {**doc, "code": UT_WRITE.replace("CRC->DR == 0U", "ll_crc_regs[0] == 0U")}
    out = swe4.validate_test(ws, legacy, c)
    assert "ll_crc_regs does not exist in instance mode: preset and read registers through CRC-><MEMBER>" in out


def test_swe4_unit_tests_run_on_the_ram_instance(inst_ws, monkeypatch):
    import shutil

    from forge_factory.lrtx import swe4
    from forge_factory.workflow import scaffold

    if not shutil.which("clang"):
        pytest.skip("clang not installed")
    ws = _swe3(inst_ws)
    rel = scaffold.scaffold(ws)["file"]
    (ws / rel).write_text(swe4._with_tests(ws, [("ut_ut_001", UT_WRITE)]))
    r = _invoke(ws, monkeypatch, "forge-tests-mcp", "run_unit", {}, role="swe4-author", phase="SWE.4")
    assert r["status"] == "PASS" and r["metrics"].get("passed") == 1, r
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"  # a wrong implementation fails the same test
    hdr.write_text(hdr.read_text().replace("CRCx->IDR = InData;", "CRCx->IDR = InData & 0xFFFFU;"))
    r = _invoke(ws, monkeypatch, "forge-tests-mcp", "run_unit", {}, role="swe4-author", phase="SWE.4")
    assert r["status"] == "FAIL" and any("UT-001" in i for i in r["issues"]), r


# ---- stage 6: independent oracle and verifiers -------------------------------------------------------------------
UT_READ = """/** @test UT-002 @verifies USPEC-LL-02-01 */
static void ut_ut_002(void)
{
    ut_reset_regs();
    CRC->IDR = 0x87654321U;
    CHECK("UT-002", (LL_CRC_Read_IDR(CRC) == 0x87654321U) && (CRC->IDR == 0x87654321U));
}"""


def _contract(ws):
    from forge_factory.lrtx import swe2

    _swe3(ws)
    calls = json.loads(swe2.render(ws, swe2.normalize_interfaces(ws, IFACE), DESIGN)[swe2.CALLS])
    assert calls["calls"]["WRITE_IDR"]["args"] == ["CRC", "0x12345678U"]
    return ws


def test_independent_oracle_runs_on_the_ram_instance(inst_ws):
    import shutil

    from forge_factory.assurance import oracle_gen

    if not shutil.which("gcc"):
        pytest.skip("gcc not installed")
    ws = _contract(inst_ws)
    inc = [ws / "software/hal", ws / "software/ll"]
    r = oracle_gen.run(ws, inc, [], "stm32n6xx_ll_crc.h")
    assert r["status"] == "PASS", r
    assert [(x[1], x[2], x[3]) for x in r["results"]] == [("SWR-001", "WRITE_IDR", "PASS"), ("SWR-002", "READ_IDR", "PASS")]
    assert '_Static_assert(offsetof(CRC_TypeDef, IDR) == 4U, "RM offset of CRC_IDR");' in r["source"]
    assert "shim_regs" not in r["source"] and "ll_crc_regs" not in r["source"]
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"  # a wrong implementation fails the oracle
    hdr.write_text(hdr.read_text().replace("CRCx->IDR = InData;", "CRCx->IDR = InData & 0xFFFFU;"))
    bad = oracle_gen.run(ws, inc, [], "stm32n6xx_ll_crc.h")
    assert bad["status"] == "FAIL" and ("OR-001", "SWR-001", "WRITE_IDR", "FAIL") in bad["results"], bad
    hdr.write_text(hdr.read_text().replace("CRCx->IDR = InData & 0xFFFFU;", "CRCx->DR = InData;"))
    assert oracle_gen.run(ws, inc, [], "stm32n6xx_ll_crc.h")["status"] == "FAIL"


def test_oracle_states_count_based_cases_not_derivable_in_instance_mode(inst_ws):
    from forge_factory.assurance import oracle_gen

    inst = ll_instance(inst_ws)
    cases = [{"case": "NO_ACCESS", "op": "no_write"},
             {"case": "POLL", "op": "set", "word": 1, "register": "CRC_IDR", "never_ready": True},
             {"case": "OTHER", "op": "write", "word": 2, "register": "CRC_CR"},
             {"case": "WRITE_IDR", "op": "write", "word": 1, "register": "CRC_IDR"}]
    kept, notes = oracle_gen.instance_cases(cases, inst)
    assert [c["case"] for c in kept] == ["WRITE_IDR"]
    assert notes == ["ORACLE_NOT_DERIVABLE:NO_ACCESS:INSTANCE_MODE (register-access count)",
                     "ORACLE_NOT_DERIVABLE:POLL:INSTANCE_MODE (register-access count)",
                     "ORACLE_NOT_DERIVABLE:OTHER:INSTANCE_MODE (CRC_CR not in the declared typed layout)"]


def test_block_array_verifiers_check_typed_instance_code(inst_ws):
    import shutil

    from forge_factory.assurance import register_proof, register_wp, verifiers
    from forge_factory.lrtx import swe4
    from forge_factory.workflow import scaffold

    if not shutil.which("clang"):
        pytest.skip("clang not installed")
    ws = _contract(inst_ws)
    rel = scaffold.scaffold(ws)["file"]
    (ws / rel).write_text(swe4._with_tests(ws, [("ut_ut_001", UT_WRITE), ("ut_ut_002", UT_READ)]))
    sem = verifiers.v_register_semantics(ws)  # review follow-up 2: typed accesses are scanned, not skipped
    assert sem["status"] == "PASS" and not sem["findings"], sem
    conc = verifiers.v_concurrency(ws)
    assert conc["status"] == "PASS", conc
    assert not any("INSTANCE_MODE" in f for f in verifiers.v_arch(ws)["findings"])
    oracle = verifiers.v_oracle(ws)
    assert oracle["status"] == "PASS" and oracle["cases"] == 2, oracle
    api = verifiers.v_api_execution(ws)  # the unit tests build on the pinned device header and run both functions
    if api["status"] != "NOT_SUPPORTED" or "not installed" not in str(api["findings"]):
        assert api["status"] == "PASS", api
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"
    hdr.write_text(hdr.read_text().replace("#define LL_CRC_IDR_IDR_POS 0U", "#define LL_CRC_IDR_IDR_POS 1U"))
    assert verifiers.v_register_semantics(ws)["status"] == "FAIL"  # findings still fail in instance mode
    (ws / "workproducts/SWE.1/register_oracle.json").write_text("{}")  # a SafeC contract file is present
    (ws / register_wp.OBLIGATIONS_FILE).parent.mkdir(parents=True, exist_ok=True)
    (ws / register_wp.OBLIGATIONS_FILE).write_text("{}")
    for mod in (register_proof, register_wp):
        assert mod.prove(ws, [ws / "software/ll"], "stm32n6xx_ll_crc.h")["reason"].startswith("INSTANCE_MODE")
    assert verifiers._target_oracle_findings(ws) == ["LIMITATION:TARGET_ORACLE_NOT_APPLICABLE:INSTANCE_MODE"]


# ---- stage 7: SWE.5 / SWE.6 and the simulator image ---------------------------------------------------------------
INTEGRATION = """#include <stdio.h>
#include <stdint.h>
#include <string.h>
#define FORGE_HOST_DEVICE_IMPLEMENTATION
#include "stm32n6xx_ll_crc.h"
static int failures = 0;
#define CHECK(id, cond) do { if (cond) { printf("%s PASS\\n", (id)); } else { printf("%s FAIL\\n", (id)); failures++; } } while (0)
/** @test IT-001 @verifies IF-01 IF-02 SWC_LL */
static void it_round_trip(void)
{
    LL_CRC_Write_IDR(CRC, 0xA5A5A5A5U);
    CHECK("IT-001", (LL_CRC_Read_IDR(CRC) == 0xA5A5A5A5U) && (CRC->DR == 0U));
}
int main(void)
{
    (void)memset((void *)&forge_host_crc, 0, sizeof(forge_host_crc));
    it_round_trip();
    return (failures == 0) ? 0 : 1;
}
"""
TARGET = """/** @file test_crc_target.c @verifies IF-01 IF-02 */
#include "stm32n6xx_ll_crc.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void) { FORGE_TEST_BEGIN();
  TCHECK(1, CRC->IDR == 0U);
  LL_CRC_Write_IDR(CRC, 0x12345678U);
  TCHECK(2, CRC->IDR == 0x12345678U);
  TCHECK(3, LL_CRC_Read_IDR(CRC) == 0x12345678U);
  LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU);
  TCHECK(4, LL_CRC_Read_IDR(CRC) == 0xFFFFFFFFU);
  FORGE_TEST_END(); return 0; }
"""


def test_swe5_swe6_texts_and_checks_use_the_instance(inst_ws, legacy_ws, monkeypatch):
    from forge_factory.lrtx import swe5, swe6
    from forge_factory.workflow import robot_scaffold

    ws = _swe3(inst_ws)
    seen = []
    real = swe5.S.packet
    monkeypatch.setattr(swe5.S, "packet", lambda **k: seen.append(k["instructions"]) or real(**k))
    swe5.file_packet(ws, "target", "m")
    swe5.file_packet(ws, "integration", "m")
    swe6.scenario_packet(ws, "idr", ["SWR-001"], "m")
    target, integration, scenario = seen
    assert "registers of the instance macro CRC (CRC->IDR for CRC_IDR" in target and "ll_crc_regs[" not in target
    assert "'#define FORGE_HOST_DEVICE_IMPLEMENTATION' directly before" in integration
    assert "volatile uint32_t ll_crc_regs" not in integration and "memset((void *)&forge_host_crc" in integration
    assert "CRC->IDR for CRC_IDR" in scenario and "ll_crc_regs[" not in scenario
    assert swe5.validate_file(ws, "integration", {"code": INTEGRATION}) == []
    out = swe5.validate_file(ws, "integration", {"code": INTEGRATION.replace(
        "#define FORGE_HOST_DEVICE_IMPLEMENTATION\n", "volatile uint32_t ll_crc_regs[6];\n")})
    assert "ll_crc_regs does not exist in instance mode: access registers as CRC-><MEMBER>" in out
    assert any("FORGE_HOST_DEVICE_IMPLEMENTATION" in f for f in out)
    assert swe5.validate_file(ws, "target", {"code": TARGET}) == []
    doc = {"default_code": TARGET.replace("CRC->IDR == 0U", "ll_crc_regs[1] == 0U"), "never_ready_code": "",
           "never_ready_swrs": []}
    assert any("does not exist in instance mode" in f for f in swe6.validate_scenarios(ws, doc, ["SWR-001"]))
    head = robot_scaffold.header(ws)
    assert "# Register access in scenarios: CRC-><MEMBER> & LL_CRC_<REG>_<FIELD>_MSK" in head
    assert "ll_crc_regs[LL_CRC_<REG>_OFFSET / 4U]" in robot_scaffold.header(legacy_ws)


def test_integration_test_runs_on_the_ram_instance(inst_ws, monkeypatch):
    import shutil

    if not shutil.which("clang"):
        pytest.skip("clang not installed")
    ws = _swe3(inst_ws)
    p = ws / "software/tests/integration/test_crc_integration.c"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(INTEGRATION)
    r = _invoke(ws, monkeypatch, "forge-tests-mcp", "run_integration", {}, role="swe5-author", phase="SWE.5")
    assert r["status"] == "PASS" and r["metrics"]["passed"] == 1, r


def test_target_image_builds_and_runs_on_the_simulated_instance(inst_ws, tmp_path):
    import shutil

    from forge_factory.mcp.servers import sim

    if not shutil.which("arm-none-eabi-gcc"):
        pytest.skip("arm-none-eabi-gcc not installed")
    ws = _swe3(inst_ws)
    t = ws / "software/tests/target"
    t.mkdir(parents=True, exist_ok=True)
    (t / "test_crc_target.c").write_text(TARGET)
    ok, _log, errs = sim.build_image(ws, t / "test_crc_target.c", tmp_path / "crc.elf")
    assert ok, errs
    if sim.renode_bin() is None:
        pytest.skip("Renode not installed (image built, not run)")
    res, _out = sim.run_image(sim.renode_bin(), tmp_path / "crc.elf", "default", tmp_path, ws)
    assert res == {"magic_ok": True, "passed": 4, "failed": 0, "done": True, "failed_ids": []}, res


def test_performance_wrappers_take_the_instance_and_the_image_builds(inst_ws, tmp_path):
    import shutil

    from forge_factory import simulation_performance as performance
    from forge_factory.mcp.servers import sim

    if not shutil.which("arm-none-eabi-gcc"):
        pytest.skip("arm-none-eabi-gcc not installed")
    ws = _swe3(inst_ws)
    budget = performance.selected(ws)
    assert budget["test_source"] == "software/tests/target/test_performance.c"
    out = tmp_path / "perf"
    out.mkdir()
    performance.prepare(ws, out)
    decl = (out / "forge_performance_calls.h").read_text()
    assert "void forge_measure_LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData);" in decl
    assert "uint32_t forge_measure_LL_CRC_Read_IDR(const CRC_TypeDef *CRCx);" in decl
    test = ws / budget["test_source"]
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text('#include "stm32n6xx_ll_crc.h"\n#include "forge_target_test.h"\n#include "forge_performance_calls.h"\n'
                    "FORGE_MAILBOX_DEFINE;\nint main(void) { FORGE_TEST_BEGIN();\n"
                    "  forge_measure_LL_CRC_Write_IDR(CRC, 0x5AU);\n"
                    "  TCHECK(1, forge_measure_LL_CRC_Read_IDR(CRC) == 0x5AU);\n  FORGE_TEST_END(); return 0; }\n")
    ok, _log, errs = sim.build_image(ws, test, tmp_path / "perf.elf")
    assert ok, errs


# ---- review follow-up 1: a driver must use its instance argument --------------------------------------------------
BYPASS_WRITE = WRITE_UNIT.replace("    CRCx->IDR = InData;", "    (void)CRCx;\n    CRC->IDR = InData;")
HOST_WRITE = WRITE_UNIT.replace("    CRCx->IDR = InData;", "    (void)CRCx;\n    forge_host_crc.IDR = InData;")
ALIAS_WRITE = WRITE_UNIT.replace("    CRCx->IDR = InData;", "    CRC_TypeDef *p = CRCx;\n    p->IDR = InData;")


@pytest.mark.parametrize("unit", [BYPASS_WRITE, HOST_WRITE, ALIAS_WRITE], ids=["macro", "host_object", "alias"])
def test_ll_body_that_ignores_its_instance_is_refused(inst_ws, unit):
    from forge_factory.inspection.implementation import check_implementation
    from forge_factory.lrtx import swe3

    ws = _swe2(inst_ws)
    _code(ws, units=())
    u = swe3.units(ws)[0]
    doc = {"code": unit, "spec_items": [{"id": "USPEC-LL-01-01", "behaviour": "writes the caller value to IDR",
                                         "traces": ["SWR-001"]}]}
    assert any("INSTANCE_BYPASSED:LL_CRC_Write_IDR" in f for f in swe3.validate_code(ws, doc, u))
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"
    hdr.unlink()
    (ws / ".forge-run/lrtx/SWE.3/generated-header.h").unlink(missing_ok=True)
    _code(ws, units=(unit, READ_UNIT))
    impl = check_implementation(ws)
    assert any(f.startswith("IMPL:INSTANCE_BYPASSED:LL_CRC_Write_IDR") for f in impl["major_findings"]), impl
    assert not any("LL_CRC_Read_IDR" in f for f in impl["major_findings"] if "INSTANCE" in f)


def test_oracle_fails_a_driver_that_writes_the_macro_object_instead_of_its_instance(inst_ws):
    import shutil

    from forge_factory.assurance import oracle_gen

    if not shutil.which("gcc"):
        pytest.skip("gcc not installed")
    ws = _contract(inst_ws)
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"
    hdr.write_text(hdr.read_text().replace("    CRCx->IDR = InData;", "    (void)CRCx;\n    CRC->IDR = InData;"))
    r = oracle_gen.run(ws, [ws / "software/hal", ws / "software/ll"], [], "stm32n6xx_ll_crc.h")
    assert r["status"] == "FAIL" and ("OR-001", "SWR-001", "WRITE_IDR", "FAIL") in r["results"], r
    assert "LL_CRC_Write_IDR(&forge_oracle_inst, 0x12345678U)" in r["source"]


# ---- review follow-up 2: typed register accesses are checked, not skipped ---------------------------------------
def test_oracle_fails_a_write_to_another_instance_register(inst_ws):
    import shutil

    from forge_factory.assurance import oracle_gen

    if not shutil.which("gcc"):
        pytest.skip("gcc not installed")
    ws = _contract(inst_ws)
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"
    hdr.write_text(hdr.read_text().replace("    CRCx->IDR = InData;", "    CRCx->IDR = InData;\n    CRCx->CR = InData;"))
    r = oracle_gen.run(ws, [ws / "software/hal", ws / "software/ll"], [], "stm32n6xx_ll_crc.h")
    assert r["status"] == "FAIL" and ("OR-001", "SWR-001", "WRITE_IDR", "FAIL") in r["results"], r


def test_register_scans_resolve_typed_members_through_the_declared_layout(inst_ws):
    from forge_factory.assurance import hardware, swe12, verifiers

    ws = _contract(inst_ws)
    view = hardware.instance_view("CRCx->IDR = v; x = CRCx->CR;", ll_instance(ws), verifiers._idx(ws), "ll_crc_regs")
    assert view == "ll_crc_regs[1U] = v; x = ll_crc_regs[CRCx_UNDECLARED_MEMBER_CR];"
    hdr = ws / "software/ll/stm32n6xx_ll_crc.h"
    good = hdr.read_text()
    hdr.write_text(good.replace("    CRCx->IDR = InData;", "    CRCx->IDR = InData;\n    CRCx->CR = InData;"))
    sem = verifiers.v_register_semantics(ws)
    assert sem["status"] == "FAIL" and any(f.startswith("UNRESOLVED_REGISTER_INDEX") for f in sem["findings"]), sem
    rmw = good.replace("    CRCx->IDR = InData;", "    CRCx->IDR |= InData;").replace(
        "#endif /* STM32N6XX_LL_CRC_H */", "static inline void LL_CRC_Clear_IDR(CRC_TypeDef *CRCx)\n{\n"
        "    CRCx->IDR &= 0U;\n}\n\n#endif /* STM32N6XX_LL_CRC_H */")
    hdr.write_text(rmw)
    assert swe12.shared_registers(ws) == {"CRC_IDR": ["LL_CRC_Clear_IDR", "LL_CRC_Write_IDR"]}


# ---- review follow-up 3: no resume across instance declarations -------------------------------------------------
@pytest.mark.parametrize("source,new", [("instance", None), (None, "instance"), ("instance", "other")])
def test_resume_across_instance_declarations_is_refused(tmp_path, monkeypatch, source, new):
    import subprocess

    from forge_factory.brownfield.resume import ResumeRefused
    from forge_factory.workorder import resume_from

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    inst = _scope()["instance"]
    other = {**copy.deepcopy(inst), "parameter": "crc"}
    scope = {"instance": inst, "other": other, None: None}

    def man(kind, wo):
        m = {"work_order": wo, "operation_scope": {k: v for k, v in _scope().items() if k != "instance"}}
        if kind:
            m["operation_scope"]["instance"] = scope[kind]
        return m

    src = tmp_path / "state/workorders/WO-SRC/workspace"
    (src / ".forge-run").mkdir(parents=True)
    (src / ".forge-run/manifest.json").write_text(json.dumps(man(source, "WO-SRC")))
    ws = tmp_path / "state/workorders/WO-NEW/workspace"
    (ws / ".forge-run").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    with pytest.raises(ResumeRefused, match="RESUME_INSTANCE_DECLARATION_MISMATCH"):
        resume_from(ws, man(new, "WO-NEW"), "WO-SRC")
    if source == "instance" and new is None:  # the same declaration on both sides resumes as before
        (src / ".forge-run/manifest.json").write_text(json.dumps(man("instance", "WO-SRC")))
        assert resume_from(ws, man("instance", "WO-NEW"), "WO-SRC")[0] == "SWE.1"


# ---- review follow-up 4: the mutation campaign runs on the pinned device header ---------------------------------
def test_mutation_campaign_runs_in_instance_mode(inst_ws):
    import shutil

    from forge_factory.assurance import mutation, verifiers
    from forge_factory.lrtx import swe4
    from forge_factory.workflow import scaffold

    if not shutil.which("gcc"):
        pytest.skip("gcc not installed")
    ws = _contract(inst_ws)
    rel = scaffold.scaffold(ws)["file"]
    (ws / rel).write_text(swe4._with_tests(ws, [("ut_ut_001", UT_WRITE), ("ut_ut_002", UT_READ)]))
    r = verifiers.v_mutation(ws)
    assert r["status"] == "PASS" and r["campaign"]["eligible"] == 2 and r["campaign"]["killed"] == 2, r
    assert r["campaign"]["invalid"] == 0, r
    (ws / rel).write_text(swe4._with_tests(ws, [("ut_ut_001", UT_WRITE)]))  # the read is no longer tested
    weak = verifiers.v_mutation(ws)
    assert weak["status"] == "FAIL" and any("INSTANCE_READ_ZERO" in f for f in weak["findings"]), weak
    assert mutation.instance_ops(None) == []
