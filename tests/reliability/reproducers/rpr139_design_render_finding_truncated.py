"""RPR-139 (local run WO-F014-SWE3-CRCHAL-20261103-L31C, Omniverse2, 2026-11-03): SWE.3 was BLOCKED (STUCK after three
cycles) on UNIT:DESIGN_RENDER_FAILED for all four unit designs, each reading only "Some diagram description contains
errors No diagram found; syntax: ERROR 5 Synta". inspection/swtrace.check_units cut render_ok's text to 80 characters,
so the author got PlantUML's generic stderr but not the syntax error, and the bare "5" is PlantUML's 0-based index (file
line 6). The offending line, `:if (...) then (yes)` (an activity `if` written as an action), was never shown.

Scenario (synthetic workspace in a scratch dir; needs java + the pinned PlantUML jar): one SWE.3 unit whose design has
`:if (x == 0U) then (yes)` on file line 6, through the real check_units(render=True). Symptom: the finding does not
name file line 6 and that line's text. Controls: a valid design gives no finding; a design without @startuml keeps the
existing @startuml hint in render_ok (a loosened check is an error, not ABSENT)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "the design render finding omits the PlantUML syntax error line and its text"
REQS = ("# Software requirements\n- **SWR-001** When the X enable is requested, the X driver shall set X_CR.EN.\n"
        "  - Source: owner\n")
ARCH = ('@startuml\ncomponent "X_HAL" <<SWC>> as SWC_HAL\ncomponent "X registers" as XR\nnote right of SWC_HAL\n'
        "  Allocated: SWR-001\nend note\nSWC_HAL --> XR : IF-01 register write\n@enduml\n")
UNITS = ("# Unit specifications\n## SWU-HAL-01: X enable\n- SWC: SWC_HAL\n- Functions: HAL_X_Enable\n"
         "- Design: workproducts/SWE.3/detailed_design/SWU-HAL-01.puml\n"
         "- **USPEC-HAL-01-01** Set EN through the register. Traces: SWR-001\n")
GOOD = ("@startuml\ntitle SWU-HAL-01 HAL_X_Enable\nnote right\n  USPEC: USPEC-HAL-01-01\nend note\nstart\n"
        ":HAL_X_Enable;\nstop\n@enduml\n")
# file line 6 is the `:if` (1-based); PlantUML's -syntax index for it is 5
BAD = ("@startuml\ntitle SWU-HAL-01 HAL_X_Enable USPEC-HAL-01-01\nstart\n:HAL_X_Enable(x);\n:status = 0U;\n"
       ":if (x == 0U) then (yes)\n  :return 1U;\nelse (no)\n  :status = 2U;\nendif\nstop\n@enduml\n")
BAD_LINE = ":if (x == 0U) then (yes)"


def findings(td: Path, design: str) -> list[str]:
    from forge_factory.inspection import swtrace

    ws = td / "WO-T" / "workspace"
    if ws.exists():
        shutil.rmtree(ws)
    files = {".forge-run/manifest.json": json.dumps({"layer": "HAL"}),
             "workproducts/SWE.1/software_requirements.md": REQS,
             "workproducts/SWE.2/architecture_static.puml": ARCH,
             "workproducts/SWE.3/unit_specifications.md": UNITS,
             "workproducts/SWE.3/detailed_design/SWU-HAL-01.puml": design}
    for rel, text in files.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    return [x for x in swtrace.check_units(ws, render=True, export=False)["major_findings"]
            if x.startswith("UNIT:DESIGN_RENDER_FAILED:")]


def main() -> int:
    from forge_factory.inspection import swtrace

    if swtrace._plantuml_jar() is None or shutil.which("java") is None:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:PlantUML (java + pinned jar) not available")
        return 2
    with tempfile.TemporaryDirectory() as tdn:
        td = Path(tdn)
        good = findings(td, GOOD)
        bad = findings(td, BAD)
        p = td / "nostart.puml"
        p.write_text("title x\nstart\n:a;\nstop\n")
        nostart = swtrace.render_ok(p)
    if good:
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:valid design not rendered: {good[:1]}")
        return 2
    if nostart[0] or "must start with @startuml" not in nostart[1]:
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:@startuml hint control lost: {nostart[1][:120]}")
        return 2
    if len(bad) != 1:
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:expected one render finding, got {bad[:2]}")
        return 2
    if not ("line 6" in bad[0] and BAD_LINE in bad[0]):
        print("observed: " + bad[0][:240])
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
