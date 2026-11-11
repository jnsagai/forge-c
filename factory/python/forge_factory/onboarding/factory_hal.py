"""Feature 016 OB-T066..OB-T069 (owner decision 2026-11-11, "Extend 016 to factory HAL"): onboarding of a HAL the
factory writes on top of the factory's own verified LL driver (driver style HAL_ON_LL).

The HAL work order holds owner inputs only: the driver, the target, the RM inputs, the budgets and the block
`onboarding: {"style": "HAL_ON_LL", "ll_example": "<LL example>"}`. Everything else is derived without a model call:

- the identity facts (instance, base address, page, register index, delivery file map, model gate) come from the LL
  lineage example's delivery, read against the HAL work order's own RM inputs;
- `ll_api`: the LL scope functions with their prototypes, their kind (setter, flag query, ...) and their register
  effects, read from the delivered LL code; `ll_lineage`: the LL example and the hash of its work order;
- the HAL design is one template rule per LL function kind (`plan`), and every prompt text, the HAL scope and the
  semantic required operations are rendered from it (`texts`): nothing is hand-written per driver (OB-T035..OB-T037
  closed as not needed);
- the budgets and the simulation performance budget are assumptions the owner confirms in the signed approval."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..brownfield import scope as S
from ..common import sha256_file
from .facts import Assumption, Fact, Source, derived, not_derived, value

STYLE = "HAL_ON_LL"
EXAMPLE_NAME = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")
BUDGETS = (("ASM-BUDGET-FLASH", "budgets.flash_bytes", "flash budget of the HAL (bytes)", ["SWE.3 size check",
                                                                                          "SWE.6 verification"]),
           ("ASM-BUDGET-RAM", "budgets.static_ram_bytes", "static RAM budget of the HAL (bytes)",
            ["SWE.3 size check", "SWE.6 verification"]),
           ("ASM-BUDGET-STACK", "budgets.stack_bytes", "stack budget of the HAL (bytes)",
            ["SWE.3 size check", "SWE.6 verification"]))
SIM_PERF = (("ASM-SIM-PERF-INSTRUCTIONS", "simulation_performance.instructions_per_call",
             "instructions per HAL call on the simulated target"),
            ("ASM-SIM-PERF-MICROSECONDS", "simulation_performance.microseconds_per_call",
             "microseconds per HAL call on the simulated target"),
            ("ASM-SIM-PERF-MIPS", "simulation_performance.performance_mips", "simulated core performance (MIPS)"))
SIM_PERF_SCHEMA = "forge-c/simulation-performance-budget/1"
SIM_PERF_TEST = "software/tests/target/test_performance.c"


class FactoryHalError(ValueError):
    pass


# ---- work order ----------------------------------------------------------------------------------------------------
def block(spec: dict) -> dict | None:
    """The owner's onboarding block of a factory-HAL work order, None for any other work order."""
    ob = spec.get("onboarding")
    return ob if isinstance(ob, dict) and ob.get("style") == STYLE else None


def is_factory_hal(example: Path) -> bool:
    try:
        return block(json.loads((Path(example) / "workorder.json").read_text())) is not None
    except (OSError, ValueError):
        return False


def ll_example_dir(example: Path, ob: dict) -> Path:
    name = str(ob.get("ll_example") or "")
    if not EXAMPLE_NAME.fullmatch(name):
        raise FactoryHalError(f"ONBOARDING_LL_EXAMPLE_INVALID:{name!r}")
    return Path(example).parent / name


def _rm_inputs(example: Path, spec: dict) -> dict[str, Path]:
    out = {}
    for item in spec.get("inputs") or []:
        p = (Path(example) / item["path"]).resolve()
        if "memory_map" in item["role"]:
            out["memory_map"] = p
        elif item["role"].startswith("reference_manual") and "chapter" in item["role"]:
            out["chapter"] = p
    return out


def context(example: Path):
    """(LL lineage context, HAL work order context): the LL example's delivery and scope, read against the HAL work
    order's own RM inputs and its owner instance (target.instance); plus the input-consistency gaps."""
    from . import identity as I

    example = Path(example)
    spec = json.loads((example / "workorder.json").read_text())
    ob = block(spec)
    if ob is None:
        raise FactoryHalError("ONBOARDING_NOT_FACTORY_HAL")
    llx = ll_example_dir(example, ob)
    if not (llx / "workorder.json").is_file():
        raise FactoryHalError(f"ONBOARDING_LL_EXAMPLE_MISSING:{ob['ll_example']}")
    ctx = I.context(llx)
    if ctx.spec.get("layer") != "LL" or not ctx.delivery.get("scope"):
        raise FactoryHalError(f"ONBOARDING_LL_EXAMPLE_NOT_LL:{ob['ll_example']}")
    inst = (spec.get("target") or {}).get("instance")
    if inst:
        ctx.spec = {**ctx.spec, "target": {**(ctx.spec.get("target") or {}), "instance": inst}}
    own, ll = _rm_inputs(example, spec), _rm_inputs(llx, ctx.spec)
    ctx.rm_chapter, ctx.rm_memory_map = own.get("chapter"), own.get("memory_map")
    missing = []
    for k in ("chapter", "memory_map"):
        a, b = own.get(k), ll.get(k)
        if a is None or not a.is_file():
            missing.append((f"rm_{k}", f"the HAL work order has no RM {k.replace('_', ' ')} input"))
        elif b is not None and b.is_file() and sha256_file(a) != sha256_file(b):
            missing.append((f"ll_lineage_rm_{k}", f"the HAL work order's RM {k.replace('_', ' ')} differs from the "
                                                  "LL lineage's: the LL facts would not hold for it"))
    hal = I.Ctx(example, spec, ctx.source)
    return ctx, hal, missing


def restyle(facts: list[Fact], hal) -> list[Fact]:
    """driver_style HAL_ON_LL: the owner's onboarding block over an LL lineage (its scope functions are LL_)."""
    old = next((f for f in facts if f.name == "driver_style"), None)
    rest = [f for f in facts if f.name != "driver_style"]
    ob = block(hal.spec)
    if old is None or old.value != "LL":
        return rest + [not_derived("driver_style", "workorder_onboarding_style+ll_lineage_style",
                                   f"The LL lineage {ob['ll_example']} is not an LL delivery (style "
                                   f"{old.value if old else None}): which LL does the HAL build on?",
                                   Source("workorder", "onboarding.style", value=STYLE))]
    return rest + [derived("driver_style", STYLE, "workorder_onboarding_style+ll_lineage_style",
                           Source("workorder", "onboarding.style", value=STYLE),
                           Source("workorder", f"examples/{ob['ll_example']}/workorder.json:delivery.scope.functions",
                                  value="LL"))]


def lineage_input(hal) -> dict:
    ob = block(hal.spec)
    p = ll_example_dir(hal.example, ob) / "workorder.json"
    return {"path": f"lineage/{ob['ll_example']}/workorder.json", "role": "ll_lineage_work_order",
            "sha256": sha256_file(p)}


def ll_lineage(ctx, hal) -> Fact:
    ob = block(hal.spec)
    p = ll_example_dir(hal.example, ob) / "workorder.json"
    d = ctx.delivery
    val = {"example": ob["ll_example"], "workorder_sha256": sha256_file(p), "layer": ctx.spec.get("layer"),
           "code_mode": d.get("code_mode"), "functions": len(d["scope"]["functions"])}
    return derived("ll_lineage", val, "onboarding_ll_example",
                   Source("workorder", "onboarding.ll_example", value=ob["ll_example"]),
                   Source("file", f"examples/{ob['ll_example']}/workorder.json", value=val["workorder_sha256"]))


