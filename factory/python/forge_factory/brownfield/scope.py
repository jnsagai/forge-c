"""Deterministic C facts for delivered code: function/macro index, constant-macro evaluation and register effects.

No compiler is involved; the index is a lexical scan good enough for driver headers and sources (functions,
`static inline` / `__STATIC_INLINE` functions, function-like macros). Comments are blanked (line numbers kept) and
`#if 0` blocks are skipped. Register effects are extracted for two code styles (research R6):

* forge style - `ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U] |= M`, `&= ~M`, `= M`, and reads of the same;
* CMSIS style - `WRITE_REG/SET_BIT/CLEAR_BIT/MODIFY_REG/READ_BIT/READ_REG(RCC->X, M)` and `RCC->X op= M`.

Set/clear alias registers (RCC_CSR/CCR, *ENSR/*ENCR, *RSTSR/*RSTCR) are mapped onto the bits of their base register,
so an effect reads as "set RCC_CR bit 3" whichever register the code used."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

IDENT = r"[A-Za-z_][A-Za-z0-9_]*"


@dataclass
class Definition:
    name: str
    file: str
    line: int
    kind: str                  # function | static_inline | macro
    params: list[str] = field(default_factory=list)
    body: str = ""


def strip_comments(src: str) -> str:
    """Blank /* */ and // comments and string literals' content, keeping newlines (line numbers stay valid)."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", src[i:j]))
            i = j
        elif src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            out.append(c + re.sub(r"[^\n]", " ", src[i + 1:j]) + (c if j < n else ""))
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _skip_if0(src: str) -> str:
    """Blank `#if 0 ... #endif` blocks (nesting-aware), keeping newlines."""
    lines, out, depth = src.split("\n"), [], 0
    for ln in lines:
        s = ln.strip()
        if depth:
            if re.match(r"#\s*if", s):
                depth += 1
            elif re.match(r"#\s*endif", s):
                depth -= 1
            out.append("")
            continue
        if re.match(r"#\s*if\s+0\b", s):
            depth = 1
            out.append("")
            continue
        out.append(ln)
    return "\n".join(out)


def _blank_directives(src: str) -> str:
    """Blank every preprocessor line, continuation lines included, keeping line breaks and offsets."""
    out, cont = [], False
    for ln in src.split("\n"):
        if cont or ln.lstrip().startswith("#"):
            cont = ln.rstrip().endswith("\\")
            out.append(" " * len(ln))
        else:
            out.append(ln)
    return "\n".join(out)


def _join_continuations(src: str) -> list[tuple[int, str]]:
    """Logical preprocessor lines: (first line number, text) with backslash continuations joined."""
    res, buf, start = [], [], 0
    for no, ln in enumerate(src.split("\n"), 1):
        if not buf:
            start = no
        if ln.rstrip().endswith("\\"):
            buf.append(ln.rstrip()[:-1])
            continue
        buf.append(ln)
        res.append((start, " ".join(buf)))
        buf = []
    return res


FUNC_HEAD = re.compile(rf"(?P<quals>(?:\b(?:static|inline|__inline|__STATIC_INLINE|__STATIC_FORCEINLINE|__INLINE|extern|const|"
                       rf"volatile|unsigned|signed|struct|enum)\b\s*)*)(?P<ret>{IDENT}(?:\s*\*+\s*|\s+))(?P<name>{IDENT})\s*"
                       rf"\((?P<params>[^;{{}}()]*(?:\([^()]*\)[^;{{}}()]*)*)\)\s*\{{")
KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "do", "else"}


