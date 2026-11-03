"""RPR-124 (Fabro run WO-F014-SWE2-CRCHAL-20261103-L26, local line, Omniverse2, CRC HAL order 0014m on run/gen8d,
2026-11-03): the SWE.2 author was REJECTED twice by VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH and the route ended "BLOCKED
STUCK: identical deterministic rejection twice". inspection/views.py:check_views required the string HAL_TIMEOUT in the
dynamic view of every non-LL work order, but the CRC HAL has no wait and no timeout (config/factory/peripherals/crc.yaml:
"the CRC needs no wait (RM0486 26.3.3) ... so the HAL has no timeout"; hal_wait_rule "No HAL_CRC_ function waits";
hal_dynamic_view lists no timeout path). The author could only pass by inventing a timeout path the HAL does not have.

Scenario: synthetic HAL workspaces in scratch (tracked peripheral profiles of the revision under test, a SWE.2
allocation table and static/dynamic PlantUML views that name the components and the allocated APIs, a dynamic view with
the invalid-parameter HAL_ERROR path and no HAL_TIMEOUT) checked by the real check_views. The pinned PlantUML jar is
hidden (FORGE_DATA_ROOT -> scratch) so only the content rules are exercised; the TOOL_MISSING finding is ignored.
Symptom: the CRC HAL workspace gets VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH. Controls: IWDG and RCC HAL workspaces (HALs
that wait) without HAL_TIMEOUT must still get the finding, and with HAL_TIMEOUT must not; a fix that drops the
finding for a waiting HAL is reported as an error, not as ABSENT."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "the SWE.2 dynamic view of a no-wait HAL (CRC) is rejected for a missing HAL_TIMEOUT path"
FINDING = "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH"

CASES = {  # peripheral -> (HAL component, LL component, allocated HAL functions)
    "crc": ("stm32n6xx_hal_crc", "stm32n6xx_ll_crc", ["HAL_CRC_Init", "HAL_CRC_Calculate", "HAL_CRC_Accumulate"]),
    "iwdg": ("stm32n6xx_hal_iwdg", "stm32n6xx_ll_iwdg", ["HAL_IWDG_Init", "HAL_IWDG_Refresh"]),
    "rcc": ("stm32n6xx_hal_rcc", "stm32n6xx_ll_rcc", ["HAL_RCC_HSI_Enable", "HAL_RCC_HSI_Disable"]),
}


def workspace(root: Path, pid: str, with_timeout: bool) -> Path:
    hal, ll, fns = CASES[pid]
    ws = root / f"{pid}-{'timeout' if with_timeout else 'notimeout'}"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(
        {"work_order": f"WO-RPR-124-{pid}", "peripheral": pid, "layer": "HAL"}))
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    rows = "\n".join(f"| SWR-{i:03d} | {f} |" for i, f in enumerate(fns, 1))
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "# Software architecture\n\n## Requirement allocation table\n\n| SWR | Function |\n|---|---|\n" + rows + "\n")
    (ws / "workproducts/SWE.2/architecture_static.puml").write_text(
        f"@startuml\ncomponent Caller\ncomponent {hal}\ncomponent {ll}\nCaller --> {hal}\n{hal} --> {ll}\n@enduml\n")
    calls = "\n".join(f"Caller -> HAL : {f}()\nHAL -> LL : LL call\nHAL --> Caller : HAL_OK" for f in fns)
    tail = "\nalt never ready\n  HAL --> Caller : HAL_TIMEOUT\nend" if with_timeout else ""
    (ws / "workproducts/SWE.2/architecture_dynamic.puml").write_text(
        f"@startuml\nparticipant Caller\nparticipant \"{hal}\" as HAL\nparticipant \"{ll}\" as LL\n{calls}\n"
        f"alt invalid parameter\n  HAL --> Caller : HAL_ERROR (no register access)\nend{tail}\n@enduml\n")
    return ws


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["FORGE_DATA_ROOT"] = str(root / "no-data-root")  # hide the PlantUML jar: content rules only
        os.environ.pop("FORGE_STATE_DIR", None)
        from forge_factory.inspection.views import check_views

        def findings(pid: str, with_timeout: bool) -> list[str]:
            r = check_views(workspace(root, pid, with_timeout))["major_findings"]
            return [f for f in r if f != "VIEWS:TOOL_MISSING:plantuml"]

        res = {(pid, t): findings(pid, t) for pid in CASES for t in (False, True)}
    for (pid, t), fs in res.items():
        other = [f for f in fs if f != FINDING]
        if other:
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{pid}:{other[:3]}")
            return 2
        if t and FINDING in fs:
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{pid}: a view with HAL_TIMEOUT is flagged")
            return 2
    for pid in ("iwdg", "rcc"):
        if FINDING not in res[(pid, False)]:
            print(f"REPRODUCER_ERROR:CHECK_LOOSENED:{pid}: a waiting HAL view without HAL_TIMEOUT is accepted")
            return 2
    if FINDING in res[("crc", False)]:
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
