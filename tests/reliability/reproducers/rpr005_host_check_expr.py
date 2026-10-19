"""RPR-005 (r74): run_unit/run_integration reported only 'IT-001 FAIL'; authors rewrote tests blind for three cycles.
Fixed by c13240a (CHECK_EXPR for host tests)."""
import sys
import tempfile
from pathlib import Path

SIG = "failed host CHECK reported without its expression"
TEST = ('#include <stdio.h>\nint drv(void);\n#define CHECK(id, c) do { if (c) { printf("%s PASS\\n", (id)); } '
        'else { printf("%s FAIL\\n", (id)); n++; } } while (0)\nint main(void) { int n = 0; int st;\n'
        '    st = drv();\n    CHECK("UT-007", st == 3);\n    return n; }\n')


def main() -> int:
    from forge_factory.mcp.sdk import ToolContext
    from forge_factory.mcp.servers import tests as TM

    ws = Path(tempfile.mkdtemp(prefix="rpr005-"))
    (ws / "software/src").mkdir(parents=True)
    (ws / "software/src/drv.c").write_text("int drv(void) { return 2; }\n")
    t = ws / "software/tests/unit/test_drv.c"
    t.parent.mkdir(parents=True)
    t.write_text(TEST)
    res = TM.run_unit(ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "rpr005"),
                      TM.RunIn(coverage=False))
    if res["status"] != "FAIL":
        print(f"REPRODUCER_ERROR:SETUP:{res['status']}")
        return 2
    if not any(i.startswith("CHECK_EXPR:test_drv.c#UT-007:st == 3") for i in res["issues"]):
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