# ---- the LL API ------------------------------------------------------------------------------------------------------
def _defining(ctx, defs: dict) -> dict:
    return {n: next((d for d in ds if d.body.strip() or d.kind != "macro"), ds[0]) for n, ds in defs.items() if ds}


def _path(ctx, rel: str) -> Path:
    return ctx.source.parent / rel if rel.split("/", 1)[0] == ctx.source.name else ctx.source / rel


def _signature(ctx, d) -> tuple[str, str, list[dict]]:
    """(return type, prototype, [{type, name}]) of a delivered definition, read from its file."""
    lines = _path(ctx, d.file).read_text(errors="replace").splitlines()
    text = " ".join(x.strip() for x in lines[max(0, d.line - 3):d.line + 6])
    m = re.search(rf"((?:[A-Za-z_]\w*[\s*]+)+?){re.escape(d.name)}\s*\(([^)]*)\)", text)
    if not m:
        raise FactoryHalError(f"LL_SIGNATURE_UNREADABLE:{d.name}")
    quals = r"\b(?:static|inline|__inline|__STATIC_INLINE|__STATIC_FORCEINLINE|__INLINE|extern)\b"
    ret = " ".join(re.sub(quals, "", m.group(1)).split()) or "void"
    params = []
    for p in m.group(2).split(","):
        p = " ".join(p.split())
        if not p or p == "void":
            continue
        pm = re.match(r"(.*?)(\**)\s*([A-Za-z_]\w*)$", p)
        params.append({"type": (pm.group(1) + pm.group(2)).strip(), "name": pm.group(3)})
    proto = f"{ret} {d.name}({', '.join(p['type'] + ' ' + p['name'] for p in params) or 'void'})".replace("* ", "*")
    return ret, proto, params


def _fields_in(index: dict, reg: str, mask: int | None, *, zero: bool = False) -> list[str]:
    d = index.get(reg)
    if d is None:
        return []
    out = []
    for f, fd in sorted(d["fields"].items(), key=lambda kv: kv[1]["lsb"]):
        fm = ((1 << (fd["msb"] - fd["lsb"] + 1)) - 1) << fd["lsb"]
        if mask is None or (not zero and fm & mask) or (zero and not fm & mask):
            out.append(f)
    return out


def _read_mask(text: str, macros: dict) -> int | None:
    """The mask of READ_BIT(reg, MASK) (balanced: ST writes `READ_BIT(x->SR, F) == (F)`); None for READ_REG."""
    m = re.search(r"READ_BIT\s*\(", text)
    if not m:
        return None
    depth, i, args, cur = 1, m.end(), [], ""
    while i < len(text) and depth:
        ch = text[i]
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if depth == 1 and ch == ",":
            args.append(cur)
            cur = ""
        elif depth:
            cur += ch
        i += 1
    args.append(cur)
    return S.evaluate(args[1].strip(), macros, intrinsics=True) if len(args) == 2 else None


def effects(d, macros: dict, prefix: str, index: dict) -> list[dict]:
    """The register effects of one LL function as {register, fields, op (set|clear|write|read), value}; value is
    "param" for a caller-supplied value, an integer for a constant write."""
    out = []
    for e in S.register_effects(d, macros, "cmsis", None, None, 0, prefix):
        if e.op in ("set", "clear"):
            out.append({"register": e.register, "fields": _fields_in(index, e.register, e.mask), "op": e.op})
        elif e.op == "modify":
            out.append({"register": e.register, "fields": _fields_in(index, e.register, e.clear), "op": "write",
                        "value": "param" if e.mask is None else e.mask})
        elif e.op == "write" and e.mask is None:
            out.append({"register": e.register, "fields": _fields_in(index, e.register, None), "op": "write",
                        "value": "param"})
        elif e.op == "write":  # a constant whole-register write: the fields it writes 0 (rc_w0 flag clears)
            out.append({"register": e.register, "fields": _fields_in(index, e.register, e.mask, zero=True),
                        "op": "write", "value": 0})
        else:
            out.append({"register": e.register, "fields": _fields_in(index, e.register, _read_mask(e.text, macros)),
                        "op": "read"})
    return out


def _kind(tail: str, nvalue: int, ret: str) -> tuple[str, str]:
    for pre, kind in (("IsActiveFlag_", "flag_query"), ("ClearFlag_", "flag_clear"), ("EnableIT_", "it_enable"),
                      ("DisableIT_", "it_disable"), ("IsEnabledIT_", "it_query")):
        if tail.startswith(pre):
            return kind, tail[len(pre):]
    m = re.fullmatch(r"(Enable|Disable|IsEnabled)(\w*)", tail)
    if m and not nvalue:
        return {"Enable": "enable", "Disable": "disable", "IsEnabled": "enable_query"}[m.group(1)], m.group(2)
    if tail.startswith("Set") and nvalue == 1 and ret == "void":
        return "setter", tail[3:]
    if tail.startswith("Get") and not nvalue and ret != "void":
        return "getter", tail[3:]
    if nvalue == 1 and ret == "void":
        return "write", tail
    if not nvalue and ret != "void":
        return "read", tail
    if not nvalue:
        return "action", tail
    return "unsupported", tail


def ll_api(ctx, ident: dict, register_index: dict | None) -> Fact:
    """The LL scope functions as the HAL sees them: prototype, kind, register effects (from the delivered code)."""
    from .identity import device_header

    names = list(ctx.delivery["scope"]["functions"])
    P = ident.get("prefix")
    defs = _defining(ctx, ident.get("defs") or {})
    if not P or not register_index or any(n not in defs for n in names):
        return not_derived("ll_api", "delivered_ll_definitions",
                           "The delivered LL does not define every scope function, or the register index is missing: "
                           "which LL does the HAL build on?" + (f" (undefined: {', '.join(n for n in names if n not in defs)})"
                                                               if any(n not in defs for n in names) else ""))
    dh = device_header(ctx)
    files = sorted({defs[n].file for n in names})
    macros = S.constant_macros(([dh.read_text(errors="replace")] if dh else []) +
                               [_path(ctx, f).read_text(errors="replace") for f in files])
    fp = f"LL_{P}_"
    out, srcs = [], []
    for n in names:
        d = defs[n]
        ret, proto, params = _signature(ctx, d)
        inst = [p for p in params if p["type"].replace("const ", "").rstrip("*").strip().endswith("_TypeDef")]
        vals = [p for p in params if p not in inst]
        kind, key = _kind(n[len(fp):] if n.startswith(fp) else n, len(vals), ret)
        out.append({"name": n, "kind": kind, "key": key, "prototype": proto, "returns": ret,
                    "params": vals, "effects": effects(d, macros, P, register_index)})
        srcs.append(Source("file", d.file, line=d.line, value=n))
    main = _main_enable(out, register_index)
    for f in out:
        if f["kind"] in ("enable", "disable", "enable_query"):
            f["kind"] = ("main_" if f["key"] == main else "toggle_") + f["kind"]
    header = Path(files[0]).name if len(files) == 1 else [Path(f).name for f in files]
    return derived("ll_api", {"header": header, "prefix": fp, "functions": out}, "delivered_ll_definitions", *srcs[:16])


