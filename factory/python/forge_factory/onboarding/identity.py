"""Feature 016 slice B (OB-T008..OB-T010): identity facts of a delivery, derived without any model call.

- instance: the owner's `target.instance`, else the one device-header instance the owner's scope statements name
- base_address + mm_page: the CMSIS #define chain evaluated by the build's own preprocessor (secure or non-secure as
  the build selects), and the RM memory-map row of the instance with its page; disagreement is CONFLICT
- register_prefix: the <P>_TypeDef the instance casts to; register_index: the RM chapter parsed with that prefix
- driver_style, function_prefix, headers: from the scope functions and the files that define and declare them
"""
from __future__ import annotations

import ast
import collections
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..brownfield import scope as S
from ..common import REPO_ROOT, sha256_file
from .facts import Fact, Source, agree, derived, not_derived


@dataclass
class Ctx:
    example: Path
    spec: dict
    source: Path                                          # the delivered code's package root
    packages: list[dict] = field(default_factory=list)    # {root, include_root, origin, licence}
    rm_chapter: Path | None = None
    rm_memory_map: Path | None = None

    @property
    def delivery(self) -> dict:
        return self.spec.get("delivery") or {}

    @property
    def build(self) -> dict:
        return self.delivery.get("build") or {}

    def rel(self, p: Path) -> str:
        for root in [self.source, *(Path(k["root"]) for k in self.packages)]:
            try:
                return f"{root.name}/{Path(p).resolve().relative_to(root.resolve()).as_posix()}"
            except ValueError:
                continue
        try:
            return Path(p).resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return Path(p).name


def _resolve(src: str, example: Path) -> Path:
    from ..brownfield.delivery import _resolve_source

    return _resolve_source(src, example)


def include_root(root: Path) -> Path:
    """The shallowest directory of a package holding headers (ST: Inc, Include; CMSIS core: the package root)."""
    best = None
    for h in sorted(root.rglob("*.h")):
        d = h.parent
        if best is None or len(d.relative_to(root).parts) < len(best.relative_to(root).parts):
            best = d
    return best or root


def context(example: Path) -> Ctx:
    example = Path(example)
    spec = json.loads((example / "workorder.json").read_text())
    d = spec.get("delivery") or {}
    src = _resolve(d["source"], example)
    seen, pkgs = {src.resolve()}, []
    for p in [*(d.get("packages") or []), *(x for x in d.get("dependencies") or [] if x.get("source"))]:
        root = _resolve(p["source"], example)
        if root.resolve() in seen:
            continue
        seen.add(root.resolve())
        pkgs.append({"root": root, "include_root": include_root(root), "origin": p["origin"], "licence": p["licence"]})
    pkgs.insert(0, {"root": src, "include_root": include_root(src), "origin": d.get("origin"), "licence": d.get("licence")})
    chapter = mm = None
    for item in spec.get("inputs") or []:
        p = (example / item["path"]).resolve()
        if "memory_map" in item["role"]:
            mm = p
        elif item["role"].startswith("reference_manual") and "chapter" in item["role"]:
            chapter = p
    return Ctx(example, spec, src, pkgs, chapter, mm)


# ---- preprocessor ------------------------------------------------------------------------------------------------
def compiler() -> str | None:
    return shutil.which("arm-none-eabi-gcc")


def cflags(ctx: Ctx) -> list[str]:
    b = ctx.build
    return ["-std=c11", "-mcpu=cortex-m55", "-mthumb", *(["-mcmse"] if b.get("secure") else []),
            *[f"-D{x}" for x in b.get("defines") or []],
            *[f"-I{k['include_root']}" for k in ctx.packages]]


def preprocess(ctx: Ctx, includes: list[str], exprs: dict[str, str]) -> dict[str, str] | None:
    """Expand `exprs` (name -> C expression) after `includes` with the build's own compiler and flags."""
    cc = compiler()
    if not cc:
        return None
    body = "".join(f'#include "{h}"\n' for h in includes) + \
        "".join(f"FORGE_OB_{k} = {v} ;\n" for k, v in exprs.items())
    with tempfile.TemporaryDirectory(prefix="forge-ob-pp-") as td:
        f = Path(td) / "pp.c"
        f.write_text(body)
        r = subprocess.run([cc, "-E", "-P", *cflags(ctx), str(f)], capture_output=True, text=True, timeout=120,
                           check=False)
    if r.returncode != 0:
        return None
    out = {}
    for m in re.finditer(r"FORGE_OB_(\w+) = (.*?) ;", r.stdout, re.S):
        out[m.group(1)] = " ".join(m.group(2).split())
    return out