def index(text: str, file: str) -> list[Definition]:
    """Function and function-like-macro definitions of one C file."""
    src = _skip_if0(strip_comments(text))
    defs: list[Definition] = []
    for no, ln in _join_continuations(src):
        m = re.match(rf"\s*#\s*define\s+({IDENT})\(([^)]*)\)\s*(.*)$", ln)
        if m:
            defs.append(Definition(m.group(1), file, no, "macro",
                                   [p.strip() for p in m.group(2).split(",") if p.strip()], m.group(3).strip()))
    code = _blank_directives(src)
    for m in FUNC_HEAD.finditer(code):
        name = m.group("name")
        if name in KEYWORDS or m.group("ret").strip() in KEYWORDS:
            continue
        open_at = m.end() - 1
        depth, j = 0, open_at
        while j < len(code):
            if code[j] == "{":
                depth += 1
            elif code[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        quals = m.group("quals")
        kind = "static_inline" if re.search(r"inline|INLINE", quals) else "function"
        params = [p.strip().split()[-1].lstrip("*") for p in m.group("params").split(",")
                  if p.strip() and p.strip() != "void"]
        defs.append(Definition(name, file, code.count("\n", 0, m.start("name")) + 1, kind, params,
                               code[open_at + 1:j]))
    return defs


def constant_macros(texts: list[str]) -> dict[str, str]:
    """Object-like #define NAME value from the given files (later files do not override earlier ones)."""
    out: dict[str, str] = {}
    for text in texts:
        for _no, ln in _join_continuations(_skip_if0(strip_comments(text))):
            m = re.match(rf"\s*#\s*define\s+({IDENT})(?!\()\s+(.+?)\s*$", ln)
            if m and m.group(1) not in out:
                out[m.group(1)] = m.group(2)
    return out


_SAFE = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.BitOr, ast.BitAnd, ast.BitXor, ast.LShift,
         ast.RShift, ast.Invert, ast.Add, ast.Sub, ast.Mult, ast.USub, ast.UAdd)


def _fold_position(expr: str, macros: dict[str, str], depth: int) -> str | None:
    """CMSIS POSITION_VAL(x) / __CLZ(__RBIT(x)) of a constant x: the index of its lowest set bit (32 for 0)."""
    while True:
        m = re.search(r"\b(?:POSITION_VAL|__CLZ\s*\(\s*__RBIT)\s*\(", expr)
        if not m:
            return expr
        j, d = m.end(), 1
        while j < len(expr) and d:
            d += {"(": 1, ")": -1}.get(expr[j], 0)
            j += 1
        if d:
            return None
        inner = expr[m.end():j - 1]
        end = j
        if m.group(0).startswith("__CLZ"):  # the outer __CLZ( closes after __RBIT(...)
            k = re.match(r"\s*\)", expr[j:])
            if not k:
                return None
            end = j + k.end()
        v = evaluate(inner, macros, depth + 1, intrinsics=True)
        if v is None:
            return None
        expr = expr[:m.start()] + f"({(v & -v).bit_length() - 1 if v else 32})" + expr[end:]


def evaluate(expr: str, macros: dict[str, str], depth: int = 0, intrinsics: bool = False) -> int | None:
    """Integer value of a constant C expression built from literals, casts and object-like macros (None if unknown).
    `intrinsics` (feature 015, outside RCC): POSITION_VAL / __CLZ(__RBIT()) of a constant are folded too (ST GPIO:
    MODIFY_REG(GPIOx->MODER, GPIO_MODER_MODE0 << (POSITION_VAL(Pin) * 2U), ...) with the pin bound)."""
    if depth > 20:
        return None
    if intrinsics:
        expr = _fold_position(expr, macros, depth)
        if expr is None:
            return None
    e = re.sub(r"\(\s*(?:const\s+)?(?:volatile\s+)?u?int(?:8|16|32|64)_t\s*\)", "", expr)
    e = re.sub(r"\(\s*unsigned(?:\s+(?:int|long))?\s*\)", "", e)
    e = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", e)

    def sub(m: re.Match) -> str:
        name = m.group(0)
        if name not in macros:
            raise KeyError(name)
        v = evaluate(macros[name], macros, depth + 1, intrinsics)
        if v is None:
            raise KeyError(name)
        return f"({v})"
    try:
        e = re.sub(rf"(?<![0-9A-Za-z_]){IDENT}", sub, e)
        tree = ast.parse(e.strip(), mode="eval")
    except (KeyError, SyntaxError):
        return None
    if not all(isinstance(n, _SAFE) for n in ast.walk(tree)):
        return None
    try:
        return int(eval(compile(tree, "<c-const>", "eval"), {"__builtins__": {}}, {})) & 0xFFFFFFFF  # noqa: S307 - AST checked above
    except Exception:  # noqa: BLE001
        return None


_COND = _SAFE + (ast.Compare, ast.BoolOp, ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt,
                 ast.GtE)


