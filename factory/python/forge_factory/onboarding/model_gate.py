"""Feature 016 slice I (OB-T038): the simulation-model gate, independent of how the model is written (FR-011).

  load    the platform with the model loads in Renode and every RM register of the index reads back
  reset   after reset each register reads its RM reset value (registers or fields the model lists in MODEL_LIMITS
          are reported as limits of the model, not failures)
  access  a fully read-only register ignores writes of all ones and all zeros; an rc_w0 register does not set a flag
          when ones are written
  smoke   an image built from the delivered code (the derived file map) initialises the scope instance with a zeroed
          configuration and calls a query function, and reaches its end marker (no fault, no hang)

Nothing here judges the model's functional behaviour - that is the inspector's and the target tests' job."""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from ..common import REPO_ROOT
from .facts import value

SIM_DIR = REPO_ROOT / "factory/sim/stm32n6"
HEX = re.compile(r"^(0x[0-9A-Fa-f]{8})\s*$", re.M)


def model_limits(model_text: str) -> list[str]:
    m = re.search(r"^MODEL_LIMITS\s*=\s*(\[.*?\])", model_text, re.M | re.S)
    try:
        return list(ast.literal_eval(m.group(1))) if m else []
    except (ValueError, SyntaxError):
        return []


def _monitor(renode: str, wd: Path, repl: Path, cmds: list[str]) -> tuple[list[int], str]:
    from ..mcp.sdk import run_argv

    resc = wd / "gate.resc"
    resc.write_text(f'mach create "stm32n6"\nmachine LoadPlatformDescription @{repl}\n' + "\n".join(cmds) + "\nquit\n")
    env = {"DOTNET_EnableWriteXorExecute": "0", "DOTNET_GCHeapHardLimit": "0x60000000"}
    r = run_argv([renode, "--disable-gui", "--console", "--plain", "-e", f"include @{resc}"], wd, 170,
                 {os.path.basename(renode)}, env_extra=env, mem_mb=65536, fsize_mb=512)
    out = r.stdout.decode(errors="replace")
    return [int(x, 16) for x in HEX.findall(out)], out + r.stderr.decode(errors="replace")


def _platform(wd: Path, model: Path, repl_src: Path, prefix: str) -> Path:
    m = wd / model.name
    m.write_text(re.sub(r'^SCENARIO = .*$', 'SCENARIO = "default"', model.read_text(), flags=re.M))
    repl = wd / "platform.repl"
    repl.write_text(repl_src.read_text().replace(f"{prefix}_MODEL_PATH", str(m)))
    return repl


def registers_check(pkg: dict, model: Path, repl_src: Path, renode: str) -> tuple[list[str], list[str], dict]:
    """(findings, limits, stats) of the load, reset and access checks."""
    P, base = value(pkg, "register_prefix"), int(value(pkg, "base_address"), 16)
    idx = value(pkg, "register_index") or {}
    limits_decl = model_limits(model.read_text())
    regs = sorted(idx.items(), key=lambda kv: kv[1]["offset"])
    cmds, plan = [], []
    for name, d in regs:
        cmds.append(f"sysbus ReadDoubleWord {base + d['offset']:#x}")
        plan.append(("reset", name, None))
    for name, d in regs:
        acc = {a for f in d["fields"].values() for a in f["access"]}
        if acc and acc <= {"r"}:
            for v in (0xFFFFFFFF, 0x0):
                cmds += [f"sysbus WriteDoubleWord {base + d['offset']:#x} {v:#x}",
                         f"sysbus ReadDoubleWord {base + d['offset']:#x}"]
                plan.append(("readonly", name, v))
        elif acc and acc <= {"rc_w0", "r"}:
            cmds += [f"sysbus WriteDoubleWord {base + d['offset']:#x} 0xffffffff",
                     f"sysbus ReadDoubleWord {base + d['offset']:#x}"]
            plan.append(("rc_w0", name, 0xFFFFFFFF))
    with tempfile.TemporaryDirectory(prefix="forge-ob-gate-") as td:
        vals, log = _monitor(renode, Path(td), _platform(Path(td), model, repl_src, P), cmds)
    if len(vals) != len(plan):
        return [f"MODEL_LOAD:{len(vals)}/{len(plan)} register reads answered ({(log.strip().splitlines() or [''])[-1][:160]})"], \
            [], {"reads": len(vals)}
    findings, limits = [], []
    reset_of = {}
    for (kind, name, _), v in zip(plan, vals, strict=True):
        d = idx[name]
        limited = name in limits_decl or any(f"{name}.{f}" in limits_decl for f in d["fields"])
        if kind == "reset":
            reset_of[name] = v
            if d["reset"] is not None and v != d["reset"]:
                (limits if limited else findings).append(
                    f"MODEL_RESET:{name} model 0x{v:08X} RM 0x{d['reset']:08X}")
        elif kind == "readonly" and v != reset_of[name]:
            (limits if limited else findings).append(f"MODEL_ACCESS:{name} read-only register changed to 0x{v:08X}")
        elif kind == "rc_w0" and v & ~reset_of[name]:
            (limits if limited else findings).append(f"MODEL_ACCESS:{name} rc_w0 flags set by writing ones")
    return findings, limits, {"registers": len(regs), "reads": len(vals)}