def _main_enable(fns: list[dict], index: dict) -> str | None:
    """The key of the peripheral's main enable: LL_<P>_Enable, else the Enable<X> that sets bit 0 of the register at
    the lowest offset (SPI_CR1.SPE, TIM_CR1.CEN)."""
    keys = [f["key"] for f in fns if f["kind"] == "enable"]
    if "" in keys:
        return ""
    if not index:
        return None
    first = min(index, key=lambda r: index[r]["offset"])
    bit0 = next((f for f, d in index[first]["fields"].items() if d["lsb"] == 0), None)
    for f in fns:
        if f["kind"] == "enable" and any(e["register"] == first and e["op"] == "set" and bit0 in e["fields"]
                                         for e in f["effects"]):
            return f["key"]
    return None


# ---- the HAL design (template rules) --------------------------------------------------------------------------------
def snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower().strip("_")


def _width_mask(fd: dict) -> int:
    return ((1 << (fd["msb"] - fd["lsb"] + 1)) - 1) << fd["lsb"]


def _hex(v: int) -> str:
    return f"0x{v:08X}U"


def plan(pkg: dict, device_macros: set[str] | None = None) -> dict:
    """The factory HAL of a HAL_ON_LL package, one rule per LL function kind:

    - setters and Enable/Disable pairs (other than the peripheral's main enable) and interrupt enables become the fields
      of a configuration that HAL_<P>_Init checks and writes (a value is the register encoding the LL setter takes; a
      selection is 0 or 1), with the peripheral disabled first when the LL can disable it;
    - the main enable becomes HAL_<P>_Start / HAL_<P>_Stop / HAL_<P>_IsEnabled;
    - flag queries and clears become HAL_<P>_GetFlag / HAL_<P>_ClearFlag with HAL_<P>_FLAG_<F> selectors;
    - getters, data writes, data reads and actions become one HAL function each; a setter whose value the LL scope
      also reads back (a getter) is a runtime value and gets HAL_<P>_Set<X> too (the WWDG refresh, the TIM counter);
    - no HAL function waits: the LL scope has no wait, the caller polls and bounds its loop."""
    P, inst = value(pkg, "register_prefix"), value(pkg, "instance")
    ll, index = value(pkg, "ll_api"), value(pkg, "register_index") or {}
    if not (P and inst and ll):
        raise FactoryHalError("FACTORY_HAL_FACTS_MISSING")
    macros = device_macros or set()
    p, hp = P.lower(), f"HAL_{P}_"
    cfg_t = f"hal_{p}_config_t"
    fns = ll["functions"]
    unsupported = [f["name"] for f in fns if f["kind"] == "unsupported"]
    if unsupported:
        raise FactoryHalError("FACTORY_HAL_LL_KIND_UNSUPPORTED:" + ",".join(unsupported))
    by_kind = lambda k: [f for f in fns if f["kind"] == k]  # noqa: E731
    pair = lambda k, key: next((f for f in fns if f["kind"] == k and f["key"] == key), None)  # noqa: E731

    def field_check(f: dict) -> dict:
        e = next((x for x in f["effects"] if x["op"] == "write" and x["fields"]), None)
        if e is None:
            return {"register": None, "fields": [], "mask": None, "allowed": None}
        d = index[e["register"]]
        writable = [x for x in e["fields"] if set(d["fields"][x]["access"]) & {"rw", "w", "rs", "rc_w0", "rc_w1"}]
        allowed = 0
        for x in writable or e["fields"]:
            allowed |= _width_mask(d["fields"][x])
        short = e["register"][len(P) + 1:]
        names = [f"{P}_{short}_{x}" for x in (writable or e["fields"])]
        expr = " | ".join(names) if all(n in macros for n in names) and macros else _hex(allowed)
        lsb = min(d["fields"][x]["lsb"] for x in (writable or e["fields"]))
        first = min((writable or e["fields"]), key=lambda x: d["fields"][x]["lsb"])
        fd = d["fields"][first]
        reset = ((d.get("reset") or 0) >> fd["lsb"]) & ((1 << (fd["msb"] - fd["lsb"] + 1)) - 1)
        sample = ((reset ^ 1) << lsb) & allowed
        return {"register": e["register"], "fields": writable or e["fields"], "mask": expr, "allowed": allowed,
                "check": allowed != 0xFFFFFFFF, "sample": sample, "invalid": (~allowed) & 0xFFFFFFFF}

    config, init_calls = [], []
    for f in fns:
        if f["kind"] == "setter":
            c = field_check(f)
            config.append({"name": snake(f["key"]), "kind": "value", "ll": [f["name"]], **c})
        elif f["kind"] == "toggle_enable":
            off = pair("toggle_disable", f["key"])
            config.append({"name": f"{snake(f['key'])}_enable", "kind": "select", "ll": [f["name"]] +
                           ([off["name"]] if off else []), "effects": {"1": f["effects"],
                                                                       "0": off["effects"] if off else []}})
        elif f["kind"] == "it_enable":
            off = pair("it_disable", f["key"])
            config.append({"name": f"{snake(f['key'])}_it_enable", "kind": "select", "ll": [f["name"]] +
                           ([off["name"]] if off else []), "effects": {"1": f["effects"],
                                                                       "0": off["effects"] if off else []}})
    m_on, m_off, m_q = (next(iter(by_kind(k)), None) for k in ("main_enable", "main_disable", "main_enable_query"))
    api = []
    if config:
        api.append({"name": f"{hp}Init", "proto": f"hal_status_t {hp}Init(const {cfg_t} *p_config)", "kind": "init",
                    "ll": ([m_off["name"]] if m_off else []) + [x for c in config for x in c["ll"]]})
    if m_on:
        api.append({"name": f"{hp}Start", "proto": f"hal_status_t {hp}Start(void)", "kind": "start",
                    "ll": [m_on["name"]], "effects": m_on["effects"]})
    if m_off:
        api.append({"name": f"{hp}Stop", "proto": f"hal_status_t {hp}Stop(void)", "kind": "stop",
                    "ll": [m_off["name"]], "effects": m_off["effects"]})
    if m_q:
        api.append({"name": f"{hp}IsEnabled", "proto": f"hal_status_t {hp}IsEnabled(uint32_t *p_state)",
                    "kind": "query", "ll": [m_q["name"]], "effects": m_q["effects"]})
    flags = []
    for f in by_kind("flag_query"):
        clr = pair("flag_clear", f["key"])
        read = next((e for e in f["effects"] if e["op"] == "read" and e["fields"]), None)
        flags.append({"key": f["key"], "selector": f"{hp}FLAG_{f['key'].upper()}", "query": f["name"],
                      "clear": clr["name"] if clr else None, "register": read["register"] if read else None,
                      "field": read["fields"][0] if read else None, "clear_effects": clr["effects"] if clr else []})
    for f in by_kind("flag_clear"):  # a clear without a query keeps its own selector
        if not any(x["key"] == f["key"] for x in flags):
            flags.append({"key": f["key"], "selector": f"{hp}FLAG_{f['key'].upper()}", "query": None,
                          "clear": f["name"], "register": None, "field": None, "clear_effects": f["effects"]})
    if any(x["query"] for x in flags):
        api.append({"name": f"{hp}GetFlag", "proto": f"hal_status_t {hp}GetFlag(uint32_t flag, uint32_t *p_state)",
                    "kind": "get_flag", "ll": [x["query"] for x in flags if x["query"]]})
    if any(x["clear"] for x in flags):
        api.append({"name": f"{hp}ClearFlag", "proto": f"hal_status_t {hp}ClearFlag(uint32_t flag)",
                    "kind": "clear_flag", "ll": [x["clear"] for x in flags if x["clear"]]})
    for f in fns:
        k = f["kind"]
        setter = pair("setter", f["key"]) if k == "getter" else None
        if setter:  # a value the LL scope writes and reads back is a runtime value (WWDG counter refresh, TIM CNT)
            c = next(c for c in config if setter["name"] in c["ll"])
            api.append({"name": f"{hp}Set{f['key']}", "proto": f"hal_status_t {hp}Set{f['key']}(uint32_t value)",
                        "kind": "setter", "ll": [setter["name"]], "effects": setter["effects"], "field": c["name"]})
        if k == "getter":
            api.append({"name": f"{hp}Get{f['key']}", "proto": f"hal_status_t {hp}Get{f['key']}({f['returns']} "
                        "*p_value)", "kind": "getter", "ll": [f["name"]], "effects": f["effects"]})
        elif k == "write":
            t = f["params"][0]["type"]
            api.append({"name": f"{hp}{f['key']}", "proto": f"hal_status_t {hp}{f['key']}({t} value)", "kind": "write",
                        "ll": [f["name"]], "effects": f["effects"], "type": t})
        elif k == "read":
            api.append({"name": f"{hp}{f['key']}", "proto": f"hal_status_t {hp}{f['key']}({f['returns']} *p_value)",
                        "kind": "read", "ll": [f["name"]], "effects": f["effects"]})
        elif k == "action":
            api.append({"name": f"{hp}{f['key']}", "proto": f"hal_status_t {hp}{f['key']}(void)", "kind": "action",
                        "ll": [f["name"]], "effects": f["effects"]})
    if not api:
        raise FactoryHalError("FACTORY_HAL_EMPTY_API")
    reached = {x for a in api for x in a["ll"]}
    unwrapped = [f["name"] for f in fns if f["name"] not in reached]
    return {"P": P, "p": p, "inst": inst, "hp": hp, "cfg_t": cfg_t, "config": config, "api": api, "flags": flags,
            "disable_first": m_off["name"] if (m_off and config) else None, "unwrapped": unwrapped,
            "ll_header": ll["header"] if isinstance(ll["header"], str) else ll["header"][0], "ll_functions": fns,
            "index": index}