def eval_int(expr: str) -> int | None:
    """An integer constant expression of literals (casts and U/L suffixes removed); None when anything else is left."""
    e = re.sub(r"\(\s*\w+_TypeDef\s*\*\s*\)", "", expr)
    e = re.sub(r"\(\s*u?int\d+_t\s*\)", "", e)
    e = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", e)
    try:
        tree = ast.parse(e, mode="eval")
    except SyntaxError:
        return None
    ok = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.LShift, ast.RShift,
          ast.BitOr, ast.BitAnd, ast.USub)
    if not all(isinstance(n, ok) for n in ast.walk(tree)):
        return None
    return int(eval(compile(tree, "<expr>", "eval")))  # noqa: S307 - literal-only AST checked above


def device_header(ctx: Ctx) -> Path | None:
    """The device header the build's define selects (STM32N657xx -> stm32n657xx.h) in a package include root."""
    for d in ctx.build.get("defines") or []:
        for k in ctx.packages:
            p = Path(k["include_root"]) / f"{d.split('=')[0].lower()}.h"
            if p.is_file():
                return p
    return None


def _define_line(path: Path, name: str) -> int | None:
    for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        if re.match(rf"\s*#\s*define\s+{re.escape(name)}\b", line):
            return i
    return None


# ---- instance ----------------------------------------------------------------------------------------------------
def instance_types(ctx: Ctx) -> dict[str, str]:
    """{instance: <P> of its <P>_TypeDef} for the device header's instances."""
    dh = device_header(ctx)
    if not dh:
        return {}
    text = dh.read_text(errors="replace")
    return dict(re.findall(r"#define\s+([A-Z][A-Z0-9_]*)_S\s+\(\((\w+)_TypeDef\s*\*\)", text))


def instance_param_types(ctx: Ctx, hdr: str) -> set[str]:
    """<P> of the instance type the scope functions take: their first parameter `<P>_TypeDef *`, or the `Instance`
    member of the handle they take (ST HAL: UART_HandleTypeDef.Instance is USART_TypeDef *)."""
    out = set()
    for n in ctx.delivery["scope"]["functions"]:
        for f, line in _declared_in(ctx, n):
            text = dict(_headers_text(ctx))[f][line - 1]
            m = re.search(rf"{re.escape(n)}\s*\(\s*(?:const\s+)?(\w+)_TypeDef\s*\*", text)
            if m:
                out.add(m.group(1))
    if not out and re.search(r"\w+_HandleTypeDef", hdr):
        out |= set(re.findall(r"\b(\w+)_TypeDef\s*\*\s*Instance\s*;", hdr))
    return out


def instance(ctx: Ctx, module_headers: list[Path]) -> Fact:
    """The owner's target.instance; else the single device instance the scope statements name whose type (or direct
    `INST->` access) the scope's own headers use - the scope text also names other peripherals (RCC, EXTI, CRC...)."""
    t = (ctx.spec.get("target") or {}).get("instance")
    scope_text = " ".join(ctx.spec.get("scope") or []) if isinstance(ctx.spec.get("scope"), list) else ""
    hdr = " ".join(h.read_text(errors="replace") for h in module_headers)
    types = instance_types(ctx)
    named = sorted(i for i in types if re.search(rf"\b{re.escape(i)}\b", scope_text)
                   and (f"{types[i]}_TypeDef" in hdr or re.search(rf"\b{re.escape(i)}->", hdr)))
    typed = instance_param_types(ctx, hdr)
    if typed and any(types[i] in typed for i in named):  # the type the scope functions take (GPIO, not EXTI)
        named = [i for i in named if types[i] in typed]
    if t:
        src = Source("workorder", "target.instance", value=t)
        if named and t not in named:
            return agree("instance", "workorder_target_instance", "the scope statements name another instance than "
                         "target.instance: which one is onboarded?", src,
                         Source("workorder", "scope", value=named[0] if len(named) == 1 else named))
        return derived("instance", t, "workorder_target_instance", src)
    if len(named) == 1:
        return derived("instance", named[0], "scope_names_one_device_instance",
                       Source("workorder", "scope", value=named[0]))
    return not_derived("instance", "scope_names_one_device_instance",
                       "Which peripheral instance is onboarded? Set target.instance in the work order"
                       + (f" (the scope names {', '.join(named)})." if named else " (the scope names none)."))


