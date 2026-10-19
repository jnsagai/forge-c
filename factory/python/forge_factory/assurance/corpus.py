"""EASA-T066/T067 — correct-versus-defective corpus: detection and false-positive measurement with real tools.

Subject: the sealed HAL r102 package (HAL source + provided LL header + its own unit/integration tests), copied.
Each variant injects ONE realistic defect class into the copy; detectors:
  factory  the package's own host unit + integration tests (as sealed), built with gcc and run
  easa     independent register-define and register-write checks (RM index), the requirement/RM-derived oracle
           (set/clear, timeout rollback + poll bound, invalid parameter) and the clang analyzer/warnings
  formal   CBMC bounded proof + Frama-C Eva over the public API (runtime errors, bounded termination only); kept as
           a separate column so the v2 easa numbers stay comparable
A detector "catches" a variant if it reports a failure that it does not report on the unmodified copy; findings on
the unmodified copy are false positives. Nothing here touches the archive.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from . import formal, hardware, oracle_gen, shadow

LL = "software/ll/stm32n6xx_ll_rcc.h"
HAL = "software/hal/stm32n6xx_hal_rcc.c"
VARIANTS = [  # id, file, old, new, defect class
    ("D01", LL, "#define LL_RCC_CR_HSEON_MSK 0x00000010U", "#define LL_RCC_CR_HSEON_MSK 0x00000020U",
     "wrong bit in generated register definition"),
    ("D02", LL, "ll_rcc_regs[LL_RCC_AHB1ENR_OFFSET / 4U] |= LL_RCC_AHB1ENR_ADC12EN_MSK",
     "ll_rcc_regs[LL_RCC_AHB1ENR_OFFSET / 4U] = LL_RCC_AHB1ENR_ADC12EN_MSK", "write clobbers other bits (= for |=)"),
    ("D03", LL, "ll_rcc_regs[LL_RCC_AHB1ENR_OFFSET / 4U] |= LL_RCC_AHB1ENR_GPDMA1EN_MSK",
     "ll_rcc_regs[LL_RCC_AHB1RSTR_OFFSET / 4U] |= LL_RCC_AHB1ENR_GPDMA1EN_MSK", "wrong register (RSTR for ENR)"),
    ("D04", HAL, "return HAL_RCC_osc_enable(timeout, LL_RCC_HSE_Enable, LL_RCC_HSE_Disable,",
     "return HAL_RCC_osc_enable(timeout, LL_RCC_HSI_Enable, LL_RCC_HSE_Disable,", "swapped oscillator (HSI for HSE)"),
    ("D05", HAL, "while ((count < timeout) && (status != HAL_OK))", "while ((count <= timeout) && (status != HAL_OK))",
     "polling bound off by one"),
    ("D06", HAL, "            disable_osc();", "            /* rollback omitted */", "no rollback of the enable bit on timeout"),
    ("D07", HAL, "if ((timeout == 0U) || (timeout > HAL_RCC_TIMEOUT_VALUE))", "if (timeout > HAL_RCC_TIMEOUT_VALUE)",
     "missing parameter check (timeout 0 accepted)"),
    ("D08", LL, "  if ((ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] & LL_RCC_SR_HSERDY_MSK) != 0U)",
     "  ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] = 0U;\n  if ((ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] & LL_RCC_SR_HSERDY_MSK) != 0U)",
     "write to the read-only status register"),
    ("D09", HAL, "    hal_status_t status = HAL_TIMEOUT;", "    hal_status_t status;", "uninitialised status variable"),
    ("D10", LL, "ll_rcc_regs[LL_RCC_AHB1RSTR_OFFSET / 4U] &= ~LL_RCC_AHB1RSTR_GPDMA1RST_MSK",
     "ll_rcc_regs[LL_RCC_AHB1RSTR_OFFSET / 4U] &= ~LL_RCC_AHB1RSTR_ADC12RST_MSK", "release clears the wrong reset bit"),
]


def _factory_tests(ws: Path) -> list[str]:
    out = []
    inc = ["-I", str(ws / "software/hal"), "-I", str(ws / "software/ll")]
    for t in ("software/tests/unit/test_rcc.c", "software/tests/integration/test_rcc_integration.c"):
        tp = ws / t
        if not tp.is_file():
            continue
        exe = ws / ("x_" + tp.stem)
        b = subprocess.run(["gcc", "-std=c99", "-O0", "-w", *inc, str(ws / HAL), str(tp), "-o", str(exe)],
                           capture_output=True, text=True)
        if b.returncode:
            out.append(f"BUILD_FAIL:{tp.name}")
            continue
        try:
            r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
            out += [f"{tp.name}:{ln.split()[0]}" for ln in r.stdout.splitlines() if ln.endswith(" FAIL")]
            if r.returncode and not any(x.startswith(tp.name) for x in out):
                out.append(f"{tp.name}:exit {r.returncode}")
        except subprocess.TimeoutExpired:
            out.append(f"{tp.name}:timeout")
    return out


def _easa(ws: Path) -> dict[str, list[str]]:
    idx = hardware.index(ws / "inputs/sections/RM0486")
    hdr = (ws / LL).read_text()
    found = {"register_checks": hardware.check_defines(hdr, idx) +
             [x for x in hardware.check_writes(hdr + (ws / HAL).read_text(), hdr, idx)
              if not x.startswith("NON_ATOMIC_RMW")]}
    r = oracle_gen.run(ws, [ws / "software/hal", ws / "software/ll"], [ws / HAL], "stm32n6xx_hal_rcc.h")
    found["oracle"] = [f"{x[0]}:{x[1]}:{x[2]}" for x in r.get("results", []) if x[3] == "FAIL"] + \
        ([f"BUILD:{r.get('reason', '')[:80]}"] if r["status"] == "BUILD_FAILED" else [])
    an = []
    for tool in (["clang", "--analyze", "-std=c11", "-Xanalyzer", "-analyzer-output=text", "-o", "/dev/null"],
                 ["clang", "-fsyntax-only", "-std=c11", "-Wall", "-Wextra", "-Wuninitialized",
                  "-Wsometimes-uninitialized", "-Wconditional-uninitialized"]):
        p = subprocess.run([*tool, "-I", str(ws / "software/hal"), "-I", str(ws / "software/ll"), str(ws / HAL)],
                           capture_output=True, text=True)
        an += [ln.split(": warning: ")[1][:90] for ln in p.stderr.splitlines() if ": warning: " in ln]
    found["analyzers"] = an
    return found


def _formal(ws: Path) -> list[str]:
    c, e = formal.cbmc(ws), formal.eva(ws)
    out = [f for f in c.get("findings", []) + e.get("findings", []) if not f.startswith("LIMITATION")]
    return out + [f"{n}:{r['status']}" for n, r in (("cbmc", c), ("eva", e)) if r["status"] not in ("PASS", "FAIL")]


def run(zip_path: Path, inputs_from: Path) -> dict:
    with tempfile.TemporaryDirectory() as td:
        x = Path(td) / "x"
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(x)
        base = shadow._workspace_from_package(x, inputs_from)
        (base / "software/hal").mkdir(exist_ok=True)
        ref_f, ref_e, ref_x = _factory_tests(base), _easa(base), _formal(base)
        rows = []
        for vid, rel, old, new, cls in VARIANTS:
            ws = Path(td) / vid
            shutil.copytree(base, ws)
            p = ws / rel
            t = p.read_text()
            if old not in t:
                rows.append({"id": vid, "class": cls, "status": "NOT_APPLICABLE", "reason": "pattern absent"})
                continue
            p.write_text(t.replace(old, new, 1))
            f = [x for x in _factory_tests(ws) if x not in ref_f]
            e = {k: [x for x in v if x not in ref_e.get(k, [])] for k, v in _easa(ws).items()}
            fx = [x for x in _formal(ws) if x not in ref_x]
            rows.append({"id": vid, "class": cls, "factory_detected": bool(f), "factory_evidence": f[:4],
                         "easa_detected": any(e.values()), "easa_by": sorted(k for k, v in e.items() if v),
                         "easa_evidence": {k: v[:3] for k, v in e.items() if v},
                         "formal_detected": bool(fx), "formal_evidence": fx[:4]})
    applicable = [r for r in rows if "factory_detected" in r]
    return {"subject": str(zip_path.name), "variants": rows,
            "false_positives_on_correct": {"factory": ref_f, **{k: v for k, v in ref_e.items() if v},
                                           **({"formal": ref_x} if ref_x else {})},
            "summary": {"variants": len(applicable),
                        "factory_caught": sum(r["factory_detected"] for r in applicable),
                        "easa_caught": sum(r["easa_detected"] for r in applicable),
                        "formal_caught": sum(r["formal_detected"] for r in applicable),
                        "either": sum(r["factory_detected"] or r["easa_detected"] for r in applicable),
                        "neither": [r["id"] for r in applicable if not (r["factory_detected"] or r["easa_detected"])],
                        "easa_only": [r["id"] for r in applicable if r["easa_detected"] and not r["factory_detected"]],
                        "factory_only": [r["id"] for r in applicable if r["factory_detected"] and not r["easa_detected"]]}}


