"""Feature 016 slice C (OB-T012..OB-T015): behaviour facts of a delivery, derived without any model call.

- file_map + framework_modules: the scope's module files (the files defining or declaring scope functions and their
  `_ex` companions), the framework modules a bounded build loop needs (each "unknown type / implicit declaration"
  mapped to the vendor header that declares it, and that header to its hal_conf module), and the dependencies as the
  compiler's own include closure (`-M`), each mapped to its package and include root
- time_base, timeout_constants, waits: in the code the scope functions reach
- undelivered_externals: a gc-sections link that keeps only what the scope reaches; every undefined symbol that is not
  C library or compiler runtime, with its declaration and the registers its result feeds
- instance_comparisons, host_instance: `Instance ==/!= X` in reached code and the macros it uses
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from ..brownfield import scope as S
from ..brownfield.delivery import HAL_MODULE_LINE, configure_hal_conf
from .facts import Assumption, Fact, Source, derived, not_derived
from .identity import Ctx, cflags, compiler

CONF_TEMPLATE = "stm32n6xx_hal_conf_template.h"
CONF = "stm32n6xx_hal_conf.h"
MAX_ROUNDS = 8
LIBC = re.compile(r"^(_|__aeabi_|__gnu_|mem(cpy|set|move|cmp)$|str\w+$|abort$|exit$|printf$|puts$|main$)")


# ---- file map and modules -------------------------------------------------------------------------------------------
def module_files(ctx: Ctx, defs: dict[str, list[S.Definition]]) -> list[Path]:
    from .identity import _declared_in

    rels = {d.file for ds in defs.values() for d in ds} | {f for n in defs for f, _ in _declared_in(ctx, n)}
    paths = {ctx.source.parent / r if r.split("/", 1)[0] == ctx.source.name else ctx.source / r for r in rels}
    for p in list(paths):
        if not p.stem.endswith("_ex"):
            for suf in (".c", ".h"):
                ex = p.with_name(f"{p.stem}_ex{suf}")
                if ex.is_file() and (suf == ".h" or p.with_suffix(".c") in paths):
                    paths.add(ex)
    return sorted(paths)


def _hal_inc(ctx: Ctx) -> Path | None:
    for k in ctx.packages:
        if (Path(k["include_root"]) / CONF_TEMPLATE).is_file():
            return Path(k["include_root"])
    return None


def _conf_map(inc: Path) -> dict[str, str]:
    """{header file name: hal_conf module} from the template's '#ifdef HAL_<M>_MODULE_ENABLED / #include' pairs."""
    text = (inc / CONF_TEMPLATE).read_text(errors="replace")
    return {h: m for m, h in re.findall(r"#ifdef\s+HAL_([A-Z0-9]+)_MODULE_ENABLED\s*\n\s*#include\s+\"([^\"]+)\"", text)}


def _module_of_header(name: str, cmap: dict[str, str]) -> str | None:
    if name in cmap:
        return cmap[name]
    base = re.sub(r"_ex\.h$", ".h", name)
    return cmap.get(base)


def _declaring_header(inc: Path, name: str) -> str | None:
    rx = re.compile(rf"(}}\s*{re.escape(name)}\s*;|typedef\s[^;]*\b{re.escape(name)}\s*;|\b{re.escape(name)}\s*\([^;]*\)\s*;"
                    rf"|#define\s+{re.escape(name)}\b)")
    for h in sorted(inc.glob("*.h")):
        if h.name == CONF_TEMPLATE:
            continue
        if name in (t := h.read_text(errors="replace")) and rx.search(t):
            return h.name
    return None


MISSING = re.compile(r"(?:unknown type name|implicit declaration of function|'?(\w+)'? undeclared)\s*'?(\w*)'?")


def _missing_names(log: str) -> list[str]:
    out = []
    for m in re.finditer(r"(?:unknown type name '(\w+)'|implicit declaration of function '(\w+)'|'(\w+)' undeclared)",
                         log):
        out.append(next(g for g in m.groups() if g))
    return list(dict.fromkeys(out))


