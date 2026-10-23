"""F011-T034 (SWE.5/SWE.6): the SafeC register-image oracle of the frozen SWE.1 contract, run on the Renode STM32N6
target model, with the work order's real LL code built for Cortex-M55.

Each oracle case is one RAM-resident image: it writes the case's initial image with the operated field flipped, then
the image itself, and reads each back. A peripheral model with side effects may not hold an arbitrary image (a
write-protected register, a write-only key register, model-driven status flags); the case is then NOT_SETTABLE on this
model, reported as such and never counted as passed. Otherwise the SWE.2 call of the case's requirement runs and the register word and the query return value
must equal the oracle's expectation. Applicability is measured on the model, not assumed from the reference manual.

Limits (recorded with the result): Renode peripheral models, not silicon; other-register effects are not compared on
target (the host oracle, the CBMC and the WP proofs cover them); one image per case.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

LIMITS = ["Renode peripheral models of the Forge-C STM32N6 platform, not silicon",
          "other-register effects are checked on the host (oracle, CBMC, WP), not on target",
          "a case whose initial image the model does not hold is NOT_SETTABLE, never a pass"]


def _image(case: dict, block: str, count: int, api_header: str) -> str:
    from .register_contract import call_text

    call = call_text(case, "10U")
    run = (f"uint32_t r = (uint32_t)({call}); ok = ({block}[{case['word']}U] == 0x{case['after']:08X}U) && "
           f"(r == {case['ret']}U);" if case["ret"] is not None else
           f"(void){call}; ok = ({block}[{case['word']}U] == 0x{case['after']:08X}U);")
    return "\n".join([
        "#include <stdint.h>", '#include "forge_target_test.h"', "FORGE_MAILBOX_DEFINE;",
        f"extern volatile uint32_t {block}[{count}];", f'#include "{api_header}"',
        "int main(void)", "{", "    int ok = 0;", "    FORGE_TEST_BEGIN();",
        # the register must hold the case's image with its field flipped AND the image itself: a register that ignores
        # writes (locked, read-only, write-only) could otherwise look settable when the image equals its reset value
        f"    {block}[{case['word']}U] = 0x{case['initial'] ^ case['mask']:08X}U;",
        f"    ok = ({block}[{case['word']}U] == 0x{case['initial'] ^ case['mask']:08X}U);",
        f"    {block}[{case['word']}U] = 0x{case['initial']:08X}U;",
        f"    if (!ok || {block}[{case['word']}U] != 0x{case['initial']:08X}U) {{",
        "        forge_mailbox.failed_ids[0] = 2U; forge_mailbox.failed = 1U;  /* NOT_SETTABLE */",
        "    } else {", f"        {run}", "        TCHECK(1, ok);", "    }", "    FORGE_TEST_END();",
        "    for (;;) { }", "}"]) + "\n"


def run(ws: Path, include_dirs: list[Path], api_header: str) -> dict:
    from ..layer import layer_of
    from ..mcp.servers import sim
    from . import register_contract as RC
    from . import safec_oracle as SO

    ws = Path(ws)
    if layer_of(ws) != "LL" or not SO.present(ws):
        return {"status": "NOT_APPLICABLE", "reason": "only LL work orders with a frozen SafeC register oracle"}
    renode = sim.renode_bin()
    if renode is None or shutil.which("arm-none-eabi-gcc") is None:
        return {"status": "UNSUPPORTED", "reason": "Renode or the GNU Arm toolchain is not installed on this host"}
    effects = {e["case"]: e for e in json.loads((ws / "workproducts/SWE.1/register_effects.json").read_text())
               ["effects"]}
    calls = json.loads((ws / RC.CALLS).read_text()).get("calls") or {}
    cases, notes = SO.cases(ws, effects, calls)
    if not cases and notes and notes[0].startswith("SAFEC_ORACLE_BLOCKED"):
        return {"status": "BLOCKED", "reason": notes[0], "issues": notes}
    rec, _issues = SO.verified(ws)
    mask_of = {name: int(next(o for o in rec["operations"] if o["intent_id"] == iid)["field_mask"], 16)
               for iid, name in rec["case_of_intent"].items()}
    cases = [{**c, "mask": mask_of[c["case"].split("@", 1)[0]]} for c in cases]
    return {**execute(ws, cases, include_dirs, api_header, renode), "notes": notes}


def execute(ws: Path, cases: list[dict], include_dirs: list[Path], api_header: str, renode: str) -> dict:
    """Build and run one image per case (case: swr, case, register, function, args, word, initial, after, ret,
    mask) on the work order's Renode platform."""
    from ..layer import profile
    from ..mcp.sdk import run_argv
    from ..mcp.servers import sim

    pr = profile(ws)
    block, count = pr["ll"]["register_block"], pr["ll"]["register_count"]
    wd = ws / "build" / "target-oracle"
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    incs = [f"-I{Path(d).resolve()}" for d in include_dirs]
    rows = []
    for n, c in enumerate(cases):
        src, elf = wd / f"case_{n:03d}.c", wd / f"case_{n:03d}.elf"
        src.write_text(_image(c, block, count, api_header))
        b = run_argv(["arm-none-eabi-gcc", *sim.CFLAGS, *incs, f"-I{sim.SIM_DIR}", "-T",
                      str(sim.linker_script(ws, wd)), str(sim.SIM_DIR / "startup.c"), str(src), "-o", str(elf)],
                     wd, 180, {"arm-none-eabi-gcc"})
        row = {"case": c["case"], "swr": c["swr"], "register": c["register"], "initial": f"0x{c['initial']:08x}"}
        if b.exit_code != 0:
            rows.append({**row, "status": "BUILD_FAILED", "detail": b.stderr.decode(errors="replace")[-200:]})
            continue
        res, _raw = sim.run_image(renode, elf, "default", wd, ws)
        if res is None or not res["magic_ok"] or not res["done"]:
            rows.append({**row, "status": "NO_RESULT"})
        elif res["passed"] == 1 and res["failed"] == 0:
            rows.append({**row, "status": "PASS"})
        elif res["failed_ids"][:1] == [2]:
            rows.append({**row, "status": "NOT_SETTABLE"})
        else:
            rows.append({**row, "status": "FAIL"})
    count_of = {s: sum(r["status"] == s for r in rows) for s in
                ("PASS", "FAIL", "NOT_SETTABLE", "BUILD_FAILED", "NO_RESULT")}
    bad = count_of["FAIL"] + count_of["BUILD_FAILED"] + count_of["NO_RESULT"]
    status = "FAIL" if bad else ("PASS" if count_of["PASS"] else "NOT_SUPPORTED")
    return {"status": status, "counts": count_of, "cases": rows, "limits": LIMITS,
            "environment": "RENODE", "simulator": "renode 1.17.0 (Forge-C STM32N6 platform)"}
