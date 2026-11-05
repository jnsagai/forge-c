"""CAPA-139 (WO-F014-SWE3-CRCHAL-20261103-L31C): UNIT:DESIGN_RENDER_FAILED was cut to 80 characters, so the author saw
PlantUML's generic 'No diagram found' and a bare 0-based index, never the syntax error; SWE.3 went STUCK after three
cycles. The finding now names the 1-based file line, its text and, for an activity diagram, the keyword written as an
action - same check, deterministic text, bounded length."""
import json
import shutil
from pathlib import Path

import pytest
from forge_factory.inspection import swtrace

NEEDS_PLANTUML = pytest.mark.skipif(swtrace._plantuml_jar() is None or shutil.which("java") is None,
                                    reason="plantuml not installed")
REQS = ("# Software requirements\n- **SWR-001** When the X enable is requested, the X driver shall set X_CR.EN.\n"
        "  - Source: owner\n")
ARCH = ('@startuml\ncomponent "X_HAL" <<SWC>> as SWC_HAL\ncomponent "X registers" as XR\nnote right of SWC_HAL\n'
        "  Allocated: SWR-001\nend note\nSWC_HAL --> XR : IF-01 register write\n@enduml\n")
UNITS = ("# Unit specifications\n## SWU-HAL-01: X enable\n- SWC: SWC_HAL\n- Functions: HAL_X_Enable\n"
         "- Design: workproducts/SWE.3/detailed_design/SWU-HAL-01.puml\n"
         "- **USPEC-HAL-01-01** Set EN through the register. Traces: SWR-001\n")
HEAD = "@startuml\ntitle SWU-HAL-01 HAL_X_Enable USPEC-HAL-01-01\nstart\n:HAL_X_Enable(x);\n:status = 0U;\n"


def _render_findings(tmp_path: Path, design: str) -> list[str]:
    ws = tmp_path / "WO-T" / "workspace"
    if ws.exists():
        shutil.rmtree(ws)
    for rel, text in {".forge-run/manifest.json": json.dumps({"layer": "HAL"}),
                      "workproducts/SWE.1/software_requirements.md": REQS,
                      "workproducts/SWE.2/architecture_static.puml": ARCH,
                      "workproducts/SWE.3/unit_specifications.md": UNITS,
                      "workproducts/SWE.3/detailed_design/SWU-HAL-01.puml": design}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    return [x for x in swtrace.check_units(ws, render=True, export=False)["major_findings"]
            if x.startswith("UNIT:DESIGN_RENDER_FAILED:")]


def test_location_names_the_one_based_file_line_and_its_text():
    text = "@startuml\nstart\n:a;\n:b\nelse\nstop\n@enduml\n"
    out = swtrace._syntax_location("ERROR\n3\nSyntax Error? (Assumed diagram type: activity)\n", text)
    assert out.startswith("PlantUML: Syntax Error? at line 4: `:b`") and "end it with ';'" in out
    assert "Assumed diagram type" not in out


def test_keyword_as_action_is_named_even_when_plantuml_reports_a_later_line():
    text = HEAD + ":if (x == 0U) then (yes)\n  :return 1U;\nelse (no)\nendif\nstop\n@enduml\n"
    out = swtrace._syntax_location("ERROR\n7\nCannot find if\n", text)
    assert "at line 8: `else (no)`" in out and "line 6: `:if (x == 0U) then (yes)` is an activity keyword" in out
    same = swtrace._syntax_location("ERROR\n5\nSyntax Error?\n", text)
    assert "at line 6: `:if (x == 0U) then (yes)` - an activity keyword written as an action" in same
    assert same.count("line 6") == 1


def test_output_without_a_line_index_keeps_the_previous_text():
    assert swtrace._syntax_location("ACTIVITY\nactivity3\n", "title x\n") == ""
    assert swtrace._syntax_location("", "x") == ""


@NEEDS_PLANTUML
def test_render_finding_carries_the_actionable_part_and_is_bounded(tmp_path):
    bad = HEAD + ":if (x == 0U) then (yes)\n  :return 1U;\nelse (no)\n  :status = 2U;\nendif\nstop\n@enduml\n"
    f = _render_findings(tmp_path, bad)
    assert len(f) == 1 and f[0].startswith("UNIT:DESIGN_RENDER_FAILED:SWU-HAL-01:PlantUML: ")
    assert "line 6: `:if (x == 0U) then (yes)`" in f[0] and "drop the leading ':'" in f[0] and len(f[0]) <= 240
    assert _render_findings(tmp_path, bad) == f  # identical input -> identical finding (STUCK detection compares)


@NEEDS_PLANTUML
def test_valid_design_and_existing_hints_are_unchanged(tmp_path):
    good = ("@startuml\ntitle SWU-HAL-01 HAL_X_Enable\nnote right\n  USPEC: USPEC-HAL-01-01\nend note\nstart\n"
            ":HAL_X_Enable;\nstop\n@enduml\n")
    assert _render_findings(tmp_path, good) == []
    p = tmp_path / "x.puml"
    p.write_text("@startuml\nstart\nif (x\n@enduml\n")
    ok, why = swtrace.render_ok(p)
    assert not ok and "syntax: ERROR 2" in why and "at line 3: `if (x`" in why  # CAPA-033 text kept
    p.write_text("title x\nstart\n:a;\nstop\n")
    assert "must start with @startuml" in swtrace.render_ok(p)[1]
