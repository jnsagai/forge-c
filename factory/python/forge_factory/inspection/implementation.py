"""Deterministic SWE.3 implementation completeness (SWE3-09): the allocated design is really implemented.

Why: in r15 every HAL prototype and definition sat inside an unterminated comment and the LL header had no
functions; compile, guideline, register-map checks and the 8B inspector all passed an empty driver.
Checks (on comment-stripped code):
* every HAL_RCC_ function named in the SWE.2 requirement allocation is declared in the HAL header and
  defined (non-static, with a body) in the HAL source;
* every LL_RCC_ function the HAL calls is defined as a static inline function in the LL header, and the LL
  header defines at least one access function;
* no commented-out code (MISRA C:2012 Dir 4.4): comment text containing C declarations/statements.
"""
from __future__ import annotations

import re
from pathlib import Path

from .architecture import ARCH, _rows, _sections
from .guideline import C_STATEMENT_KEYWORDS, strip_c

HAL_H = "software/hal/stm32n6xx_hal_rcc.h"
HAL_C = "software/hal/stm32n6xx_hal_rcc.c"
LL_H = "software/ll/stm32n6xx_ll_rcc.h"
_CODE_LINE = re.compile(r"^\s*(?:static\s+|inline\s+|const\s+)*(?:void|u?int\d+_t|hal_\w+_t|ll_\w+_t|[A-Z_]+)\s*\**"
                        r"\s*[A-Za-z_]\w*\s*\([^)]*\)\s*[;{]\s*$|^\s*[A-Za-z_][\w>.\-\[\]]*\s*(?:[|&+\-]?=)[^=].*;\s*$"
                        r"|^\s*return\b.*;\s*$|^\s*[A-Za-z_]\w*\s*\([^()]*(?:\([^()]*\)[^()]*)*\)\s*;\s*$")


def allocated_functions(ws: Path, prefix: str | None = None) -> list[str]:
    from ..layer import api_prefix, layer_of

    prefix = prefix or api_prefix(layer_of(ws))  # ADR-0009: LL work orders allocate LL_RCC_ functions
    p = ws / ARCH
    if not p.is_file():
        return []
    body = next((b for h, b in _sections(p.read_text(errors="replace")).items() if re.search(r"allocation", h)), "")
    names: list[str] = []
    for row in _rows(body):
        for cell in row:
            for n in re.findall(rf"\b{prefix}\w+", cell):
                if n[len(prefix):] == n[len(prefix):].upper():  # ALL-CAPS = macro (r30: HAL_RCC_TIMEOUT_VALUE)
                    continue
                if n not in names:
                    names.append(n)
    return names


def _defs(code: str) -> dict[str, str]:
    """name -> qualifiers for function definitions (signature followed by a body)."""
    out = {}
    for m in re.finditer(r"^[ \t]*((?:static\s+|inline\s+|__STATIC_INLINE\s+|const\s+)*)([A-Za-z_]\w*)[\s*]+"
                         r"([A-Za-z_]\w*)\s*\([^;{]*?\)\s*\{", code, re.M):
        if m.group(2) not in C_STATEMENT_KEYWORDS:
            out[m.group(3)] = m.group(1)
    return out


def _protos(code: str) -> set[str]:
    return {m.group(2) for m in re.finditer(r"^[ \t]*(?:extern\s+)?([A-Za-z_]\w*)[\s*]+([A-Za-z_]\w*)\s*\([^;{]*?\)\s*;",
                                           code, re.M) if m.group(1) not in C_STATEMENT_KEYWORDS}


def commented_out_code(raw: str) -> list[int]:
    lines = []
    for m in re.finditer(r"/\*.*?(?:\*/|\Z)|//[^\n]*", raw, re.S):
        start = raw.count("\n", 0, m.start()) + 1
        for k, line in enumerate(m.group(0).splitlines()):
            text = line.lstrip("/* ").rstrip("*/ ")
            if _CODE_LINE.match(text):
                lines.append(start + k)
    return lines