def _units(code: list[Path], hal: bool, td: Path) -> list[Path]:
    units = [p for p in code if p.suffix == ".c"]
    for p in code:
        if p.suffix == ".h":
            tu = td / f"_tu_{p.stem}.c"
            tu.write_text(('#include "stm32n6xx_hal.h"\n' if hal else "") + f'#include "{p.name}"\n')
            units.append(tu)
    return units


def _compile(ctx: Ctx, units: list[Path], incs: list[Path], extra: list[str]) -> tuple[int, str]:
    cc = compiler()
    rc, log = 0, []
    for u in units:
        r = subprocess.run([cc, "-fsyntax-only", "-Wall", *extra, *cflags(ctx), *[f"-I{i}" for i in incs], str(u)],
                           capture_output=True, text=True, timeout=120, check=False)
        rc = rc or r.returncode
        log.append(r.stdout + r.stderr)
    return rc, "\n".join(log)


def file_map_and_modules(ctx: Ctx, defs: dict[str, list[S.Definition]], style: str) -> tuple[list[Fact], dict]:
    """Facts file_map and framework_modules, plus {"files", "dependencies", "missing"} for the delivery block."""
    if not compiler():
        q = "The Arm GNU toolchain is not installed on the factory host: the file map cannot be derived."
        return [not_derived("file_map", "build_closure", q), not_derived("framework_modules", "build_closure", q)], {}
    code = module_files(ctx, defs)
    hal = style.startswith("HAL")
    dest = "software/hal" if hal else "software/ll"
    inc = _hal_inc(ctx) if hal else None
    cmap = _conf_map(inc) if inc else {}
    mods: list[str] = []
    if hal:
        main = next((p for p in code if p.suffix == ".h" and p.name in cmap), None)
        mods = [cmap[main.name]] if main else []
    srcs: list[Source] = []
    log, rc, missing = "", 1, []
    with tempfile.TemporaryDirectory(prefix="forge-ob-build-") as tds:
        td = Path(tds)
        units = _units(code, hal, td)
        incs = sorted({p.parent for p in code})
        for rnd in range(1, MAX_ROUNDS + 1):
            if hal and inc:
                (td / CONF).write_bytes(configure_hal_conf((inc / CONF_TEMPLATE).read_bytes(), mods))
            rc, log = _compile(ctx, units, [td, *incs], [])
            names = _missing_names(log)
            if rc == 0 and not names:
                break
            added = []
            for n in names:
                h = _declaring_header(inc, n) if inc else None
                m = _module_of_header(h, cmap) if h else None
                if m and m not in mods and m not in added:
                    added.append(m)
                    srcs.append(Source("log", f"onboarding build round {rnd}", value=f"{n} -> {h} -> {m}"))
                elif not h:
                    missing.append(n)
            if not added:
                break
            mods += added
        if rc != 0:
            q = "The delivered code does not build with the derived framework modules: " + \
                (", ".join(dict.fromkeys(missing)) or log.strip().splitlines()[-1][:160] if log.strip() else "no log")
            return [not_derived("file_map", "build_closure", q), not_derived("framework_modules", "build_closure", q)], \
                {"missing": sorted(set(missing))}
        deps = _include_closure(ctx, units, [td, *incs])
    files = [{"from": _from(ctx, p), "to": f"{dest}/{p.name}"} for p in code]
    dmap = []
    for p in deps:
        if p.parent == td or p.name == CONF:
            continue
        pkg, root = _package_of(ctx, p)
        if pkg is None or p in code:
            continue
        dmap.append({"from": p.resolve().relative_to(Path(pkg["root"]).resolve()).as_posix(),
                     "to": f"inputs/vendor/include/{p.resolve().relative_to(root.resolve()).as_posix()}",
                     "origin": pkg["origin"], "licence": pkg["licence"], "package": str(pkg["root"])})
    if hal and inc:
        pkg, _ = _package_of(ctx, inc / CONF_TEMPLATE)
        dmap.append({"from": (inc / CONF_TEMPLATE).resolve().relative_to(Path(pkg["root"]).resolve()).as_posix(),
                     "to": f"inputs/vendor/include/{CONF}", "origin": pkg["origin"], "licence": pkg["licence"],
                     "package": str(pkg["root"]), "configure": {"hal_modules": mods}})
    dmap.sort(key=lambda x: x["to"])
    srcs = [Source("log", "onboarding build check (syntax, -Wall)", value="PASS"), *srcs]
    facts = [derived("file_map", {"files": files, "dependencies": [{k: v for k, v in d.items() if k != "package"}
                                                                   for d in dmap]}, "build_closure", *srcs)]
    if hal:
        facts.append(derived("framework_modules", mods, "build_closure", *srcs))
    return facts, {"files": files, "dependencies": dmap, "missing": sorted(set(missing))}


