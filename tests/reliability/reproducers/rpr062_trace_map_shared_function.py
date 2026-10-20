"""RPR-062 (b006): ST's AHB1 bus functions serve two units (GPDMA1 and ADC12); the brownfield trace map allowed one
owning unit per delivered function, so either the USPECs of the second unit were SPEC_OF_OTHER_UNIT or the function
appeared twice (DEF-003)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "a delivered function shared by two units cannot be traced"


def main() -> int:
    from forge_factory.brownfield import trace as T
    from forge_factory.common import sha256_bytes

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        hdr = "static inline void LL_AHB1_GRP1_EnableClock(unsigned p) { (void)p; }\n"
        (ws / "software/ll").mkdir(parents=True)
        (ws / "software/ll/bus.h").write_text(hdr)
        (ws / ".forge-run/delivery").mkdir(parents=True)
        (ws / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [
            {"name": "LL_AHB1_GRP1_EnableClock", "file": "software/ll/bus.h", "line": 1}]}))
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "code_mode": "FROZEN",
            "delivered": [{"path": "software/ll/bus.h", "role": "delivered_code", "sha256": sha256_bytes(hdr.encode())}],
            "delivery": {"code_mode": "FROZEN"}}))
        (ws / "workproducts/SWE.3").mkdir(parents=True)
        (ws / T.MAP).write_text(json.dumps({"schema": T.SCHEMA, "rows": [
            {"function": "LL_AHB1_GRP1_EnableClock", "file": "software/ll/bus.h", "sha256": sha256_bytes(hdr.encode()),
             "unit": ["SWU-LL-03", "SWU-LL-04"], "uspecs": ["USPEC-LL-03-01", "USPEC-LL-04-01"]}]}))
        units = [{"id": "SWU-LL-03", "functions": ["LL_AHB1_GRP1_EnableClock"], "specs": [{"id": "USPEC-LL-03-01"}]},
                 {"id": "SWU-LL-04", "functions": ["LL_AHB1_GRP1_EnableClock"], "specs": [{"id": "USPEC-LL-04-01"}]}]
        rep = T.check_code(ws, units)
    if rep["verdict"] != "PASS":
        print(f"findings: {rep['major_findings'][:3]}")
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
