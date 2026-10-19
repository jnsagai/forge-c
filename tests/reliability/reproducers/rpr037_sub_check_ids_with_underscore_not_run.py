"""RPR-037 (r117): the integration program printed only sub-checks such as 'IT-005-ADC12_EN PASS'; the executed-result
parser did not accept '_' in sub-ids, so Matrix 5 marked IT-005/IT-006 NOT_RUN and the SWE.5 inspector rejected the
contradiction until the rework budget was exhausted."""
import sys
import tempfile
from pathlib import Path

SIG = "passed sub-checks with '_' reported NOT_RUN"
LOG = "IT-001 PASS\nIT-005-ADC12_EN PASS\nIT-005-ADC12_RST_ASSERTED PASS\nIT-006-CR_KEPT PASS\nIT-006-SR_KEPT PASS\n"


def main() -> int:
    from forge_factory.inspection import swtrace

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "run.log"
        p.write_text(LOG)
        res = swtrace.check_results([p])
    if res.get("IT-005") != "PASS" or res.get("IT-006") != "PASS":
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