def _from(ctx: Ctx, p: Path) -> str:
    return p.resolve().relative_to(ctx.source.resolve()).as_posix()


def _package_of(ctx: Ctx, p: Path) -> tuple[dict | None, Path | None]:
    rp = p.resolve()
    for k in ctx.packages:
        root = Path(k["include_root"]).resolve()
        if root in rp.parents:
            return k, root
    return None, None


def _include_closure(ctx: Ctx, units: list[Path], incs: list[Path]) -> list[Path]:
    cc = compiler()
    out: dict[Path, None] = {}
    for u in units:
        r = subprocess.run([cc, "-M", *cflags(ctx), *[f"-I{i}" for i in incs], str(u)], capture_output=True, text=True,
                           timeout=120, check=False)
        for tok in r.stdout.replace("\\\n", " ").split()[1:]:
            if tok.endswith(".h"):
                out[Path(tok)] = None
    return list(out)



# ---- reached code ---------------------------------------------------------------------------------------------------
CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
KEYWORDS = {"if", "while", "for", "switch", "return", "sizeof", "do", "else"}


def _strip_asserts(body: str) -> str:
    """assert_param(...) compiles to nothing with USE_FULL_ASSERT off (as delivered): its argument is not reached."""
    out, i = [], 0
    for m in re.finditer(r"\bassert_param\s*\(", body):
        if m.start() < i:
            continue
        out.append(body[i:m.start()])
        j = S._balanced(body, m.end() - 1, "(", ")")
        i = j + 1 if j >= 0 else len(body)
    out.append(body[i:])
    return "".join(out)


def reached(ctx: Ctx, code: list[Path], header_paths: list[Path]) -> tuple[dict[str, S.Definition], dict[str, S.Definition]]:
    """(functions, macros) the scope functions reach: their bodies, the module functions they call and the
    function-like macros (module or framework) they use, transitively."""
    defs: dict[str, S.Definition] = {}
    for p in code:
        for d in S.index(p.read_text(errors="replace"), ctx.rel(p)):
            if d.kind != "macro" or d.name not in defs:
                defs.setdefault(d.name, d)
    macros: dict[str, S.Definition] = {k: v for k, v in defs.items() if v.kind == "macro"}
    for h in header_paths:
        text = h.read_text(errors="replace")
        if "#define" in text:
            for d in S.index(text, ctx.rel(h)):
                if d.kind == "macro":
                    macros.setdefault(d.name, d)
    funcs = {k: v for k, v in defs.items() if v.kind != "macro"}
    todo = [n for n in ctx.delivery["scope"]["functions"] if n in funcs]
    seen_f: dict[str, S.Definition] = {}
    seen_m: dict[str, S.Definition] = {}
    while todo:
        n = todo.pop()
        d = funcs.get(n) or macros.get(n)
        if d is None or n in seen_f or n in seen_m:
            continue
        (seen_m if d.kind == "macro" else seen_f)[n] = d
        for c in CALL.findall(_strip_asserts(d.body)):
            if c not in KEYWORDS and (c in funcs or c in macros) and c not in seen_f and c not in seen_m:
                todo.append(c)
    return seen_f, seen_m


def _body(d: S.Definition) -> str:
    return _strip_asserts(d.body)


def _line(d: S.Definition, pos: int) -> int:
    return d.line + d.body.count("\n", 0, pos)