def condition(expr: str, macros: dict[str, str]) -> bool | None:
    """Truth of a constant C condition (comparisons, &&, ||, !) once arguments are bound; None if undecidable.
    Feature 015 (BENCH-USART-ST-R4): branch selection for register-effect extraction."""
    e = re.sub(r"\(\s*(?:const\s+)?(?:volatile\s+)?u?int(?:8|16|32|64)_t\s*\)", "", expr)
    e = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", e)

    def sub(m: re.Match) -> str:
        v = evaluate(m.group(0), macros, intrinsics=True)
        if v is None:
            raise KeyError(m.group(0))
        return f"({v})"
    try:
        e = re.sub(rf"(?<![0-9A-Za-z_]){IDENT}", sub, e)
        e = e.replace("&&", " and ").replace("||", " or ")
        e = re.sub(r"!(?!=)", " not ", e)
        tree = ast.parse(e.strip(), mode="eval")
    except (KeyError, SyntaxError):
        return None
    if not all(isinstance(n, _COND) for n in ast.walk(tree)):
        return None
    try:
        return bool(eval(compile(tree, "<c-cond>", "eval"), {"__builtins__": {}}, {}))  # noqa: S307 - AST checked above
    except Exception:  # noqa: BLE001
        return None


def _balanced(s: str, i: int, open_: str, close: str) -> int:
    """Index just past the bracket group that opens at s[i] (== open_), or -1."""
    depth = 0
    for j in range(i, len(s)):
        depth += s[j] == open_
        depth -= s[j] == close
        if depth == 0:
            return j + 1
    return -1


def _prune(body: str, macros: dict[str, str]) -> str:
    """Keep only the branch a braced if / else if / else chain takes when the bound arguments decide its conditions
    (ST LL_USART_SetBaudRate: an invalid prescaler or a zero baud rate selects an empty branch, so BRR is not written).
    A chain stops being pruned at its first undecidable condition: from there every branch is kept (no write hidden)."""
    out, pos = [], 0
    for m in re.finditer(r"(?<![\w])if\s*\(", body):
        if m.start() < pos or body[:m.start()].rstrip().endswith("else"):
            continue  # an 'else if' continues the chain of an earlier 'if': never a chain of its own
        branches, j, tail = [], m.start(), None
        while True:
            c0 = body.index("(", j)
            c1 = _balanced(body, c0, "(", ")")
            b0 = c1 + len(body[c1:]) - len(body[c1:].lstrip())
            if c1 < 0 or b0 >= len(body) or body[b0] != "{":
                branches = []
                break
            b1 = _balanced(body, b0, "{", "}")
            if b1 < 0:
                branches = []
                break
            branches.append((body[c0 + 1:c1 - 1], body[b0:b1]))
            j = b1
            nxt = re.match(r"\s*else\s+if\s*\(", body[j:])
            if nxt:
                j += nxt.end() - 1
                continue
            els = re.match(r"\s*else\s*\{", body[j:])
            if els:
                e0 = j + els.end() - 1
                e1 = _balanced(body, e0, "{", "}")
                if e1 < 0:
                    branches = []
                    break
                tail, j = body[e0:e1], e1
            break
        if not branches:
            continue
        keep: list[str] | None = []
        for cond, blk in branches:
            v = condition(cond, macros)
            if v is None:
                keep = None
                break
            if v:
                keep.append(blk)
                break
        else:
            if tail is not None:
                keep.append(tail)
        if keep is None:
            continue
        out.append(body[pos:m.start()] + " ".join(keep))
        pos = j
    return "".join(out) + body[pos:]


ALIAS = [(re.compile(r"^RCC_CSR$"), "RCC_CR", "set"), (re.compile(r"^RCC_CCR$"), "RCC_CR", "clear"),
         (re.compile(r"^(RCC_\w+EN)SR$"), r"\1R", "set"), (re.compile(r"^(RCC_\w+EN)CR$"), r"\1R", "clear"),
         (re.compile(r"^(RCC_\w+RST)SR$"), r"\1R", "set"), (re.compile(r"^(RCC_\w+RST)CR$"), r"\1R", "clear")]


def alias_of(register: str) -> tuple[str, str] | None:
    """(base register, 'set'|'clear') for an RCC set/clear alias register, else None."""
    for pat, base, op in ALIAS:
        if pat.match(register):
            return pat.sub(base, register), op
    return None


