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