def declarations(pl: dict) -> list[str]:
    """The generated HAL API: the configuration type, the flag selectors and the prototypes (the names the leftover
    check accepts as the package's own)."""
    out = []
    if pl["config"]:
        out.append("typedef struct { " + " ".join(f"uint32_t {c['name']};" for c in pl["config"]) +
                   f" }} {pl['cfg_t']};")
    for i, f in enumerate(pl["flags"]):
        out.append(f"#define {f['selector']} {i}U")
    if pl["flags"]:
        out.append(f"#define {pl['hp']}FLAG_COUNT {len(pl['flags'])}U")
    out += [a["proto"] + ";" for a in pl["api"]]
    return out


# ---- rendering helpers -----------------------------------------------------------------------------------------------
def _rf(reg: str, fields: list[str]) -> str:
    return f"{reg}.{'/'.join(fields)}" if fields else reg


def _effect_text(e: dict, configured: str = "the configured value") -> str:
    if e["op"] == "set":
        return f"set {_rf(e['register'], e['fields'])}"
    if e["op"] == "clear":
        return f"clear {_rf(e['register'], e['fields'])}"
    if e["op"] == "write":
        v = configured if e.get("value") == "param" else f"0x{int(e.get('value') or 0):X}"
        return f"write {v} to {_rf(e['register'], e['fields'])}"
    return f"read {_rf(e['register'], e['fields'])}"


def _a(word: str) -> str:
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def _invalid(pl: dict) -> list[str]:
    out = ["a NULL configuration, state or value pointer"]
    for c in pl["config"]:
        if c["kind"] == "select":
            out.append(f"{_a(c['name'])} other than 0 or 1")
        elif c.get("check"):
            out.append(f"{_a(c['name'])} with bits outside {_rf(c['register'], c['fields'])} (allowed mask "
                       f"{_hex(c['allowed'])})")
    if pl["flags"]:
        out.append(f"a flag selector of {pl['hp']}FLAG_COUNT or above, or a clear of a flag the LL cannot clear"
                   if any(not f["clear"] for f in pl["flags"]) else
                   f"a flag selector of {pl['hp']}FLAG_COUNT or above")
    return out


def _sample(c: dict) -> int:
    return 1 if c["kind"] == "select" else int(c.get("sample") or 0)


def _bad(c: dict) -> int:
    return 2 if c["kind"] == "select" else (int(c["invalid"]) & -int(c["invalid"]))  # lowest disallowed bit


def _init_effects(pl: dict) -> list[str]:
    out = []
    for c in pl["config"]:
        if c["kind"] == "value" and c.get("register"):
            out.append(f"op write {_rf(c['register'], c['fields'])} (the configured {c['name']})")
        elif c["kind"] == "select":
            for v in ("1", "0"):
                for e in c["effects"][v]:
                    if e["op"] in ("set", "clear") and e["fields"]:
                        out.append(f"op {e['op']} {_rf(e['register'], e['fields'])} with {c['name']} {v}")
    return out


def _c_init(pl: dict) -> str:
    # LL calls are written without the instance: the provided-LL rewrite (prompts.providedize, CAPA-131) inserts the
    # profile's instance into every call of a provided LL function, so the text holds no instance twice
    hp, cfg_t = pl["hp"], pl["cfg_t"]
    conds = ["(p_config != NULL)"]
    for c in pl["config"]:
        if c["kind"] == "select":
            conds.append(f"(p_config->{c['name']} <= 1U)")
        elif c.get("check"):
            conds.append(f"((p_config->{c['name']} & ~({c['mask']})) == 0U)")
    lines = [f"hal_status_t {hp}Init(const {cfg_t} *p_config)", "{", "    hal_status_t status = HAL_ERROR;"]
    cond = (" &&\n        ").join(conds)
    lines += [f"    if ({cond})", "    {"]
    if pl["disable_first"]:
        lines.append(f"        {pl['disable_first']}();")
    for c in pl["config"]:
        if c["kind"] == "value":
            lines.append(f"        {c['ll'][0]}(p_config->{c['name']});")
        elif len(c["ll"]) == 2:
            lines += [f"        if (p_config->{c['name']} == 1U)", "        {", f"            {c['ll'][0]}();",
                      "        }", "        else", "        {", f"            {c['ll'][1]}();", "        }"]
        else:
            lines += [f"        if (p_config->{c['name']} == 1U)", "        {", f"            {c['ll'][0]}();",
                      "        }"]
    lines += ["        status = HAL_OK;", "    }", "    return status;", "}"]
    return "\n".join(lines)