def smoke(key: str, pkg: dict, renode: str, confirmed: dict, example: Path | None = None) -> list[str]:
    """Build and run the delivered code on the model through the simulator's own build/run path."""
    from ..mcp.servers import sim

    fm = value(pkg, "file_map") or {}
    api = value(pkg, "api") or {}
    inst = value(pkg, "instance")
    spec = json.loads(((example or REPO_ROOT / "examples" / key) / "workorder.json").read_text())
    with tempfile.TemporaryDirectory(prefix="forge-ob-smoke-") as td:
        ws = Path(td) / "ws"
        for f in fm.get("files", []):
            src = Path(os.path.expandvars(spec["delivery"]["source"])) / f["from"]
            (ws / f["to"]).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, ws / f["to"])
        for d in fm.get("dependencies", []):
            src = Path(os.path.expandvars(d["source"])) / d["from"]
            (ws / d["to"]).parent.mkdir(parents=True, exist_ok=True)
            data = src.read_bytes()
            if d.get("configure"):
                from ..brownfield.delivery import configure_hal_conf

                data = configure_hal_conf(data, d["configure"]["hal_modules"])
            (ws / d["to"]).write_bytes(data)
        (ws / ".forge-run").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps(
            {"layer": "HAL", "hal_standalone": True, "peripheral": f"onboarding-preview:{key}",
             "code_mode": "FROZEN", "delivery": {"build": spec["delivery"]["build"]}}))
        stubs = []
        for e in value(pkg, "undelivered_externals") or []:
            if not e.get("prototype"):
                return [f"MODEL_SMOKE:no prototype for the undelivered {e['symbol']}"]
            ret = "void" if e["prototype"].startswith("void ") else None
            if e["role"] == "time_base":
                body = "static uint32_t t; t++; return t;"
            elif ret:
                body = ""
            else:
                body = f"return {confirmed.get(e['symbol'], 1)}U;"
            args = [a.split()[-1].lstrip("*") for a in e["prototype"].split("(", 1)[1].rstrip(")").split(",")
                    if a.strip() and a.strip() != "void"]
            stubs.append(f"{e['prototype']} {{ {''.join(f'(void){a}; ' for a in args)}{body} }}")
        fns = list(api.get("prototypes") or {})
        init = next((f for f in fns if f.endswith("_Init")), fns[0])
        query = next((f for f in fns if re.search(r"GetState|Read|Get|Is", f)), None)
        if api.get("handle"):
            decl, call = f"static {api['handle']['type']} h;", f"h.Instance = {inst}; (void){init}(&h);" + \
                (f" (void){query}(&h);" if query else "")
        else:
            it = (api.get("init") or {}).get("type")
            decl = f"static {it} cfg;" if it else ""
            call = f"{init}({inst}, {'&cfg' if it else '0'});"
        test = ws / "software/tests/target/test_onboarding_smoke.c"
        test.parent.mkdir(parents=True, exist_ok=True)
        test.write_text('#include "stm32n6xx_hal.h"\n#include "forge_target_test.h"\nFORGE_MAILBOX_DEFINE;\n'
                        + "\n".join(stubs) + f"\n{decl}\nint main(void) {{ FORGE_TEST_BEGIN(); {call} "
                        "TCHECK(1, 1); FORGE_TEST_END(); return 0; }\n")
        from ..peripheral import load

        load.cache_clear()
        elf = Path(td) / "smoke.elf"
        ok, log, errs = sim.build_image(ws, test, elf)
        if not ok:
            return ["MODEL_SMOKE_BUILD:" + "; ".join(errs[:3])]
        res, out = sim.run_image(renode, elf, "default", Path(td), ws)
    if not res or not res["magic_ok"] or not res["done"]:
        return [f"MODEL_SMOKE_RUN:{'no mailbox' if not res else 'did not reach the end marker'}"]
    return []


def check(key: str, confirmed: dict | None = None, pkg: dict | None = None, example: Path | None = None) -> dict:
    """The gate for the model the derived profile of `key` names (an existing model is re-gated, reused)."""
    from ..mcp.servers.sim import renode_bin
    from ..mcp.sdk import tool_version
    from . import facts as F
    from . import onboarding_dir

    renode = renode_bin()
    pkg = pkg or F.read_package(onboarding_dir(key))
    pid = value(pkg, "register_prefix").lower()
    model, repl = SIM_DIR / f"{pid}_model.py", SIM_DIR / f"stm32n6_{pid}.repl"
    if not renode:
        return {"verdict": "FAIL", "findings": ["MODEL_GATE_NOT_RUN:no Renode"], "limits": [], "tool": "renode",
                "version": "none"}
    if not (model.is_file() and repl.is_file()):
        return {"verdict": "FAIL", "findings": [f"MODEL_MISSING:{pid}"], "limits": [], "tool": "renode",
                "version": tool_version(renode)}
    findings, limits, stats = registers_check(pkg, model, repl, renode)
    if not any(f.startswith("MODEL_LOAD") for f in findings):
        findings += smoke(key, pkg, renode, confirmed or {}, example)
    return {"verdict": "FAIL" if findings else "PASS", "findings": findings, "limits": limits, "stats": stats,
            "model": model.name, "tool": "renode", "version": tool_version(renode)}