def time_base(funcs: dict[str, S.Definition], header_paths: list[Path], ctx: Ctx) -> Fact:
    """A framework `uint32_t f(void)` the reached code calls next to a timeout (Timeout / tickstart)."""
    cands = {}
    for h in header_paths:
        for m in re.finditer(r"^\s*uint32_t\s+(\w+)\s*\(\s*void\s*\)\s*;", h.read_text(errors="replace"), re.M):
            cands.setdefault(m.group(1), h)
    hits = []
    for d in funcs.values():
        b = _body(d)
        if not re.search(r"timeout|tickstart", b, re.I):
            continue
        for m in CALL.finditer(b):
            if m.group(1) in cands:
                hits.append((m.group(1), d, m.start()))
    if not hits:
        return derived("time_base", "NONE", "reached_time_base_call",
                       Source("log", "reached code of the scope functions", value="no framework time base called"))
    names = sorted({h[0] for h in hits})
    if len(names) > 1:
        return not_derived("time_base", "reached_time_base_call", "The reached code calls several time bases: "
                           + ", ".join(names) + " - which bounds the waits?")
    srcs = [Source("file", d.file, line=_line(d, pos), value=n) for n, d, pos in hits[:8]]
    return derived("time_base", names[0], "reached_time_base_call", *srcs)


def timeout_constants(funcs: dict[str, S.Definition], header_paths: list[Path], code: list[Path], ctx: Ctx) -> Fact:
    used = sorted({t for d in funcs.values() for t in re.findall(r"\b(\w*TIMEOUT\w*)\b", _body(d))
                   if not re.search(r"ERROR|STATE|FLAG", t)})  # HAL_SPI_ERROR_TIMEOUT is an error code
    srcs, val = [], {}
    for h in [*code, *header_paths]:
        for i, line in enumerate(h.read_text(errors="replace").splitlines(), 1):
            m = re.match(r"\s*#\s*define\s+(\w*TIMEOUT\w*)\s+(\S+)", line)
            if m and m.group(1) in used and m.group(1) not in val:
                val[m.group(1)] = m.group(2)
                srcs.append(Source("file", ctx.rel(h), line=i, value=m.group(2)))
    if not srcs:
        return derived("timeout_constants", {}, "reached_timeout_defines",
                       Source("log", "reached code of the scope functions", value="no *TIMEOUT* constant used"))
    return derived("timeout_constants", dict(sorted(val.items())), "reached_timeout_defines", *srcs)


LOOP = re.compile(r"\b(while|for)\s*\(")
# a hardware poll reads a register: through the handle's Instance, an instance pointer named the ST way (USARTx->,
# GPIOx->), a CMSIS instance (RCC->) or a flag macro; GPIO_Init->Pin is a configuration field, not a register
FLAG = re.compile(r"Instance\s*->|\b[A-Z][A-Z0-9]*x\s*->|\b[A-Z][A-Z0-9]+\s*->|GET_FLAG|READ_BIT|IS_BIT_SET|"
                  r"IS_BIT_CLR|_IsActiveFlag|_IsReady")


def waits(funcs: dict[str, S.Definition], tb: str | None) -> Fact:
    """Loops whose condition polls the hardware (a register, a flag macro), each classified by what bounds it."""
    out, srcs = [], []
    for d in sorted(funcs.values(), key=lambda x: (x.file, x.line)):
        b = _body(d)
        for m in LOOP.finditer(b):
            ce = S._balanced(b, m.end() - 1, "(", ")")
            if ce < 0:
                continue
            cond = b[m.end():ce]
            if not FLAG.search(cond):
                continue
            k = ce + 1
            while k < len(b) and b[k].isspace():
                k += 1
            be = S._balanced(b, k, "{", "}") if k < len(b) and b[k] == "{" else b.find(";", k)
            loop = cond + " " + b[k:be + 1 if be > 0 else len(b)]
            if (tb and tb != "NONE" and tb in loop) or re.search(r"\bTimeout\b|tickstart", loop, re.I):
                bound = "time_base"
            elif re.search(r"(\w+)\s*--|--\s*\w+|count", loop, re.I):
                bound = "iterations"
            else:
                bound = "unbounded"
            out.append({"function": d.name, "file": d.file, "line": _line(d, m.start()), "bound": bound})
            srcs.append(Source("file", d.file, line=_line(d, m.start()), value=bound))
    if not out:
        return derived("waits", [], "reached_flag_loops",
                       Source("log", "reached code of the scope functions", value="no hardware polling loop"))
    return derived("waits", out, "reached_flag_loops", *srcs[:16])


