"""Minimal C mutation runner (project engineering measure). Mutates one target file at a time on a scratch copy,
rebuilds the given unit test, runs it with a timeout. Killed = any FAIL / non-zero exit / timeout.
Usage: mutate.py <evidence/software dir> <target relpath> <test .c path> [extra test .c ...]"""
import re, sys, json, shutil, subprocess, tempfile, pathlib
sw, target, tests = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
OPS = [  # (name, regex, replacement)
    ("OR_TO_AND", r"\|= ", "&= "), ("CLR_TO_SET", r"&= ~", "|= "), ("NE0_TO_EQ0", r"!= 0U", "== 0U"),
    ("EQ0_TO_NE0", r"== 0U", "!= 0U"), ("LT_TO_LE", r" < ", " <= "), ("GT_TO_GE", r" > ", " >= "),
    ("OK_TO_ERROR", r"= HAL_OK;", "= HAL_ERROR;"), ("TIMEOUT_TO_OK", r"= HAL_TIMEOUT;", "= HAL_OK;"),
    ("RET1_TO_0", r"\? 1U : 0U", "? 0U : 1U"), ("DROP_CALL", r"^(\s+)(disable_osc|enable|LL_RCC_\w+)\(\);", r"\1/*dropped*/;"),
    ("INC_DROP", r"count\+\+;", ";"), ("HSI_TO_HSE_MSK", r"HSION_MSK", "HSEON_MSK"), ("HSE_TO_HSI_MSK", r"HSEON_MSK", "HSION_MSK"),
    ("ADC_TO_DMA", r"ADC12EN_MSK", "GPDMA1EN_MSK"), ("RST_ADC_TO_DMA", r"ADC12RST_MSK", "GPDMA1RST_MSK"),
    ("SR_TO_CR", r"LL_RCC_SR_OFFSET / 4U", "LL_RCC_CR_OFFSET / 4U"),
    ("ENR_TO_RSTR", r"LL_RCC_AHB1ENR_OFFSET / 4U\] (\|=|&=)", r"LL_RCC_AHB1RSTR_OFFSET / 4U] \1"),
    # register-definition faults (common-cause with test oracles that reuse these macros)
    ("DEF_BIT_SHIFT", r"(#define LL_RCC_\w+_MSK )0x0000000([1248])U", None), ("DEF_OFFSET_SHIFT", r"(#define LL_RCC_\w+_OFFSET )0x(\w+)U", None),
]
def mutants(text):
    for name, rx, rep in OPS:
        for m in re.finditer(rx, text, re.M):
            if name == "DEF_BIT_SHIFT":
                new = m.group(1) + "0x0000000%xU" % ((int(m.group(2)) << 1) & 0xF or 1)
            elif name == "DEF_OFFSET_SHIFT":
                new = m.group(1) + "0x%03XU" % (int(m.group(2), 16) + 4)
            else:
                new = m.expand(rep)
            yield name, text.count("\n", 0, m.start()) + 1, text[:m.start()] + new + text[m.end():]
src = (sw / target).read_text()
res = []
for name, line, mtext in mutants(src):
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td); shutil.copytree(sw, t / "sw"); (t / "sw" / target).write_text(mtext)
        if target.startswith("ll/"):
            shutil.copy(t / "sw" / target, t / "sw" / "include" / pathlib.Path(target).name)
        inc = sum((["-I", str(t / "sw" / d)] for d in ("include", "ll", "hal")), [])
        srcs = [str(p) for p in (t / "sw" / "src").glob("*.c") if not p.name.endswith("ll_rcc.c")]
        out = {"op": name, "line": line, "per_test": {}}
        for tc in tests:
            exe = t / ("ut_" + pathlib.Path(tc).stem)
            b = subprocess.run(["gcc", "-std=c99", "-O0", "-w", *inc, *srcs, tc, "-o", str(exe)], capture_output=True)
            if b.returncode:
                out["per_test"][tc] = "STILLBORN"; continue
            try:
                r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=5)
                out["per_test"][tc] = "KILLED" if (r.returncode or " FAIL" in r.stdout) else "SURVIVED"
            except subprocess.TimeoutExpired:
                out["per_test"][tc] = "KILLED"
        res.append(out)
print(json.dumps(res))