def _c_ut(pl: dict) -> str:
    p, hp, cfg_t = pl["p"], pl["hp"], pl["cfg_t"]
    if not pl["config"]:
        a = pl["api"][0]
        return "\n".join([f"static void ut_{p}_{snake(a['name'][len(hp):])}(void)", "{", "    hal_status_t st;",
                          "    ut_reset();", f"    st = {a['name']}({'' if '(void)' in a['proto'] else 'NULL'});",
                          f"    CHECK(\"UT-001\", st == {'HAL_OK' if '(void)' in a['proto'] else 'HAL_ERROR'});",
                          f"    CHECK(\"UT-001-LL\", ll_fake_calls(LL_FAKE_{a['ll'][0]}) == "
                          f"{'1U' if '(void)' in a['proto'] else '0U'});", "}"])
    good = ", ".join(_hex(_sample(c)) if c["kind"] == "value" else "1U" for c in pl["config"])
    bads = [c for c in pl["config"] if c["kind"] == "select" or c.get("check")]
    bad_c = bads[0] if bads else None
    bad = ", ".join((_hex(_bad(c)) if c["kind"] == "value" else "2U") if c is bad_c else
                    (_hex(_sample(c)) if c["kind"] == "value" else "1U") for c in pl["config"])
    first = pl["config"][0]
    lines = [f"static void ut_{p}_init(void)", "{", "    hal_status_t st;", f"    const {cfg_t} cfg = {{{good}}};"]
    if bad_c:
        lines.append(f"    const {cfg_t} bad = {{{bad}}};")
    lines += ["    ut_reset();", f"    st = {hp}Init(&cfg);", "    CHECK(\"UT-001\", st == HAL_OK);"]
    if first["kind"] == "value":
        lines.append(f"    CHECK(\"UT-001-{first['name'].upper()}\", ll_fake_last_arg(LL_FAKE_{first['ll'][0]}, 1U) == "
                     f"{_hex(_sample(first))});  /* argument 1: after the instance */")
    else:
        lines.append(f"    CHECK(\"UT-001-{first['name'].upper()}\", ll_fake_calls(LL_FAKE_{first['ll'][0]}) == 1U);")
    if pl["disable_first"]:
        lines.append(f"    CHECK(\"UT-001-ORDER\", ll_fake_index_of(LL_FAKE_{pl['disable_first']}, 1U) < "
                     f"ll_fake_index_of(LL_FAKE_{first['ll'][0]}, 1U));")
    if bad_c:
        lines += ["    ut_reset();", f"    st = {hp}Init(&bad);", "    CHECK(\"UT-002\", st == HAL_ERROR);",
                  "    CHECK(\"UT-002-NO-LL\", ll_fake_log_count() == 0U);"]
    lines.append("}")
    return "\n".join(lines)


def _fn_does(pl: dict, a: dict) -> str:
    hp = pl["hp"]
    if a["kind"] == "init":
        parts = []
        if pl["disable_first"]:
            parts.append(f"disables the {pl['P']} first ({pl['disable_first']}: the configuration is written while it "
                         "is disabled) and leaves it disabled")
        for c in pl["config"]:
            if c["kind"] == "value":
                parts.append(f"writes {c['name']} through {c['ll'][0]} ({_rf(c['register'], c['fields'])})")
            else:
                parts.append(f"with {c['name']} 1 calls {c['ll'][0]}" +
                             (f", with 0 calls {c['ll'][1]}" if len(c["ll"]) == 2 else ", with 0 calls nothing"))
        return "checks every configuration value first, then " + "; ".join(parts)
    if a["kind"] in ("start", "stop", "action"):
        eff = "; ".join(_effect_text(e) for e in a.get("effects") or [] if e["op"] != "read")
        return f"calls {a['ll'][0]}" + (f" ({eff})" if eff else "")
    if a["kind"] == "query":
        return f"writes 1U to *p_state when {a['ll'][0]} returns 1U, else 0U"
    if a["kind"] == "getter":
        rd = "; ".join(_rf(e["register"], e["fields"]) for e in a.get("effects") or [] if e["op"] == "read")
        return f"writes the {a['ll'][0]} result to *p_value" + (f" ({rd})" if rd else "")
    if a["kind"] == "write":
        eff = "; ".join(_effect_text(e, "value") for e in a.get("effects") or [] if e["op"] != "read")
        return f"calls {a['ll'][0]} with the value" + (f" ({eff})" if eff else "")
    if a["kind"] == "setter":
        c = next(c for c in pl["config"] if c["name"] == a["field"])
        eff = "; ".join(_effect_text(e, "the value") for e in a.get("effects") or [] if e["op"] != "read")
        chk = (f"checks the value as {pl['hp']}Init checks {a['field']} (HAL_ERROR without an LL call), then "
               if c.get("check") else "")
        return chk + f"calls {a['ll'][0]} with the value" + (f" ({eff})" if eff else "")
    if a["kind"] == "read":
        return f"writes the {a['ll'][0]} result to *p_value"
    if a["kind"] == "get_flag":
        return ("writes 1U to *p_state when the selected flag is set, else 0U (" +
                ", ".join(f"{f['selector']}: {f['query']}" + (f", {f['register']}.{f['field']}" if f["field"] else "")
                          for f in pl["flags"] if f["query"]) + ")")
    if a["kind"] == "clear_flag":
        return ("clears the selected flag (" + ", ".join(f"{f['selector']}: {f['clear']}" for f in pl["flags"]
                                                         if f["clear"]) + ")" +
                ("; a flag without an LL clear returns HAL_ERROR" if any(not f["clear"] for f in pl["flags"]) else ""))
    return ""


def _contract(pl: dict) -> list[str]:
    out = []
    for a in pl["api"]:
        if a["kind"] == "init":
            out.append(f"{a['name']} with a valid configuration gets " + ", ".join(_init_effects(pl)) + ", status HAL_OK")
        elif a["kind"] in ("start", "stop", "action", "write", "setter"):
            effs = [e for e in a.get("effects") or [] if e["op"] != "read" and e["fields"]]
            if effs:
                out.append(f"{a['name']}: " + ", ".join(
                    f"op {e['op']} {_rf(e['register'], e['fields'])}" +
                    (" with the written value" if e.get("value") == "param" else
                     (f" value {e['value']}" if e["op"] == "write" else "")) for e in effs) + ", status HAL_OK")
        elif a["kind"] == "clear_flag":
            for f in pl["flags"]:
                for e in f["clear_effects"]:
                    if e["op"] != "read" and e["fields"]:
                        out.append(f"{a['name']}({f['selector']}): op {e['op']} {_rf(e['register'], e['fields'])}" +
                                   (f" value {e['value']}" if e["op"] == "write" else "") + ", status HAL_OK")
        else:
            reads = [e for e in a.get("effects") or [] if e["op"] == "read" and e["fields"]]
            if a["kind"] == "get_flag":
                reads = [{"register": f["register"], "fields": [f["field"]]} for f in pl["flags"] if f["field"]][:1]
            if reads:
                out.append(f"{a['name']} with valid arguments: op no_write with register {reads[0]['register']} and "
                           f"field {reads[0]['fields'][0]}, status HAL_OK")
    return out


def _example_effect(pl: dict) -> dict:
    c = next((c for c in pl["config"] if c["kind"] == "value" and c.get("register")), None)
    if c:
        return {"case": f"INIT_{c['name'].upper()}", "swr": "SWR-002", "register": c["register"],
                "field": c["fields"][0], "op": "write", "value": f"0x{_sample(c):X}", "status": "HAL_OK"}
    a = next(a for a in pl["api"] if any(e["op"] in ("set", "clear") and e["fields"] for e in a.get("effects") or []))
    e = next(e for e in a["effects"] if e["op"] in ("set", "clear") and e["fields"])
    return {"case": snake(a["name"][len(pl["hp"]):]).upper(), "swr": "SWR-002", "register": e["register"],
            "field": e["fields"][0], "op": e["op"], "status": "HAL_OK"}


def _registers(pl: dict) -> list[str]:
    regs = []
    for c in pl["config"]:
        effs = ([{"register": c["register"]}] if c["kind"] == "value" and c.get("register") else
                [e for v in ("1", "0") for e in (c.get("effects") or {}).get(v, [])])
        for e in effs:
            if e["register"] not in regs:
                regs.append(e["register"])
    return regs


