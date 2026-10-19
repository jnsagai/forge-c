"""SPEC-001 T-015 - map/stack/cycle metric collectors, a baseline comparator and a Pareto report over sealed packages.

Collectors (read-only on the package; the archive hash is compared before and after):
  * flash / static RAM / largest stack frame: the package's verification/footprint record (GNU Arm object build);
  * cost per API call: for each case of the package's register contract (SWE.1 register_effects + SWE.2 api_calls,
    work orders with register_contract rc-v1), one benchmark image making that single call and one empty image are
    run on the Renode STM32N6 RCC model; cost = executed instructions(call image) - executed instructions(empty image).
    Owner decision 2026-10-19 (OD-2026-10-19-05): Renode is not cycle-accurate, so EXECUTED INSTRUCTIONS stand in for
    cycles, labelled as a proxy. Every image runs twice; a count that differs is reported NOT_DETERMINISTIC.
Comparator: per metric baseline vs candidate (lower is better), only on cases both packages measured.
Pareto: packages no other package beats on every metric (flash, stack frame, instructions on the common cases).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .common import sha256_file, utc_now

EFFECTS, CALLS = "workproducts/SWE.1/register_effects.json", "workproducts/SWE.2/api_calls.json"
METRICS = ("flash_bytes", "ram_bytes", "max_frame_bytes", "instructions_common")
PROXY = "executed instructions on the Renode cortex-m55 model (cycle proxy, not cycle-accurate; OD-2026-10-19-05)"


def bench_source(case: dict | None, header: str, timeout: str) -> str:
    from .assurance.register_contract import call_text

    call = ""
    if case is not None:
        text = call_text(case, timeout)
        call = f"    {{ volatile int r = (int){text}; (void)r; }}" if case.get("status") else f"    {text};"
    return (f'#include <stddef.h>\n#include "{header}"\n#include "forge_target_test.h"\nFORGE_MAILBOX_DEFINE;\n'
            f"int main(void)\n{{\n    FORGE_TEST_BEGIN();\n{call}\n    TCHECK(1, 1);\n    FORGE_TEST_END();\n"
            "    return 0;\n}\n")


def bench_cases(ws: Path) -> tuple[list[dict], list[str]]:
    """Calls to measure, from the contract only (a sealed package carries no RM inputs, and a benchmark needs none)."""
    eff = json.loads((ws / EFFECTS).read_text()).get("effects") or []
    calls = json.loads((ws / CALLS).read_text()).get("calls") or {}
    out, notes = [], []
    for e in eff:
        c = calls.get(e.get("case"))
        if not isinstance(c, dict) or not c.get("function"):
            notes.append(f"NO_CALL:{e.get('case')}")
            continue
        out.append({"case": e["case"], "function": c["function"], "args": list(c.get("args") or []),
                    "status": e.get("status"), "never_ready": e.get("ready") == "never"})
    return out, notes


def _count(renode: str, elf: Path, scenario: str, wd: Path) -> int | None:
    from .mcp.servers import sim

    model = wd / f"rcc_model_{scenario}.py"
    if not model.exists():
        model.write_text(re.sub(r'^SCENARIO = .*$', f'SCENARIO = "{scenario}"', (sim.SIM_DIR / "rcc_model.py").read_text(),
                                flags=re.M))
    repl = wd / f"platform_{scenario}.repl"
    if not repl.exists():
        repl.write_text((sim.SIM_DIR / "stm32n6_rcc.repl").read_text().replace("RCC_MODEL_PATH", str(model)))
    resc = wd / f"{elf.stem}.resc"
    resc.write_text(f'mach create "stm32n6"\nmachine LoadPlatformDescription @{repl}\nsysbus LoadELF @{elf}\n'
                    f'cpu VectorTableOffset 0x34000000\nemulation RunFor "0.2"\ncpu ExecutedInstructions\n'
                    f"sysbus ReadDoubleWord {sim.MAILBOX + 12:#x}\nquit\n")
    r = subprocess.run([renode, "--disable-gui", "--console", "--plain", "-e", f"include @{resc}"], cwd=wd,
                       capture_output=True, text=True, timeout=170, env={"PATH": "/usr/bin:/bin", "HOME": str(wd),
                                                                         "DOTNET_EnableWriteXorExecute": "0"})
    n = re.findall(r"^0x([0-9A-Fa-f]{16})\s*$", r.stdout, re.M)
    done = re.findall(r"^0x([0-9A-Fa-f]{8})\s*$", r.stdout, re.M)
    return int(n[0], 16) if n and done and int(done[-1], 16) == 1 else None


def collect(zip_path: Path, inputs_from: Path | None = None) -> dict:
    from .assurance import shadow
    from .mcp.servers import sim

    zip_path = Path(zip_path)
    before = sha256_file(zip_path)
    out = {"package": zip_path.name, "archive_sha256": before, "measured_at": utc_now(), "cycle_metric": PROXY}
    with tempfile.TemporaryDirectory() as td:
        x = Path(td) / "x"
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(x)
        ws = shadow._workspace_from_package(x, inputs_from)
        fp = json.loads((ws / "verification/footprint/memory_stack_summary.json").read_text())
        out.update({k: fp.get(k) for k in ("flash_bytes", "ram_bytes", "max_frame_bytes")}, footprint_scope=fp.get("scope"))
        if not ((ws / EFFECTS).is_file() and (ws / CALLS).is_file()):
            out.update(instructions={}, instructions_status="NO_REGISTER_CONTRACT (work order before rc-v1)")
            return {**out, "archive_unchanged": sha256_file(zip_path) == before}
        renode = sim.renode_bin()
        if not renode or not shutil.which("arm-none-eabi-gcc"):
            out.update(instructions={}, instructions_status="TOOL_MISSING:renode/arm-none-eabi-gcc")
            return {**out, "archive_unchanged": sha256_file(zip_path) == before}
        cases, notes = bench_cases(ws)
        layer = "LL" if not (ws / "software/hal").is_dir() else "HAL"
        header = "stm32n6xx_ll_rcc.h" if layer == "LL" else "stm32n6xx_hal_rcc.h"
        wd = Path(td) / "bench"
        wd.mkdir()

        def measure(case: dict | None, tag: str, scenario: str) -> tuple[int | None, str]:
            src = wd / f"bench_{tag}.c"
            src.write_text(bench_source(case, header, "10U"))
            elf = wd / f"bench_{tag}.elf"
            ok, _log, errs = sim.build_image(ws, src, elf)
            if not ok:
                return None, "BUILD_FAIL:" + "; ".join(errs)[:160]
            a, b = _count(renode, elf, scenario, wd), _count(renode, elf, scenario, wd)
            if a is None or b is None:
                return None, "NO_RESULT"
            return (a, "OK") if a == b else (None, f"NOT_DETERMINISTIC:{a}!={b}")

        base = {}
        res = {}
        for c in cases:
            scen = "never_ready" if c["never_ready"] else "default"
            if scen not in base:
                base[scen] = measure(None, f"empty_{scen}", scen)
            n, st = measure(c, c["case"], scen)
            b0 = base[scen][0]
            res[c["case"]] = {"instructions": n - b0 if n is not None and b0 is not None else None,
                              "status": st if base[scen][1] == "OK" else "BASE_" + base[scen][1], "scenario": scen,
                              "function": c["function"]}
        got = [v for v in res.values() if v["instructions"] is not None]
        status = "MEASURED" if got else ("NOT_MEASURED:" + (next(iter(res.values()))["status"] if res else "NO_CASES"))[:160]
        out.update(instructions=res, instructions_status=status, contract_notes=notes,
                   empty_image_instructions={k: v[0] for k, v in base.items()})
    return {**out, "archive_unchanged": sha256_file(zip_path) == before}


def _common(a: dict, b: dict) -> list[str]:
    ia, ib = a.get("instructions") or {}, b.get("instructions") or {}
    return sorted(k for k in set(ia) & set(ib) if ia[k]["instructions"] is not None and ib[k]["instructions"] is not None)


def compare(base: dict, cand: dict) -> dict:
    common = _common(base, cand)
    rows = {}
    for m in ("flash_bytes", "ram_bytes", "max_frame_bytes"):
        rows[m] = (base.get(m), cand.get(m))
    rows["instructions_common"] = (sum(base["instructions"][k]["instructions"] for k in common) if common else None,
                                   sum(cand["instructions"][k]["instructions"] for k in common) if common else None)
    out = {}
    for m, (b, c) in rows.items():
        if b is None or c is None:
            out[m] = {"baseline": b, "candidate": c, "verdict": "NOT_COMPARABLE"}
        else:
            out[m] = {"baseline": b, "candidate": c, "delta": c - b, "delta_pct": round(100 * (c - b) / b, 2) if b else None,
                      "verdict": "BETTER" if c < b else "WORSE" if c > b else "EQUAL"}
    v = {x["verdict"] for x in out.values()}
    overall = ("DOMINATES" if "BETTER" in v and "WORSE" not in v else "DOMINATED" if "WORSE" in v and "BETTER" not in v
               else "TRADE_OFF" if {"BETTER", "WORSE"} <= v else "EQUIVALENT")
    return {"baseline": base["package"], "candidate": cand["package"], "common_cases": common, "metrics": out,
            "overall": overall, "basis": "deterministic measurements (footprint tools; Renode counts checked twice)"}


def pareto(measured: list[dict]) -> dict:
    common = sorted(set.intersection(*(set(k for k, v in (m.get("instructions") or {}).items()
                                           if v["instructions"] is not None) for m in measured))) if measured else []
    pts = []
    for m in measured:
        ins = sum(m["instructions"][k]["instructions"] for k in common) if common else None
        pts.append({"package": m["package"], "flash_bytes": m["flash_bytes"], "max_frame_bytes": m["max_frame_bytes"],
                    "instructions_common": ins})
    keys = ["flash_bytes", "max_frame_bytes"] + (["instructions_common"] if common else [])

    def beats(a: dict, b: dict) -> bool:
        return all(a[k] <= b[k] for k in keys) and any(a[k] < b[k] for k in keys)
    front = [p["package"] for p in pts if not any(beats(q, p) for q in pts if q is not p)]
    return {"metrics": keys, "common_cases": common, "points": pts, "pareto_front": front, "cycle_metric": PROXY}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.optimization")
    ap.add_argument("zips", nargs="+", type=Path)
    ap.add_argument("--baseline", type=Path, help="baseline package (default: the first)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    measured = [collect(z) for z in a.zips]
    base = next((m for m in measured if a.baseline and m["package"] == a.baseline.name), measured[0])
    rep = {"schema": "forge-c/optimization-report/0.1", "generated_at": utc_now(), "cycle_metric": PROXY,
           "packages": measured, "comparisons": [compare(base, m) for m in measured if m is not base],
           "pareto": pareto(measured)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=2) + "\n")
    ok = all(m["archive_unchanged"] for m in measured) and all(m["instructions_status"] == "MEASURED" for m in measured) \
        and all(v["status"] == "OK" for m in measured for v in m["instructions"].values())
    print(json.dumps({"pareto_front": rep["pareto"]["pareto_front"], "measured": [m["instructions_status"] for m in measured],
                      "status": "PASS" if ok else "INCOMPLETE"}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