def check_implementation(ws: Path) -> dict:
    from ..common import sha256_file
    from ..layer import layer_of, provided

    layer = layer_of(ws)
    if layer == "LL":
        return _check_ll(ws)
    findings: list[str] = []
    for rec in provided(ws):  # ADR-0009: the HAL work order must not change the PROVIDED, verified LL
        if not (ws / rec["path"]).is_file() or sha256_file(ws / rec["path"]) != rec["sha256"]:
            findings.append(f"IMPL:PROVIDED_COMPONENT_CHANGED:{rec['path']}")
    raw = {rel: (ws / rel).read_text(errors="replace") if (ws / rel).is_file() else None for rel in (HAL_H, HAL_C, LL_H)}
    for rel, txt in raw.items():
        if txt is None:
            findings.append(f"IMPL:MISSING_FILE:{rel}")
        else:
            findings += [f"IMPL:COMMENTED_OUT_CODE:{rel}:{n}" for n in commented_out_code(txt)[:10]]
    code = {rel: strip_c(txt) for rel, txt in raw.items() if txt is not None}
    hal_defs = _defs(code.get(HAL_C, ""))
    hal_protos = _protos(code.get(HAL_H, ""))
    ll_defs = _defs(code.get(LL_H, ""))
    wanted = allocated_functions(ws)
    if not wanted:
        findings.append("IMPL:NO_ALLOCATED_HAL_FUNCTIONS_IN_SWE2")
    for f in wanted:
        if f not in hal_protos:
            findings.append(f"IMPL:NOT_DECLARED:{f}")
        if f not in hal_defs:
            findings.append(f"IMPL:NOT_DEFINED:{f}")
        elif "static" in hal_defs[f]:
            findings.append(f"IMPL:STATIC_API:{f}")
    if not ll_defs:
        findings.append("IMPL:NO_LL_ACCESS_FUNCTIONS")
    # The register block is placed by the linker (target) / defined by the test harness (host); a driver definition
    # collides with the harness (r38). Only the extern declaration in the LL header is allowed.
    for src in sorted(ws.glob("software/**/*.c")):
        if "/tests/" in src.as_posix():
            continue
        if re.search(r"^[^\n;]*\bvolatile\s+uint32_t\s+ll_rcc_regs\s*\[", strip_c(src.read_text(errors="replace")), re.M) \
                and not re.search(r"\bextern\b[^;]*\bll_rcc_regs\b", strip_c(src.read_text(errors="replace"))):
            findings.append(f"IMPL:REG_BLOCK_DEFINED_IN_DRIVER:{src.relative_to(ws).as_posix()}")
    called = set(re.findall(r"\b(LL_RCC_\w+)\s*\(", code.get(HAL_C, "")))
    findings += [f"IMPL:LL_CALL_UNDEFINED:{f}" for f in sorted(called - set(ll_defs))]
    return {"verdict": "FAIL" if findings else "PASS", "major_findings": findings,
            "stats": {"allocated": len(wanted), "hal_defined": len([f for f in wanted if f in hal_defs]),
                      "ll_functions": len(ll_defs), "ll_calls": len(called)}}


def _reg_block_defined(ws: Path) -> list[str]:
    out = []
    for src in sorted(ws.glob("software/**/*.c")):
        if "/tests/" in src.as_posix():
            continue
        code = strip_c(src.read_text(errors="replace"))
        if re.search(r"^[^\n;]*\bvolatile\s+uint32_t\s+ll_rcc_regs\s*\[", code, re.M) \
                and not re.search(r"\bextern\b[^;]*\bll_rcc_regs\b", code):
            out.append(f"IMPL:REG_BLOCK_DEFINED_IN_DRIVER:{src.relative_to(ws).as_posix()}")
    return out


def _check_ll(ws: Path) -> dict:
    """ADR-0009 LL work order: every LL_RCC_ function allocated in SWE.2 is a static inline definition in the LL
    header; no commented-out code; the register block is only declared (extern)."""
    findings: list[str] = []
    p = ws / LL_H
    if not p.is_file():
        findings.append(f"IMPL:MISSING_FILE:{LL_H}")
        txt = ""
    else:
        txt = p.read_text(errors="replace")
        findings += [f"IMPL:COMMENTED_OUT_CODE:{LL_H}:{n}" for n in commented_out_code(txt)[:10]]
    ll_defs = _defs(strip_c(txt))
    wanted = allocated_functions(ws, "LL_RCC_")
    if not wanted:
        findings.append("IMPL:NO_ALLOCATED_LL_FUNCTIONS_IN_SWE2")
    for f in wanted:
        if f not in ll_defs:
            findings.append(f"IMPL:NOT_DEFINED:{f}")
        elif not ("static" in ll_defs[f] and "inline" in ll_defs[f]):
            findings.append(f"IMPL:LL_NOT_STATIC_INLINE:{f}")
    if not ll_defs:
        findings.append("IMPL:NO_LL_ACCESS_FUNCTIONS")
    # CAPA-008 (r81): the LL is exactly the allocated register access - no extra helpers (HAL_RCC_PollSet,
    # LL_RCC_*_WaitReady), no HAL code and no waiting; unrequired functions drew SWE.5/6 tests and defects
    if wanted:
        findings += [f"IMPL:LL_NOT_ALLOCATED:{f}" for f in sorted(set(ll_defs) - set(wanted))]
    code = strip_c(txt)
    findings += [f"IMPL:HAL_CODE_IN_LL:{n}" for n in sorted(set(re.findall(r"\bHAL_\w+", code)))][:10]
    findings += [f"IMPL:LL_WAITS:{code.count(chr(10), 0, m.start()) + 1}"
                 for m in re.finditer(r"\b(?:while|for)\s*\(|\bdo\s*\{", code)][:10]
    # CAPA-019 (r84): the author replaced the generated register block by a pointer API; the unit harness, regmap and
    # measurement all use the extern array, and SWE.2/SWE.3 contradicted each other until the loop budget ran out
    if txt and not re.search(r"\bextern\s+volatile\s+uint32_t\s+ll_rcc_regs\s*\[[^\]]+\]", code):
        findings.append("IMPL:LL_REG_BLOCK_DECLARATION_MISSING")
    for m in re.finditer(r"^[ \t]*static\s+inline\s+[\w\s*]+?\b(LL_RCC_\w+)\s*\(([^)]*)\)\s*\{", code, re.M):
        if m.group(2).strip() not in ("void", ""):
            findings.append(f"IMPL:LL_SIGNATURE_NOT_VOID:{m.group(1)}")
    findings += _reg_block_defined(ws)
    return {"verdict": "FAIL" if findings else "PASS", "major_findings": findings,
            "stats": {"allocated": len(wanted), "ll_defined": len([f for f in wanted if f in ll_defs]),
                      "ll_functions": len(ll_defs)}}
