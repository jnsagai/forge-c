"""CAPA-229 (owner SWE.2 review 2026-11-11): WWDG HAL L35 passed SWE.2 with 0 findings although its static view drew the
HAL straight to the register block (IF-02), its dynamic view had a return arrow outside every function block and a
return arrow from the Caller, and a scratch tmp_test.puml stayed in the work products. The SWE2-08 view check and the
SWE2-09 component check now find these, and matrix 1 traces every requirement to its component AND interfaces (owner:
"add the interface allocation to matrix 1"). No checklist item changes (CAPA-133: verified lineages keep their verdicts)."""
import json

from forge_factory.inspection import swtrace as T
from forge_factory.inspection import views as V

L35_STATIC = """@startuml WWDG_HAL_Architecture_Static
component "WWDG_HAL\\nstm32n6xx_hal_wwdg" <<SWC>> as SWC_HAL
component "WWDG_LL\\nstm32n6xx_ll_wwdg" <<SWC>> as SWC_LL
component "WWDG\\n0x50002C00" as WWDG
SWC_HAL --> SWC_LL : IF-01 LL_WWDG_* accessors
SWC_HAL --> WWDG : IF-02 register access (LL instance WWDG)
SWC_LL --> WWDG : IF-03 register block
note right of SWC_HAL
Allocated: SWR-001, SWR-002, SWR-003
end note
@enduml
"""
L35_DYNAMIC = """@startuml WWDG_HAL_Architecture_Dynamic
participant Caller
participant "stm32n6xx_hal_wwdg" as HAL
participant "stm32n6xx_ll_wwdg" as LL
participant "WWDG" as WWDG
group HAL_WWDG_Init
  HAL -> LL : LL_WWDG_SetPrescaler
  LL --> WWDG : WWDG_CFR.WDGTB
  return HAL_OK
end
  HAL --> Caller : return HAL_ERROR (parameter check)
group HAL_WWDG_Refresh
  HAL -> LL : LL_WWDG_SetCounter
  LL --> WWDG : WWDG_CR.T
end
group Invalid parameter
  Note over Caller,WWDG : no register access
  Caller --> HAL : return HAL_ERROR
end
@enduml
"""
GOOD_STATIC = L35_STATIC.replace("SWC_HAL --> WWDG : IF-02 register access (LL instance WWDG)\n", "")
GOOD_DYNAMIC = (L35_DYNAMIC.replace("  HAL --> Caller : return HAL_ERROR (parameter check)\n", "")
                .replace("Caller --> HAL : return HAL_ERROR", "HAL --> Caller : HAL_ERROR"))
ARCH = """# Software architecture

## Requirement allocation table

| SWR | Function |
| --- | --- |
| SWR-001 | `HAL_WWDG_Init` |
| SWR-002 | `HAL_WWDG_Refresh` |
| SWR-003 | all `HAL_WWDG_*` (flash <= 4096 B) |
"""
REQS = """# Software requirements
- **SWR-001** The WWDG HAL shall write the window.
- **SWR-002** The WWDG HAL shall write the counter.
- **SWR-003** The WWDG HAL code shall occupy at most 4096 bytes of flash.
"""


def ws_of(tmp_path, static, dynamic, extra=()):
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": "wwdg", "work_order": "W"}))
    d = ws / "workproducts/SWE.2"
    d.mkdir(parents=True)
    (d / "architecture_static.puml").write_text(static)
    (d / "architecture_dynamic.puml").write_text(dynamic)
    (d / "software_architecture.md").write_text(ARCH)
    for name in extra:
        (d / name).write_text("@startuml\n@enduml\n")
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
    return ws


def ours(findings):
    return sorted(f.split(":line")[0] for f in findings
                  if f.startswith(("VIEWS:STRAY", "VIEWS:MESSAGE_OUTSIDE", "VIEWS:RETURN_FROM", "VIEWS:HAL_BYPASSES",
                                   "VIEWS:STATIC_MISSING_INTERFACE", "VIEWS:DYNAMIC_MISSING_API", "ARCH:HAL_BYPASSES")))


def test_the_l35_views_are_found(tmp_path):
    ws = ws_of(tmp_path, L35_STATIC, L35_DYNAMIC, extra=("tmp_test.puml",))
    f = ours(V.check_views(ws)["major_findings"]) + ours(T.check_architecture_model(ws)["major_findings"])
    assert "VIEWS:STRAY_PLANTUML:tmp_test.puml" in f
    assert "VIEWS:MESSAGE_OUTSIDE_FUNCTION_BLOCK" in f and "VIEWS:RETURN_FROM_CALLER" in f
    assert "ARCH:HAL_BYPASSES_LL:SWC_HAL->WWDG" in f


def test_a_hal_drawn_only_through_its_ll_passes_the_new_rules(tmp_path):
    ws = ws_of(tmp_path, GOOD_STATIC, GOOD_DYNAMIC)
    assert ours(V.check_views(ws)["major_findings"]) == []
    assert ours(T.check_architecture_model(ws)["major_findings"]) == []


def test_a_hal_message_to_the_registers_and_a_missing_static_interface_are_found(tmp_path):
    dyn = GOOD_DYNAMIC.replace("HAL -> LL : LL_WWDG_SetCounter", "HAL -> WWDG : WWDG_CR.T")
    sta = GOOD_STATIC.replace("SWC_LL --> WWDG : IF-03 register block\n", "")
    f = ours(V.check_views(ws_of(tmp_path, sta, dyn))["major_findings"])
    assert "VIEWS:HAL_BYPASSES_LL" in f and "VIEWS:STATIC_MISSING_INTERFACE:LL-REGISTERS" in f


def test_every_allocated_hal_api_has_a_sequence(tmp_path):
    dyn = GOOD_DYNAMIC.replace("group HAL_WWDG_Refresh", "group Refresh")
    f = ours(V.check_views(ws_of(tmp_path, GOOD_STATIC, dyn))["major_findings"])
    assert f == ["VIEWS:DYNAMIC_MISSING_API:HAL_WWDG_Refresh"]


def test_matrix_1_traces_requirements_to_component_and_interfaces(tmp_path):
    ws = ws_of(tmp_path, GOOD_STATIC, GOOD_DYNAMIC)
    T.build_all(ws, upto="SWE.2", write={1}, render=False, doxygen=False, export=False)
    rows = (ws / "workproducts/SWE.2/traceability/matrix_1_swr_to_architecture.csv").read_text().splitlines()
    assert rows[0] == "swr,swc,interfaces,status"
    assert "SWR-001,SWC_HAL,IF-01,ALLOCATED" in rows and "SWR-003,SWC_HAL,COMPONENT_LEVEL,ALLOCATED" in rows
