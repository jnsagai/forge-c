"""RPR-140 (local run WO-F014-SWE3-WWDGHAL-20261103-L32, Omniverse2, WWDG HAL order 0016m on run/gen14 6365c843 - which
already has CAPA-137 -, 2026-11-03): SWE.3 was BLOCKED "STUCK: identical deterministic rejection twice
(CONTRACT_CALL_DOES_NOT_COMPILE:workproducts/SWE.2/api_calls.json:'flag' undeclared)": the SWE.2 call contract passed
`&flag` to HAL_WWDG_GetEarlyWakeupFlag. SWE.2 (L32) had PASSED it because CAPA-137's identifier check
(assurance/register_contract._declared_words) counted EVERY word of the SWE.2 work products as declared - the architecture
prose says "NULL flag pointer" and "status flag" -, and the triage could not overrule the SWE.2 author's rejection of
DEF-001 either (the check it re-runs found nothing). Recurrence of the CAPA-137 class (CRC HAL `&crc`).

Scenario (synthetic workspace in a scratch dir, no inputs): a non-instance, non-brownfield HAL work order at SWE.2 whose
architecture prose says "NULL flag pointer" and whose C interface block declares
`uint32_t HAL_WWDG_GetFlag(uint32_t *p_flag);`, a one-case call contract FLAG(HAL_WWDG_GetFlag, <arg>), then the SWE.2
compile findings of the revision under test (register_contract.swe2_compile_findings, as the SWE.2 gate, the lrtx SWE.2
self-check and the triage use them).
Symptom: no CONTRACT_CALL_DOES_NOT_COMPILE finding names `flag` (a prose word) or `p_flag` (a prototype parameter).
Controls: the self-contained `&(uint32_t){0U}` and a macro the interface block defines get no finding (an altered control
is an error, not ABSENT)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "an SWE.2 call-contract argument named only by SWE.2 prose or a prototype parameter passes the SWE.2 identifier check"
ARCH = ("# Software architecture\n\nA NULL flag pointer returns an error; the status flag is read on request.\n\n"
        "## Interface\n\n```c\n#define HAL_WWDG_WINDOW_MAX 0x7FU\nuint32_t HAL_WWDG_GetFlag(uint32_t *p_flag);\n```\n")


def findings(d: Path, name: str, arg: str) -> list[str]:
    from forge_factory.assurance import register_contract as RC

    ws = d / name
    data = {".forge-run/manifest.json": {"work_order": f"WO-RPR140-{name}", "layer": "HAL", "peripheral": "wwdg"},
            RC.EFFECTS: {"schema": "forge-c/register-effects/1",
                         "effects": [{"case": "FLAG", "swr": "SWR-001", "op": "no_write"}]},
            RC.CALLS: {"schema": "forge-c/api-calls/1",
                       "calls": {"FLAG": {"function": "HAL_WWDG_GetFlag", "args": [arg]}}}}
    for rel, obj in data.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(json.dumps(obj))
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    if not RC.cases(ws)[0]:
        raise RuntimeError(f"SCENARIO_NOT_REACHED:{name}:no contract case")
    return [f for f in RC.swe2_compile_findings(ws, "HAL") if f.startswith("CONTRACT_CALL_DOES_NOT_COMPILE")]


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        for name, arg in (("CTL-LITERAL", "&(uint32_t){0U}"), ("CTL-MACRO", "(uint32_t)HAL_WWDG_WINDOW_MAX")):
            got = findings(d, name, arg)
            if got:
                print(f"REPRODUCER_ERROR:CONTROL_ALTERED:{name}:{got[:1]}")
                return 2
        missed = [ident for ident in ("flag", "p_flag")
                  if not any(f"'{ident}' undeclared" in f for f in findings(d, f"BAD-{ident}", f"&{ident}"))]
    if missed:
        print("observed: no CONTRACT_CALL_DOES_NOT_COMPILE finding for " + ", ".join(f"&{i}" for i in missed))
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
