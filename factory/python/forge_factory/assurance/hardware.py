"""EASA-T033/T035/T036/T038 and AT-038/AT-084 — register access semantics from the baselined reference manual.

Independent of `inspection/regmap.py` (which generates AND checks the LL defines with one parser — common-cause
finding F-02): this module parses the RM section files itself, including the per-bit ACCESS row of the bit diagram,
and checks the C code's register writes against it:
  RO_REGISTER_WRITE / RO_FIELD_WRITE   write to a register/field whose RM access is read-only (r)
  RESERVED_BIT_WRITE / UNKNOWN_FIELD   a written mask touches reserved bits or names no RM field
  UNKNOWN_REGISTER                     an offset that is not an RM register
  NON_ATOMIC_RMW                       read-modify-write where the RM provides atomic set/clear registers (concurrency)
Errata are NOT baselined for this project: every errata-dependent conclusion is UNKNOWN, never assumed clean.
Simulator semantics are compared with the RM and differences are reported (Renode is not silicon or HIL).
"""
from __future__ import annotations

import re
from pathlib import Path

ACCESS = {"r", "w", "rw", "rs", "rc_w1", "rc_w0", "rc_r", "t", "w1", "rt_w1", "rt_w0", "rw1"}
WRITEABLE = {"w", "rw", "rs", "rc_w1", "rc_w0", "w1", "rt_w1", "rt_w0", "rw1", "t"}