def instance_comparisons(funcs: dict[str, S.Definition], macros: dict[str, S.Definition], instances: set[str],
                         inst: str) -> list[Fact]:
    """Device instances the reached code (and the macros it uses) compares a pointer against; the scope instance,
    when compared, is the host mapping fact (host tests must map it to the RAM struct, feature 015 exit-11)."""
    hits: dict[str, Source] = {}
    for d in [*funcs.values(), *macros.values()]:
        b = _body(d)
        for rx in (r"[!=]=\s*\(?\s*(\w+)", r"(\w+)\s*\)?\s*[!=]="):  # both sides of == / !=
            for m in re.finditer(rx, b):
                tok = re.sub(r"_N?S$", "", m.group(1))  # CMSIS macros compare the aliases TIM2_S / TIM2_NS
                if tok in instances and tok not in hits:
                    hits[tok] = Source("file", d.file, line=_line(d, m.start()), value=tok)
    val = sorted(hits)
    srcs = [hits[k] for k in val] or [Source("log", "reached code and macros", value="no instance comparison")]
    facts = [derived("instance_comparisons", val, "reached_instance_compare", *srcs)]
    if inst in hits:
        facts.append(derived("host_instance", inst, "reached_instance_compare", hits[inst]))
    else:
        facts.append(derived("host_instance", "NONE", "reached_instance_compare",
                             Source("log", "reached code and macros", value=f"{inst} not compared")))
    return facts


# ---- undelivered externals --------------------------------------------------------------------------------------
UNDEF = re.compile(r"undefined reference to `([^']+)'")


def undelivered_externals(ctx: Ctx, code: list[Path], dep_dirs: list[Path], conf_dir: Path | None, style: str,
                          funcs: dict[str, S.Definition], prefix: str | None, tb: str | None,
                          header_paths: list[Path]) -> tuple[Fact, list[Assumption]]:
    """Link what the scope reaches (gc-sections from references to every scope function); undefined symbols that are
    not C library / compiler runtime are undelivered. A non-void one whose result reaches a register write needs a
    test-environment assumption (its value is the environment's choice, not the inputs')."""
    cc = compiler()
    if not cc:
        return not_derived("undelivered_externals", "gc_link_undefined", "No Arm GNU toolchain on the factory host."), []
    names = ctx.delivery["scope"]["functions"]
    hal = style.startswith("HAL")
    module_h = [p.name for p in code if p.suffix == ".h" and not p.stem.endswith("_ex")]
    with tempfile.TemporaryDirectory(prefix="forge-ob-link-") as tds:
        td = Path(tds)
        main = td / "forge_ob_main.c"
        main.write_text(('#include "stm32n6xx_hal.h"\n' if hal else "") +
                        "".join(f'#include "{h}"\n' for h in module_h) +
                        "void *volatile forge_ob_keep[] = {" + ", ".join(f"(void *)&{n}" for n in names) + "};\n"
                        "int main(void) { return forge_ob_keep[0] != 0; }\n")
        incs = [*(([conf_dir]) if conf_dir else []), *sorted({p.parent for p in code}), *dep_dirs]
        cmd = [cc, *cflags(ctx), *[f"-I{i}" for i in incs], "-O1", "-ffunction-sections", "-fdata-sections",
               "-nostartfiles", "-specs=nosys.specs", "-Wl,--gc-sections", "-Wl,-e,main",
               str(main), *[str(p) for p in code if p.suffix == ".c"], "-o", str(td / "a.elf")]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    log = r.stdout + r.stderr
    syms = sorted({s for s in UNDEF.findall(log) if not LIBC.match(s)})
    if r.returncode != 0 and not syms:
        return not_derived("undelivered_externals", "gc_link_undefined",
                           "The reached code does not link: " + (log.strip().splitlines() or ["no log"])[-1][:200]), []
    out, asm = [], []
    for s in syms:
        decl = _prototype(s, header_paths)
        feeds = _feeds(s, funcs, prefix)
        role = "time_base" if s == tb else ("value" if decl and not decl[0].startswith("void ") else "procedure")
        out.append({"symbol": s, "prototype": decl[0] if decl else None, "role": role, "feeds": feeds})
        if role == "value":
            asm.append(Assumption(f"ASM-{s.upper().replace('_', '-')}", s,
                                  f"{s} is not delivered; its return value is chosen by the test environment",
                                  [f"{prefix}_{r}" for r in feeds] or [f"return value of {s}"]))
    srcs = [Source("log", "onboarding gc-sections link (scope functions as roots)", value=syms or "none")]
    srcs += [Source("file", d[1], line=d[2], value=s) for s in syms if (d := _prototype(s, header_paths))]
    return derived("undelivered_externals", out, "gc_link_undefined", *srcs), asm