# ---- base address and memory map -------------------------------------------------------------------------------
MM_ROW = re.compile(r"^\s*(0x[0-9A-Fa-f]{8})\s*-\s*0x[0-9A-Fa-f]{8}\s+(0x[0-9A-Fa-f]{8})\s*-\s*0x[0-9A-Fa-f]{8}\s+(.+?)\s{2,}\d")


def _names_instance(desc: str, inst: str) -> bool:
    """An RM Table 3 description names the instance: a token equal to it, or with the same number and a name the
    instance's letters begin (RM0486 writes TIMER2 for TIM2, SPI1/I2S1 for SPI1)."""
    mi = re.fullmatch(r"([A-Z]+)(\d*)([A-Z]?)", inst)
    toks = re.split(r"[\s/(),]+", desc.upper()) + re.split(r"[/(),]+", re.sub(r"\s+", "", desc.upper()))
    for tok in toks:
        if tok == inst:
            return True
        mt = re.fullmatch(r"([A-Z]+)(\d+)", tok)
        if mi and mt and mi.group(2) and mt.group(2) == mi.group(2) and mt.group(1).startswith(mi.group(1)) \
                and not mi.group(3):
            return True
    return False


def memory_map_row(ctx: Ctx, inst: str) -> tuple[int, int, int, str] | None:
    """(secure start, non-secure start, page, description) of the instance's Table 3 row, or None."""
    if not ctx.rm_memory_map or not ctx.rm_memory_map.is_file():
        return None
    page = None
    for line in ctx.rm_memory_map.read_text(errors="replace").splitlines():
        pm = re.match(r"^<!-- source: \S+ p\.(\d+) -->", line)
        if pm:
            page = int(pm.group(1))
        m = MM_ROW.match(line)
        if m and _names_instance(m.group(3), inst):
            return int(m.group(1), 16), int(m.group(2), 16), page, m.group(3).strip()
    return None


def base_address(ctx: Ctx, inst: str) -> list[Fact]:
    secure = bool(ctx.build.get("secure"))
    dh = device_header(ctx)
    pp = preprocess(ctx, ["stm32n6xx.h"], {"BASE": f"{inst}_BASE", "INST": inst}) if dh else None
    cm = eval_int(pp["BASE"]) if pp else None
    name = f"{inst}_BASE_{'S' if secure else 'NS'}"
    srcs = []
    if cm is not None and dh is not None:
        srcs.append(Source("file", ctx.rel(dh), line=_define_line(dh, name), value=f"0x{cm:08X}"))
    row = memory_map_row(ctx, inst)
    if row:
        srcs.append(Source("doc", ctx.rel(ctx.rm_memory_map), page=row[2],
                           value=f"0x{(row[0] if secure else row[1]):08X}"))
    out = []
    if row and cm is not None:
        out.append(agree("base_address", "cmsis_base_chain+mm_table_row",
                         f"The device header and the RM memory map give different {inst} base addresses: which is "
                         "right for this part?", *srcs))
    else:
        missing = "the RM memory-map row" if not row else "the device header definition"
        out.append(not_derived("base_address", "cmsis_base_chain+mm_table_row",
                               f"No {missing} for {inst} was found in the inputs: provide it.", *srcs))
    if row and row[2]:
        out.append(derived("mm_page", row[2], "mm_table_row",
                           Source("doc", ctx.rel(ctx.rm_memory_map), page=row[2], value=row[3])))
    else:
        out.append(not_derived("mm_page", "mm_table_row", f"No RM page of the {inst} memory-map row in the inputs."))
    return out


# ---- prefix and register index ---------------------------------------------------------------------------------
def register_prefix(ctx: Ctx, inst: str) -> Fact:
    dh = device_header(ctx)
    pp = preprocess(ctx, ["stm32n6xx.h"], {"INST": inst}) if dh else None
    m = re.search(r"\(\s*([A-Z][A-Z0-9]*)_TypeDef\s*\*\s*\)", pp["INST"]) if pp else None
    if not m:
        return not_derived("register_prefix", "instance_typedef", f"{inst} does not expand to a <P>_TypeDef pointer.")
    return derived("register_prefix", m.group(1), "instance_typedef",
                   Source("file", ctx.rel(dh), line=_define_line(dh, f"{inst}_S"), value=m.group(1)))