def _bit_columns(line: str) -> dict[int, int] | None:
    toks = list(re.finditer(r"\d+", line))
    if len(toks) != 16 or line.strip(" 0123456789") != "":
        return None
    return {int(m.group(0)): (m.start() + m.end()) // 2 for m in toks}


def _register_name(text: str, prefix: str) -> str | None:
    name = re.search(rf"^#+ .*\(({prefix}_[A-Z0-9_]+)\)\s*$", text, re.M)
    if name or prefix == "RCC":  # RCC: the exact heading rule only (results unchanged)
        return name.group(1) if name else None
    # feature 015: multi-instance registers named by the RM placeholder (GPIOx_MODER, TIMx_CR1), optionally with the
    # instances "(x = ...)", maybe wrapped onto the first lines after the heading -> CMSIS form (GPIO_MODER, TIM_CR1).
    # Written here separately from inspection.regmap on purpose (independent parser, finding F-02).
    head = "\n".join(text.splitlines()[:6])
    m = re.search(rf"^(?:#+ .*|[ \t]*)\(({prefix})x?(_[A-Z0-9_]+)\)\s*(?:\(\s*x\s*=[^)]*\)\s*)?$", head, re.M)
    return m.group(1) + m.group(2) if m else None


def parse_section(text: str, prefix: str = "RCC") -> dict | None:
    name = _register_name(text, prefix)
    off = re.search(r"Address offset:\s*(0x[0-9a-fA-F]+)", text)
    if not (name and off):
        return None
    reset = re.search(r"Reset value:\s*(0x[0-9a-fA-F]{4}\s?[0-9a-fA-F]{4})", text)
    if prefix != "RCC":  # feature 015: per-port values (the first, port A) and 16-bit registers ('0x0000')
        reset = re.search(r"Reset value:\s*Port [A-Z]:\s*(0x[0-9a-fA-F]{4}\s?[0-9a-fA-F]{4})", text) or reset or \
            re.search(r"Reset value:\s*(0x[0-9a-fA-F]{4})\s*$", text, re.M)
    fields: dict[str, dict] = {}
    for m in re.finditer(r"^\s*Bits?\s+(\d+)(?::(\d+))?\s+([A-Z][A-Z0-9_]*)(?:\[\d+(?::\d+)?\])?\s*:", text, re.M):
        msb, lsb = int(m.group(1)), int(m.group(2) or m.group(1))
        if lsb <= msb <= 31:
            fields.setdefault(m.group(3), {"msb": msb, "lsb": lsb, "access": set()})
    # feature 015: one line for every pin of a port ('Bits 31:0 MODEy[1:0]: ... pin y (y = 15 to 0)') -> MODE0..MODE15
    for m in re.finditer(r"^\s*Bits?\s+(\d+):(\d+)\s+([A-Z][A-Z0-9_]*?)y(?:\[\d+(?::\d+)?\])?\s*:.*?"
                         r"\(y\s*=\s*(\d+)\s+to\s+(\d+)\)", text, re.M):
        msb, lsb, n = int(m.group(1)), int(m.group(2)), abs(int(m.group(4)) - int(m.group(5))) + 1
        y0 = min(int(m.group(4)), int(m.group(5)))  # GPIOx_AFRH: AFSELy (y = 15 to 8) starts at pin 8
        width = (msb - lsb + 1) // n if msb >= lsb else 0
        if width and width * n == msb - lsb + 1:
            for y in range(n):
                fields.setdefault(f"{m.group(3)}{y0 + y}", {"msb": lsb + (y + 1) * width - 1, "lsb": lsb + y * width,
                                                            "access": set()})
    # Repeated single-bit fields can list strided positions rather than a contiguous range. The GPIO advanced
    # configuration tables wrap the low four positions onto the following line (RETy: 31,27,...,7,3).
    for m in re.finditer(r"^[ \t]*Bits?[ \t]+((?:\d+[ \t]*,[ \t]*)+\d+[ \t]*,?)[ \t]+"
                         r"([A-Z][A-Z0-9_]*?)y[ \t]*:[^\n]*?\(y\s*=\s*(\d+)\s+to\s+(\d+)\)", text, re.M):
        positions = [int(bit) for bit in re.findall(r"\d+", m.group(1))]
        first, last = int(m.group(3)), int(m.group(4))
        count = abs(first - last) + 1
        end = text.find("\n", m.end())
        if len(positions) < count and end >= 0:
            continuation = re.match(r"[ \t]*(\d+(?:[ \t]*,[ \t]*\d+)+)\b", text[end + 1:])
            if continuation:
                positions += [int(bit) for bit in re.findall(r"\d+", continuation.group(1))]
        if len(positions) != count or len(set(positions)) != count or any(bit > 31 for bit in positions):
            continue  # incomplete/ambiguous declarations remain unknown; never fill a guessed stride
        step = 1 if last >= first else -1
        for pin, bit in zip(range(first, last + step, step), positions, strict=True):
            fields.setdefault(f"{m.group(2)}{pin}", {"msb": bit, "lsb": bit, "access": set()})
    access_by_bit: dict[int, str] = {}
    lines = text.splitlines()
    cols = None
    for line in lines:
        c = _bit_columns(line)
        if c:
            cols = c
            continue
        toks = [m for m in re.finditer(r"\S+", line)]
        if cols and toks and all(t.group(0) in ACCESS for t in toks):
            for t in toks:
                center = (t.start() + t.end()) // 2
                bit = min(cols, key=lambda b: abs(cols[b] - center))
                access_by_bit[bit] = t.group(0)
    for f in fields.values():
        f["access"] = sorted({access_by_bit[b] for b in range(f["lsb"], f["msb"] + 1) if b in access_by_bit})
    used = 0
    for f in fields.values():
        used |= ((1 << (f["msb"] - f["lsb"] + 1)) - 1) << f["lsb"]
    return {"name": name, "offset": int(off.group(1), 16),
            "reset": int(reset.group(1).replace(" ", ""), 16) if reset else None, "fields": fields,
            "reserved_mask": (~used) & 0xFFFFFFFF, "access_by_bit": access_by_bit,
            "read_only": bool(access_by_bit) and all(a == "r" for a in access_by_bit.values())}


def _prefix_of(sections_dir: Path) -> str:
    """Feature 009: RM register prefix of the work order owning <ws>/inputs/sections/<DOC> (RCC by default)."""
    from ..layer import register_prefix

    ws = Path(sections_dir).parents[2] if len(Path(sections_dir).parents) > 2 else None
    return register_prefix(ws) if ws is not None and (ws / ".forge-run/manifest.json").is_file() else "RCC"


def index(sections_dir: Path, prefix: str | None = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    prefix = prefix or _prefix_of(sections_dir)
    for p in sorted(Path(sections_dir).glob("*.md")):
        r = parse_section(p.read_text(errors="replace"), prefix)
        if r and r["name"] not in out:
            out[r["name"]] = r
        elif r and prefix != "RCC":  # feature 015: an "[alternate]" description of the same register (USART_ISR with
            o = out[r["name"]]       # FIFO disabled: TXE/RXNE for TXFNF/RXFNE) adds its field names for the same bits
            for k, v in r["fields"].items():
                o["fields"].setdefault(k, v)
            used = 0
            for f in o["fields"].values():
                used |= ((1 << (f["msb"] - f["lsb"] + 1)) - 1) << f["lsb"]
            o["reserved_mask"] = (~used) & 0xFFFFFFFF
    return out


def set_clear_aliases(idx: dict[str, dict]) -> dict[str, tuple[str, str]]:
    """RCC_CR -> (RCC_CSR, RCC_CCR), RCC_AHB1ENR -> (RCC_AHB1ENSR, RCC_AHB1ENCR) ... where the RM provides them."""
    out = {}
    for n in idx:
        if n == "RCC_CR" and "RCC_CSR" in idx and "RCC_CCR" in idx:
            out[n] = ("RCC_CSR", "RCC_CCR")
        m = re.match(r"RCC_(\w+?)(ENR|RSTR|LPENR)$", n)
        if m:
            s, c = f"RCC_{m.group(1)}{m.group(2)[:-1]}SR", f"RCC_{m.group(1)}{m.group(2)[:-1]}CR"
            if s in idx and c in idx:
                out[n] = (s, c)
    return out


# ---- code scan -------------------------------------------------------------------------------------------------
def prefix_of_index(idx: dict[str, dict]) -> str:
    """Feature 009: the RM register prefix of an index (IWDG_KR -> IWDG); RCC for an empty index."""
    return next(iter(idx)).split("_", 1)[0] if idx else "RCC"


def define_rx(prefix: str = "RCC") -> re.Pattern:
    """Numeric LL_<PPP>_ defines of an LL header."""
    return re.compile(rf"^\s*#\s*define\s+(LL_{prefix}_\w+)\s+\(?\s*(0x[0-9A-Fa-f]+|\d+)U?L?\s*\)?", re.M)


def write_rx(block: str = "ll_rcc_regs") -> re.Pattern:
    """Writes through the LL register-block array (ADR-0009), e.g. ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = ..."""
    return re.compile(rf"{re.escape(block)}\s*\[\s*([^\]]+?)\s*\]\s*(\|=|&=|=)(?!=)\s*([^;]+);")


def block_of(prefix: str) -> str:
    """The register-block name of a prefix by the profile convention (ll_rcc_regs, ll_iwdg_regs)."""
    return f"ll_{prefix.lower()}_regs"


DEFINE = define_rx("RCC")
WRITE = write_rx("ll_rcc_regs")


def _eval_index(expr: str, defs: dict[str, int]) -> int | None:
    e = expr
    for k, v in sorted(defs.items(), key=lambda kv: -len(kv[0])):
        e = re.sub(rf"\b{k}\b", str(v), e)
    e = re.sub(r"(\d+)[uUlL]+\b", r"\1", e)
    if not re.fullmatch(r"[\d\s()+*/x0-9A-Fa-f-]+", e):
        return None
    try:
        return int(eval(e.replace("/", "//"), {"__builtins__": {}}))  # noqa: S307 - digits/operators only
    except Exception:  # noqa: BLE001
        return None


def scan_writes(code: str, header_defs: str, prefix: str = "RCC", block: str | None = None) -> list[dict]:
    defs = {m.group(1): int(m.group(2), 0) for m in define_rx(prefix).finditer(header_defs)}
    out = []
    for m in write_rx(block or block_of(prefix)).finditer(code):
        word = _eval_index(m.group(1), defs)
        rhs = m.group(3)
        masks = re.findall(rf"LL_{prefix}_\w+_MSK", rhs)
        lit = [] if masks else [int(re.sub(r"[uUlL]+$", "", x), 0)
                                for x in re.findall(r"\b(?:0x[0-9A-Fa-f]+|\d+)[uUlL]*\b", rhs)]
        value = 0
        for mk in masks:
            value |= defs.get(mk, 0)
        for v in lit:
            value |= v
        out.append({"line": code.count("\n", 0, m.start()) + 1, "word": word, "op": m.group(2), "masks": masks,
                    "value": value, "text": m.group(0)[:120]})
    return out


def check_writes(code: str, header_defs: str, idx: dict[str, dict], block: str | None = None) -> list[str]:
    """`block`: the register-block array (feature 009: the work order's profile; default by the prefix convention)."""
    by_off = {r["offset"]: r for r in idx.values()}
    aliases = set_clear_aliases(idx)
    p = prefix_of_index(idx)
    f = []
    for w in scan_writes(code, header_defs, p, block):
        if w["word"] is None:
            f.append(f"UNRESOLVED_REGISTER_INDEX:line {w['line']}")
            continue
        reg = by_off.get(w["word"] * 4)
        if reg is None:
            f.append(f"UNKNOWN_REGISTER:offset 0x{w['word'] * 4:X}:line {w['line']}")
            continue
        if reg["read_only"]:
            f.append(f"RO_REGISTER_WRITE:{reg['name']}:line {w['line']}")
            continue
        touched = w["value"]
        if touched & reg["reserved_mask"]:
            f.append(f"RESERVED_BIT_WRITE:{reg['name']}:0x{touched & reg['reserved_mask']:08X}:line {w['line']}")
        for b in range(32):
            if touched >> b & 1 and b in reg["access_by_bit"] and reg["access_by_bit"][b] not in WRITEABLE:
                f.append(f"RO_FIELD_WRITE:{reg['name']}:bit {b}:line {w['line']}")
        known = {f"LL_{p}_{reg['name'][len(p) + 1:]}_{fld}_MSK" for fld in reg["fields"]}
        for mk in w["masks"]:
            if mk not in known:
                f.append(f"UNKNOWN_FIELD:{mk}:for {reg['name']}:line {w['line']}")
        if w["op"] in ("|=", "&=") and reg["name"] in aliases:
            s, c = aliases[reg["name"]]
            f.append(f"NON_ATOMIC_RMW:{reg['name']}:line {w['line']}:RM provides {s}/{c}")
    return f


def errata_status(ws: Path) -> dict:
    """Errata are part of the hardware baseline only if the work-order inputs list them."""
    man = Path(ws) / "inputs" / "inputs-manifest.json"
    import json

    docs = json.loads(man.read_text())["documents"] if man.is_file() else []
    er = [d for d in docs if re.search(r"\bES\d{4}|errata", f"{d.get('doc', '')} {d.get('markdown', '')}", re.I)]
    return {"status": "BASELINED" if er else "UNKNOWN", "documents": [d.get("doc") for d in er],
            "consequence": None if er else "errata-dependent behaviour is UNKNOWN (no errata sheet in the inputs)"}


SIM_READY = re.compile(r"READY_MASK\s*=\s*(0x[0-9A-Fa-f]+)|RCC_SR.*?RCC_CR\s*&\s*(0x[0-9A-Fa-f]+)", re.S)


def simulator_mismatches(model_text: str, idx: dict[str, dict]) -> list[str]:
    """AT-084: compare the behavioural Renode RCC model with the RM (ready-flag derivation, reset values, set/clear
    registers). Every difference is a fidelity limitation of simulated evidence, never hidden. Feature 009: the
    comparison rules exist for the RCC model only; another peripheral's model is reported not comparable."""
    out = []
    if idx and prefix_of_index(idx) != "RCC":
        return [f"SIMULATOR_MODEL_NOT_COMPARABLE:no RM comparison rule for the {prefix_of_index(idx)} model "
                "(LIMITATION: the model is not checked against the RM)"]
    m = SIM_READY.search(model_text)
    sr, cr = idx.get("RCC_SR"), idx.get("RCC_CR")
    if not (m and sr and cr):
        return ["SIMULATOR_MODEL_NOT_COMPARABLE"]
    model_mask = int(m.group(1) or m.group(2), 16)
    rm_mask = 0
    for f, d in sr["fields"].items():
        on = f.replace("RDY", "ON")
        if f.endswith("RDY") and on in cr["fields"] and cr["fields"][on]["lsb"] == d["lsb"]:
            rm_mask |= 1 << d["lsb"]
    if model_mask != rm_mask:
        out.append(f"SIMULATOR_MISMATCH:RCC_SR ready mask model 0x{model_mask:X} != RM 0x{rm_mask:X}")
    zero_reset = bool(re.search(r"regs\.get\(\s*\w+\s*,\s*0\s*\)|every register starts at 0", model_text, re.I))
    if zero_reset:
        for name in ("RCC_CR", "RCC_SR", "RCC_AHB1ENR", "RCC_AHB1RSTR"):
            r = idx.get(name)
            if r and r["reset"]:
                out.append(f"SIMULATOR_MISMATCH:{name} reset value model 0x0 != RM 0x{r['reset']:08X}")
    aliases = set_clear_aliases(idx)
    for reg, (s_, c_) in sorted(aliases.items()):
        if reg in ("RCC_CR", "RCC_AHB1ENR", "RCC_AHB1RSTR"):
            so, co = idx[s_]["offset"], idx[c_]["offset"]
            if f"0x{so:03X}".lower() not in model_text.lower() and f"0x{so:x}" not in model_text.lower():
                out.append(f"SIMULATOR_MISMATCH:{s_}/{c_} (0x{so:X}/0x{co:X}) not modelled as set/clear of {reg}")
    return out


def check_defines(header: str, idx: dict[str, dict]) -> list[str]:
    """Independent re-check of LL_<PPP>_<REG>_OFFSET/_<FIELD>_POS/_MSK defines against the RM index (a different
    parser than inspection/regmap.py, which generates AND checks the defines - common-cause finding F-02). The prefix
    is the index's (feature 009)."""
    f = []
    p = prefix_of_index(idx)
    for name, val in re.findall(rf"#\s*define\s+(LL_{p}_\w+)\s+\(?\s*(0x[0-9A-Fa-f]+|\d+)U?L?\s*\)?", header):
        m = re.match(rf"LL_{p}_([A-Z0-9]+)_(OFFSET|([A-Z0-9]+)_(POS|MSK))$", name)
        if not m:
            continue
        v, reg = int(val, 0), idx.get(f"{p}_" + m.group(1))
        if reg is None:
            f.append(f"DEFINE_UNKNOWN_REGISTER:{name}")
            continue
        if m.group(2) == "OFFSET":
            if v != reg["offset"]:
                f.append(f"DEFINE_MISMATCH:{name}:0x{v:X}!=0x{reg['offset']:X}")
            continue
        fld = reg["fields"].get(m.group(3))
        if fld is None:
            f.append(f"DEFINE_UNKNOWN_FIELD:{name}")
            continue
        want = fld["lsb"] if m.group(4) == "POS" else ((1 << (fld["msb"] - fld["lsb"] + 1)) - 1) << fld["lsb"]
        if v != want:
            f.append(f"DEFINE_MISMATCH:{name}:0x{v:X}!=0x{want:X}")
    return f