CMSIS_BIT_MACROS = {"WRITE_REG", "SET_BIT", "CLEAR_BIT", "MODIFY_REG", "READ_BIT", "READ_REG"}
ARRAY_AS = {("AFR", "0"): "AFRL", ("AFR", "1"): "AFRH"}
# stm32n6xx.h exclusive-access (LDREX/STREX) forms, read like their plain macros (feature 015, outside RCC)
ATOMIC_AS = {"ATOMIC_SET_BIT": "SET_BIT", "ATOMIC_CLEAR_BIT": "CLEAR_BIT", "ATOMIC_MODIFY_REG": "MODIFY_REG",
             "ATOMIC_SETH_BIT": "SET_BIT", "ATOMIC_CLEARH_BIT": "CLEAR_BIT", "ATOMIC_MODIFYH_REG": "MODIFY_REG"}


@dataclass
class Effect:
    register: str              # base register after alias mapping, e.g. RCC_CR
    op: str                    # set | clear | write | read | modify
    mask: int | None           # bit mask (None: not a constant)
    via: str = ""              # the register the code actually accessed (alias)
    text: str = ""
    clear: int | None = None   # MODIFY_REG's clear mask (op modify; mask is then the value written)


def _bind(body: str, params: list[str], args: list[str]) -> str:
    for p, a in zip(params, args, strict=False):  # fewer args than params: the rest stay unbound
        body = re.sub(rf"\b{re.escape(p)}\b", f"({a})", body)
    return body