def _ll_effect_example(pl: dict) -> tuple[dict, str] | None:
    for f in pl["ll_functions"]:
        for e in f["effects"]:
            if f["kind"] == "setter" and e["op"] == "write" and e["fields"]:
                c = next(c for c in pl["config"] if f["name"] in c["ll"])
                return {"case": f"SET_{f['key'].upper()}", "swr": "SWR-001", "register": e["register"],
                        "field": e["fields"][0], "op": "write", "value": f"0x{_sample(c):X}"}, f["name"]
    for f in pl["ll_functions"]:
        for e in f["effects"]:
            if e["op"] in ("set", "clear") and e["fields"]:
                return {"case": snake(f["key"] or f["kind"]).upper() or "ENABLE", "swr": "SWR-001",
                        "register": e["register"], "field": e["fields"][0], "op": e["op"]}, f["name"]
    return None


# ---- texts ------------------------------------------------------------------------------------------------------------
def texts(pkg: dict, ll_scope: list[str], system_name: str, device_macros: set[str], model: str) -> dict:
    """`prompt` (the base keys + the 15 hal_* keys the feature 009 HAL overlay consumes) and `work_order` (the
    generated HAL scope, the semantic required operations and the HAL declarations) of a HAL_ON_LL package."""
    pl = plan(pkg, device_macros)
    P, p, inst, hp = pl["P"], pl["p"], pl["inst"], pl["hp"]
    base, page, ch = value(pkg, "base_address"), value(pkg, "mm_page"), value(pkg, "rm_chapter")
    doc = ch["doc"]
    llh = pl["ll_header"]
    llstem, halstem = Path(llh).stem, f"stm32n6xx_hal_{p}"
    fnames = [a["name"] for a in pl["api"]]
    T = lambda text, key: {"text": text, "from": f"template:factory_hal.{key}"}  # noqa: E731
    regs = _registers(pl)
    inv = _invalid(pl)
    effx = _example_effect(pl)
    init = next((a for a in pl["api"] if a["kind"] == "init"), None)
    first_v = next((c for c in pl["config"] if c["kind"] == "value" and c.get("register")), None)
    if first_v:
        req = (f"When the {P} initialisation is requested with a valid configuration, the {system_name} shall write the "
               f"configured {first_v['name'].replace('_', ' ')} to {first_v['register']}.{first_v['fields'][0]}.")
    else:
        a = next(a for a in pl["api"] if a["kind"] in ("start", "action", "write"))
        req = (f"When {a['name']} is requested, the {system_name} shall " +
               _effect_text(next(e for e in a["effects"] if e["op"] != "read"), "the requested value") + ".")
    order = ", ".join(fnames)
    flag_txt = ""
    if pl["flags"]:
        f0 = next((f for f in pl["flags"] if f["query"]), pl["flags"][0])
        flag_txt = f"{f0['selector']}, &flag"
    cfg_lit = ", ".join(f".{c['name']} = {_hex(_sample(c)) if c['kind'] == 'value' else '1U'}" for c in pl["config"])
    bad_lits = [f"{_a(c['name'])} of {_hex(_bad(c)) if c['kind'] == 'value' else '2U'}" for c in pl["config"]
                if c["kind"] == "select" or c.get("check")]
    eg = ([f'"&(const {pl["cfg_t"]}){{ {cfg_lit} }}"'] if pl["config"] else []) + \
        ([f'for the flag query "{flag_txt}"'] if flag_txt else [])
    args = ((", e.g. " + " and ".join(eg)) if eg else "") + "; invalid cases pass the invalid value (NULL" + \
        "".join(", " + b for b in bad_lits) + (f", {hp}FLAG_COUNT" if pl["flags"] else "") + ")"
    api_txt = ("Interfaces (each HAL_" + P + "_ API with hal_status_t, built only on the PROVIDED LL_" + P +
               f"_ functions of {llh} (each takes the instance {inst} first; a configuration value is the register "
               "encoding the LL setter takes, i.e. a value of its LL constants): " +
               "; ".join(f"{a['proto']} - {_fn_does(pl, a)}" for a in pl["api"]) +
               (f"; with typedef struct {{{' '.join('uint32_t ' + c['name'] + ';' for c in pl['config'])}}} "
                f"{pl['cfg_t']}" if pl["config"] else "") +
               (f"; the flag selectors {', '.join(f['selector'] for f in pl['flags'])} (0U..{len(pl['flags']) - 1}U) "
                f"and {hp}FLAG_COUNT" if pl["flags"] else "") +
               (f"; no function wraps {', '.join(pl['unwrapped'])} (read-back queries of what Init configures)"
                if pl["unwrapped"] else "") + ")")
    dyn = (f"showing {order} using the allocated HAL_{P}_ function names, each calling its LL_{P}_ functions" +
           (f" (Init: {pl['disable_first']} first, then the configuration)" if pl["disable_first"] else "") +
           ", plus an invalid parameter returning HAL_ERROR without register access")
    checks = "; ".join(inv)
    rest = []
    for a in pl["api"]:
        if a["kind"] != "init":
            rest.append(f"{a['name']} {_fn_does(pl, a)}")
    wait_rest = ("(the parameter checks come first). " + "; ".join(rest) + "; every function returns HAL_OK after its "
                 "LL calls and HAL_ERROR, without any LL call, on an invalid parameter.") if rest else \
        "(the parameter checks come first); it returns HAL_OK after its LL calls."
    contract = ("The oracle sees only the register values after the call: " + "; ".join(_contract(pl)) +
                "; invalid parameter: one entry per invalid value (" + "; ".join(inv) + ") with op no_write and status "
                "HAL_ERROR (no register/field). The call order" +
                (f" ({pl['disable_first']} before the configuration)" if pl["disable_first"] else "") +
                " is verified by the unit tests, not by the contract.")
    ut_rule = []
    if init:
        ut_rule.append(f"{init['name']} gets a valid case (each configured value passed to its LL function" +
                       (f", {pl['disable_first']} called first" if pl["disable_first"] else "") +
                       ") and one HAL_ERROR case per invalid value with no LL call")
    for a in pl["api"]:
        if a["kind"] in ("start", "stop", "action"):
            ut_rule.append(f"{a['name']} checks its {a['ll'][0]} call")
        elif a["kind"] == "write":
            ut_rule.append(f"{a['name']} checks the value passed to {a['ll'][0]}")
        elif a["kind"] == "setter":
            ut_rule.append(f"{a['name']} checks the value passed to {a['ll'][0]}" +
                           (" and an invalid value with no LL call" if next(
                               c for c in pl["config"] if c["name"] == a["field"]).get("check") else ""))
        elif a["kind"] in ("query", "getter", "read"):
            ut_rule.append(f"{a['name']} gets a case with the LL query scripted (ll_fake_return_from) and a NULL "
                           "pointer case")
        elif a["kind"] == "get_flag":
            ut_rule.append(f"{a['name']} gets a flag-set case (the LL query scripted 1U), a flag-clear case, an "
                           "unknown selector and a NULL pointer case")
        elif a["kind"] == "clear_flag":
            ut_rule.append(f"{a['name']} checks the LL clear call and an unknown selector")
    host = f"on the host the registers keep the written values; no {P} flag changes by itself"
    poll = ("the provided LL scope has no wait: the caller polls the flag queries and bounds its loop" if pl["flags"]
            else "the provided LL scope has no wait")
    f0 = next((f for f in pl["flags"] if f["query"] and f["field"]), None)
    integ = ("(" + (f"{init['name']} with a valid configuration on the real LL - the configured values reach "
                    f"{', '.join(regs)} -" if init else f"the HAL functions on the real LL -") +
             (f", then {', '.join(a['name'] for a in pl['api'] if a['kind'] != 'init')}" if len(pl["api"]) > 1 else "") +
             (f" ({f0['register']}.{f0['field']} preset for {hp}GetFlag)" if f0 else "") + f" - {host} -" +
             (f", and an invalid configuration returning HAL_ERROR with {', '.join(regs)} unchanged" if init and regs
              else "") + ")")
    tgt = (f"write software/tests/target/test_{p}_target.c (" +
           (f"{init['name']} with a valid configuration returns HAL_OK on the {P} model and the configured values "
            f"reach {', '.join(regs)}; " if init else "") +
           ", ".join(f"{a['name']} returns HAL_OK" for a in pl["api"] if a["kind"] in ("start", "stop", "action"))
           + ("; " if any(a["kind"] in ("start", "stop", "action") for a in pl["api"]) else "") +
           f"every expected register value and flag follows the simulator description and {doc}) and "
           f"software/tests/target/test_{p}_target_errors.c (each invalid parameter returns HAL_ERROR and leaves the "
           f"{P} registers at their reset values)")
    # base keys: the provided LL as the HAL's lower layer (LL-step instructions of the same profile)
    lx = _ll_effect_example(pl)
    llfns = [f["name"] for f in pl["ll_functions"]]
    first_set = next((f for f in pl["ll_functions"] if f["kind"] == "setter"), None)
    mask_ex = (first_v["mask"].split(" | ")[0] if first_v and not first_v["mask"].startswith("0x") else
               f"{lx[0]['register']}_{lx[0]['field']}" if lx else f"{P}_<REG>_<FIELD>")
    q = next((f for f in pl["ll_functions"] if f["kind"] in ("flag_query", "main_enable_query", "getter")), None)
    ut_ll = None
    if first_set and first_v:
        short = first_v["register"][len(P) + 1:]
        ut_ll = "\n".join([f"static void ut_{p}_{snake(first_set['key'])}(void)", "{", "    ut_reset_regs();",
                           f"    {first_set['name']}({_hex(_sample(first_v))});",
                           f"    CHECK(\"UT-001\", (forge_host_{p}.{short} & ({first_v['mask']})) == "
                           f"{_hex(_sample(first_v))});", "}"])
    elif lx:
        e, fn = lx
        short = e["register"][len(P) + 1:]
        ut_ll = "\n".join([f"static void ut_{p}_{snake(fn[len(P) + 4:])}(void)", "{", "    ut_reset_regs();",
                           f"    {fn}();", f"    CHECK(\"UT-001\", (forge_host_{p}.{short} & "
                           f"{e['register']}_{e['field']}) {'!=' if e['op'] == 'set' else '=='} 0U);", "}"])
    prompt = {
        "swe1_cover": {"text": f"Cover (only what the {P} scope names, for the instance {inst}; name the registers "
                               f"{P}_<REG> as the {doc} {P}x_ registers of the instance): " + "; ".join(ll_scope),
                       "from": "owner:scope"},
        "swe1_effect_example": T(json.dumps(lx[0], separators=(",", ":")) if lx else "{}", "swe1_effect_example"),
        "swe1_effect_rule": T('Use op "write" with "value" (an integer or "0x..." string) for a field the requirement '
                              'writes a value to, op "set"/"clear" for a single bit; a function that writes a '
                              "caller-supplied value gets one entry with a representative value and the api_calls args "
                              "pass that value. Read and query functions get op no_write with register/field.",
                              "swe1_effect_rule"),
        "ll_api": T(f"the ST CubeN6 functions as delivered (each takes the {P}_TypeDef instance pointer first): "
                    f"{', '.join(llfns)}; list in Interfaces exactly the functions of the allocation table", "ll_api"),
        "swe2_static_view": T(f"a Caller, the component {halstem} (HAL), the component {llstem} (LL, header-only, "
                              f"PROVIDED) and the {inst} register block ({base}, {doc} p.{page}) and their dependencies "
                              "(Caller -> HAL -> LL -> registers)", "swe2_static_view"),
        "swe2_dynamic_view": T(f"participants Caller, {llstem}, {inst}, showing {', '.join(llfns)} using the allocated "
                               f"LL_{P}_ function names (the caller bounds every polling loop)", "swe2_dynamic_view"),
        "ut_example": T(ut_ll or "", "ut_example"),
        "ut_rule": T(f"Host unit tests pass the generated host instance {inst} (forge_host_device.h maps it to the RAM "
                     f"struct forge_host_{p}; {base} is the device address and is used on the target only). Set and "
                     "value functions check the written field and that a preset unrelated field of the same register "
                     "is preserved; flag clears check the clear write; queries get a set and a clear case.", "ut_rule"),
        "target_model": {"text": f"The simulated {inst} (factory/sim/stm32n6/{p}_model.py): {model} Expected values in "
                                 "target checks follow this model.", "from": f"model:{p}_model.py"},
        "target_tests": T(f"write software/tests/target/test_{p}_target.c (the scope functions on the simulated {inst}: "
                          "the values written reach their registers; every expected register value follows the "
                          f"simulator description and {doc}) and software/tests/target/test_{p}_target_flags.c (the "
                          "flag queries and clears the simulator can produce)", "target_tests"),
        "field_mask_example": T(mask_ex, "field_mask_example"),
        "query_example": T(f"{q['name']}()" if q else f"{llfns[0]}()", "query_example"),
        "integration": T(f"the LL functions in the order a caller uses them ({', '.join(llfns)}) ({host})",
                         "integration"),
        "requirement_example": T((f"When {first_set['name']} is called with a value, the {P} LL driver shall write the "
                                  f"value to {first_v['register']}.{first_v['fields'][0]}.") if first_set and first_v
                                 else f"When {lx[1]} is called, the {P} LL driver shall {lx[0]['op']} "
                                      f"{lx[0]['register']}.{lx[0]['field']}." if lx else req, "requirement_example"),
        # ---- the 15 HAL keys -----------------------------------------------------------------------------------------
        "hal_requirement_example": T(req, "hal_requirement_example"),
        "hal_reset_example": T(f"(e.g. '- **SWR-0nn** While no {P} initialisation has been requested after reset, the "
                               f"{system_name} shall not write any {P} register.')", "hal_reset_example"),
        "hal_failure_responses": T("one requirement per failure response (invalid parameter -> HAL_ERROR without "
                                   "register writes, naming the invalid values: " + checks + "), and one timing "
                                   f"requirement: every HAL_{P}_ function returns without waiting on a {P} flag "
                                   f"({poll})", "hal_failure_responses"),
        "hal_api": T(api_txt, "hal_api"),
        "hal_dynamic_view": T(dyn, "hal_dynamic_view"),
        "hal_wait_rule": T(f"No HAL_{P}_ function waits ({poll}); each function checks its parameters first ({checks}), "
                           "returning HAL_ERROR before any register write, then calls the LL functions like this "
                           f"example (adapt names; the provided ST LL takes the {P} instance {inst} first and a "
                           "configuration value as the register encoding of its LL constants):", "hal_wait_rule"),
        "hal_example": T(_c_init(pl) if init else
                         "\n".join([f"{pl['api'][0]['proto']}", "{", f"    {pl['api'][0]['ll'][0]}();",
                                    "    return HAL_OK;", "}"]), "hal_example"),
        "hal_wait_rest": T(wait_rest, "hal_wait_rest"),
        "hal_contract_rule": T(contract, "hal_contract_rule"),
        "hal_ut_example": T(_c_ut(pl), "hal_ut_example"),
        "hal_ut_rule": T("; ".join(ut_rule) + ".", "hal_ut_rule"),
        "hal_integration": T(integ, "hal_integration"),
        "hal_effect_example": T(json.dumps(effx, separators=(",", ":")), "hal_effect_example"),
        "hal_args_example": T(args, "hal_args_example"),
        "hal_target_tests": T(tgt, "hal_target_tests"),
    }
    wo = {"scope": T(scope(pl, ll_scope, pkg), "scope"),
          "semantic_required_operations": T(required_operations(pl), "semantic_required_operations"),
          "hal_api": T(declarations(pl), "hal_api_declarations")}
    return {"prompt": prompt, "work_order": wo}


