"""RPR-052 (T-015 on HAL r161-r164): a sealed package workspace has the HAL unit in software/hal AND software/src; the
target image build passed both to the linker (multiple definition of every HAL function) and the optimization
report still said MEASURED although no case had a count."""
import sys
import tempfile
from pathlib import Path

SIG = "package workspace links the same compile unit twice"


def main() -> int:
    from forge_factory.mcp.servers import sim

    seen: list[list[str]] = []

    class R:
        returncode = exit_code = 1
        stdout, stderr = b"", b"collect2: error: ld returned 1 exit status\n"

    sim.run_argv = lambda argv, *a, **k: (seen.append(list(argv)), R())[1]
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        for d in ("software/hal", "software/src"):
            (ws / d).mkdir(parents=True)
            (ws / d / "stm32n6xx_hal_rcc.c").write_text("int HAL_X(void) { return 0; }\n")
        (ws / "t.c").write_text("int main(void) { return 0; }\n")
        sim.build_image(ws, ws / "t.c", ws / "t.elf")
    units = [Path(a).name for a in seen[0] if a.endswith(".c") and "/software/" in a]
    if len(units) != len(set(units)):
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
