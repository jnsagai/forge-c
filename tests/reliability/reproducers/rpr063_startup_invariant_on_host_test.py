"""RPR-063 (b006): SWE.1 mapped the startup invariant SWR-018 ("While no LL function has been called after reset, ...")
to a host unit test; the test was tautological (the harness starts after reset), SWE.4 failed SWE4-02/SWE4-06 until
its rework budget ran out. The SWE.1 gate accepted the mapping."""
import sys
import tempfile
from pathlib import Path

SIG = "SWE.1 gate accepts a startup invariant mapped to a host unit test"


def main() -> int:
    from forge_factory.inspection import gate as G

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "workproducts/SWE.1").mkdir(parents=True)
        (ws / "traceability").mkdir()
        (ws / "workproducts/SWE.1/software_requirements.md").write_text(
            "# Software requirements\n- **SWR-018** While no LL function has been called after reset, the RCC LL driver "
            "shall not write any RCC register.\n")
        (ws / "traceability/requirements_to_tests.csv").write_text(
            "requirement_id,test_id,test_file\nSWR-018,UT-018,software/tests/unit/test_rcc.c\n")
        src = Path(G.__file__).read_text()
        found = []
        if "startup_on_host" in src:
            from forge_factory.inspection.test_mapping import startup_on_host

            found = startup_on_host(ws)
    if not found:
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