def _sections(ctx: Ctx) -> dict[str, tuple[str, int | None]]:
    from ..workorder import split_sections

    files, idx = split_sections(ctx.rm_chapter.read_text(errors="replace"), ctx.rm_chapter.stem.split("-")[0])
    pages = {}
    for line in idx:
        parts = [x.strip() for x in line.split(" | ")]
        if len(parts) == 4:
            pages[parts[3]] = int(parts[2][2:]) if parts[2][2:].isdigit() else None
    return {k: (v, pages.get(k)) for k, v in files.items()}


def register_index(ctx: Ctx, prefix: str) -> Fact:
    from ..assurance.hardware import parse_section

    if not ctx.rm_chapter or not ctx.rm_chapter.is_file():
        return not_derived("register_index", "rm_register_sections", "The RM chapter input is missing.")
    regs, srcs = {}, []
    for name, (text, page) in sorted(_sections(ctx).items()):
        r = parse_section(text, prefix)
        if not r:
            continue
        o = regs.setdefault(r["name"], {"offset": r["offset"], "reset": r["reset"], "fields": {}, "page": page})
        for f, d in r["fields"].items():
            o["fields"].setdefault(f, {"msb": d["msb"], "lsb": d["lsb"], "access": list(d["access"])})
        if len(srcs) < 64 and r["name"] not in {s.value for s in srcs}:
            srcs.append(Source("doc", ctx.rel(ctx.rm_chapter), page=page, value=r["name"]))
    if not regs:
        return not_derived("register_index", "rm_register_sections",
                           f"The RM chapter has no register section with the prefix {prefix}_.")
    return derived("register_index", {k: regs[k] for k in sorted(regs)}, "rm_register_sections", *srcs)


# ---- scope functions, style, headers -----------------------------------------------------------------------------
def scope_definitions(ctx: Ctx) -> dict[str, list[S.Definition]]:
    """Every definition/declaration file of each scope function in the delivered package (Src/*.c, Inc/*.h)."""
    names = list(ctx.delivery["scope"]["functions"])
    found: dict[str, list[S.Definition]] = {n: [] for n in names}
    for p in sorted(ctx.source.rglob("*")):
        if p.suffix not in (".c", ".h") or not p.is_file():
            continue
        text = p.read_text(errors="replace")
        if not any(n in text for n in names):
            continue
        for d in S.index(text, ctx.rel(p)):
            if d.name in found:
                found[d.name].append(d)
    return found


def _headers_text(ctx: Ctx) -> list[tuple[str, list[str]]]:
    cache = ctx.__dict__.setdefault("_hdr", None)
    if cache is None:
        cache = [(ctx.rel(p), p.read_text(errors="replace").splitlines()) for p in sorted(ctx.source.rglob("*.h"))]
        ctx.__dict__["_hdr"] = cache
    return cache


def _declared_in(ctx: Ctx, name: str) -> list[tuple[str, int]]:
    out = []
    rx = re.compile(rf"\b{re.escape(name)}\s*\(")
    for rel, lines in _headers_text(ctx):
        for i, line in enumerate(lines, 1):
            if name in line and rx.search(line) and line.rstrip().endswith(";") and "#define" not in line:
                out.append((rel, i))
    return out


def function_prefix(ctx: Ctx) -> Fact:
    names = ctx.delivery["scope"]["functions"]
    c = collections.Counter(m.group(0) for n in names if (m := re.match(r"[A-Za-z]+_[A-Za-z0-9]+_", n)))
    if not c:
        return not_derived("function_prefix", "scope_common_prefix", "The scope functions share no <API>_<P>_ prefix.")
    best, k = c.most_common(1)[0]
    return derived("function_prefix", best, "scope_common_prefix",
                   Source("workorder", "delivery.scope.functions", value=f"{k}/{len(names)}"))


