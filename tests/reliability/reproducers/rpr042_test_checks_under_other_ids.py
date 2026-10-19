"""RPR-042 (r126): the function tagged '@test UT-010' printed its checks as UT-100/UT-106..UT-113; Matrix 4 marked
UT-010 NOT_RUN, the deterministic gate said nothing actionable and the SWE.4 inspector rejected the contradiction."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

SIG = "test without its own result line not named"
TEST = "/** @test UT-010 @verifies USPEC-HAL-01-01 */\nstatic void ut_a(void)\n{\n    CHECK(\"UT-100\", 1);\n}\n"
UNITS = ("## SWU-HAL-01: HSE\n- SWC: SWC_HAL\n- Functions: HAL_RCC_HSE_Enable\n"
         "- **USPEC-HAL-01-01** Enable HSE. Traces: SWR-001\n")


def main() -> int:
    from forge_factory.inspection import swtrace

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        log = b"UT-100 PASS\n"
        h = hashlib.sha256(log).hexdigest()
        for rel, text in {".forge-run/manifest.json": json.dumps({"layer": "HAL"}),
                          "workproducts/SWE.3/unit_specifications.md": UNITS,
                          "software/tests/unit/test_rcc.c": TEST,
                          "evidence/tool-results.jsonl": json.dumps({"op": "run_unit", "phase": "SWE.4", "result": {
                              "status": "PASS", "artifact_refs": [f"artifact:sha256:{h}"]}}) + "\n"}.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        (ws / "evidence/raw").mkdir(parents=True, exist_ok=True)
        (ws / f"evidence/raw/{h}.log").write_bytes(log)
        f = swtrace.build_all(ws, render=False, doxygen=False, upto="SWE.4")["findings"].get("SWE.4", [])
    if not any(x.startswith("UT:TEST_NOT_OBSERVED:UT-010") and "UT-010-<suffix>" in x for x in f):
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
