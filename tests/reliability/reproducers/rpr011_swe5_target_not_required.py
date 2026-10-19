"""RPR-011 (r81): the SWE.5 presence gate required only run_integration, so SWE.5 froze while run_renode (target
tests) failed; only the finalizer noticed (target_verification gap)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "SWE.5 presence gate passes with failing target tests"


def main() -> int:
    from forge_factory.inspection.engine import Store

    ws = Path(tempfile.mkdtemp(prefix="rpr011-"))
    for rel in ("workproducts/SWE.5/integration_verification_report.md",
                "software/tests/integration/test_rcc_integration.c"):
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text("x\n")
    (ws / "evidence").mkdir()
    rows = [{"server": "forge-tests-mcp", "op": "run_integration", "ts_utc": "2026-10-16T11:00:00Z",
             "result": {"status": "PASS"}},
            {"server": "forge-sim-mcp", "op": "run_renode", "ts_utc": "2026-10-16T11:01:00Z",
             "result": {"status": "FAIL"}}]
    (ws / "evidence/tool-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    missing = Store(ws).missing_outputs("SWE.5")
    if not any("run_renode" in m for m in missing):
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
