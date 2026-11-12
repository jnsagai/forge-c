"""ReqIF export (SWE1-08) and PlantUML architecture views (SWE2-08): valid outputs pass, broken ones fail."""
import pytest
from forge_factory.inspection.reqif_export import OUT, export, validate
from forge_factory.inspection.views import DYNAMIC, check_views, plantuml_jar
from test_swe2_architecture import ARCH_MIN, DYNAMIC_PUML, STATIC_PUML

REQS = ("# Software requirements\n- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.\n"
        "  - Source: RM0486 p.480\n- **SWR-002** If the HSI ready flag is not set within the timeout, then the RCC driver "
        "shall return HAL_TIMEOUT.\n  - Source: RM0486 p.482\n")


def test_reqif_export_is_xsd_valid_with_trace_relations(tmp_path):
    (tmp_path / "workproducts/SWE.1").mkdir(parents=True)
    (tmp_path / "traceability").mkdir()
    (tmp_path / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
    (tmp_path / "traceability/requirements_to_tests.csv").write_text(
        "requirement_id,test_id,test_file\nSWR-001,UT-001,t.c\nSWR-002,UT-002,t.c\n")
    out = export(tmp_path)
    assert out["verdict"] == "PASS" and out["spec_objects"] == 4, out  # 2 SWR + 2 tests
    xml = (tmp_path / OUT).read_text()
    assert "EVENT" in xml and "UNWANTED" in xml and "RM0486 p.480" in xml and xml.count("<SPEC-RELATION ") == 2
    assert export(tmp_path) and (tmp_path / OUT).read_text() == xml  # deterministic
    (tmp_path / OUT).write_text(xml.replace("<SPEC-OBJECTS>", "<SPEC-OBJECTS><BOGUS/>"))
    assert validate(tmp_path / OUT)["verdict"] == "FAIL"


@pytest.mark.skipif(plantuml_jar() is None, reason="plantuml not installed")
def test_plantuml_views_valid_render_and_broken_views_fail(tmp_path):
    (tmp_path / "workproducts/SWE.2").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.2/software_architecture.md").write_text(ARCH_MIN)
    (tmp_path / "workproducts/SWE.2/architecture_static.puml").write_text(STATIC_PUML)
    (tmp_path / "workproducts/SWE.2/architecture_dynamic.puml").write_text(DYNAMIC_PUML)
    ok = check_views(tmp_path, render=True)
    assert ok["verdict"] == "PASS", ok
    assert (tmp_path / "workproducts/SWE.2/architecture_static.svg").is_file()
    (tmp_path / "workproducts/SWE.2/architecture_dynamic.puml").write_text(
        DYNAMIC_PUML.replace("HAL_TIMEOUT", "HAL_ERROR").replace("->", "-> ->"))
    bad = check_views(tmp_path)["major_findings"]
    assert "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH" in bad and any(f.startswith("VIEWS:SYNTAX:") for f in bad)
    assert any(f.startswith("VIEWS:SYNTAX:" + DYNAMIC + ":line ") for f in bad)
    (tmp_path / "workproducts/SWE.2/architecture_static.puml").unlink()
    assert check_views(tmp_path)["major_findings"][0].startswith("VIEWS:MISSING:static")