def _split_args(s: str) -> list[str]:
    out, depth, cur = [], 0, []
    for ch in s:
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def register_effects(defn: Definition, macros: dict[str, str], style: str, args: list[str] | None = None,
                     defs: dict[str, Definition] | None = None, depth: int = 0, prefix: str = "RCC") -> list[Effect]:
    """Register effects of one function or macro, with arguments bound; follows calls into other delivered
    definitions (one level per call, up to 4 levels). `prefix` is the work order's RM register prefix (feature 015:
    the RCC-only patterns missed ST's CRC/SPI code, which reaches the registers through an instance pointer such as
    `CRCx->CR` or `(CRC)->CR` once the argument is bound, and writes 8/16-bit data registers through a cast)."""
    body = _bind(defn.body, defn.params, args or [])
    pfx = prefix
    effects: list[Effect] = []
    if pfx != "RCC" and args:  # feature 015: the branch the bound arguments select (RCC extraction unchanged)
        for _ in range(8):
            pruned = _prune(body, macros)
            if pruned == body:
                break
            body = pruned

    if pfx != "RCC":  # CMSIS register arrays: GPIOx->AFR[0]/[1] are RM0486's GPIOx_AFRL/AFRH (others: name + index)
        body = re.sub(r"->\s*(\w+)\s*\[\s*(\d+)U?\s*\]", lambda m: "->" + ARRAY_AS.get((m.group(1), m.group(2)),
                                                                                    m.group(1) + m.group(2)), body)

    def ev(x: str | None) -> int | None:
        return None if x is None else evaluate(x, macros, intrinsics=pfx != "RCC")

    def eff(reg: str, op: str, mask_expr: str | None, text: str) -> None:
        mask = ev(mask_expr)
        al = alias_of(reg)
        if al and op in ("write", "set"):
            effects.append(Effect(al[0], al[1], mask, reg, text))
        else:
            effects.append(Effect(reg, op, mask, "", text))

    if style == "forge":
        acc = re.compile(rf"ll_{pfx.lower()}_regs\s*\[\s*LL_{pfx}_({IDENT}?)_OFFSET\s*/\s*4U?\s*\]")
        for m in re.finditer(acc.pattern + r"\s*(\|=|&=|=(?!=))\s*([^;]+);", body):
            reg, op, rhs = f"{pfx}_" + m.group(1), m.group(2), m.group(3).strip()
            if op == "|=":
                eff(reg, "set", rhs, m.group(0))
            elif op == "&=":
                inner = re.sub(r"^~\s*", "", rhs.strip())
                eff(reg, "clear" if rhs.strip().startswith("~") else "modify", inner, m.group(0))
            else:
                eff(reg, "write", rhs, m.group(0))
        writes = {m.start() for m in re.finditer(acc.pattern + r"\s*(\|=|&=|=(?!=))", body)}
        for m in acc.finditer(body):
            if m.start() not in writes:
                effects.append(Effect(f"{pfx}_" + m.group(1), "read", None, "", m.group(0)))
    else:
        # RCC: the global instance exactly as before; other peripherals: the instance or its pointer parameter, with
        # or without the parentheses of a bound argument (CRC, CRCx, (CRC), SPI1, SPIx, ...)
        reg_ref = rf"RCC\s*->\s*({IDENT})" if pfx == "RCC" else rf"\(*\s*{pfx}\w*\s*\)*\s*->\s*({IDENT})"
        names = "WRITE_REG|SET_BIT|CLEAR_BIT|MODIFY_REG|READ_BIT|READ_REG"
        if pfx != "RCC":  # CMSIS exclusive-access forms (ST USART: ATOMIC_MODIFY_REG(USARTx->CR1, RE | TE, dir))
            names = "ATOMIC_(?:SETH?_BIT|CLEARH?_BIT|MODIFYH?_REG)|" + names
        macro_rx = rf"\b({names})\s*\(\s*{reg_ref}\s*(?:,([^;]*))?\)\s*;?"
        for m in re.finditer(macro_rx, body):
            macro, reg = ATOMIC_AS.get(m.group(1), m.group(1)), f"{pfx}_" + m.group(2)
            rest = _split_args(m.group(3) or "")
            if macro == "WRITE_REG":
                eff(reg, "write", rest[0] if rest else None, m.group(0))
            elif macro == "SET_BIT":
                eff(reg, "set", rest[0] if rest else None, m.group(0))
            elif macro == "CLEAR_BIT":
                eff(reg, "clear", rest[0] if rest else None, m.group(0))
            elif macro == "MODIFY_REG":
                eff(reg, "modify", rest[1] if len(rest) > 1 else None, m.group(0))
                effects[-1].clear = ev(rest[0]) if rest else None
            else:
                effects.append(Effect(reg, "read", evaluate(rest[0], macros) if rest else None, "", m.group(0)))
        for m in re.finditer(rf"{reg_ref}\s*(\|=|&=|=(?!=))\s*([^;]+);", body):
            reg, op, rhs = f"{pfx}_" + m.group(1), m.group(2), m.group(3).strip()
            if op == "|=":
                eff(reg, "set", rhs, m.group(0))
            elif op == "&=":
                eff(reg, "clear" if rhs.startswith("~") else "modify", re.sub(r"^~\s*", "", rhs), m.group(0))
            else:
                eff(reg, "write", rhs, m.group(0))
        if pfx != "RCC":  # 8/16-bit data register access through a cast: *((__IO uint8_t *)&SPIx->TXDR) = v
            cast = (rf"\*\s*\(\s*\(\s*(?:__IO\s+|volatile\s+)?uint(?:8|16|32)_t(?:\s+__IO|\s+volatile)?\s*\*\s*\)"
                    rf"\s*\(?\s*&\s*{reg_ref}\s*\)?\s*\)")
            for m in re.finditer(cast + r"\s*=(?!=)\s*([^;]+);", body):
                eff(f"{pfx}_" + m.group(1), "write", m.group(2).strip(), m.group(0))
            writes = {m.start() for m in re.finditer(cast + r"\s*=(?!=)", body)}
            for m in re.finditer(cast, body):
                if m.start() not in writes:
                    effects.append(Effect(f"{pfx}_" + m.group(1), "read", None, "", m.group(0)))
    if defs and depth < 4:  # calls into other delivered functions/macros
        for m in re.finditer(rf"\b({IDENT})\s*\(", body):
            callee = defs.get(m.group(1))
            if callee is None or callee.name == defn.name:
                continue
            if pfx != "RCC" and (callee.name in CMSIS_BIT_MACROS or callee.name in ATOMIC_AS):  # read semantically
                continue  # above; expanding MODIFY_REG's own WRITE_REG would add a mask-less whole-register write (015)
            j, d = m.end(), 1
            while j < len(body) and d:
                d += {"(": 1, ")": -1}.get(body[j], 0)
                j += 1
            effects += register_effects(callee, macros, style, _split_args(body[m.end():j - 1]), defs, depth + 1,
                                        prefix)
    return effects


def bits(mask: int | None) -> list[int]:
    return [] if mask is None else [b for b in range(32) if mask >> b & 1]