def _prototype(sym: str, header_paths: list[Path]) -> tuple[str, str, int] | None:
    for h in header_paths:
        for i, line in enumerate(h.read_text(errors="replace").splitlines(), 1):
            if sym in line:
                m = re.match(rf"\s*((?:\w+\s+)+\**\s*{re.escape(sym)}\s*\([^;]*\))\s*;", line)
                if m:
                    return " ".join(m.group(1).split()), h.name, i
    return None


def _feeds(sym: str, funcs: dict[str, S.Definition], prefix: str | None) -> list[str]:
    """Registers written (inside the same reached function) from a variable that holds the symbol's result."""
    regs: set[str] = set()
    for d in funcs.values():
        b = _body(d)
        if sym not in b:
            continue
        tainted = set(re.findall(rf"\b(\w+)\s*=\s*[^;=]*\b{re.escape(sym)}\s*\(", b))
        changed = True
        while changed:
            changed = False
            for v, rhs in re.findall(r"\b(\w+)\s*=\s*([^;=][^;]*);", b):
                if v not in tainted and any(re.search(rf"\b{re.escape(t)}\b", rhs) for t in tainted):
                    tainted.add(v)
                    changed = True
        for t in tainted:
            for m in re.finditer(r"->\s*(\w+)\s*=\s*([^;]*);", b):
                if re.search(rf"\b{re.escape(t)}\b", m.group(2)):
                    regs.add(m.group(1))
            for m in re.finditer(r"(?:WRITE_REG|MODIFY_REG)\s*\(\s*[^,]*->\s*(\w+)\s*,([^;]*)\)\s*;", b):
                if re.search(rf"\b{re.escape(t)}\b", m.group(2)):
                    regs.add(m.group(1))
    return sorted(regs)


__all__ = ["Assumption", "file_map_and_modules", "module_files", "reached"]


def derive(ctx: Ctx, ident: dict, style: str) -> tuple[list[Fact], list[Assumption], dict]:
    """All slice C facts; `ident` is identity.derive()'s intermediate values. Returns (facts, assumptions, delivery
    map {files, dependencies, missing})."""
    from .identity import instance_types

    facts, dmap = file_map_and_modules(ctx, ident["defs"], style)
    if not dmap.get("files"):
        return facts, [], dmap
    code = module_files(ctx, ident["defs"])
    headers = [Path(d["package"]) / d["from"] for d in dmap["dependencies"] if not d.get("configure")]
    dep_dirs = sorted({Path(k["include_root"]) for k in ctx.packages})
    funcs, macros = reached(ctx, code, headers)
    tb = time_base(funcs, headers, ctx)
    facts += [tb, timeout_constants(funcs, headers, code, ctx), waits(funcs, tb.value)]
    if ident.get("instance"):
        facts += instance_comparisons(funcs, macros, set(instance_types(ctx)), ident["instance"])
    with tempfile.TemporaryDirectory(prefix="forge-ob-conf-") as tds:
        conf_dir = None
        conf = next((d for d in dmap["dependencies"] if d.get("configure")), None)
        if conf:
            conf_dir = Path(tds)
            (conf_dir / CONF).write_bytes(configure_hal_conf((Path(conf["package"]) / conf["from"]).read_bytes(),
                                                             conf["configure"]["hal_modules"]))
        ext, asm = undelivered_externals(ctx, code, dep_dirs, conf_dir, style, funcs, ident.get("prefix"),
                                         tb.value if tb.status == "DERIVED" else None, headers)
    facts.append(ext)
    return facts, asm, dmap