def headers(ctx: Ctx, defs: dict[str, list[S.Definition]], prefix: str) -> Fact:
    """The module header and source of the scope (the file that defines / declares most scope functions)."""
    src_c = collections.Counter(d.file for ds in defs.values() for d in ds if d.file.endswith(".c"))
    hdr = collections.Counter(f for n in defs if n.startswith(prefix) for f, _ in _declared_in(ctx, n))
    hdr.update(d.file for ds in defs.values() for d in ds if d.file.endswith(".h") and d.kind == "static_inline")
    if not hdr:
        return not_derived("headers", "scope_defining_files", "No delivered header declares the scope functions.")
    h = hdr.most_common(1)[0][0]
    val = {"header": Path(h).name, **({"source": Path(src_c.most_common(1)[0][0]).name} if src_c else {})}
    return derived("headers", val, "scope_defining_files", Source("file", h, value=val["header"]))


def handle_type(ctx: Ctx) -> tuple[str, str] | None:
    """(handle type, header) when the scope functions take a <X>_HandleTypeDef pointer first (ST classic HAL)."""
    for n in ctx.delivery["scope"]["functions"]:
        for f, line in _declared_in(ctx, n):
            text = dict(_headers_text(ctx))[f][line - 1]
            m = re.search(rf"{re.escape(n)}\s*\(\s*(?:const\s+)?(\w+_HandleTypeDef)\s*\*", text)
            if m:
                return m.group(1), f
    return None


def instance_pointer(ctx: Ctx) -> tuple[str, str] | None:
    """(<P>_TypeDef, header) when the scope functions take the instance pointer first (ST GPIO HAL)."""
    for n in ctx.delivery["scope"]["functions"]:
        for f, line in _declared_in(ctx, n):
            m = re.search(rf"{re.escape(n)}\s*\(\s*(?:const\s+)?(\w+_TypeDef)\s*\*", dict(_headers_text(ctx))[f][line - 1])
            if m:
                return m.group(1), f
    return None


def driver_style(ctx: Ctx, prefix: str) -> Fact:
    layer = ctx.spec.get("layer")
    if prefix.startswith("LL_"):
        style = "LL"
    elif prefix.startswith("HAL_"):
        style = "HAL_STANDALONE" if ctx.delivery.get("provided_ll") is False else "HAL_ON_LL"
    else:
        return not_derived("driver_style", "scope_api_prefix", f"Unknown driver API prefix {prefix}.")
    srcs = [Source("workorder", "delivery.scope.functions", value=prefix),
            Source("workorder", "layer / delivery.provided_ll", value=f"{layer}/{ctx.delivery.get('provided_ll')}")]
    h = (handle_type(ctx) or instance_pointer(ctx)) if style == "HAL_STANDALONE" else None
    if h:
        srcs.append(Source("file", h[1], value=h[0]))
    elif style == "HAL_STANDALONE":
        return not_derived("driver_style", "scope_api_prefix", "A HAL without LL whose functions take neither a handle nor an instance pointer: "
                           "which driver style is it?", *srcs)
    return derived("driver_style", style, "scope_api_prefix", *srcs)


def module_headers(ctx: Ctx, defs: dict[str, list[S.Definition]]) -> list[Path]:
    files = {f for n in defs for f, _ in _declared_in(ctx, n)} | \
        {d.file for ds in defs.values() for d in ds if d.file.endswith(".h")}
    return [ctx.source.parent / f if f.split("/", 1)[0] == ctx.source.name else ctx.source / f for f in sorted(files)]


def derive(ctx: Ctx) -> tuple[list[Fact], dict]:
    """Slice B facts plus the intermediate values later slices need (instance, prefix, definitions)."""
    fp = function_prefix(ctx)
    defs = scope_definitions(ctx)
    facts = [fp]
    if fp.value:
        facts += [headers(ctx, defs, fp.value), driver_style(ctx, fp.value)]
    inst = instance(ctx, module_headers(ctx, defs))
    facts.append(inst)
    ctxv = {"instance": inst.value, "defs": defs, "function_prefix": fp.value, "prefix": None}
    if inst.value is None:
        return facts, ctxv
    facts += base_address(ctx, inst.value)
    pfx = register_prefix(ctx, inst.value)
    facts.append(pfx)
    ctxv["prefix"] = pfx.value
    if pfx.value:
        facts.append(register_index(ctx, pfx.value))
    return facts, ctxv


def input_records(ctx: Ctx) -> list[dict]:
    out = []
    for item in ctx.spec.get("inputs") or []:
        p = (ctx.example / item["path"]).resolve()
        if p.is_file():
            out.append({"path": f"inputs/{p.name}", "role": item["role"], "sha256": sha256_file(p)})
    return out


