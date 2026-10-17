"""RPR-031 (r110): SWE3-04 failed because no explicit MISRA C:2012 deviation record existed although the analyzers
reported nothing; the statement must be generated from the recorded facts (deviations: none)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "no generated MISRA deviation statement"


def main() -> int:
    try:
        from forge_factory.inspection import unit_scaffold
    except ImportError:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        (ws / ".forge-run").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
        (ws / "software/ll").mkdir(parents=True)
        (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text("static inline void LL_RCC_X(void)\n{\n}\n")
        (ws / "evidence").mkdir()
        (ws / "evidence/tool-results.jsonl").write_text(json.dumps({"op": "cppcheck", "result": {
            "status": "PASS", "metrics": {"misra_rules_violated": 0, "general_findings": 0}}}) + "\n")
        unit_scaffold.scaffold(ws)
        p = ws / "workproducts/SWE.3/misra_deviations.md"
        ok = p.is_file() and "- Deviations: none" in p.read_text() and "NOT CLAIMED" in p.read_text()
    print("SYMPTOM_ABSENT" if ok else f"SYMPTOM_PRESENT:{SIG}")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
