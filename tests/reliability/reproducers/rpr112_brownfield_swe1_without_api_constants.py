"""RPR-112 (Fabro runs WO-F014-CMP-SWE1-CRCL-20261102-05 and -06, cloud comparison line, loop10, 2026-11-02): full CRC
LL from ST code (FROZEN brownfield, 10 scoped functions). The SWE.1 author and inspector never saw the frozen API's
argument constants (LL_CRC_POLYLENGTH_*, LL_CRC_INDATA_REVERSE_*, LL_CRC_OUTDATA_REVERSE_*): the requirements of
LL_CRC_SetPolynomialSize / Set*DataReverseMode named sizes and reversal modes but no argument value, or invented an
encoding as an open point, and the inspector failed SWE1-02 three times (BLOCKED STUCK SAME_ITEM_FAILED_3X).

Scenario: the real work-order prepare of example 0014c's FROZEN ST CRC delivery (its tracked workorder.json; the
pinned ST sources from FORGE_DATA_ROOT; git-ignored RM inputs replaced by a tracked input, a one-section RM stub in
Forge-C wording written into the temporary workspace), then the real SWE.1 author packet of the CRC_CR task and the
real SWE.1 inspector evidence (only the frozen-baseline lookup stubbed). Everything is written under TMPDIR.
Symptom: the author's or the inspector's sources lack a scoped function's argument constant with its value."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "brownfield SWE.1 author or inspector sources lack the frozen API argument constants of a scoped function"
ST = "inputs/st/stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_crc.h"
# ST CubeN6 v1.4.0 constant identifiers with the CRC_CR bit patterns RM0486 26.4.3 gives them (POLYSIZE 4:3,
# REV_IN 6:5, REV_OUT 8:7, RTYPE_IN 9, RTYPE_OUT 10)
WANT = {"LL_CRC_POLYLENGTH_16B": "0x00000008", "LL_CRC_POLYLENGTH_7B": "0x00000018",
        "LL_CRC_INDATA_REVERSE_HALFWORD_BYWORD": "0x00000220", "LL_CRC_OUTDATA_REVERSE_BYTE": "0x00000500"}


def pairs(o, out: set) -> set:
    """Every (constant name, value) pair a JSON source states."""
    if isinstance(o, dict):
        if isinstance(o.get("name"), str) and isinstance(o.get("value"), str):
            out.add((o["name"], o["value"]))
        for v in o.values():
            pairs(v, out)
    elif isinstance(o, list):
        for v in o:
            pairs(v, out)
    return out


def has_all(srcs: list[dict]) -> bool:
    found: set = set()
    for s in srcs:
        try:
            pairs(json.loads(s["text"]), found)
        except ValueError:
            continue
    return set(WANT.items()) <= found


def main() -> int:
    data = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent"))
    if not (data / ST).is_file() or shutil.which("arm-none-eabi-gcc") is None:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:pinned ST sources or arm-none-eabi-gcc not available")
        return 2
    from forge_factory.common import REPO_ROOT
    td = Path(tempfile.mkdtemp())
    os.environ["FORGE_STATE_DIR"] = str(td / "state")
    os.environ["FORGE_EVENTS_DIR"] = str(td / "state/events")
    spec = json.loads((REPO_ROOT / "examples/0014c-st-cube-crc/workorder.json").read_text())
    if spec.get("delivery", {}).get("code_mode") != "FROZEN" or \
            "LL_CRC_SetPolynomialSize" not in spec["delivery"]["scope"]["functions"]:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:0014c is no FROZEN delivery scoping LL_CRC_SetPolynomialSize")
        return 2
    spec["inputs"] = [{"path": str(REPO_ROOT / "examples/0014-crc-st/inputs/inputs-manifest.json"),
                       "role": "conversion_provenance"}]
    spec.pop("peripheral", None)  # its key-section check needs the git-ignored RM text
    ex = td / "ex"
    ex.mkdir()
    (ex / "workorder.json").write_text(json.dumps(spec))
    from forge_factory import workorder as WO
    from forge_factory.inspection import engine
    from forge_factory.lrtx import review, swe1
    ws, _man = WO.prepare(ex, "WO-RPR112")
    if any(ws.rglob("stm32n6xx_ll_crc.h")):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:delivered code already in the SWE.1 workspace")
        return 2
    sec = "inputs/sections/RM0486/26.4.3_CRC_control_register_CRC_CR.md"
    (ws / sec).parent.mkdir(parents=True, exist_ok=True)
    (ws / sec).write_text("# 26.4.3 CRC control register (CRC_CR)\n\nAddress offset: 0x08\n\nReset value: 0x0000 0000\n\n"
                          "Bits 4:3 POLYSIZE[1:0]: polynomial size (00: 32, 01: 16, 10: 8, 11: 7 bit).\n")
    g = {"id": "CRC_CR_1", "register": "CRC_CR", "section": "26.4.3", "file": sec, "pages": [1173],
         "fields": {"POLYSIZE": {"msb": 4, "lsb": 3, "access": ["rw"], "description": "Polynomial size"}}}
    author = swe1.group_packet(ws, g, "rpr112-model")
    prompt = "\n".join(m["content"] for m in author["_messages"])
    srcs_author = [{"path": s["path"], "text": (ws / s["path"]).read_text(errors="replace")}
                   for s in author["sources"] if (ws / s["path"]).is_file()]
    srcs_author = [s for s in srcs_author if s["text"] in prompt]  # only what the model is sent
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("# Software requirements\n")
    engine.Store.latest_baseline = lambda self, ph: {"baseline_id": "BL-SWE.1-001", "baseline_hash": "h" * 64,
                                                     "files": ["workproducts/SWE.1/software_requirements.md"]}
    _bl, srcs_inspector = review.evidence(ws, "SWE.1")
    code_leak = any("MODIFY_REG(" in s["text"] or "CRCx->" in s["text"] for s in srcs_author + srcs_inspector)
    if code_leak:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:delivered code text reached SWE.1 (FR-007)")
        return 2
    if has_all(srcs_author) and has_all(srcs_inspector):
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
