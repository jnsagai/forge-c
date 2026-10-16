"""RPR-003 (r74): a test edited after a runtime failure until it passed was reported PASS by the test tool; the
anti-bending verdict came only at the author gate, in the last cycle. Fixed by c13240a (tool-time HOW_TO_DECLARE)."""
import sys
import tempfile
from pathlib import Path

SIG = "run_unit reported PASS for an undeclared test edited after a runtime failure"
TEST = '#include <stdio.h>\nint drv(void);\nint main(void) {{ if (drv() == {v}) {{ printf("UT-001 PASS\\n"); return 0; }} ' \
       'printf("UT-001 FAIL\\n"); return 1; }}\n'


def main() -> int:
    from forge_factory.mcp.sdk import ToolContext
    from forge_factory.mcp.servers import tests as TM

    ws = Path(tempfile.mkdtemp(prefix="rpr003-"))
    (ws / "software/src").mkdir(parents=True)
    (ws / "software/src/drv.c").write_text("int drv(void) { return 2; }\n")
    t = ws / "software/tests/unit/test_drv.c"
    t.parent.mkdir(parents=True)
    t.write_text(TEST.format(v=1))
    ctx = ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "rpr003")
    first = TM.run_unit(ctx, TM.RunIn(coverage=False))
    if first["status"] != "FAIL":
        print(f"REPRODUCER_ERROR:SETUP:first run {first['status']}")
        return 2
    t.write_text(TEST.format(v=2))  # bent to the code, not declared
    second = TM.run_unit(ctx, TM.RunIn(coverage=False))
    if second["status"] == "PASS":
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