def scope(pl: dict, ll_scope: list[str], pkg: dict) -> list[str]:
    """The HAL work order's scope statements, generated from the plan (the owner reviews them in the summary)."""
    P, hp, inst = pl["P"], pl["hp"], pl["inst"]
    lineage = value(pkg, "ll_lineage") or {}
    out = [f"HAL: hal_status_t API with {hp} prefix and a const configuration pointer, built only on the PROVIDED "
           f"LL_{P}_ functions of {pl['ll_header']} (LL lineage {lineage.get('example')}), for the instance {inst}"]
    for a in pl["api"]:
        out.append(f"{a['name']}: {_fn_does(pl, a)}")
    out.append("Parameter checks before any register write, returning HAL_ERROR: " + "; ".join(_invalid(pl)))
    out.append(f"No {hp} function waits on a {P} flag (the provided LL scope has no wait" +
               ("; the caller polls the flag queries and bounds its loop)" if pl["flags"] else ")"))
    out.append(f"Performance: each {hp} call completes within the simulation performance budget")
    out.append(f"The LL header is provided by a verified {P} LL work order (--provided-from)")
    oos = next((s for s in ll_scope if s.startswith("Out of scope:")), None)
    if oos:
        items = [x.strip() for x in re.split(r",(?![^()]*\))", oos[len("Out of scope:"):]) if x.strip()]
        items = [x for x in items if not re.search(r"\bHAL\b", x)]
        out.append("Out of scope (as for the LL lineage): " + ", ".join(items))
    if pl["unwrapped"]:
        out.append(f"Not wrapped: {', '.join(pl['unwrapped'])} (read-back queries of what {hp}Init configures)")
    return out


