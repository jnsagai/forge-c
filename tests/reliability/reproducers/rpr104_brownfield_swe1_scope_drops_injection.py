"""RPR-104 (Fabro run WO-F014-SWE1-CRCK-20261101-L9, Omniverse2, 2026-11-02): the brownfield ST CRC IDR order ran
SWE.1 only (--stop-after SWE.1); SWE.1 passed, but its graph had no delivery_inject node (built only with SWE.2), so the
order ended without .forge-run/delivery/injection.json and the SWE.2 resume was refused
(RESUME_RECORD_UNREADABLE:injection.json).

Scenario: the real workflow builder for a FROZEN brownfield LL order scoped to SWE.1. Symptom: the graph has no
delivery_inject node."""
import sys

SIG = "a brownfield workflow graph scoped to SWE.1 has no delivery_inject node"


def main() -> int:
    from forge_factory.workflow.builder import build
    dot, _nodes = build("WO-RPR104", layer="LL", trace=True, peripheral="crc", brownfield="FROZEN", stop_after="SWE.1")
    if "swe1_inspect_gate" not in dot:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no SWE.1 graph")
        return 2
    if "delivery_inject [" in dot:
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
