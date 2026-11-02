"""RPR-120 (Fabro run WO-F014-CMP-SWE2-IWDGG-20261102-08, cloud comparison line, loop10, 2026-11-02): SWR-009 is a
truncating write ("If the caller requests a reload value above 0xFFF, then the IWDG LL driver shall write only bits
11:0 of the requested value to IWDG_RLR.RL"; verified by calling with 0x00001234 and expecting RL == 0x234). The
SWE.1 register-effects contract could record only the resulting field value (case RLR_RL_WRITE_TRUNCATED value
0x234: the author schema has no other property and the value must fit the 12-bit field), and the SWE.2 deterministic
check lrtx/swe2.py:validate_interfaces required the api_calls.json argument to equal that value. The author had to write
LL_IWDG_SetReloadCounter(0x234U), the inspector correctly rejected it as not exercising the above-0xFFF input
(SWE2-06 in INS-SWE.2-001..003) and SWE.2 was BLOCKED (STUCK SAME_ITEM_FAILED_3X).

Scenario: a synthetic IWDG LL workspace in scratch (tracked IWDG peripheral profile, the two RLR write requirements of
the run, a register-effects contract whose truncating case records the requested input 0x1234 next to the value
0x234) and the real SWE.1 author schema and SWE.2 interface check of the revision under test. Control: the in-range
case (value 0x123, argument 0x123U) passes the argument check. Symptom: the SWE.1 schema cannot carry the requested
input, or the SWE.2 check refuses the call with the requested input 0x1234U. A fix that also accepts the truncated
0x234U for that case is reported as an error (the check must not be loosened)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "a truncating-write case cannot pass the SWE.2 argument check with the above-field input its requirement requires"

REQS = (
    "# Software requirements\n\n"
    "- **SWR-007** When the caller requests a reload value in the range 0x000 to 0xFFF, the IWDG LL driver shall write "
    "the requested value to IWDG_RLR.RL, write 0 to the reserved IWDG_RLR bits 31:12 as RM0486 requires, and leave "
    "every other IWDG register unchanged.\n"
    "  - Source: RM0486 p.2990\n"
    "  - Verification: Host unit test: preset IWDG_RLR to 0x00000FFF, call the reload-set function with 0x0123; the "
    "test passes when IWDG_RLR.RL equals the requested value.\n"
    "- **SWR-009** If the caller requests a reload value above 0xFFF, then the IWDG LL driver shall write only bits 11:0 "
    "of the requested value to IWDG_RLR.RL, write 0 to the reserved IWDG_RLR bits 31:12 as RM0486 requires, leave every "
    "other IWDG register unchanged and return no status.\n"
    "  - Source: RM0486 p.2990\n"
    "  - Verification: Host unit test on the ll_iwdg_regs array indexed by LL_IWDG_RLR_OFFSET / 4U: preset IWDG_RLR to "
    "0x00000FFF and the other IWDG registers to known patterns, then call the reload-set function with 0x00001234 (and "
    "with 0xFFFFFFFF); the test passes when IWDG_RLR.RL equals 0x234 (respectively 0xFFF), IWDG_RLR bits 31:12 read 0, "
    "and all other IWDG register words are unchanged.\n")
IN_RANGE = {"case": "RLR_RL_WRITE_IN_RANGE", "swr": "SWR-007", "register": "IWDG_RLR", "field": "RL", "op": "write",
            "value": "0x123"}
TRUNCATED = {"case": "RLR_RL_WRITE_TRUNCATED", "swr": "SWR-009", "register": "IWDG_RLR", "field": "RL", "op": "write",
             "value": "0x234", "requested": "0x1234"}
IDX = {"IWDG_RLR": {"name": "IWDG_RLR", "offset": 8, "fields": {"RL": {"msb": 11, "lsb": 0, "access": ["rw"]}}}}


def interfaces(arg: str) -> dict:
    fn = {"name": "LL_IWDG_SetReloadCounter", "returns": "void", "params": [{"name": "counter", "type": "uint32_t"}],
          "operation": "masked read-modify-write of IWDG_RLR.RL", "fields": ["IWDG_RLR.RL"]}
    return {"functions": [fn],
            "allocation": [{"swr": s, "functions": [fn["name"]], "responsibility": "writes the reload value"}
                           for s in ("SWR-007", "SWR-009")],
            "calls": [{"case": "RLR_RL_WRITE_IN_RANGE", "function": fn["name"], "args": ["0x123U"]},
                      {"case": "RLR_RL_WRITE_TRUNCATED", "function": fn["name"], "args": [arg]}]}


def main() -> int:
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe1, swe2

    schema_errors = S.validate({k: v for k, v in TRUNCATED.items() if k != "swr"}, swe1.EFFECT_SCHEMA)
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps(
            {"work_order": "WO-RPR-120", "peripheral": "iwdg", "layer": "LL"}))
        (ws / "workproducts/SWE.1").mkdir(parents=True)
        (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
        (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps(
            {"schema": "forge-c/register-effects/1", "effects": [IN_RANGE, TRUNCATED]}))

        def arg_findings(arg: str) -> list[str]:
            return [f for f in swe2.validate_interfaces(ws, interfaces(arg), IDX) if "argument must be" in f]

        requested, truncated = arg_findings("0x1234U"), arg_findings("0x234U")
    if any("RLR_RL_WRITE_IN_RANGE" in f for f in requested + truncated):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the in-range control case fails the argument check")
        return 2
    if schema_errors or requested:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if not truncated:
        print("REPRODUCER_ERROR:CHECK_LOOSENED:the truncated field value 0x234U is accepted as the call argument")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