def required_operations(pl: dict) -> list[dict]:
    """semantic_required_operations: the source-bound register forms of the LL scope (one per field and action, at
    most 32, in LL scope order)."""
    out, seen = [], set()

    def add(reg, field, action, val=None):
        k = (reg, field, action)
        if k in seen or len(out) >= 32:
            return
        seen.add(k)
        out.append({"register": reg, "field": field, "action": action,
                    **({"logical_value": str(val)} if val is not None else {})})

    for f in pl["ll_functions"]:
        c = next((c for c in pl["config"] if c["kind"] == "value" and f["name"] in c["ll"]), None)
        for e in f["effects"]:
            for fld in e["fields"][:1] if e["op"] == "write" and e.get("value") == "param" else e["fields"]:
                if e["op"] == "read":
                    add(e["register"], fld, "read_field")
                elif e["op"] == "set":
                    add(e["register"], fld, "set_field")
                elif e["op"] == "clear":
                    add(e["register"], fld, "clear_field")
                elif e.get("value") == "param":
                    lv = None
                    if c and c.get("register") == e["register"]:
                        lsb = min(pl["index"][e["register"]]["fields"][x]["lsb"] for x in c["fields"])
                        lv = _sample(c) >> lsb
                    add(e["register"], fld, "write_field", lv if lv is not None else 1)
                else:
                    add(e["register"], fld, "write_field", int(e["value"]))
    return out


# ---- assumptions -----------------------------------------------------------------------------------------------------
def assumptions(spec: dict) -> list[Assumption]:
    """OB-T069: the budgets and the simulation performance budget are owner values: assumptions the owner confirms in
    the signed approval (verify refuses an unconfirmed one); the work order's values are only proposals."""
    out = []
    b, sp = spec.get("budgets") or {}, spec.get("simulation_performance") or {}
    for aid, sym, reason, affects in BUDGETS:
        v = b.get(sym.split(".", 1)[1])
        out.append(Assumption(aid, sym, f"{reason}: an owner value, not derivable from the inputs", affects,
                              v, Source("workorder", sym, value=v) if v is not None else None))
    for aid, sym, reason in SIM_PERF:
        v = sp.get(sym.split(".", 1)[1])
        out.append(Assumption(aid, sym, f"{reason}: an owner value, not derivable from the inputs",
                              ["SWE.5 target performance test", "SWE.6 verification"], v,
                              Source("workorder", sym, value=v) if v is not None else None))
    return out


def apply(spec: dict, pkg: dict, approval: dict) -> dict:
    """OB-T070: the HAL_ON_LL work order as `workorder.prepare` uses it - the package's generated scope and the
    owner-confirmed budgets; a work order with hand-written scope, prompt texts or a delivery is refused (FR-025), and
    a `peripheral` it names must be the package's."""
    from .texts import work_order

    hand = [k for k in spec if k in ("scope", "delivery") or k.startswith("prompt")]
    if hand:
        raise FactoryHalError(f"ONBOARDING_HAND_TEXT_REFUSED:{','.join(sorted(hand))} (a factory-HAL work order holds "
                              "owner inputs only)")
    if pkg.get("driver_style") != STYLE:
        raise FactoryHalError(f"ONBOARDING_STYLE_MISMATCH:{pkg.get('driver_style')}")
    pid = (value(pkg, "register_prefix") or "").lower()
    if spec.get("peripheral") and spec["peripheral"] != pid:
        raise FactoryHalError(f"ONBOARDING_PERIPHERAL_MISMATCH:{spec['peripheral']} (package: {pid})")
    sc = work_order(pkg.get("texts"), "scope")
    if not sc:
        raise FactoryHalError("ONBOARDING_SCOPE_NOT_GENERATED")
    budgets, sim = confirmed_budgets(spec, pkg, approval)
    out = {k: v for k, v in spec.items() if k != "simulation_performance"}
    out.update(scope=list(sc), budgets=budgets)
    if sim:
        out["simulation_performance"] = sim
    return out


def confirmed_budgets(spec: dict, pkg: dict, approval: dict) -> tuple[dict, dict]:
    """(budgets, simulation_performance) of an approved HAL_ON_LL work order: the owner-confirmed assumption values."""
    conf = {c["id"]: c["value"] for c in approval.get("assumption_confirmations") or []}
    budgets, perf = {}, {}
    for a in pkg["assumptions"]:
        group, key = a["symbol"].split(".", 1)
        if a["id"] in conf and conf[a["id"]] is not None and group in ("budgets", "simulation_performance"):
            (budgets if group == "budgets" else perf)[key] = int(conf[a["id"]])
    for k in ("flash_bytes", "static_ram_bytes", "stack_bytes"):
        if k not in budgets:
            raise FactoryHalError(f"ONBOARDING_BUDGET_NOT_CONFIRMED:{k}")
    budgets["status"] = f"owner-confirmed in onboarding approval {approval.get('approval_id')}"
    sim = None
    if perf:
        sim = {"schema": SIM_PERF_SCHEMA, **perf,
               "test_source": (spec.get("simulation_performance") or {}).get("test_source") or SIM_PERF_TEST}
    return budgets, sim
